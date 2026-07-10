#!/usr/bin/env python3
"""CAPSULE E — A-arm atomic 12-route market with GLOBAL domain_bucket (new file only).

Process-local monkeypatch of live_driver.derive_domain_bucket → always derive under
task_family="GLOBAL" (bucket "global"). Never edits live_driver.py on disk.
Also loads S01∪S02 packets so --stream-manifest can span both shards.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
ECON_LAB_DIR = Path(__file__).resolve().parents[1]
SHARDS_ROOT = (
    REPO_ROOT
    / "evidence/bench/swe_bench_verified_500_campaign_20260629/shards"
)
TASKS_GLOB = "ipqc/*-W*/worker_safe_tasks/*/task_packet.json"

sys.path.insert(0, str(ECON_LAB_DIR))
sys.path.insert(0, str(REPO_ROOT / "tools" / "bench"))
sys.path.insert(0, str(REPO_ROOT / "src"))

import live_driver as ld  # noqa: E402

GLOBAL_TASK_FAMILY = "GLOBAL"
DOMAIN_BUCKET_MODE = "GLOBAL_CONSTANT"
_ORIG_DERIVE = ld.derive_domain_bucket
_ORIG_LOAD = ld.load_task_packets


def load_s01s02_packets(_shard_root: Optional[Path] = None) -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    for shard in ("S01", "S02"):
        root = SHARDS_ROOT / shard
        for path in sorted(root.glob(TASKS_GLOB)):
            data = json.loads(path.read_text(encoding="utf-8"))
            data["_task_packet_path"] = path
            data["_task_dir"] = path.parent
            data["_shard"] = shard
            packets.append(data)
    return packets


def derive_domain_bucket_global(cli_bin: Path, task_family: Optional[str] = None) -> str:
    """Force GLOBAL bucket; ignore per-task family. Uses CLI so derivation is authoritative."""
    del task_family
    bucket = _ORIG_DERIVE(cli_bin, GLOBAL_TASK_FAMILY)
    if bucket != "global":
        raise RuntimeError(f"expected domain_bucket 'global', got {bucket!r}")
    return bucket


def main(argv: Optional[list[str]] = None) -> int:
    ld.derive_domain_bucket = derive_domain_bucket_global  # type: ignore[assignment]
    ld.load_task_packets = load_s01s02_packets  # type: ignore[assignment]

    parser = argparse.ArgumentParser(
        description="CAPSULE E A-arm GLOBAL flat market (live_driver wrapper)"
    )
    parser.add_argument("--out", type=Path, required=True, help="arm dir or verdict.json path")
    parser.add_argument("--stream-manifest", type=Path, required=True)
    parser.add_argument("--econ-fold-cli", type=Path, default=None)
    parser.add_argument("--tau", default="0.5", choices=["0", "0.5", "1", "2", "inf"])
    parser.add_argument("--fractional-reward", action="store_true")
    parser.add_argument("--run-label", default="etransfer-A")
    parser.add_argument("--max-tasks", type=int, default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--scoring-python",
        default=str(Path.home() / ".turingos" / "swebench-venv" / "bin" / "python"),
    )
    parser.add_argument("--scoring-timeout-s", type=int, default=2700)
    parser.add_argument("--task-dir-root", type=Path, default=None)
    parser.add_argument("--report-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    if str(args.out).endswith(".json"):
        out_verdict = args.out
        arm_dir = args.out.parent
    else:
        arm_dir = args.out
        arm_dir.mkdir(parents=True, exist_ok=True)
        out_verdict = arm_dir / "verdict.json"

    task_dir_root = args.task_dir_root or (arm_dir / "task_runs")
    report_dir = args.report_dir or (arm_dir / "scoring")

    ns = argparse.Namespace(
        smoke=False,
        max_tasks=args.max_tasks,
        out=out_verdict,
        econ_fold_cli=args.econ_fold_cli,
        scoring_python=args.scoring_python,
        scoring_timeout_s=args.scoring_timeout_s,
        tau=args.tau,
        task_dir_root=task_dir_root,
        report_dir=report_dir,
        resume=bool(args.resume),
        priors=None,
        frozen_backup=False,
        task_shard=SHARDS_ROOT / "S01",  # ignored by patched loader
        run_label=args.run_label,
        stream_manifest=args.stream_manifest,
        reset_at_task_index=None,
        fractional_reward=bool(args.fractional_reward),
    )

    verdict = ld.run_driver(ns)

    meta = verdict.setdefault("stage_b_prime_meta", {})
    meta["domain_bucket_mode"] = DOMAIN_BUCKET_MODE
    meta["global_task_family"] = GLOBAL_TASK_FAMILY
    meta["etransfer_arm"] = "A"
    meta["fractional_reward"] = bool(args.fractional_reward)
    buckets = sorted(
        {t.get("domain_bucket") for t in verdict.get("tasks", []) if t.get("domain_bucket")}
    )
    meta["domain_buckets_observed"] = buckets
    verdict["domain_bucket_mode"] = DOMAIN_BUCKET_MODE
    verdict["etransfer_arm"] = "A"

    out_verdict.parent.mkdir(parents=True, exist_ok=True)
    out_verdict.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "WROTE_VERDICT",
                "arm": "A",
                "path": str(out_verdict),
                "domain_buckets_observed": buckets,
                "task_count": verdict.get("task_count"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
