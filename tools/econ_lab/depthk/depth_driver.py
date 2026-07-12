#!/usr/bin/env python3
"""CAPSULE B — depth-k layered scaffold market driver (feasibility build).

Nature: exploratory construction, NOT a confirmatory experiment. This driver produces
smoke evidence and a working depth-2 substrate; it does **not** claim statistical
significance.

Architecture (design doc §1.4 / CAPSULE B dispatch 2026-07-09):
  scaffold = staged decision sequence (context → repair → verify)
  market key per stage = (domain_bucket, stage_name, option)
  wire encoding: scaffold_id := stage_option_id (CLI derive-stage-keys)
  seed = Decision 4 + ‖ stage_name  (econ_fold_cli fold-and-suggest-stage)
  credit assignment v0 = equal share of verify verdict across the three stage nodes
    (honest label: "v0 均摊,非因果归因" — known ceiling, not a defect)

File-partition discipline: lives under tools/econ_lab/depthk/; may **read-only import**
public helpers from live_driver.py (smoke path only, lazy); must not modify
live_driver / run_*.sh / analysis/*.

Budget: real worker calls capped at --max-worker-calls (smoke default 2, hard ceiling 8).

Usage:
  python3 tools/econ_lab/depthk/depth_driver.py --smoke --out tools/econ_lab/runs/depthk_smoke_20260709
  python3 tools/econ_lab/depthk/depth_driver.py --offline-mock --out /tmp/depthk_mock
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
ECON_LAB_DIR = Path(__file__).resolve().parents[1]

DRIVER_SCHEMA = "econ_lab.depthk.depth_driver.verdict.v1"
CREDIT_ASSIGNMENT_V0 = "v0_equal_share_not_causal"
EVIDENCE_CLASS_SMOKE = "SMOKE_FIXTURE"
S02_SHARD = (
    REPO_ROOT
    / "evidence/bench/swe_bench_verified_500_campaign_20260629/shards/S02"
)
TASKS_GLOB = "ipqc/*-W*/worker_safe_tasks/*/task_packet.json"
LINEAGES = ("deepseek", "qwen", "glm", "kimi")

STAGE_WALK = ("context", "repair", "verify")
STAGE_OPTIONS = {
    "context": ("minimal", "source_context"),
    "repair": ("single_shot", "loop"),
    "verify": ("none", "self_check"),
}


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(label: str) -> str:
    return "sha256:" + sha256_hex(label.encode("utf-8"))


def find_default_cli_bin() -> Path:
    for profile in ("debug", "release"):
        candidate = REPO_ROOT / "target" / profile / "econ_fold_cli"
        if candidate.exists():
            return candidate
    raise SystemExit(
        "econ_fold_cli binary not found under target/{debug,release}; run "
        "`cargo build --bin econ_fold_cli -p turing-economy` first"
    )


def call_cli(cli_bin: Path, subcommand: str, request: dict[str, Any]) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            [str(cli_bin), subcommand],
            input=json.dumps(request).encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            f"econ_fold_cli {subcommand} failed (timed out after {error.timeout}s)"
        ) from error
    if proc.returncode != 0:
        raise RuntimeError(
            f"econ_fold_cli {subcommand} failed (exit {proc.returncode}): "
            f"{proc.stderr.decode('utf-8', 'replace')}"
        )
    return json.loads(proc.stdout.decode("utf-8"))


def compose_dispatch_arm(context: str, repair: str, verify: str) -> str:
    """Mirror of routing_fold::compose_dispatch_arm (dispatch label only)."""
    del repair
    if context == "minimal":
        return "armA"
    if verify == "self_check":
        return "armC"
    return "armB"


def derive_stage_keys(
    cli_bin: Path, task_family: Optional[str]
) -> tuple[str, dict[tuple[str, str], str]]:
    """Return (domain_bucket, {(stage, option): stage_option_id})."""
    response = call_cli(
        cli_bin,
        "derive-stage-keys",
        {
            "schema": "econ_fold_cli.derive_stage_keys.request.v1",
            "task_family": task_family,
        },
    )
    bucket = response["domain_bucket"]
    mapping: dict[tuple[str, str], str] = {}
    for row in response["stage_keys"]:
        mapping[(row["stage_name"], row["option"])] = row["stage_option_id"]
    return bucket, mapping


def fold_and_select_stage(
    cli_bin: Path,
    *,
    stage_name: str,
    domain_bucket: str,
    stage_option_ids: dict[tuple[str, str], str],
    committed_routing_events: list[dict[str, Any]],
    instance_id: str,
    router_mode: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """One stage softmax/argmax over the stage's option space (CLI single source of truth)."""
    options = STAGE_OPTIONS[stage_name]
    candidate_routes = []
    for option in options:
        sid = stage_option_ids[(stage_name, option)]
        candidate_routes.append(
            {
                "route_id": option,
                "market_id": f"stage:{domain_bucket}:{sid}",
                "expected_failure_domain": "swe_bench_worker_repair",
                "requested_tokens": 12000,
                "domain_bucket": domain_bucket,
                "scaffold_id": sid,
            }
        )
    tape_fingerprint = digest(
        "|".join(
            sorted(
                e.get("RoutingPriorUpdated", {}).get("event_hash", "")
                for e in committed_routing_events
            )
        )
    )
    response = call_cli(
        cli_bin,
        "fold-and-suggest-stage",
        {
            "schema": "econ_fold_cli.fold_and_suggest_stage.request.v1",
            "stage_name": stage_name,
            "committed_routing_events": committed_routing_events,
            "initial_prices": [],
            "candidate_routes": candidate_routes,
            "price_signal_hash": digest(f"price-signal.v1:depthk:{tape_fingerprint}"),
            "pput_prior_hash": digest(f"pput-prior.v1:depthk:{instance_id}:{stage_name}"),
            "trigger_event_hash": digest(f"trigger-event.v1:depthk:{instance_id}"),
            "router_mode": router_mode or {"kind": "SoftmaxArgmaxBypass"},
        },
    )
    return response


