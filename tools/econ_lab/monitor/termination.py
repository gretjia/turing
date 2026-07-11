"""WP-H3 (ADR-ECON-007 `adr/ADR-ECON-007-route-market-loop-remedy.md` Decision 4;
design doc `research/RES_ROUTE_lockIn_remedy_design_20260710.md` §2 L1.3): the
verification-gated termination guard + route-falsification report.

Decision 4, verbatim: "任何终止路径(成功/放弃)必须携带验证器证据。裸 error-out 非法。
放弃的合法产物 = RouteFalsified PRESERVE 事件 + 结构化报告 {route_id, attempts,
verifier_evidence[], detector_events[], remaining_candidates[], recommendation},回流
GRILL-ME 层(人/facilitator 续议)。报告是 proposal_only,不推进任何 accepted_head。"

This module is the sole legal exit for a route's trajectory. It defines exactly two
outcomes (never a third, and never a bare, unaccounted-for exception escaping past its
own guard):

  * ACCEPTED  -- legal ONLY when at least one `verifier_evidence` entry carries a
    "pass" result (Decision 4's "成功=accept 证据"). `terminate_accepted` raises
    `TerminationError` (BLOCKED, never silently downgraded/guessed) when no such
    evidence exists; a caller with no accept evidence must go through the FALSIFIED
    path instead -- there is no third, evidence-free way to end a route.
  * FALSIFIED -- Decision 4's "放弃" path, always legal, always produces BOTH a
    `RouteFalsified` PRESERVE event (`route_falsified_event`, mirroring the identity/
    hash shape `interventions.trajectory_rolled_back_event` already established for
    `TrajectoryRolledBack`) and a structured report carrying exactly Decision 4's six
    fields plus `schema`/`proposal_only` (`build_route_falsification_report`). The
    report is `proposal_only: true` and is never fed back into any `accepted_head`
    fold by this module -- it only ever flows out to the caller for the GRILL-ME
    layer, matching Decision 4's own text.

`guard_bare_termination` is the actual "guard" primitive named in this WP's brief: it
wraps a caller-supplied zero-argument `finalize` callable (the caller's own attempt at
ending a route) and makes bare error-out structurally impossible to observe from the
outside --
  * if `finalize` raises ANY exception, that exception is caught here and NEVER
    re-raised; only the exception's own `type(...).__name__` (never its message,
    args, or traceback -- arbitrary text may carry anything, including a smuggled
    B-zone number, and Decision 3's fact-only discipline applies to this report's
    content exactly as it does to WP-H2's diagnostic text) is folded into one
    `BARE_ERROR_INTERCEPTED` attempts entry, and the call is redirected to
    `terminate_falsified`;
  * if `finalize` returns normally but there is still no verifier accept evidence,
    that is *also* an illegal bare "silent success" under Decision 4 ("任何终止路径
    ... 必须携带验证器证据") and is redirected to the same `terminate_falsified` path,
    never allowed through as a phantom ACCEPTED;
  * only when `finalize` returns normally AND accept evidence exists does this
    function hand off to `terminate_accepted`.
So every call to `guard_bare_termination` returns a `TerminationOutcome` with
`status` in `{ACCEPTED, FALSIFIED}` and nothing else ever escapes it.

Constitutional placement (Decision 2/4, Art I.1.1/F1): this module never writes Q and
never calls the independent verifier -- `verifier_evidence` is caller-supplied evidence
*about* what the verifier already decided (the same `{phase, result}` shape as
`loop_detector`'s own `event_type == "verification"` envelope), not a settlement call
this module makes itself. `RouteFalsified` is routed to the trajectory-stream tape
only (mirroring `interventions.py`'s `TrajectoryRolledBack` placement note: "此事件不
进 Q fold"), never a `crates/turing-economy` `EconomyEvent` variant.

Decision-3 discipline (Art III.4/F4) applied to THIS module's own new agent-adjacent
surface (the falsification report, which flows to the GRILL-ME/facilitator layer):
every caller-supplied fact field (`attempts`, `verifier_evidence`, `detector_events`,
`remaining_candidates`, `recommendation`) is blacklist-scanned by
`assert_report_has_no_bzone_leak` before a report is ever constructed --
`RouteFalsificationError` (BLOCKED) is raised, never silently stripped/patched, on any
violation. The blacklist token family mirrors `interventions.py`'s
`_FORBIDDEN_KEY_TOKENS` (ADR-ECON-003 Decisions 1/3/4, reused verbatim by
`tools/gates/gate_f4_econ_leakage.sh`) -- duplicated here (not imported as a private
symbol) so this module's own enforcement never depends on `interventions.py`'s
internal naming. Unlike `interventions.assert_decision3_legal` (built for the fully
flattened, agent-in-band diagnostic *facts* mapping, where even a bare int/bool is
disallowed), this module's report legitimately carries a handful of structural
non-B-zone integers a facilitator/reviewer needs to make sense of a report (e.g. how
many verifier_evidence entries exist is implicit in list length, never a field value
itself) -- so the blacklist here targets exactly what Decision 3/this WP's own red
line names ("τ/λ/地板/桶键/检测器阈值数值"), not every numeric type on principle; see
`assert_report_has_no_bzone_leak`'s own docstring for the precise rule.

`tools/econ_lab/live_driver.py`'s `--monitor` hook wiring for this module lives in
that file, not here (mirrors `interventions.py`'s own placement note): when WP-H2's
`execute_rollback` raises `RollbackCapExceededError` (that module's own documented
extension point -- "the caller decides how to degrade gracefully"), the hook now also
calls `terminate_falsified` for that route, appends the resulting `RouteFalsified`
event to `monitor_tape`, and records the report under
`verdict["monitor_summary"]["route_falsification_reports"]` (present, defaulting to
`[]`, only when `--monitor` is set -- exactly WP-H2's own additive-only discipline).

Canonical-JSON note: reuses the exact same disciplined-approximation `_jcs_sha256`
helper `interventions.py` documents (sorted keys, compact separators, no
`ensure_ascii` escaping) -- duplicated locally rather than imported for the same
naming-independence reason as the blacklist tokens above.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple

from .loop_detector import VERIFICATION_RESULTS

ROUTE_FALSIFIED_SCHEMA_ID = "route_falsified.v1"
ROUTE_FALSIFIED_EVENT_TYPE = "RouteFalsified"
PRESERVE_HEAD_EFFECT = "PRESERVE"
ROUTE_FALSIFICATION_REPORT_SCHEMA = "econ_lab.monitor.route_falsification_report.v1"

ACCEPTED = "ACCEPTED"
FALSIFIED = "FALSIFIED"


class TerminationError(Exception):
    """Raised on a structurally illegal termination attempt (BLOCKED, never silently
    guessed/patched) -- carries no B-zone parameter value, only structural fact text
    (mirrors `interventions.InterventionError` / `loop_detector.LoopDetectorError`'s
    precedent)."""


class RouteFalsificationError(TerminationError):
    """Raised by `assert_report_has_no_bzone_leak` / `build_route_falsification_report`
    when caller-supplied report content violates the Decision-3 blacklist this
    module's own docstring describes."""


