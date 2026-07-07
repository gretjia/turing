#!/usr/bin/env python3
"""WP9a -- econ_lab 真实运行驱动层 (live-run driver layer).

Spec sources (sole authority; no formula/threshold/key-function is invented here -- a
missing detail is reported BLOCKED, never guessed):
  1. research/RES_ECON_emergence_toplevel_design_20260707.md R1.1 §3, §7 (E-harness / WP9
     rows; the driver is the "real task flow" successor to WP7's fixture-only harness).
  2. adr/ADR-ECON-003-emergence-routing-spec-pins.md Decisions 1 (scaffold_id/domain_bucket),
     4 (deterministic selection, tau limit semantics), 6 (Q/N/P fold, Q_eff feeds selection).
  3. research/PREREG_ECON_emergence_experiments_20260707.md §1, §2, Appendix A (task stream,
     arms, Stage A gating).

Hard stop this file enforces in code, not just by convention: PREREG Appendix A's worker
lineage line is unchecked ("BLOCKED-on-owner ... 本机当前仅有 DeepSeek 一条谱系凭据") and
Appendix A's frozen-declaration checkbox is unchecked, so no Stage A production-scale batch
may run. `--smoke` is the only mode this file permits to spend real worker-call budget
(<= 2 total, enforced below); any other invocation without `--smoke` still runs the full
per-task loop machinery but the caller is responsible for keeping `--max-tasks` bounded --
this file does not gate a production batch, but a production batch was never authorized in
this task and none is invoked here.

Single source of truth for the deterministic math: every routing-key derivation
(domain_bucket/scaffold_id) and every fold/selection decision is a subprocess call into
`econ_fold_cli` (crates/turing-economy/src/bin/econ_fold_cli.rs), never re-derived in
Python. The only Python-side "formula" in this file is the held-out accept/verify split
(`tools/econ_lab/verifier/split.py`, already WP7's own pinned v0 implementation, imported
verbatim, not re-implemented) and the worker dispatch itself (imported from
`tools/bench/run_deepseek_arm_a_worker.py`, WP9a's own M3 precedent, not re-implemented).

Known, reported (not silently patched) spec gaps:
  * Task-packet schema `turingos.swebench_worker_safe_task_packet.v1` carries no literal
    `task_family` key (ADR-ECON-003 Decision 1 assumes one exists). Per this task's own
    dispatch instructions ("repo/family field from packet"), this driver feeds the packet's
    `repo` field (e.g. "astropy/astropy") as the `task_family` input to
    `econ_fold_cli derive-keys`, which performs the actual pinned normalization
    (NFC + ascii-lowercase + trim) -- this file never re-derives that normalization itself.
  * ADR-ECON-003 Decision 5's "B 区配置文件机制(路径在 agent 不可见区)" names a mechanism
    but pins no concrete file path/schema. `--tau-config` below is this driver's own
    placeholder plumbing point (a local JSON file with tau_hi_q32/tau_lo_q32/n_anneal), used
    only for a `--router-mode softmax-finite` invocation this driver never actually takes in
    this task (`--smoke` hardcodes tau=0 argmax-bypass, and no Stage A batch runs at all).
  * ADR-ECON-003 Decision 2's independent-verifier v0 (`tools/econ_lab/verifier/
    independent_verifier.py`) is fixture-only: it judges a synthetic `verify_witnesses`
    array that does not exist for a real SWE-bench task. This driver does NOT invent a live
    differential checker. A task whose case_id lands on the held-out split's VERIFY side
    still gets a real worker dispatch + real score, but the driver does not emit a
    `RoutingPriorUpdated` event for it (no independent verdict exists to attach) -- it is
    recorded in the verdict JSON as `side=verify, backup_update=BLOCKED_NO_LIVE_INDEPENDENT_VERIFIER`.
    A task on the ACCEPT side never triggers a backup update by design (ADR-ECON-003
    Decision 2(a)/(the harness's own `arms.py` convention: only verify-side outcomes ever
    call `ledger.update`), so that is not a gap, it is the pinned design.

Usage:
    python3 tools/econ_lab/live_driver.py --smoke --out <path> \
        [--econ-fold-cli <path>] [--scoring-python <path>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
ECON_LAB_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ECON_LAB_DIR))
sys.path.insert(0, str(REPO_ROOT / "tools" / "bench"))

from verifier.split import ACCEPT_SIDE, VERIFY_SIDE, split_side  # noqa: E402
import run_deepseek_arm_a_worker as arm_a_worker  # noqa: E402

SHARD_ROOT = REPO_ROOT / "evidence/bench/swe_bench_verified_500_campaign_20260629/shards/S01"
TASKS_GLOB = "ipqc/S01-W*/worker_safe_tasks/*/task_packet.json"

DRIVER_SCHEMA = "econ_lab.live_driver.verdict.v1"
EVIDENCE_CLASS_SMOKE = "SMOKE_FIXTURE"
EVIDENCE_CLASS_REAL = "REAL_HARNESS_OUTPUTS_AND_PROVIDER_RECEIPTS"

# Routing space v0 (task instructions: "M3's three scaffolds (armA=pro_source_repair,
# armB=source_context_loop, armC=ablation) x available worker lineage (currently just
# DeepSeek)"). `verify_loop` names the real scorer this driver wires below (the discovered
# scoring entry point), not a placeholder.
ARM_DESCRIPTORS: dict[str, dict[str, Any]] = {
    "armA": {
        "decomposition_kind": "single_shot_capsule_repair",
        "toolchain": ["deepseek"],
        "team_spec": "solo_worker_capsule_only",
        "verify_loop": "swebench_official_harness_v1",
        "source_context_name": None,
    },
    "armB": {
        "decomposition_kind": "source_context_loop_repair",
        "toolchain": ["deepseek"],
        "team_spec": "solo_worker_with_source_context",
        "verify_loop": "swebench_official_harness_v1",
        "source_context_name": "source_context.md",
    },
    "armC": {
        "decomposition_kind": "source_context_loop_repair_ablation",
        "toolchain": ["deepseek"],
        # WP9a scope note (reported, not silently assumed): the real M3 armB/armC
        # distinction was the presence/absence of a failure-memory broadcast-rules section
        # (tools/bench/audit_ablation_capsules.py); this driver has no failure-memory
        # broadcast source wired in yet, so armC here differs from armB only by its
        # scaffold_id (team_spec label below), not by worker-request content. Faithful
        # minimal implementation of "the M3 three scaffolds" per this task's scope, not a
        # silently invented equivalence -- true ablation-content wiring is future work.
        "team_spec": "solo_worker_with_source_context_ablated_broadcast",
        "verify_loop": "swebench_official_harness_v1",
        "source_context_name": "source_context.md",
    },
}
WORKER_LINEAGE = "deepseek"  # PREREG Appendix A: only lineage with credentials today.


# ---------------------------------------------------------------------------
# econ_fold_cli subprocess bridge (single source of truth for all deterministic math)
# ---------------------------------------------------------------------------


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
    proc = subprocess.run(
        [str(cli_bin), subcommand],
        input=json.dumps(request).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"econ_fold_cli {subcommand} failed (exit {proc.returncode}): "
            f"{proc.stderr.decode('utf-8', 'replace')}"
        )
    return json.loads(proc.stdout.decode("utf-8"))


def derive_domain_bucket(cli_bin: Path, task_family: Optional[str]) -> str:
    response = call_cli(
        cli_bin,
        "derive-keys",
        {
            "schema": "econ_fold_cli.derive_keys.request.v1",
            "task_family": task_family,
            "scaffold_descriptors": [],
        },
    )
    return response["domain_bucket"]


def derive_scaffold_ids(cli_bin: Path) -> dict[str, str]:
    """One `derive-keys` call for all three arms' `scaffold_id`s (ADR-ECON-003 Decision 1)."""
    descriptors = [
        {
            "label": arm,
            "decomposition_kind": spec["decomposition_kind"],
            "toolchain": spec["toolchain"],
            "team_spec": spec["team_spec"],
            "verify_loop": spec["verify_loop"],
        }
        for arm, spec in ARM_DESCRIPTORS.items()
    ]
    response = call_cli(
        cli_bin,
        "derive-keys",
        {
            "schema": "econ_fold_cli.derive_keys.request.v1",
            "task_family": None,
            "scaffold_descriptors": descriptors,
        },
    )
    return {row["label"]: row["scaffold_id"] for row in response["scaffold_ids"]}


