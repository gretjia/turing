import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "evidence" / "theory" / "turing_completeness_witness_20260703"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_instruction_registry_freezes_decjz_and_two_counter_state():
    registry = _load(ROOT / "programs" / "instruction_schema_registry.v1.json")

    assert registry["schema_id"] == "turingos.tc_witness.instruction_registry.v1"
    assert registry["machine_class"] == "minsky_counter_machine"
    assert registry["counters"] == ["counter_a", "counter_b"]
    assert "WITHOUT decrement" in registry["decjz_semantics"]
    assert {row["op"] for row in registry["instructions"]} == {"INC", "DECJZ", "HALT"}
    assert registry["state_schema"]["required"] == [
        "program_counter",
        "counter_a",
        "counter_b",
        "halted",
    ]


def test_payload_schemas_stay_inside_auditor_codec_subset():
    schema_dir = ROOT / "programs" / "payload_schemas"
    expected = {
        "computation_started.v1.json",
        "instruction_authorized.v1.json",
        "instruction_applied.v1.json",
        "machine_state_observed.v1.json",
        "computation_halted.v1.json",
    }
    seen = {path.name for path in schema_dir.glob("*.json")}

    assert seen == expected
    for path in schema_dir.glob("*.json"):
        payload = _load(path)
        encoded = json.dumps(payload, sort_keys=True)
        assert '"number"' not in encoded
        assert ".0" not in encoded
        assert payload["additionalProperties"] is False


def test_additive_registry_rows_are_m0_chain_proposal_not_silent_registry_edit():
    proposal = _load(ROOT / "registry" / "additive_event_registry_rows_tc_witness_v1.json")
    rows = proposal["proposed_rows"]

    assert proposal["proposal_status"] == "PROPOSED_M0_CHAIN"
    assert [row["canonical_name"] for row in rows] == [
        "ComputationStarted",
        "InstructionAuthorized",
        "InstructionApplied",
        "MachineStateObserved",
        "ComputationHalted",
    ]
    auth = next(row for row in rows if row["canonical_name"] == "InstructionAuthorized")
    assert auth["event_class"] == "AUTHORIZATION"
    assert auth["head_effect"] == "ADVANCE"
    assert auth["target_ref"] == "authorization_head"
    assert all(row["status"] == "ADDITIVE_TC_WITNESS_V1" for row in rows)
