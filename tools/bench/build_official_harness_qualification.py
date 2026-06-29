#!/usr/bin/env python3
"""Build an upstream SWE-bench Docker harness qualification packet.

The packet is BLOCKED until real `python -m swebench.harness.run_evaluation`
artifacts are present. It never rewrites Phase F/Stage16 evidence and never
treats repo-local evaluator output as official SWE-bench evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def rel(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def command_output(args: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(args, text=True, capture_output=True, timeout=10, check=False)
    except Exception as exc:  # pragma: no cover - defensive environment probe
        return False, str(exc)
    return result.returncode == 0, (result.stdout + result.stderr).strip()


def environment_preflight(swebench_package_present: bool | None = None) -> dict[str, Any]:
    docker_path = shutil.which("docker")
    docker_ok = False
    docker_version = None
    if docker_path:
        docker_ok, docker_version = command_output([docker_path, "--version"])
    if swebench_package_present is None:
        swebench_package_present = importlib.util.find_spec("swebench") is not None
    return {
        "docker_available": docker_path is not None,
        "docker_version": docker_version,
        "docker_environment_used": False,
        "swebench_package_present": bool(swebench_package_present),
        "python_swebench_module": "swebench.harness.run_evaluation",
    }


def build_predictions_from_phase_f(phase_f_root: Path, out_root: Path) -> dict[str, Any]:
    patch_manifest = load_json(phase_f_root / "patch_manifest.json")
    rows: list[dict[str, Any]] = []
    patch_records: list[dict[str, Any]] = []
    for item in patch_manifest.get("patches", []):
        if not isinstance(item, dict):
            continue
        instance_id = item["instance_id"]
        candidate = rel(phase_f_root, item["candidate_patch_path"])
        patch_text = candidate.read_text(encoding="utf-8")
        candidate_out = out_root / "patch_artifacts" / instance_id / "candidate.patch"
        candidate_out.parent.mkdir(parents=True, exist_ok=True)
        candidate_out.write_text(patch_text, encoding="utf-8")
        rows.append(
            {
                "instance_id": instance_id,
                "model_name_or_path": "turingos-phase-f-official-qualification",
                "model_patch": patch_text,
                "candidate_patch_sha256": sha256_file(candidate_out),
                "candidate_source": "worker_derived",
            }
        )
        patch_records.append(
            {
                "instance_id": instance_id,
                "candidate_patch_path": str(candidate_out.relative_to(out_root)),
                "candidate_patch_sha256": sha256_file(candidate_out),
                "candidate_source": "worker_derived",
                "source_phase_f_patch_sha256": item.get("candidate_patch_sha256"),
            }
        )
    predictions = out_root / "predictions_phase_f_20.jsonl"
    predictions.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    write_json(out_root / "patch_manifest.json", {"patches": patch_records, "patch_count": len(patch_records)})
    return {
        "predictions_path": str(predictions.relative_to(out_root)),
        "predictions_sha256": sha256_file(predictions),
        "prediction_count": len(rows),
    }


def build_qualification(
    phase_f_root: Path,
    out_root: Path,
    *,
    swebench_package_present: bool | None = None,
) -> dict[str, Any]:
    out_root.mkdir(parents=True, exist_ok=True)
    preflight = environment_preflight(swebench_package_present=swebench_package_present)
    predictions = build_predictions_from_phase_f(phase_f_root, out_root)
    command = (
        "python -m swebench.harness.run_evaluation "
        "--dataset_name princeton-nlp/SWE-bench_Verified "
        "--split test "
        f"--predictions_path {predictions['predictions_path']} "
        "--run_id turingos_phase_f_official_qualification "
        "--max_workers 2"
    )
    # Placeholder files make the missing executable evidence explicit and hash-bound.
    for rel_path, text in {
        "logs/run_stdout.txt": "",
        "logs/run_stderr.txt": "",
        "logs/docker_build_or_cache.log": "",
    }.items():
        path = out_root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    qualification = {
        "schema_id": "turingos.official_swebench_harness_qualification.v1",
        "status": "BLOCKED",
        "official_harness_kind": "upstream_swebench_docker",
        "command": command,
        "dataset_name": "princeton-nlp/SWE-bench_Verified",
        "split": "test",
        "docker_environment_used": False,
        "docker_available": preflight["docker_available"],
        "docker_version": preflight["docker_version"],
        "swebench_package_present": preflight["swebench_package_present"],
        "evaluation_results_present": False,
        "stdout_stderr_digests_present": False,
        "docker_build_or_cache_logs_present": False,
        "fail_to_pass_checked": False,
        "pass_to_pass_checked": False,
        "repo_local_evaluator_marked_official": False,
        "predictions_path": predictions["predictions_path"],
        "evaluation_results_path": "evaluation_results/results.json",
        "stdout_path": "logs/run_stdout.txt",
        "stderr_path": "logs/run_stderr.txt",
        "docker_build_or_cache_log_path": "logs/docker_build_or_cache.log",
        "release_next_phase_g": False,
        "required_next_action": "run_upstream_swebench_docker_harness_and_bind_results",
    }
    write_json(out_root / "official_harness_qualification.json", qualification)
    write_json(
        out_root / "CLAIM_BOUNDARY.json",
        {
            "artifact_kind": "OFFICIAL_SWEBENCH_DOCKER_HARNESS_QUALIFICATION",
            "source_phase_f_root": str(phase_f_root),
            "full_swe_bench_score_claim_allowed": False,
            "leaderboard_equivalence_claim_allowed": False,
            "repo_local_evaluator_official_claim_allowed": False,
            "campaign_launch_allowed": False,
        },
    )
    write_json(out_root / "environment_preflight.json", preflight)
    readme = """# Official SWE-bench Harness Qualification

This packet is BLOCKED until real upstream SWE-bench Docker harness output is
present. It prepares worker-derived predictions from the Phase F 20-task shard
and records the required `python -m swebench.harness.run_evaluation` command.

It does not rewrite old MicroTape and does not mark repo-local evaluator output
as official SWE-bench evidence.
"""
    (out_root / "README.md").write_text(readme, encoding="utf-8")
    return qualification


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase-f-root", type=Path, required=True)
    parser.add_argument("--out-root", type=Path, required=True)
    args = parser.parse_args()
    report = build_qualification(args.phase_f_root, args.out_root)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
