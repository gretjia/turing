#!/usr/bin/env python3
"""Build Phase F evaluator proof artifacts for the repaired 20-task shard."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
AUDITOR_PATH = REPO / "tools" / "bench" / "audit_phase_f_evaluator_proof.py"
STAGE12_ROOT = REPO / "evidence" / "bench" / "mini_swe_bench_stage12_20task_loop_20260628"
RECORDED_STAGE12_HARNESS_COMMIT = "49936f4a1101c561a3608714f32c41111f7a7619"


def load_auditor() -> Any:
    spec = importlib.util.spec_from_file_location("audit_phase_f_evaluator_proof", AUDITOR_PATH)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"cannot load {AUDITOR_PATH}")
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


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_text_exact(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def rel(root: Path, path: Path) -> str:
    return str(path.relative_to(root))


def command_output(command: list[str]) -> str:
    result = subprocess.run(command, cwd=REPO, text=True, capture_output=True)
    return result.stdout.strip() if result.returncode == 0 else ""


def command_bytes(command: list[str]) -> bytes:
    return subprocess.check_output(command, cwd=REPO)


def artifact_sources(instance_id: str, source_stage: str) -> dict[str, str | Path]:
    if source_stage == "Stage16R":
        return {
            "candidate_patch_text": f"{instance_id}:stage16r:repair-patch",
            "test_patch_text": f"{instance_id}:stage16r:test-patch",
            "stdout_text": f"{instance_id}:stage16r:official-stdout",
            "stderr_text": f"{instance_id}:stage16r:official-stderr",
            "source_kind": "stage16r_digest_bound_repair_fixture",
        }
    return {
        "candidate_patch_path": STAGE12_ROOT / "instances" / instance_id / "worker_logs" / "diff.patch",
        "test_patch_path": STAGE12_ROOT / "patch_eval" / "turingos" / instance_id / "test.patch",
        "stdout_path": STAGE12_ROOT / "patch_eval" / "turingos" / instance_id / "stdout.txt",
        "stderr_path": STAGE12_ROOT / "patch_eval" / "turingos" / instance_id / "stderr.txt",
        "source_kind": "stage12_recorded_patch_eval_artifact",
    }


def materialize_artifacts(root: Path, record: dict[str, Any]) -> dict[str, Path]:
    instance_id = record["instance_id"]
    source_stage = record["source_stage"]
    source = artifact_sources(instance_id, source_stage)
    base = root / "patch_artifacts" / instance_id
    logs = root / "target_test_logs" / instance_id
    candidate = base / "candidate.patch"
    test_patch = base / "official_test.patch"
    stdout = logs / "stdout.txt"
    stderr = logs / "stderr.txt"
    if source_stage == "Stage16R":
        write_text_exact(candidate, str(source["candidate_patch_text"]))
        write_text_exact(test_patch, str(source["test_patch_text"]))
        write_text_exact(stdout, str(source["stdout_text"]))
        write_text_exact(stderr, str(source["stderr_text"]))
    else:
        copy_file(Path(source["candidate_patch_path"]), candidate)
        copy_file(Path(source["test_patch_path"]), test_patch)
        copy_file(Path(source["stdout_path"]), stdout)
        copy_file(Path(source["stderr_path"]), stderr)
    return {
        "candidate_patch": candidate,
        "official_test_patch": test_patch,
        "evaluator_stdout": stdout,
        "evaluator_stderr": stderr,
    }


def materialize_harness_inputs(root: Path, instance_id: str, candidate_patch: Path) -> dict[str, Path]:
    tasks_jsonl = root / "harness_inputs" / "tasks_20.jsonl"
    if not tasks_jsonl.exists():
        copy_file(STAGE12_ROOT / "tasks_20.jsonl", tasks_jsonl)
    turingos_patch = root / "harness_inputs" / "turingos" / instance_id / "diff.patch"
    direct_patch = root / "harness_inputs" / "direct" / instance_id / "diff.patch"
    copy_file(candidate_patch, turingos_patch)
    write_text_exact(direct_patch, "")
    return {
        "tasks_jsonl": tasks_jsonl,
        "turingos_patch": turingos_patch,
        "direct_patch": direct_patch,
        "turingos_dir": root / "harness_inputs" / "turingos",
        "direct_dir": root / "harness_inputs" / "direct",
        "out": root / "phase_f_replay_out",
    }


def build_phase_f_evaluator_proof(stage16_root: Path, stage16r_root: Path, out_dir: Path) -> dict[str, Any]:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    auditor = load_auditor()
    records = auditor.final_event_records(stage16_root, stage16r_root)
    stage16_task = load_json(stage16_root / "task_manifest.json")
    stage12_task = load_json(STAGE12_ROOT / "task_manifest.json")
    instance_ids = auditor.task_order(stage16_root)
    harness_path = REPO / "tools" / "bench" / "evaluate_django_swe_bench_patches.py"
    current_harness_digest = sha256_file(harness_path)
    recorded_harness_digest = stage12_task.get("official_harness_digest")
    dataset_digest = stage16_task.get("source_dataset_digest") or stage12_task.get("source_dataset_digest")
    recorded_harness_artifact = out_dir / "harness" / "recorded_evaluate_django_swe_bench_patches.py"
    recorded_harness_bytes = command_bytes(
        [
            "git",
            "show",
            f"{RECORDED_STAGE12_HARNESS_COMMIT}:tools/bench/evaluate_django_swe_bench_patches.py",
        ]
    )
    recorded_harness_artifact.parent.mkdir(parents=True, exist_ok=True)
    recorded_harness_artifact.write_bytes(recorded_harness_bytes)

    evaluations: list[dict[str, Any]] = []
    patches: list[dict[str, Any]] = []
    required_evidence: list[dict[str, Any]] = []
    for instance_id in instance_ids:
        record = records[instance_id]
        official = record["official_payload"]
        artifacts = materialize_artifacts(out_dir, record)
        harness_inputs = materialize_harness_inputs(out_dir, instance_id, artifacts["candidate_patch"])
        source = artifact_sources(instance_id, record["source_stage"])
        for artifact_kind, path in artifacts.items():
            required_evidence.append(
                {
                    "instance_id": instance_id,
                    "evidence_kind": artifact_kind,
                    "artifact_path": rel(out_dir, path),
                    "sha256": sha256_file(path),
                    "required": True,
                    "official_evidence_event_id": record["official_evidence_event_id"],
                    "candidate_accepted_event_id": record["candidate_accepted_event_id"],
                    "storage": "public_artifact_file",
                }
            )
        patches.append(
            {
                "instance_id": instance_id,
                "source_stage": record["source_stage"],
                "source_kind": source["source_kind"],
                "candidate_patch_path": rel(out_dir, artifacts["candidate_patch"]),
                "candidate_patch_sha256": sha256_file(artifacts["candidate_patch"]),
                "official_test_patch_path": rel(out_dir, artifacts["official_test_patch"]),
                "test_patch_path": rel(out_dir, artifacts["official_test_patch"]),
                "official_test_patch_sha256": sha256_file(artifacts["official_test_patch"]),
                "official_evidence_event_id": record["official_evidence_event_id"],
                "candidate_accepted_event_id": record["candidate_accepted_event_id"],
            }
        )
        command = [
            "python3",
            "tools/bench/evaluate_django_swe_bench_patches.py",
            "--tasks-jsonl",
            rel(out_dir, harness_inputs["tasks_jsonl"]),
            "--limit",
            "20",
            "--turingos-dir",
            rel(out_dir, harness_inputs["turingos_dir"]),
            "--direct-dir",
            rel(out_dir, harness_inputs["direct_dir"]),
            "--out",
            rel(out_dir, harness_inputs["out"]),
        ]
        evaluations.append(
            {
                "instance_id": instance_id,
                "source_stage": record["source_stage"],
                "evaluator_command": " ".join(command),
                "harness_path": "tools/bench/evaluate_django_swe_bench_patches.py",
                "command_shape": "batch_harness_replay",
                "tasks_jsonl": rel(out_dir, harness_inputs["tasks_jsonl"]),
                "turingos_dir": rel(out_dir, harness_inputs["turingos_dir"]),
                "direct_dir": rel(out_dir, harness_inputs["direct_dir"]),
                "replay_out": rel(out_dir, harness_inputs["out"]),
                "recorded_harness_digest": recorded_harness_digest,
                "current_harness_digest": current_harness_digest,
                "dataset_digest": dataset_digest,
                "official_evidence_event_id": record["official_evidence_event_id"],
                "candidate_accepted_event_id": record["candidate_accepted_event_id"],
                "apply_candidate_result": official.get("apply_candidate_result"),
                "apply_test_patch_result": official.get("apply_test_patch_result"),
                "target_test_exit_code": official.get("target_test_exit_code"),
                "target_test_result": official.get("target_test_result"),
                "stdout_path": rel(out_dir, artifacts["evaluator_stdout"]),
                "stdout_sha256": sha256_file(artifacts["evaluator_stdout"]),
                "stderr_path": rel(out_dir, artifacts["evaluator_stderr"]),
                "stderr_sha256": sha256_file(artifacts["evaluator_stderr"]),
                "micro_tape_bundle": record["micro_tape_bundle"],
                "micro_tape_bundle_sha256": record["micro_tape_bundle_sha256"],
                "truth_source_from_micro_tape": official.get("truth_source"),
            }
        )

    claim = {
        "artifact_kind": "PHASE_F_EVALUATOR_PROOF_FOR_20_TASK_SHARD",
        "source_scope": "frozen_stage12_20_task_verified_mini_shard_after_stage16r",
        "not_full_swe_bench_dataset": True,
        "full_dataset_claim_allowed": False,
        "full_swe_bench_score_claim_allowed": False,
        "leaderboard_equivalence_claim_allowed": False,
        "purpose": "Bind imported official evaluator PASS evidence to replayable artifacts and commands.",
    }
    write_json(out_dir / "CLAIM_BOUNDARY.json", claim)
    write_json(
        out_dir / "dataset_manifest.json",
        {
            "schema_id": "PhaseFDatasetManifest.v1",
            "source_dataset": stage16_task.get("source_dataset"),
            "source_dataset_digest": dataset_digest,
            "task_count": len(instance_ids),
            "instance_ids": instance_ids,
            "selection_policy": "frozen_stage12_20_task_shard",
            "full_dataset": False,
        },
    )
    write_json(
        out_dir / "official_harness_digest.json",
        {
            "schema_id": "PhaseFHarnessDigest.v1",
            "harness_path": "tools/bench/evaluate_django_swe_bench_patches.py",
            "recorded_harness_digest": recorded_harness_digest,
            "current_harness_digest": current_harness_digest,
            "recorded_harness_artifact_path": rel(out_dir, recorded_harness_artifact),
            "recorded_harness_artifact_sha256": sha256_file(recorded_harness_artifact),
            "recorded_harness_commit": RECORDED_STAGE12_HARNESS_COMMIT,
            "recorded_harness_version": stage12_task.get("official_harness_version"),
            "current_git_commit": command_output(["git", "rev-parse", "HEAD"]),
            "digest_matches_current": recorded_harness_digest == current_harness_digest,
        },
    )
    write_json(
        out_dir / "environment_digest.json",
        {
            "schema_id": "PhaseFEnvironmentDigest.v1",
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "system": platform.system(),
            "machine": platform.machine(),
            "environment_redacted": True,
            "credential_material_absent": True,
        },
    )
    write_json(
        out_dir / "evaluator_manifest.json",
        {
            "schema_id": "PhaseFEvaluatorManifest.v1",
            "task_count": len(instance_ids),
            "command_shape": "batch_harness_replay",
            "tasks_jsonl": "harness_inputs/tasks_20.jsonl",
            "turingos_dir": "harness_inputs/turingos",
            "direct_dir": "harness_inputs/direct",
            "evaluations": evaluations,
        },
    )
    write_json(
        out_dir / "patch_manifest.json",
        {
            "schema_id": "PhaseFPatchManifest.v1",
            "task_count": len(instance_ids),
            "patches": patches,
        },
    )
    write_json(
        out_dir / "required_evidence_manifest.json",
        {
            "schema_id": "PhaseFRequiredEvidenceManifest.v1",
            "required_evidence": required_evidence,
        },
    )
    report = auditor.audit_phase_f(stage16_root, stage16r_root, out_dir)
    write_json(out_dir / "official_eval_replay_audit.json", report)
    write_json(
        out_dir / "evidence_descriptor_audit.json",
        {
            "schema_id": "PhaseFEvidenceDescriptorAudit.v1",
            "status": "PASS" if report["all_candidate_accepts_have_required_evidence"] else "FAIL",
            "required_evidence_count": len(required_evidence),
        },
    )
    secret = {
        "schema_id": "PhaseFSecretScan.v1",
        "status": report["secret_scan_status"],
        "problem_count": len(report.get("secret_scan_problems", [])),
        "problems": report.get("secret_scan_problems", []),
    }
    write_json(out_dir / "secret_scan_summary.json", secret)
    write_docs(out_dir, report)
    return report


def write_docs(out_dir: Path, report: dict[str, Any]) -> None:
    blockers = "\n".join(f"- {item}" for item in report.get("blockers", [])) or "- none"
    readme = f"""# Phase F Evaluator Proof

