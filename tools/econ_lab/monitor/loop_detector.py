"""WP-H1 (ADR-ECON-007 `adr/ADR-ECON-007-route-market-loop-remedy.md` Decision 2;
design doc `research/RES_ROUTE_lockIn_remedy_design_20260710.md` §2 L1.1 rule 1): the
external loop detector -- a rule-based *pure function* over a trajectory event stream,
"外部于 worker" (never the worker's own self-report; the design doc's frontier evidence
puts LLM self-diagnosis accuracy at ~11%, so this module never reads a worker-authored
verdict as a trigger source).

Constitutional placement (Decision 2, Art I.1.1/F1): this detector **never writes Q**.
Its only output is a structural judgment -- ``{tripped, rule_id, evidence}`` -- for a
caller (WP-H2's diagnostic-injection/rollback consumer) to act on. The economy's only Q
update source remains the independent verifier settlement path (unchanged, untouched by
this module). Nothing here constructs, mutates, or references `EconomyEvent`,
`BudgetSuggestion`, or any other `crates/turing-economy` type -- this is a harness-side
Python analysis primitive, not a kernel change.

Determinism (Art 0.2): every function below is a total function of its explicit
arguments. No wall-clock read (`time.time`/`datetime.now`), no RNG, no hidden mutable
global. "Elapsed" facts used by the phase-timeout rule are `seq` deltas *carried in the
input event stream itself* (assigned once by whatever produced the trajectory, replayed
here as literal data) -- never read live by this module. Given the same event list and
the same config twice, `detect`/`find_all_trips` return byte-identical results.

B-zone discipline (ADR-ECON-007 Decision 3; Art III.4/F4): the detector's numeric
thresholds (how many consecutive same-fragment failures, how wide the repeat-signature
window, how many repeats within it, how many steps a phase may stay open) are exactly
the "τ/λ/地板/桶键/检测器阈值数值" family Decision 3 puts in the B-zone -- existence
public, values secret, "否则 agent 可精确规避熔断". This module therefore never
hardcodes a single one of those numbers: `LoopDetectorConfig` is 100% caller-supplied,
sourced from the B-zone config layer at the call site. The only concrete numbers in this
*file* live in the test fixtures below (`if __name__` blocks / `tests/`), and those
fixture values are honestly labeled harness-invented placeholders, not economic
constants -- see the fixture docstrings for why (the design doc explicitly marks these
specific thresholds as an unresolved, uncited "开放问题→内部实验", §5, so unlike
`crates/turing-economy/src/routing_fold.rs`'s `AnnealConfig` test fixture -- which *is*
allowed to mirror the real ADR-ECON-003 Decision 5 starting values because those are
public A-zone-adjacent constants -- nothing here may claim to mirror a pinned number,
because none exists yet).

Diagnostic-content discipline (ADR-ECON-007 Decision 3): every `LoopTrip.evidence`
dict below carries only failure *facts* Decision 3 allows agents to see -- which
file/fragment, which action signature, which phase, which failure category, what was
already tried -- and never a count, a threshold, an elapsed duration, or any other
B-zone quantity. In particular no evidence dict ever says "triggered the Nth time";
the diagnostic vocabulary matches Decision 3's own example: "检测到循环" (loop
detected), not "第 N 次触发".

-------------------------------------------------------------------------------------
Event-stream format: empirical derivation (per WP-H1 spec: "格式先从既有 runs/*/
task_runs 与 verdict 结构实证提取并文档化")
-------------------------------------------------------------------------------------

`tools/econ_lab`'s existing on-disk trajectory artifacts (inspected under
`tools/econ_lab/runs/stageA_20260707/*/task_runs/**` for this WP) are the empirical
anchor for every field name below:

  * `worker_receipt.json` (schema `turingos.wp9a.live_driver_siliconflow_worker_receipt.
    v1`, e.g. `tau_0/task_runs/astropy__astropy-13579/deepseek/worker_receipt.json`)
    carries `instance_id`, `lineage`, `arm`, `status` ("COMPLETED"), `wall_time_ms`.
  * `settlement.json` (schema `econ_lab.live_driver.settlement_checkpoint.v1`, e.g.
    `tau_0p5/task_runs/pytest-dev__pytest-5787/settlement.json`) carries
    `instance_id`, `domain_bucket`, `selected_route_id` (`"{instance_id}::{arm}::
    {lineage}"`), and a `dispatches[]` list whose each element carries
    `worker_result.status` (`COMPLETED`|`ERROR`), `worker_result.primary_attempt_status`,
    `scoring_result.status` (`COMPLETED`|`SCORING_FAILED`|`SKIPPED_NO_PATCH`),
    `scoring_result.resolved` (bool), `live_split_verdict.{accept_verdict,verify_verdict}`
    (bool, present only once the independent verifier actually ran), and
    `backup_update.applied` (bool).

Empirically, **no currently-persisted artifact records a per-edit/per-command event
trace** (no file/fragment-level "tried X, failed, tried Y" log exists yet in
`tools/econ_lab/runs/**`) -- `armB`'s `source_context_loop_repair` "loop" is a prompt
*scaffold* label (`decomposition_kind`), not a recorded multi-turn interaction log.
This is a genuine spec gap in the *existing artifacts*, reported rather than papered
over: WP-H1's job (per ADR-ECON-007 Decision 2 / design doc L1.1) is to define the
*consumer contract* new instrumentation must emit, not to reverse-engineer a trace
format that does not exist on disk today. The envelope below is therefore built by
extending the real field-naming conventions found above (snake_case, `instance_id`,
`route_id` = `"{instance_id}::{arm}::{lineage}"`, `schema` version tags, `status`
enums, an explicit monotonic ordering key) into the smallest event vocabulary the four
L1.1 rules need. [`events_from_real_settlement_checkpoint`][] below is the empirical
format-fit proof: it translates a real, unmodified `settlement.json` (copied verbatim
into `tools/econ_lab/monitor/fixtures/`, see its own docstring for the source path and
sha256) into this envelope losslessly with respect to the facts the four rules read,
and one of that translation's outputs genuinely trips a rule (see the fixture test).

Event envelope (every element of the input JSON array is one such object):

  Common fields (every event):
    seq            int    -- 0-based, strictly increasing across the whole stream;
                              assigned once by the producer, replayed here as data
                              (never generated by this module).
    event_type     str    -- one of EVENT_TYPES below.
    instance_id    str    -- empirical: `settlement.json`/`worker_receipt.json`
                              `instance_id`.
    route_id       str | None -- empirical: `settlement.json` `selected_route_id`
                              (`"{instance_id}::{arm}::{lineage}"`).

  event_type == "edit" (a single file/fragment change attempt):
    file_path         str
    fragment_id        str | None  -- e.g. hunk/function identifier, optional
    action_signature    str         -- normalized/hashed identity of *what was tried*
                                        (e.g. a diff-shape digest); used by the
                                        repeat-signature-window rule.
    outcome             str         -- one of EDIT_OUTCOMES.

  event_type == "command" (a non-edit tool/shell invocation attempt):
    action_signature    str
    outcome             str  -- one of EDIT_OUTCOMES (same vocabulary; empirical:
                                 `worker_result.status` COMPLETED/ERROR collapses onto
                                 "succeeded"/"failed" for exactly this purpose).

  event_type == "phase_boundary" (execution stage marker, e.g. "dispatch"/"scoring"):
    phase       str
    boundary    str  -- "start" | "end".

  event_type == "verification" (empirical: `scoring_result`/`live_split_verdict`
  actually ran and returned a verdict -- evidence *existing*, independent of whether
  that verdict was pass or fail):
    phase       str | None
    result      str  -- one of VERIFICATION_RESULTS.

  event_type == "termination" (the trajectory/phase ended -- success or abandonment):
    phase           str | None
    reason_class    str  -- a short fact label, e.g. "COMPLETED" | "ERROR"; never a
                             B-zone value, only a category (Decision 3).
"""
from __future__ import annotations

