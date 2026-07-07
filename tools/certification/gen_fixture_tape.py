#!/usr/bin/env python3
"""Generate a deterministic FIXTURE long-tape event stream for FCE-B4."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def event(seed: str, index: int) -> dict[str, Any]:
    prev = sha256_bytes(f"{seed}:{index - 1}".encode("utf-8")) if index > 0 else "sha256:" + "0" * 64
    payload = {
        "schema_id": "turingos.fce.fixture_event.v1",
        "fixture_or_real": "FIXTURE",
        "event_index": index,
        "event_type": "FCEFixtureEvent",
        "canonical_append_route": "designated_writer_fixture_path",
        "prev_event_digest": prev,
        "payload": {
            "seed": seed,
            "value": sha256_bytes(f"{seed}:{index}:payload".encode("utf-8"))[:24],
        },
    }
    material = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["event_digest"] = sha256_bytes(material)
    return payload


def write_tape(out: Path, count: int, seed: str) -> str:
    if count < 10_000:
        raise ValueError("count must be at least 10000 for the FCE-B4 fixture")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for index in range(count):
            handle.write(json.dumps(event(seed, index), sort_keys=True, separators=(",", ":")) + "\n")
    return sha256_bytes(out.read_bytes())


def self_test() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        a = root / "a.jsonl"
        b = root / "b.jsonl"
        digest_a = write_tape(a, 10_000, "self-test")
        digest_b = write_tape(b, 10_000, "self-test")
        assert digest_a == digest_b
        rows = a.read_text(encoding="utf-8").splitlines()
        assert len(rows) == 10_000
        first = json.loads(rows[0])
        last = json.loads(rows[-1])
        assert first["fixture_or_real"] == "FIXTURE"
        assert last["event_index"] == 9999
    print("FCE_FIXTURE_TAPE_SELF_TEST_PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=10_000)
    parser.add_argument("--out")
    parser.add_argument("--seed", default="fce-fixture")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if not args.out:
        parser.error("--out is required unless --self-test is used")
    digest = write_tape(Path(args.out), args.count, args.seed)
    print(json.dumps({"schema_id": "turingos.fce.fixture_tape.summary.v1", "out": args.out, "sha256": digest}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
