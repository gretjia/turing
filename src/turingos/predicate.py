"""turingos.predicate — the deterministic Predicate kernel (B-4, ADR-0004) [Art. I.1].

Frozen Stage-0 interface (contracts/INTERFACES.md predicate.py section,
contracts/predicate_set.md):

    @dataclass(frozen=True) PredicateResult{passed, reasons, reason_digest}
    def evaluate(*, capsule, receipt, worktree, tape, event_type) -> PredicateResult
    CHECK_CODES = (...)

The Predicate that gates a SOVEREIGN_ACCEPT advance is a boolean f: X -> {0,1} over Tape
bytes — MECHANICALLY DECIDABLE ONLY. It runs the P0 codec guard plus the closed check set
P1..P9 and NOTHING else. There is NO style / NL / human-review / opinion check anywhere in
this gate; such concerns are routed to a RiskFinding or human review, never the boolean gate
(release-audit 临时违宪 #5).

evaluate is PURE: it reads the capsule/receipt/worktree/tape and returns a result. It NEVER
appends to the tape and NEVER moves a ref (the loop driver records a PredicateEvaluated event
separately; emitting it is not this function's job).

Determinism contract: two evaluations over identical inputs yield identical `passed` AND
identical `reason_digest`. The digest is sha256(JCS(sorted reason records)); each reason record
is {check, ok, reason_code, detail} with a STABLE detail derived purely from the inputs, so
identical inputs produce an identical digest.

Every individual check is wrapped so an unexpected exception surfaces as a failing reason record
(never a crash) — the gate is total over its inputs.

Stdlib only (`subprocess`, `os`, `dataclasses`).
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

from . import codec, registry, replay, schemas
from .errors import (
    AsciiKeyViolation,
    FloatViolation,
    SchemaInvalid,
    TuringOSError,
)

# The closed set of FAIL reason codes (contracts/predicate_set.md). Frozen.
CHECK_CODES = (
    "schema_invalid",
    "parent_mismatch",
    "scope_violation",
    "isolation_violation",
    "receipt_hash_mismatch",
    "test_fail",
    "anchor_mismatch",
    "replay_mismatch",
    "advance_rule_violation",
    "ascii_key_violation",
    "float_violation",
)

# Registry event names the predicate inspects on the tape (read-only).
_RECEIPT_EVENT = "WorkerReceiptImported"
_MACRO_EVENT = "MacroObservationImported"

# The event class whose advance rule (P9) is enforced.
_ADVANCE_CLASS = "SOVEREIGN_ACCEPT"

# Deterministic git identity for the read-only worktree/tape plumbing P7 may run.
_GIT_ENV = {
    "GIT_AUTHOR_NAME": "turingos",
    "GIT_AUTHOR_EMAIL": "tape@turingos.local",
    "GIT_COMMITTER_NAME": "turingos",
    "GIT_COMMITTER_EMAIL": "tape@turingos.local",
    "GIT_AUTHOR_DATE": "2026-06-20T00:00:00+0000",
    "GIT_COMMITTER_DATE": "2026-06-20T00:00:00+0000",
}


@dataclass(frozen=True)
class PredicateResult:
    """The result of one deterministic predicate evaluation over Tape bytes.

    passed         — True iff every reason record is ok (P0 + P1..P9 all hold).
    reasons        — one record per check: {check, ok, reason_code|None, detail}.
    reason_digest  — sha256(JCS(sorted reason records)); byte-deterministic for identical inputs.
    """

    passed: bool
    reasons: tuple
    reason_digest: str


# --- reason record helper ---------------------------------------------------


def _ok(check: str, detail: str = "") -> dict:
    return {"check": check, "ok": True, "reason_code": None, "detail": detail}


def _fail(check: str, reason_code: str, detail: str) -> dict:
    return {"check": check, "ok": False, "reason_code": reason_code, "detail": detail}


# --- git read-only plumbing (P7) -------------------------------------------


def _git_capture(repo: str, *args: str):
    env = {**os.environ, **_GIT_ENV}
    return subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True, env=env
    )


def _is_git_repo(path: str) -> bool:
    res = _git_capture(path, "rev-parse", "--is-inside-work-tree")
    return res.returncode == 0 and res.stdout.strip() == "true"


def _worktree_tree_oid(path: str):
    res = _git_capture(path, "rev-parse", "HEAD^{tree}")
    if res.returncode != 0:
        return None
    return res.stdout.strip() or None


# --- path isolation helper (P4) --------------------------------------------


def _is_isolated_path(path: str) -> bool:
    """A touched path is isolated iff it is relative, has no '..' segment, is not absolute."""
    if not isinstance(path, str) or not path:
        return False
    if os.path.isabs(path):
        return False
    # Reject Windows-style drive/absolute too (defensive); split on both separators.
    normalized = path.replace("\\", "/")
    segments = normalized.split("/")
    if ".." in segments:
        return False
    return True


# --- individual checks (P0..P9) --------------------------------------------
# Each returns a reason record. Each is wrapped by _safe so an unexpected error becomes a
# failing record rather than crashing the total gate.


def _check_p0_codec(capsule: dict, receipt: dict) -> dict:
    """P0 — ascii-key / no-float guard on both the capsule and the receipt."""
    for name, payload in (("capsule", capsule), ("receipt", receipt)):
        try:
            codec.assert_ascii_keys(payload)
        except AsciiKeyViolation as exc:
            return _fail("P0_codec", "ascii_key_violation", f"{name}: {exc}")
        try:
            codec.assert_no_floats(payload)
        except FloatViolation as exc:
            return _fail("P0_codec", "float_violation", f"{name}: {exc}")
    return _ok("P0_codec", "ascii keys + no floats on capsule and receipt")


def _check_p1_schema(capsule: dict, receipt: dict) -> dict:
    """P1 — capsule and receipt validate against their frozen schemas."""
    try:
        schemas.validate_capsule(capsule)
    except SchemaInvalid as exc:
        return _fail("P1_schema", "schema_invalid", f"capsule: {exc}")
    try:
        schemas.validate_receipt(receipt)
    except SchemaInvalid as exc:
        return _fail("P1_schema", "schema_invalid", f"receipt: {exc}")
    return _ok("P1_schema", "capsule + receipt schema valid")


def _check_p2_parent(capsule: dict, tape) -> dict:
    """P2 — capsule context tape_tip equals the live tape_tip OR is an ancestor (FF-only)."""
    ctx = capsule.get("context")
    if not isinstance(ctx, dict):
        return _fail("P2_parent", "parent_mismatch", "capsule.context missing")
    declared = ctx.get("tape_tip")
    live = tape.tape_tip()
    if declared == live:
        return _ok("P2_parent", "tape_tip equals live tip")
    if not isinstance(declared, str) or not declared:
        return _fail("P2_parent", "parent_mismatch", f"declared tape_tip {declared!r} != live {live!r}")
    if live is None:
        return _fail("P2_parent", "parent_mismatch", f"declared tape_tip {declared!r} but tape empty")
    # FF: declared must be an ancestor of the live tip.
    res = _git_capture(tape.repo_dir, "merge-base", "--is-ancestor", declared, live)
    if res.returncode == 0:
        return _ok("P2_parent", f"tape_tip {declared} is ancestor of live tip")
    return _fail(
        "P2_parent", "parent_mismatch",
        f"declared tape_tip {declared!r} is neither live tip {live!r} nor an ancestor",
    )


def _check_p3_scope(capsule: dict, receipt: dict) -> dict:
    """P3 — files_touched subset of allowed_files and disjoint from forbidden_files."""
    candidate = receipt.get("candidate") if isinstance(receipt, dict) else None
    touched = candidate.get("files_touched") if isinstance(candidate, dict) else None
    if not isinstance(touched, list):
        return _fail("P3_scope", "scope_violation", "receipt.candidate.files_touched missing")
    allowed = capsule.get("allowed_files")
    if not isinstance(allowed, list):
        return _fail("P3_scope", "scope_violation", "capsule.allowed_files missing")
    forbidden = capsule.get("forbidden_files", [])
    if not isinstance(forbidden, list):
        forbidden = []

    touched_set = set(touched)
    allowed_set = set(allowed)
    forbidden_set = set(forbidden)

    not_allowed = sorted(touched_set - allowed_set)
    if not_allowed:
        return _fail(
            "P3_scope", "scope_violation",
            f"touched paths outside allowed_files: {not_allowed}",
        )
    overlap = sorted(touched_set & forbidden_set)
    if overlap:
        return _fail(
            "P3_scope", "scope_violation",
            f"touched paths in forbidden_files: {overlap}",
        )
    return _ok("P3_scope", f"{len(touched_set)} touched path(s) within scope")


def _check_p4_isolation(receipt: dict) -> dict:
    """P4 — every touched path is relative, has no '..' segment, is not absolute."""
    candidate = receipt.get("candidate") if isinstance(receipt, dict) else None
    touched = candidate.get("files_touched") if isinstance(candidate, dict) else None
    if not isinstance(touched, list):
        return _fail("P4_isolation", "isolation_violation", "receipt.candidate.files_touched missing")
    offenders = sorted(p for p in touched if not _is_isolated_path(p))
    if offenders:
        return _fail(
            "P4_isolation", "isolation_violation",
            f"non-isolated touched path(s): {offenders}",
        )
    return _ok("P4_isolation", f"{len(touched)} touched path(s) isolated")


def _latest_event_payload_hash(tape, event_type: str):
    """Return (payload, payload_hash) of the LATEST event of `event_type` on the tape, or (None, None).

    Reads Tape bytes only (tape.walk); the last matching event in chronological order wins.
    """
    found = None
    for ev in tape.walk():
        if ev.get("event_type") == event_type:
            found = ev
    if found is None:
        return None, None
    return found.get("payload"), found.get("envelope", {}).get("payload_hash")


def _check_p5_receipt_hash(receipt: dict, tape) -> dict:
    """P5 — content_digest(receipt) equals the latest imported WorkerReceiptImported payload_hash."""
    _, imported_hash = _latest_event_payload_hash(tape, _RECEIPT_EVENT)
    if imported_hash is None:
        return _fail(
            "P5_receipt_hash", "receipt_hash_mismatch",
            "no WorkerReceiptImported event on the tape",
        )
    try:
        recomputed = codec.content_digest(receipt)
    except (AsciiKeyViolation, FloatViolation) as exc:
        return _fail("P5_receipt_hash", "receipt_hash_mismatch", f"receipt not codec-canonical: {exc}")
    if recomputed != imported_hash:
        return _fail(
            "P5_receipt_hash", "receipt_hash_mismatch",
            f"recomputed {recomputed} != imported {imported_hash}",
        )
    return _ok("P5_receipt_hash", "receipt digest matches imported payload_hash")


def _check_p6_tests(capsule: dict, worktree: str) -> dict:
    """P6 — every command in capsule.acceptance_commands exits 0 (re-run, cwd=worktree)."""
    commands = capsule.get("acceptance_commands")
    if not isinstance(commands, list) or not commands:
        return _fail("P6_tests", "test_fail", "no acceptance_commands declared")
    failures = []
    for cmd in commands:
        try:
            res = subprocess.run(
                cmd, shell=True, cwd=worktree,
                capture_output=True, text=True,
            )
        except OSError as exc:
            failures.append(f"{cmd!r} -> spawn error: {exc}")
            continue
        if res.returncode != 0:
            failures.append(f"{cmd!r} -> exit {res.returncode}")
    if failures:
        return _fail("P6_tests", "test_fail", "; ".join(failures))
    return _ok("P6_tests", f"{len(commands)} acceptance command(s) exit 0")


def _check_p7_anchor(receipt: dict, worktree: str, tape) -> dict:
    """P7 — candidate tree_oid non-empty and binds the declared Macro anchor / worktree tree."""
    candidate = receipt.get("candidate") if isinstance(receipt, dict) else None
    tree_oid = candidate.get("tree_oid") if isinstance(candidate, dict) else None
    if not isinstance(tree_oid, str) or not tree_oid:
        return _fail("P7_anchor", "anchor_mismatch", "receipt.candidate.tree_oid empty/missing")

    macro_payload, _ = _latest_event_payload_hash(tape, _MACRO_EVENT)
    if isinstance(macro_payload, dict) and macro_payload.get("tree_oid") is not None:
        anchor = macro_payload.get("tree_oid")
        if tree_oid != anchor:
            return _fail(
                "P7_anchor", "anchor_mismatch",
                f"candidate tree_oid {tree_oid} != Macro anchor {anchor}",
            )
        return _ok("P7_anchor", "candidate tree_oid binds the Macro anchor")

    # No Macro anchor imported: fall back to binding the worktree git tree if it is a repo.
    if _is_git_repo(worktree):
        wt_tree = _worktree_tree_oid(worktree)
        if wt_tree is None:
            return _fail("P7_anchor", "anchor_mismatch", "worktree has no resolvable HEAD^{tree}")
        if tree_oid != wt_tree:
            return _fail(
                "P7_anchor", "anchor_mismatch",
                f"candidate tree_oid {tree_oid} != worktree tree {wt_tree}",
            )
        return _ok("P7_anchor", "candidate tree_oid binds the worktree tree")

    # Non-empty tree_oid, no anchor and no git worktree to bind against: accept the non-empty anchor.
    return _ok("P7_anchor", "candidate tree_oid present (no anchor/worktree to cross-bind)")


def _check_p8_replay(tape) -> dict:
    """P8 — replay(tape) rebuilt accepted_head equals tape.accepted_head() (replay invariant)."""
    try:
        state = replay.replay(tape)
    except TuringOSError as exc:
        return _fail("P8_replay", "replay_mismatch", f"replay failed: {exc}")
    on_disk = tape.accepted_head()
    if state.accepted_head != on_disk:
        return _fail(
            "P8_replay", "replay_mismatch",
            f"rebuilt accepted_head {state.accepted_head!r} != on-disk {on_disk!r}",
        )
    return _ok("P8_replay", "replay rebuilds accepted_head byte-equal")


def _check_p9_advance(capsule: dict, tape, event_type: str) -> dict:
    """P9 — for a SOVEREIGN_ACCEPT event, accepted_head FF must hold; non-accept is ok."""
    try:
        ev_class = registry.event_class(event_type)
    except TuringOSError as exc:
        return _fail("P9_advance", "advance_rule_violation", f"unknown event_type: {exc}")

    if ev_class != _ADVANCE_CLASS:
        return _ok("P9_advance", f"event_type {event_type} is not SOVEREIGN_ACCEPT (no advance)")

    ctx = capsule.get("context")
    accepted_before = ctx.get("accepted_head") if isinstance(ctx, dict) else None
    live_tip = tape.tape_tip()
    if live_tip is None:
        return _fail("P9_advance", "advance_rule_violation", "tape empty; cannot advance")
    if not isinstance(accepted_before, str) or not accepted_before:
        return _fail(
            "P9_advance", "advance_rule_violation",
            f"capsule context accepted_head {accepted_before!r} not set",
        )
    if accepted_before == live_tip:
        return _ok("P9_advance", "accepted_head == tape_tip (FF holds)")
    res = _git_capture(tape.repo_dir, "merge-base", "--is-ancestor", accepted_before, live_tip)
    if res.returncode == 0:
        return _ok("P9_advance", "accepted_head is ancestor of tape_tip (FF holds)")
    return _fail(
        "P9_advance", "advance_rule_violation",
        f"accepted_head {accepted_before!r} is not an ancestor of tape_tip {live_tip!r}",
    )


# --- safe wrapper -----------------------------------------------------------


def _safe(check_name: str, fn) -> dict:
    """Run a check; convert any unexpected exception into a deterministic failing record.

    The reason_code is the FIRST code in CHECK_CODES owned by this check is not knowable here,
    so an unexpected error is reported under a stable synthetic code per check via the detail —
    but to keep the closed code set, we map an unexpected error to the check's primary code.
    """
    try:
        return fn()
    except Exception as exc:  # total gate: never let a check crash the evaluation.
        return _fail(check_name, _PRIMARY_CODE[check_name], f"unexpected error: {type(exc).__name__}: {exc}")


# Map each check to its primary FAIL reason code (for the _safe fallback path).
_PRIMARY_CODE = {
    "P0_codec": "ascii_key_violation",
    "P1_schema": "schema_invalid",
    "P2_parent": "parent_mismatch",
    "P3_scope": "scope_violation",
    "P4_isolation": "isolation_violation",
    "P5_receipt_hash": "receipt_hash_mismatch",
    "P6_tests": "test_fail",
    "P7_anchor": "anchor_mismatch",
    "P8_replay": "replay_mismatch",
    "P9_advance": "advance_rule_violation",
}


# --- the public gate --------------------------------------------------------


def evaluate(*, capsule: dict, receipt: dict, worktree: str, tape,
             event_type: str) -> PredicateResult:
    """Run the closed mechanical check set (P0 + P1..P9) and return a deterministic result.

    PURE: reads only the supplied inputs + the Tape bytes; never appends, never moves a ref.
    Total: every check is wrapped so an unexpected error becomes a failing record, not a crash.
    Deterministic: identical inputs yield identical `passed` AND identical `reason_digest`.
    """
    reasons = [
        _safe("P0_codec", lambda: _check_p0_codec(capsule, receipt)),
        _safe("P1_schema", lambda: _check_p1_schema(capsule, receipt)),
        _safe("P2_parent", lambda: _check_p2_parent(capsule, tape)),
        _safe("P3_scope", lambda: _check_p3_scope(capsule, receipt)),
        _safe("P4_isolation", lambda: _check_p4_isolation(receipt)),
        _safe("P5_receipt_hash", lambda: _check_p5_receipt_hash(receipt, tape)),
        _safe("P6_tests", lambda: _check_p6_tests(capsule, worktree)),
        _safe("P7_anchor", lambda: _check_p7_anchor(receipt, worktree, tape)),
        _safe("P8_replay", lambda: _check_p8_replay(tape)),
        _safe("P9_advance", lambda: _check_p9_advance(capsule, tape, event_type)),
    ]

    passed = all(r["ok"] for r in reasons)

    # reason_digest = sha256(JCS(sorted reason records)). Sort by check name; each record carries
    # a STABLE detail derived purely from the inputs, so identical inputs => identical digest.
    sorted_reasons = sorted(
        (
            {
                "check": r["check"],
                "ok": r["ok"],
                "reason_code": r["reason_code"],
                "detail": r["detail"],
            }
            for r in reasons
        ),
        key=lambda r: r["check"],
    )
    reason_digest = codec.content_digest({"reasons": sorted_reasons})

    return PredicateResult(
        passed=passed,
        reasons=tuple(reasons),
        reason_digest=reason_digest,
    )
