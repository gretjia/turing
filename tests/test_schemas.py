"""Contract tests for turingos.schemas (stdlib unittest; pytest is NOT installed).

Predicate-first: these tests freeze the schemas.py contract per
contracts/INTERFACES.md + contracts/capsule.schema.json + contracts/receipt.schema.json
BEFORE the implementation is written.

schemas.py depends on the FROZEN codec + registry seams (codec.assert_ascii_keys,
codec.assert_no_floats, registry.is_known). Those are sibling modules built in parallel
and may not exist on disk yet, so we install deterministic stand-ins into sys.modules
that implement exactly the frozen API surface schemas.py is allowed to call. This keeps
the schemas module self-testable in isolation while still exercising the real codec/registry
seam (the stubs raise the real errors from turingos.errors).
"""
from __future__ import annotations

import sys
import types
import unittest

# --- install frozen-seam stand-ins for codec + registry BEFORE importing schemas ---
# turingos.errors is real and present; reuse its exception classes so the stubs raise
# exactly what the real codec/registry raise.
from turingos import errors as _errors  # noqa: E402

_KNOWN_EVENTS = frozenset(
    {
        "SystemBootstrapped",
        "ProjectAdopted",
        "GoalStateAccepted",
        "ModulePlanAccepted",
        "AtomProposed",
        "WorkCapsuleBuilt",
        "WorkerDispatched",
        "HumanSteerInjected",
        "WorkerReceiptImported",
        "MacroObservationImported",
        "PredicateEvaluated",
        "CandidateAccepted",
        "CandidateRejected",
        "FailureNode",
        "ExplorationArchived",
        "ExplorationPromoted",
        "ReplayVerified",
        "HandoffGenerated",
    }
)


def _stub_assert_ascii_keys(payload):
    def _walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if not (isinstance(k, str) and k.isascii()):
                    raise _errors.AsciiKeyViolation(f"non-ascii key: {k!r}")
                _walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                _walk(v)

    _walk(payload)


def _stub_assert_no_floats(payload):
    def _walk(o):
        if isinstance(o, bool):
            return
        if isinstance(o, float):
            raise _errors.FloatViolation("float value forbidden")
        if isinstance(o, dict):
            for v in o.values():
                _walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                _walk(v)

    _walk(payload)


def _install_seam_stubs():
    codec = sys.modules.get("turingos.codec")
    if codec is None:
        codec = types.ModuleType("turingos.codec")
        sys.modules["turingos.codec"] = codec
    # Always (re)bind the two methods schemas.py is allowed to call so the test
    # is hermetic even if a partial real codec is present.
    codec.assert_ascii_keys = _stub_assert_ascii_keys
    codec.assert_no_floats = _stub_assert_no_floats

    registry = sys.modules.get("turingos.registry")
    if registry is None:
        registry = types.ModuleType("turingos.registry")
        sys.modules["turingos.registry"] = registry
    registry.is_known = lambda et: et in _KNOWN_EVENTS


_install_seam_stubs()

from turingos import schemas  # noqa: E402
from turingos.errors import SchemaInvalid  # noqa: E402


def valid_capsule() -> dict:
    return {
        "schema_id": "turingos.capsule.v1",
        "capsule_id": "cap:0123abcd",
        "atom_id": "M0.A1",
        "module_id": "M0",
        "goal_ref": "deadbeef",
        "intent": "implement schemas",
        "allowed_files": ["src/turingos/schemas.py", "tests/test_schemas.py"],
        "forbidden_files": [],
        "budget": {"wall_seconds": 60, "max_retries": 1},
        "injected_rules": [
            {"failure_class": "test_fail", "rule": "declared tests must include boundary X"}
        ],
        "acceptance_commands": ["python3 -m unittest tests.test_schemas"],
        "context": {"tape_tip": "aa11", "accepted_head": "bb22"},
    }


def valid_receipt() -> dict:
    return {
        "schema_id": "turingos.receipt.v1",
        "receipt_id": "rcpt:0123abcd",
        "capsule_id": "cap:0123abcd",
        "worker_id": "fake",
        "worktree_path": "/tmp/wt",
        "candidate": {
            "tree_oid": "ff00ff00",
            "files_touched": ["src/turingos/schemas.py"],
            "macro_commit": "abc123",
        },
        "declared_test_results": [{"command": "python3 -m unittest", "exit_code": 0}],
        "evidence_digests": ["sha256:abc"],
        "status": "ok",
        "no_orphan": True,
    }