def select_lineage(
    cli_bin: Path,
    *,
    domain_bucket: str,
    committed_routing_events: list[dict[str, Any]],
    instance_id: str,
    stage_choices: dict[str, str],
) -> str:
    """Lineage selection reuses pre-existing fold-and-suggest (v2) over 4 lineages."""
    descriptors = []
    for lineage in LINEAGES:
        descriptors.append(
            {
                "label": lineage,
                "decomposition_kind": (
                    f"depthk_v2:{stage_choices['context']}"
                    f":{stage_choices['repair']}:{stage_choices['verify']}"
                ),
                "toolchain": [lineage],
                "team_spec": "depthk_composed_scaffold",
                "verify_loop": "swebench_official_harness_v1",
            }
        )
    keys_resp = call_cli(
        cli_bin,
        "derive-keys",
        {
            "schema": "econ_fold_cli.derive_keys.request.v1",
            "task_family": None,
            "scaffold_descriptors": descriptors,
        },
    )
    by_label = {row["label"]: row["scaffold_id"] for row in keys_resp["scaffold_ids"]}
    candidate_routes = []
    for lineage in LINEAGES:
        sid = by_label[lineage]
        candidate_routes.append(
            {
                "route_id": lineage,
                "market_id": f"lineage:{domain_bucket}:{sid}",
                "expected_failure_domain": "swe_bench_worker_repair",
                "requested_tokens": 12000,
                "domain_bucket": domain_bucket,
                "scaffold_id": sid,
            }
        )
    tape_fingerprint = digest(
        "|".join(
            sorted(
                e.get("RoutingPriorUpdated", {}).get("event_hash", "")
                for e in committed_routing_events
            )
        )
    )
    response = call_cli(
        cli_bin,
        "fold-and-suggest",
        {
            "schema": "econ_fold_cli.fold_and_suggest.request.v2",
            "committed_routing_events": committed_routing_events,
            "initial_prices": [],
            "candidate_routes": candidate_routes,
            "price_signal_hash": digest(f"price-signal.v1:depthk-lineage:{tape_fingerprint}"),
            "pput_prior_hash": digest(f"pput-prior.v1:depthk-lineage:{instance_id}"),
            "trigger_event_hash": digest(f"trigger-event.v1:depthk-lineage:{instance_id}"),
            "router_mode": {"kind": "SoftmaxArgmaxBypass"},
        },
    )
    route_id = response["budget_suggestion"]["route_id"]
    if route_id not in LINEAGES:
        raise RuntimeError(f"unexpected lineage route_id {route_id!r}")
    return route_id