def fold_and_select(
    cli_bin: Path,
    *,
    committed_routing_events: list[dict[str, Any]],
    domain_bucket: str,
    scaffold_ids: dict[str, str],
    instance_id: str,
    tau_config: Optional[dict[str, int]],
) -> dict[str, Any]:
    candidate_routes = [
        {
            "route_id": f"{instance_id}::{arm}",
            "market_id": f"routing:{domain_bucket}:{scaffold_ids[arm]}",
            "expected_failure_domain": "swe_bench_worker_repair",
            "requested_tokens": 12000,
            "domain_bucket": domain_bucket,
            "scaffold_id": scaffold_ids[arm],
        }
        for arm in ARM_DESCRIPTORS
    ]
    # Opaque commitment hashes (ADR-ECON-003 Decision 4 requires *some* already-committed
    # sha256: digest as seed input, not a specific derivation formula for these two --
    # derived here from the already-committed tape state + instance_id so a replay of the
    # same tape prefix reproduces the same seed input, never from wall-clock/live-random).
    tape_fingerprint = digest(
        "|".join(sorted(e.get("RoutingPriorUpdated", {}).get("event_hash", "") for e in committed_routing_events))
    )
    price_signal_hash = digest("price-signal.v1:" + tape_fingerprint)
    pput_prior_hash = digest("pput-prior.v1:" + instance_id)

    if tau_config is None:
        router_mode = {"kind": "SoftmaxArgmaxBypass"}
    else:
        router_mode = {"kind": "SoftmaxFinite", "tau_q32_mantissa": tau_config["tau_hi_q32_mantissa"]}

    response = call_cli(
        cli_bin,
        "fold-and-suggest",
        {
            "schema": "econ_fold_cli.fold_and_suggest.request.v1",
            "committed_routing_events": committed_routing_events,
            "initial_prices": [],
            "candidate_routes": candidate_routes,
            "price_signal_hash": price_signal_hash,
            "pput_prior_hash": pput_prior_hash,
            "router_mode": router_mode,
        },
    )
    return response


