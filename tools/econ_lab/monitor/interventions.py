"""WP-H2 (ADR-ECON-007 `adr/ADR-ECON-007-route-market-loop-remedy.md` Decision 1/3;
design doc `research/RES_ROUTE_lockIn_remedy_design_20260710.md` §2 L1.2): diagnostic
message injection + ledger-compliant rollback, consuming WP-H1's
`monitor.loop_detector.LoopTrip` judgments (`tools/econ_lab/monitor/loop_detector.py`).

Two independent primitives live here, both pure functions over their explicit
arguments (Art 0.2 determinism -- no clock/RNG/hidden global anywhere below; the same
inputs always produce byte-identical outputs, so a tape built from these primitives
replays deterministically):

(a) Diagnostic generator (`build_diagnostic`): turns one `LoopTrip` into a
    `Diagnostic` whose `.text`/`.facts` carry ONLY Decision-3-legal fact content --
    which file/fragment, which action signature(s), which failure category, which
    phase, what was already tried. Never a tau/lambda/floor/bucket-key/Q/N/S/P value,
    never a count/threshold/duration, never "第 N 次触发" phrasing (Decision 3's own
    example of what NOT to say -- this module says "loop detected", never "triggered
    the Nth time").

    This is enforced structurally, not just by convention, three ways:
      1. `build_diagnostic`'s only input is a `LoopTrip` (rule_id + evidence dict) --
         it never receives a `LoopDetectorConfig`, an economy `NodeState`/`Ledger`, or
         any other object that could even *carry* a B-zone number, so there is no
         reachable channel for one to leak through in the first place.
      2. `assert_decision3_legal` type-checks every `facts` value (str / list-of-str /
         None only -- no int/float/bool anywhere, recursively) and rejects any key
         whose name contains a B-zone token (tau/lambda/floor/bucket/threshold/q_eff/
         count/...), independent of what rule produced it.
      3. `assert_no_unexplained_numbers_in_text` extracts every digit run from the
         rendered `.text` and requires it to be a literal substring of some
         already-whitelisted fact string (e.g. a digit that happens to appear inside a
         real file path) -- an un-traceable digit run (which is exactly what a smuggled
         count/threshold would look like) is rejected.
    All three run inside `build_diagnostic` itself before it returns, so a
    `Diagnostic` object cannot exist in an illegal state.

(b) Rollback event + executor (`execute_rollback`): Decision 1's ledger semantics --
    "回滚绝不改写 tape。回滚 = 追加 PRESERVE 事件 TrajectoryRolledBack
    {fork_point_event_hash, reason_class, detector_rule_id, diagnostic_digest},随后
    工作区(worktree/内存轨迹)重置到分叉点". Concretely:
      * `tape` is the append-only full history (every event ever observed, including
        every rolled-back segment and every `TrajectoryRolledBack` event itself --
        Decision 1: "历史完整保留,重放时回滚本身可重放").
      * `workspace` is the mutable *working* trajectory execution continues from; a
        rollback truncates it back to (and including) the fork-point event, while
        `tape` is only ever appended to, never truncated/rewritten.
    Event identity mirrors the `RoutingPriorUpdated` precedent
    (`crates/turing-economy/src/lib.rs`: `schema_id`/`event_type`/
    `head_effect="PRESERVE"` plus a derived `event_hash` = canonical-JSON-then-SHA256
    over the event's own identity fields) at this module's Python/JSON
    trajectory-stream layer -- deliberately NOT a `crates/turing-economy` `EconomyEvent`
    variant: Decision 1 routes `TrajectoryRolledBack` to the trajectory stream only,
    never the Q fold ("此事件不进 Q fold"), mirroring WP-H1's own placement ("harness-
    side Python analysis primitive, not a kernel change" -- see `loop_detector.py`'s
    module docstring).

    Rollback cap (Decision 1: "同一分叉点重复回滚计数入事件;超过 A 区公开上限(初值
    2)即禁止再回滚该点"): unlike `LoopDetectorConfig`'s B-zone-secret thresholds, this
    cap IS a published A-zone constant per Decision 1's own text --
    `DEFAULT_MAX_ROLLBACKS_PER_FORK_POINT = 2` is that value (still caller-overridable,
    never silently hardcoded past the constructor default -- see `execute_rollback`'s
    `max_rollbacks_per_fork_point` parameter). The per-fork-point count is never stored
    as an extra event field (Decision 1 pins the event to exactly four fields); it is
    *derived* by scanning `tape` for prior `TrajectoryRolledBack` events whose
    `fork_point_event_hash` matches (`count_prior_rollbacks_at_fork_point`), which also
    sidesteps any need for `event_hash` itself to be unique across repeated rollbacks
    of the same fork point (it need not be, and generally will not be, since two
    rollbacks of the same fork point for the same detected condition legitimately
    carry identical identity-field content; `event_hash` is an audit/replay digest,
    never a dedup key here -- there is no Q-fold consumer of this event to dedup for).

(c) `tools/econ_lab/live_driver.py`'s `--monitor` hook wiring lives in that file, not
    here -- this module exposes only the pure, replayable primitives that hook calls
    (`build_diagnostic`, `execute_rollback`, `resolve_fork_point`,
    `trajectory_event_hash`, `count_prior_rollbacks_at_fork_point`,
    `renumber_and_append`), so `live_driver.py`'s own integration point stays a thin,
    independently-testable call site rather than a second copy of this logic.

Canonical-JSON note (same disciplined-approximation precedent as
`tools/econ_lab/node.py`'s own harness-level fold, see that module's docstring): the
`_jcs_sha256` helper below sorts keys and uses compact separators (no whitespace, no
`ensure_ascii` escaping) for determinism, but is NOT the full RFC 8785 JCS
`turing_contracts::jcs` (the Rust crate `RoutingPriorUpdated.event_hash` actually uses)
implements -- no float-canonicalization/NFC edge cases arise here because every value
this module ever feeds it is a plain str/list/dict/None built by this module itself,
never an externally-sourced float.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple

from . import loop_detector
from .loop_detector import (
    RULE_PHASE_TIMEOUT,
    RULE_REPEATED_ACTION_SIGNATURE_WINDOW,
    RULE_SAME_FRAGMENT_REPEATED_FAILURE,
    RULE_TERMINATION_WITHOUT_VERIFIER_EVIDENCE,
    LoopTrip,
    TrajectoryEvent,
)

# ADR-ECON-007 Decision 1: "超过 A 区公开上限(初值 2)即禁止再回滚该点" -- a published
# A-zone constant (existence AND value public), unlike LoopDetectorConfig's B-zone-secret
# thresholds. Still caller-overridable; never silently hardcoded past this default.
DEFAULT_MAX_ROLLBACKS_PER_FORK_POINT = 2

TRAJECTORY_ROLLED_BACK_SCHEMA_ID = "trajectory_rolled_back.v1"
TRAJECTORY_ROLLED_BACK_EVENT_TYPE = "TrajectoryRolledBack"
PRESERVE_HEAD_EFFECT = "PRESERVE"


class InterventionError(Exception):
    """Raised on a structurally invalid input or a Decision-3 whitelist/blacklist
    violation (BLOCKED, never silently guessed/patched) -- carries no B-zone parameter
    value, only structural fact text (mirrors `loop_detector.LoopDetectorError` /
    `node.FoldError`'s precedent)."""


class RollbackCapExceededError(InterventionError):
    """Raised when ADR-ECON-007 Decision 1's per-fork-point rollback cap is already
    met -- the caller must not append another `TrajectoryRolledBack` event for this
    fork point ("禁止再回滚该点")."""


# ---------------------------------------------------------------------------
# Canonical-JSON / hashing helpers (see module docstring's canonical-JSON note).
# ---------------------------------------------------------------------------


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _jcs_sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def trajectory_event_hash(event: TrajectoryEvent) -> str:
    """Deterministic identity digest for one trajectory-stream event (WP-H1's
    edit/command/phase_boundary/verification/termination envelope) -- the value a
    `TrajectoryRolledBack.fork_point_event_hash` names. Pure function of the event's
    own fields only: the same event dict always derives the same hash, so a fork point
    is unambiguously nameable and survives tape replay byte-identically."""
    return _jcs_sha256({"schema": "trajectory_event_identity.v1", **dict(event)})


# ---------------------------------------------------------------------------
# (a) Diagnostic generator (ADR-ECON-007 Decision 3).
# ---------------------------------------------------------------------------

# Key-name blacklist (Decision 3 / F4 forbidden-identifier families, ADR-ECON-003
# Decisions 1/3/4, reused verbatim by `tools/gates/gate_f4_econ_leakage.sh`): a
# `Diagnostic.facts` key whose lowercased name *contains* any of these tokens is
# rejected outright, regardless of which rule tried to emit it.
_FORBIDDEN_KEY_TOKENS: Tuple[str, ...] = (
    "tau",
    "lambda",
    "floor",
    "bucket",
    "threshold",
    "q_eff",
    "q_value",
    "count",
    "n_eff",
    "h_lineage",
    "elapsed",
    "duration",
    "seq",
    "window_size",
    "repeat",
)

_FORBIDDEN_TEXT_PATTERN = re.compile(
    r"(?i)\b(tau|lambda|threshold|floor|bucket.?key|q[_-]?eff|n_eff|h_lineage)\b|[τλ]"
)

_DIGIT_RUN = re.compile(r"\d+")


def _flatten_strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for v in value.values():
            yield from _flatten_strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _flatten_strings(v)


def _assert_no_numeric_leak(value: Any, *, path: str) -> None:
    if isinstance(value, bool):
        raise InterventionError(f"Decision 3 blacklist: boolean value at {path!r} not allowed in diagnostic facts")
    if isinstance(value, (int, float)):
        raise InterventionError(f"Decision 3 blacklist: numeric value at {path!r} not allowed in diagnostic facts")
    if value is None or isinstance(value, str):
        return
    if isinstance(value, (list, tuple)):
        for i, item in enumerate(value):
            _assert_no_numeric_leak(item, path=f"{path}[{i}]")
        return
    if isinstance(value, Mapping):
        for k, v in value.items():
            _assert_no_numeric_leak(v, path=f"{path}.{k}")
        return
    raise InterventionError(f"Decision 3 blacklist: unsupported value type at {path!r}: {type(value)!r}")


def assert_decision3_legal(facts: Mapping[str, Any]) -> None:
    """Whitelist/blacklist assertion over a `Diagnostic.facts`-shaped mapping (ADR-
    ECON-007 Decision 3): every key must be free of B-zone tokens, and every value must
    be `str`/`list[str]`/`None` only (no int/float/bool anywhere, recursively). Public
    (not `_`-prefixed) so tests can exercise it directly against both legal and
    deliberately-illegal fixtures, not just indirectly through `build_diagnostic`."""
    for key, value in facts.items():
        lowered = key.lower()
        if any(token in lowered for token in _FORBIDDEN_KEY_TOKENS):
            raise InterventionError(f"Decision 3 blacklist: forbidden field name {key!r}")
        _assert_no_numeric_leak(value, path=key)


def assert_no_bzone_terms_in_text(text: str) -> None:
    """Blacklist scan over rendered diagnostic text for literal B-zone vocabulary
    (tau/lambda/floor/bucket-key/Q_eff/N_eff/H_lineage, ASCII or Greek). Public for the
    same direct-test reason as `assert_decision3_legal`."""
    match = _FORBIDDEN_TEXT_PATTERN.search(text)
    if match:
        raise InterventionError(f"Decision 3 blacklist: forbidden B-zone term {match.group()!r} in diagnostic text")


def assert_no_unexplained_numbers_in_text(text: str, facts: Mapping[str, Any]) -> None:
    """Blacklist scan: every digit run in `text` must be traceable to a substring of
    some already-whitelisted fact string (e.g. a digit legitimately embedded in a real
    file path or action signature). An un-traceable digit run is exactly the shape a
    smuggled count/threshold/duration would take ("triggered 3 times") and is
    rejected -- this is what stops Decision 3's "不说'第 N 次触发'" rule from being
    just a style guideline."""
    allowed_strings = list(_flatten_strings(dict(facts)))
    for run in _DIGIT_RUN.findall(text):
        if not any(run in s for s in allowed_strings):
            raise InterventionError(
                f"Decision 3 blacklist: digit sequence {run!r} in diagnostic text is not traceable to a "
                "whitelisted fact string (possible B-zone numeric leak)"
            )


@dataclass(frozen=True)
class Diagnostic:
    """A Decision-3-legal, agent-visible diagnostic message (ADR-ECON-007 Decision 3:
    "诊断消息是故意 agent 可见的新通道"). `facts` is the structured whitelist-checked
    payload `text` is rendered from; `digest` is a `sha256:`-prefixed identity digest
    over `(rule_id, text, facts)`, referenced by `TrajectoryRolledBack.diagnostic_digest`
    so the tape can prove *which* diagnostic accompanied a given rollback without
    re-embedding the full text in the event itself."""

    rule_id: str
    text: str
    facts: Mapping[str, Any]
    digest: str


def _diagnostic_same_fragment(evidence: Mapping[str, Any]) -> Tuple[Dict[str, Any], str]:
    file_path = evidence["file_path"]
    fragment_id = evidence.get("fragment_id")
    attempted = list(evidence.get("attempted_action_signatures", []))
    facts = {
        "fact_class": "REPEATED_FAILED_EDIT",
        "file_path": file_path,
        "fragment_id": fragment_id,
        "attempted_action_signatures": attempted,
    }
    location = file_path if fragment_id is None else f"{file_path} (fragment {fragment_id})"
    tried = ", ".join(attempted) if attempted else "no recorded prior attempt"
    text = (
        f"Loop detected: repeated failed edits on {location}. Already attempted: {tried}. "
        "Try a materially different approach for this file/fragment instead of repeating "
        "the same edit."
    )
    return facts, text


def _diagnostic_repeated_signature(evidence: Mapping[str, Any]) -> Tuple[Dict[str, Any], str]:
    signature = evidence["action_signature"]
    recent = list(evidence.get("recent_action_signatures", []))
    facts = {
        "fact_class": "REPEATED_ACTION_SIGNATURE",
        "action_signature": signature,
        "recent_action_signatures": recent,
    }
    recent_text = ", ".join(recent) if recent else "no recorded recent actions"
    text = (
        f"Loop detected: the action '{signature}' keeps recurring in recent steps "
        f"(recent actions: {recent_text}). Reconsider the current approach rather than "
        "repeating this action."
    )
    return facts, text


def _diagnostic_phase_timeout(evidence: Mapping[str, Any]) -> Tuple[Dict[str, Any], str]:
    phase = evidence["phase"]
    facts = {"fact_class": "PHASE_STILL_OPEN", "phase": phase}
    text = (
        f"Loop detected: the '{phase}' phase has stayed open without closing. Wrap up or "
        "explicitly close this phase before continuing."
    )
    return facts, text


def _diagnostic_bare_termination(evidence: Mapping[str, Any]) -> Tuple[Dict[str, Any], str]:
    phase = evidence.get("phase")
    reason_class = evidence.get("reason_class")
    facts = {"fact_class": "BARE_TERMINATION", "phase": phase, "reason_class": reason_class}
    where = f"in phase '{phase}'" if phase is not None else "outside any tracked phase"
    text = (
        f"Termination without verifier evidence: the trajectory ended (reason: {reason_class}) "
        f"{where} without any prior verification result. A termination must carry verifier "
        "evidence; do not end without it."
    )
    return facts, text


_DIAGNOSTIC_BUILDERS = {
    RULE_SAME_FRAGMENT_REPEATED_FAILURE: _diagnostic_same_fragment,
    RULE_REPEATED_ACTION_SIGNATURE_WINDOW: _diagnostic_repeated_signature,
    RULE_PHASE_TIMEOUT: _diagnostic_phase_timeout,
    RULE_TERMINATION_WITHOUT_VERIFIER_EVIDENCE: _diagnostic_bare_termination,
}


def build_diagnostic(trip: LoopTrip) -> Diagnostic:
    """Turn one `LoopTrip` (WP-H1's `{rule_id, at_seq, evidence}` judgment) into a
    Decision-3-legal `Diagnostic`. Self-validating: raises `InterventionError` (never
    returns a non-compliant object) if the rendered facts/text would violate the
    whitelist/blacklist -- see the module docstring's three-layer enforcement note."""
    builder = _DIAGNOSTIC_BUILDERS.get(trip.rule_id)
    if builder is None:
        raise InterventionError(f"no diagnostic template for rule_id {trip.rule_id!r}")
    facts, text = builder(trip.evidence)
    assert_decision3_legal(facts)
    assert_no_bzone_terms_in_text(text)
    assert_no_unexplained_numbers_in_text(text, facts)
    digest = _jcs_sha256({"schema": "diagnostic_identity.v1", "rule_id": trip.rule_id, "text": text, "facts": facts})
    return Diagnostic(rule_id=trip.rule_id, text=text, facts=facts, digest=digest)


# ---------------------------------------------------------------------------
# (b) Fork-point resolution + rollback executor (ADR-ECON-007 Decision 1).
# ---------------------------------------------------------------------------


def resolve_fork_point(events: Sequence[TrajectoryEvent], trip: LoopTrip) -> TrajectoryEvent:
    """The trajectory event a rollback for `trip` resets the workspace back to
    (Decision 1: "工作区 ... 重置到分叉点"). Pure function of `events`/`trip` only;
    always returns an event that is literally present in `events` (by `seq`), never a
    synthesized one, so the caller can locate its index and hash it via
    `trajectory_event_hash`.

    Per-rule fork-point choice (not itself ADR-pinned -- ADR-ECON-007 Decision 1 names
    the mechanism, not a per-rule resolution algorithm; this is this module's own
    documented, deterministic policy, not a guessed B-zone number):
      * SAME_FRAGMENT_REPEATED_FAILURE -> the earliest failed edit of the repeated
        (file_path, fragment_id) streak (undoes the whole repeated-failure run).
      * REPEATED_ACTION_SIGNATURE_WINDOW -> the earliest occurrence (at/before the
        trip) of the repeating action_signature.
      * PHASE_TIMEOUT -> the phase's own "start" boundary event (undoes the whole
        stalled phase).
      * TERMINATION_WITHOUT_VERIFIER_EVIDENCE -> the start boundary of the
        un-verified phase, or the very first event of the trajectory when the
        termination was not scoped to any phase (global termination).
    """
    if not events:
        raise InterventionError("cannot resolve a fork point in an empty event stream")

    if trip.rule_id == RULE_SAME_FRAGMENT_REPEATED_FAILURE:
        file_path = trip.evidence["file_path"]
        fragment_id = trip.evidence.get("fragment_id")
        for event in events:
            if (
                event.get("event_type") == "edit"
                and event.get("file_path") == file_path
                and event.get("fragment_id") == fragment_id
                and event.get("outcome") == "failed"
                and event["seq"] <= trip.at_seq
            ):
                return event
        raise InterventionError(
            f"no matching failed edit event found for fork-point resolution (file_path={file_path!r}, "
            f"fragment_id={fragment_id!r})"
        )

    if trip.rule_id == RULE_REPEATED_ACTION_SIGNATURE_WINDOW:
        signature = trip.evidence["action_signature"]
        for event in events:
            if (
                event.get("event_type") in ("edit", "command")
                and event.get("action_signature") == signature
                and event["seq"] <= trip.at_seq
            ):
                return event
        raise InterventionError(
            f"no matching action event found for fork-point resolution (action_signature={signature!r})"
        )

    if trip.rule_id == RULE_PHASE_TIMEOUT:
        phase = trip.evidence["phase"]
        candidate: Optional[TrajectoryEvent] = None
        for event in events:
            if event["seq"] > trip.at_seq:
                break
            if event.get("event_type") == "phase_boundary" and event.get("phase") == phase and event.get(
                "boundary"
            ) == "start":
                candidate = event
        if candidate is None:
            raise InterventionError(f"no phase-start event found for fork-point resolution (phase={phase!r})")
        return candidate

    if trip.rule_id == RULE_TERMINATION_WITHOUT_VERIFIER_EVIDENCE:
        phase = trip.evidence.get("phase")
        if phase is not None:
            candidate = None
            for event in events:
                if event["seq"] > trip.at_seq:
                    break
                if event.get("event_type") == "phase_boundary" and event.get("phase") == phase and event.get(
                    "boundary"
                ) == "start":
                    candidate = event
            if candidate is not None:
                return candidate
        return events[0]

    raise InterventionError(f"no fork-point resolution rule for rule_id {trip.rule_id!r}")


def _index_of_event(events: Sequence[TrajectoryEvent], event: TrajectoryEvent) -> int:
    target_seq = event["seq"]
    for index, candidate in enumerate(events):
        if candidate["seq"] == target_seq:
            return index
    raise InterventionError(f"fork-point event (seq={target_seq}) is not present in the given event sequence")


def count_prior_rollbacks_at_fork_point(tape: Sequence[Mapping[str, Any]], fork_point_event_hash: str) -> int:
    """How many `TrajectoryRolledBack` events already reference this exact
    `fork_point_event_hash`, derived by scanning `tape` (never stored as a separate
    event field -- see module docstring's rollback-cap note)."""
    return sum(
        1
        for event in tape
        if event.get("event_type") == TRAJECTORY_ROLLED_BACK_EVENT_TYPE
        and event.get("fork_point_event_hash") == fork_point_event_hash
    )


def trajectory_rolled_back_event(
    *,
    fork_point_event_hash: str,
    reason_class: str,
    detector_rule_id: str,
    diagnostic_digest: str,
    seq: Optional[int] = None,
) -> Dict[str, Any]:
    """Construct one `TrajectoryRolledBack` PRESERVE event (ADR-ECON-007 Decision 1's
    exact four-field payload), identity-hashed the same way
    `crates/turing-economy/src/lib.rs::routing_prior_event_hash` hashes
    `RoutingPriorUpdated` -- canonicalize the identity fields, SHA-256 them,
    `sha256:`-prefix the digest.

    `seq` (optional): stream-position bookkeeping only, exactly like every other
    trajectory event's own `seq` field (`loop_detector`'s envelope) -- deliberately
    NOT one of the four Decision-1 identity fields the hash is computed over (adding a
    `tape`-appended event needs *some* `seq` so `tape` stays a well-formed trajectory
    stream `renumber_and_append` can keep extending; the hash must stay a pure function
    of the four Decision-1 fields alone so two rollbacks of the same fork point for the
    same detected condition are still recognizable as carrying the same identity
    content, only appended at different stream positions)."""
    identity = {
        "schema": "trajectory_rolled_back_identity.v1",
        "fork_point_event_hash": fork_point_event_hash,
        "reason_class": reason_class,
        "detector_rule_id": detector_rule_id,
        "diagnostic_digest": diagnostic_digest,
    }
    event_hash = _jcs_sha256(identity)
    event: Dict[str, Any] = {
        "schema_id": TRAJECTORY_ROLLED_BACK_SCHEMA_ID,
        "event_type": TRAJECTORY_ROLLED_BACK_EVENT_TYPE,
        "head_effect": PRESERVE_HEAD_EFFECT,
        "fork_point_event_hash": fork_point_event_hash,
        "reason_class": reason_class,
        "detector_rule_id": detector_rule_id,
        "diagnostic_digest": diagnostic_digest,
        "event_hash": event_hash,
    }
    if seq is not None:
        event["seq"] = seq
    return event


@dataclass(frozen=True)
class RollbackResult:
    """`tape`/`workspace` are the *new* full histories after the rollback (inputs are
    never mutated -- pure function). `event` is the appended `TrajectoryRolledBack`
    dict; `fork_point` is the workspace event execution now resumes from."""

    tape: Tuple[Dict[str, Any], ...]
    workspace: Tuple[Dict[str, Any], ...]
    event: Dict[str, Any]
    fork_point: Dict[str, Any]


def execute_rollback(
    *,
    tape: Sequence[Mapping[str, Any]],
    workspace: Sequence[TrajectoryEvent],
    trip: LoopTrip,
    diagnostic: Diagnostic,
    max_rollbacks_per_fork_point: int = DEFAULT_MAX_ROLLBACKS_PER_FORK_POINT,
) -> RollbackResult:
    """ADR-ECON-007 Decision 1's rollback executor: appends a `TrajectoryRolledBack`
    event to `tape` (never rewriting/truncating it) and returns a `workspace` reset to
    the fork point. Raises `RollbackCapExceededError` (never silently clamps/skips)
    when this fork point has already been rolled back
    `max_rollbacks_per_fork_point` times -- Decision 1: "禁止再回滚该点"; the caller
    decides how to degrade gracefully (e.g. `live_driver.py`'s hook catches this and
    simply stops intervening at that fork point, per that module's own docstring)."""
    fork_point = resolve_fork_point(workspace, trip)
    fork_point_hash = trajectory_event_hash(fork_point)
    prior = count_prior_rollbacks_at_fork_point(tape, fork_point_hash)
    if prior >= max_rollbacks_per_fork_point:
        raise RollbackCapExceededError(
            f"fork point {fork_point_hash} already rolled back {prior} time(s); cap is "
            f"{max_rollbacks_per_fork_point} (ADR-ECON-007 Decision 1)"
        )

    # `tape`'s own next stream position (see `trajectory_rolled_back_event`'s `seq`
    # note) -- `.get("seq", -1)` rather than `["seq"]` because a `TrajectoryRolledBack`
    # entry already in `tape` always has one (this function always sets it), but
    # defensively tolerates any future tape-only bookkeeping entry that might not.
    next_tape_seq = max((e.get("seq", -1) for e in tape), default=-1) + 1
    event = trajectory_rolled_back_event(
        fork_point_event_hash=fork_point_hash,
        reason_class=str(trip.evidence.get("fact_class", trip.rule_id)),
        detector_rule_id=trip.rule_id,
        diagnostic_digest=diagnostic.digest,
        seq=next_tape_seq,
    )
    new_tape: Tuple[Dict[str, Any], ...] = tuple(dict(e) for e in tape) + (event,)

    fork_index = _index_of_event(workspace, fork_point)
    new_workspace: Tuple[Dict[str, Any], ...] = tuple(dict(e) for e in workspace[: fork_index + 1])

    return RollbackResult(tape=new_tape, workspace=new_workspace, event=event, fork_point=dict(fork_point))


# ---------------------------------------------------------------------------
# Trajectory-stream bookkeeping helper shared with `live_driver.py`'s hook.
# ---------------------------------------------------------------------------


def renumber_and_append(
    events: Sequence[TrajectoryEvent], new_events: Sequence[TrajectoryEvent]
) -> List[Dict[str, Any]]:
    """Append `new_events` (freshly `seq`'d 0..k by some translator, e.g.
    `loop_detector.events_from_real_settlement_checkpoint` applied to one task's
    settlement) onto `events`, renumbering the appended copies' `seq` to continue
    `events`' own strictly-increasing sequence (`loop_detector._validated`'s
    invariant). Pure function; never mutates either input list."""
    next_seq = max((e["seq"] for e in events), default=-1) + 1
    appended: List[Dict[str, Any]] = []
    for offset, event in enumerate(new_events):
        renumbered = dict(event)
        renumbered["seq"] = next_seq + offset
        appended.append(renumbered)
    return list(dict(e) for e in events) + appended


__all__ = [
    "DEFAULT_MAX_ROLLBACKS_PER_FORK_POINT",
    "TRAJECTORY_ROLLED_BACK_SCHEMA_ID",
    "TRAJECTORY_ROLLED_BACK_EVENT_TYPE",
    "PRESERVE_HEAD_EFFECT",
    "InterventionError",
    "RollbackCapExceededError",
    "Diagnostic",
    "RollbackResult",
    "build_diagnostic",
    "assert_decision3_legal",
    "assert_no_bzone_terms_in_text",
    "assert_no_unexplained_numbers_in_text",
    "resolve_fork_point",
    "trajectory_event_hash",
    "count_prior_rollbacks_at_fork_point",
    "trajectory_rolled_back_event",
    "execute_rollback",
    "renumber_and_append",
    "loop_detector",
]
