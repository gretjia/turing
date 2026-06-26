#!/usr/bin/env python3
"""Run local deterministic gates and emit GateResult.v1 receipts."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from headless_common import (
    executed_clean_fixture,
    executed_tampered_fixture,
    gate_result,
    sha256_path,
    which_digest,
    write_json,
)


def tool_path_for(argv: list[str]) -> Path:
    if not argv:
        return Path(__file__).resolve()
    first = Path(argv[0])
    if first.is_absolute():
        return first
    resolved = shutil.which(argv[0])
    return Path(resolved) if resolved else Path(__file__).resolve()


def authority_kernel_command() -> list[str]:
    return [
        "cargo",
        "test",
        "-p",
        "turing-contracts",
        "-p",
        "turing-git-tape",
        "-p",
        "turing-kernel",
        "-p",
        "turing-replay",
    ]


def run(argv: list[str], cwd: Path) -> dict:
    proc = subprocess.run(argv, cwd=cwd, text=True, capture_output=True)
    return {
        "argv": argv,
        "exit_status": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def write_command_gate(repo: Path, out_dir: Path, gate_id: str, argv: list[str]) -> dict:
    logs = out_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    result = run(argv, repo)
    log_path = logs / f"{gate_id}.json"
    write_json(log_path, result)
    receipt = gate_result(
        gate_id=gate_id,
        phase_id="F0-F8",
        command_argv=argv,
        exit_status=result["exit_status"],
        reasons=[
            {
                "id": "command_exit_zero",
                "verdict": "PASS" if result["exit_status"] == 0 else "FAIL",
            }
        ],
        not_run=[],
        tool_path=tool_path_for(argv),
        input_paths=[repo / "Cargo.toml", repo / "pyproject.toml"],
        output_path=log_path,
        stdout=result["stdout"],
        stderr=result["stderr"],
        clean_fixture_results=[executed_clean_fixture(repo, out_dir, gate_id)],
        tampered_fixture_results=[executed_tampered_fixture(repo, out_dir, gate_id)],
    )
    write_json(out_dir / "gate_results" / f"{gate_id}.json", receipt)
    return receipt


def write_runsc_gate(repo: Path, out_dir: Path) -> dict:
    logs = out_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    runsc, _digest = which_digest("runsc")
    not_run = []
    if runsc is None:
        not_run.append("runsc_missing")
        green = {"argv": ["runsc"], "exit_status": 127, "stdout": "", "stderr": "runsc missing"}
        red = {"argv": ["runsc"], "exit_status": 127, "stdout": "", "stderr": "runsc missing"}
    else:
        green = run(
            [runsc, "--rootless", "--ignore-cgroups", "--network=none", "do", "/bin/true"],
            repo,
        )
        red = run(
            [
                runsc,
                "--rootless",
                "--ignore-cgroups",
                "--network=none",
                "do",
                "/bin/sh",
                "-c",
                "exit 7",
            ],
            repo,
        )
    log_path = logs / "G7-RUNSC-RED-GREEN.json"
    write_json(log_path, {"green": green, "red": red})
    reasons = [
        {
            "id": "runsc_green_executes_true",
            "verdict": "PASS" if green["exit_status"] == 0 else "FAIL",
        },
        {
            "id": "runsc_red_preserves_child_failure",
            "verdict": "PASS" if red["exit_status"] == 7 else "FAIL",
        },
    ]
    receipt = gate_result(
        gate_id="G7-RUNSC-RED-GREEN",
        phase_id="F5",
        command_argv=[runsc or "runsc", "--rootless", "--ignore-cgroups", "--network=none", "do", "<probe>"],
        exit_status=0 if green["exit_status"] == 0 and red["exit_status"] == 7 else 1,
        reasons=reasons,
        not_run=not_run,
        tool_path=Path(runsc) if runsc else Path(__file__).resolve(),
        input_paths=[repo / "evidence/g12/phase_capsule.json"],
        output_path=log_path,
        stdout=green["stdout"] + red["stdout"],
        stderr=green["stderr"] + red["stderr"],
        clean_fixture_results=[
            {
                "id": "runsc_green_true",
                "verdict": "PASS" if green["exit_status"] == 0 else "FAIL",
                "executed": True,
                "exit_status": green["exit_status"],
                "argv": green["argv"],
            }
        ],
        tampered_fixture_results=[
            {
                "id": "runsc_red_exit_7",
                "verdict": "FAIL" if red["exit_status"] == 7 else "PASS",
                "executed": True,
                "exit_status": red["exit_status"],
                "argv": red["argv"],
            }
        ],
    )
    write_json(out_dir / "gate_results" / "G7-RUNSC-RED-GREEN.json", receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--skip-slow", action="store_true")
    args = parser.parse_args(argv)

    script = Path(__file__).resolve()
    repo = script.parents[2]
    out_dir = Path(args.out_dir)
    (out_dir / "gate_results").mkdir(parents=True, exist_ok=True)

    receipts = []
    receipts.append(write_command_gate(repo, out_dir, "G1-RUST-AUTHORITY-KERNEL", authority_kernel_command()))
    receipts.append(
        write_command_gate(
            repo,
            out_dir,
            "G-ADVERSARY-UNION",
            ["python3", "tools/headless/run_adversary_union.py", "--out", str(out_dir / "adversary_union_run.json")],
        )
    )
    if not args.skip_slow:
        receipts.append(write_command_gate(repo, out_dir, "G-PYTEST", ["python3", "-m", "pytest"]))
        receipts.append(
            write_command_gate(repo, out_dir, "G-CARGO-FMT", ["cargo", "fmt", "--all", "--", "--check"])
        )
        receipts.append(
            write_command_gate(
                repo,
                out_dir,
                "G-CARGO-CLIPPY",
                ["cargo", "clippy", "--workspace", "--all-targets", "--", "-D", "warnings"],
            )
        )
        receipts.append(write_command_gate(repo, out_dir, "G-CARGO-TEST", ["cargo", "test", "--workspace"]))
    receipts.append(write_runsc_gate(repo, out_dir))

    summary_path = out_dir / "local_gate_summary.json"
    summary = {
        "schema_id": "LocalGateSummary.v1",
        "receipts": [str(out_dir / "gate_results" / f"{r['gate_id']}.json") for r in receipts],
        "products": {r["gate_id"]: r["product"] for r in receipts},
    }
    write_json(summary_path, summary)
    print(json.dumps({"summary": str(summary_path), "products": summary["products"]}, sort_keys=True))
    return 0 if all(r["product"] == "PASS" for r in receipts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
