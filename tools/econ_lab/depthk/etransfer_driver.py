#!/usr/bin/env python3
"""CAPSULE E — T-arm depth-k stage market with GLOBAL domain_bucket (new file only).

Imports helpers from depth_driver / live_driver; never edits those originals.
Stage keys forced to domain_bucket constant derived from task_family="GLOBAL"
(CLI returns "global") so stage stats transfer across families.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
ECON_LAB_DIR = Path(__file__).resolve().parents[1]
DEPTHK_DIR = Path(__file__).resolve().parent
SHARDS_ROOT = (
    REPO_ROOT
    / "evidence/bench/swe_bench_verified_500_campaign_20260629/shards"
)
TASKS_GLOB = "ipqc/*-W*/worker_safe_tasks/*/task_packet.json"

sys.path.insert(0, str(DEPTHK_DIR))
sys.path.insert(0, str(ECON_LAB_DIR))
sys.path.insert(0, str(REPO_ROOT / "tools" / "bench"))
sys.path.insert(0, str(REPO_ROOT / "src"))

import depth_driver as dd  # noqa: E402
import live_driver as ld  # noqa: E402

DRIVER_SCHEMA = "econ_lab.etransfer.depthk.verdict.v1"
GLOBAL_TASK_FAMILY = "GLOBAL"
DOMAIN_BUCKET_MODE = "GLOBAL_CONSTANT"


def tau_router_mode(tau: float) -> dict[str, Any]:
    if tau == 0:
        return {"kind": "SoftmaxArgmaxBypass"}
    if tau == float("inf"):
        return {"kind": "SoftmaxUniform"}
    return {"kind": "SoftmaxFinite", "tau_q32_mantissa": int(float(tau) * (1 << 32))}


def load_s01s02_packets() -> list[dict[str, Any]]:
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


def force_global_stage_keys(cli_bin: Path) -> tuple[str, dict[tuple[str, str], str]]:
    """Always derive stage keys under GLOBAL family → shared domain_bucket 'global'."""
    bucket, stage_ids = dd.derive_stage_keys(cli_bin, GLOBAL_TASK_FAMILY)
    if bucket != "global":
        raise RuntimeError(
            f"expected domain_bucket 'global' for task_family=GLOBAL, got {bucket!r}"
        )
    return bucket, stage_ids


def load_split_manifest(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    return data, dd.sha256_hex(raw)


def run_etransfer_stage(
    *,
    out_dir: Path,
    cli_bin: Path,
    stream_manifest: Path,
    scoring_python: str,
    scoring_timeout_s: int,
    tau: float,
    fractional_reward: bool,
    run_label: str,
    max_tasks: Optional[int],
    max_worker_calls: Optional[int],
    resume: bool,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    task_runs = out_dir / "task_runs"
    scoring_root = out_dir / "scoring"
    task_runs.mkdir(parents=True, exist_ok=True)
    scoring_root.mkdir(parents=True, exist_ok=True)

    manifest, manifest_sha = load_split_manifest(stream_manifest)
    stream_ids = [str(x) for x in manifest["instance_ids"]]
    train_ids = set(manifest.get("train_instance_ids") or [])
    heldout_ids = set(manifest.get("heldout_instance_ids") or [])
    heldout_start = int(manifest.get("heldout_start_index", len(train_ids)))

    packets_all = load_s01s02_packets()
    packets = ld.order_packets_by_stream_manifest(packets_all, stream_ids)
    if max_tasks is not None:
        packets = packets[: max_tasks]

    deepseek_cfg = ld.load_provider_config()
    bucket, stage_ids = force_global_stage_keys(cli_bin)
    router_mode = tau_router_mode(tau)

    committed: list[dict[str, Any]] = []
    tasks_out: list[dict[str, Any]] = []
    worker_calls = 0
    stage_node_train_n: dict[str, int] = {
        f"{s}:{o}": 0 for s, opts in dd.STAGE_OPTIONS.items() for o in opts
    }

    class _Args:
        pass

    args = _Args()
    args.scoring_python = scoring_python
    args.scoring_timeout_s = scoring_timeout_s
    args.fractional_reward = fractional_reward

    for task_index, packet in enumerate(packets):
        if max_worker_calls is not None and worker_calls >= max_worker_calls:
            break
        instance_id = packet["instance_id"]
        side = (
            "TRAIN"
            if instance_id in train_ids
            else ("HELDOUT" if instance_id in heldout_ids else "UNKNOWN")
        )
        task_dir = task_runs / instance_id
        record_path = task_dir / "depthk_task_record.json"

        if resume and record_path.exists():
            task_record = json.loads(record_path.read_text(encoding="utf-8"))
            credit_events = task_record.get("credit_events") or []
            committed.extend(credit_events)
            if task_record.get("worker_result_status") == "COMPLETED" or task_record.get(
                "worker_calls_increment", 0
            ):
                worker_calls += 1
            # Train N from credit events
            if side == "TRAIN" and credit_events:
                for s in dd.STAGE_WALK:
                    opt = task_record["stage_choices"][s]
                    stage_node_train_n[f"{s}:{opt}"] = stage_node_train_n.get(f"{s}:{opt}", 0) + 1
            tasks_out.append(task_record)
            continue

        stage_choices: dict[str, str] = {}
        stage_chain: list[dict[str, Any]] = []
        for stage_name in dd.STAGE_WALK:
            sel = dd.fold_and_select_stage(
                cli_bin,
                stage_name=stage_name,
                domain_bucket=bucket,
                stage_option_ids=stage_ids,
                committed_routing_events=committed,
                instance_id=instance_id,
                router_mode=router_mode,
            )
            chosen = sel["budget_suggestion"]["route_id"]
            stage_choices[stage_name] = chosen
            stage_chain.append(
                {
                    "stage_name": stage_name,
                    "option": chosen,
                    "stage_option_id": stage_ids[(stage_name, chosen)],
                    "budget_suggestion": sel["budget_suggestion"],
                    "node_states": sel.get("node_states"),
                }
            )

        lineage = dd.select_lineage(
            cli_bin,
            domain_bucket=bucket,
            committed_routing_events=committed,
            instance_id=instance_id,
            stage_choices=stage_choices,
        )
        arm = dd.compose_dispatch_arm(**stage_choices)

        focus = [(s, stage_choices[s]) for s in dd.STAGE_WALK]
        nodes_before = dd.snapshot_stage_nodes(
            cli_bin,
            domain_bucket=bucket,
            stage_option_ids=stage_ids,
            committed_routing_events=committed,
            focus=focus,
        )

        verify_sid = stage_ids[("verify", stage_choices["verify"])]
        settlement = ld._settle_one(
            args=args,
            packet=packet,
            arm=arm,
            lineage=lineage,
            task_dir_root=task_runs,
            report_root=scoring_root,
            deepseek_native_provider_config=deepseek_cfg,
            cli_bin=cli_bin,
            route_domain=bucket,
            route_scaffold=verify_sid,
            run_label=run_label,
            task_index=task_index,
        )
        worker_calls += 1

        verify_verdict: Optional[bool] = None
        verify_pass_fraction: Optional[float] = None
        live = settlement.get("live_split_verdict") or {}
        if live and live.get("verify_verdict") is not None and not live.get("not_enough_tests"):
            verify_verdict = bool(live["verify_verdict"])
            verify_pass_fraction = live.get("verify_pass_fraction")
            if verify_pass_fraction is None:
                verify_pass_fraction = 1.0 if verify_verdict else 0.0
        elif settlement.get("settlement_verdict_resolved") is not None:
            # Fallback only when live_split absent; prefer verify-side metric.
            verify_verdict = bool(settlement["settlement_verdict_resolved"])
            verify_pass_fraction = 1.0 if verify_verdict else 0.0

        credit_events: list[dict[str, Any]] = []
        if verify_verdict is not None and (
            (not fractional_reward)
            or (verify_pass_fraction is not None and not live.get("not_enough_tests", False))
            or settlement.get("settlement_verdict_resolved") is not None
        ):
            # Credit when we have a usable verdict. Fractional path needs fraction;
            # if not_enough_tests, skip (match depth_driver honesty).
            if live and live.get("not_enough_tests"):
                credit_events = []
            else:
                credit_events = dd.credit_assign_v0(
                    cli_bin,
                    domain_bucket=bucket,
                    stage_choices=stage_choices,
                    stage_option_ids=stage_ids,
                    verify_verdict=verify_verdict,
                    instance_id=instance_id,
                    lineage=lineage,
                    run_label=run_label,
                    task_index=task_index,
                    fractional_reward=fractional_reward,
                    verify_pass_fraction=verify_pass_fraction,
                )
                committed.extend(credit_events)
                if side == "TRAIN" and credit_events:
                    for s in dd.STAGE_WALK:
                        opt = stage_choices[s]
                        stage_node_train_n[f"{s}:{opt}"] = (
                            stage_node_train_n.get(f"{s}:{opt}", 0) + 1
                        )

        nodes_after = dd.snapshot_stage_nodes(
            cli_bin,
            domain_bucket=bucket,
            stage_option_ids=stage_ids,
            committed_routing_events=committed,
            focus=focus,
        )

        task_record = {
            "instance_id": instance_id,
            "side": side,
            "task_index": task_index,
            "domain_bucket": bucket,
            "domain_bucket_mode": DOMAIN_BUCKET_MODE,
            "stage_chain": stage_chain,
            "stage_choices": stage_choices,
            "dispatch_arm": arm,
            "lineage": lineage,
            "worker_result_status": settlement.get("worker_result_status"),
            "provider_path": settlement.get("provider_path"),
            "scoring_status": (settlement.get("scoring_result") or {}).get("status"),
            "settlement_verdict_resolved": settlement.get("settlement_verdict_resolved"),
            "live_split_verdict": settlement.get("live_split_verdict"),
            "verify_verdict_for_credit": verify_verdict,
            "verify_pass_fraction": verify_pass_fraction,
            "credit_assignment": dd.CREDIT_ASSIGNMENT_V0,
            "credit_events_count": len(credit_events),
            "credit_events": credit_events,
            "nodes_before": nodes_before,
            "nodes_after": nodes_after,
            "worker_calls_increment": 1,
            "worker_receipt_paths": dd._find_receipts(task_runs, instance_id, lineage),
            "scoring_report_paths": dd._find_scoring(scoring_root, instance_id, lineage),
        }
        tasks_out.append(task_record)
        task_dir.mkdir(parents=True, exist_ok=True)
        record_path.write_text(
            json.dumps(task_record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    # Final full-node snapshot (all 6 stage options under GLOBAL)
    all_focus = [(s, o) for s, opts in dd.STAGE_OPTIONS.items() for o in opts]
    final_nodes = dd.snapshot_stage_nodes(
        cli_bin,
        domain_bucket=bucket,
        stage_option_ids=stage_ids,
        committed_routing_events=committed,
        focus=all_focus,
    )

    verdict = {
        "schema": DRIVER_SCHEMA,
        "mode": "etransfer_stage_market",
        "arm_label": "T",
        "evidence_class": "REAL_HARNESS_OUTPUTS_AND_PROVIDER_RECEIPTS",
        "credit_assignment": dd.CREDIT_ASSIGNMENT_V0,
        "credit_assignment_note": (
            "v0 equal share of verify verdict across the three stage nodes used on the path; "
            "not causal credit assignment — known ceiling (CAPSULE B memo R1)"
        ),
        "fractional_reward": fractional_reward,
        "tau": tau,
        "domain_bucket_mode": DOMAIN_BUCKET_MODE,
        "domain_bucket": bucket,
        "global_task_family": GLOBAL_TASK_FAMILY,
        "stream_manifest_path": str(stream_manifest),
        "stream_manifest_sha256": manifest_sha,
        "split_fingerprint_sha256": manifest.get("fingerprint_sha256"),
        "heldout_start_index": heldout_start,
        "train_count_planned": len(train_ids),
        "heldout_count_planned": len(heldout_ids),
        "tasks": tasks_out,
        "worker_calls_used": worker_calls,
        "max_worker_calls": max_worker_calls,
        "committed_routing_events_count": len(committed),
        "stage_node_train_n": stage_node_train_n,
        "final_stage_nodes": final_nodes,
        "run_label": run_label,
        "generated_at_unix": int(time.time()),
        "significance_claims": "NONE — confirmatory readout is etransfer_readout.py only",
    }
    (out_dir / "verdict.json").write_text(
        json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "committed_routing_events.json").write_text(
        json.dumps(committed, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return verdict


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="CAPSULE E T-arm GLOBAL stage market driver")
    parser.add_argument("--out", type=Path, required=True, help="arm output directory")
    parser.add_argument("--stream-manifest", type=Path, required=True)
    parser.add_argument("--econ-fold-cli", type=Path, default=None)
    parser.add_argument("--tau", type=float, default=0.5)
    parser.add_argument("--fractional-reward", action="store_true")
    parser.add_argument("--run-label", default="etransfer-T")
    parser.add_argument("--max-tasks", type=int, default=None)
    parser.add_argument("--max-worker-calls", type=int, default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--scoring-python",
        default=str(Path.home() / ".turingos" / "swebench-venv" / "bin" / "python"),
    )
    parser.add_argument("--scoring-timeout-s", type=int, default=2700)
    args = parser.parse_args(argv)

    cli_bin = args.econ_fold_cli or dd.find_default_cli_bin()
    if not cli_bin.exists():
        raise SystemExit(f"econ_fold_cli not found at {cli_bin}")

    verdict = run_etransfer_stage(
        out_dir=args.out,
        cli_bin=cli_bin,
        stream_manifest=args.stream_manifest,
        scoring_python=args.scoring_python,
        scoring_timeout_s=args.scoring_timeout_s,
        tau=float(args.tau),
        fractional_reward=bool(args.fractional_reward),
        run_label=args.run_label,
        max_tasks=args.max_tasks,
        max_worker_calls=args.max_worker_calls,
        resume=bool(args.resume),
    )
    print(
        json.dumps(
            {
                "status": "WROTE_VERDICT",
                "arm": "T",
                "worker_calls_used": verdict["worker_calls_used"],
                "out": str(args.out / "verdict.json"),
                "domain_bucket": verdict["domain_bucket"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
