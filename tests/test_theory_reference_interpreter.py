import ast
from pathlib import Path

import pytest

from tools.theory.reference_interpreter import State, run, state_hash, step


REPO = Path(__file__).resolve().parents[1]
INTERPRETER = REPO / "tools" / "theory" / "reference_interpreter.py"


def test_inc_advances_program_counter_and_counter():
    program = [{"op": "INC", "counter": "counter_a", "next_pc": 1}]

    assert step(program, State()).state == State(program_counter=1, counter_a=1)


def test_halt_sets_halted_without_advancing_state_again():
    program = [{"op": "HALT"}]

    result = step(program, State(program_counter=0, counter_a=2, counter_b=3))

    assert result.state == State(program_counter=0, counter_a=2, counter_b=3, halted=True)
    assert step(program, result.state).state == result.state


def test_decjz_zero_jumps_without_decrementing():
    program = [{"op": "DECJZ", "counter": "counter_a", "zero_pc": 7, "nonzero_pc": 1}]

    assert step(program, State(counter_a=0, counter_b=4)).state == State(
        program_counter=7,
        counter_a=0,
        counter_b=4,
    )


def test_decjz_nonzero_decrements_then_jumps():
    program = [{"op": "DECJZ", "counter": "counter_b", "zero_pc": 7, "nonzero_pc": 2}]

    assert step(program, State(counter_a=3, counter_b=5)).state == State(
        program_counter=2,
        counter_a=3,
        counter_b=4,
    )


def test_unknown_instruction_op_is_rejected_by_closed_schema():
    with pytest.raises(ValueError, match="unknown op"):
        step([{"op": "ADD", "counter": "counter_a"}], State())


def test_trace_hashes_are_deterministic():
    program = [
        {"op": "INC", "counter": "counter_a", "next_pc": 1},
        {"op": "DECJZ", "counter": "counter_a", "zero_pc": 3, "nonzero_pc": 2},
        {"op": "HALT"},
    ]

    first = run(program, max_steps=8)
    second = run(program, max_steps=8)

    assert first.trace == second.trace
    assert first.trace == [
        {
            "prev_state_hash": state_hash(State()),
            "next_state_hash": state_hash(State(program_counter=1, counter_a=1)),
        },
        {
            "prev_state_hash": state_hash(State(program_counter=1, counter_a=1)),
            "next_state_hash": state_hash(State(program_counter=2, counter_a=0)),
        },
        {
            "prev_state_hash": state_hash(State(program_counter=2, counter_a=0)),
            "next_state_hash": state_hash(State(program_counter=2, counter_a=0, halted=True)),
        },
    ]


def test_state_hash_uses_sha256_prefix():
    assert state_hash(State()).startswith("sha256:")


def test_reference_interpreter_has_no_tape_append_write_or_turingos_import_surface():
    source = INTERPRETER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    ]
    attrs = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}

    assert not any(name.startswith("turingos") for name in imports)
    assert not {"tape", "replay", "codec"} & {part for name in imports for part in name.split(".")}
    assert "append" not in attrs
    assert "write" not in attrs
    assert "open(" not in source
