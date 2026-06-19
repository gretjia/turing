"""turingos.schemas — explicit structural validation for capsule / receipt / event payloads.

Frozen seam (contracts/INTERFACES.md):
    def validate_capsule(capsule: dict) -> None      # raises SchemaInvalid
    def validate_receipt(receipt: dict) -> None
    def validate_event_payload(event_type: str, payload: dict) -> None

This module is the structural P1 (`schema_invalid`) check plus the P0 codec guard
(`ascii_key_violation` / `float_violation`) applied to capsule/receipt/event payloads.

Design constraints (per build harness):
  * EXPLICIT structural validation only — NO jsonschema / no third-party libraries.
    The structure mirrors contracts/capsule.schema.json + contracts/receipt.schema.json
    field-for-field: required fields, additionalProperties=false (unknown top-level/sub
    keys rejected), const schema_id, id/oid patterns, types, enums, array minItems,
    integer minimums.
  * Codec policy [Art. I.1 / contracts/codec_policy.md]: every payload is run through
    codec.assert_ascii_keys (ASCII-only load-bearing keys) and codec.assert_no_floats
    (no float values). Those live in the FROZEN turingos.codec module and are imported
    LAZILY so this module loads even while sibling kernel modules are still being built,
    and so the codec seam stays swappable.
  * Closed-world events: validate_event_payload defers the "is this a real event type?"
    question to the FROZEN turingos.registry.is_known (closed-world: unknown => False),
    never to a private copy of the event list.

Any violation raises turingos.errors.SchemaInvalid(message). The codec guard raises
AsciiKeyViolation / FloatViolation (subclasses of TuringOSError); we surface those as
SchemaInvalid so callers see one structural-validation failure type, while the original
codec error is chained for audit.
"""
from __future__ import annotations

import re
from typing import Any

from . import errors

# --- frozen patterns (mirror the JSON schemas) -------------------------------
CAPSULE_SCHEMA_ID = "turingos.capsule.v1"
RECEIPT_SCHEMA_ID = "turingos.receipt.v1"

_CAPSULE_ID_RE = re.compile(r"^cap:[0-9a-f]{8,64}$")
_RECEIPT_ID_RE = re.compile(r"^rcpt:[0-9a-f]{8,64}$")

_RECEIPT_STATUS = frozenset({"ok", "failed", "timeout", "killed"})


def _fail(message: str) -> "None":
    raise errors.SchemaInvalid(message)


# --- low-level structural helpers -------------------------------------------
def _require_dict(value: Any, where: str) -> dict:
    if not isinstance(value, dict):
        _fail(f"{where}: expected object, got {type(value).__name__}")
    return value  # type: ignore[return-value]


def _check_keys(obj: dict, *, required: tuple, allowed: frozenset, where: str) -> None:
    """Enforce required fields and additionalProperties=false (closed key set)."""
    keys = set(obj.keys())
    missing = [k for k in required if k not in keys]
    if missing:
        _fail(f"{where}: missing required field(s): {', '.join(sorted(missing))}")
    extra = sorted(keys - allowed)
    if extra:
        _fail(f"{where}: unknown key(s) (additionalProperties=false): {', '.join(extra)}")


def _is_int(value: Any) -> bool:
    # bool is a subclass of int in Python; schema integers must NOT accept bools,
    # and floats must NOT pass as integers.
    return isinstance(value, int) and not isinstance(value, bool)


def _check_str(obj: dict, key: str, where: str, *, min_length: int = 0) -> None:
    if key not in obj:
        return
    v = obj[key]
    if not isinstance(v, str):
        _fail(f"{where}.{key}: expected string, got {type(v).__name__}")
    if min_length and len(v) < min_length:
        _fail(f"{where}.{key}: string shorter than minLength {min_length}")


def _check_const(obj: dict, key: str, const: str, where: str) -> None:
    if obj.get(key) != const:
        _fail(f"{where}.{key}: must equal const {const!r}, got {obj.get(key)!r}")


def _check_pattern(obj: dict, key: str, pattern: re.Pattern, where: str) -> None:
    v = obj.get(key)
    if not isinstance(v, str):
        _fail(f"{where}.{key}: expected string, got {type(v).__name__}")
    if not pattern.fullmatch(v):
        _fail(f"{where}.{key}: {v!r} does not match {pattern.pattern}")


def _check_int(obj: dict, key: str, where: str, *, minimum: "int | None" = None) -> None:
    if key not in obj:
        return
    v = obj[key]
    if not _is_int(v):
        _fail(f"{where}.{key}: expected integer, got {type(v).__name__}")
    if minimum is not None and v < minimum:
        _fail(f"{where}.{key}: {v} < minimum {minimum}")


