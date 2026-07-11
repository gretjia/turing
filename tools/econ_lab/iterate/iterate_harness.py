#!/usr/bin/env python3
"""WP-L3-1: task-internal iterate-until-pass harness.

Spec sources (per the WP brief, "ADR 在计划目录不在仓库 -- 代码 docstring 引用其路径属正常"):
  - `PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/adr/ADR-ECON-007-route-market-loop-remedy.md`
    Decision 2 (detector never writes Q), Decision 3 (B-zone diagnostic discipline),
    Decision 4 (verification-gated termination + `RouteFalsified` proposal_only report),
    Decision 6a (task-internal same-signature retry limit, PROVISIONAL, fixture value 2).
  - `PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/research/RES_ROUTE_lockIn_remedy_design_20260710.md`
    §2 L1.2/L1.3 (diagnostic injection + verification-gated termination).

Recon anchors this module is built directly on top of (read-only reuse, nothing in
`tools/econ_lab/monitor/`, `tools/econ_lab/depthk/`, or `tools/econ_lab/analysis/` is
modified by this WP):

  * Receipt-chain shape the ship-gate auditor actually checks --
    `tools/bench/audit_loop_until_pass.py:113-142` (`audit_run`): the event chain
    FailureNode -> FailureCertificate -> BroadcastRuleActivated -> RetryAuthorized ->
    WorkCapsuleBuilt(second attempt) -> CandidateAccepted, with
    `retry_decision_source in {tape_reducer_or_policy, tape_policy}` and
    `fallback_to_auto_authorization: false`. This module's `run_iterate_harness`
    produces exactly that chain (generalized to N attempts, N >= 2) via the same
    low-level tape primitives `tools/bench/run_mini_swe_bench_substrate_smoke.py`'s
    `build_stage11_loop_until_pass_bundle` already uses and proves audit-clean
    (`append_stage6_event`/`stage6_base_state`/`load_event_registry`), loaded here by
    file path (that script is not an importable package) exactly the way
    `tests/test_stage11_loop_until_pass.py` already does.
  * Worker context injection point -- `tools/bench/run_deepseek_arm_a_worker.py:606`
    `load_worker_visible_context(...)` (via its `run_one_task` call site at that line):
    this harness calls that same function fresh at the top of every attempt (never
    cached across attempts) so `source_context.md` and the failure-memory broadcast
    section are rematerialized from disk each round, exactly as the WP brief requires
    ("每轮迭代重物化 source_context + 失败记忆 broadcast 节").
  * CAPSULE H component interfaces -- `tools/econ_lab/monitor/{loop_detector,
    interventions,termination}.py`, read-only, same call shape `live_driver.py`'s
    `--monitor` hook already established:
      - `monitor.loop_detector.find_all_trips`/`LoopDetectorConfig`: every attempt's
        edit/command trace is appended to a running detector event stream and replayed
        through the detector after each attempt ("检测器喂入(每轮事件进 loop_detector)").
      - `monitor.termination.terminate_falsified`/`assert_report_has_no_bzone_leak`:
        the escalation path (same-signature retry limit exceeded) is a direct call to
        `terminate_falsified`, and this module's own failure-memory guidance text is
        scanned with the *same* `assert_report_has_no_bzone_leak` function before it is
        ever embedded in a `BroadcastRuleActivated` payload (the WP brief's "语言化失败
        事实,过 termination.py 的 assert_report_has_no_bzone_leak 同款扫描").
      - Unlike `live_driver.py`'s own `--monitor` hook (which documents `remaining_
        candidates` as an honest always-`[]` gap: "驱动器的当前选择是 single-winner
        dispatch...`remaining_candidates` stays `[]` rather than inventing IDs"), this
        module's `IterateConfig.remaining_candidates` is caller-supplied from the
        route combination the caller actually has on hand, so the falsification report
        this harness builds is never forced to leave that field empty -- closing the
        recon-identified always-empty hole for exactly the case (task-internal
        escalation) where a caller-supplied candidate list is normally available.

Two independent event streams are produced, deliberately never merged (this mirrors
`termination.py`'s own placement note that `RouteFalsified`/`TrajectoryRolledBack`
"此事件不进 Q fold"/never enter the registered micro-tape -- confirmed empirically
here: `pack/04_registries/event_registry_v5_3_1.json`'s `unknown_event_policy` is
`REJECT` and neither `RouteFalsified` nor `TrajectoryRolledBack` is a registered
`canonical_name`, so appending either through `append_stage6_event` would raise):

  1. The **micro-tape event chain** (git-tape, registered event types only) --
     `SystemConstitutionAccepted` ... `FailureNode` ... `CandidateAccepted` ...
     `PPUTAccounted` -- built with the exact same registry-checked
     `append_stage6_event` primitive Stage11's own fixture uses, so a bundle this
     module produces is byte-shape-compatible with what
     `tools/bench/audit_loop_until_pass.py` already knows how to audit.
  2. The **detector trajectory stream** (`monitor.loop_detector`'s own documented JSON
     envelope: `seq`/`event_type`/`instance_id`/`route_id` plus edit/command/
     phase_boundary/verification/termination fields) -- harness-side only, never
     written to the git tape, exactly mirroring `live_driver.py`'s own
     `monitor_tape`/`monitor_workspace` placement.

Two terminal outcomes only, mirroring `monitor.termination`'s own two-outcome design
(never a third, bare-error-out shape):

  * ``CONVERGED`` -- some attempt N (N >= 2, since attempt 1 is deliberately the "坏
    路线" this WP names) returns a PASS official-evaluator verdict before the
    same-signature retry limit is hit. Produces a full `loop_until_pass` block whose
    keys/semantics are exactly what `audit_loop_until_pass.py`'s `audit_run` checks.
  * ``ESCALATED`` -- the same failure signature (failure_class, abstract_pattern) repeats
    `IterateConfig.same_signature_retry_limit` times consecutively (fixture value 2,
    ADR-ECON-007 Decision 6a: "任务内...同签名失败尝试连续 2 次...允许一次诚实重试").
    Calls `monitor.termination.terminate_falsified` with `remaining_candidates` taken
    verbatim from `IterateConfig.remaining_candidates` (the recon-identified gap this
    WP closes) and returns its `RouteFalsified` event + structured report *without*
    ever appending either to the micro-tape (unregistered event type; see above) and
    *without* advancing any `accepted_head` (Decision 4: "proposal_only,不推进任何
    accepted_head" -- this module never calls anything that could).

A third, structural-only outcome (``BUDGET_EXHAUSTED``) exists purely as a safety net
for `IterateConfig.max_attempts_hard_cap` (a published, caller-overridable A-zone-style
bound, *not* a B-zone secret threshold -- mirrors `interventions.
DEFAULT_MAX_ROLLBACKS_PER_FORK_POINT`'s own "still caller-overridable, never silently
hardcoded past the constructor default" discipline): it fires only if the
same-signature streak never reaches the escalation limit yet the hard cap is exhausted
first (e.g. a worker that keeps failing with a *different* signature every attempt),
mirrors Stage11's own `force_budget_exhausted` fixture shape, and is exercised by this
module's own test suite but is not the WP's two named cases.

Determinism (Art 0.2): every function in this module is a total function of its
explicit arguments plus the caller-supplied `worker_fn` -- no wall-clock read, no RNG,
no hidden mutable module-level state. Replaying the same `task`/`worker_fn` sequence/
`config` twice against a fresh `out_dir` produces byte-identical tape bundles (proved
by `tests/test_econ_lab_iterate_harness.py::test_replay_is_byte_identical`).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

REPO = Path(__file__).resolve().parents[3]
ECON_LAB = REPO / "tools" / "econ_lab"
BENCH = REPO / "tools" / "bench"

if str(ECON_LAB) not in sys.path:
    sys.path.insert(0, str(ECON_LAB))

# Read-only reuse of the CAPSULE H components (per the WP red line: this module never
# edits anything under tools/econ_lab/monitor/).
from monitor import loop_detector as monitor_loop_detector  # noqa: E402
from monitor import termination as monitor_termination  # noqa: E402


class HarnessError(Exception):
    """Raised on a structurally invalid input (BLOCKED, never silently guessed/
    patched) -- mirrors `loop_detector.LoopDetectorError` / `termination.
    TerminationError`'s precedent: carries only structural fact text, never a
    B-zone parameter value."""


def _load_module(name: str, path: Path):
    """Load one of the `tools/bench/*.py` scripts by file path (they are standalone
    scripts, not an importable package) -- the exact pattern
    `tests/test_stage11_loop_until_pass.py::load_module` already uses."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise HarnessError(f"cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SMOKE = _load_module("_iterate_harness_stage11_tape_primitives", BENCH / "run_mini_swe_bench_substrate_smoke.py")
