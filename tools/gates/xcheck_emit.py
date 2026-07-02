#!/usr/bin/env python3
"""Emit Python canonical byte hex for the M1a JCS xcheck corpus."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from turingos import codec  # noqa: E402


def iter_cases(path: Path):
    case_index = 0
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        case_index += 1
        try:
            yield case_index, json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{line_number}: invalid JSON: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "corpus",
        nargs="?",
        default=str(Path(__file__).with_name("corpus_jcs_extended.jsonl")),
        help="JSONL corpus path",
    )
    args = parser.parse_args(argv)

    for case_index, value in iter_cases(Path(args.corpus)):
        print(f"{case_index}\t{codec.derived_python_canonical_bytes_fixture(value).hex()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