# ---------------------------------------------------------------------------
# Task packets
# ---------------------------------------------------------------------------


def load_task_packets(shard_root: Path = SHARD_ROOT) -> list[dict[str, Any]]:
    packets = []
    for path in sorted(shard_root.glob(TASKS_GLOB)):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["_task_packet_path"] = path
        data["_task_dir"] = path.parent
        packets.append(data)
    return packets


def task_family_for_packet(packet: dict[str, Any]) -> Optional[str]:
    # See module doc's "known, reported spec gap" note: worker-safe packets carry no literal
    # task_family key, so this driver feeds the packet's `repo` field to the CLI's pinned
    # domain_bucket normalization.
    return packet.get("repo")


def nfc_lower_trim_preview(raw: Optional[str]) -> str:
    """Debug-only local preview of what the CLI's `domain_bucket` will very likely return
    (NOT authoritative -- only `econ_fold_cli derive-keys` output is used for routing). Kept
    to a single call site (task selection ordering) and never fed into any fold/selection
    input, so it cannot cause the drift the module doc warns against."""
    if not raw:
        return "default"
    normalized = unicodedata.normalize("NFC", raw).lower().strip()
    return normalized or "default"


# ---------------------------------------------------------------------------
# Non-secret provider config (ADR-ECON-003 out of scope; task instructions: read only
# non-secret base_url/model fields from ~/.turingos/provider-profiles.json, DEEPSEEK_API_KEY
# from env only, never write the key value anywhere).
# ---------------------------------------------------------------------------