_WORKER_CTX = _load_module("_iterate_harness_worker_context", BENCH / "run_deepseek_arm_a_worker.py")
_TAPE_AUDITOR = _load_module("_iterate_harness_tape_auditor", BENCH / "audit_micro_tape_decision_dag.py")

load_worker_visible_context = _WORKER_CTX.load_worker_visible_context
classify_stage11_observed_signals = _SMOKE.classify_stage11_observed_signals
SWEBENCH_FORBIDDEN_PATHS = _SMOKE.SWEBENCH_FORBIDDEN_PATHS
LEGACY_COST_EVENT_SCHEMA = _SMOKE.LEGACY_COST_EVENT_SCHEMA


def digest_text(text: str) -> str:
    return _SMOKE.digest_text(text)


def digest_bytes(data: bytes) -> str:
    return _SMOKE.digest_bytes(data)


# ---------------------------------------------------------------------------
# Fact-only failure-memory content (ADR-ECON-007 Decision 3): the two allowed
# `failure_class` values this harness reuses from `classify_stage11_observed_signals`
# (a third, `SEMANTIC_FAIL`, is also reused) each map to one abstract-pattern fact and
# one guidance sentence -- pure prose, no digit/threshold/count, no bucket/tau/lambda
# vocabulary. Validated structurally (not just by convention) by
# `compose_failure_broadcast_content`'s own call to
# `monitor.termination.assert_report_has_no_bzone_leak` before any caller can embed
# the result in a tape payload.
# ---------------------------------------------------------------------------

_FAILURE_GUIDANCE: Dict[str, Tuple[str, str]] = {
    "WRONG_FILE": (
        "the previous attempt edited a file outside the scope the failing test implicates",
        "Focus edits on the module the failing test actually implicates; do not re-edit the file that was already tried and rejected.",
    ),
    "CONTEXT_MISSING": (
        "the previous attempt ran out of required source context before finishing the fix",
        "Read the worker-visible source context section before editing; do not guess at code that was never shown.",
    ),
    "SEMANTIC_FAIL": (
        "the previous attempt's patch applied but the target test still failed on semantic grounds",
        "Re-examine the expected behavior named by the failing test before re-attempting the same code path.",
    ),
}


