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
import os
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
# WP-H2 (ADR-ECON-007 Decision 1/2/3): loop-detector + diagnostic-injection/rollback hook,
# gated end-to-end by `--monitor` (default off -- see `run_driver`'s own "monitor_enabled"
# block and its docstring note there). A bare import is a static, side-effect-free binding
# and therefore never itself perturbs a byte of `--monitor`-absent output.
from monitor import interventions as monitor_interventions  # noqa: E402
from monitor import loop_detector as monitor_loop_detector  # noqa: E402
# WP-H3 (ADR-ECON-007 Decision 4): verification-gated termination guard +
# route-falsification report, invoked only where WP-H2's own rollback remedy is
# already exhausted (`RollbackCapExceededError`, that module's own documented
# extension point) -- see `run_driver`'s "monitor_enabled" block below and
# `monitor/termination.py`'s module docstring for the full hook-placement note.
from monitor import termination as monitor_termination  # noqa: E402

SHARD_ROOT = REPO_ROOT / "evidence/bench/swe_bench_verified_500_campaign_20260629/shards/S01"
# Shard-name-agnostic (Stage B', `--task-shard`, ADR-ECON-003 Decision 7.6): `shard_root`
# itself already scopes the glob to one shard (S01 by default, S02 under `--task-shard`) --
# the "S01"/"S02" prefix inside each ipqc window directory name (e.g. `S01-W00`, `S02-W00`)
# is redundant given that scoping, so this pattern matches either shard's own window-directory
# naming instead of being hardcoded to S01's. Behavior-identical for the default S01 case (the
# exact same files match) -- previously `ipqc/S01-W*/...`, which silently matched zero files
# under any other shard root (the bug `--task-shard` would otherwise hit).
TASKS_GLOB = "ipqc/*-W*/worker_safe_tasks/*/task_packet.json"

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
    try:
        proc = subprocess.run(
            [str(cli_bin), subcommand],
            input=json.dumps(request).encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
    except subprocess.TimeoutExpired as error:
        # Same failure contract as the nonzero-exit branch below (a RuntimeError naming the
        # subcommand), so callers never see a raw TimeoutExpired leak out of this bridge.
        raise RuntimeError(
            f"econ_fold_cli {subcommand} failed (timed out after {error.timeout}s)"
        ) from error
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


# ---------------------------------------------------------------------------
# Stage B' warm-start priors (ADR-ECON-003 Decision 6.1/7.6, PREREG Appendix A amendment #4,
# `--priors`) -- offline JSON load only, no formula invented: the P-injection semantics
# (first-appearance freeze, P=0.5 default for a missing route) live entirely in the
# pre-existing Rust `initial_prices` fold plumbing (`fold_and_select` above /
# `crates/turing-economy/src/bin/econ_fold_cli.rs::q_eff_for_key`); this section only turns a
# priors file into that request field's shape.
# ---------------------------------------------------------------------------

#: Q32.32 fixed-point unit, mirrored from `crates/turing-economy/src/routing_fold.rs::Q32_ONE`
#: (ADR-ECON-003 Decision 4: "全程 Q32.32 定点"). Encoding-only constant (matches this file's
#: pre-existing `--tau` mantissa conversion below) -- not a re-derivation of any economic
#: formula.
_Q32_ONE = 1 << 32


def load_stage_b_prime_priors(priors_path: Path) -> tuple[dict[str, float], str]:
    """Load a Stage B' warm-start priors file. Accepts both the pinned
    `econ_lab.stage_b_prime_priors.v1` shape (`tools/econ_lab/analysis/
    gen_stage_b_priors.py`'s own output, `{"priors": {"<arm>::<lineage>": p, ...}, ...}`) and a
    bare `{"<arm>::<lineage>": p, ...}` mapping (this flag's own documented contract) -- never
    guessed beyond these two shapes. Returns `(priors_map, file_sha256_hex)`; the sha256 is
    computed over the raw file bytes (before JSON parsing) so it is exactly reproducible by an
    independent `sha256sum` of the same path (migration/provenance evidence, ADR-ECON-003
    Decision 7.6: "注入文件的 sha256 与生成脚本必须 pin 入预注册")."""
    raw_bytes = priors_path.read_bytes()
    file_sha256 = sha256_hex(raw_bytes)
    parsed = json.loads(raw_bytes.decode("utf-8"))
    if isinstance(parsed, dict) and "priors" in parsed and isinstance(parsed["priors"], dict):
        priors_map = parsed["priors"]
    elif isinstance(parsed, dict):
        priors_map = parsed
    else:
        raise ValueError(f"--priors file {priors_path} must be a JSON object")
    return {str(k): float(v) for k, v in priors_map.items()}, file_sha256


def _p_float_to_q32_mantissa_decimal(p: float) -> str:
    """`p` (a `[0, 1]` probability) -> its Q32.32 fixed-point mantissa as a decimal-literal
    string (the exact wire shape `econ_fold_cli`'s `InitialPriceInput.p_q32` parses -- JSON
    numbers cannot losslessly carry the i128 range, same rationale as the Rust struct's own
    doc comment). Clamped to `[0, 1]` first (Decision 6.1: "clamp 到 [0,1]"); truncated toward
    zero on the fixed-point scale (Decision 4's rounding convention throughout this file,
    e.g. the pre-existing `--tau` mantissa conversion below)."""
    clamped = max(0.0, min(1.0, p))
    return str(int(clamped * _Q32_ONE))


def stage_b_prime_initial_prices(
    priors_map: dict[str, float],
    *,
    domain_bucket: str,
    scaffold_ids: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    """One `initial_prices` entry per (arm, lineage) route named in `priors_map`, for the
    *current task's* `domain_bucket` (a route's warm-start P applies at every domain_bucket it
    is encountered under -- `scaffold_id` alone, not `(domain_bucket, scaffold_id)`, is the
    priors file's own key granularity, per this flag's documented contract). A route absent
    from `priors_map` is simply omitted here -- the CLI's own `q_eff_for_key` fallback already
    applies `P = 0.5` to any `(domain_bucket, scaffold_id)` key with no `initial_prices` entry
    and no fold history, so "文件缺路由 ⇒ 该路由 P=0.5" needs no explicit entry from this side."""
    entries: list[dict[str, Any]] = []
    for arm in ARM_DESCRIPTORS:
        for lineage in LINEAGES:
            label = _scaffold_label(arm, lineage)
            if label not in priors_map:
                continue
            entries.append(
                {
                    "domain_bucket": domain_bucket,
                    "scaffold_id": scaffold_ids[arm][lineage],
                    "p_q32": _p_float_to_q32_mantissa_decimal(priors_map[label]),
                }
            )
    return entries


def fold_and_select(
    cli_bin: Path,
    *,
    committed_routing_events: list[dict[str, Any]],
    domain_bucket: str,
    scaffold_ids: dict[str, dict[str, str]],
    instance_id: str,
    tau_config: Optional[dict[str, int]],
    initial_prices: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Routes over the full 4-lineage x 3-scaffold = 12-candidate space (PREREG Appendix A
    lineage-expansion update).

    `initial_prices` (Stage B' warm-start P, ADR-ECON-003 Decision 6.1/7.6, PREREG Appendix A
    amendment #4): the pre-existing `econ_fold_cli.fold_and_suggest.request.v2` `initial_prices`
    field, previously always sent empty (`[]`) by this driver. Each entry seeds one
    `(domain_bucket, scaffold_id)` node's `P` for its *first* appearance in the fold (Decision
    6.1: "P 在节点首次创建时定格") -- no new Rust plumbing, this is the same field
    `run_fold_and_suggest` in `econ_fold_cli.rs` already reads. `None`/empty is
    behavior-identical to the pre-Stage-B' call (every key falls back to the CLI's own
    `P = 0.5` uninformative-prior default)."""
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
    # trigger_event_hash (ADR-ECON-003 Decision 4, B1 remedy -- the seed's pinned fourth
    # input): the identity digest of the event that triggered this routing decision. In this
    # driver the trigger is the arrival of one worker-safe task packet, and `instance_id` is
    # that packet's committed identity (unique per routing decision: `fold_and_select` runs
    # at most once per instance per run; resume replays the checkpoint instead of re-routing).
    # Deterministic and replayable: derived only from the committed packet identity, never
    # from wall-clock/live-random -- same discipline as the two hashes above. The ADR pins
    # the seed formula, not a derivation for this digest; the WP7 fixture harness likewise
    # carries a per-trial `trigger_event_hash` (tools/econ_lab/fixtures/
    # generate_self_test_stream.py), which this per-task derivation mirrors for the live run.
    # NOTE: `price_signal_hash`'s tape-fingerprint embedding above predates B1 and stays
    # untouched (removing it would alter more preregistered behavior than B1 authorizes).
    trigger_event_hash = digest("trigger-event.v1:" + instance_id)

    if tau_config is None:
        router_mode = {"kind": "SoftmaxArgmaxBypass"}
    elif tau_config.get("kind") == "uniform":
        router_mode = {"kind": "SoftmaxUniform"}
    else:
        router_mode = {"kind": "SoftmaxFinite", "tau_q32_mantissa": tau_config["tau_hi_q32_mantissa"]}

    response = call_cli(
        cli_bin,
        "fold-and-suggest",
        {
            # v2: adds the required `trigger_event_hash` (B1 remedy; see the CLI's own
            # schema-version note in econ_fold_cli.rs `run_fold_and_suggest`).
            "schema": "econ_fold_cli.fold_and_suggest.request.v2",
            "committed_routing_events": committed_routing_events,
            "initial_prices": initial_prices or [],
            "candidate_routes": candidate_routes,
            "price_signal_hash": price_signal_hash,
            "pput_prior_hash": pput_prior_hash,
            "trigger_event_hash": trigger_event_hash,
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


def load_stream_manifest(manifest_path: Path) -> tuple[list[str], str]:
    """Load a P3-E3 (or generic) ordered instance_id stream manifest.

    Accepts either:
      {"schema": "...", "instance_ids": ["id1", ...], ...}
      ["id1", "id2", ...]  (bare list)

    Returns (instance_ids_in_order, file_sha256_hex). Order is authoritative for
    the evaluation stream when --stream-manifest is set; load_task_packets' glob
    sort is overridden by this order (missing ids are rejected).
    """
    raw_bytes = manifest_path.read_bytes()
    file_sha256 = sha256_hex(raw_bytes)
    parsed = json.loads(raw_bytes.decode("utf-8"))
    if isinstance(parsed, dict) and isinstance(parsed.get("instance_ids"), list):
        ids = [str(x) for x in parsed["instance_ids"]]
    elif isinstance(parsed, list):
        ids = [str(x) for x in parsed]
    else:
        raise ValueError(
            f"--stream-manifest {manifest_path} must be a JSON object with "
            f"'instance_ids' list or a bare list of instance_id strings"
        )
    if not ids:
        raise ValueError(f"--stream-manifest {manifest_path} has empty instance_ids")
    if len(ids) != len(set(ids)):
        raise ValueError(f"--stream-manifest {manifest_path} contains duplicate instance_ids")
    return ids, file_sha256


def order_packets_by_stream_manifest(
    packets: list[dict[str, Any]], instance_ids: list[str]
) -> list[dict[str, Any]]:
    """Reorder/filter loaded packets to match the stream manifest order exactly."""
    by_id = {p["instance_id"]: p for p in packets}
    missing = [iid for iid in instance_ids if iid not in by_id]
    if missing:
        raise SystemExit(
            f"--stream-manifest references {len(missing)} instance_id(s) not found "
            f"under the task shard (first missing: {missing[0]})"
        )
    return [by_id[iid] for iid in instance_ids]


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


def load_provider_config() -> Optional[dict[str, Any]]:
    """DeepSeek-direct's own non-secret config (the fallback path's native adapter).

    Returns `None` when `~/.turingos/provider-profiles.json` does not exist at all (an
    environment with no DeepSeek-direct fallback configured): the deepseek lineage's
    SiliconFlow-primary path is unaffected, and `dispatch_worker_for_lineage` below reports
    the fallback dispatch as NOT_RUN with a "provider config missing" detail instead of the
    whole driver crashing at startup. When the file exists, behavior is unchanged byte for
    byte (including the stores_api_key_values refusal)."""
    profile_path = Path.home() / ".turingos" / "provider-profiles.json"
    try:
        profile_text = profile_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    data = json.loads(profile_text)
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
    diagnostic_prefix: Optional[str] = None,
) -> dict[str, Any]:
    """DeepSeek-direct native adapter (deepseek lineage's fallback path).

    `diagnostic_prefix` (WP-H2, ADR-ECON-007 Decision 1/3, `--monitor` only): a
    Decision-3-legal `interventions.Diagnostic.text` string to inject into this
    dispatch's worker-visible context, written to an on-disk
    `diagnostic_context.md` sibling and threaded through
    `run_one_task`'s pre-existing `extra_context_file` plumbing point (never a new
    mechanism -- this reuses the same field the DeepSeek-direct path already exposes
    for `--broadcast-rules`-adjacent extra context). `None` (the default, and the only
    value any pre-WP-H2 call site ever passed) is fully behavior-identical to before
    this parameter existed.
    """
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

    extra_context_file = None
    if diagnostic_prefix:
        diagnostic_context_path = task_dir_root / instance_id / "diagnostic_context.md"
        diagnostic_context_path.parent.mkdir(parents=True, exist_ok=True)
        diagnostic_context_path.write_text(diagnostic_prefix, encoding="utf-8")
        extra_context_file = diagnostic_context_path

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
            extra_context_file=extra_context_file,
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
    diagnostic_prefix: Optional[str] = None,
) -> dict[str, Any]:
    """Generic OpenAI-compatible dispatch (SiliconFlow primary path for all 4 lineages).

    `diagnostic_prefix` (WP-H2, ADR-ECON-007 Decision 1/3, `--monitor` only): when set,
    a Decision-3-legal `interventions.Diagnostic.text` string prepended (as its own
    markdown section) to the worker-visible capsule text before dispatch -- "注入诊断
    到下一次 worker 上下文". `None` (the default, and the only value any pre-WP-H2 call
    site ever passed) is fully behavior-identical to before this parameter existed.
    """
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
        if diagnostic_prefix:
            capsule_text = (
                "## Prior-step diagnostic (external loop detector)\n\n"
                f"{diagnostic_prefix}\n\n---\n\n" + capsule_text
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
    deepseek_native_provider_config: Optional[dict[str, Any]],
    diagnostic_prefix: Optional[str] = None,
) -> dict[str, Any]:
    """Dispatch one (arm, lineage) pair, applying the deepseek-only SiliconFlow-primary /
    DeepSeek-direct-fallback rule (PREREG Appendix A, frozen; see module doc's fallback-
    trigger note for the exact condition this driver uses). A `None`
    `deepseek_native_provider_config` (no `~/.turingos/provider-profiles.json` on this
    machine -- see `load_provider_config`) makes the fallback leg NOT_RUN with a
    "provider config missing" detail; the SiliconFlow-primary leg is unaffected.

    `diagnostic_prefix` (WP-H2, `--monitor` only, default `None`): forwarded verbatim to
    both the SiliconFlow-primary and DeepSeek-direct-fallback dispatch calls below -- see
    each of their own docstrings for how it is injected. `None` is behavior-identical to
    before this parameter existed."""
    primary_result = dispatch_via_siliconflow(
        arm=arm, lineage=lineage, packet=packet, task_dir_root=task_dir_root, diagnostic_prefix=diagnostic_prefix
    )
    if (
        lineage == "deepseek"
        and LINEAGE_CONFIGS[lineage]["has_native_fallback"]
        and primary_result["status"] in ("NOT_RUN", "ERROR", "API_ERROR")
    ):
        if deepseek_native_provider_config is None:
            return {
                "status": "NOT_RUN",
                "detail": "provider config missing (~/.turingos/provider-profiles.json not found)",
                "instance_id": packet["instance_id"],
                "arm": arm,
                "lineage": lineage,
                "provider_path": "deepseek_direct_fallback",
                "primary_attempt_status": primary_result["status"],
            }
        fallback_result = dispatch_worker(
            arm=arm,
            packet=packet,
            provider_config=deepseek_native_provider_config,
            task_dir_root=task_dir_root / "deepseek_direct_fallback",
            run_id_prefix=run_id_prefix,
            diagnostic_prefix=diagnostic_prefix,
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


def _read_scoring_report(
    *,
    report_dir: Path,
    run_id: str,
    instance_id: str,
    model_name: str = "wp9a-live-driver",
) -> Optional[dict[str, Any]]:
    """Pure read-back of an already-completed `score_with_official_harness` run's on-disk
    artifacts -- no subprocess, no mutation. Returns `None` when the aggregated report file
    does not exist yet (the caller's cue that the harness must actually be run first, or run
    again). Factored out of `score_with_official_harness` (WP9c) so the fresh path and the
    resume "评分产物在 -> 复用报告重算裁决" path (`--resume`, ADR-ECON-003 Decision 2.4 wiring
    unaffected) share one reader and can never disagree on how a report is interpreted --
    this refactor changes `score_with_official_harness`'s call shape, not its output, so
    fresh-run verdicts are unaffected (see `tests/test_live_driver_head_parity.py`)."""
    report_path = report_dir / f"{model_name}.{run_id}.json"
    if not report_path.exists():
        return None
    # Aggregated report, schema_version 2 (see this module's WP9b orchestrator addendum doc
    # comment above): per-outcome instance_id lists, not a `{instance_id: {...}}` mapping.
    try:
        aggregated_report = json.loads(report_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # A truncated/unreadable aggregated report (e.g. a killed run's partial write) is
        # treated exactly like a missing one: the caller's cue that the harness must be run
        # (again) -- never a crash, and never a fabricated verdict from partial bytes.
        return None
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

    # B2 remedy (independent audit B2, ADR-ECON-003 Decision 7.1, 2026-07-08 orchestrator
    # ruling): distinguish "the harness actually determined a failure" (a real double-fail,
    # `harness_error_reason` set -- `patch_apply_failed`/`empty_patch`) from "the harness
    # never actually evaluated this run at all" (`infra_null_reason` set -- `incomplete`, or
    # an ERROR-bucket outcome with no pinned patch-apply-failure marker, i.e. the per-instance
    # report/log was malformed or never written). Only the latter is new behavior; RESOLVED/
    # UNRESOLVED are untouched.
    tests_status: Optional[dict[str, Any]] = None
    harness_error_reason: Optional[str] = None
    infra_null_reason: Optional[str] = None
    if outcome in ("RESOLVED", "UNRESOLVED"):
        tests_status = _read_per_instance_tests_status(instance_dir, instance_id)
    elif outcome == "INCOMPLETE":
        # The harness's own bucket for "never actually finished evaluating this instance" --
        # a fabricated FAIL here was exactly B2's bug.
        infra_null_reason = "incomplete"
    elif outcome == "EMPTY_PATCH":
        # The harness's *own* empty-patch classification (distinct from this driver's
        # SKIPPED_NO_PATCH short-circuit in `_settle_one`, which never reaches the harness at
        # all -- see B3). This is a real harness-side determination, same "legit fail"
        # treatment as `patch_apply_failed`, not infra_null.
        harness_error_reason = "empty_patch"
    else:  # ERROR
        reason = _classify_harness_error_reason(instance_dir)
        if reason == "patch_apply_failed":
            harness_error_reason = reason
        else:
            # No per-instance report/log at all and no pinned patch-apply-failure marker --
            # the harness never actually evaluated this instance (report malformed/never
            # written). B2: infra_null, not a fabricated FAIL.
            infra_null_reason = "harness_error_no_report"

    result = {
        "status": "COMPLETED",
        "outcome": outcome,
        # Kept for back-compat/diagnostics only: this is the harness's own whole-test-suite
        # verdict, no longer what market settlement uses (Decision 2.4: settlement uses
        # `live_split_verdict.accept_verdict`, computed independently by `_settle_one` below).
        "resolved": outcome == "RESOLVED",
        "tests_status": tests_status,
        "harness_error_reason": harness_error_reason,
        "report_path": str(report_path),
        "log_path": str(report_dir / "run_evaluation.log"),
        "raw_report": aggregated_report,
    }
    if infra_null_reason is not None:
        # Deliberately omitted (not set to `None`) on every other outcome: the happy-path
        # (RESOLVED/UNRESOLVED/EMPTY_PATCH/patch_apply_failed) return shape is byte-identical
        # to the pre-B2 shape, so this is additive-only.
        result["infra_null_reason"] = infra_null_reason
    return result


# B6 remedy (independent audit B6, ADR-ECON-003 Decision 7.5, 2026-07-08 orchestrator
# ruling): "评分成功即写 SCORING_OK.marker(内容=报告 sha256);resume 仅在 marker 校验通过时
# 信任盘上报告,否则重评分" -- eliminates the residual resume gap where a fresh run that ends
# with scoring rc!=0 *after* the harness partially wrote a report returns SCORING_FAILED (no
# settlement), but a later `--resume` treated the on-disk report as COMPLETED regardless (the
# report's mere *existence* was the only signal `_read_scoring_report` ever checked). The
# marker is written only from the one call site below where `_read_scoring_report` already
# returned a COMPLETED result for a *successful* (`returncode == 0`) harness run -- never on
# the SCORING_FAILED path -- so its presence is a positive attestation "this exact report was
# produced by a run this driver itself judged successful", not just "a file exists".
SCORING_OK_MARKER_FILENAME = "SCORING_OK.marker"
MODEL_NAME = "wp9a-live-driver"


def _scoring_ok_marker_path(report_dir: Path) -> Path:
    return report_dir / SCORING_OK_MARKER_FILENAME


def _aggregated_report_path(report_dir: Path, *, run_id: str, model_name: str = MODEL_NAME) -> Path:
    return report_dir / f"{model_name}.{run_id}.json"


def _write_scoring_ok_marker(report_dir: Path, report_path: Path) -> None:
    """Atomic write (same tmp+`os.replace` discipline as `_write_settlement_checkpoint`):
    content is the aggregated report file's own sha256 hex digest, so a later reader can
    cheaply verify the marker still describes the report bytes actually on disk (not just
    that a marker file happens to exist)."""
    marker_path = _scoring_ok_marker_path(report_dir)
    digest_hex = sha256_hex(report_path.read_bytes())
    tmp_path = marker_path.with_name(marker_path.name + ".tmp")
    tmp_path.write_text(digest_hex + "\n", encoding="utf-8")
    os.replace(tmp_path, marker_path)


def _scoring_ok_marker_valid(*, report_dir: Path, report_path: Path) -> bool:
    """`True` only if `SCORING_OK.marker` exists *and* its recorded sha256 matches the
    aggregated report file currently on disk -- both conditions absent/mismatched degrade to
    `False` (never a crash), the resume caller's cue to re-score rather than trust the report."""
    marker_path = _scoring_ok_marker_path(report_dir)
    try:
        marker_text = marker_path.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    try:
        report_bytes = report_path.read_bytes()
    except OSError:
        return False
    return marker_text == sha256_hex(report_bytes)


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
    model_name = MODEL_NAME
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

    report_path = _aggregated_report_path(report_dir, run_id=run_id, model_name=model_name)
    if proc.returncode != 0 or not report_path.exists():
        return {
            "status": "SCORING_FAILED",
            "command": command,
            "returncode": proc.returncode,
            "log_path": str(log_path),
        }
    scoring_result = _read_scoring_report(
        report_dir=report_dir, run_id=run_id, instance_id=instance_id, model_name=model_name
    )
    if scoring_result is None:
        # report_path.exists() was just checked above, so `None` here means the report file
        # exists but is unreadable/truncated -- same SCORING_FAILED contract as a harness
        # that produced no report at all (never a fabricated verdict).
        return {
            "status": "SCORING_FAILED",
            "command": command,
            "returncode": proc.returncode,
            "log_path": str(log_path),
        }
    # B6: this is the *only* call site that writes SCORING_OK.marker -- exactly the point
    # where this function itself has just confirmed (`returncode == 0` above, plus a
    # successfully-read-back `scoring_result`) that this report was produced by a run this
    # driver judged successful. A future `--resume` may only trust an on-disk report when this
    # marker validates against it (`_scoring_ok_marker_valid`); a report left behind by a run
    # that hit SCORING_FAILED never gets a marker, closing the fresh/resume divergence.
    _write_scoring_ok_marker(report_dir, report_path)
    return scoring_result


