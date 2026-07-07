#!/usr/bin/env python3
"""FCE-B4: memory/context handling under long-horizon load.

Purpose (09_FINAL_CERTIFICATION_EVALS.md §5, FCE-B4): the agentic stack stays correct as tape
and context grow (Intent §3: orchestrators run hours-to-days). Cross-cutting, blocking scenario
(not a goal-row scenario, but FCE-B4 must PASS for the suite to reach SHIPPED per §8's
cross-cutting note).

Four checks, matching the spec's four numbered steps exactly:

  1. Long-tape correctness (FIXTURE): generate a >=10,000-event fixture tape with
     gen_fixture_tape.py; run a strict auditor (full digest/chain/index/fixture-label
     recomputation against every event) TWICE and assert the two verdicts are identical
     (determinism); build a "console" snapshot (tape-derived summary + hash) from two
     independent reads and assert the snapshot hash is equal (hash-equal rebuild); record
     wall-clock and peak memory.
  2. Constraint persistence: a scripted 8-atom orchestrator session seeds a constraint at atom 1
     ("never touch path X; re-verify the constitution pin at each checkpoint") and checkpoints
     at atoms 4 and 8 both (a) genuinely re-run a constitution-pin verification command and
     (b) never touch the forbidden path.
  3. Checkpoint/compaction resilience: between atoms 5 and 6 the in-memory orchestrator object is
     destroyed and a FRESH object is built that reads the constraint ONLY from the persisted
     session-state file (never from chat memory); the constraint must survive intact and continue
     to be enforced through atom 8.
  4. Failure-memory scale check: 50 FIXTURE broadcast rules are generated and fed into the REAL
     production FailureMemory (src/turingos/capsule.py); the built (schema-validated) capsule's
     injected_rules must respect the pre-registered injection budget (ADR-M4-006:
     max_active_rules=4, max_rule_chars=4000) -- top-N selection, no unbounded prompt growth --
     even though far more than 4 distinct relevant rules are available.

Real code defect fixed as part of this scenario (documented in full in the module docstrings of
src/turingos/capsule.py and src/turingos/schemas.py, and in this scenario's README.md): before
this change, FailureMemory.relevant_rules() had NO ceiling -- a long-running session accumulating
many distinct FailureClasses against the same atom/module would grow a capsule's injected_rules
without bound (the audit's P12 "rule pile-up without retirement" finding, RES_M4 §2.8/§4). Check 4
below would have FAILed honestly against the pre-fix code (50 fed rules -> unbounded
injected_rules); it PASSes now because the pre-registered budget from
m4_self_improvement/real_s01_deepseek_20260703/proposals/BroadcastRuleRetired_PROPOSAL.json's
`pre_registered_capsule_budget` was landed into FailureMemory's defaults, capsule.schema.json's
`injected_rules.maxItems`, and schemas.py's structural guard (defense in depth).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCENARIO_DIR = Path(__file__).resolve().parent
CERT_TOOLS_DIR = SCENARIO_DIR.parent
sys.path.insert(0, str(CERT_TOOLS_DIR))
import gen_fixture_tape  # noqa: E402
import gen_fixture_broadcast_rules  # noqa: E402


CONSTITUTION_SHA256 = "a0174ef8a2be6914f86ea8e594e022c7ca6a4221ed63535d65a997e096ca3ad0"
TAPE_EVENT_COUNT = 10_000
TAPE_SEED = "fce-b4-long-horizon"

CONSTRAINT_TEXT = "never touch path X; re-verify the constitution pin at each checkpoint"
FORBIDDEN_PATH = "FORBIDDEN/DO_NOT_TOUCH.txt"
CHECKPOINT_ATOMS = (4, 8)
COMPACTION_BEFORE_ATOM = 6  # compaction forced strictly between atoms 5 and 6

# Scripted, never-touches-forbidden-path atom activity. One atom (7) touches a similarly named
# but distinct path to prove the checker discriminates rather than trivially matching a prefix.
ATOM_TOUCHED_FILES = {
    1: ["work/atom_1_notes.md"],
    2: ["work/atom_2_impl.py"],
    3: ["work/atom_3_impl.py", "work/atom_3_tests.py"],
    4: ["work/atom_4_impl.py"],
    5: ["work/atom_5_impl.py"],
    6: ["work/atom_6_impl.py"],
    7: ["FORBIDDEN/DO_NOT_TOUCH_2.txt", "work/atom_7_impl.py"],  # near-miss, not the forbidden path
    8: ["work/atom_8_impl.py"],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def run_command(name: str, argv: list[str], cwd: Path, out_dir: Path, timeout: int = 120) -> dict[str, Any]:
    started = time.monotonic()
    proc = subprocess.run(
        argv,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    stdout = out_dir / f"{name}.stdout.txt"
    stderr = out_dir / f"{name}.stderr.txt"
    stdout.write_text(proc.stdout, encoding="utf-8")
    stderr.write_text(proc.stderr, encoding="utf-8")
    return {
        "name": name,
        "cmd": " ".join(argv),
        "exit_code": proc.returncode,
        "wall_clock_ms": elapsed_ms,
        "stdout": stdout.name,
        "stderr": stderr.name,
        "stdout_text": proc.stdout,
        "stderr_text": proc.stderr,
    }


def normalize(value: Any) -> Any:
    volatile = {"wall_clock_ms", "peak_rss_kb", "timestamp_utc"}
    if isinstance(value, dict):
        return {k: normalize(v) for k, v in value.items() if k not in volatile}
    if isinstance(value, list):
        return [normalize(item) for item in value]
    return value


# --- Check 1: long-tape correctness (auditor + console) ----------------------


def audit_tape(tape_path: Path, seed: str) -> dict[str, Any]:
    """Strict auditor: recompute EVERY event from (seed, index) via the fixture generator's own
    deterministic formula and assert byte-for-byte dict equality against what is actually on the
    tape. This checks event_digest correctness, the prev_event_digest chain, monotonic
    event_index, and the FIXTURE label, all in one pass -- a divergence anywhere is a genuine
    integrity failure, not a fabricated pass."""
    started = time.monotonic()
    event_count = 0
    first_digest = None
    last_digest = None
    with tape_path.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            actual = json.loads(line)
            expected = gen_fixture_tape.event(seed, index)
            if actual != expected:
                raise AssertionError(f"tape event {index} diverges from recomputation")
            if actual.get("fixture_or_real") != "FIXTURE":
                raise AssertionError(f"tape event {index} missing FIXTURE label")
            if actual.get("event_index") != index:
                raise AssertionError(f"tape event {index} has wrong event_index {actual.get('event_index')}")
            if index == 0:
                first_digest = actual["event_digest"]
            last_digest = actual["event_digest"]
            event_count += 1
    elapsed_ms = int((time.monotonic() - started) * 1000)
    peak_rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "schema_id": "turingos.fce.b4.auditor_report.v1",
        "event_count": event_count,
        "first_event_digest": first_digest,
        "last_event_digest": last_digest,
        "chain_and_digest_recompute_ok": True,
        "all_events_fixture_labeled": True,
        "wall_clock_ms": elapsed_ms,
        "peak_rss_kb": peak_rss_kb,
    }


def build_console_snapshot(tape_path: Path) -> dict[str, Any]:
    """"Console" rebuild: an independent, from-scratch read of the tape file that derives a
    tape-level summary (file digest, first/last event digests, event count) purely from tape
    bytes -- the same discipline the real M6 console projection audit uses (every displayed value
    must be tape-derivable). Two independent calls of this function against the same file must
    produce a byte-identical snapshot and therefore an identical snapshot_hash."""
    tape_sha256 = sha256_file(tape_path)
    lines = tape_path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    last = json.loads(lines[-1])
    body = {
        "schema_id": "turingos.fce.b4.console_snapshot.v1",
        "tape_sha256": tape_sha256,
        "event_count": len(lines),
        "first_event_digest": first["event_digest"],
        "last_event_digest": last["event_digest"],
    }
    snapshot_hash = sha256_bytes(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    body["snapshot_hash"] = snapshot_hash
    return body


def check1_long_tape_correctness(
    *, scenario_root: Path, repo: Path, commands: list[dict[str, Any]]
) -> tuple[bool, dict[str, Any], list[Path]]:
    tape_path = scenario_root / "fixture_tape.jsonl"
    gen_command = run_command(
        "gen_fixture_tape",
        [
            sys.executable,
            str(CERT_TOOLS_DIR / "gen_fixture_tape.py"),
            "--count",
            str(TAPE_EVENT_COUNT),
            "--seed",
            TAPE_SEED,
            "--out",
            str(tape_path),
        ],
        cwd=repo,
        out_dir=scenario_root,
    )
    commands.append(gen_command)
    gen_ok = gen_command["exit_code"] == 0 and tape_path.is_file()
    generator_summary = json.loads(gen_command["stdout_text"]) if gen_command["stdout_text"].strip() else {}

    auditor_report_1 = audit_tape(tape_path, TAPE_SEED) if gen_ok else {}
    auditor_report_2 = audit_tape(tape_path, TAPE_SEED) if gen_ok else {}
    auditor_deterministic = gen_ok and normalize(auditor_report_1) == normalize(auditor_report_2)

    console_snapshot_1 = build_console_snapshot(tape_path) if gen_ok else {}
    console_snapshot_2 = build_console_snapshot(tape_path) if gen_ok else {}
    console_hash_equal = (
        gen_ok
        and console_snapshot_1.get("snapshot_hash") == console_snapshot_2.get("snapshot_hash")
        and console_snapshot_1 == console_snapshot_2
    )

    event_count_ok = gen_ok and auditor_report_1.get("event_count", 0) >= 10_000

    report = {
        "schema_id": "turingos.fce.b4.check1_long_tape_report.v1",
        "tape_path": tape_path.name,
        "tape_generation": {
            "cmd": gen_command["cmd"],
            "exit_code": gen_command["exit_code"],
            "reported_sha256": generator_summary.get("sha256"),
            "actual_sha256": sha256_file(tape_path) if tape_path.is_file() else None,
            "generator_reported_digest_matches_actual": (
                gen_ok and generator_summary.get("sha256") == sha256_file(tape_path)
            ),
        },
        "auditor_pass_1": auditor_report_1,
        "auditor_pass_2": auditor_report_2,
        "auditor_deterministic_across_two_runs": auditor_deterministic,
        "console_snapshot_1": console_snapshot_1,
        "console_snapshot_2": console_snapshot_2,
        "console_rebuild_hash_equal": console_hash_equal,
        "event_count_at_least_10000": event_count_ok,
    }
    report_path = scenario_root / "check1_long_tape_report.json"
    write_json(report_path, report)

    passed = bool(gen_ok and event_count_ok and auditor_deterministic and console_hash_equal)
    return passed, report, [report_path]


# --- Checks 2 & 3: constraint persistence + checkpoint/compaction resilience --


def run_constitution_pin_command(
    *, plan_root: Path, scenario_root: Path, atom_index: int
) -> dict[str, Any]:
    constitution_path = plan_root.parent / "turing_v5" / "pack_v5_3_1" / "00_authority" / "constitution_root_law.md"
    command = run_command(
        f"atom{atom_index}_constitution_pin_check",
        ["sha256sum", str(constitution_path)],
        cwd=plan_root.parent,
        out_dir=scenario_root,
    )
    digest = command["stdout_text"].split()[0] if command["stdout_text"].strip() else ""
    command["constitution_pin_matches"] = command["exit_code"] == 0 and digest == CONSTITUTION_SHA256
    command["constitution_path"] = str(constitution_path)
    return command


class ScriptedOrchestratorSession:
    """A minimal, deterministic stand-in for an orchestrator's per-atom loop. The constraint is
    persisted to `state_path` (representing the tracker/tape) on every write; a session object's
    own Python attributes represent ONLY in-memory/chat-scoped state, which a real compaction or
    process restart would discard. Reading the constraint always goes through `state_path`, never
    through an in-memory field, so the mechanical fix for context loss (Intent §8.6-style: state
    must live in the tracker/tape, not chat memory) is actually exercised, not merely asserted."""

    def __init__(self, state_path: Path) -> None:
        self._state_path = state_path

    def seed_constraint(self, constraint_text: str, forbidden_path: str) -> None:
        write_json(
            self._state_path,
            {
                "schema_id": "turingos.fce.b4.session_state.v1",
                "constraint_text": constraint_text,
                "forbidden_path": forbidden_path,
                "checkpoint_log": [],
            },
        )

    def _load_state(self) -> dict[str, Any]:
        return json.loads(self._state_path.read_text(encoding="utf-8"))

    def run_atom(
        self,
        atom_index: int,
        touched_files: list[str],
        *,
        plan_root: Path,
        scenario_root: Path,
        is_checkpoint: bool,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        state = self._load_state()  # constraint recovered from the persisted store, every atom
        forbidden_path = state["forbidden_path"]
        path_x_touched = forbidden_path in touched_files
        record: dict[str, Any] = {
            "atom_index": atom_index,
            "touched_files": touched_files,
            "path_x_touched": path_x_touched,
            "constraint_text_at_read_time": state["constraint_text"],
        }
        command = None
        if is_checkpoint:
            command = run_constitution_pin_command(
                plan_root=plan_root, scenario_root=scenario_root, atom_index=atom_index
            )
            record["constitution_check_ran"] = True
            record["constitution_check_exit_code"] = command["exit_code"]
            record["constitution_pin_matches"] = command["constitution_pin_matches"]
            state["checkpoint_log"].append(
                {"atom_index": atom_index, "exit_code": command["exit_code"], "matches_pin": command["constitution_pin_matches"]}
            )
            write_json(self._state_path, state)
        else:
            record["constitution_check_ran"] = False
        return record, command


def check2_and_check3_constraint_persistence(
    *, scenario_root: Path, plan_root: Path, commands: list[dict[str, Any]]
) -> tuple[bool, bool, dict[str, Any], list[Path]]:
    state_path = scenario_root / "session_state.json"
    session = ScriptedOrchestratorSession(state_path)
    session.seed_constraint(CONSTRAINT_TEXT, FORBIDDEN_PATH)
    seeded_state = json.loads(state_path.read_text(encoding="utf-8"))

    atom_records: list[dict[str, Any]] = []
    checkpoint_records: dict[int, dict[str, Any]] = {}
    post_compaction_record: dict[str, Any] | None = None

    for atom_index in range(1, 9):
        if atom_index == COMPACTION_BEFORE_ATOM:
            # Force a context compaction / session restart strictly between atoms 5 and 6: the
            # in-memory Python object is discarded entirely and a FRESH one is built that reads
            # the constraint ONLY from state_path (never re-seeded, never passed in memory).
            del session
            session = ScriptedOrchestratorSession(state_path)
            recovered_state = json.loads(state_path.read_text(encoding="utf-8"))
            post_compaction_record = {
                "recovered_constraint_text": recovered_state.get("constraint_text"),
                "recovered_forbidden_path": recovered_state.get("forbidden_path"),
                "constraint_text_matches_seeded": recovered_state.get("constraint_text") == seeded_state["constraint_text"],
                "forbidden_path_matches_seeded": recovered_state.get("forbidden_path") == seeded_state["forbidden_path"],
            }

        is_checkpoint = atom_index in CHECKPOINT_ATOMS
        record, command = session.run_atom(
            atom_index,
            ATOM_TOUCHED_FILES[atom_index],
            plan_root=plan_root,
            scenario_root=scenario_root,
            is_checkpoint=is_checkpoint,
        )
        atom_records.append(record)
        if command is not None:
            commands.append(command)
        if is_checkpoint:
            checkpoint_records[atom_index] = record

    no_atom_touched_forbidden_path = all(not r["path_x_touched"] for r in atom_records)
    checkpoints_ok = all(
        checkpoint_records[idx]["constitution_check_ran"]
        and checkpoint_records[idx]["constitution_check_exit_code"] == 0
        and checkpoint_records[idx]["constitution_pin_matches"]
        and not checkpoint_records[idx]["path_x_touched"]
        for idx in CHECKPOINT_ATOMS
    )
    post_compaction_ok = bool(
        post_compaction_record
        and post_compaction_record["constraint_text_matches_seeded"]
        and post_compaction_record["forbidden_path_matches_seeded"]
    )

    report = {
        "schema_id": "turingos.fce.b4.constraint_persistence_report.v1",
        "constraint_text": CONSTRAINT_TEXT,
        "forbidden_path": FORBIDDEN_PATH,
        "checkpoint_atoms": list(CHECKPOINT_ATOMS),
        "compaction_forced_before_atom": COMPACTION_BEFORE_ATOM,
        "atom_records": atom_records,
        "post_compaction_record": post_compaction_record,
        "no_atom_touched_forbidden_path_2_of_2_near_miss_discriminated": (
            no_atom_touched_forbidden_path and atom_records[6]["touched_files"] == ATOM_TOUCHED_FILES[7]
        ),
        "checkpoints_2_of_2_pass": checkpoints_ok,
        "post_compaction_1_of_1_pass": post_compaction_ok,
    }
    report_path = scenario_root / "check2_3_constraint_persistence_report.json"
    write_json(report_path, report)

    check2_passed = bool(checkpoints_ok and no_atom_touched_forbidden_path)
    check3_passed = bool(post_compaction_ok and no_atom_touched_forbidden_path)
    return check2_passed, check3_passed, report, [report_path]


# --- Check 4: failure-memory scale check -------------------------------------


def check4_failure_memory_scale(
    *, scenario_root: Path, repo: Path, commands: list[dict[str, Any]]
) -> tuple[bool, dict[str, Any], list[Path]]:
    rules_path = scenario_root / "broadcast_rules_fixture.json"
    gen_command = run_command(
        "gen_fixture_broadcast_rules",
        [
            sys.executable,
            str(CERT_TOOLS_DIR / "gen_fixture_broadcast_rules.py"),
            "--count",
            "50",
            "--max-active",
            "8",
            "--out",
            str(rules_path),
        ],
        cwd=repo,
        out_dir=scenario_root,
    )
    commands.append(gen_command)
    gen_ok = gen_command["exit_code"] == 0 and rules_path.is_file()
    fixture_rules = json.loads(rules_path.read_text(encoding="utf-8"))["rules"] if gen_ok else []

    src_dir = repo / "src"
    sys.path.insert(0, str(src_dir))
    from turingos import capsule as capsule_mod  # noqa: PLC0415
    from turingos import schemas  # noqa: PLC0415
    from turingos.tape import Tape  # noqa: PLC0415

    tape_dir = scenario_root / "scale_check_micro_tape"
    tape = Tape.init(str(tape_dir), "FCE-B4-W1")
    tape.append("SystemBootstrapped", {"kind": "boot"}, predicate_pass=True)

    atom = {
        "atom_id": "FCE-B4-ATOM",
        "module_id": "FCE-B4",
        "intent": "long-horizon failure-memory scale check",
        "allowed_files": ["fixture/scale_check.py"],
        "acceptance_commands": ["true"],
    }

    reason_codes = list(capsule_mod.FailureMemory._CLASS_BY_REASON.keys())

    # Reference (uncapped) FailureMemory: proves >4 distinct relevant rules genuinely exist in
    # this 50-rule feed, so the budgeted result below is a real truncation, not a vacuous one.
    fm_uncapped = capsule_mod.FailureMemory(max_active_rules=10_000, max_rule_chars=10_000_000)
    fm_budgeted = capsule_mod.FailureMemory()  # production defaults: ADR-M4-006 budget

    for index, fixture_rule in enumerate(fixture_rules):
        reason_code = reason_codes[index % len(reason_codes)]
        failure_node = {
            "atom_id": atom["atom_id"],
            "module_id": atom["module_id"],
            "reason_code": reason_code,
            "reason_detail": f"fixture broadcast rule {fixture_rule.get('rule_id')} (private, not broadcast)",
        }
        fm_uncapped.classify(failure_node)
        fm_budgeted.classify(failure_node)

    uncapped_rules = fm_uncapped.relevant_rules(atom)
    capsule = capsule_mod.build_capsule(tape, atom, failure_memory=fm_budgeted)
    schema_valid = True
    schema_error = None
    try:
        schemas.validate_capsule(capsule)
    except Exception as exc:  # noqa: BLE001
        schema_valid = False
        schema_error = str(exc)

    injected = capsule.get("injected_rules", [])
    total_chars = sum(len(r["rule"]) for r in injected)
    total_tokens = sum(len(r["rule"].split()) for r in injected)
    token_ceiling = 700  # pinned: max_rule_chars=4000 / ~avg 5.7 chars-per-token, rounded down

    report = {
        "schema_id": "turingos.fce.b4.failure_memory_scale_report.v1",
        "fixture_rules_fed": len(fixture_rules),
        "distinct_relevant_rules_uncapped": len(uncapped_rules),
        "pre_registered_budget": {
            "max_active_rules": capsule_mod._DEFAULT_MAX_ACTIVE_RULES,
            "max_rule_chars": capsule_mod._DEFAULT_MAX_RULE_CHARS,
            "source": (
                "PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/m4_self_improvement/"
                "real_s01_deepseek_20260703/proposals/BroadcastRuleRetired_PROPOSAL.json"
                "#pre_registered_capsule_budget"
            ),
        },
        "capsule_injected_rules_count": len(injected),
        "capsule_injected_rules_total_chars": total_chars,
        "capsule_injected_rules_total_tokens": total_tokens,
        "token_ceiling": token_ceiling,
        "capsule_schema_valid": schema_valid,
        "capsule_schema_error": schema_error,
        "budget_is_a_genuine_truncation": len(uncapped_rules) > capsule_mod._DEFAULT_MAX_ACTIVE_RULES,
    }
    report_path = scenario_root / "check4_failure_memory_scale_report.json"
    write_json(report_path, report)

    passed = bool(
        gen_ok
        and schema_valid
        and len(fixture_rules) == 50
        and len(uncapped_rules) > capsule_mod._DEFAULT_MAX_ACTIVE_RULES  # proves it's a real cap
        and len(injected) <= capsule_mod._DEFAULT_MAX_ACTIVE_RULES
        and total_chars <= capsule_mod._DEFAULT_MAX_RULE_CHARS
        and total_tokens <= token_ceiling
    )
    return passed, report, [rules_path, report_path]


# --- verdict assembly --------------------------------------------------------


def build_verdict(
    *,
    root: Path,
    scenario_id: str,
    commands: list[dict[str, Any]],
    criteria: list[dict[str, Any]],
    started: float,
    evidence_files: list[Path],
) -> dict[str, Any]:
    scenario_root = root / scenario_id
    command_results = scenario_root / "command_results.json"
    write_json(
        command_results,
        {
            "schema_id": "turingos.fce.b4.command_results.v1",
            "commands": [
                {
                    "name": item["name"],
                    "cmd": item["cmd"],
                    "exit_code": item["exit_code"],
                    "wall_clock_ms": item["wall_clock_ms"],
                }
                for item in commands
            ],
        },
    )
    evidence_paths = [rel(root, command_results)]
    for command in commands:
        evidence_paths.append(f"{scenario_id}/{command['stdout']}")
        evidence_paths.append(f"{scenario_id}/{command['stderr']}")
    for path in evidence_files:
        if path.is_file():
            evidence_paths.append(rel(root, path))
    evidence_paths = sorted(set(evidence_paths))
    passed = all(item["result"] is True for item in criteria)
    return {
        "schema_id": "turingos.fce_scenario_verdict.v1",
        "scenario_id": scenario_id,
        "verdict": "PASS" if passed else "FAIL",
        "not_run_is_fail": True,
        "goals_served": ["G2", "G5"],
        "commands_executed": [
            {"cmd": command["cmd"], "exit_code": command["exit_code"]} for command in commands
        ],
        "pass_criteria_results": criteria,
        "evidence": evidence_paths,
        "evidence_sha256": {item: sha256_file(root / item) for item in evidence_paths},
        "fixture_or_real": "FIXTURE",
        "automatic_fail_triggered": None,
        "wall_clock_ms": int((time.monotonic() - started) * 1000),
        "timestamp_utc": utc_now(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--plan-root", required=True)
    parser.add_argument("--scenario-id", required=True)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    repo = Path(args.repo).resolve()
    plan_root = Path(args.plan_root).resolve()
    scenario_id = args.scenario_id
    scenario_root = root / scenario_id
    scenario_root.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    commands: list[dict[str, Any]] = []
    evidence_files: list[Path] = []

    check1_ok, check1_report, check1_evidence = check1_long_tape_correctness(
        scenario_root=scenario_root, repo=repo, commands=commands
    )
    evidence_files.extend(check1_evidence)

    check2_ok, check3_ok, check23_report, check23_evidence = check2_and_check3_constraint_persistence(
        scenario_root=scenario_root, plan_root=plan_root, commands=commands
    )
    evidence_files.extend(check23_evidence)

    check4_ok, check4_report, check4_evidence = check4_failure_memory_scale(
        scenario_root=scenario_root, repo=repo, commands=commands
    )
    evidence_files.extend(check4_evidence)

    criteria = [
        {
            "criterion": "check1_long_tape_10000_plus_events_auditor_and_console_deterministic",
            "result": check1_ok,
            "evidence": rel(root, scenario_root / "check1_long_tape_report.json"),
        },
        {
            "criterion": "check2_constraint_persistence_checkpoints_atom4_and_atom8",
            "result": check2_ok,
            "evidence": rel(root, scenario_root / "check2_3_constraint_persistence_report.json"),
        },
        {
            "criterion": "check3_checkpoint_compaction_resilience_constraint_survives_restart",
            "result": check3_ok,
            "evidence": rel(root, scenario_root / "check2_3_constraint_persistence_report.json"),
        },
        {
            "criterion": "check4_failure_memory_injection_budget_respected_under_scale",
            "result": check4_ok,
            "evidence": rel(root, scenario_root / "check4_failure_memory_scale_report.json"),
        },
    ]

    readme = scenario_root / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# FCE-B4 Memory/Context Handling Under Long-Horizon Load",
                "",
                "Evidence label: FIXTURE.",
                "",
                "Generates a >=10,000-event synthetic tape (gen_fixture_tape.py) and runs a strict",
                "auditor plus a console-style rebuild over it twice each to prove determinism and",
                "hash-equal rebuild; runs a scripted 8-atom session proving a constraint seeded at",
                "atom 1 survives to checkpoints at atoms 4 and 8 and a forced context compaction",
                "between atoms 5 and 6; and feeds 50 FIXTURE broadcast rules through the REAL",
                "production FailureMemory/build_capsule (src/turingos/capsule.py) to prove the",
                "capsule injection budget is respected at scale.",
                "",
                "This scenario also LANDS a real code fix: FailureMemory.relevant_rules() previously",
                "had no ceiling (audit finding P12, RES_M4 §2.8/§4 -- \"rule pile-up without",
                "retirement\"). The pre-registered budget from",
                "m4_self_improvement/real_s01_deepseek_20260703/proposals/BroadcastRuleRetired_PROPOSAL.json",
                "(max_active_rules=4, max_rule_chars=4000) is now enforced in",
                "src/turingos/capsule.py (FailureMemory defaults + selection logic),",
                "contracts/capsule.schema.json (injected_rules.maxItems=4), and src/turingos/schemas.py",
                "(structural guard, defense in depth). Check 4's report records that more than 4",
                "distinct relevant rules are genuinely available from the 50-rule feed (an uncapped",
                "reference FailureMemory is built alongside the budgeted one), so the observed",
                "truncation to <=4 is a real effect of the fix, not a vacuous pass.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    claim_boundary = scenario_root / "CLAIM_BOUNDARY.json"
    write_json(
        claim_boundary,
        {
            "schema_id": "CLAIM_BOUNDARY.v2",
            "evidence_class": "FIXTURE",
            "claims": [
                "FCE-B4 long-horizon fixture-tape auditor/console determinism check",
                "FCE-B4 scripted 8-atom constraint-persistence and compaction-resilience check",
                "FCE-B4 failure-memory injection-budget scale check over the real production capsule builder",
                "landed a real fix for audit finding P12 (unbounded broadcast-rule injection) in "
                "src/turingos/capsule.py, contracts/capsule.schema.json, and src/turingos/schemas.py",
            ],
            "non_claims": [
                "not a real multi-day/multi-hour LLM orchestrator session",
                "not a real production 10,000-event tape (synthetic FIXTURE tape only)",
                "not release eligibility",
                "not SHIPPED",
            ],
        },
    )
    evidence_files.extend([readme, claim_boundary])

    verdict = build_verdict(
        root=root,
        scenario_id=scenario_id,
        commands=commands,
        criteria=criteria,
        started=started,
        evidence_files=evidence_files,
    )
    write_json(scenario_root / f"{scenario_id}_verdict.json", verdict)
    print(json.dumps({"scenario_id": scenario_id, "verdict": verdict["verdict"]}, sort_keys=True))
    return 0 if verdict["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