def snapshot_stage_nodes(
    cli_bin: Path,
    *,
    domain_bucket: str,
    stage_option_ids: dict[tuple[str, str], str],
    committed_routing_events: list[dict[str, Any]],
    focus: list[tuple[str, str]],
) -> dict[str, dict[str, Any]]:
    """Fold tape once and extract (Q,N,P) for the focused stage keys."""
    response = fold_and_select_stage(
        cli_bin,
        stage_name="context",
        domain_bucket=domain_bucket,
        stage_option_ids=stage_option_ids,
        committed_routing_events=committed_routing_events,
        instance_id="__snapshot__",
    )
    by_scaffold = {row["scaffold_id"]: row for row in response.get("node_states", [])}
    out: dict[str, dict[str, Any]] = {}
    for stage_name, option in focus:
        sid = stage_option_ids[(stage_name, option)]
        key = f"{stage_name}:{option}"
        if sid in by_scaffold:
            out[key] = {
                "stage_option_id": sid,
                "n": by_scaffold[sid]["n"],
                "s": by_scaffold[sid]["s"],
                "p_q32": by_scaffold[sid]["p_q32"],
                "q_eff_q32": by_scaffold[sid]["q_eff_q32"],
            }
        else:
            out[key] = {
                "stage_option_id": sid,
                "n": 0,
                "s": 0,
                "p_q32": str(1 << 31),
                "q_eff_q32": str(1 << 31),
                "note": "absent_from_fold_map_means_N0_prior",
            }
    return out


def credit_assign_v0(
    cli_bin: Path,
    *,
    domain_bucket: str,
    stage_choices: dict[str, str],
    stage_option_ids: dict[tuple[str, str], str],
    verify_verdict: bool,
    instance_id: str,
    lineage: str,
    run_label: str,
    task_index: int,
    fractional_reward: bool = False,
    verify_pass_fraction: float | None = None,
) -> list[dict[str, Any]]:
    """Update all three stage nodes with the same verify reward (equal share, not causal).

    ADR-ECON-006: when ``fractional_reward`` is True, each stage node receives
    ``verdict_fraction_q32 = floor(verify_pass_fraction * 2^32)`` instead of binary v.
    """
    events: list[dict[str, Any]] = []
    frac_q32: str | None = None
    if fractional_reward:
        frac = 0.0 if verify_pass_fraction is None else max(0.0, min(1.0, float(verify_pass_fraction)))
        frac_q32 = str(int(frac * (1 << 32)))
    for stage_name in STAGE_WALK:
        option = stage_choices[stage_name]
        sid = stage_option_ids[(stage_name, option)]
        attestation = digest(
            json.dumps(
                {
                    "schema": "depthk.credit_assign_v0.attestation.v1",
                    "instance_id": instance_id,
                    "lineage": lineage,
                    "stage_name": stage_name,
                    "option": option,
                    "verify_verdict": verify_verdict,
                    "verify_pass_fraction": verify_pass_fraction,
                    "fractional_reward": fractional_reward,
                    "run_label": run_label,
                    "task_index": task_index,
                    "credit_assignment": CREDIT_ASSIGNMENT_V0,
                },
                sort_keys=True,
            )
        )
        build_req: dict[str, Any] = {
            "schema": "econ_fold_cli.build_routing_prior_updated.request.v1",
            "route_domain": domain_bucket,
            "route_scaffold": sid,
            "verdict": bool(verify_verdict),
            "verdict_source_id": "verifier:depthk_credit_assign_v0",
            "verifier_attestation_hash": attestation,
        }
        if frac_q32 is not None:
            build_req["verdict_fraction_q32"] = frac_q32
        build = call_cli(
            cli_bin,
            "build-routing-prior-updated",
            build_req,
        )
        events.append(build["event"])
    return events


