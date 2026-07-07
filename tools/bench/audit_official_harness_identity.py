#!/usr/bin/env python3
"""Gate official SWE-bench harness identity.

Repo-local target-test runners can be useful internal replay evidence, but they
cannot satisfy this gate. The official launch path must be upstream SWE-bench
Docker `python -m swebench.harness.run_evaluation` with FAIL_TO_PASS and
PASS_TO_PASS evidence.
"""

from __future__ import annotations

import argparse
import json
import shlex
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


def contains_run_evaluation(command: Any) -> bool:
    if not isinstance(command, str):
        return False
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    return "-m" in parts and "swebench.harness.run_evaluation" in parts


def audit_config(config_path: Path) -> dict[str, Any]:
    config = load_json(config_path)
    problems: list[str] = []
    if config.get("official_harness_kind") != "upstream_swebench_docker":
        problems.append("official_harness_kind must be upstream_swebench_docker")
    if not contains_run_evaluation(config.get("command")):
        problems.append("command must invoke python -m swebench.harness.run_evaluation")
    for key in [
        "docker_environment_used",
        "evaluation_results_present",
        "stdout_stderr_digests_present",
        "docker_build_or_cache_logs_present",
        "fail_to_pass_checked",
        "pass_to_pass_checked",
    ]:
        if config.get(key) is not True:
            problems.append(f"{key} must be true")
    if config.get("repo_local_evaluator_marked_official") is not False:
        problems.append("repo-local evaluator cannot be marked official")
    return {
        "schema_id": "turingos.official_harness_identity_audit.v1",
        "status": "PASS" if not problems else "FAIL",
        "problems": problems,
        "official_harness_kind": config.get("official_harness_kind"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = audit_config(args.config)
    write_json(args.out, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
