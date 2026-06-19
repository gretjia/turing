"""turingos.capsule — the Shielded Work Capsule builder + FailureMemory shield (S-4).

Frozen seam (contracts/INTERFACES.md capsule.py section + contracts/capsule.schema.json):

    def build_capsule(tape, atom, *, failure_memory) -> dict   # emits WorkCapsuleBuilt (PROPOSAL)
    class FailureMemory:
        def classify(self, failure_node) -> dict              # raw FailureNode -> {failure_class, rule}
        def relevant_rules(self, atom) -> list                # ONLY rules whose class is relevant to atom

This module is the SHIELD [Art. II / Art. III.4, Goodhart shield]. The constitutional pattern
is BROADCAST + SHIELD:

    raw failure  ->  private evidence (stays on the Tape, reachable)
                 ->  FailureClass (a coarse, mechanical bucket)
                 ->  an ABSTRACT rule (a lesson, e.g. "declared tests must include boundary case X")
                 ->  inject ONLY the relevant rule into the next capsule.

What the capsule carries is therefore SCOPE + budget + the declared acceptance commands + the
relevant abstract rules, and NOTHING ELSE. In particular a capsule MUST NOT contain:

  * raw failure payloads / worker stdout / stack traces / stderr — those are private evidence,
    broadcast nowhere; they live on the Tape as FailureNode bytes (reachable, not re-injected);
  * any gate / scoring / predicate logic — the candidate worker must never see the gate it will
    be judged by (Art. III.4: optimizing to a visible gate is Goodhart's law). The deterministic
    Predicate kernel (turingos.predicate) is the gate, and it lives OUTSIDE the capsule.

`build_capsule` produces a `turingos.capsule.v1` object, validates it with
`schemas.validate_capsule` (the same structural floor every consumer relies on), emits a
`WorkCapsuleBuilt` event (registry class PROPOSAL: head_effect PRESERVE -> tape_tip advances,
accepted_head does NOT — building a capsule is never a sovereign act), and returns the capsule.

`capsule_id` is content-addressed: "cap:" + a hash over the capsule body (atom scope + budget +
acceptance commands + context + injected rules), so identical inputs yield an identical id and a
change in any load-bearing input changes the id. Because the context binds the live `tape_tip`
and `accepted_head`, two builds against different tips get different ids.

Stdlib only (`hashlib` via the frozen turingos.codec). No third-party deps.
"""
from __future__ import annotations

import hashlib

from . import codec, schemas
from .errors import SchemaInvalid

# Registry event name this module emits (PROPOSAL / PRESERVE: tape_tip advances, accepted_head does not).
_CAPSULE_EVENT = "WorkCapsuleBuilt"

# Default budget for a 1.0 local dogfood capsule (integers only — no floats per codec policy).
# These are scope/resource bounds, NOT gate logic: they bound how long/often a worker may run,
# they do not score or judge the candidate.
_DEFAULT_WALL_SECONDS = 900
_DEFAULT_MAX_RETRIES = 1


# --- FailureMemory: the shield's lift-and-filter -----------------------------


