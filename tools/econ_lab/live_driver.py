#!/usr/bin/env python3
"""WP9a -- econ_lab 真实运行驱动层 (live-run driver layer).

Spec sources (sole authority; no formula/threshold/key-function is invented here -- a
missing detail is reported BLOCKED, never guessed):
  1. research/RES_ECON_emergence_toplevel_design_20260707.md R1.1 §3, §7 (E-harness / WP9
     rows; the driver is the "real task flow" successor to WP7's fixture-only harness).
  2. adr/ADR-ECON-003-emergence-routing-spec-pins.md Decisions 1 (scaffold_id/domain_bucket),
     4 (deterministic selection, tau limit semantics), 6 (Q/N/P fold, Q_eff feeds selection).
  3. research/PREREG_ECON_emergence_experiments_20260707.md §1, §2, Appendix A (task stream,
     arms, worker lineage, Stage A gating).

Lineage-expansion update (PREREG Appendix A frozen 2026-07-07): worker lineage went from
"DeepSeek only" to 4 independent pretrained lineages, 3 of them ((Qwen/GLM/Kimi) reachable
only through a SiliconFlow aggregator credential, DeepSeek reachable through SiliconFlow as
primary with direct `DEEPSEEK_API_KEY` as fallback:
  - deepseek: `deepseek-ai/DeepSeek-V4-Flash` (SiliconFlow primary, DeepSeek-direct fallback)
  - qwen:     `Qwen/Qwen3-Coder-30B-A3B-Instruct` (SiliconFlow only)
  - glm:      `zai-org/GLM-4.5-Air` (SiliconFlow only)
  - kimi:     `moonshotai/Kimi-K2.7-Code` (SiliconFlow only)
Routing space v0 is therefore 4 lineages x 3 scaffolds = 12 candidate routes per task.
Appendix A itself flags (honestly, not hidden by this file) that lineages 2-4 share the same
SiliconFlow serving infrastructure -- "谱系 = 预训练祖先,行为相关性由 N_eff 估计器实测"
(lineage = pretraining ancestry; behavioral correlation is *measured*, not assumed, by the
N_eff estimator) -- which is exactly why this file wires N_eff/H_lineage (WP5) below rather
than asserting independence a priori.

Hard stop this file enforces in code, not just by convention: PREREG Appendix A's task-flow
and worker-lineage checkboxes are frozen, but the frozen-declaration line at the very bottom
of Appendix A ("冻结声明行(全部就绪后:日期 + 声明人)") is still unchecked, so no Stage A
production-scale batch may run. `--smoke` is the only mode this file permits to spend real
worker-call budget (<= 4 total, at most 1 per lineage, enforced below); any other invocation
without `--smoke` still runs the full per-task loop machinery but the caller is responsible
for keeping `--max-tasks` bounded -- this file does not gate a production batch, but a
production batch was never authorized in this task and none is invoked here.

Single source of truth for the deterministic math: every routing-key derivation
(domain_bucket/scaffold_id), every fold/selection decision, the N_eff/H_lineage
diversity-metrics estimate, and every `RoutingPriorUpdated` event's `event_hash` (WP9b) is a
subprocess call into `econ_fold_cli` (crates/turing-economy/src/bin/econ_fold_cli.rs), never
re-derived in Python. The only Python-side "formula" reachable from this file is the
held-out accept/verify split (`tools/econ_lab/verifier/split.py`'s pinned v0
`SHA256("heldout-split.v1" + id)` first-byte-parity implementation, WP7's own), now applied
at **test_id** granularity by `tools/econ_lab/verifier/live_split_verifier.py` (WP9b,
ADR-ECON-003 Decision 2 point 4) rather than at this file's own `instance_id` granularity --
see that module's docstring and `_settle_one` below; the DeepSeek-direct dispatch is imported
from
`tools/bench/run_deepseek_arm_a_worker.py` (WP9a's own M3 precedent, not re-implemented),
and the 3 new SiliconFlow-routed lineages' dispatch reuses that same module's prompt-text
and response-parsing helpers (`response_message`, `extract_unified_diff`) -- only the actual
HTTP client call is new, unavoidable plumbing (a different provider's wire endpoint), not a
duplicated formula.

Lineage-label discipline (this file's own added rule, requested alongside the frozen
Appendix A update -- not one of the 4 gate_f4-forbidden identifier families, but held to the
same discipline): the 4 short lineage labels (`deepseek`/`qwen`/`glm`/`kimi`) are the only
lineage identifiers that ever appear in a settlement record, the diversity-metrics history,
the verdict JSON, or this file's own stdout/stderr. The full model-ID strings
(`LINEAGE_CONFIGS[...]["model_id"]`) are confined to provider-config/dispatch internals and
the raw per-task `worker_receipt.json` artifact (the same place the pre-existing DeepSeek
worker script already records `model_requested`/`model_reported` -- a dispatch-internal
artifact, not a routing/diversity/settlement surface).

Known, reported (not silently patched) spec gaps:
  * Task-packet schema `turingos.swebench_worker_safe_task_packet.v1` carries no literal
    `task_family` key (ADR-ECON-003 Decision 1 assumes one exists). Per this task's own
    dispatch instructions ("repo/family field from packet"), this driver feeds the packet's
    `repo` field (e.g. "astropy/astropy") as the `task_family` input to
    `econ_fold_cli derive-keys`, which performs the actual pinned normalization
    (NFC + ascii-lowercase + trim) -- this file never re-derives that normalization itself.
  * The frozen Appendix A shard-size claim ("55 个 worker-safe 任务包,5 波 x 11 题") still
    does not match the materialized shard on disk: `evidence/bench/
    swe_bench_verified_500_campaign_20260629/shards/S01/shard_manifest.json` states
    `"task_count": 50, "audit_atom": "50_task_sealed_shard"` (verified: 10 tasks x 5 windows).
    This driver loads whatever actually exists (50), not a fabricated 55th task.
  * ADR-ECON-003 Decision 5's "B 区配置文件机制(路径在 agent 不可见区)" names a mechanism
    but pins no concrete file path/schema. `--tau-config` below is this driver's own
    placeholder plumbing point, used only for a `--router-mode softmax-finite` invocation
    this driver never actually takes in this task (`--smoke` hardcodes tau=0 argmax-bypass,
    and no Stage A batch runs at all).
  * SUPERSEDED (WP9b, ADR-ECON-003 Decision 2 point 4, 2026-07-07 增补): this driver used to
    have no live independent verifier -- `tools/econ_lab/verifier/independent_verifier.py`
    is fixture-only (it judges a synthetic `verify_witnesses` array that does not exist for
    a real SWE-bench task), and the driver used to split on the whole task's `instance_id`
    (`verifier.split.split_side`), recording every VERIFY-side task's backup update as
    `BLOCKED_NO_LIVE_INDEPENDENT_VERIFIER` and every ACCEPT-side task's as
    `accept_side_no_backup_update_by_design` -- i.e. Q never updated, ever. Decision 2.4
    replaces the instance_id-level split entirely with a **test_id-level** split
    (`tools/econ_lab/verifier/live_split_verifier.py`, reusing `verifier.split.split_side`'s
    same hash/domain-separator at test_id granularity): every scored (task, arm, lineage)
    dispatch now gets BOTH an `accept_verdict` (market settlement) and a `verify_verdict`
    (backup/RoutingPriorUpdated) read independently from the same harness execution's
    per-test report. See `_settle_one` and `run_driver` below for the wiring.
  * The frozen Appendix A text pins DeepSeek-direct as "fallback" for the deepseek lineage
    but does not pin an exact trigger condition (e.g. a specific HTTP status). This driver
    treats "SiliconFlow dispatch returned NOT_RUN (missing SILICONFLOW_API_KEY) or ERROR
    (the call itself failed)" as the trigger -- documented dispatch-plumbing judgment, not a
    guessed fold/selection formula (Decisions 4/6 are untouched by this choice).

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
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
ECON_LAB_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ECON_LAB_DIR))
sys.path.insert(0, str(REPO_ROOT / "tools" / "bench"))

from verifier import live_split_verifier  # noqa: E402
import run_deepseek_arm_a_worker as arm_a_worker  # noqa: E402

SHARD_ROOT = REPO_ROOT / "evidence/bench/swe_bench_verified_500_campaign_20260629/shards/S01"
TASKS_GLOB = "ipqc/S01-W*/worker_safe_tasks/*/task_packet.json"

DRIVER_SCHEMA = "econ_lab.live_driver.verdict.v1"
EVIDENCE_CLASS_SMOKE = "SMOKE_FIXTURE"
EVIDENCE_CLASS_REAL = "REAL_HARNESS_OUTPUTS_AND_PROVIDER_RECEIPTS"

SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
SILICONFLOW_API_KEY_ENV = "SILICONFLOW_API_KEY"

# Routing space v0, scaffold axis (task instructions: M3's three scaffolds). `verify_loop`
# names the real scorer this driver wires below (the discovered scoring entry point).
ARM_DESCRIPTORS: dict[str, dict[str, Any]] = {
    "armA": {
        "decomposition_kind": "single_shot_capsule_repair",
        "team_spec": "solo_worker_capsule_only",
        "verify_loop": "swebench_official_harness_v1",
        "source_context_name": None,
    },
    "armB": {
        "decomposition_kind": "source_context_loop_repair",
        "team_spec": "solo_worker_with_source_context",
        "verify_loop": "swebench_official_harness_v1",
        "source_context_name": "source_context.md",
    },
    "armC": {
        "decomposition_kind": "source_context_loop_repair_ablation",
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

# Routing space v0, lineage axis (PREREG Appendix A, frozen 2026-07-07). Full model IDs are
# confined here and to dispatch internals -- see module doc's lineage-label discipline note.
LINEAGE_CONFIGS: dict[str, dict[str, Any]] = {
    "deepseek": {
        "model_id": "deepseek-ai/DeepSeek-V4-Flash",
        "primary": {"base_url": SILICONFLOW_BASE_URL, "api_key_env": SILICONFLOW_API_KEY_ENV},
        "has_native_fallback": True,
    },
    "qwen": {
        "model_id": "Qwen/Qwen3-Coder-30B-A3B-Instruct",
        "primary": {"base_url": SILICONFLOW_BASE_URL, "api_key_env": SILICONFLOW_API_KEY_ENV},
        "has_native_fallback": False,
    },
    "glm": {
        "model_id": "zai-org/GLM-4.5-Air",
        "primary": {"base_url": SILICONFLOW_BASE_URL, "api_key_env": SILICONFLOW_API_KEY_ENV},
        "has_native_fallback": False,
    },
    "kimi": {
        "model_id": "moonshotai/Kimi-K2.7-Code",
        "primary": {"base_url": SILICONFLOW_BASE_URL, "api_key_env": SILICONFLOW_API_KEY_ENV},
        "has_native_fallback": False,
    },
}
LINEAGES = tuple(LINEAGE_CONFIGS.keys())  # ("deepseek", "qwen", "glm", "kimi")


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


def _scaffold_label(arm: str, lineage: str) -> str:
    return f"{arm}::{lineage}"


def derive_scaffold_ids(cli_bin: Path) -> dict[str, dict[str, str]]:
    """One `derive-keys` call for all 12 (arm, lineage) `scaffold_id`s (ADR-ECON-003
    Decision 1). The lineage enters the descriptor's `toolchain` field (the short label
    only, per the module doc's lineage-label discipline) so each (arm, lineage) pair gets
    its own distinct routing-fold node, as the routing space's 4x3 shape requires.

    Returns `{arm: {lineage: scaffold_id}}`.
    """
    descriptors = [
        {
            "label": _scaffold_label(arm, lineage),
            "decomposition_kind": spec["decomposition_kind"],
            "toolchain": [lineage],
            "team_spec": spec["team_spec"],
            "verify_loop": spec["verify_loop"],
        }
        for arm, spec in ARM_DESCRIPTORS.items()
        for lineage in LINEAGES
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
    by_label = {row["label"]: row["scaffold_id"] for row in response["scaffold_ids"]}
    result: dict[str, dict[str, str]] = {arm: {} for arm in ARM_DESCRIPTORS}
    for arm in ARM_DESCRIPTORS:
        for lineage in LINEAGES:
            result[arm][lineage] = by_label[_scaffold_label(arm, lineage)]
    return result


def fold_and_select(
    cli_bin: Path,
    *,
    committed_routing_events: list[dict[str, Any]],
    domain_bucket: str,
    scaffold_ids: dict[str, dict[str, str]],
    instance_id: str,
    tau_config: Optional[dict[str, int]],
) -> dict[str, Any]:
    """Routes over the full 4-lineage x 3-scaffold = 12-candidate space (PREREG Appendix A
    lineage-expansion update)."""
    candidate_routes = [
        {
            "route_id": f"{instance_id}::{arm}::{lineage}",
            "market_id": f"routing:{domain_bucket}:{scaffold_ids[arm][lineage]}",
            "expected_failure_domain": "swe_bench_worker_repair",
            "requested_tokens": 12000,
            "domain_bucket": domain_bucket,
            "scaffold_id": scaffold_ids[arm][lineage],
        }
        for arm in ARM_DESCRIPTORS
        for lineage in LINEAGES
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


def diversity_metrics_for_history(cli_bin: Path, history: list[dict[str, Any]]) -> dict[str, Any]:
    """Single source of truth: turing_economy::diversity_metrics::compute_n_eff_and_h_lineage
    (WP5), via the `diversity-metrics` subcommand. `history` entries carry only short lineage
    labels (module doc's lineage-label discipline)."""
    return call_cli(
        cli_bin,
        "diversity-metrics",
        {"schema": "econ_fold_cli.diversity_metrics.request.v1", "history": history},
    )


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
    (NOT authoritative -- only `econ_fold_cli derive-keys` output is used for routing)."""
    if not raw:
        return "default"
    normalized = unicodedata.normalize("NFC", raw).lower().strip()
    return normalized or "default"


# ---------------------------------------------------------------------------
# Non-secret provider config (task instructions: read only non-secret base_url/model
# fields from ~/.turingos/provider-profiles.json, API keys from env only, never write a
# key value anywhere).
# ---------------------------------------------------------------------------


def load_provider_config() -> dict[str, Any]:
    """DeepSeek-direct's own non-secret config (the fallback path's native adapter)."""
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
# Worker dispatch.
#
# Two dispatch paths:
#   1. DeepSeek-direct native adapter: reuses tools/bench/run_deepseek_arm_a_worker.py
#      verbatim (WP9a's own M3 precedent) -- this is the deepseek lineage's *fallback* path.
#   2. Generic OpenAI-compatible adapter (new, unavoidable plumbing: SiliconFlow is a
#      distinct HTTP endpoint from DeepSeek's native one): the deepseek lineage's *primary*
#      path, and the only path for qwen/glm/kimi. Reuses arm_a_worker's prompt-construction
#      wording and response-parsing helpers so the same worker prompt/patch-extraction
#      contract holds across every lineage; only the HTTP client call itself is new.
# ---------------------------------------------------------------------------


def dispatch_worker(
    *,
    arm: str,
    packet: dict[str, Any],
    provider_config: dict[str, Any],
    task_dir_root: Path,
    run_id_prefix: str,
) -> dict[str, Any]:
    """DeepSeek-direct native adapter (deepseek lineage's fallback path)."""
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
            timeout_s=600,
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


def _build_generic_chat_request(*, model: str, capsule_text: str, max_tokens: int) -> dict[str, Any]:
    """Minimal, standard OpenAI-compatible chat-completion request. Prompt wording
    deliberately mirrors `run_deepseek_arm_a_worker.build_worker_request`'s system/user
    content (same worker contract across every lineage) but omits DeepSeek-specific fields
    (`thinking`, `reasoning_effort`) that a generic OpenAI-compatible endpoint may not
    recognize."""
    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a weak SWE-bench worker. Use only the worker-safe capsule. "
                    "Return only a source-code unified diff. Do not edit tests. "
                    "Do not mention hidden tests, gold patches, or evaluator labels."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Your first characters must be: diff --git \n"
                    "Produce one best-effort source-only unified diff for this SWE-bench task. "
                    "Do not wrap the diff in markdown fences and do not add explanation before or after it. "
                    "If uncertain, still return the best source-only patch you can infer.\n\n"
                    + capsule_text
                ),
            },
        ],
        "stream": False,
        "max_tokens": max_tokens,
    }