def _check_str_array(
    obj: dict, key: str, where: str, *, min_items: int = 0
) -> None:
    if key not in obj:
        return
    v = obj[key]
    if not isinstance(v, list):
        _fail(f"{where}.{key}: expected array, got {type(v).__name__}")
    if len(v) < min_items:
        _fail(f"{where}.{key}: array has {len(v)} item(s) < minItems {min_items}")
    for i, item in enumerate(v):
        if not isinstance(item, str):
            _fail(f"{where}.{key}[{i}]: expected string, got {type(item).__name__}")


# --- codec seam (lazy; FROZEN turingos.codec) --------------------------------
def _codec_guard(payload: Any, where: str) -> None:
    """Run the P0 codec guard over an arbitrary payload object.

    Imported lazily so schemas.py loads before/independent of the sibling codec
    module, and so the codec seam stays swappable. Codec violations are surfaced
    as SchemaInvalid (with the original codec error chained for audit).
    """
    from . import codec  # lazy: frozen turingos.codec seam

    try:
        codec.assert_ascii_keys(payload)
    except errors.AsciiKeyViolation as exc:
        raise errors.SchemaInvalid(f"{where}: {exc}") from exc
    try:
        codec.assert_no_floats(payload)
    except errors.FloatViolation as exc:
        raise errors.SchemaInvalid(f"{where}: {exc}") from exc


# --- public API: validate_capsule -------------------------------------------
_CAPSULE_REQUIRED = (
    "schema_id",
    "capsule_id",
    "atom_id",
    "allowed_files",
    "budget",
    "acceptance_commands",
    "context",
)
_CAPSULE_ALLOWED = frozenset(
    {
        "schema_id",
        "capsule_id",
        "atom_id",
        "module_id",
        "goal_ref",
        "intent",
        "allowed_files",
        "forbidden_files",
        "budget",
        "injected_rules",
        "acceptance_commands",
        "context",
    }
)
_BUDGET_REQUIRED = ("wall_seconds", "max_retries")
_BUDGET_ALLOWED = frozenset({"wall_seconds", "max_retries"})
_CONTEXT_REQUIRED = ("tape_tip", "accepted_head")
_CONTEXT_ALLOWED = frozenset({"tape_tip", "accepted_head"})
_INJECTED_RULE_REQUIRED = ("failure_class", "rule")
_INJECTED_RULE_ALLOWED = frozenset({"failure_class", "rule"})


def validate_capsule(capsule: dict) -> None:
    """Validate a Shielded Work Capsule against turingos.capsule.v1. Raises SchemaInvalid."""
    where = "capsule"
    _require_dict(capsule, where)
    # codec guard first: ASCII-only keys / no floats over the whole object.
    _codec_guard(capsule, where)

    _check_keys(capsule, required=_CAPSULE_REQUIRED, allowed=_CAPSULE_ALLOWED, where=where)

    _check_const(capsule, "schema_id", CAPSULE_SCHEMA_ID, where)
    _check_pattern(capsule, "capsule_id", _CAPSULE_ID_RE, where)
    _check_str(capsule, "atom_id", where, min_length=1)
    # optional free-form strings
    _check_str(capsule, "module_id", where)
    _check_str(capsule, "goal_ref", where)
    _check_str(capsule, "intent", where)

    _check_str_array(capsule, "allowed_files", where, min_items=0)
    _check_str_array(capsule, "forbidden_files", where, min_items=0)
    _check_str_array(capsule, "acceptance_commands", where, min_items=1)

    # budget sub-object
    budget = _require_dict(capsule["budget"], f"{where}.budget")
    _check_keys(
        budget, required=_BUDGET_REQUIRED, allowed=_BUDGET_ALLOWED, where=f"{where}.budget"
    )
    _check_int(budget, "wall_seconds", f"{where}.budget", minimum=1)
    _check_int(budget, "max_retries", f"{where}.budget", minimum=0)

    # context sub-object
    context = _require_dict(capsule["context"], f"{where}.context")
    _check_keys(
        context, required=_CONTEXT_REQUIRED, allowed=_CONTEXT_ALLOWED, where=f"{where}.context"
    )
    _check_str(context, "tape_tip", f"{where}.context")
    _check_str(context, "accepted_head", f"{where}.context")

    # injected_rules (shield) — array of {failure_class, rule}; no raw failure leakage.
    if "injected_rules" in capsule:
        rules = capsule["injected_rules"]
        if not isinstance(rules, list):
            _fail(f"{where}.injected_rules: expected array, got {type(rules).__name__}")
        for i, rule in enumerate(rules):
            rwhere = f"{where}.injected_rules[{i}]"
            _require_dict(rule, rwhere)
            _check_keys(
                rule,
                required=_INJECTED_RULE_REQUIRED,
                allowed=_INJECTED_RULE_ALLOWED,
                where=rwhere,
            )
            _check_str(rule, "failure_class", rwhere)
            _check_str(rule, "rule", rwhere)


