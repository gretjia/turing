#!/usr/bin/env python3
"""Execute a small real fixture probe for GateResult receipts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


FORBIDDEN = {
    "HUMAN_RATIFIED",
    "OG10_SIGNED",
    "FOUNDATION_READY",
    "M2_ENABLED",
    "CLOSED",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True)
    args = parser.parse_args()

    fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    if fixture.get("schema_id") != "FixtureProbe.v1":
        print("schema_id rejected")
        return 2
    if fixture.get("not_run"):
        print("not_run rejected")
        return 3
    text = json.dumps(fixture, sort_keys=True, separators=(",", ":"))
    found = sorted(token for token in FORBIDDEN if token in text)
    if found:
        print(f"forbidden claims rejected: {found}")
        return 4
    print("fixture accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
