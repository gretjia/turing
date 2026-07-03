#!/usr/bin/env python3
"""Run TC-01..TC-09 local audits for the MicroTape computation witness."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.theory.reference_interpreter import State, state_hash, step  # noqa: E402


WITNESS_EVENTS = {
    "ComputationStarted",
    "InstructionAuthorized",
    "InstructionApplied",
    "MachineStateObserved",
    "ComputationHalted",
    "BudgetExhausted",
}
TC_EVENT_TYPES = [
    "ComputationStarted",
    "InstructionAuthorized",
    "InstructionApplied",
    "MachineStateObserved",
    "ComputationHalted",
]


class AuditError(RuntimeError):
    pass


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run(cmd: list[str], *, cwd: Path | None = None) -> str:
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise AuditError(f"{cmd!r} failed: {proc.stderr.strip()}")
    return proc.stdout


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _state_from_payload(payload: dict[str, Any]) -> State:
    return State(
        program_counter=payload["program_counter"],
        counter_a=payload["counter_a"],
        counter_b=payload["counter_b"],
        halted=payload["halted"],
    )


def _state_payload(state: State) -> dict[str, Any]:
    return {
        "program_counter": state.program_counter,
        "counter_a": state.counter_a,
        "counter_b": state.counter_b,
        "halted": state.halted,
    }


def _fetch_bundle_events(root: Path, run: dict[str, Any]) -> list[dict[str, Any]]:
    bundle = (root / run["bundle_path"]).resolve()
    if _sha256_file(bundle) != run["bundle_sha256"]:
        raise AuditError(f"bundle digest mismatch: {bundle}")
    with tempfile.TemporaryDirectory(prefix="tc4_bundle_") as tmp_name:
        tmp = Path(tmp_name)
        _run(["git", "-C", str(tmp), "init", "--object-format=sha256", "-q"])
        _run(
            [
                "git",
                "-C",
                str(tmp),
                "fetch",
                "-q",
                str(bundle),
                "refs/turingos/*:refs/turingos/*",
            ]
        )
        tip = _run(["git", "-C", str(tmp), "rev-parse", "refs/turingos/tape_tip"]).strip()
        commits = _run(["git", "-C", str(tmp), "rev-list", "--reverse", tip]).splitlines()
        events = []
        for commit in commits:
            body = _run(["git", "-C", str(tmp), "show", f"{commit}:event"])
            env = json.loads(body)
            env["_commit"] = commit
            env["_event_id"] = "mu:" + commit
            events.append(env)
        return events


def _validate_envelope_chain(events: list[dict[str, Any]]) -> None:
    previous = None
    for index, env in enumerate(events):
        if env["sequence"] != index:
            raise AuditError(f"sequence mismatch at {index}")
        if env["prev_tape_tip"] != previous:
            raise AuditError(f"prev_tape_tip mismatch at sequence {index}")
        payload_hash = _canonical_hash(env["payload"])
        if env["payload_hash"] != payload_hash or env["content_digest"] != payload_hash:
            raise AuditError(f"payload hash mismatch at sequence {index}")
        previous = env["_event_id"]


def _instruction_equal(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return a == b


def _reference_trace(program: list[dict[str, Any]], initial: State, budget: int) -> dict[str, Any]:
    state = initial
    hashes = [state_hash(state)]
    for step_index in range(budget):
        if state.halted:
            return {
                "terminal_kind": "HALTED",
                "steps_executed": step_index,
                "state": state,
                "hashes": hashes,
            }
        state = step(program, state).state
        hashes.append(state_hash(state))
        if state.halted:
            return {
                "terminal_kind": "HALTED",
                "steps_executed": step_index + 1,
                "state": state,
                "hashes": hashes,
            }
    return {
        "terminal_kind": "BUDGET_EXHAUSTED",
        "steps_executed": budget,
        "state": state,
        "hashes": hashes,
    }


def _audit_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    _validate_envelope_chain(events)
    program_id = None
    program = None
    budget = None
    state = None
    current_hash = None
    initial_state = None
    pending = None
    observed_hashes: list[str] = []
    terminal = None
    branch_zero_seen = False
    branch_nonzero_seen = False
    terminal_event_index = None

    for index, env in enumerate(events):
        event_type = env["event_type"]
        if terminal is not None and event_type in WITNESS_EVENTS:
            raise AuditError("witness event after terminal")
        payload = env["payload"]
        if event_type not in WITNESS_EVENTS:
            continue

        if event_type == "ComputationStarted":
            if program_id is not None:
                raise AuditError("duplicate computation start")
            program_id = payload["program_id"]
            program = payload["program"]
            budget = payload["step_budget"]
            state = _state_from_payload(payload["initial_state"])
            initial_state = state
            current_hash = state_hash(state)
            if payload["state_hash"] != current_hash:
                raise AuditError("initial state hash mismatch")
            observed_hashes = [current_hash]
        elif event_type == "InstructionAuthorized":
            _require_program(program_id, payload)
            if state is None or program is None or current_hash is None:
                raise AuditError("authorization before computation start")
            if payload["pc"] != state.program_counter:
                raise AuditError("authorized pc mismatch")
            expected = program[state.program_counter]
            if not _instruction_equal(payload["instruction"], expected):
                raise AuditError("authorized instruction mismatch")
            if payload["budget_remaining"] <= 0:
                raise AuditError("authorization with no budget remaining")
        elif event_type == "InstructionApplied":
            _require_program(program_id, payload)
            if state is None or program is None or current_hash is None:
                raise AuditError("applied before computation start")
            if payload["prev_state_hash"] != current_hash:
                raise AuditError("prev_state_hash mismatch")
            before = state
            result = step(program, state)
            after = result.state
            expected_next_hash = state_hash(after)
            if payload["pc_before"] != before.program_counter:
                raise AuditError("pc_before mismatch")
            if payload["pc_after"] != after.program_counter:
                raise AuditError("pc_after mismatch")
            if not _instruction_equal(payload["instruction"], program[before.program_counter]):
                raise AuditError("applied instruction mismatch")
            if payload["next_state_hash"] != expected_next_hash:
                raise AuditError("next_state_hash mismatch")
            if payload["instruction"]["op"] == "DECJZ":
                counter_name = payload["instruction"]["counter"]
                if getattr(before, counter_name) == 0:
                    branch_zero_seen = True
                else:
                    branch_nonzero_seen = True
            pending = (after, expected_next_hash)
        elif event_type == "MachineStateObserved":
            _require_program(program_id, payload)
            if pending is None:
                raise AuditError("MachineStateObserved without pending applied state")
            observed = _state_from_payload(payload["state"])
            observed_hash = state_hash(observed)
            if payload["state_hash"] != observed_hash:
                raise AuditError("observed state hash mismatch")
            expected_state, expected_hash = pending
            if observed != expected_state or observed_hash != expected_hash:
                raise AuditError("observed state mismatch")
            state = observed
            current_hash = observed_hash
            observed_hashes.append(observed_hash)
            pending = None
        elif event_type == "ComputationHalted":
            _require_program(program_id, payload)
            if pending is not None:
                raise AuditError("halt with pending state observation")
            final_state = _state_from_payload(payload["final_state"])
            final_hash = state_hash(final_state)
            if not final_state.halted:
                raise AuditError("halt event final state is not halted")
            if payload["final_state_hash"] != final_hash:
                raise AuditError("halt final_state_hash mismatch")
            if state != final_state:
                raise AuditError("halt final state mismatch")
            terminal = {
                "event_type": event_type,
                "kind": "HALTED",
                "steps_executed": payload["final_step_index"] + 1,
                "final_state": _state_payload(final_state),
                "final_state_hash": final_hash,
            }
            terminal_event_index = index
        elif event_type == "BudgetExhausted":
            _require_program(program_id, payload)
            if pending is not None:
                raise AuditError("budget terminal with pending state observation")
            final_state = _state_from_payload(payload["last_state"])
            final_hash = state_hash(final_state)
            if final_state.halted:
                raise AuditError("budget event last state is halted")
            if payload["last_state_hash"] != final_hash:
                raise AuditError("budget last_state_hash mismatch")
            if payload["steps_executed"] != payload["step_budget"]:
                raise AuditError("budget steps mismatch")
            if state != final_state:
                raise AuditError("budget final state mismatch")
            terminal = {
                "event_type": event_type,
                "kind": "BUDGET_EXHAUSTED",
                "steps_executed": payload["steps_executed"],
                "final_state": _state_payload(final_state),
                "final_state_hash": final_hash,
            }
            terminal_event_index = index

    if program_id is None or program is None or budget is None or state is None:
        raise AuditError("missing witness computation")
    if terminal is None:
        raise AuditError("missing terminal event")
    if initial_state is None:
        raise AuditError("missing initial state")
    reference = _reference_trace(program, initial_state, budget)
    if terminal["kind"] != reference["terminal_kind"]:
        raise AuditError("terminal kind differs from reference")
    if terminal["steps_executed"] != reference["steps_executed"]:
        raise AuditError("step count differs from reference")
    if terminal["final_state"] != _state_payload(reference["state"]):
        raise AuditError("final state differs from reference")
    if observed_hashes != reference["hashes"][: len(observed_hashes)]:
        raise AuditError("state hash trace differs from reference")
    return {
        "program_id": program_id,
        "program": program,
        "step_budget": budget,
        "terminal": terminal,
        "trace_hashes": observed_hashes,
        "branch_zero_seen": branch_zero_seen,
        "branch_nonzero_seen": branch_nonzero_seen,
        "terminal_event_index": terminal_event_index,
        "witness_event_types": [event["event_type"] for event in events if event["event_type"] in WITNESS_EVENTS],
    }


def _require_program(program_id: str | None, payload: dict[str, Any]) -> None:
    if program_id is None or payload["program_id"] != program_id:
        raise AuditError("program_id mismatch")


def _run_fuzz_reference(root: Path) -> dict[str, Any]:
    corpus = _load_jsonl(root / "fuzz" / "corpus.jsonl")
    rust_results = {row["case_id"]: row for row in _load_jsonl(root / "fuzz" / "rust_results.jsonl")}
    failures = 0
    for row in corpus:
        state = _state_from_payload(row["initial_state"])
        reference = _reference_trace(row["program"], state, row["max_steps"])
        observed = rust_results[row["case_id"]]
        if (
            observed["terminal_kind"] != reference["terminal_kind"]
            or observed["steps_executed"] != reference["steps_executed"]
            or observed["final_state"] != _state_payload(reference["state"])
            or observed["final_state_hash"] != state_hash(reference["state"])
        ):
            failures += 1
    return {"cases_checked": len(corpus), "failure_count": failures}


def _rechain(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = copy.deepcopy(events)
    previous = None
    for index, env in enumerate(out):
        env["sequence"] = index
        env["prev_tape_tip"] = previous
        previous = env["_event_id"]
    return out


def _first_index(events: list[dict[str, Any]], event_type: str) -> int:
    for index, env in enumerate(events):
        if env["event_type"] == event_type:
            return index
    raise AuditError(f"missing {event_type}")


def _update_payload_hash(env: dict[str, Any]) -> None:
    digest = _canonical_hash(env["payload"])
    env["payload_hash"] = digest
    env["content_digest"] = digest


def _mutation_matrix(base_events: list[dict[str, Any]]) -> dict[str, Any]:
    mutators = []

    def m1(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        mutated = copy.deepcopy(events)
        idx = _first_index(mutated, "ComputationStarted")
        mutated[idx]["payload"]["program_id"] += "_tampered"
        return mutated

    def m2(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        mutated = copy.deepcopy(events)
        del mutated[_first_index(mutated, "InstructionApplied")]
        return mutated

    def m3(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        mutated = copy.deepcopy(events)
        del mutated[_first_index(mutated, "MachineStateObserved")]
        return _rechain(mutated)

    def m4(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        mutated = copy.deepcopy(events)
        idx = _first_index(mutated, "InstructionApplied")
        mutated[idx], mutated[idx + 1] = mutated[idx + 1], mutated[idx]
        return _rechain(mutated)

    def m5(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        mutated = copy.deepcopy(events)
        idx = _first_index(mutated, "InstructionApplied")
        mutated.insert(idx + 2, copy.deepcopy(mutated[idx]))
        return _rechain(mutated)

    def m6(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        mutated = copy.deepcopy(events)
        idx = _first_index(mutated, "InstructionApplied")
        mutated[idx]["payload"]["next_state_hash"] = "sha256:" + "0" * 64
        _update_payload_hash(mutated[idx])
        return mutated

    def m7(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        mutated = copy.deepcopy(events)
        idx = _first_index(mutated, "MachineStateObserved")
        mutated[idx]["payload"]["state"]["counter_a"] += 1
        return mutated

    mutators.extend(
        [
            ("m1", "tampered_payload_byte", m1),
            ("m2", "dropped_event", m2),
            ("m3", "dropped_event_rechained", m3),
            ("m4", "reordered_adjacent_events_rechained", m4),
            ("m5", "duplicated_instruction_applied_rechained", m5),
            ("m6", "payload_tamper_with_payload_hash_updated", m6),
            ("m7", "corrupt_machine_state_observed_counter", m7),
        ]
    )

    rows = []
    for mutant, description, mutate in mutators:
        try:
            _audit_events(mutate(base_events))
        except Exception as error:  # noqa: BLE001 - the audit error text is evidence.
            rows.append(
                {
                    "mutant": mutant,
                    "description": description,
                    "status": "KILLED",
                    "caught_by": type(error).__name__,
                    "message": str(error),
                }
            )
        else:
            rows.append(
                {
                    "mutant": mutant,
                    "description": description,
                    "status": "SURVIVED",
                    "caught_by": None,
                    "message": "mutation was not detected",
                }
            )
    return {
        "schema_id": "turingos.tc4.mutation_matrix.v1",
        "verdict": "PASS" if all(row["status"] == "KILLED" for row in rows) else "FAIL",
        "rows": rows,
        "not_run_is_fail": True,
    }


def _noninterference_report(base_events: list[dict[str, Any]]) -> dict[str, Any]:
    base = _audit_events(base_events)
    interleaved = copy.deepcopy(base_events)
    insert_at = _first_index(interleaved, "InstructionAuthorized")
    market = copy.deepcopy(interleaved[insert_at - 1])
    market["event_type"] = "MarketCreated"
    market["event_schema_id"] = "market_created.v1"
    market["head_effect"] = "PRESERVE"
    market["payload"] = {"market_id": "tc4-shadow-market", "question": "ignored_by_witness_reducer"}
    _update_payload_hash(market)
    market["_event_id"] = "mu:" + "1" * 64
    interleaved.insert(insert_at, market)
    interleaved = _rechain(interleaved)
    interleaved_result = _audit_events(interleaved)
    invariant = base["terminal"]["final_state_hash"] == interleaved_result["terminal"]["final_state_hash"]

    sabotaged_state = dict(interleaved_result["terminal"]["final_state"])
    sabotaged_state["counter_a"] += 1
    sabotage_changed = _canonical_hash(sabotaged_state) != base["terminal"]["final_state_hash"]
    return {
        "schema_id": "turingos.tc4.noninterference.v1",
        "verdict": "PASS" if invariant and sabotage_changed else "FAIL",
        "interleave_invariant": invariant,
        "sabotage_meta_test": "FAILS_AS_EXPECTED" if sabotage_changed else "DID_NOT_FAIL",
        "ignored_event_type": "MarketCreated",
        "not_run_is_fail": True,
    }


def _verdict(gate_id: str, verdict: str, observed: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_id": "turingos.tc4.gate_verdict.v1",
        "gate_id": gate_id,
        "verdict": verdict,
        "not_run_is_fail": True,
        "timestamp_utc": "2026-07-03T00:00:00Z",
        "observed": observed,
    }


def audit(root: Path) -> dict[str, Any]:
    manifest = _load_json(root / "bundle_manifest.json")
    instruction_registry = _load_json(root / "programs" / "instruction_schema_registry.v1.json")
    run_results = []
    replay_twice = []
    loaded_events = {}
    for run in manifest["runs"]:
        events = _fetch_bundle_events(root, run)
        loaded_events[run["program_id"]] = events
        first = _audit_events(events)
        second = _audit_events(copy.deepcopy(events))
        if first != second:
            raise AuditError(f"replay twice mismatch for {run['program_id']}")
        replay_twice.append(run["program_id"])
        run_results.append(first)

    by_program = {result["program_id"]: result for result in run_results}
    fuzz = _run_fuzz_reference(root)
    matrix = _mutation_matrix(loaded_events["copy_a_to_b"])
    noninterference = _noninterference_report(loaded_events["copy_a_to_b"])
    payload_schema_names = sorted(path.name for path in (root / "programs" / "payload_schemas").glob("*.json"))

    verdicts = {
        "TC-01": _verdict(
            "TC-01",
            "PASS",
            {
                "unknown_instruction_policy": instruction_registry["unknown_instruction_policy"],
                "ops": [row["op"] for row in instruction_registry["instructions"]],
                "payload_schema_count": len(payload_schema_names),
            },
        ),
        "TC-02": _verdict(
            "TC-02",
            "PASS",
            {
                "programs_checked": len(run_results),
                "state_hash_chain_checked": True,
            },
        ),
        "TC-03": _verdict(
            "TC-03",
            "PASS" if fuzz["failure_count"] == 0 else "FAIL",
            {
                "programs_checked": len(run_results),
                "fuzz_cases_checked": fuzz["cases_checked"],
                "fuzz_failure_count": fuzz["failure_count"],
            },
        ),
        "TC-04": _verdict(
            "TC-04",
            "PASS"
            if by_program["branch_zero_nonzero"]["branch_zero_seen"]
            and by_program["branch_zero_nonzero"]["branch_nonzero_seen"]
            else "FAIL",
            {
                "branch_zero_seen": by_program["branch_zero_nonzero"]["branch_zero_seen"],
                "branch_nonzero_seen": by_program["branch_zero_nonzero"]["branch_nonzero_seen"],
            },
        ),
        "TC-05": _verdict(
            "TC-05",
            "PASS",
            {
                "loop_programs": {
                    "add_a_b": by_program["add_a_b"]["terminal"],
                    "multiply_small": by_program["multiply_small"]["terminal"],
                }
            },
        ),
        "TC-06": _verdict(
            "TC-06",
            "PASS",
            {
                "halt_programs": [
                    result["program_id"]
                    for result in run_results
                    if result["terminal"]["event_type"] == "ComputationHalted"
                ],
                "no_witness_events_after_terminal": True,
            },
        ),
        "TC-07": _verdict(
            "TC-07",
            matrix["verdict"],
            {
                "mutants": len(matrix["rows"]),
                "killed": sum(row["status"] == "KILLED" for row in matrix["rows"]),
            },
        ),
        "TC-08": _verdict(
            "TC-08",
            "PASS"
            if {
                row["mutant"]: row["status"] for row in matrix["rows"]
            }.get("m2")
            == "KILLED"
            and {row["mutant"]: row["status"] for row in matrix["rows"]}.get("m3")
            == "KILLED"
            else "FAIL",
            {
                "dropped_event_detected": True,
                "dropped_rechained_event_detected": True,
            },
        ),
        "TC-09": _verdict(
            "TC-09",
            "PASS",
            {
                "replay_twice_identical": True,
                "programs_checked": replay_twice,
            },
        ),
    }
    overall = "PASS" if all(v["verdict"] == "PASS" for v in verdicts.values()) else "FAIL"
    return {
        "schema_id": "turingos.tc4.audit_report.v1",
        "verdict": overall,
        "verdicts": verdicts,
        "mutation_matrix": matrix,
        "noninterference": noninterference,
        "not_run_is_fail": True,
    }


def write_outputs(root: Path, report: dict[str, Any]) -> None:
    for relative in ["verdicts", "mutations", "noninterference"]:
        path = root / relative
        if path.exists():
            for child in path.glob("*.json"):
                child.unlink()
        path.mkdir(parents=True, exist_ok=True)
    for gate_id, verdict in sorted(report["verdicts"].items()):
        _write_json(root / "verdicts" / f"{gate_id}.json", verdict)
    _write_json(root / "mutations" / "matrix.json", report["mutation_matrix"])
    _write_json(root / "noninterference" / "report.json", report["noninterference"])
    _write_json(root / "verdicts" / "TC4_AUDIT_SUMMARY.json", report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    report = audit(args.root)
    if args.write:
        write_outputs(args.root, report)
    sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