def load_provider_config() -> dict[str, Any]:
    profile_path = Path.home() / ".turingos" / "provider-profiles.json"
    data = json.loads(profile_path.read_text(encoding="utf-8"))
    if data.get("stores_api_key_values"):
        raise RuntimeError(
            "refusing to read provider-profiles.json: stores_api_key_values is true, "
            "cannot rule out secret material in this file"
        )
    return {
        "api_key_env": data.get("deepseek_api_key_env", "DEEPSEEK_API_KEY"),
        "base_url": data.get("deepseek_base_url", "https://api.deepseek.com"),
        "model": data.get("deepseek_reasoning_model") or data.get("deepseek_default_model"),
    }


# ---------------------------------------------------------------------------
# Worker dispatch (reuses tools/bench/run_deepseek_arm_a_worker.py verbatim -- WP9a's own
# M3 precedent for DeepSeek request/response shape, cost receipt, patch extraction).
# ---------------------------------------------------------------------------


def dispatch_worker(
    *,
    arm: str,
    packet: dict[str, Any],
    provider_config: dict[str, Any],
    task_dir_root: Path,
    run_id_prefix: str,
) -> dict[str, Any]:
    import os

    instance_id = packet["instance_id"]
    capsule_path = packet["_task_dir"] / "worker_capsule.md"
    api_key = os.environ.get(provider_config["api_key_env"])
    if not api_key:
        return {
            "status": "NOT_RUN",
            "missing_env": [provider_config["api_key_env"]],
            "instance_id": instance_id,
            "arm": arm,
        }

    price_table = {"models": {}}  # no cost-table entry available offline; cost_microusd best-effort 0
    try:
        result = arm_a_worker.run_one_task(
            root=SHARD_ROOT.parent.parent,  # evidence/bench/swe_bench_verified_500_campaign_20260629
            shard="S01",
            window=packet["ipqc_window_id"],
            instance_id=instance_id,
            capsule_path=capsule_path,
            model=provider_config["model"],
            api_key=api_key,
            price_table=price_table,
            max_tokens=12000,
            timeout_s=240,
            thinking_type="disabled",
            reasoning_effort=None,
            source_context_name=ARM_DESCRIPTORS[arm]["source_context_name"],
            extra_context_file=None,
            broadcast_rules=None,
            broadcast_rules_file=None,
            broadcast_section_mode="none",
            visible_capsule_out_dir=None,
            task_dir_root=task_dir_root,
            apply_root_dir=None,
            experiment_phase="wp9a-live-driver",
            run_id_prefix=run_id_prefix,
            split_label="wp9a-live-driver",
            agent_id="wp9a-live-driver",
            branch_id="branch:wp9a-live-driver",
            arm_label=arm,
            receipt_schema_id="turingos.wp9a.live_driver_worker_receipt.v1",
            system_role_label=f"weak {arm} SWE-bench worker (WP9a live-run driver)",
        )
        result["status"] = "COMPLETED"
        return result
    except Exception as error:  # noqa: BLE001 -- live evidence driver records task failures.
        return {
            "status": "ERROR",
            "error_type": type(error).__name__,
            "error_message": str(error),
            "instance_id": instance_id,
            "arm": arm,
        }


# ---------------------------------------------------------------------------
# Scoring: the discovered authoritative entry point is the upstream official SWE-bench
# Docker harness, `python -m swebench.harness.run_evaluation` (see tools/bench/
# run_swebench_shard.py's own `build_command`, and the real M3 S01 arm evaluations already
# on disk at evidence/.../shards/S01/arms/*/scoring/full_s01/*.json and
# turing/logs/run_evaluation/turingos_m3_s01_arm*_20260703/ -- same command shape reused
# here verbatim, never reimplemented as ad hoc pass/fail logic).
# ---------------------------------------------------------------------------