def _call_openai_compatible(
    *, base_url: str, api_key: str, request_payload: dict[str, Any], timeout_s: int
) -> tuple[dict[str, Any], str, int]:
    """Generic OpenAI-compatible `/chat/completions` POST (SiliconFlow's own documented
    wire format). Mirrors `run_deepseek_provider_canary.call_deepseek`'s shape but is not
    DeepSeek-specific: no assumptions about DeepSeek-only usage fields."""
    data = json.dumps(request_payload, sort_keys=True).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=data,
        method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    start = time.monotonic()
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        raw_bytes = response.read()
    wall_time_ms = int((time.monotonic() - start) * 1000)
    raw_text = raw_bytes.decode("utf-8", errors="replace")
    parsed = json.loads(raw_text)
    if not isinstance(parsed, dict):
        raise ValueError("provider response must be a JSON object")
    return parsed, raw_text, wall_time_ms


def dispatch_via_siliconflow(
    *,
    arm: str,
    lineage: str,
    packet: dict[str, Any],
    task_dir_root: Path,
    timeout_s: int = 600,
) -> dict[str, Any]:
    """Generic OpenAI-compatible dispatch (SiliconFlow primary path for all 4 lineages)."""
    import os

    instance_id = packet["instance_id"]
    api_key = os.environ.get(SILICONFLOW_API_KEY_ENV)
    if not api_key:
        return {
            "status": "NOT_RUN",
            "missing_env": [SILICONFLOW_API_KEY_ENV],
            "instance_id": instance_id,
            "arm": arm,
            "lineage": lineage,
            "provider_path": "siliconflow",
        }

    model_id = LINEAGE_CONFIGS[lineage]["model_id"]
    capsule_path = packet["_task_dir"] / "worker_capsule.md"
    source_context_name = ARM_DESCRIPTORS[arm]["source_context_name"]
    try:
        capsule_text, _source_meta = arm_a_worker.load_worker_visible_context(
            capsule_path, source_context_name=source_context_name
        )
        request_payload = _build_generic_chat_request(model=model_id, capsule_text=capsule_text, max_tokens=12000)
        response, response_raw, wall_time_ms = _call_openai_compatible(
            base_url=SILICONFLOW_BASE_URL, api_key=api_key, request_payload=request_payload, timeout_s=timeout_s
        )
        message = arm_a_worker.response_message(response)
        content = message.get("content") or ""
        if not isinstance(content, str):
            raise ValueError("response content must be a string or null")
        patch_text = arm_a_worker.extract_unified_diff(content)

        task_dir = task_dir_root / instance_id / lineage
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "candidate.patch").write_text(patch_text, encoding="utf-8")
        # Dispatch-internal raw artifact only (module doc's lineage-label discipline): the
        # full model_id is fine here, mirroring the pre-existing DeepSeek worker_receipt.json
        # convention (model_requested/model_reported), never propagated further.
        receipt = {
            "schema_id": "turingos.wp9a.live_driver_siliconflow_worker_receipt.v1",
            "status": "COMPLETED",
            "instance_id": instance_id,
            "arm": arm,
            "lineage": lineage,
            "model_requested": model_id,
            "model_reported": str(response.get("model") or ""),
            "wall_time_ms": wall_time_ms,
            "candidate_patch_sha256": digest(patch_text),
            "response_sha256": digest(response_raw),
            "content_length_chars": len(content),
        }
        (task_dir / "worker_receipt.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return {
            "status": "COMPLETED",
            "instance_id": instance_id,
            "arm": arm,
            "lineage": lineage,
            "provider_path": "siliconflow",
            "candidate_patch_sha256": receipt["candidate_patch_sha256"],
            "candidate_patch_bytes": len(patch_text.encode("utf-8")),
            "wall_time_ms": wall_time_ms,
        }
    except urllib.error.HTTPError as error:
        body = error.read()
        return {
            "status": "API_ERROR",
            "http_status": error.code,
            "error_body_sha256": digest(body.decode("utf-8", "replace")),
            "instance_id": instance_id,
            "arm": arm,
            "lineage": lineage,
            "provider_path": "siliconflow",
        }
    except Exception as error:  # noqa: BLE001 -- live evidence driver records task failures.
        return {
            "status": "ERROR",
            "error_type": type(error).__name__,
            "error_message": str(error),
            "instance_id": instance_id,
            "arm": arm,
            "lineage": lineage,
            "provider_path": "siliconflow",
        }