# ---------------------------------------------------------------------------
# Canonical-JSON / hashing helpers (see module docstring's canonical-JSON note).
# ---------------------------------------------------------------------------


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _jcs_sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


# ---------------------------------------------------------------------------
# Decision-3 blacklist over the falsification report's own content (see module
# docstring's "Decision-3 discipline" section for why this targets exactly the
# named B-zone token family rather than banning every numeric type on principle).
# ---------------------------------------------------------------------------

_FORBIDDEN_KEY_TOKENS: Tuple[str, ...] = (
    "tau",
    "lambda",
    "floor",
    "bucket",
    "threshold",
    "q_eff",
    "q_value",
    "n_eff",
    "h_lineage",
    "elapsed",
    "duration",
    "window_size",
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


def _assert_field_shape(value: Any, *, path: str) -> None:
    """Every leaf of a report field must be `str`/`list`/`dict`/`None` -- never a bare
    `bool`/`int`/`float` (Decision 3's own quantities are always numbers; disallowing
    every raw number here, not just the named tokens, is the safe superset this
    module's docstring promises, matching `interventions.assert_decision3_legal`'s own
    posture for exactly the same reason)."""
    if isinstance(value, bool) or isinstance(value, (int, float)):
        raise RouteFalsificationError(f"Decision 3 blacklist: numeric/boolean value at {path!r} is not allowed")
    if value is None or isinstance(value, str):
        return
    if isinstance(value, (list, tuple)):
        for i, item in enumerate(value):
            _assert_field_shape(item, path=f"{path}[{i}]")
        return
    if isinstance(value, Mapping):
        for k, v in value.items():
            lowered = str(k).lower()
            if any(token in lowered for token in _FORBIDDEN_KEY_TOKENS):
                raise RouteFalsificationError(f"Decision 3 blacklist: forbidden field name {k!r} at {path!r}")
            _assert_field_shape(v, path=f"{path}.{k}")
        return
    raise RouteFalsificationError(f"Decision 3 blacklist: unsupported value type at {path!r}: {type(value)!r}")


def assert_report_has_no_bzone_leak(report: Mapping[str, Any]) -> None:
    """Whitelist/blacklist assertion over a would-be report dict (ADR-ECON-007
    Decision 3, applied to this module's own report surface). Checks, recursively,
    over `attempts`/`verifier_evidence`/`detector_events`/`remaining_candidates`/
    `recommendation`/`route_id`:
      1. no field name (at any nesting depth) contains a B-zone token
         (`_FORBIDDEN_KEY_TOKENS`);
      2. no leaf value is a bare `int`/`float`/`bool` (every quantity must already be
         rendered into a fact string by the caller, e.g. `"task_index": "3"` never
         `"task_index": 3` -- this keeps a literal digit traceable to a whitelisted
         string per rule 3 below, exactly like `interventions.
         assert_no_unexplained_numbers_in_text`'s own contract);
      3. `recommendation` (the one field meant to be read as prose) carries no literal
         B-zone vocabulary (`_FORBIDDEN_TEXT_PATTERN`) and no digit run that is not a
         substring of some other already-whitelisted fact string in the report.
    Public (not `_`-prefixed) so tests can exercise it directly against both legal and
    deliberately-illegal fixtures, not just indirectly through
    `build_route_falsification_report`."""
    for field_name in ("attempts", "verifier_evidence", "detector_events", "remaining_candidates", "route_id"):
        if field_name in report:
            _assert_field_shape(report[field_name], path=field_name)

    recommendation = report.get("recommendation")
    if recommendation is None:
        return
    if not isinstance(recommendation, str):
        raise RouteFalsificationError("Decision 3 blacklist: 'recommendation' must be a str")
    match = _FORBIDDEN_TEXT_PATTERN.search(recommendation)
    if match:
        raise RouteFalsificationError(
            f"Decision 3 blacklist: forbidden B-zone term {match.group()!r} in recommendation text"
        )
    allowed_strings = list(_flatten_strings(report.get("attempts", [])))
    allowed_strings += list(_flatten_strings(report.get("verifier_evidence", [])))
    allowed_strings += list(_flatten_strings(report.get("detector_events", [])))
    allowed_strings += list(_flatten_strings(report.get("remaining_candidates", [])))
    allowed_strings.append(str(report.get("route_id", "")))
    for run in _DIGIT_RUN.findall(recommendation):
        if not any(run in s for s in allowed_strings):
            raise RouteFalsificationError(
                f"Decision 3 blacklist: digit sequence {run!r} in recommendation text is not traceable to a "
                "whitelisted report fact string (possible B-zone numeric leak)"
            )


# ---------------------------------------------------------------------------
# Verifier-evidence normalization (same {phase, result} envelope
# `loop_detector`'s `event_type == "verification"` events already carry).
# ---------------------------------------------------------------------------


def _normalize_verifier_evidence_entry(entry: Mapping[str, Any]) -> Dict[str, Any]:
    result = entry.get("result")
    if result not in VERIFICATION_RESULTS:
        raise TerminationError(
            f"verifier_evidence entry has result={result!r}, must be one of {VERIFICATION_RESULTS!r}"
        )
    return {"phase": entry.get("phase"), "result": result}


def _has_accept_evidence(verifier_evidence: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    normalized = [_normalize_verifier_evidence_entry(e) for e in verifier_evidence]
    return [e for e in normalized if e["result"] == "pass"]


# ---------------------------------------------------------------------------
# RouteFalsified PRESERVE event (mirrors `interventions.trajectory_rolled_back_event`'s
# identity/hash shape).
# ---------------------------------------------------------------------------


def route_falsified_event(
    *,
    route_id: str,
    report_digest: str,
    seq: Optional[int] = None,
) -> Dict[str, Any]:
    """Construct one `RouteFalsified` PRESERVE event (ADR-ECON-007 Decision 4's
    "放弃的合法产物"). Identity fields are `route_id` + `report_digest` (the digest of
    the full structured report this event accompanies, referenced the same way
    `TrajectoryRolledBack.diagnostic_digest` references `Diagnostic.digest` -- the
    event stays a compact tape-anchored pointer, never re-embedding the full report).
    `seq` (optional): stream-position bookkeeping only, never part of the identity
    hash -- same discipline as `trajectory_rolled_back_event`'s own `seq` note."""
    identity = {
        "schema": "route_falsified_identity.v1",
        "route_id": route_id,
        "report_digest": report_digest,
    }
    event_hash = _jcs_sha256(identity)
    event: Dict[str, Any] = {
        "schema_id": ROUTE_FALSIFIED_SCHEMA_ID,
        "event_type": ROUTE_FALSIFIED_EVENT_TYPE,
        "head_effect": PRESERVE_HEAD_EFFECT,
        "route_id": route_id,
        "report_digest": report_digest,
        "event_hash": event_hash,
    }
    if seq is not None:
        event["seq"] = seq
    return event


# ---------------------------------------------------------------------------
# Structured report (ADR-ECON-007 Decision 4's exact six-field payload).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RouteFalsificationReport:
    """Decision 4's structured report: `{route_id, attempts, verifier_evidence[],
    detector_events[], remaining_candidates[], recommendation}`, plus this module's
    own `schema`/`proposal_only`/`digest` bookkeeping. `proposal_only` is always
    `True` -- Decision 4: "报告是 proposal_only,不推进任何 accepted_head" -- this
    module never sets it any other way, and nothing here writes to any
    `accepted_head`/fold at all."""

    route_id: str
    attempts: Tuple[Dict[str, Any], ...]
    verifier_evidence: Tuple[Dict[str, Any], ...]
    detector_events: Tuple[Dict[str, Any], ...]
    remaining_candidates: Tuple[str, ...]
    recommendation: str
    digest: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": ROUTE_FALSIFICATION_REPORT_SCHEMA,
            "route_id": self.route_id,
            "attempts": [dict(a) for a in self.attempts],
            "verifier_evidence": [dict(v) for v in self.verifier_evidence],
            "detector_events": [dict(d) for d in self.detector_events],
            "remaining_candidates": list(self.remaining_candidates),
            "recommendation": self.recommendation,
            "proposal_only": True,
            "digest": self.digest,
        }


def build_route_falsification_report(
    *,
    route_id: str,
    attempts: Sequence[Mapping[str, Any]],
    verifier_evidence: Sequence[Mapping[str, Any]],
    detector_events: Sequence[Mapping[str, Any]],
    remaining_candidates: Sequence[str],
    recommendation: str,
) -> RouteFalsificationReport:
    """Build one Decision-4-shaped, Decision-3-legal `RouteFalsificationReport`.
    Self-validating: raises `RouteFalsificationError` (never returns a non-compliant
    object) if the assembled report would violate `assert_report_has_no_bzone_leak` --
    same self-validating discipline as `interventions.build_diagnostic`."""
    normalized_evidence = [_normalize_verifier_evidence_entry(e) for e in verifier_evidence]
    attempts_t = tuple(dict(a) for a in attempts)
    detector_events_t = tuple(dict(d) for d in detector_events)
    remaining_t = tuple(str(c) for c in remaining_candidates)

    candidate_report = {
        "schema": ROUTE_FALSIFICATION_REPORT_SCHEMA,
        "route_id": route_id,
        "attempts": [dict(a) for a in attempts_t],
        "verifier_evidence": list(normalized_evidence),
        "detector_events": [dict(d) for d in detector_events_t],
        "remaining_candidates": list(remaining_t),
        "recommendation": recommendation,
        "proposal_only": True,
    }
    assert_report_has_no_bzone_leak(candidate_report)

    digest = _jcs_sha256(
        {
            "schema": "route_falsification_report_identity.v1",
            "route_id": route_id,
            "attempts": candidate_report["attempts"],
            "verifier_evidence": candidate_report["verifier_evidence"],
            "detector_events": candidate_report["detector_events"],
            "remaining_candidates": candidate_report["remaining_candidates"],
            "recommendation": recommendation,
        }
    )
    return RouteFalsificationReport(
        route_id=route_id,
        attempts=attempts_t,
        verifier_evidence=tuple(normalized_evidence),
        detector_events=detector_events_t,
        remaining_candidates=remaining_t,
        recommendation=recommendation,
        digest=digest,
    )


# ---------------------------------------------------------------------------
# Termination outcome + the two named entry points + the guard.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TerminationOutcome:
    """`status` is always exactly `ACCEPTED` or `FALSIFIED` -- Decision 4 names no
    third legal termination shape. `accept_evidence` is set only for `ACCEPTED`;
    `event`/`report` are set only for `FALSIFIED` (a dict-shaped `RouteFalsified`
    event and this module's own report dict, respectively)."""

    status: str
    route_id: str
    accept_evidence: Optional[Dict[str, Any]] = None
    event: Optional[Dict[str, Any]] = None
    report: Optional[Dict[str, Any]] = None


def terminate_accepted(*, route_id: str, verifier_evidence: Sequence[Mapping[str, Any]]) -> TerminationOutcome:
    """Decision 4's success path. Legal ONLY when at least one `verifier_evidence`
    entry is a "pass" result -- raises `TerminationError` (BLOCKED, never silently
    guessed/downgraded) otherwise; the caller must use `terminate_falsified` (directly,
    or via `guard_bare_termination`) instead."""
    accept = _has_accept_evidence(verifier_evidence)
    if not accept:
        raise TerminationError(
            f"Decision 4: a success termination requires at least one verifier accept evidence entry; "
            f"route_id={route_id!r} has none"
        )
    return TerminationOutcome(status=ACCEPTED, route_id=route_id, accept_evidence=accept[-1])


def terminate_falsified(
    *,
    route_id: str,
    attempts: Sequence[Mapping[str, Any]],
    verifier_evidence: Sequence[Mapping[str, Any]],
    detector_events: Sequence[Mapping[str, Any]],
    remaining_candidates: Sequence[str],
    recommendation: str,
    seq: Optional[int] = None,
) -> TerminationOutcome:
    """Decision 4's "放弃" path -- always legal. Builds the structured report
    (`build_route_falsification_report`, which raises `RouteFalsificationError` on any
    Decision-3 violation, never silently sanitizing caller content) and the
    accompanying `RouteFalsified` PRESERVE event, and returns both, never advancing
    any `accepted_head` (Decision 4: "proposal_only")."""
    report = build_route_falsification_report(
        route_id=route_id,
        attempts=attempts,
        verifier_evidence=verifier_evidence,
        detector_events=detector_events,
        remaining_candidates=remaining_candidates,
        recommendation=recommendation,
    )
    event = route_falsified_event(route_id=route_id, report_digest=report.digest, seq=seq)
    return TerminationOutcome(status=FALSIFIED, route_id=route_id, event=event, report=report.to_dict())


def guard_bare_termination(
    finalize: Callable[[], Any],
    *,
    route_id: str,
    attempts: Sequence[Mapping[str, Any]],
    verifier_evidence: Sequence[Mapping[str, Any]],
    detector_events: Sequence[Mapping[str, Any]],
    remaining_candidates: Sequence[str],
    recommendation: str,
    seq: Optional[int] = None,
) -> TerminationOutcome:
    """The guard named in this WP's brief: the sole call site through which a caller
    should attempt to end a route's trajectory. `finalize` is the caller's own
    termination attempt (a zero-argument callable; its return value is ignored --
    only whether it raises matters). See the module docstring's "guard_bare_termination"
    section for the exact three-way dispatch this performs; in every case the return
    value is a `TerminationOutcome` and no exception from `finalize` is ever allowed to
    propagate past this function -- that is precisely what makes a bare error-out
    structurally impossible to observe from the caller's side of this guard."""
    try:
        finalize()
    except Exception as exc:  # noqa: BLE001 -- deliberate: Decision 4 makes every
        # uncaught exception here illegal to propagate bare; this IS the guard.
        # Only the exception's *class name* is recorded (never its message/args/
        # traceback -- see module docstring's fact-only rationale).
        intercepted_attempt = {
            "fact_class": "BARE_ERROR_INTERCEPTED",
            "route_id": route_id,
            "exception_class": type(exc).__name__,
        }
        return terminate_falsified(
            route_id=route_id,
            attempts=list(attempts) + [intercepted_attempt],
            verifier_evidence=verifier_evidence,
            detector_events=detector_events,
            remaining_candidates=remaining_candidates,
            recommendation=recommendation,
            seq=seq,
        )

    try:
        return terminate_accepted(route_id=route_id, verifier_evidence=verifier_evidence)
    except TerminationError:
        # `finalize()` completed without raising, but there is still no verifier
        # accept evidence -- Decision 4 forbids treating this as a silent success
        # just as much as a bare error; it becomes the same legal abandonment report
        # path, never a crash, never a guessed accept.
        return terminate_falsified(
            route_id=route_id,
            attempts=attempts,
            verifier_evidence=verifier_evidence,
            detector_events=detector_events,
            remaining_candidates=remaining_candidates,
            recommendation=recommendation,
            seq=seq,
        )


__all__ = [
    "ROUTE_FALSIFIED_SCHEMA_ID",
    "ROUTE_FALSIFIED_EVENT_TYPE",
    "PRESERVE_HEAD_EFFECT",
    "ROUTE_FALSIFICATION_REPORT_SCHEMA",
    "ACCEPTED",
    "FALSIFIED",
    "TerminationError",
    "RouteFalsificationError",
    "assert_report_has_no_bzone_leak",
    "route_falsified_event",
    "RouteFalsificationReport",
    "build_route_falsification_report",
    "TerminationOutcome",
    "terminate_accepted",
    "terminate_falsified",
    "guard_bare_termination",
]