def score_with_official_harness(
    *,
    python_bin: str,
    instance_id: str,
    model_patch: str,
    run_id: str,
    report_dir: Path,
    timeout_s: int = 1800,
) -> dict[str, Any]:
    report_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = report_dir / "predictions.jsonl"
    model_name = "wp9a-live-driver"
    row = {"instance_id": instance_id, "model_name_or_path": model_name, "model_patch": model_patch}
    predictions_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    command = [
        python_bin,
        "-m",
        "swebench.harness.run_evaluation",
        "--dataset_name",
        "princeton-nlp/SWE-bench_Verified",
        "--split",
        "test",
        "--predictions_path",
        str(predictions_path),
        "--instance_ids",
        instance_id,
        "--max_workers",
        "1",
        "--timeout",
        str(timeout_s),
        "--cache_level",
        "env",
        "--namespace",
        "swebench",
        "--run_id",
        run_id,
        "--report_dir",
        str(report_dir),
    ]
    log_path = report_dir / "run_evaluation.log"
    try:
        proc = subprocess.run(
            command,
            cwd=report_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_s + 180,
            text=True,
        )
    except Exception as error:  # noqa: BLE001 -- record the real failure, never fabricate a verdict.
        return {
            "status": "SCORING_ENV_BLOCKED",
            "command": command,
            "error_type": type(error).__name__,
            "error_message": str(error),
        }
    log_path.write_text(proc.stdout or "", encoding="utf-8")

    report_path = report_dir / f"{model_name}.{run_id}.json"
    if proc.returncode != 0 or not report_path.exists():
        return {
            "status": "SCORING_FAILED",
            "command": command,
            "returncode": proc.returncode,
            "log_path": str(log_path),
        }
    report = json.loads(report_path.read_text(encoding="utf-8"))
    instance_report = report.get(instance_id, {})
    return {
        "status": "COMPLETED",
        "resolved": bool(instance_report.get("resolved", False)),
        "report_path": str(report_path),
        "log_path": str(log_path),
        "raw_report": instance_report,
    }


# ---------------------------------------------------------------------------
# Main per-task loop
# ---------------------------------------------------------------------------


