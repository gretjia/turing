#!/usr/bin/env python3
"""One-shot generator for `fixtures/self_test_stream.json` (schema
``econ_lab.task_stream.v1``), the synthetic fixture stream the WP7 harness's
"fixture 流自测" test drives through all five arms end to end.

The generator itself is deterministic (fixed seed strings, no live randomness) so
re-running it reproduces byte-identical output; the JSON artifact is what is actually
checked in and loaded by `runner.py --self-test` and the pytest suite -- this script is
not imported at test time.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

OUT_PATH = Path(__file__).resolve().parent / "self_test_stream.json"

SCAFFOLDS_PER_BUCKET = ("scaffold:sha256:s0", "scaffold:sha256:s1", "scaffold:sha256:s2", "scaffold:sha256:s3")
P_PRIORS = {"scaffold:sha256:s0": 0.5, "scaffold:sha256:s1": 0.5, "scaffold:sha256:s2": 0.4, "scaffold:sha256:s3": 0.3}
TRIALS_PER_BUCKET = 48


def _bit(seed: str, salt: str) -> int:
    digest = hashlib.sha256((salt + seed).encode("utf-8")).digest()
    return digest[0] & 1


def _build_bucket(bucket_name: str) -> dict:
    scaffolds = {sid: {"p_prior": P_PRIORS[sid]} for sid in SCAFFOLDS_PER_BUCKET}
    trials = []
    for i in range(TRIALS_PER_BUCKET):
        case_id = f"case-{bucket_name}-{i:04d}"
        outcomes = {}
        for sid in SCAFFOLDS_PER_BUCKET:
            accept = _bit(f"{case_id}:{sid}", "accept-outcome.self-test.v1")
            witnesses = [
                _bit(f"{case_id}:{sid}", "witness-a.self-test.v1"),
                _bit(f"{case_id}:{sid}", "witness-b.self-test.v1"),
                _bit(f"{case_id}:{sid}", "witness-c.self-test.v1"),
            ]
            outcomes[sid] = {"accept": accept, "verify_witnesses": witnesses}
        trials.append(
            {
                "case_id": case_id,
                "price_signal_hash": f"sha256:price-{bucket_name}-{i:04d}",
                "pput_prior_hash": f"sha256:pput-{bucket_name}-{i:04d}",
                "trigger_event_hash": f"sha256:trigger-{bucket_name}-{i:04d}",
                "outcomes": outcomes,
            }
        )
    return {"scaffolds": scaffolds, "trials": trials}


def build_stream() -> dict:
    return {
        "schema": "econ_lab.task_stream.v1",
        "buckets": {
            "bucket_alpha": _build_bucket("bucket_alpha"),
            "bucket_beta": _build_bucket("bucket_beta"),
        },
    }


def main() -> int:
    stream = build_stream()
    OUT_PATH.write_text(json.dumps(stream, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