class FailureMemory:
    """Lifts raw FailureNodes to ABSTRACT FailureClass rules and filters them to an atom.

    The shield never re-broadcasts raw failure detail. `classify` reads a raw FailureNode
    payload, derives a coarse mechanical `failure_class` from its reason_code, mints an
    ABSTRACT rule (a generalizable lesson, derived from the class — never the raw stdout /
    stack trace), remembers it (keyed by where the failure occurred), and returns
    `{failure_class, rule}`.

    `relevant_rules(atom)` returns ONLY the rules whose remembered origin is RELEVANT to the
    given atom — i.e. failures from the same atom or the same module. Failures from unrelated
    atoms/modules are filtered OUT, so a capsule for atom X never inherits a lesson learned on
    an unrelated atom Y (the S-4 "inject only the relevant rule" property).
    """

    # Map a mechanical predicate reason_code to a coarse, stable FailureClass bucket.
    # (failure_class is orthogonal to event_type; this is the companion failure-class axis.)
    _CLASS_BY_REASON = {
        "schema_invalid": "SchemaShape",
        "parent_mismatch": "ParentTip",
        "scope_violation": "Scope",
        "isolation_violation": "Isolation",
        "receipt_hash_mismatch": "ReceiptIntegrity",
        "test_fail": "DeclaredTests",
        "anchor_mismatch": "MacroAnchor",
        "replay_mismatch": "ReplayEquality",
        "advance_rule_violation": "AdvanceRule",
        "ascii_key_violation": "Codec",
        "float_violation": "Codec",
    }

    # The ABSTRACT lesson minted per FailureClass. These are generalizable rules a worker can act
    # on — never raw failure detail, never the gate itself.
    _RULE_BY_CLASS = {
        "SchemaShape": "emitted payloads must validate against their frozen schema before append",
        "ParentTip": "build on the live tape_tip (FF-only); re-read the tip before proposing",
        "Scope": "touch ONLY the declared allowed_files; do not write outside capsule scope",
        "Isolation": "write only inside the assigned worktree; use relative, '..'-free paths",
        "ReceiptIntegrity": "the receipt must be canonical so its digest matches the imported hash",
        "DeclaredTests": "declared tests must cover the boundary cases the change is meant to handle",
        "MacroAnchor": "bind the candidate to the declared Macro tree anchor exactly",
        "ReplayEquality": "all accepted state must be rebuildable from Tape bytes alone",
        "AdvanceRule": "only a SOVEREIGN_ACCEPT with a passing predicate may advance accepted_head",
        "Codec": "load-bearing keys must be ASCII and values must contain no floats",
    }

    _UNKNOWN_CLASS = "Unclassified"
    _UNKNOWN_RULE = "review the recorded FailureNode evidence and tighten the declared acceptance"

    def __init__(self) -> None:
        # Each remembered entry: {failure_class, rule, atom_id, module_id}. atom_id/module_id are
        # the shield's RELEVANCE keys (internal filter axis) — they are NOT copied into a capsule's
        # injected_rules (which is strictly {failure_class, rule}); they only decide what is relevant.
        self._memory: list = []

    @staticmethod
    def _reason_code(failure_node: dict) -> str:
        """Extract the mechanical reason_code from a raw FailureNode payload (best-effort, total)."""
        if not isinstance(failure_node, dict):
            return ""
        rc = failure_node.get("reason_code")
        if isinstance(rc, str) and rc:
            return rc
        # Some FailureNodes nest the code under a predicate result; check a couple of stable spots.
        result = failure_node.get("predicate_result")
        if isinstance(result, dict):
            rc = result.get("reason_code")
            if isinstance(rc, str) and rc:
                return rc
        return ""

    def classify(self, failure_node: dict) -> dict:
        """Lift a raw FailureNode to an ABSTRACT {failure_class, rule} and remember it.

        Reads ONLY the mechanical reason_code + the atom/module identity from the raw node; the
        raw stdout / stack trace / stderr are deliberately ignored (never lifted, never broadcast).
        Returns the abstract {failure_class, rule}; the same dict shape that goes into a capsule's
        injected_rules. Determinism: identical reason_code -> identical class -> identical rule.
        """
        reason_code = self._reason_code(failure_node)
        failure_class = self._CLASS_BY_REASON.get(reason_code, self._UNKNOWN_CLASS)
        rule = self._RULE_BY_CLASS.get(failure_class, self._UNKNOWN_RULE)

        atom_id = failure_node.get("atom_id") if isinstance(failure_node, dict) else None
        module_id = failure_node.get("module_id") if isinstance(failure_node, dict) else None

        self._memory.append(
            {
                "failure_class": failure_class,
                "rule": rule,
                "atom_id": atom_id,
                "module_id": module_id,
            }
        )
        # Return only the abstract pair (no relevance keys leak to the caller / capsule).
        return {"failure_class": failure_class, "rule": rule}

    @staticmethod
    def _is_relevant(entry: dict, atom: dict) -> bool:
        """A remembered failure is relevant to `atom` iff it occurred on the same atom or module."""
        if not isinstance(atom, dict):
            return False
        atom_id = atom.get("atom_id")
        module_id = atom.get("module_id")
        if entry.get("atom_id") is not None and entry.get("atom_id") == atom_id:
            return True
        if entry.get("module_id") is not None and entry.get("module_id") == module_id:
            return True
        return False

    def relevant_rules(self, atom: dict) -> list:
        """Return ONLY the abstract rules relevant to `atom` (de-duplicated, deterministic order).

        Filters the remembered failures to those that occurred on the same atom or module, lifts
        each to its {failure_class, rule} pair, and de-duplicates by (failure_class, rule). The
        returned list is exactly the capsule's injected_rules: NO raw payload, NO relevance keys,
        NO unrelated class. Given a history with >=2 UNRELATED classes, only the relevant class(es)
        survive this filter.
        """
        out: list = []
        seen = set()
        for entry in self._memory:
            if not self._is_relevant(entry, atom):
                continue
            pair = (entry["failure_class"], entry["rule"])
            if pair in seen:
                continue
            seen.add(pair)
            out.append({"failure_class": entry["failure_class"], "rule": entry["rule"]})
        return out