def dispatch_worker_for_lineage(
    *,
    arm: str,
    lineage: str,
    packet: dict[str, Any],
    task_dir_root: Path,
    run_id_prefix: str,
    deepseek_native_provider_config: dict[str, Any],
) -> dict[str, Any]:
    """Dispatch one (arm, lineage) pair, applying the deepseek-only SiliconFlow-primary /
    DeepSeek-direct-fallback rule (PREREG Appendix A, frozen; see module doc's fallback-
    trigger note for the exact condition this driver uses)."""
    primary_result = dispatch_via_siliconflow(
        arm=arm, lineage=lineage, packet=packet, task_dir_root=task_dir_root
    )
    if (
        lineage == "deepseek"
        and LINEAGE_CONFIGS[lineage]["has_native_fallback"]
        and primary_result["status"] in ("NOT_RUN", "ERROR", "API_ERROR")
    ):
        fallback_result = dispatch_worker(
            arm=arm,
            packet=packet,
            provider_config=deepseek_native_provider_config,
            task_dir_root=task_dir_root / "deepseek_direct_fallback",
            run_id_prefix=run_id_prefix,
        )
        fallback_result["lineage"] = lineage
        fallback_result["provider_path"] = "deepseek_direct_fallback"
        fallback_result["primary_attempt_status"] = primary_result["status"]
        return fallback_result
    return primary_result


