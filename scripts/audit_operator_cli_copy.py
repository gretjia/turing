#!/usr/bin/env python3
"""Audit human-facing Operator Console copy emitted by the CLI."""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = (
    "accepted",
    "verified",
    "passed",
    "merged",
    "done",
    "completed",
    "constitutional",
    "approved",
    "closed",
)


def run(command: list[str], *, cwd: Path = ROOT) -> tuple[int, str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return result.returncode, result.stdout + result.stderr


def main() -> int:
    build_code, build_output = run(["cargo", "build", "-p", "turing-cli", "--quiet"])
    if build_code != 0:
        print(build_output, file=sys.stderr)
        return build_code

    turing = str(ROOT / "target" / "debug" / "turing")

    with tempfile.TemporaryDirectory() as fixture_dir:
        fixture_repo = Path(fixture_dir) / "micro_tape"
        fixture_code, fixture_output = run(
            [
                "python3",
                str(ROOT / "tools" / "hci" / "make_fixture_micro_tape.py"),
                "--out",
                str(fixture_repo),
                "--summary-json",
                str(Path(fixture_dir) / "fixture.json"),
            ]
        )
        if fixture_code != 0:
            print(fixture_output, file=sys.stderr)
            return fixture_code

        # A fresh, empty cwd with no TURING_MICRO_GIT / .turingos config — used to audit the F1
        # bare-command fail-closed copy (no configured tape) without polluting other commands'
        # working directory.
        empty_cwd = Path(fixture_dir) / "no_tape_configured"
        empty_cwd.mkdir()

        # Each entry: (argv, cwd, expected_exit_code). A real MicroTape fixture (not the demo)
        # exercises status/panoview render copy; the bare invocations exercise the F1 no-tape
        # fail-closed copy, which must also stay free of the forbidden completion-claim words.
        commands: list[tuple[list[str], Path, int]] = [
            ([turing, "--help"], ROOT, 0),
            ([turing, "help", "commands"], ROOT, 0),
            ([turing, "status", "--micro-git", str(fixture_repo)], ROOT, 0),
            ([turing, "panoview", "--micro-git", str(fixture_repo)], ROOT, 0),
            ([turing, "status"], empty_cwd, 2),
            ([turing, "panoview"], empty_cwd, 2),
            ([turing, "explain", "blocker"], ROOT, 0),
            (
                [
                    turing,
                    "explain",
                    "event",
                    "mu:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                ],
                ROOT,
                0,
            ),
            ([turing, "ask", "approve candidate"], ROOT, 0),
            ([turing, "ask", "reject candidate"], ROOT, 0),
            (
                [
                    turing,
                    "approval",
                    "preview",
                    "--approval-id",
                    "copy_audit_preview",
                    "--authority-epoch",
                    "1",
                    "--action",
                    "capsule_approve",
                    "--subject",
                    "wc_copy",
                    "--risk",
                    "P2",
                    "--evidence-digest",
                    "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "--signature-route",
                    "none",
                ],
                ROOT,
                0,
            ),
        ]
        failures: list[str] = []
        for command, cwd, expected_exit in commands:
            code, output = run(command, cwd=cwd)
            if code != expected_exit:
                failures.append(
                    f"{' '.join(command)} exited {code} (expected {expected_exit}): {output.strip()}"
                )
                continue
            if expected_exit == 2 and "Run:" not in output:
                failures.append(
                    f"{' '.join(command)} fail-closed copy is missing a next command (\"Run:\")"
                )
            for word in FORBIDDEN:
                if re.search(rf"\b{re.escape(word)}\b", output, flags=re.IGNORECASE):
                    failures.append(f"{' '.join(command)} emitted forbidden copy word {word!r}")

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    print("operator CLI copy audit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