def compose_failure_broadcast_content(failure_class: str, route_id: str) -> Tuple[str, str]:
    """Build `(abstract_pattern, guidance)` fact strings for one failed attempt's
    failure_class, then structurally validate them with the *same*
    `monitor.termination.assert_report_has_no_bzone_leak` scan Decision-4 falsification
    reports use (the WP brief's "过 termination.py 的 assert_report_has_no_bzone_leak
    同款扫描") -- raises `HarnessError` (never silently strips/patches) if the composed
    text would leak a B-zone token or an untraceable digit run."""
    if failure_class not in _FAILURE_GUIDANCE:
        raise HarnessError(f"no fact-only broadcast content registered for failure_class {failure_class!r}")
    abstract_pattern, guidance = _FAILURE_GUIDANCE[failure_class]
    probe_report = {
        "route_id": route_id,
        "attempts": [{"fact_class": "PRIOR_ATTEMPT_FAILURE", "failure_class": failure_class}],
        "verifier_evidence": [],
        "detector_events": [],
        "remaining_candidates": [],
        "recommendation": guidance,
    }
    try:
        monitor_termination.assert_report_has_no_bzone_leak(probe_report)
    except monitor_termination.RouteFalsificationError as exc:
        raise HarnessError(f"failure-memory broadcast content failed Decision-3 scan: {exc}") from exc
    return abstract_pattern, guidance


# ---------------------------------------------------------------------------
# Worker contract: the harness never assumes anything about how an attempt was
# produced (mock/offline for tests, a real CLI/API dispatch for the smoke run) -- it
# only consumes this envelope.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AttemptOutcome:
    """One attempt's result, as the harness's worker contract.

    `result`: "PASS" or "FAIL" (the official-evaluator-shaped verdict this attempt is
        credited with; the harness never infers PASS/FAIL any other way -- Decision 4's
        "任何终止路径必须携带验证器证据" applies at the attempt level too).
    `observed_signals`: the same observer-derived signal vocabulary
        `classify_stage11_observed_signals` reads (`diff_scope`/`timeout_kind`/
        `receipt_schema_status`/`official_evaluator_result`/`command_result`/
        `exit_code`/`macro_observation_kind`) -- required whenever `result == "FAIL"`.
    `edit_trace`: zero or more `monitor.loop_detector` event *fragments* (event_type +
        its own fields, `seq`/`instance_id`/`route_id` are assigned by the harness) --
        this is what feeds the detector "有机触发" (organic trip) case.
    `prompt_tokens`/`completion_tokens`/`tool_tokens`/`tool_stdout_tokens`: counted into
        this attempt's `CostEvent` (and therefore the final `PPUTAccounted.
        total_run_token_count` sum `audit_loop_until_pass.py` checks).
    `wall_time_ms`: this attempt's wall time, counted the same way.
    `patch_note`: one short fact-only sentence describing what this attempt tried (never
        a raw diff/log -- feeds a falsification report's `attempts[]` if this attempt is
        the one that triggers escalation).
    """

    result: str
    observed_signals: Mapping[str, Any] = field(default_factory=dict)
    edit_trace: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tool_tokens: int = 0
    tool_stdout_tokens: int = 0
    wall_time_ms: int = 1
    patch_note: str = "attempt produced a candidate patch"

    def __post_init__(self) -> None:
        if self.result not in ("PASS", "FAIL"):
            raise HarnessError(f"AttemptOutcome.result must be PASS or FAIL, got {self.result!r}")

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens + self.tool_tokens + self.tool_stdout_tokens


WorkerCallable = Callable[[int, str, Sequence[Mapping[str, Any]]], AttemptOutcome]
"""`(attempt_index, worker_visible_capsule_text, active_broadcast_rules) -> AttemptOutcome`."""


@dataclass(frozen=True)
class IterateConfig:
    """B-zone / A-zone injection point (ADR-ECON-007 Decision 3/6a): every threshold
    below is caller-supplied, never a literal in this module's control-flow (mirrors
    `monitor.loop_detector.LoopDetectorConfig`'s own discipline)."""

    route_id: str
    remaining_candidates: Sequence[str]
    loop_detector_config: monitor_loop_detector.LoopDetectorConfig
    # B-zone (Decision 6a): task-internal same-signature consecutive-failure limit.
    # PROVISIONAL fixture value per Decision 6a is 2 ("允许一次诚实重试") -- this field
    # has no default precisely so no call site can silently inherit an unstated
    # number; see `SAME_SIGNATURE_RETRY_LIMIT_FIXTURE_ADR007_DECISION_6A` below for the
    # one place that value is named, and only as an explicitly-imported fixture
    # constant, never a bare literal here.
    same_signature_retry_limit: int
    # A-zone-style published safety bound (not a B-zone secret; mirrors
    # `interventions.DEFAULT_MAX_ROLLBACKS_PER_FORK_POINT`'s own posture) -- guards
    # against a worker that keeps failing with a *different* signature every attempt
    # and would otherwise never hit the same-signature escalation path.
    max_attempts_hard_cap: int = 8
    broadcast_section_mode: str = "always"

    def __post_init__(self) -> None:
        if self.same_signature_retry_limit < 1:
            raise HarnessError("same_signature_retry_limit must be >= 1")
        if self.max_attempts_hard_cap < 2:
            raise HarnessError("max_attempts_hard_cap must be >= 2 (attempt 1 is always the bad route)")


# ADR-ECON-007 Decision 6a's own PROVISIONAL fixture value, named once here (never a
# bare literal at any `IterateConfig(...)` call site in this module or its tests) --
# "临时阈值(PROVISIONAL,B 区存放,agent 不可见): (a) 任务内(迭代 harness): 同签名失败
# 尝试连续 2 次...升级到路线重选". Decision 6a's own sunset clause applies (re-calibrate
# after 200 organic iterations); this constant is the harness-side placeholder until
# that ADR revision lands.
SAME_SIGNATURE_RETRY_LIMIT_FIXTURE_ADR007_DECISION_6A = 2