# --- public API: validate_receipt -------------------------------------------
_RECEIPT_REQUIRED = (
    "schema_id",
    "receipt_id",
    "capsule_id",
    "worker_id",
    "worktree_path",
    "candidate",
    "status",
)
_RECEIPT_ALLOWED = frozenset(
    {
        "schema_id",
        "receipt_id",
        "capsule_id",
        "worker_id",
        "worktree_path",
        "candidate",
        "declared_test_results",
        "evidence_digests",
        "status",
        "no_orphan",
    }
)
_CANDIDATE_REQUIRED = ("tree_oid", "files_touched")
_CANDIDATE_ALLOWED = frozenset({"tree_oid", "files_touched", "macro_commit"})
_TEST_RESULT_REQUIRED = ("command", "exit_code")
_TEST_RESULT_ALLOWED = frozenset({"command", "exit_code"})


def validate_receipt(receipt: dict) -> None:
    """Validate a Worker Receipt against turingos.receipt.v1. Raises SchemaInvalid."""
    where = "receipt"
    _require_dict(receipt, where)
    _codec_guard(receipt, where)

    _check_keys(receipt, required=_RECEIPT_REQUIRED, allowed=_RECEIPT_ALLOWED, where=where)

    _check_const(receipt, "schema_id", RECEIPT_SCHEMA_ID, where)
    _check_pattern(receipt, "receipt_id", _RECEIPT_ID_RE, where)
    _check_pattern(receipt, "capsule_id", _CAPSULE_ID_RE, where)
    _check_str(receipt, "worker_id", where)
    _check_str(receipt, "worktree_path", where)

    status = receipt.get("status")
    if status not in _RECEIPT_STATUS:
        _fail(
            f"{where}.status: {status!r} not in enum "
            f"{{{', '.join(sorted(_RECEIPT_STATUS))}}}"
        )

    # candidate sub-object: requires tree_oid + files_touched.
    candidate = _require_dict(receipt["candidate"], f"{where}.candidate")
    _check_keys(
        candidate,
        required=_CANDIDATE_REQUIRED,
        allowed=_CANDIDATE_ALLOWED,
        where=f"{where}.candidate",
    )
    _check_str(candidate, "tree_oid", f"{where}.candidate")
    _check_str_array(candidate, "files_touched", f"{where}.candidate")
    _check_str(candidate, "macro_commit", f"{where}.candidate")

    # declared_test_results — array of {command, exit_code}. P6 RE-RUNS; recorded for audit.
    if "declared_test_results" in receipt:
        results = receipt["declared_test_results"]
        if not isinstance(results, list):
            _fail(
                f"{where}.declared_test_results: expected array, got {type(results).__name__}"
            )
        for i, tr in enumerate(results):
            twhere = f"{where}.declared_test_results[{i}]"
            _require_dict(tr, twhere)
            _check_keys(
                tr,
                required=_TEST_RESULT_REQUIRED,
                allowed=_TEST_RESULT_ALLOWED,
                where=twhere,
            )
            _check_str(tr, "command", twhere)
            _check_int(tr, "exit_code", twhere)

    _check_str_array(receipt, "evidence_digests", where)

    if "no_orphan" in receipt and not isinstance(receipt["no_orphan"], bool):
        _fail(
            f"{where}.no_orphan: expected boolean, got {type(receipt['no_orphan']).__name__}"
        )


# --- public API: validate_event_payload -------------------------------------
def validate_event_payload(event_type: str, payload: dict) -> None:
    """Validate an event payload: closed-world type + dict + codec guard.

    The 18-event registry is closed-world; an unknown event_type is a schema
    violation. Per-event payload SCHEMAS are progressively elaborated in later
    modules; in 1.0 the structural floor is: known type, dict payload, ASCII-only
    keys, no floats. Raises SchemaInvalid.
    """
    from . import registry  # lazy: frozen turingos.registry seam

    if not isinstance(event_type, str) or not registry.is_known(event_type):
        _fail(f"event_payload: unknown event_type {event_type!r} (closed-world registry)")

    where = f"event_payload[{event_type}]"
    _require_dict(payload, where)
    _codec_guard(payload, where)