class TestValidCapsule(unittest.TestCase):
    def test_valid_capsule_passes(self):
        # returns None, raises nothing
        self.assertIsNone(schemas.validate_capsule(valid_capsule()))

    def test_minimal_capsule_passes(self):
        cap = {
            "schema_id": "turingos.capsule.v1",
            "capsule_id": "cap:0123abcd",
            "atom_id": "M0.A1",
            "allowed_files": [],
            "budget": {"wall_seconds": 1, "max_retries": 0},
            "acceptance_commands": ["true"],
            "context": {"tape_tip": "aa", "accepted_head": "bb"},
        }
        self.assertIsNone(schemas.validate_capsule(cap))


class TestCapsuleRejections(unittest.TestCase):
    def test_not_a_dict(self):
        with self.assertRaises(SchemaInvalid):
            schemas.validate_capsule(["not", "a", "dict"])

    def test_missing_required_field(self):
        cap = valid_capsule()
        del cap["atom_id"]
        with self.assertRaises(SchemaInvalid):
            schemas.validate_capsule(cap)

    def test_unknown_extra_key_rejected(self):
        cap = valid_capsule()
        cap["surprise"] = 1
        with self.assertRaises(SchemaInvalid):
            schemas.validate_capsule(cap)

    def test_bad_schema_id_const(self):
        cap = valid_capsule()
        cap["schema_id"] = "turingos.capsule.v2"
        with self.assertRaises(SchemaInvalid):
            schemas.validate_capsule(cap)

    def test_bad_capsule_id_pattern(self):
        cap = valid_capsule()
        cap["capsule_id"] = "capsule:xyz"
        with self.assertRaises(SchemaInvalid):
            schemas.validate_capsule(cap)

    def test_capsule_id_too_short(self):
        cap = valid_capsule()
        cap["capsule_id"] = "cap:abc"  # 3 hex < 8
        with self.assertRaises(SchemaInvalid):
            schemas.validate_capsule(cap)

    def test_capsule_id_non_hex(self):
        cap = valid_capsule()
        cap["capsule_id"] = "cap:zzzzzzzz"
        with self.assertRaises(SchemaInvalid):
            schemas.validate_capsule(cap)

    def test_empty_acceptance_commands_rejected(self):
        cap = valid_capsule()
        cap["acceptance_commands"] = []
        with self.assertRaises(SchemaInvalid):
            schemas.validate_capsule(cap)

    def test_acceptance_commands_not_array(self):
        cap = valid_capsule()
        cap["acceptance_commands"] = "python3 -m unittest"
        with self.assertRaises(SchemaInvalid):
            schemas.validate_capsule(cap)

    def test_acceptance_command_item_not_string(self):
        cap = valid_capsule()
        cap["acceptance_commands"] = [123]
        with self.assertRaises(SchemaInvalid):
            schemas.validate_capsule(cap)

    def test_atom_id_empty_string(self):
        cap = valid_capsule()
        cap["atom_id"] = ""  # minLength 1
        with self.assertRaises(SchemaInvalid):
            schemas.validate_capsule(cap)

    def test_allowed_files_not_array(self):
        cap = valid_capsule()
        cap["allowed_files"] = "src/x.py"
        with self.assertRaises(SchemaInvalid):
            schemas.validate_capsule(cap)

    def test_allowed_files_item_not_string(self):
        cap = valid_capsule()
        cap["allowed_files"] = [1, 2]
        with self.assertRaises(SchemaInvalid):
            schemas.validate_capsule(cap)

    def test_budget_not_object(self):
        cap = valid_capsule()
        cap["budget"] = 60
        with self.assertRaises(SchemaInvalid):
            schemas.validate_capsule(cap)

    def test_budget_missing_required(self):
        cap = valid_capsule()
        del cap["budget"]["max_retries"]
        with self.assertRaises(SchemaInvalid):
            schemas.validate_capsule(cap)

    def test_budget_unknown_key(self):
        cap = valid_capsule()
        cap["budget"]["extra"] = 1
        with self.assertRaises(SchemaInvalid):
            schemas.validate_capsule(cap)

    def test_budget_wall_seconds_below_min(self):
        cap = valid_capsule()
        cap["budget"]["wall_seconds"] = 0  # minimum 1
        with self.assertRaises(SchemaInvalid):
            schemas.validate_capsule(cap)

    def test_budget_wall_seconds_not_int(self):
        cap = valid_capsule()
        cap["budget"]["wall_seconds"] = 60.0  # float forbidden / not integer
        with self.assertRaises(SchemaInvalid):
            schemas.validate_capsule(cap)

    def test_budget_max_retries_negative(self):
        cap = valid_capsule()
        cap["budget"]["max_retries"] = -1  # minimum 0
        with self.assertRaises(SchemaInvalid):
            schemas.validate_capsule(cap)

    def test_budget_bool_not_accepted_as_int(self):
        cap = valid_capsule()
        cap["budget"]["wall_seconds"] = True  # bool must not count as integer
        with self.assertRaises(SchemaInvalid):
            schemas.validate_capsule(cap)

    def test_context_missing_required(self):
        cap = valid_capsule()
        del cap["context"]["tape_tip"]
        with self.assertRaises(SchemaInvalid):
            schemas.validate_capsule(cap)

    def test_context_unknown_key(self):
        cap = valid_capsule()
        cap["context"]["weird"] = "x"
        with self.assertRaises(SchemaInvalid):
            schemas.validate_capsule(cap)

    def test_injected_rule_missing_field(self):
        cap = valid_capsule()
        cap["injected_rules"] = [{"failure_class": "x"}]  # missing rule
        with self.assertRaises(SchemaInvalid):
            schemas.validate_capsule(cap)

    def test_injected_rule_unknown_key(self):
        cap = valid_capsule()
        cap["injected_rules"] = [
            {"failure_class": "x", "rule": "y", "raw_stdout": "leak"}
        ]
        with self.assertRaises(SchemaInvalid):
            schemas.validate_capsule(cap)

    def test_non_ascii_key_rejected(self):
        cap = valid_capsule()
        cap["context"]["tape_tip"] = {"ékey": "v"}
        # tape_tip must be a string anyway, but the ascii guard should also fire.
        with self.assertRaises(SchemaInvalid):
            schemas.validate_capsule(cap)

    def test_float_value_rejected(self):
        cap = valid_capsule()
        # inject a float somewhere the structural check would not otherwise catch
        cap["goal_ref"] = "ok"
        cap["injected_rules"] = [{"failure_class": "c", "rule": "r"}]
        # put a float into a free-form string-typed field via budget already covered;
        # use a nested float through allowed_files would be type error, so use module_id float:
        cap["module_id"] = 1.5
        with self.assertRaises(SchemaInvalid):
            schemas.validate_capsule(cap)