def run_offline_mock(out_dir: Path, cli_bin: Path) -> dict[str, Any]:
    """Deterministic offline path: no worker/API/Docker."""
    out_dir.mkdir(parents=True, exist_ok=True)
    committed: list[dict[str, Any]] = []
    tasks_out: list[dict[str, Any]] = []

    # Same domain_bucket so stage nodes are shared across the two synthetic scaffolds.
    synthetic = [
        {"instance_id": "mock__task_alpha", "repo": "Astropy/Astropy"},
        {"instance_id": "mock__task_beta", "repo": "Astropy/Astropy"},
    ]
    for task_index, packet in enumerate(synthetic):
        bucket, stage_ids = derive_stage_keys(cli_bin, packet["repo"])
        stage_selections: dict[str, Any] = {}
        for stage_name in STAGE_WALK:
            sel = fold_and_select_stage(
                cli_bin,
                stage_name=stage_name,
                domain_bucket=bucket,
                stage_option_ids=stage_ids,
                committed_routing_events=committed,
                instance_id=packet["instance_id"],
                router_mode={"kind": "SoftmaxUniform"},
            )
            chosen = sel["budget_suggestion"]["route_id"]
            stage_selections[stage_name] = {
                "route_id": chosen,
                "stage_option_id": stage_ids[(stage_name, chosen)],
            }

        # Force shared path for the sharing assertion.
        stage_choices = {
            "context": "source_context",
            "repair": "loop",
            "verify": "none",
        }
        arm = compose_dispatch_arm(**stage_choices)
        lineage = "deepseek"
        focus = [(s, stage_choices[s]) for s in STAGE_WALK]
        before = snapshot_stage_nodes(
            cli_bin,
            domain_bucket=bucket,
            stage_option_ids=stage_ids,
            committed_routing_events=committed,
            focus=focus,
        )
        verify_verdict = task_index == 0
        new_events = credit_assign_v0(
            cli_bin,
            domain_bucket=bucket,
            stage_choices=stage_choices,
            stage_option_ids=stage_ids,
            verify_verdict=verify_verdict,
            instance_id=packet["instance_id"],
            lineage=lineage,
            run_label="offline_mock",
            task_index=task_index,
        )
        committed.extend(new_events)
        after = snapshot_stage_nodes(
            cli_bin,
            domain_bucket=bucket,
            stage_option_ids=stage_ids,
            committed_routing_events=committed,
            focus=focus,
        )
        tasks_out.append(
            {
                "instance_id": packet["instance_id"],
                "domain_bucket": bucket,
                "stage_choices": stage_choices,
                "stage_selections_live": stage_selections,
                "dispatch_arm": arm,
                "lineage": lineage,
                "verify_verdict": verify_verdict,
                "nodes_before": before,
                "nodes_after": after,
                "credit_assignment": CREDIT_ASSIGNMENT_V0,
                "events_appended": len(new_events),
            }
        )

    bucket, stage_ids = derive_stage_keys(cli_bin, "Sympy/Sympy")
    seed_sep = {}
    for stage_name in STAGE_WALK:
        sel = fold_and_select_stage(
            cli_bin,
            stage_name=stage_name,
            domain_bucket=bucket,
            stage_option_ids=stage_ids,
            committed_routing_events=[],
            instance_id="seed-sep-instance",
            router_mode={"kind": "SoftmaxUniform"},
        )
        seed_sep[stage_name] = sel["budget_suggestion"]["route_id"]

    shared_ns = {
        k: tasks_out[-1]["nodes_after"][k]["n"] for k in tasks_out[-1]["nodes_after"]
    }

    verdict = {
        "schema": DRIVER_SCHEMA,
        "mode": "offline_mock",
        "evidence_class": "OFFLINE_MOCK",
        "credit_assignment": CREDIT_ASSIGNMENT_V0,
        "tasks": tasks_out,
        "seed_domain_separation": seed_sep,
        "shared_stage_node_n_after_two_tasks": shared_ns,
        "assertions": {
            "shared_nodes_n_equals_2": all(n == 2 for n in shared_ns.values()),
            "seed_sep_all_stages_present": set(seed_sep) == set(STAGE_WALK),
            "deterministic_replay_note": "re-run this mode; bit-identical verdict expected",
        },
        "worker_calls_used": 0,
    }
    (out_dir / "verdict.json").write_text(
        json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return verdict


def _import_live_driver():
    """Lazy import for smoke path only (read-only use of public helpers)."""
    sys.path.insert(0, str(ECON_LAB_DIR))
    sys.path.insert(0, str(REPO_ROOT / "tools" / "bench"))
    sys.path.insert(0, str(REPO_ROOT / "src"))
    import live_driver as ld  # noqa: WPS433

    return ld


def load_s02_packets(max_tasks: int) -> list[dict[str, Any]]:
    packets = []
    for path in sorted(S02_SHARD.glob(TASKS_GLOB)):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["_task_packet_path"] = path
        data["_task_dir"] = path.parent
        packets.append(data)
    if not packets:
        raise SystemExit(f"no S02 task packets under {S02_SHARD}")
    return packets[:max_tasks]


def run_smoke(
    out_dir: Path,
    cli_bin: Path,
    *,
    scoring_python: str,
    max_worker_calls: int,
    max_tasks: int,
    scoring_timeout_s: int,
    fractional_reward: bool = False,
) -> dict[str, Any]:
    """Real smoke: ≤max_worker_calls worker dispatches on S02 tasks, full stage chain."""
    if max_worker_calls > 8:
        raise SystemExit("hard budget ceiling is 8 real worker calls (CAPSULE B)")
    out_dir.mkdir(parents=True, exist_ok=True)
    task_runs = out_dir / "task_runs"
    scoring_root = out_dir / "scoring"
    task_runs.mkdir(parents=True, exist_ok=True)
    scoring_root.mkdir(parents=True, exist_ok=True)

    ld = _import_live_driver()
    packets = load_s02_packets(max_tasks)
    deepseek_cfg = ld.load_provider_config()
    committed: list[dict[str, Any]] = []
    tasks_out: list[dict[str, Any]] = []
    worker_calls = 0
    run_label = f"depthk_smoke:{out_dir.name}"

    for task_index, packet in enumerate(packets):
        if worker_calls >= max_worker_calls:
            break
        instance_id = packet["instance_id"]
        family = packet.get("repo")
        bucket, stage_ids = derive_stage_keys(cli_bin, family)

        stage_choices: dict[str, str] = {}
        stage_chain: list[dict[str, Any]] = []
        for stage_name in STAGE_WALK:
            sel = fold_and_select_stage(
                cli_bin,
                stage_name=stage_name,
                domain_bucket=bucket,
                stage_option_ids=stage_ids,
                committed_routing_events=committed,
                instance_id=instance_id,
                router_mode={"kind": "SoftmaxArgmaxBypass"},
            )
            chosen = sel["budget_suggestion"]["route_id"]
            stage_choices[stage_name] = chosen
            stage_chain.append(
                {
                    "stage_name": stage_name,
                    "option": chosen,
                    "stage_option_id": stage_ids[(stage_name, chosen)],
                    "budget_suggestion": sel["budget_suggestion"],
                }
            )

        lineage = select_lineage(
            cli_bin,
            domain_bucket=bucket,
            committed_routing_events=committed,
            instance_id=instance_id,
            stage_choices=stage_choices,
        )
        arm = compose_dispatch_arm(**stage_choices)

        focus = [(s, stage_choices[s]) for s in STAGE_WALK]
        nodes_before = snapshot_stage_nodes(
            cli_bin,
            domain_bucket=bucket,
            stage_option_ids=stage_ids,
            committed_routing_events=committed,
            focus=focus,
        )

        class _Args:
            pass

        args = _Args()
        args.scoring_python = scoring_python
        args.scoring_timeout_s = scoring_timeout_s
        args.fractional_reward = fractional_reward

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
        elif settlement.get("settlement_verdict_resolved") is not None:
            verify_verdict = bool(settlement["settlement_verdict_resolved"])
            verify_pass_fraction = 1.0 if verify_verdict else 0.0

        credit_events: list[dict[str, Any]] = []
        if verify_verdict is not None:
            credit_events = credit_assign_v0(
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

        nodes_after = snapshot_stage_nodes(
            cli_bin,
            domain_bucket=bucket,
            stage_option_ids=stage_ids,
            committed_routing_events=committed,
            focus=focus,
        )

        task_record = {
            "instance_id": instance_id,
            "domain_bucket": bucket,
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
            "credit_assignment": CREDIT_ASSIGNMENT_V0,
            "credit_events_count": len(credit_events),
            "nodes_before": nodes_before,
            "nodes_after": nodes_after,
            "worker_receipt_paths": _find_receipts(task_runs, instance_id, lineage),
            "scoring_report_paths": _find_scoring(scoring_root, instance_id, lineage),
        }
        tasks_out.append(task_record)
        task_dir = task_runs / instance_id
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "depthk_task_record.json").write_text(
            json.dumps(task_record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    verdict = {
        "schema": DRIVER_SCHEMA,
        "mode": "smoke",
        "evidence_class": EVIDENCE_CLASS_SMOKE,
        "credit_assignment": CREDIT_ASSIGNMENT_V0,
        "credit_assignment_note": (
            "v0 equal share of verify verdict across the three stage nodes used on the path; "
            "not causal credit assignment — known ceiling, not a defect"
        ),
        "fractional_reward": fractional_reward,
        "task_shard": "S02",
        "tasks": tasks_out,
        "worker_calls_used": worker_calls,
        "max_worker_calls": max_worker_calls,
        "committed_routing_events_count": len(committed),
        "significance_claims": "NONE — exploratory feasibility build only",
    }
    (out_dir / "verdict.json").write_text(
        json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "committed_routing_events.json").write_text(
        json.dumps(committed, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return verdict


def _find_receipts(task_runs: Path, instance_id: str, lineage: str) -> list[str]:
    paths = []
    for candidate in (
        task_runs / instance_id / lineage / "worker_receipt.json",
        task_runs / "deepseek_direct_fallback" / instance_id / "worker_receipt.json",
    ):
        if candidate.exists():
            paths.append(str(candidate))
    return paths


def _find_scoring(scoring_root: Path, instance_id: str, lineage: str) -> list[str]:
    report_dir = scoring_root / instance_id / lineage
    if not report_dir.exists():
        return []
    return [str(p) for p in sorted(report_dir.glob("*.json"))]


def main() -> None:
    parser = argparse.ArgumentParser(description="CAPSULE B depth-k layered market driver")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--econ-fold-cli", type=Path, default=None)
    parser.add_argument("--smoke", action="store_true", help="real S02 smoke (≤8 worker calls)")
    parser.add_argument(
        "--offline-mock",
        action="store_true",
        help="deterministic offline mock (0 worker calls)",
    )
    parser.add_argument("--max-tasks", type=int, default=2)
    parser.add_argument("--max-worker-calls", type=int, default=2)
    parser.add_argument(
        "--scoring-python",
        default=str(Path.home() / ".turingos" / "swebench-venv" / "bin" / "python"),
    )
    parser.add_argument("--scoring-timeout-s", type=int, default=1800)
    parser.add_argument(
        "--fractional-reward",
        action="store_true",
        help="ADR-ECON-006: credit-assign verify-side pass fraction to stage nodes",
    )
    args = parser.parse_args()

    if args.smoke and args.offline_mock:
        raise SystemExit("choose exactly one of --smoke / --offline-mock")
    if not args.smoke and not args.offline_mock:
        raise SystemExit("must pass --smoke or --offline-mock")

    cli_bin = args.econ_fold_cli or find_default_cli_bin()
    if not cli_bin.exists():
        raise SystemExit(f"econ_fold_cli not found at {cli_bin}; build it first")

    if args.offline_mock:
        verdict = run_offline_mock(args.out, cli_bin)
    else:
        verdict = run_smoke(
            args.out,
            cli_bin,
            scoring_python=args.scoring_python,
            max_worker_calls=args.max_worker_calls,
            max_tasks=args.max_tasks,
            scoring_timeout_s=args.scoring_timeout_s,
            fractional_reward=bool(args.fractional_reward),
        )

    print(
        json.dumps(
            {
                "status": "ADDRESSED",
                "worker_calls_used": verdict["worker_calls_used"],
                "out": str(args.out),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