# ---------------------------------------------------------------------------
# Main per-task loop
# ---------------------------------------------------------------------------

# Opaque verifier-instance identifier (ADR-ECON-003 Decision 2.2: structurally separate from
# the accept predicate; carries no formula/threshold value, only labels which independent
# reading script produced the verdict).
LIVE_SPLIT_VERIFIER_SOURCE_ID = "verifier:live_split_verifier.v1"


def _verifier_attestation_hash(
    *,
    instance_id: str,
    arm: str,
    lineage: str,
    live_split_result: dict[str, Any],
    run_label: str,
    task_index: int,
) -> str:
    """`sha256:`-prefixed 64-hex attestation digest over exactly what the independent
    verifier read (the verify-side test_id set and its own verdict, or the harness-error
    reason when there was no per-test data at all) -- not a re-derivation of any
    routing/selection formula, just an evidence digest so a later audit can recompute and
    check it against the same fixed inputs (Art 0.2 style discipline).

    `run_label`/`task_index` (B5 remedy: independent audit B5, ADR-ECON-003 Decision 7.4,
    2026-07-08 orchestrator ruling): `routing_prior_event_hash`'s pinned identity formula
    (`crates/turing-economy/src/lib.rs::routing_prior_event_hash`) is *not* touched --
    uniqueness is this caller's own contract instead. Without these two fields, a legitimately
    repeated byte-identical re-attestation (same instance/arm/lineage/verdict/test_ids, e.g. a
    resume that re-scores the same instance and reaches the same outcome) collides on
    `event_hash` and hard-errors the whole fold (`RoutingFoldDuplicateEventHash`) instead of
    counting a second, distinct observation. `task_index` is the driver's own per-task loop
    counter (`run_driver`'s `enumerate(...)`); `run_label` is a per-invocation identifier the
    caller supplies (`--run-label`, defaulting to the `--out` path -- see `main()`) so two
    different driver invocations over the same task/arm/lineage (e.g. two Stage B' arms, or a
    genuine independent rerun) never collide either, even at the same `task_index`."""
    payload = {
        "schema": "live_split_verifier.attestation.v1",
        "instance_id": instance_id,
        "arm": arm,
        "lineage": lineage,
        "verify_test_ids": live_split_result["verify_test_ids"],
        "verify_verdict": live_split_result["verify_verdict"],
        "harness_error_reason": live_split_result["harness_error_reason"],
        "run_label": run_label,
        "task_index": task_index,
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
    infra_null_reason: Optional[str] = None,
    run_label: str = "",
    task_index: int = 0,
    fractional_reward: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], Optional[dict[str, Any]]]:
    """ADR-ECON-003 Decision 2.4 wiring: independently judge this (task, arm, lineage)
    settlement's harness report, then -- unless NOT_ENOUGH_TESTS/infra_null -- ask
    `econ_fold_cli` to build the fully-hashed `RoutingPriorUpdated` event for the verify-side
    verdict (never recomputed in Python).

    `harness_error_reason` (orchestrator addendum, 2026-07-07, point 3): when set, this
    (task, arm, lineage) settlement never produced a per-instance report.json at all (the
    harness's own `error_ids` bucket), so `judge_harness_error` is used instead of `judge` --
    there is no `tests_status` to independently read.

    `infra_null_reason` (B2 remedy, ADR-ECON-003 Decision 7.1, 2026-07-08): when set, the
    harness never actually evaluated this run at all -- `judge_infra_null` is used, and this
    function returns without calling `econ_fold_cli` at all (no fabricated verdict, no
    settlement, no backup update, exactly the `NOT_ENOUGH_TESTS` branch's own "withhold, don't
    invent" shape). Mutually exclusive with `harness_error_reason` by construction of this
    function's only caller (`_read_scoring_report` never sets both).

    `run_label`/`task_index` (B5 remedy, ADR-ECON-003 Decision 7.4): folded into the
    attestation hash so a legitimately repeated (instance, arm, lineage, verdict) observation
    across different invocations/tasks never collides on `event_hash` -- see
    `_verifier_attestation_hash`'s own docstring.

    Returns `(live_split_result, backup_update, routing_prior_updated_event_or_none)`. The
    caller is responsible for appending the returned event onto its own
    `committed_routing_events` tape (this function has no tape-mutation side effect, to keep
    it a pure-ish, independently testable unit)."""
    if infra_null_reason is not None:
        live_split_result = live_split_verifier.judge_infra_null(infra_null_reason)
        backup_update = {"applied": False, "reason": f"INFRA_NULL:{infra_null_reason}"}
        return live_split_result, backup_update, None

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
        instance_id=instance_id,
        arm=arm,
        lineage=lineage,
        live_split_result=live_split_result,
        run_label=run_label,
        task_index=task_index,
    )
    # ADR-ECON-006: fractional verify reward. Q32.32 mantissa = floor(v * 2^32), same
    # truncation as --tau / Decision 4. Binary path omits the field (byte-identical event).
    build_req: dict[str, Any] = {
        "schema": "econ_fold_cli.build_routing_prior_updated.request.v1",
        "route_domain": route_domain,
        "route_scaffold": route_scaffold,
        "verdict": bool(live_split_result["verify_verdict"]),
        "verdict_source_id": LIVE_SPLIT_VERIFIER_SOURCE_ID,
        "verifier_attestation_hash": attestation_hash,
    }
    if fractional_reward:
        frac = live_split_result.get("verify_pass_fraction")
        if frac is None:
            # not_enough_tests already returned above; harness_error uses 0.0.
            frac = 0.0
        frac = max(0.0, min(1.0, float(frac)))
        build_req["verdict_fraction_q32"] = str(int(frac * (1 << 32)))
    build_response = call_cli(
        cli_bin,
        "build-routing-prior-updated",
        build_req,
    )
    event = build_response["event"]
    event_hash = event["RoutingPriorUpdated"]["event_hash"]
    backup_update = {
        "applied": True,
        "routing_prior_updated_event_hash": event_hash,
        "fractional_reward": fractional_reward,
        "verdict_fraction_q32": build_req.get("verdict_fraction_q32"),
    }
    return live_split_result, backup_update, event


