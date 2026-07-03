from dataclasses import dataclass, replace
from types import SimpleNamespace
import hashlib, json


@dataclass(frozen=True)
class State:
    program_counter: int = 0; counter_a: int = 0; counter_b: int = 0; halted: bool = False


def _payload(state):
    return {
        "program_counter": state.program_counter,
        "counter_a": state.counter_a,
        "counter_b": state.counter_b,
        "halted": state.halted,
    }


def state_hash(state):
    raw = json.dumps(_payload(state), sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _counter(instr):
    counter = instr.get("counter")
    if counter not in {"counter_a", "counter_b"}:
        raise ValueError(f"unknown counter: {counter!r}")
    return counter


def _pc(instr, name):
    value = instr.get(name)
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"invalid {name}: {value!r}")
    return value


def _checked_state(state):
    if min(state.program_counter, state.counter_a, state.counter_b) < 0:
        raise ValueError("state fields must be nonnegative")
    return state


def step(program, state=None):
    state = _checked_state(state or State())
    prev_hash = state_hash(state)
    if state.halted:
        return SimpleNamespace(state=state, prev_state_hash=prev_hash, next_state_hash=prev_hash)
    if state.program_counter >= len(program):
        raise ValueError(f"program counter out of range: {state.program_counter}")
    instr = program[state.program_counter]
    op = instr.get("op")
    if op == "INC":
        counter = _counter(instr)
        next_state = replace(
            state,
            program_counter=_pc(instr, "next_pc"),
            **{counter: getattr(state, counter) + 1},
        )
    elif op == "DECJZ":
        counter = _counter(instr)
        if getattr(state, counter) == 0:
            next_state = replace(state, program_counter=_pc(instr, "zero_pc"))
        else:
            next_state = replace(
                state,
                program_counter=_pc(instr, "nonzero_pc"),
                **{counter: getattr(state, counter) - 1},
            )
    elif op == "HALT":
        next_state = replace(state, halted=True)
    else:
        raise ValueError(f"unknown op: {op!r}")
    return SimpleNamespace(
        state=next_state,
        prev_state_hash=prev_hash,
        next_state_hash=state_hash(next_state),
    )


def run(program, initial_state=None, max_steps=1000):
    state = _checked_state(initial_state or State())
    trace = []
    for _ in range(max_steps):
        if state.halted:
            return SimpleNamespace(state=state, trace=trace)
        result = step(program, state)
        trace = trace + [
            {
                "prev_state_hash": result.prev_state_hash,
                "next_state_hash": result.next_state_hash,
            }
        ]
        state = result.state
    raise RuntimeError("step budget exhausted")
