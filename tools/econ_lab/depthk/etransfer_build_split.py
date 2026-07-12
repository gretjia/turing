#!/usr/bin/env python3
"""CAPSULE E — build TRAIN/HELDOUT family split + stream manifest (frozen rules).

Rules (CAPSULE E §3, orchestrator-frozen):
  - Candidates = S01 ∪ S02 (100 instances).
  - Family = instance_id prefix before '__'.
  - Family → TRAIN if first byte of SHA256("etransfer-split.v1"||family) is even,
    HELDOUT if odd.
  - Within family: sort (historical accept-pass count DESC, instance_id ASC)
    from stageA 5 + stageBprime 4 arm verdicts (settlement_verdict_resolved True).
  - Take ≤25 TRAIN tasks total, ≤25 HELDOUT (top by the same ranking key within side).
  - Stream order = all TRAIN (families sorted by name, within-family order)
    then all HELDOUT (same).
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
ECON_LAB = Path(__file__).resolve().parents[1]
SHARDS_ROOT = (
    REPO_ROOT
    / "evidence/bench/swe_bench_verified_500_campaign_20260629/shards"
)
TASKS_GLOB = "ipqc/*-W*/worker_safe_tasks/*/task_packet.json"
SPLIT_SALT = "etransfer-split.v1"
MAX_PER_SIDE = 25

HISTORICAL_VERDICTS = [
    ECON_LAB / "runs/stageA_20260707/tau_0/verdict.json",
    ECON_LAB / "runs/stageA_20260707/tau_0p5/verdict.json",
    ECON_LAB / "runs/stageA_20260707/tau_1/verdict.json",
    ECON_LAB / "runs/stageA_20260707/tau_2/verdict.json",
    ECON_LAB / "runs/stageA_20260707/tau_inf/verdict.json",
    ECON_LAB / "runs/stageBprime_20260708/W/verdict.json",
    ECON_LAB / "runs/stageBprime_20260708/F/verdict.json",
    ECON_LAB / "runs/stageBprime_20260708/C/verdict.json",
    ECON_LAB / "runs/stageBprime_20260708/U/verdict.json",
]


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def family_of(instance_id: str) -> str:
    return instance_id.split("__", 1)[0]


def family_side(family: str) -> str:
    digest = hashlib.sha256((SPLIT_SALT + family).encode("utf-8")).digest()
    return "TRAIN" if (digest[0] % 2 == 0) else "HELDOUT"


def historical_accept_pass_counts() -> Counter:
    counts: Counter = Counter()
    for path in HISTORICAL_VERDICTS:
        if not path.exists():
            raise SystemExit(f"missing historical verdict: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        for task in data.get("tasks", []):
            iid = task.get("instance_id")
            if not iid:
                continue
            for disp in task.get("dispatches", []):
                if disp.get("settlement_verdict_resolved") is True:
                    counts[iid] += 1
                    break
    return counts


def load_s01s02_instance_ids() -> list[str]:
    ids: list[str] = []
    for shard in ("S01", "S02"):
        root = SHARDS_ROOT / shard
        for path in sorted(root.glob(TASKS_GLOB)):
            packet = json.loads(path.read_text(encoding="utf-8"))
            ids.append(packet["instance_id"])
    if len(ids) != 100 or len(set(ids)) != 100:
        raise SystemExit(f"expected 100 unique S01∪S02 instances, got {len(ids)}/{len(set(ids))}")
    return ids


def rank_key(iid: str, pass_counts: Counter) -> tuple[int, str]:
    # sort key for ascending sort of negated pass count: higher pass first
    return (-pass_counts[iid], iid)


def select_side(
    candidates: list[str],
    pass_counts: Counter,
    *,
    max_n: int,
) -> list[str]:
    """Top-max_n by (pass DESC, instance_id ASC), then stream-order by family name."""
    ranked = sorted(candidates, key=lambda iid: rank_key(iid, pass_counts))
    selected = ranked[:max_n]
    # Stream order within side: family ASC, then within-family (pass DESC, id ASC)
    return sorted(
        selected,
        key=lambda iid: (family_of(iid), rank_key(iid, pass_counts)),
    )


def build_manifest() -> dict[str, Any]:
    all_ids = load_s01s02_instance_ids()
    pass_counts = historical_accept_pass_counts()
    by_family: dict[str, list[str]] = {}
    for iid in all_ids:
        by_family.setdefault(family_of(iid), []).append(iid)

    family_assignment: dict[str, str] = {}
    train_pool: list[str] = []
    heldout_pool: list[str] = []
    for family in sorted(by_family):
        side = family_side(family)
        family_assignment[family] = side
        # Within family ranking
        ordered = sorted(by_family[family], key=lambda iid: rank_key(iid, pass_counts))
        if side == "TRAIN":
            train_pool.extend(ordered)
        else:
            heldout_pool.extend(ordered)

    train_ids = select_side(train_pool, pass_counts, max_n=MAX_PER_SIDE)
    heldout_ids = select_side(heldout_pool, pass_counts, max_n=MAX_PER_SIDE)
    stream = train_ids + heldout_ids

    train_families = sorted(f for f, s in family_assignment.items() if s == "TRAIN")
    heldout_families = sorted(f for f, s in family_assignment.items() if s == "HELDOUT")

    instances_detail = []
    for iid in stream:
        instances_detail.append(
            {
                "instance_id": iid,
                "family": family_of(iid),
                "side": family_assignment[family_of(iid)],
                "historical_accept_pass_count": int(pass_counts[iid]),
            }
        )

    # Fingerprint over the frozen rule outputs (not wall-clock).
    fingerprint_payload = {
        "split_salt": SPLIT_SALT,
        "family_assignment": family_assignment,
        "train_instance_ids": train_ids,
        "heldout_instance_ids": heldout_ids,
        "instance_ids": stream,
        "historical_verdict_paths": [str(p.relative_to(REPO_ROOT)) for p in HISTORICAL_VERDICTS],
        "pass_counts": {k: pass_counts[k] for k in sorted(pass_counts)},
    }
    fingerprint = sha256_hex(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )

    return {
        "schema": "econ_lab.etransfer_split_manifest.v1",
        "split_salt": SPLIT_SALT,
        "split_rule": (
            'family → TRAIN iff first byte of SHA256("etransfer-split.v1"||family) is even; '
            "HELDOUT if odd. Within family: (historical accept-pass DESC, instance_id ASC). "
            "≤25 per side by that ranking; stream = TRAIN (family name ASC) then HELDOUT."
        ),
        "candidate_pool": "S01∪S02",
        "candidate_count": len(all_ids),
        "historical_verdict_count": len(HISTORICAL_VERDICTS),
        "historical_verdict_paths": [str(p.relative_to(REPO_ROOT)) for p in HISTORICAL_VERDICTS],
        "family_assignment": family_assignment,
        "train_families": train_families,
        "heldout_families": heldout_families,
        "train_count": len(train_ids),
        "heldout_count": len(heldout_ids),
        "train_instance_ids": train_ids,
        "heldout_instance_ids": heldout_ids,
        "instance_ids": stream,
        "heldout_start_index": len(train_ids),
        "instances": instances_detail,
        "fingerprint_sha256": fingerprint,
    }


def main(argv: list[str] | None = None) -> int:
    out = REPO_ROOT / "tools/econ_lab/runs/etransfer_20260710/etransfer_split_manifest.json"
    if argv and len(argv) >= 2 and argv[0] == "--out":
        out = Path(argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest()
    raw = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    out.write_text(raw, encoding="utf-8")
    file_sha = sha256_hex(raw.encode("utf-8"))
    print(
        json.dumps(
            {
                "status": "WROTE_SPLIT_MANIFEST",
                "path": str(out),
                "file_sha256": file_sha,
                "fingerprint_sha256": manifest["fingerprint_sha256"],
                "train_count": manifest["train_count"],
                "heldout_count": manifest["heldout_count"],
                "train_families": manifest["train_families"],
                "heldout_families": manifest["heldout_families"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