# ---------------------------------------------------------------------------
# Scoring: the discovered authoritative entry point is the upstream official SWE-bench
# Docker harness, `python -m swebench.harness.run_evaluation` (see tools/bench/
# run_swebench_shard.py's own `build_command`, and the real M3 S01 arm evaluations already
# on disk at evidence/.../shards/S01/arms/*/scoring/full_s01/*.json and
# turing/logs/run_evaluation/turingos_m3_s01_arm*_20260703/ -- same command shape reused
# here verbatim, never reimplemented as ad hoc pass/fail logic).
# ---------------------------------------------------------------------------


# WP9b orchestrator addendum (2026-07-07, "基于刚完成的真实评分链验证,实证锚点在盘上"):
# the aggregated report this function reads back (`{model_name}.{run_id}.json`, written by
# `swebench.harness.reporting.make_run_report`) is `schema_version: 2` -- per-outcome
# instance_id *lists* (`resolved_ids`/`unresolved_ids`/`error_ids`/`empty_patch_ids`/
# `incomplete_ids`), never a `{instance_id: {...}}` mapping. The real per-test `tests_status`
# block lives in a second, separate per-instance report file
# (`swebench.harness.run_evaluation`'s own `report_path`, confirmed against
# `~/.turingos/swebench-venv/lib/python3.11/site-packages/swebench/harness/{run_evaluation,
# reporting,constants}.py`, v4.1.0 -- never guessed from memory): `<report_dir>/
# logs/run_evaluation/<run_id>/<model_name>/<instance_id>/report.json`, which exists only
# when the patch applied and the eval script actually ran (RESOLVED/UNRESOLVED outcomes).
RUN_EVALUATION_LOG_DIR_NAME = "logs/run_evaluation"
PER_INSTANCE_REPORT_FILENAME = "report.json"
PER_INSTANCE_LOG_FILENAME = "run_instance.log"
# `swebench.harness.constants.APPLY_PATCH_FAIL`'s literal marker string (v4.1.0): the one
# `error_ids` cause the orchestrator addendum pins a specific reason for.
APPLY_PATCH_FAIL_MARKER = ">>>>> Patch Apply Failed"