def consecutive_same_signature_count(failure_signatures: Sequence[Tuple[str, str]]) -> int:
    """Pure function (Art 0.2): the trailing run-length of identical
    `(failure_class, abstract_pattern)` entries at the end of `failure_signatures`
    (chronological, one entry per failed attempt so far, including the most recent).
    Mirrors `interventions.count_prior_rollbacks_at_fork_point`'s own "derive from the
    replayed list, never a hidden mutable counter" discipline."""
    if not failure_signatures:
        return 0
    last = failure_signatures[-1]
    count = 0
    for signature in reversed(failure_signatures):
        if signature != last:
            break
        count += 1
    return count


# ---------------------------------------------------------------------------
# Detector trajectory stream helpers (append-only; never rewritten -- Decision 1's
# ledger discipline applied to this harness-local stream too).
# ---------------------------------------------------------------------------


def _append_detector_events(
    stream: List[Dict[str, Any]],
    fragments: Sequence[Mapping[str, Any]],
    *,
    instance_id: str,
    route_id: str,
) -> List[Dict[str, Any]]:
    appended = list(stream)
    next_seq = (max((e["seq"] for e in appended), default=-1)) + 1
    for fragment in fragments:
        event = dict(fragment)
        event["seq"] = next_seq
        event["instance_id"] = instance_id
        event["route_id"] = route_id
        appended.append(event)
        next_seq += 1
    return appended


def _phase_fragment(phase: str, boundary: str) -> Dict[str, Any]:
    return {"event_type": "phase_boundary", "phase": phase, "boundary": boundary}


def _verification_fragment(result: str, *, phase: str = "attempt") -> Dict[str, Any]:
    return {"event_type": "verification", "phase": phase, "result": result}


def _termination_fragment(reason_class: str, *, phase: str = "attempt") -> Dict[str, Any]:
    return {"event_type": "termination", "phase": phase, "reason_class": reason_class}


# ---------------------------------------------------------------------------
# The harness itself.
# ---------------------------------------------------------------------------


