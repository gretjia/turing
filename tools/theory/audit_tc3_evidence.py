#!/usr/bin/env python3
"""Audit TC3 witness export artifacts against the TC1 reference interpreter."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.theory.reference_interpreter import State, state_hash, step  # noqa: E402


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


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


def _run_reference(program: list[dict[str, Any]], state: State, max_steps: int) -> dict[str, Any]:
    for step_index in range(max_steps):
        if state.halted:
            return {
                "terminal_kind": "HALTED",
                "steps_executed": step_index,
                "final_state": _state_payload(state),
                "final_state_hash": state_hash(state),
            }
        state = step(program, state).state
        if state.halted:
            return {
                "terminal_kind": "HALTED",
                "steps_executed": step_index + 1,
                "final_state": _state_payload(state),
                "final_state_hash": state_hash(state),
            }
    return {
        "terminal_kind": "BUDGET_EXHAUSTED",
        "steps_executed": max_steps,
        "final_state": _state_payload(state),
        "final_state_hash": state_hash(state),
    }


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(root: Path) -> dict[str, Any]:
    manifest = _load_json(root / "bundle_manifest.json")
    fuzz_manifest = _load_json(root / "fuzz" / "fuzz_manifest.json")
    corpus = _load_jsonl(root / "fuzz" / "corpus.jsonl")
    rust_results = {
        row["case_id"]: row for row in _load_jsonl(root / "fuzz" / "rust_results.jsonl")
    }

    failures: list[dict[str, Any]] = []
    for row in corpus:
        case_id = row["case_id"]
        observed = rust_results.get(case_id)
        if observed is None:
            failures.append({"case_id": case_id, "reason": "missing_rust_result"})
            continue
        expected = _run_reference(
            row["program"],
            _state_from_payload(row["initial_state"]),
            row["max_steps"],
        )
        mismatch = {
            key: {"rust": observed.get(key), "reference": expected[key]}
            for key in ["terminal_kind", "steps_executed", "final_state", "final_state_hash"]
            if observed.get(key) != expected[key]
        }
        if mismatch:
            failures.append({"case_id": case_id, "reason": "differential_mismatch", "mismatch": mismatch})

    bundle_failures = []
    for line in (root / "bundle_sha256s.txt").read_text(encoding="utf-8").splitlines():
        expected, rel = line.split("  ", 1)
        actual = _sha256_file(root / rel)
        if actual != expected:
            bundle_failures.append({"path": rel, "expected": expected, "actual": actual})

    verdict = "PASS" if not failures and not bundle_failures else "FAIL"
    return {
        "schema_id": "turingos.tc3.differential_results.v1",
        "verdict": verdict,
        "evidence_class": manifest["evidence_class"],
        "seed": fuzz_manifest["seed"],
        "cases_checked": len(corpus),
        "program_count": manifest["program_count"],
        "bundle_count": len(manifest["runs"]),
        "differential_failures": failures[:20],
        "differential_failure_count": len(failures),
        "bundle_digest_failures": bundle_failures,
        "not_run_is_fail": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    report = audit(args.root)
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.write:
        out = args.root / "fuzz" / "differential_results.json"
        out.write_text(payload, encoding="utf-8")
    sys.stdout.write(payload)
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