def _per_instance_report_dir(report_dir: Path, *, run_id: str, model_name: str, instance_id: str) -> Path:
    return report_dir / RUN_EVALUATION_LOG_DIR_NAME / run_id / model_name / instance_id


def _read_per_instance_tests_status(instance_dir: Path, instance_id: str) -> Optional[dict[str, Any]]:
    """Read the real per-test `tests_status` block (RESOLVED/UNRESOLVED outcomes only --
    caller guards this). Returns `None` if the file is unexpectedly absent/malformed, which
    `live_split_verifier.judge` already treats defensively (not_enough_tests=True), not as a
    crash."""
    report_path = instance_dir / PER_INSTANCE_REPORT_FILENAME
    if not report_path.exists():
        return None
    try:
        per_instance_report = json.loads(report_path.read_text(encoding="utf-8"))
        return (per_instance_report.get(instance_id) or {}).get("tests_status")
    except (json.JSONDecodeError, AttributeError):
        return None


def _classify_harness_error_reason(instance_dir: Path) -> str:
    """Distinguish the one `error_ids` cause the orchestrator addendum (2026-07-07, point 3)
    pins a specific reason for (`EvaluationError: Patch Apply Failed`, swebench's own
    `APPLY_PATCH_FAIL` marker in `run_instance.log`) from every other `error_ids` cause
    (timeout, build failure, an empty/malformed report file, ...) -- reported generically as
    `"harness_error"` for the latter, never invented as a specific reason this driver was not
    given."""
    log_path = instance_dir / PER_INSTANCE_LOG_FILENAME
    if log_path.exists():
        try:
            log_text = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            log_text = ""
        if APPLY_PATCH_FAIL_MARKER in log_text:
            return "patch_apply_failed"
    return "harness_error"


def score_with_official_harness(
    *,
    python_bin: str,
    instance_id: str,
    model_patch: str,
    run_id: str,
    report_dir: Path,
    timeout_s: int = 1800,
) -> dict[str, Any]:
    # The harness subprocess runs with cwd=report_dir; every path handed to it
    # (and every path this function reads back) must therefore be absolute, or
    # a relative --predictions_path re-resolves against report_dir itself.
    report_dir = report_dir.resolve()
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
    # Aggregated report, schema_version 2 (see this function's module-level doc comment
    # above): per-outcome instance_id lists, not a `{instance_id: {...}}` mapping.
    aggregated_report = json.loads(report_path.read_text(encoding="utf-8"))
    instance_dir = _per_instance_report_dir(
        report_dir, run_id=run_id, model_name=model_name, instance_id=instance_id
    )

    if instance_id in (aggregated_report.get("resolved_ids") or []):
        outcome = "RESOLVED"
    elif instance_id in (aggregated_report.get("unresolved_ids") or []):
        outcome = "UNRESOLVED"
    elif instance_id in (aggregated_report.get("empty_patch_ids") or []):
        outcome = "EMPTY_PATCH"
    elif instance_id in (aggregated_report.get("incomplete_ids") or []):
        outcome = "INCOMPLETE"
    else:
        # swebench's own catch-all bucket (`make_run_report`): no report.json ever existed,
        # or the report file was empty/malformed -- includes, but is not limited to,
        # `EvaluationError: Patch Apply Failed` (orchestrator addendum point 3).
        outcome = "ERROR"

    tests_status: Optional[dict[str, Any]] = None
    harness_error_reason: Optional[str] = None
    if outcome in ("RESOLVED", "UNRESOLVED"):
        tests_status = _read_per_instance_tests_status(instance_dir, instance_id)
    else:
        harness_error_reason = _classify_harness_error_reason(instance_dir)

    return {
        "status": "COMPLETED",
        "outcome": outcome,
        # Kept for back-compat/diagnostics only: this is the harness's own whole-test-suite
        # verdict, no longer what market settlement uses (Decision 2.4: settlement uses
        # `live_split_verdict.accept_verdict`, computed independently by `_settle_one` below).
        "resolved": outcome == "RESOLVED",
        "tests_status": tests_status,
        "harness_error_reason": harness_error_reason,
        "report_path": str(report_path),
        "log_path": str(log_path),
        "raw_report": aggregated_report,
    }