import json
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Deque, Dict, Iterator, List, Mapping, MutableMapping, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Event vocabulary (documented above; enforced defensively, not just advisory).
# ---------------------------------------------------------------------------

EVENT_TYPES = ("edit", "command", "phase_boundary", "verification", "termination")
EDIT_OUTCOMES = ("failed", "succeeded", "unknown")
VERIFICATION_RESULTS = ("pass", "fail")
PHASE_BOUNDARIES = ("start", "end")

TrajectoryEvent = Mapping[str, Any]

# ---------------------------------------------------------------------------
# Rule identifiers (ADR-ECON-007 Decision 2 / design doc L1.1 rule 1, listed in the
# design doc's own order: same-fragment repeat, repeated-signature window ("过程图回边
# 计数"'s harness-level analogue), phase timeout, termination-without-verifier-evidence
# (Decision 4)).
# ---------------------------------------------------------------------------

RULE_SAME_FRAGMENT_REPEATED_FAILURE = "SAME_FRAGMENT_REPEATED_FAILURE"
RULE_REPEATED_ACTION_SIGNATURE_WINDOW = "REPEATED_ACTION_SIGNATURE_WINDOW"
RULE_PHASE_TIMEOUT = "PHASE_TIMEOUT"
RULE_TERMINATION_WITHOUT_VERIFIER_EVIDENCE = "TERMINATION_WITHOUT_VERIFIER_EVIDENCE"

