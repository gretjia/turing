#!/usr/bin/env python3
"""Fail on operator UI copy that claims closure without evidence."""

from __future__ import annotations

import re
import sys
from pathlib import Path


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


def iter_files(paths: list[str]):
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            yield from sorted(p for p in path.rglob("*") if p.is_file())
        elif path.is_file():
            yield path
        else:
            print(f"missing path: {path}", file=sys.stderr)
            raise SystemExit(2)


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: lint_hci_copy.py <file-or-dir> [...]", file=sys.stderr)
        return 2
    pattern = re.compile(r"\b(" + "|".join(map(re.escape, FORBIDDEN)) + r")\b", re.I)
    failures: list[str] = []
    for path in iter_files(argv):
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if "copy-law-allow-list:" in line:
                continue
            match = pattern.search(line)
            if match:
                failures.append(f"{path}:{lineno}: forbidden operator copy: {match.group(1)}")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("operator copy lint: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