#: B3 remedy (independent audit B3, ADR-ECON-003 Decision 7.2, 2026-07-08 orchestrator
#: ruling): `harness_error_reason` passed to `_apply_live_split_verifier` for a worker that
#: completed but produced an empty/whitespace-only patch -- SWE-bench semantics: an empty
#: patch is a failed task, never "not evaluated". Distinct string from the harness's own
#: `"empty_patch"` outcome (B2) for provenance: this case never reaches the harness at all.
EMPTY_PATCH_WORKER_OUTPUT_REASON = "empty_patch_worker_output"


def _settle_one(
    *,
    args: argparse.Namespace,
    packet: dict[str, Any],
    arm: str,
    lineage: str,
    task_dir_root: Path,
    report_root: Path,
    deepseek_native_provider_config: Optional[dict[str, Any]],
    cli_bin: Path,
    route_domain: str,
    route_scaffold: str,
    run_label: str = "",
    task_index: int = 0,
    diagnostic_prefix: Optional[str] = None,
    monitor_enabled: bool = False,
) -> dict[str, Any]:
    """Dispatch one (arm, lineage) pair for one task, score it if a patch was produced, and
    -- if scoring completed -- independently re-judge the harness's per-test report (WP9b,
    ADR-ECON-003 Decision 2.4). Never fabricates a verdict: `settlement_verdict_resolved`
    and `live_split_verdict` stay `None` unless the real scorer actually completed, *or* the
    worker's own output was determinate (B3: an empty patch is itself a determinate outcome
    under SWE-bench semantics, scored without ever invoking the harness).

    Market settlement uses `accept_verdict` (Decision 2.4: "accept 裁决(市场结算侧)"),
    **not** the harness's own whole-test-suite `resolved` boolean -- the two differ whenever
    any grading-relevant test lands on the verify side of the held-out split.

    `diagnostic_prefix` / `monitor_enabled` (WP-H2, `--monitor` only, both default to the
    pre-WP-H2 "off" values): forwarded to `dispatch_worker_for_lineage` -- see that
    function's own docstring. The `diagnostic_prefix` kwarg is only ever passed down to
    `dispatch_worker_for_lineage` when `monitor_enabled` is `True` (mirroring `--monitor`
    itself); when `monitor_enabled` is `False` (its default, and the value on every
    pre-WP-H2 call site) the kwarg is *not passed at all* -- not merely passed as `None`
    -- so any caller-supplied replacement of `dispatch_worker_for_lineage` (e.g. a test
    monkeypatch or stub) that predates this parameter and does not accept it keeps
    working unchanged. This is behavior-identical to before this parameter existed.
    """
    instance_id = packet["instance_id"]
    dispatch_kwargs: dict[str, Any] = {
        "arm": arm,
        "lineage": lineage,
        "packet": packet,
        "task_dir_root": task_dir_root,
        "run_id_prefix": "wp9a-live-driver",
        "deepseek_native_provider_config": deepseek_native_provider_config,
    }
    if monitor_enabled:
        dispatch_kwargs["diagnostic_prefix"] = diagnostic_prefix
    worker_result = dispatch_worker_for_lineage(**dispatch_kwargs)

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
                    infra_null_reason=scoring_result.get("infra_null_reason"),
                    run_label=run_label,
                    task_index=task_index,
                    fractional_reward=bool(getattr(args, "fractional_reward", False)),
                )
                settlement_verdict = live_split_result["accept_verdict"]
        else:
            # B3: worker COMPLETED but the patch is empty/whitespace-only -- under SWE-bench
            # semantics this is a *determinate task failure*, never "not evaluated": settle
            # FAIL, verify FAIL, no canary, normal feedback v=0, counted in the denominator
            # (never funneled into infra_null). The harness is never invoked for this case
            # (there is nothing for it to apply/run).
            live_split_result, backup_update, routing_prior_updated_event = _apply_live_split_verifier(
                cli_bin=cli_bin,
                instance_id=instance_id,
                arm=arm,
                lineage=lineage,
                route_domain=route_domain,
                route_scaffold=route_scaffold,
                tests_status=None,
                harness_error_reason=EMPTY_PATCH_WORKER_OUTPUT_REASON,
                run_label=run_label,
                task_index=task_index,
                fractional_reward=bool(getattr(args, "fractional_reward", False)),
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


# ---------------------------------------------------------------------------
# WP9c -- `--resume` support.
#
# Spec source (sole authority; a missing detail is reported BLOCKED, never guessed): this
# task's own orchestrator brief (2026-07-07, "语义规则(orchestrator 钉死)" points 1-2), since
# neither ADR-ECON-003 nor PREREG Appendix A names a resume/checkpoint mechanism -- the
# underlying settlement semantics this file reconstructs from disk (accept/verify split,
# Q/N/P fold, RoutingPriorUpdated) remain exactly Decision 2.4/6's, unchanged by this section.
#
# Hard constraint A (this file's caller): resume must be able to reconstruct purely from
# what a driver run *already wrote to disk* -- per task, only
# `task_runs/<instance>/<lineage>/{candidate.patch, worker_receipt.json}` (worker artifacts)
# and the scoring artifacts under `report-dir/<instance>/<lineage>/` (aggregated report +
# `logs/run_evaluation/<run_id>/<model>/<instance>/report.json`); the committed_routing_events
# tape and per-domain_bucket diversity history are process-local and never persisted on their
# own, so this section's own `settlement.json` checkpoint (point 2 below) is the only
# additional on-disk state this file introduces to make that reconstruction cheap (skip
# `econ_fold_cli` subprocess calls entirely for already-settled tasks) rather than merely
# possible (the coarser artifact-level reconstruction below remains correct without it, e.g.
# after a kill between "scoring completed" and "checkpoint written").
# ---------------------------------------------------------------------------

SETTLEMENT_CHECKPOINT_SCHEMA = "econ_lab.live_driver.settlement_checkpoint.v1"
SETTLEMENT_CHECKPOINT_FILENAME = "settlement.json"


def _settlement_checkpoint_path(task_dir_root: Path, instance_id: str) -> Path:
    return task_dir_root / instance_id / SETTLEMENT_CHECKPOINT_FILENAME


def _load_settlement_checkpoint(task_dir_root: Path, instance_id: str) -> Optional[dict[str, Any]]:
    path = _settlement_checkpoint_path(task_dir_root, instance_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # A truncated/unreadable checkpoint (e.g. left by a run killed mid-write, before
        # `_write_settlement_checkpoint` became atomic) degrades to "no checkpoint": the
        # caller falls back to the coarser artifact-level reconstruction below, which remains
        # correct without the checkpoint -- resume never crashes on partial checkpoint bytes.
        return None


def _write_settlement_checkpoint(task_dir_root: Path, instance_id: str, checkpoint: dict[str, Any]) -> None:
    """Point 2 of the resume semantics: written after *every* task's settlement, fresh or
    resumed alike -- never conditioned on `--resume`. This write has no return value read by
    `run_driver` and touches no key of the `verdict` dict it builds, so it cannot change
    `verdict.json`'s bytes by construction (guarded by
    `tests/test_live_driver_head_parity.py`, which never passes `--resume` and still exercises
    this write path once WP9c's fresh-run call site below runs).

    The write is atomic (temp file in the same directory, then `os.replace`): a kill during
    the write leaves either the previous checkpoint or none at all on disk, never a truncated
    `settlement.json` -- and `_load_settlement_checkpoint` above degrades a truncated file to
    "no checkpoint" anyway, so both halves of the contract hold independently."""
    path = _settlement_checkpoint_path(task_dir_root, instance_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)


def _reconstruct_worker_result_from_artifacts(
    *,
    task_dir_root: Path,
    instance_id: str,
    arm: str,
    lineage: str,
) -> Optional[dict[str, Any]]:
    """Hard constraint A's resume rule ("若有 candidate.patch/worker_receipt -> 绝不重调
    worker"): read back a prior worker dispatch's on-disk artifacts and reconstruct the same
    `worker_result` shape `dispatch_worker_for_lineage` would have returned, so the downstream
    scoring/settlement code below (shared verbatim with `_settle_one`) is byte-identical
    whether or not the worker was actually re-invoked this process.

    Returns `None` when either artifact is missing at every candidate path this file's own
    dispatch paths ever write to -- a partial write from a killed process (e.g. candidate.patch
    written, then killed before worker_receipt.json; or a worker_receipt.json that exists but
    is truncated/unparseable) is deliberately treated the same as "no artifact" (matching the
    fresh-dispatch contract, which always writes both files as one unit), so the caller falls
    back to a full re-dispatch rather than settling on a possibly-truncated patch.

    Checks the siliconflow path first (`task_dir_root/<instance>/<lineage>/`), then -- only
    for the deepseek lineage -- the native-fallback path
    (`task_dir_root/deepseek_direct_fallback/<instance>/`), mirroring `_settle_one`'s own
    patch-path resolution by `provider_path`.
    """
    siliconflow_dir = task_dir_root / instance_id / lineage
    if (siliconflow_dir / "candidate.patch").exists() and (siliconflow_dir / "worker_receipt.json").exists():
        try:
            receipt = json.loads((siliconflow_dir / "worker_receipt.json").read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # Truncated/unreadable receipt = "no artifact" (docstring contract above):
            # re-dispatch rather than settle on a possibly-partial write.
            return None
        patch_bytes = len((siliconflow_dir / "candidate.patch").read_text(encoding="utf-8").encode("utf-8"))
        return {
            "status": "COMPLETED",
            "instance_id": receipt.get("instance_id", instance_id),
            "arm": receipt.get("arm", arm),
            "lineage": lineage,
            "provider_path": "siliconflow",
            "candidate_patch_sha256": receipt.get("candidate_patch_sha256"),
            "candidate_patch_bytes": patch_bytes,
            "wall_time_ms": receipt.get("wall_time_ms"),
        }
    if lineage == "deepseek":
        fallback_dir = task_dir_root / "deepseek_direct_fallback" / instance_id
        if (fallback_dir / "candidate.patch").exists() and (fallback_dir / "worker_receipt.json").exists():
            try:
                receipt = json.loads((fallback_dir / "worker_receipt.json").read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                # Same truncated-receipt rule as the siliconflow path above: "no artifact".
                return None
            patch_bytes = len((fallback_dir / "candidate.patch").read_text(encoding="utf-8").encode("utf-8"))
            # Known, reported gap (this module's own "known spec gaps" discipline, see the
            # module docstring): `candidate_audit_status`/`candidate_audit_problems` live in a
            # third artifact (`worker_candidate_audit.json`) that hard constraint A's own
            # resume-anchor list does not name (only candidate.patch/worker_receipt.json) --
            # best-effort reconstruction from the receipt alone; these two fields are `None`
            # when resume is reconstructing this rare fallback path (the deepseek lineage's
            # SiliconFlow-primary path covers the overwhelming majority of Stage A dispatches;
            # see the module docstring's fallback-trigger note).
            return {
                "instance_id": receipt.get("instance_id", instance_id),
                "status": receipt.get("status", "COMPLETED"),
                "model_reported": receipt.get("model_reported"),
                "candidate_patch_sha256": receipt.get("candidate_patch_sha256"),
                "candidate_patch_bytes": patch_bytes,
                "candidate_audit_status": None,
                "candidate_audit_problems": None,
                "cost_microusd": (receipt.get("cost_event") or {}).get("cost", {}).get("cost_microusd"),
                "usage": receipt.get("usage"),
                "lineage": lineage,
                "provider_path": "deepseek_direct_fallback",
                "primary_attempt_status": "RECONSTRUCTED_FROM_ARTIFACTS",
            }
    return None


def _reused_report_matches_current_patch(*, report_dir: Path, instance_id: str, model_patch: str) -> bool:
    """Resume tamper guard for `_settle_one_resume`'s report-reuse branch: an on-disk
    aggregated scoring report is only reusable if it was actually computed over the *current*
    `candidate.patch`. The fresh scoring path (`score_with_official_harness`) records exactly
    what it handed the harness in `<report_dir>/predictions.jsonl` (one JSON row per line:
    `instance_id` / `model_name_or_path` / `model_patch`); this cross-checks the current
    patch's sha256 against the `model_patch` recorded there for this `instance_id`. Any
    mismatch, missing/unreadable predictions file, or absent row returns `False`, and the
    caller falls back to re-scoring (local docker, zero API spend) instead of settling one
    patch on another patch's report. Resume-only: the fresh path never reads this."""
    predictions_path = report_dir / "predictions.jsonl"
    try:
        prediction_lines = predictions_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    current_patch_sha256 = sha256_hex(model_patch.encode("utf-8"))
    for line in prediction_lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            return False
        if isinstance(row, dict) and row.get("instance_id") == instance_id:
            recorded_patch = row.get("model_patch")
            return (
                isinstance(recorded_patch, str)
                and sha256_hex(recorded_patch.encode("utf-8")) == current_patch_sha256
            )
    return False


def _settle_one_resume(
    *,
    args: argparse.Namespace,
    packet: dict[str, Any],
    arm: str,
    lineage: str,
    task_dir_root: Path,
    report_root: Path,
    deepseek_native_provider_config: Optional[dict[str, Any]],
    cli_bin: Path,
    route_domain: str,
    route_scaffold: str,
    run_label: str = "",
    task_index: int = 0,
    diagnostic_prefix: Optional[str] = None,
    monitor_enabled: bool = False,
) -> dict[str, Any]:
    """Resume-aware counterpart of `_settle_one` for one (task, lineage): reuses on-disk
    worker/scoring artifacts when present instead of recalling the worker or (when the
    aggregated scoring report already exists *and validates*, B6 below) the harness. Judgment
    code (`_apply_live_split_verifier`) and return shape are shared verbatim with `_settle_one`
    -- this function differs only in *how* `worker_result`/`scoring_result` are obtained,
    never in how they are judged, so a resumed settlement and a fresh settlement of the same
    underlying artifacts are byte-identical (`tests/test_live_driver_resume.py`).

    `diagnostic_prefix` / `monitor_enabled` (WP-H2, `--monitor` only, both default to the
    pre-WP-H2 "off" values): only reachable when `worker_result is None` below (the "no
    artifact at all -> full fresh path" branch); once real reconstructed worker artifacts
    exist, no new dispatch happens here for either parameter to affect. Both default to
    behavior-identical-to-before-this-parameter-existed; see `_settle_one`'s own docstring
    for how `monitor_enabled=False` (its default) keeps the forwarded kwarg from ever
    reaching `dispatch_worker_for_lineage`.
    """
    instance_id = packet["instance_id"]

    worker_result = _reconstruct_worker_result_from_artifacts(
        task_dir_root=task_dir_root, instance_id=instance_id, arm=arm, lineage=lineage
    )
    if worker_result is None:
        # Hard constraint A: "全缺 -> 正常全流程" -- no worker artifact at all, so this task's
        # settlement takes the exact same path a fresh (non-resume) run would.
        return _settle_one(
            args=args,
            packet=packet,
            arm=arm,
            lineage=lineage,
            task_dir_root=task_dir_root,
            report_root=report_root,
            deepseek_native_provider_config=deepseek_native_provider_config,
            cli_bin=cli_bin,
            route_domain=route_domain,
            route_scaffold=route_scaffold,
            run_label=run_label,
            task_index=task_index,
            diagnostic_prefix=diagnostic_prefix,
            monitor_enabled=monitor_enabled,
        )

    scoring_result: dict[str, Any] = {"status": "SKIPPED_NO_PATCH"}
    settlement_verdict: Optional[bool] = None
    live_split_result: Optional[dict[str, Any]] = None
    backup_update: dict[str, Any] = {"applied": False, "reason": "SCORING_NOT_COMPLETED"}
    routing_prior_updated_event: Optional[dict[str, Any]] = None

    provider_path = worker_result.get("provider_path", "siliconflow")
    if provider_path == "deepseek_direct_fallback":
        patch_path = task_dir_root / "deepseek_direct_fallback" / instance_id / "candidate.patch"
    else:
        patch_path = task_dir_root / instance_id / lineage / "candidate.patch"
    model_patch = patch_path.read_text(encoding="utf-8") if patch_path.exists() else ""

    if model_patch.strip():
        run_id = f"wp9a-live-driver-{instance_id}-{lineage}"
        report_dir = (report_root / instance_id / lineage).resolve()
        report_path = _aggregated_report_path(report_dir, run_id=run_id)
        # B6 remedy (independent audit B6, ADR-ECON-003 Decision 7.5, 2026-07-08 orchestrator
        # ruling): only trust an on-disk aggregated report when `SCORING_OK.marker` validates
        # against it -- a report left behind by a run that hit SCORING_FAILED (rc!=0 after the
        # harness partially wrote a report) never got a marker, so it is unconditionally
        # re-scored instead of silently treated as COMPLETED. Closes the residual fresh/resume
        # divergence the patch-hash tamper guard below did not cover.
        reused_scoring_result = (
            _read_scoring_report(report_dir=report_dir, run_id=run_id, instance_id=instance_id)
            if _scoring_ok_marker_valid(report_dir=report_dir, report_path=report_path)
            else None
        )
        if reused_scoring_result is not None and not _reused_report_matches_current_patch(
            report_dir=report_dir, instance_id=instance_id, model_patch=model_patch
        ):
            # Tamper guard (`_reused_report_matches_current_patch`): the on-disk report was
            # computed over a different patch than the candidate.patch now on disk -- never
            # settle on it; fall through to re-scoring the current patch instead.
            reused_scoring_result = None
        if reused_scoring_result is not None:
            # "评分产物在 -> 复用报告重算裁决" -- `live_split_verifier.judge` is a pure function,
            # so re-judging an already-produced report is exactly what a fresh run's own single
            # judge call would have computed; no harness subprocess, no worker call.
            scoring_result = reused_scoring_result
        else:
            # "评分产物缺(或 marker 未过校验)-> 用既有补丁重跑评分" -- local docker only, zero
            # API spend (the patch itself is reused verbatim; only the harness, never the
            # worker, runs again). This call site also (re-)writes SCORING_OK.marker on
            # success (see `score_with_official_harness`).
            scoring_result = score_with_official_harness(
                python_bin=args.scoring_python,
                instance_id=instance_id,
                model_patch=model_patch,
                run_id=run_id,
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
                infra_null_reason=scoring_result.get("infra_null_reason"),
                run_label=run_label,
                task_index=task_index,
                fractional_reward=bool(getattr(args, "fractional_reward", False)),
            )
            settlement_verdict = live_split_result["accept_verdict"]
    else:
        # B3 (see `_settle_one`'s own comment): reconstructed worker artifacts with an
        # empty/whitespace-only patch are the same determinate task failure a fresh run would
        # settle -- never re-invokes the harness or the worker.
        live_split_result, backup_update, routing_prior_updated_event = _apply_live_split_verifier(
            cli_bin=cli_bin,
            instance_id=instance_id,
            arm=arm,
            lineage=lineage,
            route_domain=route_domain,
            route_scaffold=route_scaffold,
            tests_status=None,
            harness_error_reason=EMPTY_PATCH_WORKER_OUTPUT_REASON,
            run_label=run_label,
            task_index=task_index,
            fractional_reward=bool(getattr(args, "fractional_reward", False)),
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

    # Stage B' task-stream override (`--task-shard`, ADR-ECON-003 Decision 7.6 out-of-sample
    # discipline: "评测任务与先验来源任务必须零交集"): defaults to the pre-existing S01 root
    # (`SHARD_ROOT`) when absent -- behavior-identical to every pre-Stage-B' call.
    task_shard_arg = getattr(args, "task_shard", None)
    shard_root = Path(task_shard_arg) if task_shard_arg else SHARD_ROOT
    packets = load_task_packets(shard_root)
    if not packets:
        raise SystemExit(f"no task packets found under {shard_root}/{TASKS_GLOB}")

    # P3-E3 ordered stream (`--stream-manifest`): when present, the evaluation order is the
    # manifest's instance_id list (PHASE1 then PHASE2 family blocks for P3-E3), not the
    # default glob sort of load_task_packets. Absent -> behavior-identical to every
    # pre-P3-E3 call.
    stream_manifest_arg = getattr(args, "stream_manifest", None)
    stream_manifest_sha256: Optional[str] = None
    stream_instance_ids: Optional[list[str]] = None
    if stream_manifest_arg:
        stream_instance_ids, stream_manifest_sha256 = load_stream_manifest(Path(stream_manifest_arg))
        packets = order_packets_by_stream_manifest(packets, stream_instance_ids)

    # Stage B' warm-start priors (`--priors`, ADR-ECON-003 Decision 6.1/7.6): loaded once per
    # run, applied per task below in `fold_and_select`'s `initial_prices`. Absent by default
    # (empty map -> `stage_b_prime_initial_prices` returns `[]` -> behavior-identical to every
    # pre-Stage-B' call, which always sent `initial_prices: []`).
    priors_arg = getattr(args, "priors", None)
    priors_map: dict[str, float] = {}
    priors_sha256: Optional[str] = None
    if priors_arg:
        priors_map, priors_sha256 = load_stage_b_prime_priors(Path(priors_arg))

    # Stage B' frozen-backup arm (`--frozen-backup`, ADR-ECON-003 Decision 7.7): the
    # RoutingPriorUpdated event is still built and persisted (evidence complete -- see the
    # checkpoint's own `routing_prior_updated_event` field below, unconditionally written),
    # but is never appended to `committed_routing_events` (the fold's own event sequence), so
    # every route's `Q_eff` stays pinned at its `P` for the whole run ("Q_eff 恒为 P").
    frozen_backup = bool(getattr(args, "frozen_backup", False))

    # P3-E3 reset arm (`--reset-at-task-index`, CAPSULE A §3 R arm): when task_index reaches
    # this 0-based index (i.e. after finishing the previous task, before routing the current
    # one), clear committed_routing_events so the fold restarts with the same injected priors
    # (Q/N/S zeroed, P re-pinned via initial_prices on first post-reset appearance). Pure
    # deterministic bookkeeping -- no new fold formula. None/absent -> no reset (L/Z arms).
    reset_at_task_index = getattr(args, "reset_at_task_index", None)
    if reset_at_task_index is not None:
        reset_at_task_index = int(reset_at_task_index)
    reset_applied_at: Optional[int] = None

    # B5 remedy (ADR-ECON-003 Decision 7.4): per-invocation identifier folded into every
    # verifier attestation so two different driver invocations over the same (instance, arm,
    # lineage, verdict) never collide on `event_hash` -- see `_verifier_attestation_hash`'s
    # own docstring. `--run-label` lets a caller (e.g. `run_stage_b_prime.sh`) supply an
    # explicit label; the default (`--out`'s own path) is already distinct per arm/run in
    # every existing caller (`run_stage_a.sh` writes each arm to its own `--out`), so this is
    # a safe zero-config default, not a new required flag.
    run_label = getattr(args, "run_label", None) or str(args.out)

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
        # Stage A arm invocation (--tau): maps the PREREG tau grid onto the three Rust
        # router modes. Mantissa = floor(tau * 2^32) per ADR-ECON-003 Decision 4; the
        # values below are the frozen experiment arms, not B-zone production constants.
        tau_arg = getattr(args, "tau", None)
        if tau_arg is None or tau_arg == "0":
            tau_config = None  # tau=0 argmax-bypass (Decision 4 mode bypass)
        elif tau_arg == "inf":
            tau_config = {"kind": "uniform"}
        else:
            tau_config = {"tau_hi_q32_mantissa": int(float(tau_arg) * (1 << 32))}
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
    # B2 remedy (ADR-ECON-003 Decision 7.1): dispatches the harness never actually evaluated
    # at all (infra_null) -- counted, never settled, never fed back.
    infra_null_count = 0
    # Per-domain_bucket settlement history for the N_eff/H_lineage estimator (WP5), lineage
    # labels only (module doc's lineage-label discipline). `settlement_index` is shared
    # across lineages settled on the *same* task/round (ADR-ECON-003 Decision 3: "对齐到
    #共同结算索引"), incremented once per task processed, not per lineage.
    diversity_history: dict[str, list[dict[str, Any]]] = {}

    resume_mode = bool(getattr(args, "resume", False))

    # WP-H2 (ADR-ECON-007 Decision 1/2/3): --monitor hook state. `monitor_enabled` gates
    # every single line below in this block and every use of `pending_diagnostic_text`
    # further down the task loop -- when it is False (the default; every pre-WP-H2 call
    # site never set --monitor at all), none of this runs and `verdict["monitor_summary"]`
    # is never added, so a --monitor-absent run stays byte-identical to a pre-WP-H2 run
    # (see tests/test_live_driver_monitor_hook.py).
    monitor_enabled = bool(getattr(args, "monitor", False))
    monitor_cfg: Optional["monitor_loop_detector.LoopDetectorConfig"] = None
    monitor_rollback_cap = monitor_interventions.DEFAULT_MAX_ROLLBACKS_PER_FORK_POINT
    monitor_rollback_cap_arg = getattr(args, "monitor_rollback_cap", None)
    if monitor_rollback_cap_arg is not None:
        monitor_rollback_cap = int(monitor_rollback_cap_arg)
    if monitor_enabled:
        monitor_config_path = getattr(args, "monitor_config", None)
        if not monitor_config_path:
            raise SystemExit(
                "--monitor requires --monitor-config (ADR-ECON-007 Decision 3: no B-zone "
                "loop-detector threshold may be hardcoded in this file)"
            )
        with open(monitor_config_path, "r", encoding="utf-8") as handle:
            monitor_cfg_raw = json.load(handle)
        monitor_cfg = monitor_loop_detector.LoopDetectorConfig(**monitor_cfg_raw)
    # `monitor_tape`: append-only full history (ADR-ECON-007 Decision 1: "回滚绝不改写
    # tape"). `monitor_workspace`: the working trajectory a rollback resets to its fork
    # point; execution (i.e. this driver's own next-task dispatch) continues from it.
    monitor_tape: list[dict[str, Any]] = []
    monitor_workspace: list[dict[str, Any]] = []
    monitor_diagnostics_issued: list[dict[str, Any]] = []
    # WP-H3 (ADR-ECON-007 Decision 4): populated only when WP-H2's rollback remedy is
    # already exhausted for a fork point (see the `RollbackCapExceededError` branch
    # below) -- Decision 4's "放弃" report path. Always present under `--monitor`
    # (defaulting to `[]`, exactly WP-H2's own `monitor_diagnostics_issued` discipline).
    monitor_route_falsification_reports: list[dict[str, Any]] = []
    # Consumed exactly once, by the *next* task's dispatch calls below (Decision 1/3's
    # "触发时注入诊断到下一次 worker 上下文并回滚") -- never re-used across two tasks.
    pending_diagnostic_text: Optional[str] = None

    for task_index, packet in enumerate(packets[:max_tasks]):
        instance_id = packet["instance_id"]

        # P3-E3 R-arm reset: at the switch point, drop pre-switch fold events so subsequent
        # routing re-seeds from the same injected priors. Applied on both the fresh path and
        # the resume-replay path so a resumed R arm reconstructs the same post-reset tape.
        if reset_at_task_index is not None and task_index == reset_at_task_index:
            committed_routing_events = []
            reset_applied_at = task_index

        # WP9c point 1: "若该题存在增量检查点 settlement.json -> 逐字节采用其中的 fold 事件
        # 与结算记录,不重算" -- when a checkpoint exists, this task's entire settlement
        # (domain_bucket, selection, every dispatch) is replayed verbatim from disk: no
        # `econ_fold_cli` subprocess call, no worker dispatch, no scoring re-read.
        checkpoint = _load_settlement_checkpoint(task_dir_root, instance_id) if resume_mode else None

        if checkpoint is not None:
            domain_bucket = checkpoint["domain_bucket"]
            selected_route_id = checkpoint["selected_route_id"]
            selected_arm = checkpoint["selected_arm"]
            selected_lineage = checkpoint["selected_lineage"]
            dispatch_mode = checkpoint["dispatch_mode"]
            budget_suggestion = checkpoint["budget_suggestion"]
            task_evidence_class = checkpoint.get("evidence_class", evidence_class)
            dispatches = []
            for stored_dispatch in checkpoint["dispatches"]:
                settled = dict(stored_dispatch)
                routing_prior_updated_event = settled.pop("routing_prior_updated_event", None)
                if routing_prior_updated_event is not None:
                    routing_prior_updated_applied_count += 1
                    if not frozen_backup:
                        # Stage B' frozen-backup (Decision 7.7): the event stays evidence-only
                        # (already persisted in the checkpoint) but never enters the fold's
                        # event sequence -- see the fresh-path branch's identical gate below.
                        committed_routing_events.append(routing_prior_updated_event)
                dispatches.append(settled)

                if settled.get("worker_result_status") == "COMPLETED":
                    real_worker_calls += 1

                live_split_verdict = settled.get("live_split_verdict")
                if live_split_verdict is not None:
                    settled_dispatch_count += 1
                    not_enough_tests_count += int(live_split_verdict["not_enough_tests"])
                    canary_count += int(live_split_verdict["canary"])
                    infra_null_count += int(bool(live_split_verdict.get("infra_null", False)))

                if settled.get("settlement_verdict_resolved") is not None:
                    diversity_history.setdefault(domain_bucket, []).append(
                        {
                            "lineage_id": settled["lineage"],
                            "settlement_index": task_index,
                            "verdict": bool(settled["settlement_verdict_resolved"]),
                        }
                    )
        else:
            task_family = task_family_for_packet(packet)
            domain_bucket = derive_domain_bucket(cli_bin, task_family)

            selection = fold_and_select(
                cli_bin,
                committed_routing_events=committed_routing_events,
                domain_bucket=domain_bucket,
                scaffold_ids=scaffold_ids,
                instance_id=instance_id,
                tau_config=tau_config,
                initial_prices=stage_b_prime_initial_prices(
                    priors_map, domain_bucket=domain_bucket, scaffold_ids=scaffold_ids
                ),
            )
            selected_route_id = selection["budget_suggestion"]["route_id"]
            _instance, selected_arm, selected_lineage = selected_route_id.split("::")
            budget_suggestion = selection["budget_suggestion"]
            task_evidence_class = evidence_class

            if args.smoke:
                dispatch_mode = "smoke_all_lineages_for_winning_arm"
                lineages_to_dispatch = list(LINEAGES)
            else:
                dispatch_mode = "single_winner"
                lineages_to_dispatch = [selected_lineage]

            # WP-H2 (ADR-ECON-007 Decision 1/3): the diagnostic queued by a rollback
            # detected on the *previous* task (if any) is injected into every lineage
            # dispatch of *this* task, then consumed (never re-used on a later task).
            # `monitor_enabled` is False on every pre-WP-H2 call site, so
            # `task_diagnostic_prefix` is always `None` there -- zero behavior change.
            task_diagnostic_prefix = pending_diagnostic_text if monitor_enabled else None
            pending_diagnostic_text = None

            dispatches = []
            checkpoint_dispatches: list[dict[str, Any]] = []
            for lineage in lineages_to_dispatch:
                if real_call_cap is not None and real_worker_calls >= real_call_cap:
                    settled = {
                        "lineage": lineage,
                        "worker_result_status": "SKIPPED_SPEND_CAP",
                        "provider_path": None,
                        "worker_result": {"status": "SKIPPED_SPEND_CAP"},
                        "scoring_result": {"status": "SKIPPED_NO_PATCH"},
                        "settlement_verdict_resolved": None,
                        "live_split_verdict": None,
                        "backup_update": {"applied": False, "reason": "SKIPPED_SPEND_CAP"},
                    }
                    dispatches.append(settled)
                    checkpoint_dispatches.append({**settled, "routing_prior_updated_event": None})
                    continue

                settle_fn = _settle_one_resume if resume_mode else _settle_one
                settled = settle_fn(
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
                    run_label=run_label,
                    task_index=task_index,
                    diagnostic_prefix=task_diagnostic_prefix,
                    monitor_enabled=monitor_enabled,
                )
                if settled["worker_result_status"] == "COMPLETED":
                    real_worker_calls += 1

                # Decision 2.4 backup-update wiring: feed the independent verifier's
                # RoutingPriorUpdated event (if one was built) back onto the tape this same
                # driver run folds over for every subsequent task's selection -- this is the
                # live "回灌" (feedback) WP9a lacked entirely. Checkpoint write below is
                # unconditional (evidence complete, Decision 7.7); only the *fold* append is
                # gated by `frozen_backup` (Stage B' frozen-backup arm: Q_eff stays pinned at
                # P for the whole run).
                routing_prior_updated_event = settled.pop("_routing_prior_updated_event", None)
                if routing_prior_updated_event is not None:
                    routing_prior_updated_applied_count += 1
                    if not frozen_backup:
                        committed_routing_events.append(routing_prior_updated_event)
                dispatches.append(settled)
                checkpoint_dispatches.append({**settled, "routing_prior_updated_event": routing_prior_updated_event})

                live_split_verdict = settled.get("live_split_verdict")
                if live_split_verdict is not None:
                    settled_dispatch_count += 1
                    not_enough_tests_count += int(live_split_verdict["not_enough_tests"])
                    canary_count += int(live_split_verdict["canary"])
                    infra_null_count += int(bool(live_split_verdict.get("infra_null", False)))

                if settled["settlement_verdict_resolved"] is not None:
                    diversity_history.setdefault(domain_bucket, []).append(
                        {
                            "lineage_id": lineage,
                            "settlement_index": task_index,
                            "verdict": bool(settled["settlement_verdict_resolved"]),
                        }
                    )

            # WP9c point 2: written for every freshly-settled task, fresh run or resume alike
            # (never for a task replayed from an existing checkpoint above) -- see
            # `_write_settlement_checkpoint`'s own docstring for why this cannot perturb
            # `verdict.json`'s bytes.
            _write_settlement_checkpoint(
                task_dir_root,
                instance_id,
                {
                    "schema": SETTLEMENT_CHECKPOINT_SCHEMA,
                    "instance_id": instance_id,
                    "task_index": task_index,
                    "domain_bucket": domain_bucket,
                    "selected_route_id": selected_route_id,
                    "selected_arm": selected_arm,
                    "selected_lineage": selected_lineage,
                    "dispatch_mode": dispatch_mode,
                    "budget_suggestion": budget_suggestion,
                    "evidence_class": task_evidence_class,
                    "dispatches": checkpoint_dispatches,
                },
            )

            # WP-H2 (ADR-ECON-007 Decision 1/2/3): feed this task's just-settled
            # dispatches to the external loop detector, one call per task (this
            # driver's finest available trajectory granularity -- see WP-H1's own
            # documented spec gap: no per-edit trace exists on disk yet, so
            # `events_from_real_settlement_checkpoint` is the honest empirical
            # bridge, reused verbatim rather than re-derived). `monitor_tape` is
            # append-only (Decision 1: never rewritten/truncated); `monitor_workspace`
            # is the working view a rollback resets to its fork point -- the two are
            # allowed to diverge in their own internal `seq` numbering after a
            # rollback (each is independently renumbered going forward), which is
            # harmless: `seq` only needs to be locally monotonic within whichever list
            # the detector/hash logic is given, and the one event whose identity must
            # stay stable across repeated reference (the fork point itself) is never
            # touched by `renumber_and_append` -- only *newly appended* events are.
            if monitor_enabled:
                task_settlement_for_monitor = {
                    "instance_id": instance_id,
                    "selected_route_id": selected_route_id,
                    "dispatches": checkpoint_dispatches,
                }
                task_events = monitor_loop_detector.events_from_real_settlement_checkpoint(
                    task_settlement_for_monitor
                )
                monitor_tape = monitor_interventions.renumber_and_append(monitor_tape, task_events)
                monitor_workspace = monitor_interventions.renumber_and_append(monitor_workspace, task_events)

                trip_dict = monitor_loop_detector.detect(monitor_workspace, monitor_cfg)
                if trip_dict["tripped"]:
                    trip = monitor_loop_detector.LoopTrip(
                        rule_id=trip_dict["rule_id"], at_seq=trip_dict["at_seq"], evidence=trip_dict["evidence"]
                    )
                    diagnostic = monitor_interventions.build_diagnostic(trip)
                    try:
                        rollback_result = monitor_interventions.execute_rollback(
                            tape=monitor_tape,
                            workspace=monitor_workspace,
                            trip=trip,
                            diagnostic=diagnostic,
                            max_rollbacks_per_fork_point=monitor_rollback_cap,
                        )
                    except monitor_interventions.RollbackCapExceededError as cap_error:
                        # Decision 1: "禁止再回滚该点" -- this fork point stays
                        # un-rolled-back; execution continues without intervention for
                        # it (no diagnostic injected, no workspace reset). Recorded as
                        # evidence, never silently swallowed.
                        monitor_diagnostics_issued.append(
                            {
                                "task_index": task_index,
                                "rule_id": trip.rule_id,
                                "outcome": "ROLLBACK_CAP_EXCEEDED",
                                "detail": str(cap_error),
                            }
                        )
                        # WP-H3 (ADR-ECON-007 Decision 4): WP-H2's own documented
                        # extension point ("the caller decides how to degrade
                        # gracefully") -- remediation for this fork point is exhausted,
                        # which is exactly Decision 4's "放弃" (abandon) case. The
                        # bare `except` above is never allowed to just fall through to
                        # the next task silently; it must produce a `RouteFalsified`
                        # PRESERVE event + structured report instead. Every field
                        # fed to `terminate_falsified` below is fact-only (Decision 3):
                        # `trip.evidence` is already guaranteed Decision-3-legal by
                        # `loop_detector`'s own construction, and the two harness-
                        # authored strings below (`fact_class`/`recommendation`) carry
                        # no B-zone token or digit.
                        falsified_route_id = selected_route_id
                        falsified_verifier_evidence = [
                            {"phase": e.get("phase"), "result": e["result"]}
                            for e in monitor_workspace
                            if e.get("event_type") == "verification"
                        ]
                        falsified_detector_events = [{"rule_id": trip.rule_id, "evidence": dict(trip.evidence)}]
                        # Honest gap, not a guess (this WP's own red line): the
                        # driver's current selection is single-winner dispatch and
                        # does not enumerate alternate route candidates anywhere --
                        # `remaining_candidates` stays `[]` rather than inventing IDs.
                        falsified_remaining_candidates: list[str] = []
                        next_tape_seq = max((e.get("seq", -1) for e in monitor_tape), default=-1) + 1
                        termination_outcome = monitor_termination.terminate_falsified(
                            route_id=falsified_route_id,
                            attempts=[
                                {
                                    "fact_class": "REMEDIATION_EXHAUSTED",
                                    "detector_rule_id": trip.rule_id,
                                }
                            ],
                            verifier_evidence=falsified_verifier_evidence,
                            detector_events=falsified_detector_events,
                            remaining_candidates=falsified_remaining_candidates,
                            recommendation=(
                                "Rollback remediation is exhausted for this route's "
                                "detected fork point without verifier evidence; "
                                "recommend GRILL-ME review before further dispatch on "
                                "this route."
                            ),
                            seq=next_tape_seq,
                        )
                        monitor_tape = list(monitor_tape) + [termination_outcome.event]
                        monitor_route_falsification_reports.append(termination_outcome.report)
                    else:
                        monitor_tape = list(rollback_result.tape)
                        monitor_workspace = list(rollback_result.workspace)
                        pending_diagnostic_text = diagnostic.text
                        monitor_diagnostics_issued.append(
                            {
                                "task_index": task_index,
                                "rule_id": trip.rule_id,
                                "outcome": "ROLLED_BACK",
                                "diagnostic_digest": diagnostic.digest,
                                "rollback_event_hash": rollback_result.event["event_hash"],
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
                "budget_suggestion": budget_suggestion,
                "dispatches": dispatches,
                "evidence_class": task_evidence_class,
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
            # B2 remedy (ADR-ECON-003 Decision 7.1): always present (usually 0) -- see
            # `tests/test_live_driver_head_parity.py`'s own normalization note for why this
            # key's mere presence is a legitimate, expected divergence from a pre-WP10 anchor.
            "infra_null_count": infra_null_count,
        },
        # Stage B' / P3-E3 run metadata (ADR-ECON-003 Decision 7.6/7.7, CAPSULE A §3):
        # always present (fields are `None`/`False` when the corresponding flag is unused),
        # never a τ/λ/floor/B-zone value (Art III.4/F4) -- every field here is either a
        # caller-supplied label/path/index or a sha256 digest.
        "stage_b_prime_meta": {
            "schema": "econ_lab.stage_b_prime_meta.v1",
            "frozen_backup": frozen_backup,
            "priors_path": str(priors_arg) if priors_arg else None,
            "priors_sha256": priors_sha256,
            "task_shard": str(task_shard_arg) if task_shard_arg else None,
            "run_label": run_label,
            "stream_manifest": str(stream_manifest_arg) if stream_manifest_arg else None,
            "stream_manifest_sha256": stream_manifest_sha256,
            "reset_at_task_index": reset_at_task_index,
            "reset_at": reset_applied_at,
            "fractional_reward": bool(getattr(args, "fractional_reward", False)),
        },
        "generated_at_unix": int(time.time()),
    }
    # WP-H2: `monitor_summary` is added ONLY when --monitor was set -- never present
    # (not even as a null-valued key) on a --monitor-absent run, so verdict.json stays
    # byte-identical to a pre-WP-H2 run when the flag is unused (see
    # tests/test_live_driver_monitor_hook.py). This block is evidence/ledger
    # bookkeeping (tape/workspace/diagnostics already issued to workers), not a new
    # worker-visible surface itself.
    if monitor_enabled:
        verdict["monitor_summary"] = {
            "schema": "econ_lab.live_driver.monitor_summary.v1",
            "tape_event_count": len(monitor_tape),
            "workspace_event_count": len(monitor_workspace),
            "diagnostics_issued": monitor_diagnostics_issued,
            # WP-H3 (ADR-ECON-007 Decision 4): always present under --monitor
            # (defaulting to `[]`, WP-H2's own additive-only discipline) -- one
            # `RouteFalsificationReport.to_dict()` per exhausted-remediation fork
            # point (see the `RollbackCapExceededError` branch above).
            "route_falsification_reports": monitor_route_falsification_reports,
            "tape": monitor_tape,
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
    parser.add_argument(
        "--tau",
        choices=["0", "0.5", "1", "2", "inf"],
        default=None,
        help="Stage A arm temperature (PREREG E-price-tau grid); ignored under --smoke",
    )
    parser.add_argument("--task-dir-root", type=Path, default=None)
    parser.add_argument("--report-dir", type=Path, default=None)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="WP9c: reconstruct already-settled tasks from on-disk checkpoints/artifacts "
        "(task_runs/<instance>/settlement.json, or candidate.patch+worker_receipt.json plus "
        "scoring reports) instead of recomputing; never re-invokes a worker when a prior "
        "candidate.patch/worker_receipt.json pair exists for a task -- --task-dir-root/"
        "--report-dir must point at the same directories the interrupted run used",
    )
    parser.add_argument(
        "--priors",
        type=Path,
        default=None,
        help="Stage B' warm-start P (ADR-ECON-003 Decision 6.1/7.6): path to a priors JSON "
        "file -- either the pinned econ_lab.stage_b_prime_priors.v1 shape "
        "({\"priors\": {\"<arm>::<lineage>\": p, ...}, ...}) or a bare "
        "{\"<arm>::<lineage>\": p, ...} mapping. A route absent from the file gets the "
        "existing P=0.5 uninformative-prior default. The file's sha256 is recorded in "
        "verdict.json's stage_b_prime_meta.",
    )
    parser.add_argument(
        "--frozen-backup",
        action="store_true",
        help="Stage B' frozen-backup arm (ADR-ECON-003 Decision 7.7): RoutingPriorUpdated "
        "events are still built and persisted as evidence, but never appended to the fold's "
        "own event sequence -- every route's Q_eff stays pinned at its P for the whole run.",
    )
    parser.add_argument(
        "--task-shard",
        type=Path,
        default=None,
        help="Task-stream root override (default: the S01 shard root baked into SHARD_ROOT); "
        "Stage B' points this at the S02 shard so the evaluation task stream and the "
        "--priors source task stream are disjoint (out-of-sample discipline, ADR-ECON-003 "
        "Decision 7.6).",
    )
    parser.add_argument(
        "--run-label",
        default=None,
        help="B5 remedy (ADR-ECON-003 Decision 7.4): per-invocation identifier folded into "
        "every RoutingPriorUpdated verifier attestation, so two different driver invocations "
        "over the same (instance, arm, lineage, verdict) never collide on event_hash. "
        "Defaults to --out's own path (already distinct per arm/run in every existing "
        "caller).",
    )
    parser.add_argument(
        "--stream-manifest",
        type=Path,
        default=None,
        help="P3-E3 ordered evaluation stream: path to a JSON file with an 'instance_ids' "
        "list (or a bare list of instance_id strings). When set, packets are reordered to "
        "match this list exactly (CAPSULE A §3: PHASE1 families then PHASE2 families). "
        "File sha256 is recorded in verdict stage_b_prime_meta.",
    )
    parser.add_argument(
        "--reset-at-task-index",
        type=int,
        default=None,
        help="P3-E3 R-arm switch-point reset (CAPSULE A §3): 0-based task index at which "
        "committed_routing_events is cleared before routing (Q/N/S zeroed; P re-seeded from "
        "--priors via initial_prices). Deterministic pure bookkeeping; recorded as "
        "stage_b_prime_meta.reset_at when applied.",
    )
    parser.add_argument(
        "--fractional-reward",
        action="store_true",
        help="ADR-ECON-006: use verify-side pass fraction as RoutingPriorUpdated reward "
        "(Q32.32); default is binary verify-all-pass. Mode is recorded in stage_b_prime_meta.",
    )
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="WP-H2 (ADR-ECON-007 Decision 1/2/3): enable the external loop-detector + "
        "diagnostic-injection + ledger-compliant-rollback hook. Off by default -- every "
        "code path this flag gates is additive-only and never executes when absent, so a "
        "run without --monitor is byte-identical to a pre-WP-H2 run.",
    )
    parser.add_argument(
        "--monitor-config",
        type=Path,
        default=None,
        help="Required when --monitor is set: path to a JSON object with the B-zone "
        "loop-detector thresholds (same_fragment_failure_threshold/action_window_size/"
        "action_window_repeat_threshold/phase_timeout_steps -- ADR-ECON-007 Decision 3; "
        "never hardcoded in this file).",
    )
    parser.add_argument(
        "--monitor-rollback-cap",
        type=int,
        default=None,
        help="Per-fork-point rollback cap (ADR-ECON-007 Decision 1: published A-zone "
        "constant, initial value 2). Defaults to "
        "interventions.DEFAULT_MAX_ROLLBACKS_PER_FORK_POINT when --monitor is set and "
        "this is absent.",
    )
    args = parser.parse_args(argv)

    verdict = run_driver(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "WROTE_VERDICT", "path": str(args.out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