_RULE_PRECEDENCE = (
    RULE_SAME_FRAGMENT_REPEATED_FAILURE,
    RULE_REPEATED_ACTION_SIGNATURE_WINDOW,
    RULE_PHASE_TIMEOUT,
    RULE_TERMINATION_WITHOUT_VERIFIER_EVIDENCE,
)


class LoopDetectorError(Exception):
    """Raised on a structurally invalid config or event stream (BLOCKED, never
    silently guessed/clamped) -- carries no B-zone parameter value, only structural
    fact text (mirrors `tools/econ_lab/node.py`'s `FoldError` precedent)."""


# ---------------------------------------------------------------------------
# Config: every threshold is caller-supplied (B-zone injection point, never a literal
# in this module -- see the module docstring's B-zone discipline section).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LoopDetectorConfig:
    """B-zone-injected thresholds for rules 1-3 (ADR-ECON-007 Decision 3). Rule 4
    (termination-without-verifier-evidence) is a structural invariant (ADR-ECON-007
    Decision 4) and needs no threshold, so it has no field here.

    same_fragment_failure_threshold: rule 1 -- number of *consecutive* "failed" edit
        events targeting the same (file_path, fragment_id) key required to trip.
    action_window_size: rule 2 -- the trailing window size (in edit+command events)
        the repeated-action-signature check slides over.
    action_window_repeat_threshold: rule 2 -- how many times one action_signature must
        recur inside that window to trip.
    phase_timeout_steps: rule 3 -- how many further events (seq delta) a phase may
        remain open (a "start" boundary with no matching "end") before it counts as
        stalled.
    """

    same_fragment_failure_threshold: int
    action_window_size: int
    action_window_repeat_threshold: int
    phase_timeout_steps: int

    def __post_init__(self) -> None:
        for name in (
            "same_fragment_failure_threshold",
            "action_window_size",
            "action_window_repeat_threshold",
            "phase_timeout_steps",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or value < 1:
                raise LoopDetectorError(f"{name} must be a positive int, got {value!r}")
        if self.action_window_repeat_threshold > self.action_window_size:
            raise LoopDetectorError(
                "action_window_repeat_threshold cannot exceed action_window_size"
            )


# ---------------------------------------------------------------------------
# Output judgment.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LoopTrip:
    """One rule-trip judgment. `evidence` carries only Decision-3-legal fact content
    (never a count/threshold/duration -- see the module docstring)."""

    rule_id: str
    at_seq: int
    evidence: Mapping[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tripped": True,
            "rule_id": self.rule_id,
            "at_seq": self.at_seq,
            "evidence": dict(self.evidence),
        }


NOT_TRIPPED: Dict[str, Any] = {"tripped": False, "rule_id": None, "at_seq": None, "evidence": None}


# ---------------------------------------------------------------------------
# Stream validation helper (pure; only checks structural shape, never a clock/RNG).
# ---------------------------------------------------------------------------


def _validated(events: Sequence[TrajectoryEvent]) -> List[TrajectoryEvent]:
    ordered = list(events)
    prev_seq: Optional[int] = None
    for event in ordered:
        if "seq" not in event or "event_type" not in event:
            raise LoopDetectorError("every event needs 'seq' and 'event_type'")
        seq = event["seq"]
        if not isinstance(seq, int):
            raise LoopDetectorError(f"event seq must be an int, got {seq!r}")
        if prev_seq is not None and seq <= prev_seq:
            raise LoopDetectorError(
                f"event stream must be strictly increasing by seq (got {seq} after {prev_seq})"
            )
        prev_seq = seq
        if event["event_type"] not in EVENT_TYPES:
            raise LoopDetectorError(f"unknown event_type {event['event_type']!r}")
    return ordered


# ---------------------------------------------------------------------------
# Rule 1: same file/fragment, N consecutive failed edits (design doc L1.1 rule 1,
# first clause: "同一文件/片段连续 N 次失败编辑").
# ---------------------------------------------------------------------------


def _rule_same_fragment_repeated_failure(
    events: Sequence[TrajectoryEvent], config: LoopDetectorConfig
) -> Iterator[LoopTrip]:
    streak: MutableMapping[Tuple[str, Optional[str]], List[str]] = {}
    for event in events:
        if event.get("event_type") != "edit":
            continue
        key = (event["file_path"], event.get("fragment_id"))
        if event.get("outcome") == "failed":
            tried = streak.setdefault(key, [])
            tried.append(event.get("action_signature", "unknown"))
            if len(tried) >= config.same_fragment_failure_threshold:
                yield LoopTrip(
                    rule_id=RULE_SAME_FRAGMENT_REPEATED_FAILURE,
                    at_seq=event["seq"],
                    evidence={
                        "fact_class": "REPEATED_FAILED_EDIT",
                        "file_path": key[0],
                        "fragment_id": key[1],
                        "attempted_action_signatures": list(tried),
                    },
                )
                streak[key] = []  # one report per streak; resume counting fresh
        else:
            streak[key] = []


# ---------------------------------------------------------------------------
# Rule 2: repeated action signature inside a trailing window (design doc L1.1 rule 1,
# second clause: "过程图回边计数" -- this harness-level analogue counts a repeated
# action *signature* recurring inside a bounded trailing window of edit/command
# events, the JSON-event-stream equivalent of a process-graph back edge).
# ---------------------------------------------------------------------------


def _rule_repeated_action_signature_window(
    events: Sequence[TrajectoryEvent], config: LoopDetectorConfig
) -> Iterator[LoopTrip]:
    window: Deque[Tuple[str, int]] = deque(maxlen=config.action_window_size)
    already_reported: set = set()
    for event in events:
        if event.get("event_type") not in ("edit", "command"):
            continue
        signature = event.get("action_signature", "unknown")
        window.append((signature, event["seq"]))
        counts = Counter(sig for sig, _ in window)
        top_signature, top_count = counts.most_common(1)[0]
        if top_count >= config.action_window_repeat_threshold and top_signature not in already_reported:
            already_reported.add(top_signature)
            yield LoopTrip(
                rule_id=RULE_REPEATED_ACTION_SIGNATURE_WINDOW,
                at_seq=event["seq"],
                evidence={
                    "fact_class": "REPEATED_ACTION_SIGNATURE",
                    "action_signature": top_signature,
                    "recent_action_signatures": [sig for sig, _ in window],
                },
            )


# ---------------------------------------------------------------------------
# Rule 3: phase timeout (design doc L1.1 rule 1, third clause: "阶段超时").
# ---------------------------------------------------------------------------


def _rule_phase_timeout(
    events: Sequence[TrajectoryEvent], config: LoopDetectorConfig
) -> Iterator[LoopTrip]:
    open_phases: MutableMapping[str, int] = {}
    reported_phases: set = set()
    for event in events:
        if event.get("event_type") == "phase_boundary":
            phase = event["phase"]
            if event["boundary"] == "start":
                open_phases[phase] = event["seq"]
            elif event["boundary"] == "end":
                open_phases.pop(phase, None)
            continue
        for phase, start_seq in list(open_phases.items()):
            if phase in reported_phases:
                continue
            if event["seq"] - start_seq >= config.phase_timeout_steps:
                reported_phases.add(phase)
                yield LoopTrip(
                    rule_id=RULE_PHASE_TIMEOUT,
                    at_seq=event["seq"],
                    evidence={
                        "fact_class": "PHASE_STILL_OPEN",
                        "phase": phase,
                    },
                )


# ---------------------------------------------------------------------------
# Rule 4: termination without prior verifier evidence in that phase (ADR-ECON-007
# Decision 4: "任何终止路径 ... 必须携带验证器证据。裸 error-out 非法"). Purely
# structural -- no B-zone threshold, so it needs no LoopDetectorConfig field.
# ---------------------------------------------------------------------------


def _rule_termination_without_verifier_evidence(
    events: Sequence[TrajectoryEvent],
) -> Iterator[LoopTrip]:
    verified_phases: set = set()
    verified_globally = False
    for event in events:
        if event.get("event_type") == "verification" and event.get("result") in VERIFICATION_RESULTS:
            phase = event.get("phase")
            if phase is None:
                verified_globally = True
            else:
                verified_phases.add(phase)
            continue
        if event.get("event_type") == "termination":
            phase = event.get("phase")
            has_evidence = verified_globally or (phase is not None and phase in verified_phases)
            if not has_evidence:
                yield LoopTrip(
                    rule_id=RULE_TERMINATION_WITHOUT_VERIFIER_EVIDENCE,
                    at_seq=event["seq"],
                    evidence={
                        "fact_class": "BARE_TERMINATION",
                        "phase": phase,
                        "reason_class": event.get("reason_class"),
                    },
                )


_RULE_FUNCS = {
    RULE_SAME_FRAGMENT_REPEATED_FAILURE: lambda events, cfg: _rule_same_fragment_repeated_failure(events, cfg),
    RULE_REPEATED_ACTION_SIGNATURE_WINDOW: lambda events, cfg: _rule_repeated_action_signature_window(events, cfg),
    RULE_PHASE_TIMEOUT: lambda events, cfg: _rule_phase_timeout(events, cfg),
    RULE_TERMINATION_WITHOUT_VERIFIER_EVIDENCE: lambda events, cfg: _rule_termination_without_verifier_evidence(events),
}


def find_all_trips(
    events: Sequence[TrajectoryEvent], config: LoopDetectorConfig
) -> List[LoopTrip]:
    """Replay the whole stream and return every rule trip found, ordered by `at_seq`
    and (for ties) by the rule's design-doc listing order (`_RULE_PRECEDENCE`). Pure
    and fully replayable: identical `events`/`config` always yields an identical list.
    """
    ordered_events = _validated(events)
    trips: List[LoopTrip] = []
    for rule_id in _RULE_PRECEDENCE:
        trips.extend(_RULE_FUNCS[rule_id](ordered_events, config))
    trips.sort(key=lambda t: (t.at_seq, _RULE_PRECEDENCE.index(t.rule_id)))
    return trips


def detect(events: Sequence[TrajectoryEvent], config: LoopDetectorConfig) -> Dict[str, Any]:
    """The WP-H1 spec-shape entry point: `{tripped, rule_id, evidence}` (plus
    `at_seq`, useful to a caller such as WP-H2's rollback fork-point resolution, but
    not part of the minimal spec triple). Reports only the *first* trip encountered in
    stream order (ADR-ECON-007 Decision 2's single-fuse-event model: the detector
    reports a fact, it does not accumulate a running trigger count anywhere an agent
    could read it)."""
    trips = find_all_trips(events, config)
    if not trips:
        return dict(NOT_TRIPPED)
    return trips[0].to_dict()


# ---------------------------------------------------------------------------
# Empirical format-fit translator (WP-H1 spec: "用一条真实历史轨迹...做实证 fixture
# 证明格式适配"). Deterministic, lossless with respect to the facts the four rules
# above read; invents no per-edit granularity the source file does not actually have
# (see the module docstring's "no currently-persisted artifact records a per-edit
# trace" gap note) -- it only ever emits "command"/"verification"/"phase_boundary"/
# "termination" events, never a synthesized "edit" event, because `settlement.json`
# has no file/fragment-level data to honestly populate one with.
# ---------------------------------------------------------------------------


def events_from_real_settlement_checkpoint(settlement: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Translate one real `econ_lab.live_driver.settlement_checkpoint.v1` document
    (e.g. `tools/econ_lab/monitor/fixtures/real_settlement_*.json`, copied verbatim
    from `tools/econ_lab/runs/stageA_20260707/**`) into this module's event envelope.
    """
    instance_id = settlement["instance_id"]
    route_id = settlement.get("selected_route_id")
    events: List[Dict[str, Any]] = []
    seq = 0

    def _emit(event: Dict[str, Any]) -> None:
        nonlocal seq
        event["seq"] = seq
        event["instance_id"] = instance_id
        event["route_id"] = route_id
        events.append(event)
        seq += 1

    _emit({"event_type": "phase_boundary", "phase": "dispatch", "boundary": "start"})

    any_verifier_evidence = False
    for dispatch in settlement.get("dispatches", []):
        worker_result = dispatch.get("worker_result", {})
        lineage = dispatch.get("lineage", "unknown")
        outcome = "succeeded" if worker_result.get("status") == "COMPLETED" else "failed"
        _emit(
            {
                "event_type": "command",
                "action_signature": f"dispatch_worker:{lineage}",
                "outcome": outcome,
            }
        )

        scoring_result = dispatch.get("scoring_result") or {}
        if scoring_result.get("status") == "COMPLETED":
            any_verifier_evidence = True
            live_split_verdict = dispatch.get("live_split_verdict") or {}
            resolved = bool(scoring_result.get("resolved")) or bool(
                live_split_verdict.get("accept_verdict") and live_split_verdict.get("verify_verdict")
            )
            _emit(
                {
                    "event_type": "verification",
                    "phase": "dispatch",
                    "result": "pass" if resolved else "fail",
                }
            )

    reason_class = "COMPLETED" if any_verifier_evidence else settlement.get(
        "dispatches", [{}]
    )[-1].get("worker_result", {}).get("status", "UNKNOWN")
    _emit({"event_type": "phase_boundary", "phase": "dispatch", "boundary": "end"})
    _emit({"event_type": "termination", "phase": "dispatch", "reason_class": reason_class})

    return events


def load_json_event_stream(path: Path) -> List[Dict[str, Any]]:
    """Load a JSON-array event stream from disk (pure file read + `json.loads`; no
    clock, no network, no mutation of the file)."""
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise LoopDetectorError("event stream file must be a JSON array")
    return data