def run_driver(args: argparse.Namespace) -> dict[str, Any]:
    cli_bin = args.econ_fold_cli or find_default_cli_bin()
    evidence_class = EVIDENCE_CLASS_SMOKE if args.smoke else EVIDENCE_CLASS_REAL

    packets = load_task_packets()
    if not packets:
        raise SystemExit(f"no task packets found under {SHARD_ROOT}/{TASKS_GLOB}")

    scaffold_ids = derive_scaffold_ids(cli_bin)

    if args.smoke:
        # Deliverable 3: exactly 1 task x 1 arm, tau=0, real worker calls <= 2 total.
        # Task selection (deterministic, not outcome-cherry-picked): the first task (sorted
        # instance_id order) whose held-out case_id lands on the ACCEPT side, so the smoke
        # run exercises the fully-real, unblocked leg (dispatch -> official-harness scoring
        # -> accept-side settlement, no backup/independent-verifier call needed by design --
        # see module doc's independent-verifier gap note for why VERIFY-side tasks are
        # skipped here).
        selected = None
        for packet in sorted(packets, key=lambda p: p["instance_id"]):
            if split_side(packet["instance_id"]) == ACCEPT_SIDE:
                selected = packet
                break
        if selected is None:
            raise SystemExit("no task in this shard lands on the held-out ACCEPT side (unexpected)")
        packets = [selected]
        max_tasks = 1
        tau_config = None  # tau=0 argmax-bypass, per --smoke's own contract
    else:
        max_tasks = args.max_tasks if args.max_tasks is not None else len(packets)
        tau_config = None  # this driver invocation never runs Stage A; see module doc.

    provider_config = load_provider_config()
    task_dir_root = args.task_dir_root or (Path(args.out).resolve().parent / "task_runs")
    report_root = args.report_dir or (Path(args.out).resolve().parent / "scoring")

    committed_routing_events: list[dict[str, Any]] = []
    task_results: list[dict[str, Any]] = []
    real_worker_calls = 0

    for packet in packets[:max_tasks]:
        instance_id = packet["instance_id"]
        task_family = task_family_for_packet(packet)
        domain_bucket = derive_domain_bucket(cli_bin, task_family)

        selection = fold_and_select(
            cli_bin,
            committed_routing_events=committed_routing_events,
            domain_bucket=domain_bucket,
            scaffold_ids=scaffold_ids,
            instance_id=instance_id,
            tau_config=tau_config,
        )
        selected_route_id = selection["budget_suggestion"]["route_id"]
        selected_arm = selected_route_id.split("::")[-1]

        side = split_side(instance_id)

        if args.smoke and real_worker_calls >= 2:
            # Hard cap enforced in code, not just by convention (deliverable 3 red line).
            worker_result = {"status": "SKIPPED_SPEND_CAP", "instance_id": instance_id, "arm": selected_arm}
        else:
            worker_result = dispatch_worker(
                arm=selected_arm,
                packet=packet,
                provider_config=provider_config,
                task_dir_root=task_dir_root,
                run_id_prefix="wp9a-live-driver",
            )
            if worker_result.get("status") == "COMPLETED":
                real_worker_calls += 1

        scoring_result: dict[str, Any] = {"status": "SKIPPED_NO_PATCH"}
        settlement_verdict: Optional[bool] = None
        if worker_result.get("status") == "COMPLETED":
            patch_path = task_dir_root / instance_id / "candidate.patch"
            model_patch = patch_path.read_text(encoding="utf-8") if patch_path.exists() else ""
            if model_patch.strip():
                scoring_result = score_with_official_harness(
                    python_bin=args.scoring_python,
                    instance_id=instance_id,
                    model_patch=model_patch,
                    run_id=f"wp9a-live-driver-{instance_id}",
                    report_dir=report_root / instance_id,
                    timeout_s=args.scoring_timeout_s,
                )
                if scoring_result.get("status") == "COMPLETED":
                    settlement_verdict = scoring_result["resolved"]

        backup_update: dict[str, Any] = {"applied": False}
        if side == ACCEPT_SIDE:
            backup_update = {"applied": False, "reason": "accept_side_no_backup_update_by_design"}
        elif side == VERIFY_SIDE:
            # See module doc's independent-verifier gap: no live differential checker is
            # wired for real SWE-bench tasks, so no RoutingPriorUpdated is fabricated here.
            backup_update = {"applied": False, "reason": "BLOCKED_NO_LIVE_INDEPENDENT_VERIFIER"}

        task_results.append(
            {
                "instance_id": instance_id,
                "domain_bucket": domain_bucket,
                "scaffold_ids": scaffold_ids,
                "selected_route_id": selected_route_id,
                "selected_arm": selected_arm,
                "budget_suggestion": selection["budget_suggestion"],
                "held_out_split_side": side,
                "worker_result_status": worker_result.get("status"),
                "worker_result": {k: v for k, v in worker_result.items() if k != "usage_raw_sha256"},
                "scoring_result": {k: v for k, v in scoring_result.items() if k != "command"},
                "settlement_verdict_resolved": settlement_verdict,
                "backup_update": backup_update,
                "evidence_class": evidence_class,
            }
        )

    verdict = {
        "schema": DRIVER_SCHEMA,
        "evidence_class": evidence_class,
        "mode": "smoke" if args.smoke else "full",
        "worker_lineage": WORKER_LINEAGE,
        "arm_descriptors": {arm: spec["decomposition_kind"] for arm, spec in ARM_DESCRIPTORS.items()},
        "scaffold_ids": scaffold_ids,
        "real_worker_calls_made": real_worker_calls,
        "real_worker_calls_cap": 2 if args.smoke else None,
        "task_count": len(task_results),
        "tasks": task_results,
        "generated_at_unix": int(time.time()),
    }
    return verdict


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--smoke", action="store_true", help="1 task x 1 arm, tau=0, <=2 real worker calls")
    parser.add_argument("--max-tasks", type=int, default=None, help="only used outside --smoke")
    parser.add_argument("--out", type=Path, required=True, help="verdict JSON output path")
    parser.add_argument("--econ-fold-cli", type=Path, default=None)
    parser.add_argument(
        "--scoring-python",
        default=sys.executable,
        help="python interpreter with a working `swebench` package (numpy<2-ABI compatible; "
        "see module doc's environment note if the current interpreter's swebench import is broken)",
    )
    parser.add_argument("--scoring-timeout-s", type=int, default=1800)
    parser.add_argument("--task-dir-root", type=Path, default=None)
    parser.add_argument("--report-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    verdict = run_driver(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "WROTE_VERDICT", "path": str(args.out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
