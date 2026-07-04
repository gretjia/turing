#!/usr/bin/env python3
"""FCE-R1: full test suites and module gates green at the pinned cert SHA."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def pytest_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = "src"
    env.pop("FCE_CONTEXT_SEPARATED", None)
    return env


def rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def run_command(
    *,
    name: str,
    argv: list[str],
    repo: Path,
    out_dir: Path,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    proc = subprocess.run(
        argv,
        cwd=repo,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    stdout = out_dir / f"{name}.stdout.txt"
    stderr = out_dir / f"{name}.stderr.txt"
    stdout.write_text(proc.stdout, encoding="utf-8")
    stderr.write_text(proc.stderr, encoding="utf-8")
    return {
        "name": name,
        "cmd": " ".join(argv),
        "exit_code": proc.returncode,
        "wall_clock_ms": elapsed_ms,
        "stdout": stdout.name,
        "stderr": stderr.name,
    }


def build_verdict(root: Path, scenario_id: str, commands: list[dict[str, Any]], started: float) -> dict[str, Any]:
    scenario_root = root / scenario_id
    command_results = scenario_root / "command_results.json"
    write_json(command_results, {"schema_id": "turingos.fce.r1.command_results.v1", "commands": commands})

    evidence_paths = [rel(root, command_results)]
    for command in commands:
        evidence_paths.append(f"{scenario_id}/{command['stdout']}")
        evidence_paths.append(f"{scenario_id}/{command['stderr']}")
    hci_result = scenario_root / "hci_gates" / "hci_gates_result.json"
    if hci_result.is_file():
        evidence_paths.append(rel(root, hci_result))

    evidence_sha = {item: sha256_file(root / item) for item in evidence_paths}
    criteria = [
        {
            "criterion": f"{command['name']}_exit_zero",
            "result": command["exit_code"] == 0,
            "evidence": rel(root, command_results),
        }
        for command in commands
    ]
    passed = all(item["result"] for item in criteria)
    return {
        "schema_id": "turingos.fce_scenario_verdict.v1",
        "scenario_id": scenario_id,
        "verdict": "PASS" if passed else "FAIL",
        "not_run_is_fail": True,
        "goals_served": ["G2"],
        "commands_executed": [
            {"cmd": command["cmd"], "exit_code": command["exit_code"]} for command in commands
        ],
        "pass_criteria_results": criteria,
        "evidence": evidence_paths,
        "evidence_sha256": evidence_sha,
        "fixture_or_real": "REAL",
        "automatic_fail_triggered": None,
        "wall_clock_ms": int((time.monotonic() - started) * 1000),
        "timestamp_utc": utc_now(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--plan-root", required=True)
    parser.add_argument("--scenario-id", required=True)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    repo = Path(args.repo).resolve()
    plan_root = Path(args.plan_root).resolve()
    scenario_id = args.scenario_id
    scenario_root = root / scenario_id
    scenario_root.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    py_env = pytest_env()
    commands = [
        run_command(
            name="python_pytest_collect",
            argv=["python3", "-m", "pytest", "--collect-only", "-q", "tests"],
            repo=repo,
            out_dir=scenario_root,
            env=py_env,
        ),
        run_command(
            name="python_pytest_full",
            argv=["python3", "-m", "pytest", "-q", "tests"],
            repo=repo,
            out_dir=scenario_root,
            env=py_env,
        ),
        run_command(
            name="rust_cargo_workspace",
            argv=["cargo", "test", "--workspace", "--quiet"],
            repo=repo,
            out_dir=scenario_root,
        ),
        run_command(
            name="m1a_self_test",
            argv=["bash", "tools/ci/run_m1a_gates.sh", "--self-test"],
            repo=repo,
            out_dir=scenario_root,
        ),
        run_command(
            name="m1a_gates",
            argv=["bash", "tools/ci/run_m1a_gates.sh"],
            repo=repo,
            out_dir=scenario_root,
        ),
        run_command(
            name="hci_self_test",
            argv=["bash", "tools/hci/run_hci_gates.sh", "--self-test", "--out-dir", str(scenario_root / "hci_self_test")],
            repo=repo,
            out_dir=scenario_root,
        ),
        run_command(
            name="hci_gates",
            argv=["bash", "tools/hci/run_hci_gates.sh", "--out-dir", str(scenario_root / "hci_gates")],
            repo=repo,
            out_dir=scenario_root,
        ),
        run_command(
            name="m0_alignment",
            argv=["bash", str(plan_root / "governance/verify_alignment.sh")],
            repo=repo,
            out_dir=scenario_root,
        ),
    ]
    verdict = build_verdict(root, scenario_id, commands, started)
    write_json(scenario_root / f"{scenario_id}_verdict.json", verdict)
    return 0 if verdict["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