class TestValidReceipt(unittest.TestCase):
    def test_valid_receipt_passes(self):
        self.assertIsNone(schemas.validate_receipt(valid_receipt()))

    def test_minimal_receipt_passes(self):
        r = {
            "schema_id": "turingos.receipt.v1",
            "receipt_id": "rcpt:0123abcd",
            "capsule_id": "cap:0123abcd",
            "worker_id": "fake",
            "worktree_path": "/tmp/wt",
            "candidate": {"tree_oid": "ff00", "files_touched": []},
            "status": "failed",
        }
        self.assertIsNone(schemas.validate_receipt(r))


class TestReceiptRejections(unittest.TestCase):
    def test_not_a_dict(self):
        with self.assertRaises(SchemaInvalid):
            schemas.validate_receipt("nope")

    def test_missing_required_field(self):
        r = valid_receipt()
        del r["worker_id"]
        with self.assertRaises(SchemaInvalid):
            schemas.validate_receipt(r)

    def test_unknown_extra_key_rejected(self):
        r = valid_receipt()
        r["leak"] = "x"
        with self.assertRaises(SchemaInvalid):
            schemas.validate_receipt(r)

    def test_bad_schema_id_const(self):
        r = valid_receipt()
        r["schema_id"] = "turingos.receipt.v2"
        with self.assertRaises(SchemaInvalid):
            schemas.validate_receipt(r)

    def test_bad_receipt_id_pattern(self):
        r = valid_receipt()
        r["receipt_id"] = "receipt:abcd1234"
        with self.assertRaises(SchemaInvalid):
            schemas.validate_receipt(r)

    def test_bad_capsule_id_pattern(self):
        r = valid_receipt()
        r["capsule_id"] = "cap:zz"
        with self.assertRaises(SchemaInvalid):
            schemas.validate_receipt(r)

    def test_bad_status_enum(self):
        r = valid_receipt()
        r["status"] = "succeeded"
        with self.assertRaises(SchemaInvalid):
            schemas.validate_receipt(r)

    def test_all_valid_statuses(self):
        for st in ("ok", "failed", "timeout", "killed"):
            r = valid_receipt()
            r["status"] = st
            self.assertIsNone(schemas.validate_receipt(r))

    def test_candidate_not_object(self):
        r = valid_receipt()
        r["candidate"] = "ff00"
        with self.assertRaises(SchemaInvalid):
            schemas.validate_receipt(r)

    def test_candidate_missing_tree_oid(self):
        r = valid_receipt()
        del r["candidate"]["tree_oid"]
        with self.assertRaises(SchemaInvalid):
            schemas.validate_receipt(r)

    def test_candidate_missing_files_touched(self):
        r = valid_receipt()
        del r["candidate"]["files_touched"]
        with self.assertRaises(SchemaInvalid):
            schemas.validate_receipt(r)

    def test_candidate_unknown_key(self):
        r = valid_receipt()
        r["candidate"]["sneaky"] = 1
        with self.assertRaises(SchemaInvalid):
            schemas.validate_receipt(r)

    def test_files_touched_item_not_string(self):
        r = valid_receipt()
        r["candidate"]["files_touched"] = [1]
        with self.assertRaises(SchemaInvalid):
            schemas.validate_receipt(r)

    def test_declared_test_result_missing_field(self):
        r = valid_receipt()
        r["declared_test_results"] = [{"command": "x"}]  # missing exit_code
        with self.assertRaises(SchemaInvalid):
            schemas.validate_receipt(r)

    def test_declared_test_result_exit_code_not_int(self):
        r = valid_receipt()
        r["declared_test_results"] = [{"command": "x", "exit_code": "0"}]
        with self.assertRaises(SchemaInvalid):
            schemas.validate_receipt(r)

    def test_no_orphan_not_bool(self):
        r = valid_receipt()
        r["no_orphan"] = "true"
        with self.assertRaises(SchemaInvalid):
            schemas.validate_receipt(r)

    def test_float_value_rejected(self):
        r = valid_receipt()
        r["declared_test_results"] = [{"command": "x", "exit_code": 1}]
        r["candidate"]["macro_commit"] = "abc"
        # Inject a float into a string-typed field => structural type error AND float guard.
        r["worker_id"] = 3.14
        with self.assertRaises(SchemaInvalid):
            schemas.validate_receipt(r)


class TestEventPayload(unittest.TestCase):
    def test_known_event_dict_payload_passes(self):
        self.assertIsNone(
            schemas.validate_event_payload("FailureNode", {"failure_class": "test_fail", "n": 2})
        )

    def test_unknown_event_rejected(self):
        with self.assertRaises(SchemaInvalid):
            schemas.validate_event_payload("NotAnEvent", {"a": 1})

    def test_payload_not_dict_rejected(self):
        with self.assertRaises(SchemaInvalid):
            schemas.validate_event_payload("FailureNode", ["not", "a", "dict"])

    def test_non_ascii_key_rejected(self):
        with self.assertRaises(SchemaInvalid):
            schemas.validate_event_payload("FailureNode", {"clé": "v"})

    def test_float_in_payload_rejected(self):
        with self.assertRaises(SchemaInvalid):
            schemas.validate_event_payload("FailureNode", {"score": 0.5})

    def test_bool_payload_value_is_fine(self):
        # bool is not a float; should pass
        self.assertIsNone(
            schemas.validate_event_payload("ReplayVerified", {"equal": True})
        )


if __name__ == "__main__":
    unittest.main()
