#!/usr/bin/env python3
"""Audit Phase F evaluator proof artifacts.

Phase F is a shard-scoped evaluator evidence packet. It proves that the
OfficialEvaluatorEvidenceImported PASS events consumed by the frozen 20-task
shard are bound to reproducible artifact descriptors. It does not prove a full
SWE-bench dataset or leaderboard claim.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shlex
import tempfile
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
MICRO_TAPE_AUDITOR = REPO / "tools" / "bench" / "audit_micro_tape_decision_dag.py"
FORBIDDEN_SECRET = [
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"(?i)(private[_-]?key|signing[_-]?seed|auth\.json|api[_-]?key)(\s*[:=]\s*)[A-Za-z0-9_./~:-]{6,}"),
]


def load_micro_tape_auditor() -> Any:
    spec = importlib.util.spec_from_file_location("audit_micro_tape_decision_dag", MICRO_TAPE_AUDITOR)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"cannot load {MICRO_TAPE_AUDITOR}")
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def payload(event: dict[str, Any]) -> dict[str, Any]:
    value = event.get("payload")
    return value if isinstance(value, dict) else {}


def sequence(event: dict[str, Any] | None) -> int | None:
    if event is None:
        return None
    value = event.get("sequence")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def task_order(stage16_root: Path) -> list[str]:
    manifest = load_json(stage16_root / "task_manifest.json")
    ids = manifest.get("instance_ids")
    if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
        raise ValueError("Stage16 task_manifest missing instance_ids")
    return ids


def coverage_by_id(root: Path) -> dict[str, dict[str, Any]]:
    coverage = load_json(root / "substrate_coverage.json")
    return {
        run["instance_id"]: run
        for run in coverage.get("turingos_arm_runs", [])
        if isinstance(run, dict) and isinstance(run.get("instance_id"), str)
    }


def final_event_records(stage16_root: Path, stage16r_root: Path) -> dict[str, dict[str, Any]]:
    auditor = load_micro_tape_auditor()
    stage16_runs = coverage_by_id(stage16_root)
    stage16r_runs = coverage_by_id(stage16r_root)
    records: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory(prefix="turingos-phase-f-events-") as temp:
        work = Path(temp)
        for instance_id in task_order(stage16_root):
            source = "Stage16R" if instance_id in stage16r_runs else "Stage16"
            run = stage16r_runs.get(instance_id) or stage16_runs[instance_id]
            bundle = Path(run["micro_tape_bundle"])
            git_dir, _ = auditor.fetch_bundle(bundle, work / instance_id)
            events = auditor.read_event_chain(git_dir)
            official_passes = [
                event
                for event in events
                if event.get("event_type") == "OfficialEvaluatorEvidenceImported"
                and payload(event).get("result") == "PASS"
            ]
            accepts = [event for event in events if event.get("event_type") == "CandidateAccepted"]
            official = official_passes[-1] if official_passes else None
            accept = accepts[-1] if accepts else None
            if official is None or accept is None:
                records[instance_id] = {
                    "instance_id": instance_id,
                    "source_stage": source,
                    "micro_tape_bundle": str(bundle),
                    "problems": ["missing final official PASS or CandidateAccepted"],
                }
                continue
            records[instance_id] = {
                "instance_id": instance_id,
                "source_stage": source,
                "micro_tape_bundle": str(bundle),
                "micro_tape_bundle_sha256": sha256_file(bundle),
                "official_evidence_event_id": official["_event_id"],
                "official_evidence_sequence": official["sequence"],
                "candidate_accepted_event_id": accept["_event_id"],
                "candidate_accepted_sequence": accept["sequence"],
                "official_payload": payload(official),
                "accept_payload": payload(accept),
                "official_precedes_accept": (
                    sequence(official) is not None
                    and sequence(accept) is not None
                    and sequence(official) < sequence(accept)
                ),
                "problems": [],
            }
    return records


def relative_path(root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return root / path


def scan_secrets(root: Path) -> list[dict[str, str]]:
    problems: list[dict[str, str]] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix == ".bundle":
            continue
        text = path.read_text(errors="ignore")
        for pattern in FORBIDDEN_SECRET:
            match = pattern.search(text)
            if match:
                problems.append({"path": str(path), "match": match.group(0)[:80]})
    return problems


def supported_evaluator_command(command: str) -> bool:
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    required = {"--tasks-jsonl", "--turingos-dir", "--direct-dir", "--out"}
    forbidden = {"--instance-id", "--candidate-patch", "--test-patch"}
    return required.issubset(parts) and not forbidden.intersection(parts)


def looks_like_unified_diff(path: Path) -> bool:
    text = path.read_text(errors="ignore")
    return text.startswith("diff --git ") and "\n--- " in text and "\n+++ " in text


def audit_phase_f(stage16_root: Path, stage16r_root: Path, root: Path) -> dict[str, Any]:
    problems: list[str] = []
    blockers: list[str] = []
    records = final_event_records(stage16_root, stage16r_root)
    expected_ids = task_order(stage16_root)

    claim = load_json(root / "CLAIM_BOUNDARY.json") if (root / "CLAIM_BOUNDARY.json").exists() else {}
    if claim.get("not_full_swe_bench_dataset") is not True:
        problems.append("CLAIM_BOUNDARY must mark not_full_swe_bench_dataset=true")
    if claim.get("full_swe_bench_score_claim_allowed") is not False:
        problems.append("full SWE-bench score claim must remain forbidden")
    if claim.get("full_dataset_claim_allowed") is not False:
        problems.append("full dataset claim must remain forbidden")
    if claim.get("leaderboard_equivalence_claim_allowed") is not False:
        problems.append("leaderboard equivalence claim must remain forbidden")

    evaluator = load_json(root / "evaluator_manifest.json") if (root / "evaluator_manifest.json").exists() else {}
    patch_manifest = load_json(root / "patch_manifest.json") if (root / "patch_manifest.json").exists() else {}
    evidence_manifest = load_json(root / "required_evidence_manifest.json") if (root / "required_evidence_manifest.json").exists() else {}
    dataset_manifest = load_json(root / "dataset_manifest.json") if (root / "dataset_manifest.json").exists() else {}
    harness_manifest = load_json(root / "official_harness_digest.json") if (root / "official_harness_digest.json").exists() else {}
    if dataset_manifest.get("task_count") != 20:
        problems.append("dataset task_count must be 20 for Phase F shard proof")
    if dataset_manifest.get("instance_ids") != expected_ids:
        problems.append("dataset instance_ids must match Stage16 task manifest")
    recorded_harness = harness_manifest.get("recorded_harness_digest")
    recorded_artifact_path = harness_manifest.get("recorded_harness_artifact_path")
    if isinstance(recorded_artifact_path, str):
        artifact = relative_path(root, recorded_artifact_path)
        if not artifact.exists() or sha256_file(artifact) != recorded_harness:
            problems.append("recorded harness artifact must match recorded_harness_digest")
    else:
        blockers.append("recorded harness artifact missing; evaluator replay cannot be externally pinned")
    if harness_manifest.get("digest_matches_current") is not True and not isinstance(recorded_artifact_path, str):
        blockers.append("recorded harness digest differs from current harness and no pinned recorded artifact is present")
    evaluator_by_id = {
        item.get("instance_id"): item
        for item in evaluator.get("evaluations", [])
        if isinstance(item, dict)
    }
    patch_by_id = {
        item.get("instance_id"): item
        for item in patch_manifest.get("patches", [])
        if isinstance(item, dict)
    }
    if sorted(patch_by_id) != sorted(expected_ids) or len(patch_manifest.get("patches", [])) != len(expected_ids):
        problems.append("patch_manifest must contain exactly the 20 Stage16 task ids")
    if sorted(evaluator_by_id) != sorted(expected_ids) or len(evaluator.get("evaluations", [])) != len(expected_ids):
        problems.append("evaluator_manifest must contain exactly the 20 Stage16 task ids")
    evidence_items = [item for item in evidence_manifest.get("required_evidence", []) if isinstance(item, dict)]
    evidence_by_instance: dict[str, list[dict[str, Any]]] = {}
    for item in evidence_items:
        evidence_by_instance.setdefault(str(item.get("instance_id")), []).append(item)

    run_reports: list[dict[str, Any]] = []
    all_reproducible = True
    all_accepts_required = True
    for instance_id in task_order(stage16_root):
        record = records[instance_id]
        run_problems = list(record.get("problems", []))
        official_payload = record.get("official_payload", {})
        patch = patch_by_id.get(instance_id)
        evaluation = evaluator_by_id.get(instance_id)
        evidence = evidence_by_instance.get(instance_id, [])
        if patch is None:
            run_problems.append("missing patch manifest entry")
        else:
            candidate_path = relative_path(root, str(patch.get("candidate_patch_path", "")))
            test_patch_path = relative_path(root, str(patch.get("test_patch_path", "")))
            if not candidate_path.exists():
                run_problems.append("candidate patch artifact missing")
            elif sha256_file(candidate_path) != official_payload.get("candidate_patch_hash"):
                run_problems.append("candidate patch digest mismatch")
            elif patch.get("candidate_patch_sha256") != official_payload.get("candidate_patch_hash"):
                run_problems.append("candidate patch manifest digest mismatch")
            elif record.get("source_stage") == "Stage16R" and not looks_like_unified_diff(candidate_path):
                blockers.append(f"{instance_id}: Stage16R candidate artifact is digest-bound but not a replayable unified diff")
            if not test_patch_path.exists():
                run_problems.append("test patch artifact missing")
            elif sha256_file(test_patch_path) != official_payload.get("test_patch_hash"):
                run_problems.append("test patch digest mismatch")
            elif patch.get("official_test_patch_sha256") != official_payload.get("test_patch_hash"):
                run_problems.append("test patch manifest digest mismatch")
            elif record.get("source_stage") == "Stage16R" and not looks_like_unified_diff(test_patch_path):
                blockers.append(f"{instance_id}: Stage16R test patch artifact is digest-bound but not a replayable unified diff")
        if evaluation is None:
            run_problems.append("missing evaluator manifest entry")
        else:
            if not evaluation.get("evaluator_command"):
                run_problems.append("evaluator command missing")
            elif not supported_evaluator_command(str(evaluation.get("evaluator_command"))):
                run_problems.append("unsupported evaluator command")
            for key, expected in [
                ("apply_candidate_result", "PASS"),
                ("apply_test_patch_result", "PASS"),
                ("target_test_result", "PASS"),
                ("target_test_exit_code", 0),
            ]:
                if evaluation.get(key) != expected:
                    run_problems.append(f"{key} must be {expected!r}")
            stdout_path = relative_path(root, str(evaluation.get("stdout_path", "")))
            stderr_path = relative_path(root, str(evaluation.get("stderr_path", "")))
            if not stdout_path.exists() or sha256_file(stdout_path) != official_payload.get("stdout_hash"):
                run_problems.append("stdout evidence digest mismatch")
            elif evaluation.get("stdout_sha256") != official_payload.get("stdout_hash"):
                run_problems.append("stdout manifest digest mismatch")
            if not stderr_path.exists() or sha256_file(stderr_path) != official_payload.get("stderr_hash"):
                run_problems.append("stderr evidence digest mismatch")
            elif evaluation.get("stderr_sha256") != official_payload.get("stderr_hash"):
                run_problems.append("stderr manifest digest mismatch")
            if evaluation.get("official_evidence_event_id") != record.get("official_evidence_event_id"):
                run_problems.append("official evidence event id mismatch")
            if evaluation.get("candidate_accepted_event_id") != record.get("candidate_accepted_event_id"):
                run_problems.append("candidate accepted event id mismatch")
        kinds = {item.get("evidence_kind") for item in evidence}
        required_kinds = {"candidate_patch", "official_test_patch", "evaluator_stdout", "evaluator_stderr"}
        if not required_kinds.issubset(kinds):
            run_problems.append("required evidence descriptors missing")
            all_accepts_required = False
        for item in evidence:
            if item.get("required") is not True:
                run_problems.append("required evidence descriptor must be required=true")
                all_accepts_required = False
            artifact_path = relative_path(root, str(item.get("artifact_path", "")))
            if not artifact_path.exists() or sha256_file(artifact_path) != item.get("sha256"):
                run_problems.append("required evidence artifact digest mismatch")
                all_accepts_required = False
            if item.get("official_evidence_event_id") != record.get("official_evidence_event_id"):
                run_problems.append("required evidence official event id mismatch")
                all_accepts_required = False
        if not record.get("official_precedes_accept"):
            run_problems.append("official PASS must precede CandidateAccepted")
        if run_problems:
            all_reproducible = False
        run_reports.append(
            {
                "instance_id": instance_id,
                "source_stage": record.get("source_stage"),
                "official_evidence_event_id": record.get("official_evidence_event_id"),
                "candidate_accepted_event_id": record.get("candidate_accepted_event_id"),
                "status": "PASS" if not run_problems else "FAIL",
                "problems": run_problems,
            }
        )
    secret_problems = scan_secrets(root)
    if secret_problems:
        problems.append("secret scan found credential-shaped values")
    problems.extend(problem for run in run_reports for problem in run["problems"])
    artifact_binding = not problems and len(run_reports) == 20
    executable_replay = artifact_binding and not blockers
    if problems or len(run_reports) != 20:
        status = "FAIL"
    elif blockers:
        status = "PARTIAL"
    else:
        status = "PASS"
    return {
        "schema_id": "PhaseFEvaluatorProofAudit.v1",
        "status": status,
        "task_count": len(run_reports),
        "full_swe_bench_score_claim_allowed": False,
        "full_dataset_claim_allowed": False,
        "leaderboard_equivalence_claim_allowed": False,
        "release_next_phase_g": status == "PASS",
        "artifact_microtape_digest_binding": artifact_binding,
        "official_evaluator_executable_replay": executable_replay,
        "all_solved_tasks_have_reproducible_official_eval": executable_replay,
        "all_candidate_accepts_have_required_evidence": all_accepts_required and not problems,
        "secret_scan_status": "PASS" if not secret_problems else "FAIL",
        "problems": problems,
        "blockers": sorted(set(blockers)),
        "runs": run_reports,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage16-root", required=True)
    parser.add_argument("--stage16r-root", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    report = audit_phase_f(Path(args.stage16_root), Path(args.stage16r_root), Path(args.root))
    write_json(Path(args.out), report)
    return 0 if report["status"] in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