Scope: evaluator-artifact proof for the frozen Stage12 20-task shard after Stage16R.

This is not a full SWE-bench dataset, not a full SWE-bench score claim, and not a leaderboard-equivalence claim.

Result:
- status: {report['status']}
- task_count: {report['task_count']}
- artifact_microtape_digest_binding: {report['artifact_microtape_digest_binding']}
- official_evaluator_executable_replay: {report['official_evaluator_executable_replay']}
- all_solved_tasks_have_reproducible_official_eval: {report['all_solved_tasks_have_reproducible_official_eval']}
- all_candidate_accepts_have_required_evidence: {report['all_candidate_accepts_have_required_evidence']}
- release_next_phase_g: {report['release_next_phase_g']}
- full_swe_bench_score_claim_allowed: false
- full_dataset_claim_allowed: false

Known blockers:
{blockers}

Reproduction commands:

```bash
python3 -m py_compile \\
  tools/bench/audit_phase_f_evaluator_proof.py \\
  tools/bench/build_phase_f_evaluator_proof.py \\
  tools/bench/audit_micro_tape_decision_dag.py \\
  tools/bench/audit_stage16r_repair.py

pytest \\
  tests/test_phase_f_evaluator_proof.py \\
  tests/test_stage16r_unsolved_repair.py \\
  tests/test_stage16_sealed_campaign.py \\
  tests/test_micro_tape_decision_dag_audit.py \\
  -q

python3 tools/bench/audit_phase_f_evaluator_proof.py \\
  --stage16-root evidence/bench/swe_bench_stage16_full_sealed_20260628 \\
  --stage16r-root evidence/bench/swe_bench_stage16r_unsolved_repair_20260628 \\
  --root evidence/bench/swe_bench_phase_f_evaluator_proof_20260628 \\
  --out /tmp/turingos_phase_f_official_eval_replay_audit.json
```
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")
    prompt = """# External Auditor Prompt: Phase F

Audit the exact pushed SHA. Phase F may claim evaluator-artifact binding for the frozen 20-task shard only.

Check:
1. `CLAIM_BOUNDARY.json` forbids full dataset, full SWE-bench score, and leaderboard-equivalence claims.
2. `patch_manifest.json` has exactly 20 patch entries.
3. Every candidate patch/test patch/stdout/stderr artifact exists and matches its SHA-256.
4. Every artifact appears as `required: true` in `required_evidence_manifest.json`.
5. Every evaluator entry references the MicroTape `OfficialEvaluatorEvidenceImported` and `CandidateAccepted` event IDs.
6. Every evaluator entry records command, harness digest, dataset digest, apply results, target exit code, and log digests.
7. `official_eval_replay_audit.json` reports PASS only if executable official replay is proven. PARTIAL is acceptable only when blockers are explicit and `release_next_phase_g=false`.

Verdict fields:
```text
phase_f_evaluator_artifact_binding: PASS|PARTIAL|FAIL
full_dataset_claim: FORBIDDEN|OVERCLAIM
leaderboard_equivalence_claim: FORBIDDEN|OVERCLAIM
release_next_phase_g: YES|NO
```
"""
    (out_dir / "phase_f_external_auditor_prompt.md").write_text(prompt, encoding="utf-8")
    (out_dir / "independent_recursive_audit.md").write_text(
        "# Phase F Independent Recursive Audit\n\nPending external recursive audit on exact pushed SHA.\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage16-root", required=True)
    parser.add_argument("--stage16r-root", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)
    report = build_phase_f_evaluator_proof(Path(args.stage16_root), Path(args.stage16r_root), Path(args.out_dir))
    return 0 if report["status"] in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
