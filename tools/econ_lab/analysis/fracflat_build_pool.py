#!/usr/bin/env python3
"""Build CAPSULE D fracflat pool: top-50 of S01∪S02 by historical accept-pass count.

Sort key (frozen CAPSULE D §3):
  (historical accept-pass count DESC, instance_id ASC)

Historical arms (9 verdicts under tools/econ_lab/runs/):
  stageA_20260707: tau_0, tau_0p5, tau_1, tau_2, tau_inf  (S01)
  stageBprime_20260708: W, F, C, U                          (S02)

Accept-pass = settlement_verdict_resolved is True on any dispatch for that task,
with live_split accept_verdict True as fallback when settlement is null.

Also materializes a virtual task-shard root (symlinks only) so live_driver can
load S01∪S02 packets via TASKS_GLOB under a single --task-shard.

NEW FILES ONLY (analysis/fracflat_* and runs paths). Does not modify S01/S02.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

STAGE_A_ARMS = ["tau_0", "tau_0p5", "tau_1", "tau_2", "tau_inf"]
STAGE_B_ARMS = ["W", "F", "C", "U"]
TASKS_GLOB = "ipqc/*-W*/worker_safe_tasks/*/task_packet.json"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def shard_root(repo: Path, name: str) -> Path:
    return (
        repo
        / "evidence/bench/swe_bench_verified_500_campaign_20260629/shards"
        / name
    )


def list_packet_ids(shard: Path) -> list[str]:
    ids: list[str] = []
    for path in sorted(shard.glob(TASKS_GLOB)):
        data = json.loads(path.read_text(encoding="utf-8"))
        ids.append(str(data["instance_id"]))
    return ids


def packet_path_index(shard: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for path in sorted(shard.glob(TASKS_GLOB)):
        data = json.loads(path.read_text(encoding="utf-8"))
        out[str(data["instance_id"])] = path
    return out


def task_accepted(task: dict) -> bool:
    for d in task.get("dispatches") or []:
        sv = d.get("settlement_verdict_resolved")
        if sv is True:
            return True
        if sv is False:
            continue
        lsv = d.get("live_split_verdict") or {}
        if lsv.get("accept_verdict") is True:
            return True
    return False


def historical_accept_counts(repo: Path, universe: set[str]) -> dict[str, int]:
    counts = {iid: 0 for iid in universe}
    arm_paths: list[Path] = []
    for a in STAGE_A_ARMS:
        arm_paths.append(repo / "tools/econ_lab/runs/stageA_20260707" / a / "verdict.json")
    for a in STAGE_B_ARMS:
        arm_paths.append(repo / "tools/econ_lab/runs/stageBprime_20260708" / a / "verdict.json")

    arm_summaries = []
    for path in arm_paths:
        v = json.loads(path.read_text(encoding="utf-8"))
        n_pass = 0
        for task in v.get("tasks") or []:
            iid = str(task.get("instance_id"))
            if iid not in counts:
                continue
            if task_accepted(task):
                counts[iid] += 1
                n_pass += 1
        arm_summaries.append(
            {
                "path": str(path.relative_to(repo)),
                "accept_pass_count": n_pass,
                "task_count": len(v.get("tasks") or []),
            }
        )
    return counts, arm_summaries


def materialize_task_root(repo: Path, task_root: Path) -> int:
    """Symlink each S01/S02 task directory into task_root for glob load.

    Entire task dirs are linked (not only task_packet.json) so the worker can
    resolve sibling files (worker_capsule.md, source_context.md) via _task_dir.
    """
    import shutil

    if task_root.exists():
        shutil.rmtree(task_root)
    task_root.mkdir(parents=True, exist_ok=True)
    n = 0
    for shard_name in ("S01", "S02"):
        src_shard = shard_root(repo, shard_name)
        for window in sorted((src_shard / "ipqc").glob("*-W*")):
            if not window.is_dir():
                continue
            src_wst = window / "worker_safe_tasks"
            if not src_wst.is_dir():
                continue
            dst_wst = task_root / "ipqc" / window.name / "worker_safe_tasks"
            dst_wst.mkdir(parents=True, exist_ok=True)
            for task_dir in sorted(src_wst.iterdir()):
                if not task_dir.is_dir():
                    continue
                pkt = task_dir / "task_packet.json"
                if not pkt.is_file():
                    continue
                dst_task = dst_wst / task_dir.name
                if dst_task.exists() or dst_task.is_symlink():
                    if dst_task.is_symlink():
                        dst_task.unlink()
                    else:
                        shutil.rmtree(dst_task)
                rel = os.path.relpath(task_dir.resolve(), start=dst_task.parent.resolve())
                dst_task.symlink_to(rel)
                n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="pool manifest path (default: analysis/fracflat_pool_manifest.json)",
    )
    ap.add_argument(
        "--task-root",
        type=Path,
        default=None,
        help="virtual combined task-shard root (default: analysis/fracflat_task_root)",
    )
    ap.add_argument("--top-k", type=int, default=50)
    args = ap.parse_args()

    repo = repo_root()
    out = args.out or (repo / "tools/econ_lab/analysis/fracflat_pool_manifest.json")
    task_root = args.task_root or (repo / "tools/econ_lab/analysis/fracflat_task_root")

    s01 = list_packet_ids(shard_root(repo, "S01"))
    s02 = list_packet_ids(shard_root(repo, "S02"))
    if len(s01) != 50 or len(s02) != 50:
        raise SystemExit(f"expected 50+50 packets, got S01={len(s01)} S02={len(s02)}")
    if set(s01) & set(s02):
        raise SystemExit("S01 and S02 must be disjoint")

    universe = set(s01) | set(s02)
    counts, arm_summaries = historical_accept_counts(repo, universe)

    ranked = sorted(universe, key=lambda iid: (-counts[iid], iid))
    top = ranked[: args.top_k]
    if len(top) != args.top_k:
        raise SystemExit(f"top-k short: {len(top)}")

    n_linked = materialize_task_root(repo, task_root)
    # Verify all top-k packets resolve under task_root
    idx = packet_path_index(task_root)
    missing = [iid for iid in top if iid not in idx]
    if missing:
        raise SystemExit(f"top-k missing from task_root: {missing[:5]}")

    entries = []
    for rank, iid in enumerate(top):
        shard = "S01" if iid in s01 else "S02"
        entries.append(
            {
                "rank": rank,
                "instance_id": iid,
                "historical_accept_pass_count": counts[iid],
                "source_shard": shard,
            }
        )

    manifest = {
        "schema": "econ_lab.fracflat_pool_manifest.v1",
        "capsule": "D",
        "sort_key": "(historical_accept_pass_count DESC, instance_id ASC)",
        "historical_arms": {
            "stageA": STAGE_A_ARMS,
            "stageBprime": STAGE_B_ARMS,
            "n_arms": 9,
            "accept_definition": "settlement_verdict_resolved==True (fallback live_split.accept_verdict)",
        },
        "candidate_pool": {
            "shards": ["S01", "S02"],
            "n_candidates": 100,
            "s01_count": len(s01),
            "s02_count": len(s02),
        },
        "top_k": args.top_k,
        "instance_ids": top,
        "entries": entries,
        "count_histogram": {
            str(c): sum(1 for v in counts.values() if v == c) for c in range(0, max(counts.values()) + 1)
        },
        "arm_summaries": arm_summaries,
        "task_root_relative": str(task_root.relative_to(repo)),
        "task_root_packet_count": n_linked,
        "stream_order": "instance_ids (same as sort order)",
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8")
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()

    # Companion stream manifest for --stream-manifest (instance_ids only).
    stream = {
        "schema": "econ_lab.fracflat_stream_manifest.v1",
        "instance_ids": top,
        "pool_manifest": str(out.relative_to(repo)),
        "pool_manifest_sha256": sha,
    }
    stream_path = out.parent / "fracflat_stream_manifest.json"
    stream_text = json.dumps(stream, indent=2, sort_keys=True) + "\n"
    stream_path.write_text(stream_text, encoding="utf-8")
    stream_sha = hashlib.sha256(stream_text.encode("utf-8")).hexdigest()

    print(
        json.dumps(
            {
                "status": "WROTE_POOL",
                "pool_manifest": str(out),
                "pool_manifest_sha256": sha,
                "stream_manifest": str(stream_path),
                "stream_manifest_sha256": stream_sha,
                "top_k": args.top_k,
                "task_root": str(task_root),
                "task_root_packet_count": n_linked,
                "max_accept_count": max(counts.values()),
                "min_top_accept_count": counts[top[-1]],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
