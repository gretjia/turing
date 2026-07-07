#!/usr/bin/env python3
"""FCE-R1: full test suites and module gates green at the pinned cert SHA."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
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


def secure_private_tmp_dir(scenario_root: Path) -> Path:
    """Create a private (0700, owned-by-invoker) tmp root and return it.
    Daemon-spawning tests (Rust's tempfile::tempdir() and Python's tempfile
    module) both honor $TMPDIR; pointing it here means every per-test/per-daemon
    temp dir nests under an already-private directory instead of directly under
    the shared, world-writable (mode 1777) ambient /tmp -- hardening against
    umask/ambient-/tmp permission flakes in marketd's (and every other daemon's)
    socket-parent security check without weakening that check.

    Created OUTSIDE the scenario evidence root (mkdtemp is 0700 by design): if it
    lived under scenario_root, pytest fixtures written into it (e.g.
    test_stage12_contract_secret's `sk-` placeholder, or 0-byte temp files) would
    be swept into the FCE evidence tree that FCE-R5's secret-marker scan and
    FCE-R3's ops-inventory walk -- producing false redline/hygiene violations for
    another scenario's transient test data. `scenario_root` is retained for the
    signature/callsite but the dir is deliberately not nested under it.
    """
    del scenario_root  # intentionally not nested under the evidence root; see docstring
    private_tmp = Path(tempfile.mkdtemp(prefix="fce-r1-privtmp-"))
    os.chmod(private_tmp, 0o700)
    return private_tmp


def pytest_env(tmpdir: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = "src"
    env.pop("FCE_CONTEXT_SEPARATED", None)
    env["TMPDIR"] = str(tmpdir)
    return env


def cargo_env(tmpdir: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["TMPDIR"] = str(tmpdir)
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


def build_verdict(
    root: Path,
    scenario_id: str,
    commands: list[dict[str, Any]],
    started: float,
    evidence_files: list[Path] | None = None,
) -> dict[str, Any]:
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
    for path in evidence_files or []:
        if path.is_file():
            evidence_paths.append(rel(root, path))
    evidence_paths = sorted(set(evidence_paths))

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

    private_tmp = secure_private_tmp_dir(scenario_root)
    py_env = pytest_env(private_tmp)
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
            env=cargo_env(private_tmp),
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

    readme_path = scenario_root / "README.md"
    readme_path.write_text(
        "\n".join(
            [
                "# FCE-R1 Full Test Suites and Module Gates Green",
                "",
                "Evidence label: REAL.",
                "This scenario runs the real Python and Rust test suites, the M1A and",
                "HCI gate scripts, and the M0 alignment verifier at the pinned cert SHA,",
                "and records each command's real exit code as a pass criterion.",
                "",
                "Daemon-spawning tests (Rust `tempfile::tempdir()`, Python `tempfile`)",
                "are pointed at a private, scenario-local `private_tmp` (mode 0700,",
                "owned by the invoking user) via `TMPDIR`, so socket-parent directories",
                "never nest directly under the ambient, world-writable `/tmp`.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    claim_boundary_path = scenario_root / "CLAIM_BOUNDARY.json"
    write_json(
        claim_boundary_path,
        {
            "schema_id": "CLAIM_BOUNDARY.v2",
            "evidence_class": "REAL",
            "claims": ["FCE-R1 real test-suite and gate-script exit codes at the pinned cert SHA"],
            "non_claims": [
                "not a release decision",
                "not release eligibility",
                "not CLOSED/RELEASED/RATIFIED",
                "not SHIPPED",
                "not OG-10/genesis signature or M2 enablement",
            ],
        },
    )
    evidence_files = [readme_path, claim_boundary_path]

    verdict = build_verdict(root, scenario_id, commands, started, evidence_files=evidence_files)
    write_json(scenario_root / f"{scenario_id}_verdict.json", verdict)
    return 0 if verdict["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
