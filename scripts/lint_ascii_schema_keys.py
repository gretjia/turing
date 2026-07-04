#!/usr/bin/env python3
"""Require ASCII JSON object keys in operator schemas."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def iter_json_files(path: Path):
    if path.is_dir():
        yield from sorted(path.rglob("*.json"))
    else:
        yield path


def check_keys(value, path: Path, trail: str, failures: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if not key.isascii():
                failures.append(f"{path}:{trail}: non-ASCII schema key {key!r}")
            check_keys(child, path, f"{trail}.{key}" if trail else key, failures)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            check_keys(child, path, f"{trail}[{index}]", failures)


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: lint_ascii_schema_keys.py <schema-file-or-dir> [...]", file=sys.stderr)
        return 2
    failures: list[str] = []
    for raw in argv:
        for path in iter_json_files(Path(raw)):
            with path.open(encoding="utf-8") as handle:
                check_keys(json.load(handle), path, "", failures)
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("ASCII schema key lint: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