# --- build_capsule: the shielded scope envelope ------------------------------


def _capsule_id(body: dict) -> str:
    """Content-address the capsule body: "cap:" + first 32 hex of sha256(JCS(body)).

    Uses the frozen turingos.codec for the canonical bytes (ASCII-key / no-float guard included),
    so identical bodies yield an identical id and any load-bearing change perturbs it. 32 hex chars
    sits inside the schema's ^cap:[0-9a-f]{8,64}$ pattern.
    """
    digest = hashlib.sha256(codec.canonical_bytes(body)).hexdigest()
    return "cap:" + digest[:32]


def build_capsule(tape: "Tape", atom: dict, *, failure_memory: "FailureMemory") -> dict:
    """Build a Shielded Work Capsule for `atom`, emit WorkCapsuleBuilt, and return the capsule.

    The capsule is SCOPE + budget + declared acceptance commands + context + the relevant abstract
    rules — and nothing else (the shield). It validates against turingos.capsule.v1 before emission;
    an invalid capsule raises SchemaInvalid and NO commit lands. On success exactly one Micro commit
    is written: WorkCapsuleBuilt is a PROPOSAL (PRESERVE), so tape_tip advances while accepted_head
    does NOT (building a capsule is never a sovereign act).

    The injected_rules come from `failure_memory.relevant_rules(atom)` — ONLY the abstract rules
    relevant to this atom; unrelated FailureClasses and ALL raw failure detail are filtered out
    upstream by the shield, never reaching the capsule.
    """
    if not isinstance(atom, dict):
        raise SchemaInvalid(f"atom must be an object, got {type(atom).__name__}")

    atom_id = atom.get("atom_id")
    allowed_files = atom.get("allowed_files", [])
    acceptance_commands = atom.get("acceptance_commands", [])

    # The relevant abstract rules ONLY (shield filter). Each is strictly {failure_class, rule}.
    injected_rules = failure_memory.relevant_rules(atom)

    # The context binds the live two refs (read-only); the capsule is proposed against this tip.
    context = {
        "tape_tip": tape.tape_tip() or "",
        "accepted_head": tape.accepted_head() or "",
    }

    budget = {
        "wall_seconds": _DEFAULT_WALL_SECONDS,
        "max_retries": _DEFAULT_MAX_RETRIES,
    }

    # Assemble the capsule body WITHOUT capsule_id first (the id is a hash of this body), then add
    # the content-addressed id. Optional descriptive fields are included only when the atom supplies
    # them (keeps the capsule minimal and schema-clean).
    body = {
        "schema_id": "turingos.capsule.v1",
        "atom_id": atom_id,
        "allowed_files": list(allowed_files) if isinstance(allowed_files, list) else allowed_files,
        "forbidden_files": list(atom.get("forbidden_files", [])) if isinstance(atom.get("forbidden_files", []), list) else [],
        "budget": budget,
        "injected_rules": injected_rules,
        "acceptance_commands": list(acceptance_commands) if isinstance(acceptance_commands, list) else acceptance_commands,
        "context": context,
    }
    # Carry the load-bearing-but-optional scope descriptors when present (module/goal/intent).
    if isinstance(atom.get("module_id"), str):
        body["module_id"] = atom["module_id"]
    if isinstance(atom.get("intent"), str):
        body["intent"] = atom["intent"]
    # goal_ref binds the accepted_head the capsule was built against (audit/scope, not gate logic).
    if context["accepted_head"]:
        body["goal_ref"] = context["accepted_head"]

    capsule = dict(body)
    capsule["capsule_id"] = _capsule_id(body)

    # Structural gate FIRST (raises SchemaInvalid; no commit on failure). This also re-checks the
    # codec guard and additionalProperties=false — defense in depth that no raw key smuggled through.
    schemas.validate_capsule(capsule)

    # Emit the PROPOSAL on the Tape (registry-derived head_effect=PRESERVE: tape_tip advances only).
    tape.append(_CAPSULE_EVENT, capsule)

    return capsule
