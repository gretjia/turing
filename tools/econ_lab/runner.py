#!/usr/bin/env python3
"""WP7 E-harness runner (design doc `research/RES_ECON_emergence_toplevel_design_
20260707.md` R1.1 §7 WP7 row; `adr/ADR-ECON-003-emergence-routing-spec-pins.md` is the
sole formula/key-function source). Runs a task-stream fixture through the five
experiment arms (main / frozen-backup / static-oracle / placebo / tau-sweep), the
rank-inversion metric, and the held-out independent verifier, then emits a verdict JSON.

Scope: this module is the harness only. It does NOT implement the E-price-tau/E-anneal/
E-emerge *statistical decision* (two-proportion z-tests, Mann-Kendall trend test, the
N_eff/H_lineage floor gate, etc.) -- those are WP9's job, run against a frozen prereg +
frozen analysis script per the design doc's §7 WP8/WP9 rows. WP7's own acceptance is:
fixture-stream self-test, single-arm deterministic replay, and the rank-inversion metric
returning exactly 1 on a hand-constructed exactly-one-inversion fixture.

Usage:
    python3 tools/econ_lab/runner.py --self-test
    python3 tools/econ_lab/runner.py --stream <path> [--out <path>]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from arms import ArmSpec, TAU_SWEEP_GRID, pass_at_budget, simulate_bucket  # noqa: E402
from inversion import count_confirmed_inversions  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
DEFAULT_FIXTURE = FIXTURES_DIR / "self_test_stream.json"

STREAM_SCHEMA = "econ_lab.task_stream.v1"
VERDICT_SCHEMA = "econ_lab.verdict.v1"

_BACKUP_ACTIVE_KINDS = ("main", "tau_fixed")


def _tau_label(tau: Optional[float]) -> str:
    return "inf" if tau is None else str(tau)


def default_arm_specs() -> List[ArmSpec]:
    specs = [
        ArmSpec(name="main", kind="main", tau=1.0),
        ArmSpec(name="frozen_backup", kind="frozen_backup", tau=1.0),
        ArmSpec(name="static_oracle", kind="static_oracle"),
        ArmSpec(name="placebo", kind="placebo"),
    ]
    specs.extend(
        ArmSpec(name=f"tau_sweep_{_tau_label(t)}", kind="tau_fixed", tau=t) for t in TAU_SWEEP_GRID
    )
    return specs


def load_stream(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != STREAM_SCHEMA:
        raise ValueError(f"unrecognized task-stream schema (expected {STREAM_SCHEMA})")
    return data


def run_stream(stream: dict, arm_specs: Optional[List[ArmSpec]] = None) -> dict:
    arm_specs = arm_specs if arm_specs is not None else default_arm_specs()
    verdict = {"schema": VERDICT_SCHEMA, "arms": {}}
    for arm in arm_specs:
        arm_result: dict = {"buckets": {}}
        for bucket_name, bucket_fixture in stream["buckets"].items():
            trace = simulate_bucket(bucket_name, bucket_fixture, arm)
            bucket_result = {
                "pass_at_budget": pass_at_budget(trace),
                "n_accept_settled": sum(1 for e in trace.events if e.accept_pass is not None),
                "n_events": len(trace.events),
            }
            if arm.kind in _BACKUP_ACTIVE_KINDS:
                bucket_result["confirmed_inversions"] = count_confirmed_inversions(trace)
            arm_result["buckets"][bucket_name] = bucket_result
        verdict["arms"][arm.name] = arm_result
    return verdict


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stream", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)

    stream_path = DEFAULT_FIXTURE if args.self_test else args.stream
    stream = load_stream(stream_path)
    verdict = run_stream(stream)
    text = json.dumps(verdict, indent=2, sort_keys=True)

    if args.self_test:
        # Mechanical sanity: every arm must produce a result for every bucket in the
        # fixture stream, and every bucket must have settled at least one accept-side
        # trial (else the harness's own fixture is malformed).
        for arm_name, arm_result in verdict["arms"].items():
            for bucket_name, bucket_result in arm_result["buckets"].items():
                if bucket_result["n_accept_settled"] == 0:
                    print(
                        f"ECON_LAB_HARNESS_SELF_TEST_FAIL: arm={arm_name} bucket={bucket_name} "
                        "has zero accept-side settlement",
                        file=sys.stderr,
                    )
                    return 1
        print("ECON_LAB_HARNESS_SELF_TEST_PASS")
        print(text)
        return 0

    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
