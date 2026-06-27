#!/usr/bin/env python3
"""Replay TuringOS Micro Tape bundles and build an auditable decision DAG.

The auditor reads only Git Micro Tape bundles as truth. Nearby summaries can be
compared by humans, but they are not required for replay.
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


ADVANCE_EVENTS = {"SystemConstitutionAccepted", "CandidateAccepted", "HandoffAccepted"}


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def run_git(args: list[str], *, git_dir: Path | None = None, cwd: Path | None = None) -> str:
    cmd = ["git"]
    if git_dir is not None:
        cmd.append(f"--git-dir={git_dir}")
    cmd.extend(args)
    result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=True)
    return result.stdout


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


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


def fetch_bundle(bundle: Path, work_dir: Path) -> Path:
    bundle = bundle.resolve()
    if not bundle.exists():
        raise FileNotFoundError(bundle)
    git_dir = work_dir / (bundle.parent.name + ".git")
    if git_dir.exists():
        shutil.rmtree(git_dir)
    run_git(["init", "--bare", "--object-format=sha256", str(git_dir)])
    run_git(["fetch", "--quiet", str(bundle), "refs/*:refs/*"], git_dir=git_dir)
    run_git(["bundle", "verify", str(bundle)])
    return git_dir


def ref_oid(git_dir: Path, ref: str) -> str | None:
    result = subprocess.run(
        ["git", f"--git-dir={git_dir}", "rev-parse", "--verify", ref],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def read_event_chain(git_dir: Path) -> list[dict[str, Any]]:
    raw_oids = run_git(["rev-list", "--reverse", "refs/turingos/tape_tip"], git_dir=git_dir).split()
    events: list[dict[str, Any]] = []
    for oid in raw_oids:
        raw_event = run_git(["show", f"{oid}:event"], git_dir=git_dir)
        event = json.loads(raw_event)
        if not isinstance(event, dict):
            raise ValueError(f"{oid}:event is not an object")
        event["_oid"] = oid
        event["_event_id"] = "mu:" + oid
        events.append(event)
    return events


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


def short_event(event: dict[str, Any]) -> str:
    oid = str(event["_oid"])[:7]
    seq = event.get("sequence")
    return f"e{seq}_{oid}_{event.get('event_type')}"


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
        settlement_event_id = payload.get("settlement_event_id")
        if isinstance(settlement_event_id, str):
            source = next((item for item in events if item["_event_id"] == settlement_event_id), None)
            if source is not None:
                add_edge(edges, source, event, "settlement_event_ref")
    return edges


def derive_refs(events: list[dict[str, Any]]) -> dict[str, str | None]:
    accepted_head: str | None = None
    tape_tip: str | None = None
    authorization_head: str | None = None
    for event in events:
        tape_tip = event["_event_id"]
        if event.get("event_type") in ADVANCE_EVENTS and event.get("predicate_product") == "PASS":
            accepted_head = event["_event_id"]
        if event.get("event_type") in {"AtomAuthorized", "CapsuleApproved"} and event.get("predicate_product") == "PASS":
            authorization_head = event["_event_id"]
    return {
        "accepted_head": accepted_head,
        "authorization_head": authorization_head,
        "tape_tip": tape_tip,
    }


def validate_chain(events: list[dict[str, Any]], actual_refs: dict[str, str | None]) -> tuple[bool, list[str]]:
    problems: list[str] = []
    accepted_head: str | None = None
    previous: str | None = None
    for expected_sequence, event in enumerate(events):
        event_id = event["_event_id"]
        if event.get("sequence") != expected_sequence:
            problems.append(f"{event_id}: sequence {event.get('sequence')} != {expected_sequence}")
        if event.get("prev_tape_tip") != previous:
            problems.append(f"{event_id}: prev_tape_tip mismatch")
        if event.get("accepted_head_before") != accepted_head:
            problems.append(f"{event_id}: accepted_head_before mismatch")
        payload_hash = sha256_json(event.get("payload"))
        if event.get("payload_hash") != payload_hash:
            problems.append(f"{event_id}: payload_hash mismatch")
        if event.get("content_digest") not in {None, payload_hash}:
            problems.append(f"{event_id}: content_digest mismatch")
        if not ascii_keys(event):
            problems.append(f"{event_id}: non-ASCII load-bearing key")
        if has_float(event):
            problems.append(f"{event_id}: float in load-bearing payload")
        if event.get("event_type") in ADVANCE_EVENTS and event.get("predicate_product") == "PASS":
            accepted_head = event_id
        previous = event_id
    derived_refs = derive_refs(events)
    for key, value in derived_refs.items():
        if value != actual_refs.get(key):
            problems.append(f"{key}: derived {value} != actual {actual_refs.get(key)}")
    return not problems, problems


def golden_path(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    wanted = [
        "GoalStateProposed",
        "WorkCapsuleBuilt",
        "WorkerReceiptImported",
        "MacroObservationImported",
        "OfficialEvaluatorEvidenceImported",
        "CandidateAccepted",
    ]
    output: list[dict[str, Any]] = []
    for name in wanted:
        match = next((event for event in events if event.get("event_type") == name), None)
        if match is not None:
            output.append(event_summary(match))
    return output


def event_summary(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    return {
        "event_id": event["_event_id"],
        "short_id": str(event["_oid"])[:7],
        "sequence": event.get("sequence"),
        "event_type": event.get("event_type"),
        "head_effect": event.get("head_effect"),
        "predicate_product": event.get("predicate_product"),
        "writer_id": event.get("writer_id"),
        "capsule_id": payload.get("capsule_id"),
        "market_id": payload.get("market_id"),
        "result": payload.get("result"),
        "failure_class": payload.get("failure_class"),
    }


def execution_findings(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    official_pass_seq = [
        event.get("sequence")
        for event in events
        if event.get("event_type") == "OfficialEvaluatorEvidenceImported"
        and isinstance(event.get("payload"), dict)
        and event["payload"].get("result") == "PASS"
    ]
    accepted_seq = [
        event.get("sequence")
        for event in events
        if event.get("event_type") == "CandidateAccepted" and event.get("predicate_product") == "PASS"
    ]
    if official_pass_seq and accepted_seq and min(accepted_seq) > min(official_pass_seq):
        findings.append(
            {
                "finding": "official_evidence_precedes_accept",
                "severity": "INFO",
                "detail": "CandidateAccepted occurs only after OfficialEvaluatorEvidenceImported PASS.",
            }
        )
    market_before_official = [
        event
        for event in events
        if event.get("event_type") == "MarketSettled"
        and official_pass_seq
        and event.get("sequence", 999999) < min(official_pass_seq)
    ]
    if market_before_official:
        findings.append(
            {
                "finding": "market_settled_before_official_evidence",
                "severity": "WARN",
                "detail": "MarketSettled is replayable and preserve-only, but it settled before official evaluator evidence.",
            }
        )
    pput_before_accept = [
        event
        for event in events
        if event.get("event_type") == "PPUTAccounted"
        and accepted_seq
        and event.get("sequence", 999999) < min(accepted_seq)
    ]
    if pput_before_accept:
        findings.append(
            {
                "finding": "pput_accounted_before_final_accept",
                "severity": "WARN",
                "detail": "PPUTAccounted records pre-accept progress; final progress requires replay reducer or a later PPUTAccounted event.",
            }
        )
    return findings


def audit_one_bundle(bundle: Path, work_dir: Path) -> dict[str, Any]:
    git_dir = fetch_bundle(bundle, work_dir)
    events = read_event_chain(git_dir)
    actual_refs = {
        "accepted_head": ("mu:" + ref_oid(git_dir, "refs/turingos/accepted_head")) if ref_oid(git_dir, "refs/turingos/accepted_head") else None,
        "authorization_head": ("mu:" + ref_oid(git_dir, "refs/turingos/authorization_head")) if ref_oid(git_dir, "refs/turingos/authorization_head") else None,
        "tape_tip": ("mu:" + ref_oid(git_dir, "refs/turingos/tape_tip")) if ref_oid(git_dir, "refs/turingos/tape_tip") else None,
    }
    derived_refs = derive_refs(events)
    replay_valid, problems = validate_chain(events, actual_refs)
    event_counts = Counter(str(event.get("event_type")) for event in events)
    return {
        "bundle": str(bundle),
        "bundle_hash": sha256_file(bundle),
        "replay_valid": replay_valid,
        "replay_problems": problems,
        "actual_refs": actual_refs,
        "derived_refs": derived_refs,
        "event_count": len(events),
        "event_counts": dict(sorted(event_counts.items())),
        "events": [event_summary(event) for event in events],
        "dag_edges": build_dag_edges(events),
        "golden_path": golden_path(events),
        "execution_findings": execution_findings(events),
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def audit_bundles(bundles: list[Path], work_dir: Path) -> dict[str, Any]:
    work_dir.mkdir(parents=True, exist_ok=True)
    runs = [audit_one_bundle(bundle, work_dir / f"bundle_{idx}") for idx, bundle in enumerate(bundles)]
    event_counts: Counter[str] = Counter()
    finding_counts: Counter[str] = Counter()
    for run in runs:
        event_counts.update(run["event_counts"])
        finding_counts.update(finding["finding"] for finding in run["execution_findings"])
    verdict = "PASS" if runs and all(run["replay_valid"] for run in runs) else "FAIL"
    return {
        "schema_id": "MicroTapeDecisionDagAudit.v1",
        "verdict": verdict,
        "truth_source": "micro_tape_bundle_only",
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
        str(event.get("predicate_product")),
    ]
    if event.get("result") is not None:
        lines.append("result=" + str(event.get("result")))
    if event.get("failure_class") is not None:
        lines.append(str(event.get("failure_class")))
    return "\\n".join(lines)


def write_dot(report: dict[str, Any], path: Path) -> None:
    lines = ["digraph micro_tape_decision_dag {", "  rankdir=LR;", "  node [shape=box, fontname=\"Menlo\"];"]
    for run_index, run in enumerate(report["runs"]):
        lines.append(f"  subgraph cluster_{run_index} {{")
        lines.append(f"    label=\"{Path(run['bundle']).parent.name}\";")
        for event in run["events"]:
            node = event["event_id"].replace(":", "_")
            color = "palegreen" if event["event_type"] == "CandidateAccepted" else "mistyrose" if event["event_type"] == "FailureNode" else "white"
            lines.append(f"    {node} [label=\"{dot_label(event)}\", style=filled, fillcolor=\"{color}\"];")
        for edge in run["dag_edges"]:
            source = edge["from"].replace(":", "_")
            target = edge["to"].replace(":", "_")
            style = "solid" if edge["kind"] != "tape_parent" else "dotted"
            lines.append(f"    {source} -> {target} [label=\"{edge['kind']}\", style={style}];")
        lines.append("  }")
    lines.append("}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_tree_for_run(run: dict[str, Any]) -> list[str]:
    by_type: dict[str, list[dict[str, Any]]] = {}
    for event in run["events"]:
        by_type.setdefault(str(event["event_type"]), []).append(event)
    lines: list[str] = []

    def fmt(event: dict[str, Any] | None, marker: str = "") -> str:
        if event is None:
            return "(missing)"
        result = f" result={event['result']}" if event.get("result") is not None else ""
        failure = f" class={event['failure_class']}" if event.get("failure_class") is not None else ""
        return (
            f"{event['short_id']} #{event['sequence']} {event['event_type']} "
            f"[{event['predicate_product']}]{result}{failure} {marker}"
        ).rstrip()

    genesis = by_type.get("SystemConstitutionAccepted", [None])[0]
    goal = by_type.get("GoalStateProposed", [None])[0]
    capsule = by_type.get("WorkCapsuleBuilt", [None])[0]
    lines.append(f"ROOT {fmt(genesis)}")
    lines.append(f"└── {fmt(goal)}")
    lines.append(f"    └── {fmt(capsule)}")

    evidence = by_type.get("EvidenceBound", [None])[0]
    lines.append(f"        ├── evidence: {fmt(evidence)}")

    market = by_type.get("MarketCreated", [None])[0]
    position = by_type.get("PositionMinted", [None])[0]
    budget = by_type.get("BudgetAllocated", [None])[0]
    settled = by_type.get("MarketSettled", [None])[0]
    reward = by_type.get("RewardDistributed", [None])[0]
    lines.append(f"        ├── market: {fmt(market)}")
    lines.append(f"        │   ├── {fmt(position)}")
    lines.append(f"        │   ├── {fmt(budget)}")
    lines.append(f"        │   └── {fmt(settled)}")
    lines.append(f"        │       └── {fmt(reward)}")

    receipt = by_type.get("WorkerReceiptImported", [None])[0]
    macro = by_type.get("MacroObservationImported", [None])[0]
    failures = by_type.get("FailureNode", [])
    lines.append(f"        ├── worker: {fmt(receipt)}")
    lines.append(f"        │   └── macro: {fmt(macro)}")
    for idx, failure in enumerate(failures):
        branch = "└──" if idx == len(failures) - 1 else "├──"
        lines.append(f"        │       {branch} {fmt(failure, '✗FAIL')}")

    cost = by_type.get("CostEvent", [None])[0]
    pput = by_type.get("PPUTAccounted", [None])[0]
    replay = by_type.get("PredicateEvaluated", [None])[0]
    lines.append(f"        ├── pput/replay: {fmt(cost)}")
    lines.append(f"        │   └── {fmt(pput)}")
    lines.append(f"        │       └── {fmt(replay)}")

    official = by_type.get("OfficialEvaluatorEvidenceImported", [None])[0]
    accepted = by_type.get("CandidateAccepted", [None])[0]
    lines.append(f"        └── official: {fmt(official)}")
    lines.append(f"            └── {fmt(accepted, '✓ACCEPT')}")
    return lines


def write_markdown(report: dict[str, Any], path: Path) -> None:
    aggregate = report["aggregate"]
    lines = [
        "# Micro Tape Independent Decision DAG Audit",
        "",
        f"**Verdict**: {report['verdict']}",
        f"**Truth source**: {report['truth_source']}",
        f"**Bundles**: {aggregate['bundle_count']} | **Events**: {aggregate['event_count']}",
        "",
        "## Aggregate Events",
        "",
    ]
    for name, count in aggregate["event_counts"].items():
        lines.append(f"- `{name}`: {count}")
    lines.extend(["", "## Runs", ""])
    for run in report["runs"]:
        lines.append(f"### {Path(run['bundle']).parent.name}")
        lines.append("")
        lines.append(f"- bundle hash: `{run['bundle_hash']}`")
        lines.append(f"- replay valid: `{run['replay_valid']}`")
        lines.append(f"- tape_tip: `{run['actual_refs']['tape_tip']}`")
        lines.append(f"- accepted_head: `{run['actual_refs']['accepted_head']}`")
        lines.append(f"- events: `{run['event_count']}`")
        lines.append("")
        lines.append("#### Decision Tree")
        lines.append("")
        lines.append("```")
        lines.extend(render_tree_for_run(run))
        lines.append("```")
        lines.append("")
        lines.append("#### Golden Path")
        lines.append("")
        for idx, event in enumerate(run["golden_path"], start=1):
            lines.append(
                f"{idx}. `{event['short_id']}` #{event['sequence']} "
                f"{event['event_type']} [{event['predicate_product']}]"
            )
        lines.append("")
        if run["execution_findings"]:
            lines.append("#### Execution Findings")
            lines.append("")
            for finding in run["execution_findings"]:
                lines.append(f"- **{finding['severity']}** `{finding['finding']}`: {finding['detail']}")
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coverage", help="Substrate coverage JSON containing micro_tape_bundle refs")
    parser.add_argument("--bundle", action="append", default=[], help="Micro Tape bundle path; repeatable")
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
        report = audit_bundles(bundles, Path(temp))
    write_json(out_dir / "micro_tape_decision_dag_audit.json", report)
    write_markdown(report, out_dir / "micro_tape_decision_dag.md")
    write_dot(report, out_dir / "micro_tape_decision_dag.dot")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