# ---------------------------------------------------------------------------
# Main per-task loop
# ---------------------------------------------------------------------------

# Opaque verifier-instance identifier (ADR-ECON-003 Decision 2.2: structurally separate from
# the accept predicate; carries no formula/threshold value, only labels which independent
# reading script produced the verdict).
LIVE_SPLIT_VERIFIER_SOURCE_ID = "verifier:live_split_verifier.v1"


def _verifier_attestation_hash(*, instance_id: str, arm: str, lineage: str, live_split_result: dict[str, Any]) -> str:
    """`sha256:`-prefixed 64-hex attestation digest over exactly what the independent
    verifier read (the verify-side test_id set and its own verdict, or the harness-error
    reason when there was no per-test data at all) -- not a re-derivation of any
    routing/selection formula, just an evidence digest so a later audit can recompute and
    check it against the same fixed inputs (Art 0.2 style discipline)."""
    payload = {
        "schema": "live_split_verifier.attestation.v1",
        "instance_id": instance_id,
        "arm": arm,
        "lineage": lineage,
        "verify_test_ids": live_split_result["verify_test_ids"],
        "verify_verdict": live_split_result["verify_verdict"],
        "harness_error_reason": live_split_result["harness_error_reason"],
    }
    return digest(json.dumps(payload, sort_keys=True))


def _apply_live_split_verifier(
    *,
    cli_bin: Path,
    instance_id: str,
    arm: str,
    lineage: str,
    route_domain: str,
    route_scaffold: str,
    tests_status: Optional[dict[str, Any]],
    harness_error_reason: Optional[str],
) -> tuple[dict[str, Any], dict[str, Any], Optional[dict[str, Any]]]:
    """ADR-ECON-003 Decision 2.4 wiring: independently judge this (task, arm, lineage)
    settlement's harness report, then -- unless NOT_ENOUGH_TESTS -- ask `econ_fold_cli` to
    build the fully-hashed `RoutingPriorUpdated` event for the verify-side verdict (never
    recomputed in Python).

    `harness_error_reason` (orchestrator addendum, 2026-07-07, point 3): when set, this
    (task, arm, lineage) settlement never produced a per-instance report.json at all (the
    harness's own `error_ids` bucket), so `judge_harness_error` is used instead of `judge` --
    there is no `tests_status` to independently read.

    Returns `(live_split_result, backup_update, routing_prior_updated_event_or_none)`. The
    caller is responsible for appending the returned event onto its own
    `committed_routing_events` tape (this function has no tape-mutation side effect, to keep
    it a pure-ish, independently testable unit)."""
    if harness_error_reason is not None:
        live_split_result = live_split_verifier.judge_harness_error(harness_error_reason)
    else:
        live_split_result = live_split_verifier.judge(tests_status)

    if live_split_result["not_enough_tests"]:
        # Decision 2.4: "verify 侧为空(测试太少)⇒ NOT_ENOUGH_TESTS,不回灌,计数上报" --
        # no RoutingPriorUpdated event, but the caller still counts this in the verdict JSON.
        backup_update = {"applied": False, "reason": "NOT_ENOUGH_TESTS"}
        return live_split_result, backup_update, None

    attestation_hash = _verifier_attestation_hash(
        instance_id=instance_id, arm=arm, lineage=lineage, live_split_result=live_split_result
    )
    build_response = call_cli(
        cli_bin,
        "build-routing-prior-updated",
        {
            "schema": "econ_fold_cli.build_routing_prior_updated.request.v1",
            "route_domain": route_domain,
            "route_scaffold": route_scaffold,
            "verdict": bool(live_split_result["verify_verdict"]),
            "verdict_source_id": LIVE_SPLIT_VERIFIER_SOURCE_ID,
            "verifier_attestation_hash": attestation_hash,
        },
    )
    event = build_response["event"]
    event_hash = event["RoutingPriorUpdated"]["event_hash"]
    backup_update = {"applied": True, "routing_prior_updated_event_hash": event_hash}
    return live_split_result, backup_update, event


