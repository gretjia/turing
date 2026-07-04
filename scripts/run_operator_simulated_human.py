#!/usr/bin/env python3
"""Exercise Operator Console v1 as a simulated human UX walk-through."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence" / "operator_hci_console_v1" / "simulated_human"
SWE_BUNDLE = (
    ROOT
    / "evidence"
    / "bench"
    / "mini_swe_bench_stage2_3task_20260627"
    / "turingos"
    / "instances"
    / "django__django-11790"
    / "micro_tape.bundle"
)
SWE_COVERAGE = (
    ROOT
    / "evidence"
    / "bench"
    / "mini_swe_bench_stage2_3task_20260627"
    / "turingos"
    / "substrate_coverage.json"
)


@dataclass(frozen=True)
class Step:
    name: str
    argv: list[str]
    expected_exit: int = 0
    stdin: str | None = None
    env_delta: dict[str, str] = field(default_factory=dict)
    require: tuple[str, ...] = ()


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def run_step(step: Step) -> dict:
    env = {**os.environ, **step.env_delta}
    started = time.monotonic()
    result = subprocess.run(
        step.argv,
        cwd=ROOT,
        input=step.stdin,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    stdout_path = OUT / f"{step.name}.stdout"
    stderr_path = OUT / f"{step.name}.stderr"
    stdout_path.write_text(result.stdout, encoding="utf-8")
    stderr_path.write_text(result.stderr, encoding="utf-8")
    missing = [needle for needle in step.require if needle not in result.stdout + result.stderr]
    status = "PASS" if result.returncode == step.expected_exit and not missing else "FAIL"
    return {
        "name": step.name,
        "argv": step.argv,
        "expected_exit": step.expected_exit,
        "exit_code": result.returncode,
        "status": status,
        "elapsed_ms": elapsed_ms,
        "env_delta": step.env_delta,
        "stdout_path": str(stdout_path.relative_to(ROOT)),
        "stderr_path": str(stderr_path.relative_to(ROOT)),
        "stdout_sha256": digest(result.stdout),
        "stderr_sha256": digest(result.stderr),
        "required_output_missing": missing,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    turing = str(ROOT / "target" / "debug" / "turing")
    build = subprocess.run(
        ["cargo", "build", "-p", "turing-cli", "--quiet"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    (OUT / "cargo_build.stdout").write_text(build.stdout, encoding="utf-8")
    (OUT / "cargo_build.stderr").write_text(build.stderr, encoding="utf-8")
    if build.returncode != 0:
        summary = {
            "schema_id": "operator_simulated_human_report.v1",
            "status": "FAIL",
            "reason": "cargo build failed",
            "build_exit_code": build.returncode,
        }
        (OUT / "commands.summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return build.returncode

    common_approval = [
        "--key-id",
        "operator-local-key",
        "--approval-id",
        "sim_sign",
        "--authority-epoch",
        "7",
        "--action",
        "capsule_approve",
        "--subject",
        "wc_sim",
        "--risk",
        "P2",
        "--evidence-digest",
        "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    ]
    steps = [
        Step("help", [turing, "--help"], require=("Operator Console v1",)),
        Step("help_commands", [turing, "help", "commands"], require=("topic=commands",)),
        Step("status_demo", [turing, "status"], require=("operator_view_snapshot.v1",)),
        Step("panoview_demo", [turing, "panoview"], require=("safe commands:",)),
        Step("explain_blocker", [turing, "explain", "blocker"], require=("EXPLAIN_BLOCKER",)),
        Step(
            "explain_event",
            [
                turing,
                "explain",
                "event",
                "mu:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            ],
            require=("EXPLAIN_EVENT", "event_id=mu:"),
        ),
        Step("ask_approve_zh", [turing, "ask", "请批准这个 candidate"], require=("APPROVE_CANDIDATE",)),
        Step("ask_reject", [turing, "ask", "reject candidate cand1"], require=("REJECT_CANDIDATE",)),
        Step("ask_replay", [turing, "ask", "replay verify"], require=("REPLAY_VERIFY",)),
        Step("ask_propose_goal", [turing, "ask", "propose goal repair django"], require=("PROPOSE_GOAL",)),
        Step(
            "ask_propose_capsule",
            [turing, "ask", "propose capsule for django"],
            require=("PROPOSE_CAPSULE",),
        ),
        Step(
            "operator",
            [turing, "operator"],
            stdin=(
                "status\n"
                "explain event mu:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
                "help\n"
                "quit\n"
            ),
            require=("operator_view_snapshot.v1", "EXPLAIN_EVENT", "HELP"),
        ),
        Step(
            "approval_preview",
            [
                turing,
                "approval",
                "preview",
                "--approval-id",
                "sim_preview",
                "--authority-epoch",
                "7",
                "--action",
                "capsule_approve",
                "--subject",
                "wc_sim",
                "--risk",
                "P2",
                "--evidence-digest",
                "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "--signature-route",
                "none",
            ],
            require=("source_head_values=tape_tip:mu:", "post_approval_state=", "writes_micro_truth=false"),
        ),
        Step(
            "approval_sign_test_rejected",
            [turing, "approval", "sign", *common_approval, "--signature-route", "in-memory-test"],
            expected_exit=2,
            require=("--allow-test-signature", "test-only"),
        ),
        Step(
            "approval_sign_test",
            [
                turing,
                "approval",
                "sign",
                *common_approval,
                "--signature-route",
                "in-memory-test",
                "--allow-test-signature",
            ],
            require=("test_signature_only=true", "writes_micro_truth=false"),
        ),
        Step(
            "approval_hardware_expected_fail",
            [
                turing,
                "approval",
                "sign",
                "--key-id",
                "future-hsm-slot-0",
                "--approval-id",
                "sim_hardware",
                "--authority-epoch",
                "7",
                "--action",
                "capsule_approve",
                "--subject",
                "wc_sim",
                "--risk",
                "P2",
                "--evidence-digest",
                "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
                "--signature-route",
                "hardware-future",
            ],
            expected_exit=2,
            require=("hardware signing backend", "unavailable"),
        ),
        Step(
            "python_agent",
            [
                "python3",
                "-c",
                (
                    "import json; "
                    "from turingos.operator_agent import OperatorAgent; "
                    "print(json.dumps(OperatorAgent().route_turn('dispatch worker'), sort_keys=True))"
                ),
            ],
            env_delta={"PYTHONPATH": "src"},
            require=("operator_turn_trace.v1", "can_autonomous_dispatch"),
        ),
        Step("hci_copy_lint", ["python3", "scripts/lint_hci_copy.py", "docs/hci"], require=("PASS",)),
        Step("cli_copy_audit", ["python3", "scripts/audit_operator_cli_copy.py"], require=("PASS",)),
        Step(
            "schema_lint",
            ["python3", "scripts/lint_ascii_schema_keys.py", "schemas/operator"],
            require=("PASS",),
        ),
        Step(
            "operator_audit",
            ["python3", "scripts/audit_operator_agent.py"],
            env_delta={"PYTHONPATH": "src"},
            require=("PASS",),
        ),
        Step(
            "swe_smoke",
            ["bash", "tools/bench/smoke_mini_swe_bench_grok_headless.sh", "/tmp/turingos-hci-swe-smoke"],
            require=("MiniSweBenchSmokeResult.v1", "PASS"),
        ),
        Step(
            "swe_stage2_3task_audit",
            [
                "python3",
                "tools/bench/audit_mini_swe_bench_substrate_coverage.py",
                "--coverage",
                str(SWE_COVERAGE),
                "--out",
                str(OUT / "swe_stage2_3task_audit.json"),
                "--min-sample-size",
                "3",
                "--worker-process",
                "grok_cli",
            ],
        ),
        Step(
            "status_swe_bundle",
            [turing, "status", "--micro-bundle", str(SWE_BUNDLE)],
            require=("source_kind=guarded_micro_tape_read", "accepted_head=mu:344937"),
        ),
        Step(
            "panoview_swe_bundle",
            [turing, "panoview", "--micro-bundle", str(SWE_BUNDLE)],
            require=("source=guarded_micro_tape_read", "accepted_head=mu:344937"),
        ),
    ]

    commands = [run_step(step) for step in steps]
    status = "PASS" if all(command["status"] == "PASS" for command in commands) else "FAIL"
    summary = {
        "schema_id": "operator_simulated_human_report.v1",
        "status": status,
        "agent_role": "simulated_human",
        "status_ceiling": "IMPLEMENTER_ADDRESSED",
        "worktree_path": str(ROOT),
        "swe_bench_sample": {
            "bundle": str(SWE_BUNDLE.relative_to(ROOT)),
            "coverage": str(SWE_COVERAGE.relative_to(ROOT)),
            "smoke_output": "/tmp/turingos-hci-swe-smoke",
        },
        "commands": commands,
    }
    (OUT / "commands.summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": status, "commands": len(commands)}, sort_keys=True))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