def run_iterate_harness(
    *,
    out_dir: Path,
    task: Dict[str, Any],
    worker_fn: WorkerCallable,
    config: IterateConfig,
    capsule_path: Path,
    source_context_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Run one task through the iterate-until-pass loop and return a run record shaped
    to match `tools/bench/audit_loop_until_pass.py`'s `audit_run` exactly on the
    CONVERGED path (see this module's docstring for the three possible
    `outcome_status` values)."""

    instance_id = task["instance_id"]
    auditor = _TAPE_AUDITOR
    registry = auditor.load_event_registry()
    instance_dir = out_dir / "turingos" / "instances" / instance_id
    repo = instance_dir / "micro.git"
    bundle = instance_dir / "micro_tape.bundle"
    if repo.exists():
        shutil.rmtree(repo)
    instance_dir.mkdir(parents=True, exist_ok=True)
    init = _SMOKE.run_cmd(["git", "init", "--object-format=sha256", str(repo)], timeout=120)
    if init.returncode != 0:
        raise HarnessError(f"iterate harness git init failed:\n{init.stderr}")

    state = _SMOKE.stage6_base_state()
    short = hashlib.sha256(instance_id.encode("utf-8")).hexdigest()[:16]
    worker_id = "worker:sha256:" + hashlib.sha256(f"iterate:{instance_id}:worker".encode("utf-8")).hexdigest()
    atom_id = f"atom_iterate_{short}"
    market_id = f"mkt_iterate_{short}"
    candidate_id = f"cand_iterate_{short}"
    run_id = f"run_iterate_{short}"

    def append(event_type: str, payload: Dict[str, Any], writer_id: str, **kwargs: Any) -> Dict[str, Any]:
        return _SMOKE.append_stage6_event(
            repo=repo,
            state=state,
            registry=registry,
            canonical_payload_digest=auditor.canonical_payload_digest,
            event_type=event_type,
            payload=payload,
            writer_id=writer_id,
            **kwargs,
        )

    append("SystemConstitutionAccepted", {"constitution_digest": digest_text("iterate-harness constitution")}, "writer:bootstrap")
    append(
        "GoalStateProposed",
        {
            "goal_id": f"goal_iterate_{short}",
            "objective": "WP-L3-1 task-internal iterate-until-pass loop",
            "task_source": "iterate_harness",
        },
        "writer:goal",
    )
    append(
        "AtomAuthorized",
        {
            "atom_id": atom_id,
            "approval_id": f"ap_atom_iterate_{short}",
            "authority_kind": "test_local_authority_no_credentials",
            "signature_route": "test_local_authority",
        },
        "writer:test-local-authority",
    )
    append(
        "MarketCreated",
        {
            "schema_id": "market_created.v1",
            "market_id": market_id,
            "initial_pool_y": "100",
            "initial_pool_n": "100",
            "k": "10000",
            "truth_status": "statistical_signal_only",
        },
        "writer:market",
    )

    detector_stream: List[Dict[str, Any]] = []
    detector_trips: List[Dict[str, Any]] = []
    active_broadcast_rules: List[Dict[str, Any]] = []
    failure_signatures: List[Tuple[str, str]] = []
    attempt_capsule_event_ids: Dict[int, str] = {}
    total_tokens = 0
    total_wall_ms = 0
    first_failure_event: Optional[Dict[str, Any]] = None
    latest_certificate_event: Optional[Dict[str, Any]] = None
    latest_broadcast_event: Optional[Dict[str, Any]] = None
    first_retry_event: Optional[Dict[str, Any]] = None
    fail_official_events: List[Dict[str, Any]] = []
    fail_receipt_events: List[Dict[str, Any]] = []
    attempts_facts: List[Dict[str, Any]] = []
    retry_event: Optional[Dict[str, Any]] = None
    outcome_status = "BUDGET_EXHAUSTED"
    terminal_event: Optional[Dict[str, Any]] = None
    official_pass_event: Optional[Dict[str, Any]] = None
    termination_outcome = None

    attempt_index = 0
    while attempt_index < config.max_attempts_hard_cap:
        attempt_index += 1
        capsule_id = f"wc_iterate_{short}_attempt{attempt_index}"

        capsule_payload: Dict[str, Any] = {
            "capsule_id": capsule_id,
            "private_contract_hash": digest_text(f"{capsule_id}:private"),
            "acceptance_commands": ["iterate_harness.official.eval"],
            "allowed_files": task.get("allowed_files", ["**"]),
            "forbidden_files": SWEBENCH_FORBIDDEN_PATHS,
            "attempt_index": attempt_index,
            "raw_log_text_absent": True,
            "hidden_predicates_absent": True,
            "pput_or_heldout_details_absent": True,
        }
        if attempt_index == 1:
            capsule_payload["pput_formula_absent"] = True
            capsule_payload["heldout_ids_absent"] = True
        else:
            assert first_failure_event is not None and retry_event is not None and latest_broadcast_event is not None
            capsule_payload["source_failure_nodes"] = [first_failure_event["event_id"]]
            capsule_payload["visible_known_failures_to_avoid"] = [rule["guidance"] for rule in active_broadcast_rules]
            capsule_payload["consumed_broadcast_rule_ids"] = [rule["rule_id"] for rule in active_broadcast_rules]
            capsule_payload["injected_broadcast_rule_ids"] = [rule["rule_id"] for rule in active_broadcast_rules]
            capsule_payload["broadcast_rule_event_id"] = latest_broadcast_event["event_id"]

        capsule_event = append("WorkCapsuleBuilt", capsule_payload, "writer:capsule", name=f"capsule_attempt{attempt_index}")
        attempt_capsule_event_ids[attempt_index] = capsule_event["event_id"]

        dispatch_payload: Dict[str, Any] = {
            "capsule_id": capsule_id,
            "worker_id": worker_id,
            "approval_id": f"ap_dispatch_iterate_{short}_attempt{attempt_index}",
            "authority_kind": "test_local_authority_no_credentials",
            "signature_route": "test_local_authority",
        }
        if attempt_index > 1:
            assert retry_event is not None
            dispatch_payload["retry_authorization_event_id"] = retry_event["event_id"]
        append("WorkerDispatchAuthorized", dispatch_payload, "writer:test-local-authority", name=f"dispatch_attempt{attempt_index}")

        # Rematerialize the worker-visible capsule + failure-memory broadcast section
        # fresh from disk every round (WP brief: "每轮迭代重物化 source_context + 失败
        # 记忆 broadcast 节") -- never cached across attempts.
        capsule_text, _source_context_metadata = load_worker_visible_context(
            capsule_path,
            source_context_name=source_context_name,
            broadcast_rules=active_broadcast_rules,
            broadcast_section_mode=config.broadcast_section_mode,
        )

        outcome = worker_fn(attempt_index, capsule_text, tuple(active_broadcast_rules))

        detector_stream = _append_detector_events(
            detector_stream,
            [_phase_fragment("attempt", "start"), *outcome.edit_trace],
            instance_id=instance_id,
            route_id=config.route_id,
        )

        receipt_id = f"rcp_iterate_{short}_attempt{attempt_index}"
        macro_id = f"macro:diff:iterate:{short}:attempt{attempt_index}"
        patch_hash = digest_text(f"{instance_id}:iterate:attempt{attempt_index}:patch")
        total_tokens += outcome.total_tokens
        total_wall_ms += outcome.wall_time_ms

        append(
            "CostEvent",
            {
                "schema_id": LEGACY_COST_EVENT_SCHEMA,
                "run_id": run_id,
                "problem_id": instance_id,
                "split": "iterate_harness",
                "agent_id": worker_id,
                "branch_id": f"branch_iterate_{short}_attempt{attempt_index}",
                "capsule_id": capsule_id,
                "prompt_tokens": outcome.prompt_tokens,
                "completion_tokens": outcome.completion_tokens,
                "tool_tokens": outcome.tool_tokens,
                "tool_stdout_tokens": outcome.tool_stdout_tokens,
                "total_tokens": outcome.total_tokens,
                "wall_time_ms": outcome.wall_time_ms,
                "tool_stdout_hash": digest_text(f"{instance_id}:iterate:attempt{attempt_index}:tool-stdout"),
                "counted_in_total": True,
            },
            "writer:pput",
        )
        receipt_event = append(
            "WorkerReceiptImported",
            {
                "receipt_id": receipt_id,
                "capsule_id": capsule_id,
                "worker_id": worker_id,
                "exit_code": outcome.observed_signals.get("exit_code", 0 if outcome.result == "PASS" else 1),
                "stdout_hash": digest_text(f"{instance_id}:iterate:attempt{attempt_index}:stdout"),
                "stderr_hash": digest_text(f"{instance_id}:iterate:attempt{attempt_index}:stderr"),
                "done_json_hash": digest_text(f"{instance_id}:iterate:attempt{attempt_index}:done"),
                "credential_material_absent": True,
                "manual_patch": False,
                "micro_refs_moved": False,
                "patch_hash": patch_hash,
                "observed_signals_hash": digest_text(json.dumps(dict(outcome.observed_signals), sort_keys=True)),
            }
            | ({"consumed_broadcast_rule_event_id": latest_broadcast_event["event_id"]} if attempt_index > 1 and latest_broadcast_event else {}),
            "writer:receipt",
        )
        append(
            "MacroObservationImported",
            {
                "macro_id": macro_id,
                "capsule_id": capsule_id,
                "diff_hash": patch_hash,
                "external_evidence_only": True,
                "macro_observation_kind": outcome.observed_signals.get(
                    "macro_observation_kind", "repair_patch" if outcome.result == "PASS" else "patch_failed"
                ),
            },
            "writer:macro",
        )

        evidence_id = f"ev_iterate_{short}_attempt{attempt_index}"
        official_event = append(
            "OfficialEvaluatorEvidenceImported",
            {
                "schema_id": "official_evaluator_evidence_imported.v1",
                "evidence_id": evidence_id,
                "instance_id": instance_id,
                "capsule_id": capsule_id,
                "macro_anchor_id": macro_id,
                "worker_receipt_id": receipt_id,
                "candidate_patch_hash": patch_hash,
                "test_patch_hash": digest_text(f"{instance_id}:iterate:test-patch"),
                "apply_candidate_result": "PASS",
                "apply_test_patch_result": "PASS",
                "fail_to_pass_labels": [],
                "target_test_exit_code": 0 if outcome.result == "PASS" else 1,
                "target_test_result": outcome.result,
                "stdout_hash": digest_text(f"{instance_id}:iterate:attempt{attempt_index}:official-stdout"),
                "stderr_hash": digest_text(f"{instance_id}:iterate:attempt{attempt_index}:official-stderr"),
                "result": outcome.result,
                "failure_class": None if outcome.result == "PASS" else classify_stage11_observed_signals(outcome.observed_signals),
                "forbidden_test_edit_detected": False,
                "forbidden_test_edit_paths": [],
                "truth_source": "iterate_harness_deterministic_official_fixture",
            },
            "writer:official-evaluator",
            name=f"official_attempt{attempt_index}",
        )

        detector_stream = _append_detector_events(
            detector_stream,
            [_verification_fragment("pass" if outcome.result == "PASS" else "fail"), _phase_fragment("attempt", "end")],
            instance_id=instance_id,
            route_id=config.route_id,
        )
        new_trips = monitor_loop_detector.find_all_trips(detector_stream, config.loop_detector_config)
        detector_trips = [trip.to_dict() for trip in new_trips]

        if outcome.result == "PASS":
            official_pass_event = official_event
            append(
                "PPUTAccounted",
                {
                    "schema_id": "pput_accounted.v1",
                    "run_id": run_id,
                    "problem_id": instance_id,
                    "split": "iterate_harness",
                    "solved": True,
                    "verified": True,
                    "accounting_stage": "progress",
                    "basis_event_id": official_event["event_id"],
                    "terminal_event_id": official_event["event_id"],
                    "golden_path_token_count": 0,
                    "total_run_token_count": outcome.total_tokens,
                    "total_wall_time_ms": outcome.wall_time_ms,
                    "total_run_cost_microusd": 0,
                    "progress": 1,
                    "vpput_raw": "0",
                    "failed_branch_count": len(fail_receipt_events),
                    "hidden_from_worker_prompt": True,
                },
                "writer:pput",
            )
            terminal_event = append(
                "CandidateAccepted",
                {
                    "candidate_id": candidate_id,
                    "capsule_id": capsule_id,
                    "macro_anchor_id": macro_id,
                    "worker_receipt_id": receipt_id,
                    "official_evaluator_evidence_id": evidence_id,
                    "consumed_broadcast_rule_event_id": latest_broadcast_event["event_id"] if latest_broadcast_event else None,
                },
                "writer:predicate",
                name="terminal",
            )
            outcome_status = "CONVERGED"
            break

        # FAIL branch.
        fail_official_events.append(official_event)
        fail_receipt_events.append(receipt_event)
        failure_class = classify_stage11_observed_signals(outcome.observed_signals)
        abstract_pattern, guidance = compose_failure_broadcast_content(failure_class, config.route_id)
        classifier_decision = {
            "failure_class": failure_class,
            "observer_derived_failure_class": True,
            "classifier_inputs": dict(outcome.observed_signals),
            "classifier_input_sources": [
                "WorkerReceiptImported.exit_code",
                "OfficialEvaluatorEvidenceImported.result",
                "MacroObservationImported.macro_observation_kind",
            ],
            "forbidden_classifier_inputs_absent": [
                "scenario_label",
                "fixture_name",
                "instance_id_label",
                "problem_title",
                "expected_failure_class",
            ],
        }
        failure_node = append(
            "FailureNode",
            {
                "capsule_id": capsule_id,
                "candidate_id": candidate_id,
                "failure_class": failure_class,
                "detail": f"Iterate-harness attempt {attempt_index} failed and was classified from observer signals.",
                "official_evaluator_evidence_id": evidence_id,
                "classifier_decision": classifier_decision,
            },
            "writer:predicate",
            product="NOT_RUN",
            name=f"failure_attempt{attempt_index}",
        )
        if first_failure_event is None:
            first_failure_event = failure_node
        append(
            "PPUTAccounted",
            {
                "schema_id": "pput_accounted.v1",
                "run_id": run_id,
                "problem_id": instance_id,
                "split": "iterate_harness",
                "solved": False,
                "verified": False,
                "accounting_stage": "progress",
                "basis_event_id": official_event["event_id"],
                "terminal_event_id": failure_node["event_id"],
                "golden_path_token_count": 0,
                "total_run_token_count": outcome.total_tokens,
                "total_wall_time_ms": outcome.wall_time_ms,
                "total_run_cost_microusd": 0,
                "progress": 0,
                "vpput_raw": "0",
                "failed_branch_count": len(fail_receipt_events),
                "hidden_from_worker_prompt": True,
            },
            "writer:pput",
        )

        rule_id = f"br_iterate_{short}_attempt{attempt_index}"
        certificate = append(
            "FailureCertificate",
            {
                "certificate_id": f"fc_iterate_{short}_attempt{attempt_index}",
                "source_failure_node_id": failure_node["event_id"],
                "failure_class": failure_class,
                "abstract_pattern": abstract_pattern,
                "classifier_decision_hash": digest_text(json.dumps(classifier_decision, sort_keys=True)),
                "raw_log_ref": "cas:" + hashlib.sha256(f"{instance_id}:iterate:attempt{attempt_index}:private-log".encode("utf-8")).hexdigest(),
                "raw_log_text_absent": True,
                "broadcast_rule_candidate": {
                    "rule_id": rule_id,
                    "candidate_only": True,
                    "activation_event_id": None,
                    "source_failure_nodes": [failure_node["event_id"]],
                    "failure_class": failure_class,
                    "abstract_pattern": abstract_pattern,
                    "new_instruction": guidance,
                    "raw_log_text_absent": True,
                    "hidden_predicates_absent": True,
                    "pput_or_heldout_details_absent": True,
                },
            },
            "writer:failure-taxonomy",
            name=f"certificate_attempt{attempt_index}",
        )
        latest_certificate_event = certificate
        broadcast = append(
            "BroadcastRuleActivated",
            {
                "rule_id": rule_id,
                "source_failure_nodes": [failure_node["event_id"]],
                "failure_certificate_event_id": certificate["event_id"],
                "failure_class": failure_class,
                "abstract_pattern": abstract_pattern,
                "new_instruction": guidance,
                "recipients": ["future_capsule"],
                "hidden_details_removed": True,
                "raw_log_refs": ["cas:" + hashlib.sha256(f"{instance_id}:iterate:attempt{attempt_index}:private-log".encode("utf-8")).hexdigest()],
                "raw_log_refs_private_only": True,
                "raw_log_text_absent": True,
                "hidden_predicates_absent": True,
                "pput_or_heldout_details_absent": True,
            },
            "writer:failure-memory",
            name=f"broadcast_attempt{attempt_index}",
        )
        latest_broadcast_event = broadcast
        active_broadcast_rules.append({"rule_id": rule_id, "failure_class": failure_class, "guidance": guidance})
        failure_signatures.append((failure_class, abstract_pattern))
        attempts_facts.append(
            {
                "fact_class": "ATTEMPT_FAILED",
                "attempt_index": str(attempt_index),
                "failure_class": failure_class,
                "note": outcome.patch_note,
            }
        )

        streak = consecutive_same_signature_count(failure_signatures)
        if streak >= config.same_signature_retry_limit:
            verifier_evidence = [{"phase": None, "result": "fail"} for _ in fail_official_events]
            detector_events_facts = [
                {"fact_class": "DETECTOR_TRIP", "rule_id": trip["rule_id"], "evidence": dict(trip["evidence"])}
                for trip in detector_trips
            ]
            recommendation = (
                "The same failure signature repeated on consecutive attempts of this route; "
                "recommend GRILL-ME review of the remaining route candidates before further dispatch."
            )
            termination_outcome = monitor_termination.terminate_falsified(
                route_id=config.route_id,
                attempts=attempts_facts,
                verifier_evidence=verifier_evidence,
                detector_events=detector_events_facts,
                remaining_candidates=config.remaining_candidates,
                recommendation=recommendation,
                seq=len(detector_stream),
            )
            detector_stream = _append_detector_events(
                detector_stream,
                [_termination_fragment("ESCALATED")],
                instance_id=instance_id,
                route_id=config.route_id,
            )
            outcome_status = "ESCALATED"
            break

        retry_event = append(
            "RetryAuthorized",
            {
                "retry_id": f"retry_iterate_{short}_attempt{attempt_index}",
                "capsule_id": f"wc_iterate_{short}_attempt{attempt_index + 1}",
                "source_failure_node_id": failure_node["event_id"],
                "broadcast_rule_event_id": broadcast["event_id"],
                "retry_decision_source": "tape_policy",
                "approval_id": f"ap_retry_iterate_{short}_attempt{attempt_index}",
                "authority_kind": "test_local_authority_no_credentials",
                "signature_route": "test_local_authority",
                "human_intervention_count": 0,
            },
            "writer:test-local-authority",
            name=f"retry_attempt{attempt_index}",
        )
        if first_retry_event is None:
            first_retry_event = retry_event
        # continue loop -> next attempt

    if outcome_status == "BUDGET_EXHAUSTED":
        # Hard-cap safety net only (see module docstring): the same-signature streak
        # never reached the escalation limit before max_attempts_hard_cap ran out.
        settlement_basis = fail_official_events[-1] if fail_official_events else None
        terminal_event = first_failure_event
        settlement = append(
            "MarketSettled",
            {
                "schema_id": "market_settled.v1",
                "market_id": market_id,
                "result": "NO",
                "settlement_basis_event_id": settlement_basis["event_id"] if settlement_basis else None,
                "basis_kind": "official_eval",
                "terminal_event_id": terminal_event["event_id"] if terminal_event else None,
                "is_terminal": True,
                "price_not_truth_ack": True,
            },
            "writer:market",
            name="settlement",
        )
        append(
            "RewardDistributed",
            {
                "schema_id": "reward_distributed.v1",
                "event_type": "RewardDistributed",
                "market_id": market_id,
                "agent_id": worker_id,
                "reward_coin": "0",
                "slash_coin": "1",
                "reason": "BUDGET_EXHAUSTED",
                "settlement_event_id": settlement["event_id"],
            },
            "writer:market",
        )
        append(
            "PPUTAccounted",
            {
                "schema_id": "pput_accounted.v1",
                "run_id": run_id,
                "problem_id": instance_id,
                "split": "iterate_harness",
                "solved": False,
                "verified": False,
                "accounting_stage": "final",
                "basis_event_id": settlement_basis["event_id"] if settlement_basis else None,
                "terminal_event_id": terminal_event["event_id"] if terminal_event else None,
                "golden_path_token_count": 0,
                "total_run_token_count": total_tokens,
                "total_wall_time_ms": total_wall_ms,
                "total_run_cost_microusd": 0,
                "progress": 0,
                "vpput_raw": "0",
                "failed_branch_count": len(fail_receipt_events),
                "hidden_from_worker_prompt": True,
            },
            "writer:pput",
        )
    elif outcome_status == "CONVERGED":
        assert terminal_event is not None and official_pass_event is not None
        settlement = append(
            "MarketSettled",
            {
                "schema_id": "market_settled.v1",
                "market_id": market_id,
                "result": "YES",
                "settlement_basis_event_id": official_pass_event["event_id"],
                "basis_kind": "official_eval",
                "terminal_event_id": terminal_event["event_id"],
                "is_terminal": True,
                "price_not_truth_ack": True,
            },
            "writer:market",
            name="settlement",
        )
        append(
            "RewardDistributed",
            {
                "schema_id": "reward_distributed.v1",
                "event_type": "RewardDistributed",
                "market_id": market_id,
                "agent_id": worker_id,
                "reward_coin": "1",
                "slash_coin": "0",
                "reason": "PREDICATE_SETTLEMENT",
                "settlement_event_id": settlement["event_id"],
            },
            "writer:market",
        )
        append(
            "PPUTAccounted",
            {
                "schema_id": "pput_accounted.v1",
                "run_id": run_id,
                "problem_id": instance_id,
                "split": "iterate_harness",
                "solved": True,
                "verified": True,
                "accounting_stage": "final",
                "basis_event_id": official_pass_event["event_id"],
                "terminal_event_id": terminal_event["event_id"],
                "golden_path_token_count": total_tokens,
                "total_run_token_count": total_tokens,
                "total_wall_time_ms": total_wall_ms,
                "total_run_cost_microusd": 0,
                "progress": 1,
                "vpput_raw": _SMOKE.stage6_vpput(1, total_tokens, total_wall_ms),
                "failed_branch_count": len(fail_receipt_events),
                "hidden_from_worker_prompt": True,
            },
            "writer:pput",
        )
    # ESCALATED: no MarketSettled/RewardDistributed/final-PPUT/CandidateAccepted --
    # Decision 4's "放弃" path is a `RouteFalsified` proposal_only report, not a
    # settlement (nothing here advances accepted_head for this route).

    append(
        "PredicateEvaluated",
        {
            "predicate_id": "predicate.iterate_harness.replay",
            "result": "PASS",
            "source_tape_tip": state["tape_tip"],
            "replay_hash": digest_text("iterate harness replay:" + instance_id),
        },
        "writer:replay",
        product="NOT_RUN",
    )

    create = _SMOKE.run_cmd(["git", "bundle", "create", str(bundle.resolve()), "--all"], cwd=repo, timeout=120)
    if create.returncode != 0:
        raise HarnessError(f"iterate harness bundle create failed:\n{create.stderr}")
    bundle_hash = digest_bytes(bundle.read_bytes())
    shutil.rmtree(repo)

    attempts_total = attempt_index
    loop_until_pass: Optional[Dict[str, Any]] = None
    if outcome_status == "CONVERGED":
        assert first_failure_event is not None
        assert latest_certificate_event is not None
        assert latest_broadcast_event is not None
        assert first_retry_event is not None
        assert terminal_event is not None
        loop_until_pass = {
            "status": "PASS",
            "human_intervention_count": 0,
            "manual_patch_count": 0,
            "manual_approval_count": 0,
            "manual_rerun_selection_count": 0,
            "fallback_to_auto_authorization": False,
            "attempts_total": attempts_total,
            "failed_attempts_before_accept": len(fail_receipt_events),
            "first_failed_attempt_index": 1,
            "accepted_attempt_index": attempts_total,
            "budget_exhausted": False,
            "retry_decision_source": "tape_policy",
            "retry_policy_event_id": first_retry_event["event_id"],
            "first_failure_event_id": first_failure_event["event_id"],
            "failure_certificate_event_id": latest_certificate_event["event_id"],
            "broadcast_rule_activated_event_id": latest_broadcast_event["event_id"],
            "second_attempt_capsule_event_id": attempt_capsule_event_ids[2],
            "terminal_candidate_accepted_event_id": terminal_event["event_id"],
            "accepted_head": state["accepted_head"],
            "verified_from_micro_tape_bundle_only": True,
        }
        loop_until_pass["accepted_head"] = terminal_event["event_id"]

    run_record: Dict[str, Any] = {
        "instance_id": instance_id,
        "outcome_status": outcome_status,
        "route_id": config.route_id,
        "authorization_mode": "required",
        "micro_tape_bundle": str(bundle),
        "micro_tape_bundle_sha256": bundle_hash,
        "accepted_head": state["accepted_head"],
        "authorization_head": state["authorization_head"],
        "tape_tip": state["tape_tip"],
        "worker_id": worker_id,
        "market_id": market_id,
        "attempts_total": attempts_total,
        "detector_trips": detector_trips,
        "detector_stream_length": len(detector_stream),
        "basis": "iterate_harness_wp_l3_1",
    }
    if loop_until_pass is not None:
        run_record["loop_until_pass"] = loop_until_pass
    if outcome_status == "ESCALATED":
        assert termination_outcome is not None
        run_record["route_falsified_event"] = termination_outcome.event
        run_record["route_falsification_report"] = termination_outcome.report
    return run_record


def build_coverage(runs: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Wrap `run_iterate_harness` records into the
    `turingos_arm_runs`-shaped coverage document `audit_loop_until_pass.py --coverage`
    expects (its `audit_coverage` reads `coverage["turingos_arm_runs"]`)."""
    return {
        "schema_id": "IterateHarnessCoverage.v1",
        "run_id": "iterate_harness",
        "truth_source": "fresh_micro_tape_bundles",
        "scientific_status": "ITERATE_HARNESS_LOOP_FIXTURE_NOT_SOLVE_RATE",
        "sample_size": len(runs),
        "turingos_arm_runs": [dict(run) for run in runs],
    }


def write_json(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
