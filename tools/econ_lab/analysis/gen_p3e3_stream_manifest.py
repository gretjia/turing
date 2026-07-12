#!/usr/bin/env python3
"""Build the frozen P3-E3 evaluation stream manifest (CAPSULE A §3).

Stream order (frozen at dispatch):
  PHASE1_FAMILIES = {astropy, django, pydata, pytest-dev}  # 22 tasks, by instance_id
  PHASE2_FAMILIES = {matplotlib, scikit-learn, sphinx-doc, sympy}  # 28 tasks, by instance_id
  switch point = task index 22 (0-based): after PHASE1, before PHASE2.
"""
from __future__ import annotations

import json
from pathlib import Path

PHASE1_FAMILIES = frozenset({"astropy", "django", "pydata", "pytest-dev"})
PHASE2_FAMILIES = frozenset({"matplotlib", "scikit-learn", "sphinx-doc", "sympy"})
S03_ROOT = (
    Path(__file__).resolve().parents[3]
    / "evidence/bench/swe_bench_verified_500_campaign_20260629/shards/S03"
)
TASKS_GLOB = "ipqc/*-W*/worker_safe_tasks/*/task_packet.json"


def family_of(instance_id: str) -> str:
    return instance_id.split("__", 1)[0]


def main() -> int:
    packets = []
    for path in sorted(S03_ROOT.glob(TASKS_GLOB)):
        data = json.loads(path.read_text(encoding="utf-8"))
        packets.append(data)
    if len(packets) != 50:
        raise SystemExit(f"expected 50 S03 packets, found {len(packets)}")

    phase1 = sorted(
        (p["instance_id"] for p in packets if family_of(p["instance_id"]) in PHASE1_FAMILIES)
    )
    phase2 = sorted(
        (p["instance_id"] for p in packets if family_of(p["instance_id"]) in PHASE2_FAMILIES)
    )
    unknown = [
        p["instance_id"]
        for p in packets
        if family_of(p["instance_id"]) not in PHASE1_FAMILIES | PHASE2_FAMILIES
    ]
    if unknown:
        raise SystemExit(f"unknown families for instances: {unknown}")
    if len(phase1) != 22 or len(phase2) != 28:
        raise SystemExit(f"phase sizes wrong: PHASE1={len(phase1)} PHASE2={len(phase2)}")

    ordered = phase1 + phase2
    manifest = {
        "schema": "econ_lab.p3e3_stream_manifest.v1",
        "shard_id": "S03",
        "switch_task_index": 22,
        "phase1_families": sorted(PHASE1_FAMILIES),
        "phase2_families": sorted(PHASE2_FAMILIES),
        "phase1_count": len(phase1),
        "phase2_count": len(phase2),
        "instance_ids": ordered,
        "phase1_instance_ids": phase1,
        "phase2_instance_ids": phase2,
    }
    out = Path(__file__).parent / "p3e3_stream_manifest.json"
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(out)
    print(f"PHASE1={len(phase1)} PHASE2={len(phase2)} switch@22 first_p2={phase2[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