def _settle_one(
    *,
    args: argparse.Namespace,
    packet: dict[str, Any],
    arm: str,
    lineage: str,
    task_dir_root: Path,
    report_root: Path,
    deepseek_native_provider_config: dict[str, Any],
    cli_bin: Path,
    route_domain: str,
    route_scaffold: str,
) -> dict[str, Any]:
    """Dispatch one (arm, lineage) pair for one task, score it if a patch was produced, and
    -- if scoring completed -- independently re-judge the harness's per-test report (WP9b,
    ADR-ECON-003 Decision 2.4). Never fabricates a verdict: `settlement_verdict_resolved`
    and `live_split_verdict` stay `None` unless the real scorer actually completed.

    Market settlement uses `accept_verdict` (Decision 2.4: "accept 裁决(市场结算侧)"),
    **not** the harness's own whole-test-suite `resolved` boolean -- the two differ whenever
    any grading-relevant test lands on the verify side of the held-out split.
    """
    instance_id = packet["instance_id"]
    worker_result = dispatch_worker_for_lineage(
        arm=arm,
        lineage=lineage,
        packet=packet,
        task_dir_root=task_dir_root,
        run_id_prefix="wp9a-live-driver",
        deepseek_native_provider_config=deepseek_native_provider_config,
    )

    scoring_result: dict[str, Any] = {"status": "SKIPPED_NO_PATCH"}
    settlement_verdict: Optional[bool] = None
    live_split_result: Optional[dict[str, Any]] = None
    backup_update: dict[str, Any] = {"applied": False, "reason": "SCORING_NOT_COMPLETED"}
    routing_prior_updated_event: Optional[dict[str, Any]] = None
    if worker_result.get("status") == "COMPLETED":
        provider_path = worker_result.get("provider_path", "siliconflow")
        if provider_path == "deepseek_direct_fallback":
            patch_path = task_dir_root / "deepseek_direct_fallback" / instance_id / "candidate.patch"
        else:
            patch_path = task_dir_root / instance_id / lineage / "candidate.patch"
        model_patch = patch_path.read_text(encoding="utf-8") if patch_path.exists() else ""
        if model_patch.strip():
            scoring_result = score_with_official_harness(
                python_bin=args.scoring_python,
                instance_id=instance_id,
                model_patch=model_patch,
                run_id=f"wp9a-live-driver-{instance_id}-{lineage}",
                report_dir=report_root / instance_id / lineage,
                timeout_s=args.scoring_timeout_s,
            )
            if scoring_result.get("status") == "COMPLETED":
                live_split_result, backup_update, routing_prior_updated_event = _apply_live_split_verifier(
                    cli_bin=cli_bin,
                    instance_id=instance_id,
                    arm=arm,
                    lineage=lineage,
                    route_domain=route_domain,
                    route_scaffold=route_scaffold,
                    tests_status=scoring_result.get("tests_status"),
                    harness_error_reason=scoring_result.get("harness_error_reason"),
                )
                settlement_verdict = live_split_result["accept_verdict"]

    return {
        "lineage": lineage,
        "worker_result_status": worker_result.get("status"),
        "provider_path": worker_result.get("provider_path"),
        "worker_result": {k: v for k, v in worker_result.items() if k != "usage_raw_sha256"},
        "scoring_result": {k: v for k, v in scoring_result.items() if k != "command"},
        "settlement_verdict_resolved": settlement_verdict,
        "live_split_verdict": live_split_result,
        "backup_update": backup_update,
        "_routing_prior_updated_event": routing_prior_updated_event,
    }


