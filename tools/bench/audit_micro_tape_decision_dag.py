#!/usr/bin/env python3
"""Replay TuringOS Micro Tape bundles and build an auditable decision DAG.

The auditor reads Git Micro Tape bundles as truth. It intentionally separates
structural replay from constitutional protocol replay and economic timing, so a
bundle can be readable/replayable without being over-claimed as a full protocol
PASS.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVENT_REGISTRY_PATH = REPO_ROOT / "pack" / "04_registries" / "event_registry_v5_3_1.json"
SEVERITY_ORDER = {"PASS": 0, "INFO": 0, "LEGACY_MISSING": 1, "NOT_TESTED": 1, "WARN": 2, "PARTIAL": 2, "FAIL": 3}
CRITICAL_REPLAY_CHECKS = {
    "bundle_integrity",
    "git_topology",
    "canonical_payload_hash",
    "ref_reconstruction",
    "registry_head_effect",
    "accepted_head_authority",
}


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def redacted_stream_evidence(text: str) -> dict[str, Any]:
    data = text.encode("utf-8")
    return {
        "sha256": "sha256:" + hashlib.sha256(data).hexdigest(),
        "byte_length": len(data),
        "redacted": True,
    }


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"duplicate JSON key {key!r}")
        output[key] = value
    return output


def json_loads_strict(text: str) -> Any:
    return json.loads(text, object_pairs_hook=reject_duplicate_keys)


def load_json(path: Path) -> dict[str, Any]:
    data = json_loads_strict(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def ascii_keys(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str) or any(ord(ch) > 127 for ch in key):
                return False
            if not ascii_keys(child):
                return False
    elif isinstance(value, list):
        return all(ascii_keys(item) for item in value)
    return True


def has_float(value: Any) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, dict):
        return any(has_float(child) for child in value.values())
    if isinstance(value, list):
        return any(has_float(item) for item in value)
    return False


def canonical_bytes(value: Any) -> bytes:
    """Return canonical bytes for the current load-bearing JSON subset.

    TuringOS load-bearing payloads forbid floats and non-ASCII keys. For that
    constrained subset, sorted-key compact JSON bytes are stable and match the
    current benchmark tape payload profile. The auditor refuses to hash payloads
    outside that subset instead of silently impersonating a broader codec.
    """

    if not ascii_keys(value):
        raise ValueError("non-ASCII load-bearing key")
    if has_float(value):
        raise ValueError("float in load-bearing payload")
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_payload_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_json(value: Any) -> str:
    """Compatibility alias used by tests and older audit fixtures."""

    return canonical_payload_digest(value)


def load_event_registry(path: Path | None = None) -> dict[str, dict[str, Any]]:
    registry_path = path or DEFAULT_EVENT_REGISTRY_PATH
    raw = load_json(registry_path)
    events = raw.get("events")
    if not isinstance(events, list):
        raise ValueError(f"{registry_path} does not contain an events list")
    registry: dict[str, dict[str, Any]] = {}
    for item in events:
        if not isinstance(item, dict):
            raise ValueError(f"{registry_path} contains a non-object event row")
        name = item.get("canonical_name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"{registry_path} contains an event row without canonical_name")
        registry[name] = {
            "event_class": item.get("event_class"),
            "head_effect": item.get("head_effect"),
            "target_ref": item.get("target_ref"),
            "predicate_required": item.get("predicate_required"),
            "payload_schema_id": item.get("payload_schema_id"),
        }
    return registry


def run_git(args: list[str], *, git_dir: Path | None = None, cwd: Path | None = None) -> str:
    cmd = ["git"]
    if git_dir is not None:
        cmd.append(f"--git-dir={git_dir}")
    cmd.extend(args)
    result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=True)
    return result.stdout


def run_git_maybe(args: list[str], *, git_dir: Path | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    cmd = ["git"]
    if git_dir is not None:
        cmd.append(f"--git-dir={git_dir}")
    cmd.extend(args)
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)


def bundles_from_coverage(path: Path) -> list[Path]:
    coverage = load_json(path)
    bundles: list[Path] = []
    for run in coverage.get("turingos_arm_runs", []):
        if not isinstance(run, dict):
            continue
        bundle = run.get("micro_tape_bundle")
        if isinstance(bundle, str):
            bundles.append(Path(bundle))
    return bundles


def fetch_bundle(bundle: Path, work_dir: Path) -> tuple[Path, str]:
    bundle = bundle.resolve()
    if not bundle.exists():
        raise FileNotFoundError(bundle)
    git_dir = work_dir / (bundle.parent.name + ".git")
    if git_dir.exists():
        shutil.rmtree(git_dir)
    run_git(["init", "--bare", "--object-format=sha256", str(git_dir)])
    verify_output = run_git(["bundle", "verify", str(bundle)])
    run_git(["fetch", "--quiet", str(bundle), "refs/*:refs/*"], git_dir=git_dir)
    return git_dir, verify_output


def ref_oid(git_dir: Path, ref: str) -> str | None:
    result = run_git_maybe(["rev-parse", "--verify", ref], git_dir=git_dir)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def mu(oid: str | None) -> str | None:
    return "mu:" + oid if oid else None


def read_event_chain(git_dir: Path) -> list[dict[str, Any]]:
    raw_oids = run_git(["rev-list", "--reverse", "refs/turingos/tape_tip"], git_dir=git_dir).split()
    events: list[dict[str, Any]] = []
    for oid in raw_oids:
        raw_event = run_git(["show", f"{oid}:event"], git_dir=git_dir)
        event = json_loads_strict(raw_event)
        if not isinstance(event, dict):
            raise ValueError(f"{oid}:event is not an object")
        event["_oid"] = oid
        event["_event_id"] = "mu:" + oid
        events.append(event)
    return events


def commit_parents(git_dir: Path, oid: str) -> list[str]:
    raw = run_git(["cat-file", "-p", oid], git_dir=git_dir)
    parents: list[str] = []
    for line in raw.splitlines():
        if line.startswith("parent "):
            parents.append(line.split(" ", 1)[1])
    return parents


def validate_git_topology(git_dir: Path, events: list[dict[str, Any]], actual_refs: dict[str, str | None]) -> tuple[bool, list[str], dict[str, Any]]:
    problems: list[str] = []
    evidence: dict[str, Any] = {}

    fsck = run_git_maybe(["fsck", "--strict"], git_dir=git_dir)
    evidence["git_fsck_strict_returncode"] = fsck.returncode
    evidence["git_fsck_strict_stdout_digest"] = redacted_stream_evidence(fsck.stdout.strip())
    evidence["git_fsck_strict_stderr_digest"] = redacted_stream_evidence(fsck.stderr.strip())
    if fsck.returncode != 0:
        problems.append("git fsck --strict failed")

    object_format = run_git_maybe(["rev-parse", "--show-object-format"], git_dir=git_dir)
    evidence["object_format"] = object_format.stdout.strip()
    if object_format.returncode != 0 or object_format.stdout.strip() != "sha256":
        problems.append(f"git object-format {object_format.stdout.strip()!r} != sha256")

    if actual_refs.get("tape_tip") is None:
        problems.append("refs/turingos/tape_tip missing")
    if actual_refs.get("accepted_head") is None:
        problems.append("refs/turingos/accepted_head missing")

    previous_oid: str | None = None
    for idx, event in enumerate(events):
        event_id = event["_event_id"]
        oid = event["_oid"]
        parents = commit_parents(git_dir, oid)
        if idx == 0:
            if parents:
                problems.append(f"{event_id}: genesis commit parent count {len(parents)} != 0")
            if event.get("prev_tape_tip") is not None:
                problems.append(f"{event_id}: genesis commit parent mismatch: event prev_tape_tip is non-null")
        else:
            if len(parents) != 1:
                problems.append(f"{event_id}: commit parent count {len(parents)} != 1")
            elif parents[0] != previous_oid:
                problems.append(f"{event_id}: commit parent {parents[0]} != previous event oid {previous_oid}")
            payload_prev = event.get("prev_tape_tip")
            expected_prev = mu(parents[0]) if parents else None
            if payload_prev != expected_prev:
                problems.append(f"{event_id}: commit parent does not match event prev_tape_tip")
        previous_oid = oid

    tape_tip_oid = actual_refs.get("tape_tip")
    accepted_oid = actual_refs.get("accepted_head")
    if tape_tip_oid and accepted_oid:
        result = run_git_maybe(
            ["merge-base", "--is-ancestor", accepted_oid.removeprefix("mu:"), tape_tip_oid.removeprefix("mu:")],
            git_dir=git_dir,
        )
        if result.returncode != 0:
            problems.append("accepted_head is not an ancestor of tape_tip")
    authorization_oid = actual_refs.get("authorization_head")
    if tape_tip_oid and authorization_oid:
        result = run_git_maybe(
            ["merge-base", "--is-ancestor", authorization_oid.removeprefix("mu:"), tape_tip_oid.removeprefix("mu:")],
            git_dir=git_dir,
        )
        if result.returncode != 0:
            problems.append("authorization_head is not an ancestor of tape_tip")

    return not problems, problems, evidence


def short_event(event: dict[str, Any]) -> str:
    oid = str(event["_oid"])[:7]
    seq = event.get("sequence")
    return f"e{seq}_{oid}_{event.get('event_type')}"


def node_id(event: dict[str, Any]) -> str:
    return f"{event.get('sequence')}:{event.get('event_type')}:{str(event['_oid'])[:12]}"


def index_events(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for event in events:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        for key in ["capsule_id", "receipt_id", "macro_id", "evidence_id", "market_id", "candidate_id"]:
            value = payload.get(key)
            if isinstance(value, str):
                index.setdefault(key + ":" + value, event)
    return index


def add_edge(edges: list[dict[str, str]], source: dict[str, Any], target: dict[str, Any], kind: str) -> None:
    edges.append({"from": source["_event_id"], "to": target["_event_id"], "kind": kind})


def build_dag_edges(events: list[dict[str, Any]]) -> list[dict[str, str]]:
    index = index_events(events)
    edges: list[dict[str, str]] = []
    for prev, cur in zip(events, events[1:]):
        add_edge(edges, prev, cur, "tape_parent")
    by_id = {event["_event_id"]: event for event in events}
    for event in events:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        event_type = event.get("event_type")
        capsule_id = payload.get("capsule_id")
        if event_type != "WorkCapsuleBuilt" and isinstance(capsule_id, str):
            source = index.get("capsule_id:" + capsule_id)
            if source is not None:
                add_edge(edges, source, event, "capsule_ref")
        market_id = payload.get("market_id")
        if event_type != "MarketCreated" and isinstance(market_id, str):
            source = index.get("market_id:" + market_id)
            if source is not None:
                add_edge(edges, source, event, "market_ref")
        receipt_id = payload.get("worker_receipt_id")
        if isinstance(receipt_id, str):
            source = index.get("receipt_id:" + receipt_id)
            if source is not None:
                add_edge(edges, source, event, "receipt_ref")
        macro_id = payload.get("macro_anchor_id")
        if isinstance(macro_id, str):
            source = index.get("macro_id:" + macro_id)
            if source is not None:
                add_edge(edges, source, event, "macro_ref")
        evidence_id = payload.get("official_evaluator_evidence_id")
        if isinstance(evidence_id, str):
            source = index.get("evidence_id:" + evidence_id)
            if source is not None:
                add_edge(edges, source, event, "official_evidence_to_accept")
        for basis_key in ["settlement_event_id", "settlement_basis_event_id", "basis_event_id", "terminal_event_id"]:
            basis = payload.get(basis_key)
            if isinstance(basis, str) and basis in by_id:
                add_edge(edges, by_id[basis], event, basis_key)
        for parent in payload.get("parent_event_hashes", []) if isinstance(payload.get("parent_event_hashes"), list) else []:
            if isinstance(parent, str) and parent in by_id:
                add_edge(edges, by_id[parent], event, "parent_event_hash")
    return edges


def derive_refs(events: list[dict[str, Any]], registry: dict[str, dict[str, Any]]) -> dict[str, str | None]:
    accepted_head: str | None = None
    tape_tip: str | None = None
    authorization_head: str | None = None
    for event in events:
        event_id = event["_event_id"]
        tape_tip = event_id
        row = registry.get(str(event.get("event_type")))
        if row is None:
            continue
        if event.get("predicate_product") != "PASS":
            continue
        if row["event_class"] == "SOVEREIGN_ACCEPT":
            accepted_head = event_id
        elif row["event_class"] == "AUTHORIZATION":
            authorization_head = event_id
    return {
        "accepted_head": accepted_head,
        "authorization_head": authorization_head,
        "tape_tip": tape_tip,
    }


def validate_chain(
    events: list[dict[str, Any]],
    actual_refs: dict[str, str | None],
    registry: dict[str, dict[str, Any]],
) -> tuple[bool, list[str], dict[str, str]]:
    problems: list[str] = []
    categories: dict[str, str] = {
        "canonical_payload_hash": "PASS",
        "ref_reconstruction": "PASS",
        "registry_head_effect": "PASS",
        "authorization_head": "PASS",
        "accepted_head_authority": "PASS",
    }
    accepted_head: str | None = None
    authorization_head: str | None = None
    previous: str | None = None
    required_fields = [
        "writer_id",
        "authority_epoch",
        "prev_tape_tip",
        "accepted_head_before",
        "head_effect",
        "event_schema_id",
        "payload_hash",
    ]

    for expected_sequence, event in enumerate(events):
        event_id = event["_event_id"]
        for field in required_fields:
            if field not in event:
                problems.append(f"{event_id}: missing required append field {field}")
                categories["registry_head_effect"] = "FAIL"
        if event.get("sequence") != expected_sequence:
            problems.append(f"{event_id}: sequence {event.get('sequence')} != {expected_sequence}")
            categories["ref_reconstruction"] = "FAIL"
        if event.get("prev_tape_tip") != previous:
            problems.append(f"{event_id}: prev_tape_tip mismatch")
            categories["ref_reconstruction"] = "FAIL"
        if event.get("accepted_head_before") != accepted_head:
            problems.append(f"{event_id}: accepted_head_before mismatch")
            categories["accepted_head_authority"] = "FAIL"
        if "authorization_head_before" in event and event.get("authorization_head_before") != authorization_head:
            problems.append(f"{event_id}: authorization_head_before mismatch")
            categories["authorization_head"] = "FAIL"

        event_type = event.get("event_type")
        row = registry.get(str(event_type))
        if row is None:
            problems.append(f"{event_id}: unknown event_type {event_type!r}")
            categories["registry_head_effect"] = "FAIL"
        else:
            if event.get("head_effect") != row["head_effect"]:
                problems.append(f"{event_id}: head_effect {event.get('head_effect')} != registry {row['head_effect']}")
                categories["registry_head_effect"] = "FAIL"
            if event.get("event_schema_id") != row["payload_schema_id"]:
                problems.append(
                    f"{event_id}: event_schema_id {event.get('event_schema_id')} != registry {row['payload_schema_id']}"
                )
                categories["registry_head_effect"] = "FAIL"
            if row["head_effect"] == "ADVANCE" and event.get("predicate_product") != "PASS":
                problems.append(f"{event_id}: ADVANCE registry event without predicate PASS")
                categories["registry_head_effect"] = "FAIL"

        try:
            payload_hash = canonical_payload_digest(event.get("payload"))
        except ValueError as exc:
            problems.append(f"{event_id}: {exc}")
            categories["canonical_payload_hash"] = "FAIL"
        else:
            if event.get("payload_hash") != payload_hash:
                problems.append(f"{event_id}: payload_hash mismatch")
                categories["canonical_payload_hash"] = "FAIL"
            if event.get("content_digest") not in {None, payload_hash}:
                problems.append(f"{event_id}: content_digest mismatch")
                categories["canonical_payload_hash"] = "FAIL"
        if not ascii_keys(event):
            problems.append(f"{event_id}: non-ASCII load-bearing key")
            categories["canonical_payload_hash"] = "FAIL"
        if has_float(event):
            problems.append(f"{event_id}: float in load-bearing payload")
            categories["canonical_payload_hash"] = "FAIL"

        if row and event.get("predicate_product") == "PASS":
            if row["event_class"] == "SOVEREIGN_ACCEPT":
                accepted_head = event_id
            elif row["event_class"] == "AUTHORIZATION":
                authorization_head = event_id
        previous = event_id

    derived_refs = derive_refs(events, registry)
    for key, value in derived_refs.items():
        if value != actual_refs.get(key):
            if key == "authorization_head" and value is None and actual_refs.get(key) is None:
                continue
            problems.append(f"{key}: derived {value} != actual {actual_refs.get(key)}")
            if key == "authorization_head":
                categories["authorization_head"] = "FAIL"
            elif key == "accepted_head":
                categories["accepted_head_authority"] = "FAIL"
            else:
                categories["ref_reconstruction"] = "FAIL"
    if actual_refs.get("authorization_head") is None and derived_refs.get("authorization_head") is None:
        categories["authorization_head"] = "LEGACY_MISSING"
    return not any(value == "FAIL" for value in categories.values()), problems, categories


def event_summary(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    return {
        "event_id": event["_event_id"],
        "node_id": node_id(event),
        "short_id": str(event["_oid"])[:7],
        "sequence": event.get("sequence"),
        "event_type": event.get("event_type"),
        "head_effect": event.get("head_effect"),
        "predicate_product": event.get("predicate_product"),
        "writer_id": event.get("writer_id"),
        "authority_epoch": event.get("authority_epoch"),
        "capsule_id": payload.get("capsule_id"),
        "market_id": payload.get("market_id"),
        "result": payload.get("result"),
        "progress": payload.get("progress"),
        "failure_class": payload.get("failure_class"),
        "basis_event_id": payload.get("basis_event_id") or payload.get("settlement_basis_event_id"),
        "terminal_event_id": payload.get("terminal_event_id"),
    }


def accepted_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        event
        for event in events
        if event.get("event_type") == "CandidateAccepted" and event.get("predicate_product") == "PASS"
    ]


def terminal_accepted_event(events: list[dict[str, Any]], actual_accepted_head: str | None) -> dict[str, Any] | None:
    if actual_accepted_head is None:
        return None
    return next(
        (
            event
            for event in events
            if event["_event_id"] == actual_accepted_head
            and event.get("event_type") == "CandidateAccepted"
            and event.get("predicate_product") == "PASS"
        ),
        None,
    )


def first_candidate_accepted_event(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    matches = accepted_events(events)
    if not matches:
        return None
    return min(matches, key=lambda event: int(event.get("sequence", 0)))


def path_class(events: list[dict[str, Any]], actual_accepted_head: str | None = None) -> str:
    accepted = [
        event
        for event in events
        if event.get("event_type") == "CandidateAccepted" and event.get("predicate_product") == "PASS"
    ]
    official_pass = [
        event
        for event in events
        if event.get("event_type") == "OfficialEvaluatorEvidenceImported"
        and isinstance(event.get("payload"), dict)
        and event["payload"].get("result") == "PASS"
    ]
    official_fail = [
        event
        for event in events
        if event.get("event_type") == "OfficialEvaluatorEvidenceImported"
        and isinstance(event.get("payload"), dict)
        and event["payload"].get("result") == "FAIL"
    ]
    failures = [event for event in events if event.get("event_type") == "FailureNode"]
    terminal = terminal_accepted_event(events, actual_accepted_head)
    terminal_seq = terminal.get("sequence") if terminal is not None else None
    if (
        terminal is not None
        and isinstance(terminal_seq, int)
        and official_pass
        and terminal_seq > min(event["sequence"] for event in official_pass)
    ):
        return "accepted_path"
    if not accepted and (official_fail or failures):
        return "failed_path"
    return "incomplete_path"


def golden_path(events: list[dict[str, Any]], actual_accepted_head: str | None) -> list[dict[str, Any]]:
    terminal = terminal_accepted_event(events, actual_accepted_head)
    if path_class(events, actual_accepted_head) != "accepted_path" or terminal is None:
        return []
    accepted_seq = int(terminal.get("sequence"))
    wanted = {
        "GoalStateProposed",
        "WorkCapsuleBuilt",
        "WorkerReceiptImported",
        "MacroObservationImported",
        "OfficialEvaluatorEvidenceImported",
        "CandidateAccepted",
    }
    return [
        event_summary(event)
        for event in events
        if event.get("event_type") in wanted and isinstance(event.get("sequence"), int) and event.get("sequence") <= accepted_seq
    ]


def execution_findings(events: list[dict[str, Any]], actual_accepted_head: str | None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    official_terminal_seq = [
        event.get("sequence")
        for event in events
        if event.get("event_type") == "OfficialEvaluatorEvidenceImported"
        and isinstance(event.get("payload"), dict)
        and event["payload"].get("result") in {"PASS", "FAIL"}
    ]
    official_pass_seq = [
        event.get("sequence")
        for event in events
        if event.get("event_type") == "OfficialEvaluatorEvidenceImported"
        and isinstance(event.get("payload"), dict)
        and event["payload"].get("result") == "PASS"
    ]
    terminal_accept = terminal_accepted_event(events, actual_accepted_head)
    terminal_accept_seq = terminal_accept.get("sequence") if terminal_accept is not None else None
    accepted_seq = [event.get("sequence") for event in accepted_events(events)]
    if official_pass_seq and accepted_seq and min(accepted_seq) > min(official_pass_seq):
        findings.append(
            {
                "finding": "official_evidence_precedes_accept",
                "severity": "INFO",
                "detail": "CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.",
            }
        )

    official_terminal_min_seq = min(official_terminal_seq) if official_terminal_seq else None
    if official_terminal_min_seq is not None:
        for event_type, finding in [
            ("MarketSettled", "market_settled_before_terminal_evidence"),
            ("RewardDistributed", "reward_distributed_before_terminal_market_basis"),
        ]:
            early = [
                event
                for event in events
                if event.get("event_type") == event_type
                and isinstance(event.get("sequence"), int)
                and event["sequence"] < official_terminal_min_seq
            ]
            if early:
                findings.append(
                    {
                        "finding": finding,
                        "severity": "WARN",
                        "detail": f"{event_type} is replayable and preserve-only, but it occurred before terminal official evidence.",
                    }
                )

    by_id = {event["_event_id"]: event for event in events}
    terminal_market_settlements = set()
    for event in events:
        if event.get("event_type") != "MarketSettled":
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if payload.get("is_terminal") is True and isinstance(event.get("sequence"), int):
            basis = payload.get("settlement_basis_event_id")
            terminal = payload.get("terminal_event_id")
            if basis in by_id and (terminal in by_id or terminal is None):
                terminal_market_settlements.add(event["_event_id"])
            else:
                findings.append(
                    {
                        "finding": "market_terminal_basis_unresolved",
                        "severity": "WARN",
                        "detail": "Terminal MarketSettled must reference tape-resolved settlement basis and terminal event ids.",
                    }
                )

    for event in events:
        if event.get("event_type") != "RewardDistributed":
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        settlement_event_id = payload.get("settlement_event_id")
        if settlement_event_id not in terminal_market_settlements:
            findings.append(
                {
                    "finding": "reward_without_terminal_market_settlement",
                    "severity": "WARN",
                    "detail": "RewardDistributed must reference a terminal MarketSettled event.",
                }
            )

    pput_events = [event for event in events if event.get("event_type") == "PPUTAccounted"]
    if terminal_accept is not None and isinstance(terminal_accept_seq, int):
        final_pput = [
            event
            for event in pput_events
            if isinstance(event.get("sequence"), int)
            and event["sequence"] > terminal_accept_seq
            and isinstance(event.get("payload"), dict)
            and event["payload"].get("progress") == 1
            and event["payload"].get("accounting_stage") == "final"
            and event["payload"].get("terminal_event_id") == actual_accepted_head
        ]
        if not final_pput:
            findings.append(
                {
                    "finding": "pput_final_accounting_missing_after_accept",
                    "severity": "WARN",
                    "detail": "Accepted run has no post-accept final PPUTAccounted progress=1 event.",
                }
            )
    elif path_class(events, actual_accepted_head) == "failed_path":
        for event in pput_events:
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            if payload.get("progress") not in {None, 0}:
                findings.append(
                    {
                        "finding": "failed_run_has_nonzero_pput_progress",
                        "severity": "FAIL",
                        "detail": "Failed runs must have Progress_i = 0 and VPPUT_i = 0.",
                    }
                )
    return findings


def check_economic_timing(findings: list[dict[str, Any]]) -> str:
    severities = [finding["severity"] for finding in findings if finding["severity"] in {"WARN", "FAIL"}]
    if "FAIL" in severities:
        return "FAIL"
    if "WARN" in severities:
        return "WARN"
    return "PASS"


def check_decision_dag(events: list[dict[str, Any]], edges: list[dict[str, str]], actual_accepted_head: str | None) -> str:
    cls = path_class(events, actual_accepted_head)
    if cls == "incomplete_path":
        return "WARN"
    if cls == "accepted_path":
        if not any(edge["kind"] == "official_evidence_to_accept" for edge in edges):
            return "WARN"
    return "PASS"


def terminal_golden_path_status(events: list[dict[str, Any]], actual_accepted_head: str | None) -> str:
    if path_class(events, actual_accepted_head) != "accepted_path":
        return "PASS"
    path = golden_path(events, actual_accepted_head)
    if path and path[-1]["event_id"] == actual_accepted_head:
        return "PASS"
    return "FAIL"


def positive_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int) and value >= 0:
        return value
    return 0


def cost_conservation_status(events: list[dict[str, Any]]) -> str:
    final_pputs = [
        event
        for event in events
        if event.get("event_type") == "PPUTAccounted"
        and isinstance(event.get("payload"), dict)
        and event["payload"].get("accounting_stage") == "final"
    ]
    if not final_pputs:
        return "NOT_TESTED"

    cost_events = [
        event
        for event in events
        if event.get("event_type") == "CostEvent" and isinstance(event.get("payload"), dict)
    ]
    if not cost_events:
        return "FAIL"

    for pput in final_pputs:
        payload = pput["payload"]
        run_id = payload.get("run_id")
        problem_id = payload.get("problem_id")
        matching = []
        for event in cost_events:
            cost_payload = event["payload"]
            if run_id is not None and cost_payload.get("run_id") == run_id:
                matching.append(cost_payload)
            elif problem_id is not None and cost_payload.get("problem_id") == problem_id:
                matching.append(cost_payload)
        if not matching:
            return "FAIL"
        token_total = sum(positive_int(item.get("total_tokens")) for item in matching)
        wall_total = sum(positive_int(item.get("wall_time_ms")) for item in matching)
        if payload.get("total_run_token_count") != token_total:
            return "FAIL"
        if payload.get("total_wall_time_ms") != wall_total:
            return "FAIL"
    return "PASS"


def vpput_statuses(findings: list[dict[str, Any]], events: list[dict[str, Any]], actual_accepted_head: str | None) -> dict[str, str]:
    failed_progress = "FAIL" if any(f["finding"] == "failed_run_has_nonzero_pput_progress" for f in findings) else "PASS"
    accepted_final = "PASS"
    if path_class(events, actual_accepted_head) == "accepted_path":
        accepted_final = (
            "WARN"
            if any(f["finding"] == "pput_final_accounting_missing_after_accept" for f in findings)
            else "PASS"
        )
    cost_conservation = cost_conservation_status(events)
    vpput = (
        "FAIL"
        if failed_progress == "FAIL" or cost_conservation == "FAIL"
        else "WARN"
        if accepted_final == "WARN" or cost_conservation in {"WARN", "NOT_TESTED"}
        else "PASS"
    )
    return {
        "failed_progress_zero": failed_progress,
        "accepted_final_progress_one": accepted_final,
        "cost_conservation_all_branches": cost_conservation,
        "vpput_accounting": vpput,
    }


def audit_one_bundle(bundle: Path, work_dir: Path, registry: dict[str, dict[str, Any]]) -> dict[str, Any]:
    git_dir, bundle_verify_output = fetch_bundle(bundle, work_dir)
    events = read_event_chain(git_dir)
    actual_refs = {
        "accepted_head": mu(ref_oid(git_dir, "refs/turingos/accepted_head")),
        "authorization_head": mu(ref_oid(git_dir, "refs/turingos/authorization_head")),
        "tape_tip": mu(ref_oid(git_dir, "refs/turingos/tape_tip")),
    }
    derived_refs = derive_refs(events, registry)
    git_ok, git_problems, git_evidence = validate_git_topology(git_dir, events, actual_refs)
    chain_ok, chain_problems, checks = validate_chain(events, actual_refs, registry)
    checks["bundle_integrity"] = "PASS"
    checks["git_topology"] = "PASS" if git_ok else "FAIL"
    event_counts = Counter(str(event.get("event_type")) for event in events)
    edges = build_dag_edges(events)
    findings = execution_findings(events, actual_refs["accepted_head"])
    checks["economic_timing"] = check_economic_timing(findings)
    checks["decision_dag_completeness"] = check_decision_dag(events, edges, actual_refs["accepted_head"])
    checks["terminal_golden_path_anchors_to_accepted_head"] = terminal_golden_path_status(events, actual_refs["accepted_head"])
    checks.update(vpput_statuses(findings, events, actual_refs["accepted_head"]))
    if checks["economic_timing"] == "WARN":
        checks["market_accounting_correctness"] = "WARN" if any("market" in f["finding"] or "reward" in f["finding"] for f in findings) else "PASS"
    elif checks["economic_timing"] == "FAIL":
        checks["market_accounting_correctness"] = "FAIL"
    else:
        checks["market_accounting_correctness"] = "PASS"

    first_accept = first_candidate_accepted_event(events)
    terminal_accept = terminal_accepted_event(events, actual_refs["accepted_head"])
    replay_valid = chain_ok and git_ok and not any(checks.get(key) == "FAIL" for key in CRITICAL_REPLAY_CHECKS)
    return {
        "bundle": str(bundle),
        "bundle_hash": sha256_file(bundle),
        "bundle_verify_output": bundle_verify_output.strip(),
        "git_evidence": git_evidence,
        "replay_valid": replay_valid,
        "replay_problems": git_problems + chain_problems,
        "checks": checks,
        "path_class": path_class(events, actual_refs["accepted_head"]),
        "first_candidate_accepted": first_accept["_event_id"] if first_accept is not None else None,
        "terminal_candidate_accepted": terminal_accept["_event_id"] if terminal_accept is not None else None,
        "golden_path_basis": "terminal_accepted_head" if terminal_accept is not None else None,
        "actual_refs": actual_refs,
        "derived_refs": derived_refs,
        "event_count": len(events),
        "event_counts": dict(sorted(event_counts.items())),
        "events": [event_summary(event) for event in events],
        "dag_edges": edges,
        "golden_path": golden_path(events, actual_refs["accepted_head"]),
        "execution_findings": findings,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def worst_status(values: list[str]) -> str:
    if not values:
        return "NOT_TESTED"
    return max(values, key=lambda value: SEVERITY_ORDER.get(value, 99))


def aggregate_status(runs: list[dict[str, Any]]) -> dict[str, str]:
    keys = [
        "bundle_integrity",
        "git_topology",
        "canonical_payload_hash",
        "ref_reconstruction",
        "registry_head_effect",
        "authorization_head",
        "accepted_head_authority",
        "economic_timing",
        "decision_dag_completeness",
        "market_accounting_correctness",
        "terminal_golden_path_anchors_to_accepted_head",
        "failed_progress_zero",
        "accepted_final_progress_one",
        "cost_conservation_all_branches",
        "vpput_accounting",
    ]
    summary = {key: worst_status([run["checks"].get(key, "NOT_TESTED") for run in runs]) for key in keys}
    summary["bundle_accessibility"] = summary["bundle_integrity"]
    summary["basic_ref_reconstruction"] = summary["ref_reconstruction"]
    summary["replay_structural_integrity"] = (
        "PASS"
        if runs
        and all(run["replay_valid"] for run in runs)
        and summary["git_topology"] == "PASS"
        and summary["canonical_payload_hash"] == "PASS"
        else "FAIL"
    )
    if any(
        summary[key] == "FAIL"
        for key in [
            "git_topology",
            "canonical_payload_hash",
            "ref_reconstruction",
            "registry_head_effect",
            "accepted_head_authority",
            "terminal_golden_path_anchors_to_accepted_head",
        ]
    ):
        summary["constitutional_protocol_audit"] = "FAIL"
    elif summary["authorization_head"] in {"LEGACY_MISSING", "NOT_TESTED"}:
        summary["constitutional_protocol_audit"] = "PARTIAL"
    else:
        summary["constitutional_protocol_audit"] = "PASS"

    if any(value == "FAIL" for value in summary.values()):
        summary["overall"] = "FAIL"
    elif any(value in {"WARN", "PARTIAL", "LEGACY_MISSING", "NOT_TESTED"} for value in summary.values()):
        summary["overall"] = "PARTIAL"
    else:
        summary["overall"] = "PASS"
    return summary


def audit_bundles(
    bundles: list[Path],
    work_dir: Path,
    *,
    event_registry_path: Path | None = None,
    strict_vpput: bool = False,
    strict_terminal_market: bool = False,
    require_authorization_head: bool = False,
) -> dict[str, Any]:
    work_dir.mkdir(parents=True, exist_ok=True)
    registry = load_event_registry(event_registry_path)
    runs = [audit_one_bundle(bundle, work_dir / f"bundle_{idx}", registry) for idx, bundle in enumerate(bundles)]
    event_counts: Counter[str] = Counter()
    finding_counts: Counter[str] = Counter()
    for run in runs:
        event_counts.update(run["event_counts"])
        finding_counts.update(finding["finding"] for finding in run["execution_findings"])
    status_summary = aggregate_status(runs)
    strict_findings: list[dict[str, str]] = []
    if strict_vpput and status_summary.get("vpput_accounting") != "PASS":
        strict_findings.append(
            {
                "id": "strict_vpput",
                "message": "strict VPPUT gate requires vpput_accounting PASS",
            }
        )
    if strict_terminal_market and status_summary.get("market_accounting_correctness") != "PASS":
        strict_findings.append(
            {
                "id": "strict_terminal_market",
                "message": "strict terminal market gate requires market_accounting_correctness PASS",
            }
        )
    if require_authorization_head and status_summary.get("authorization_head") != "PASS":
        strict_findings.append(
            {
                "id": "require_authorization_head",
                "message": "strict authorization gate requires authorization_head PASS",
            }
        )
    if strict_findings:
        status_summary["overall"] = "FAIL"
    return {
        "schema_id": "MicroTapeDecisionDagAudit.v2",
        "verdict": status_summary["overall"],
        "truth_source": "micro_tape_bundle_only",
        "event_registry": str((event_registry_path or DEFAULT_EVENT_REGISTRY_PATH).resolve()),
        "canonicalization_profile": "turingos.jcs.v1-compatible-no-floats-ascii-keys",
        "status_summary": status_summary,
        "strict_findings": strict_findings,
        "aggregate": {
            "bundle_count": len(runs),
            "event_count": sum(run["event_count"] for run in runs),
            "event_counts": dict(sorted(event_counts.items())),
            "finding_counts": dict(sorted(finding_counts.items())),
        },
        "runs": runs,
    }


def dot_label(event: dict[str, Any]) -> str:
    lines = [
        f"#{event.get('sequence')} {event.get('event_type')}",
        f"{event.get('head_effect')} {event.get('predicate_product')}",
    ]
    if event.get("result") is not None:
        lines.append("result=" + str(event.get("result")))
    if event.get("progress") is not None:
        lines.append("progress=" + str(event.get("progress")))
    if event.get("failure_class") is not None:
        lines.append(str(event.get("failure_class")))
    return "\\n".join(lines)


def write_dot(report: dict[str, Any], path: Path) -> None:
    lines = ["digraph micro_tape_decision_dag {", "  rankdir=LR;", "  node [shape=box, fontname=\"Menlo\"];"]
    for run_index, run in enumerate(report["runs"]):
        lines.append(f"  subgraph cluster_{run_index} {{")
        lines.append(f"    label=\"{Path(run['bundle']).parent.name} ({run['path_class']})\";")
        for event in run["events"]:
            node = event["event_id"].replace(":", "_")
            if event["event_type"] == "CandidateAccepted":
                color = "palegreen"
            elif event["event_type"] == "FailureNode":
                color = "mistyrose"
            elif event["event_type"] == "OfficialEvaluatorEvidenceImported":
                color = "lightgoldenrod1"
            else:
                color = "white"
            lines.append(f"    {node} [label=\"{dot_label(event)}\", style=filled, fillcolor=\"{color}\"];")
        for edge in run["dag_edges"]:
            source = edge["from"].replace(":", "_")
            target = edge["to"].replace(":", "_")
            style = "dotted" if edge["kind"] == "tape_parent" else "solid"
            lines.append(f"    {source} -> {target} [label=\"{edge['kind']}\", style={style}];")
        lines.append("  }")
    lines.append("}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_tree_for_run(run: dict[str, Any]) -> list[str]:
    lines: list[str] = []

    def fmt(event: dict[str, Any], marker: str = "") -> str:
        result = f" result={event['result']}" if event.get("result") is not None else ""
        progress = f" progress={event['progress']}" if event.get("progress") is not None else ""
        failure = f" class={event['failure_class']}" if event.get("failure_class") is not None else ""
        return (
            f"{event['node_id']} {event['event_type']} "
            f"[{event['head_effect']}/{event['predicate_product']}]{result}{progress}{failure} {marker}"
        ).rstrip()

    lines.append(f"PATH_CLASS {run['path_class']}")
    for idx, event in enumerate(run["events"]):
        if event["event_type"] == "CandidateAccepted":
            marker = "✓ACCEPT"
        elif event["event_type"] == "FailureNode":
            marker = "✗FAIL"
        elif event["event_type"] == "OfficialEvaluatorEvidenceImported":
            marker = "EVIDENCE"
        else:
            marker = ""
        branch = "└──" if idx == len(run["events"]) - 1 else "├──"
        lines.append(f"{branch} {fmt(event, marker)}")
    return lines


def write_markdown(report: dict[str, Any], path: Path) -> None:
    aggregate = report["aggregate"]
    lines = [
        "# Micro Tape Independent Decision DAG Audit",
        "",
        f"**Verdict**: {report['verdict']}",
        f"**Truth source**: {report['truth_source']}",
        f"**Event registry**: `{report['event_registry']}`",
        f"**Canonicalization**: `{report['canonicalization_profile']}`",
        f"**Bundles**: {aggregate['bundle_count']} | **Events**: {aggregate['event_count']}",
        "",
        "## Status Matrix",
        "",
    ]
    for key, value in report["status_summary"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Aggregate Events", ""])
    for name, count in aggregate["event_counts"].items():
        lines.append(f"- `{name}`: {count}")
    lines.extend(["", "## Runs", ""])
    for run in report["runs"]:
        lines.append(f"### {Path(run['bundle']).parent.name}")
        lines.append("")
        lines.append(f"- bundle hash: `{run['bundle_hash']}`")
        lines.append(f"- replay valid: `{run['replay_valid']}`")
        lines.append(f"- path class: `{run['path_class']}`")
        lines.append(f"- tape_tip: `{run['actual_refs']['tape_tip']}`")
        lines.append(f"- authorization_head: `{run['actual_refs']['authorization_head']}`")
        lines.append(f"- accepted_head: `{run['actual_refs']['accepted_head']}`")
        lines.append(f"- events: `{run['event_count']}`")
        lines.append("")
        lines.append("#### Checks")
        lines.append("")
        for key, value in run["checks"].items():
            lines.append(f"- `{key}`: `{value}`")
        lines.append("")
        lines.append("#### Decision DAG")
        lines.append("")
        lines.append("```")
        lines.extend(render_tree_for_run(run))
        lines.append("```")
        lines.append("")
        if run["golden_path"]:
            lines.append("#### Accepted Path")
            lines.append("")
            for idx, event in enumerate(run["golden_path"], start=1):
                lines.append(
                    f"{idx}. `{event['node_id']}` {event['event_type']} "
                    f"[{event['head_effect']}/{event['predicate_product']}]"
                )
            lines.append("")
        else:
            lines.append("#### Accepted Path")
            lines.append("")
            lines.append("_No accepted path: this run is failed or incomplete._")
            lines.append("")
        if run["execution_findings"]:
            lines.append("#### Execution Findings")
            lines.append("")
            for finding in run["execution_findings"]:
                lines.append(f"- **{finding['severity']}** `{finding['finding']}`: {finding['detail']}")
            lines.append("")
        if run["replay_problems"]:
            lines.append("#### Replay Problems")
            lines.append("")
            for problem in run["replay_problems"]:
                lines.append(f"- {problem}")
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coverage", help="Substrate coverage JSON containing micro_tape_bundle refs")
    parser.add_argument("--bundle", action="append", default=[], help="Micro Tape bundle path; repeatable")
    parser.add_argument("--event-registry", help="Closed event registry JSON; defaults to pack/04_registries/event_registry_v5_3_1.json")
    parser.add_argument("--strict-vpput", action="store_true")
    parser.add_argument("--strict-terminal-market", action="store_true")
    parser.add_argument("--require-authorization-head", action="store_true")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)

    bundles = [Path(item) for item in args.bundle]
    if args.coverage:
        bundles.extend(bundles_from_coverage(Path(args.coverage)))
    if not bundles:
        raise SystemExit("no bundles supplied")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="turingos-micro-tape-audit-") as temp:
        report = audit_bundles(
            bundles,
            Path(temp),
            event_registry_path=Path(args.event_registry) if args.event_registry else None,
            strict_vpput=args.strict_vpput,
            strict_terminal_market=args.strict_terminal_market,
            require_authorization_head=args.require_authorization_head,
        )
    write_json(out_dir / "micro_tape_decision_dag_audit.json", report)
    write_markdown(report, out_dir / "micro_tape_decision_dag.md")
    write_dot(report, out_dir / "micro_tape_decision_dag.dot")
    return 1 if report["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
