#!/usr/bin/env python3
"""Audit human-facing Operator Console copy emitted by the CLI."""

from __future__ import annotations

import re
import subprocess
import sys
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


def run(command: list[str]) -> tuple[int, str]:
    result = subprocess.run(
        command,
        cwd=ROOT,
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
    commands = [
        [turing, "--help"],
        [turing, "help", "commands"],
        [turing, "status"],
        [turing, "panoview"],
        [turing, "explain", "blocker"],
        [
            turing,
            "explain",
            "event",
            "mu:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        ],
        [turing, "ask", "approve candidate"],
        [turing, "ask", "reject candidate"],
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
    ]
    failures: list[str] = []
    for command in commands:
        code, output = run(command)
        if code != 0:
            failures.append(f"{' '.join(command)} exited {code}: {output.strip()}")
            continue
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