def run_driver(args: argparse.Namespace) -> dict[str, Any]:
    cli_bin = args.econ_fold_cli or find_default_cli_bin()
    evidence_class = EVIDENCE_CLASS_SMOKE if args.smoke else EVIDENCE_CLASS_REAL

    packets = load_task_packets()
    if not packets:
        raise SystemExit(f"no task packets found under {SHARD_ROOT}/{TASKS_GLOB}")

    scaffold_ids = derive_scaffold_ids(cli_bin)
    deepseek_native_provider_config = load_provider_config()

    if args.smoke:
        # Deliverable 3: exactly 1 task x 1 winning arm (selected by the fold, tau=0), all 4
        # lineages dispatched for that arm (<= 4 real calls total, <= 1 per lineage) -- the
        # point of the smoke test is to prove every provider path is independently reachable
        # through this driver, not just DeepSeek's (per the lineage-expansion update).
        #
        # NOTE (Decision 2.4 supersession): this used to filter for a task whose *instance_id*
        # landed on the held-out ACCEPT side (`verifier.split.split_side`), because that
        # instance_id-level split used to be the sole accept/verify partition this driver
        # knew about. Decision 2.4 retires that instance_id-level split entirely -- the split
        # now happens per *test_id*, inside `live_split_verifier`, once a real harness report
        # exists (see `_settle_one`) -- so smoke-mode task selection is simply "first task by
        # instance_id": deterministic, but carries no leftover accept/verify meaning.
        packets = sorted(packets, key=lambda p: p["instance_id"])[:1]
        max_tasks = 1
        tau_config = None  # tau=0 argmax-bypass, per --smoke's own contract
        real_call_cap = 4
    else:
        max_tasks = args.max_tasks if args.max_tasks is not None else len(packets)
        tau_config = None  # this driver invocation never runs Stage A; see module doc.
        real_call_cap = None  # caller's responsibility outside --smoke; no batch runs here.

    task_dir_root = args.task_dir_root or (Path(args.out).resolve().parent / "task_runs")
    report_root = args.report_dir or (Path(args.out).resolve().parent / "scoring")

    committed_routing_events: list[dict[str, Any]] = []
    task_results: list[dict[str, Any]] = []
    real_worker_calls = 0
    # E-soundness data source (ADR-ECON-003 Decision 2.3/2.4): counted, never gated on here --
    # a rising canary/round trend is an owner/Veto-AI review signal, not something this driver
    # judges or reacts to.
    not_enough_tests_count = 0
    canary_count = 0
    settled_dispatch_count = 0
    routing_prior_updated_applied_count = 0
    # Per-domain_bucket settlement history for the N_eff/H_lineage estimator (WP5), lineage
    # labels only (module doc's lineage-label discipline). `settlement_index` is shared
    # across lineages settled on the *same* task/round (ADR-ECON-003 Decision 3: "对齐到
    #共同结算索引"), incremented once per task processed, not per lineage.
    diversity_history: dict[str, list[dict[str, Any]]] = {}

    for task_index, packet in enumerate(packets[:max_tasks]):
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
        _instance, selected_arm, selected_lineage = selected_route_id.split("::")

        if args.smoke:
            dispatch_mode = "smoke_all_lineages_for_winning_arm"
            lineages_to_dispatch = list(LINEAGES)
        else:
            dispatch_mode = "single_winner"
            lineages_to_dispatch = [selected_lineage]

        dispatches: list[dict[str, Any]] = []
        for lineage in lineages_to_dispatch:
            if real_call_cap is not None and real_worker_calls >= real_call_cap:
                dispatches.append(
                    {
                        "lineage": lineage,
                        "worker_result_status": "SKIPPED_SPEND_CAP",
                        "provider_path": None,
                        "worker_result": {"status": "SKIPPED_SPEND_CAP"},
                        "scoring_result": {"status": "SKIPPED_NO_PATCH"},
                        "settlement_verdict_resolved": None,
                        "live_split_verdict": None,
                        "backup_update": {"applied": False, "reason": "SKIPPED_SPEND_CAP"},
                    }
                )
                continue
            settled = _settle_one(
                args=args,
                packet=packet,
                arm=selected_arm,
                lineage=lineage,
                task_dir_root=task_dir_root,
                report_root=report_root,
                deepseek_native_provider_config=deepseek_native_provider_config,
                cli_bin=cli_bin,
                route_domain=domain_bucket,
                route_scaffold=scaffold_ids[selected_arm][lineage],
            )
            if settled["worker_result_status"] == "COMPLETED":
                real_worker_calls += 1

            # Decision 2.4 backup-update wiring: feed the independent verifier's
            # RoutingPriorUpdated event (if one was built) back onto the tape this same
            # driver run folds over for every subsequent task's selection -- this is the
            # live "回灌" (feedback) WP9a lacked entirely.
            routing_prior_updated_event = settled.pop("_routing_prior_updated_event", None)
            if routing_prior_updated_event is not None:
                committed_routing_events.append(routing_prior_updated_event)
                routing_prior_updated_applied_count += 1
            dispatches.append(settled)

            live_split_verdict = settled.get("live_split_verdict")
            if live_split_verdict is not None:
                settled_dispatch_count += 1
                not_enough_tests_count += int(live_split_verdict["not_enough_tests"])
                canary_count += int(live_split_verdict["canary"])

            if settled["settlement_verdict_resolved"] is not None:
                diversity_history.setdefault(domain_bucket, []).append(
                    {
                        "lineage_id": lineage,
                        "settlement_index": task_index,
                        "verdict": bool(settled["settlement_verdict_resolved"]),
                    }
                )

        task_results.append(
            {
                "instance_id": instance_id,
                "domain_bucket": domain_bucket,
                "selected_route_id": selected_route_id,
                "selected_arm": selected_arm,
                "selected_lineage": selected_lineage,
                "dispatch_mode": dispatch_mode,
                "budget_suggestion": selection["budget_suggestion"],
                "dispatches": dispatches,
                "evidence_class": evidence_class,
            }
        )

    diversity_metrics_by_bucket: dict[str, Any] = {}
    for bucket, history in diversity_history.items():
        diversity_metrics_by_bucket[bucket] = diversity_metrics_for_history(cli_bin, history)

    verdict = {
        "schema": DRIVER_SCHEMA,
        "evidence_class": evidence_class,
        "mode": "smoke" if args.smoke else "full",
        "worker_lineages": list(LINEAGES),
        "arm_descriptors": {arm: spec["decomposition_kind"] for arm, spec in ARM_DESCRIPTORS.items()},
        "scaffold_ids": scaffold_ids,
        "real_worker_calls_made": real_worker_calls,
        "real_worker_calls_cap": real_call_cap,
        "task_count": len(task_results),
        "tasks": task_results,
        "diversity_metrics_by_domain_bucket": diversity_metrics_by_bucket,
        # ADR-ECON-003 Decision 2.4 live-verifier summary (E-soundness data source): counts
        # only, never a τ/λ/floor value (Art III.4/F4) -- see `gate_f4_econ_leakage.sh`.
        "verifier_summary": {
            "schema": "econ_lab.live_split_verifier.summary.v1",
            "settled_dispatch_count": settled_dispatch_count,
            "not_enough_tests_count": not_enough_tests_count,
            "canary_count": canary_count,
            "routing_prior_updated_applied_count": routing_prior_updated_applied_count,
        },
        "generated_at_unix": int(time.time()),
    }
    return verdict


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--smoke", action="store_true", help="1 task x 1 winning arm x all 4 lineages, tau=0, <=4 real worker calls"
    )
    parser.add_argument("--max-tasks", type=int, default=None, help="only used outside --smoke")
    parser.add_argument("--out", type=Path, required=True, help="verdict JSON output path")
    parser.add_argument("--econ-fold-cli", type=Path, default=None)
    parser.add_argument(
        "--scoring-python",
        default=sys.executable,
        help="python interpreter with a working `swebench` package (numpy<2-ABI compatible; "
        "the real evaluation environment's own interpreter is "
        "~/.turingos/swebench-venv/bin/python -- the system python's swebench import is "
        "broken in that environment; see module doc's environment note)",
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
