"""turingos.loop — the Stage-1 E2E loop DRIVER (the BOOT milestone).

Frozen seam (contracts/INTERFACES.md loop.py section):

    def run_loop(spec, tape_dir, *, worker=None, max_atoms=3) -> dict

This is the driver that closes the ENTIRE minimum complete loop ONCE, end-to-end, with a
deterministic fake/manual Worker — no real vendor adapter, no GitHub. It is the orchestration
seam over the FROZEN kernel; it changes no frozen signature and adds no third-party dep.

The loop it drives (plan App B / PREDICATE.stage1_e2e.md), every step a Tape event:

    Tape.init -> boot/adopt (SystemBootstrapped + ProjectAdopted)
              -> accept_goalstate  (GoalStateAccepted, SOVEREIGN_ACCEPT)
              -> accept_module_plan (ModulePlanAccepted, SOVEREIGN_ACCEPT)
              -> planner.expand_atoms (AtomProposed x N, PROPOSAL)
              -> for each atom (up to max_atoms):
                   build a SHIELDED Work Capsule (inject ONLY the relevant abstract
                       FailureClass rule from FailureMemory) -> WorkCapsuleBuilt (PROPOSAL)
                   record the dispatch authorization        -> WorkerDispatched (PROPOSAL)
                   dispatch the (Fake) Worker to an ISOLATED worktree -> candidate + receipt
                   import the receipt                        -> WorkerReceiptImported (OBSERVATION)
                   import the Macro tree-OID anchor          -> MacroObservationImported (OBSERVATION)
                   predicate.evaluate(capsule, receipt, worktree, tape, 'CandidateAccepted')
                   record the result                         -> PredicateEvaluated (OBSERVATION)
                   PASS -> CandidateAccepted (SOVEREIGN_ACCEPT, advance accepted_head)
                   FAIL -> FailureNode (OBSERVATION, failure-is-state) + FailureMemory.classify
              -> make_handoff_bundle (HandoffGenerated) + verify_replay_equal (ReplayVerified)

The run is DRIVEN to traverse BOTH predicate branches: at least one atom fails (a fail_test /
fail_scope scenario) and at least one atom passes. The first failure's abstract rule is shielded
into the NEXT capsule (same module -> relevant), demonstrating BROADCAST + SHIELD with no raw
failure / worker stdout leaking into the capsule.

Authorized-vs-Accepted [Art. 0.4 / refs.md App C]: WorkerDispatched is a PRESERVE authorization
(it carries ordinary authorization as a Tape event, NOT a third-ref advance); only a
CandidateAccepted with a deterministic Predicate PASS advances accepted_head.

Determinism: the FakeWorker is deterministic, the planner is a pure function of module_id, and the
predicate is a pure function of Tape bytes, so the same spec yields the same branch coverage and
the same accepted state on any fresh tape (replay-equality precondition).

Stdlib only (tempfile, pathlib, json). The candidate worktree is a normal Macro git repo, separate
from both the build repo and the SHA-256 Micro Tape.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from . import boot, capsule as capsule_mod, evidence, planner, predicate, replay
from .tape import Tape
from .worker.fake import FakeWorker

# Registry event names this driver emits beyond what the kernel modules emit for it.
_WORKER_DISPATCHED = "WorkerDispatched"   # PROPOSAL — an authorization, never an advance
_PREDICATE_EVALUATED = "PredicateEvaluated"  # OBSERVATION — the recorded predicate result
_CANDIDATE_ACCEPTED = "CandidateAccepted"    # SOVEREIGN_ACCEPT — PASS path, advances accepted_head
_FAILURE_NODE = "FailureNode"                # OBSERVATION — FAIL path, failure-is-state

# The SOVEREIGN_ACCEPT event whose advance rule the predicate enforces for a candidate.
_ACCEPT_EVENT_TYPE = "CandidateAccepted"

# The DEFAULT per-atom scenario plan: drive at least one FAIL then a PASS so the run traverses
# BOTH predicate branches (the milestone requirement). fail_test exercises P6 (DeclaredTests);
# the later pass exercises the full PASS path -> CandidateAccepted advance.
_DEFAULT_SCENARIOS = ("fail_test", "pass", "pass")


def _scenario_for(worker, index: int) -> str:
    """Resolve the FakeWorker scenario for atom `index` from the `worker` argument.

    worker may be:
      * None                       -> use the default scenario plan (fail then pass).
      * a list/tuple of scenarios  -> the per-atom scenario plan (strings).
      * a single WorkerAdapter     -> used as-is for every atom (caller controls the scenario).
    """
    if worker is None:
        if index < len(_DEFAULT_SCENARIOS):
            return _DEFAULT_SCENARIOS[index]
        return "pass"
    if isinstance(worker, (list, tuple)):
        if index < len(worker):
            return worker[index]
        return worker[-1] if worker else "pass"
    return None  # a concrete adapter was supplied; _adapter_for handles it


def _adapter_for(worker, index: int):
    """Return the WorkerAdapter to dispatch for atom `index`.

    A concrete WorkerAdapter (has a callable `run`) is used directly; otherwise we build a
    deterministic FakeWorker for the scenario resolved by `_scenario_for`.
    """
    if worker is not None and not isinstance(worker, (list, tuple)) and hasattr(worker, "run"):
        return worker
    scenario = _scenario_for(worker, index)
    return FakeWorker(scenario=scenario)


def _executable_atom(atom: dict, ordinal: int) -> dict:
    """Derive a worker-EXECUTABLE atom from a planner atom.

    The planner's acceptance_commands (e.g. `python3 -m unittest tests.test_m1`) are the
    project-level declared tests; they are NOT runnable inside an isolated FakeWorker worktree.
    The driver therefore re-scopes the atom to a worktree-local candidate file plus a frozen,
    worktree-runnable acceptance command that the FakeWorker's deterministic candidate satisfies
    on a PASS and fails on a fail_test (the candidate omits the PASS_MARKER token). This keeps the
    capsule's acceptance_commands a real, re-runnable mechanical gate (P6) inside the worktree.

    The atom IDENTITY (atom_id / module_id / intent) is preserved so q_t.active_atom, the shield's
    relevance keys, and the FailureNode<->atom matching all stay coherent with the proposed plan.
    """
    rel = "candidate/atom_%d.py" % ordinal
    derived = dict(atom)
    derived["allowed_files"] = [rel]
    # A worktree-runnable, deterministic acceptance check: the FakeWorker 'pass' candidate embeds
    # PASS_MARKER (grep exits 0); 'fail_test' omits it (grep exits 1 -> P6 test_fail).
    derived["acceptance_commands"] = ["grep -q PASS_MARKER %s" % rel]
    return derived


def _failure_node_payload(atom: dict, result) -> dict:
    """Build the FailureNode payload (failure-is-state) from a FAILing predicate result.

    Carries the mechanical failure_class / reason_code (the first failing reason) + the atom/module
    relevance keys + the deterministic reason_digest. It records the mechanical predicate reasons
    (machine-readable check records) for audit on the Tape — it deliberately does NOT carry worker
    stdout / stack traces / raw stderr (those are never lifted, never broadcast). The abstract rule
    is minted by FailureMemory.classify; raw evidence stays reachable on the Tape, not re-injected.
    """
    failing = [r for r in result.reasons if not r["ok"]]
    first = failing[0] if failing else {"reason_code": "advance_rule_violation", "check": "P9_advance"}
    reason_code = first.get("reason_code") or "advance_rule_violation"
    return {
        "failure_class": reason_code,            # coarse mechanical bucket key (classify refines it)
        "reason_code": reason_code,              # the mechanical predicate reason (no raw stdout)
        "atom_id": atom.get("atom_id"),          # relevance key (shield) + reduce retry matching
        "module_id": atom.get("module_id"),      # relevance key (shield)
        "reason_digest": result.reason_digest,   # deterministic digest of the reason records
        "passed": False,
        "predicate_reasons": [
            {
                "check": r["check"],
                "ok": r["ok"],
                "reason_code": r["reason_code"],
            }
            for r in result.reasons
        ],
    }


def run_loop(spec: dict, tape_dir: str, *, worker=None, max_atoms: int = 3) -> dict:
    """Drive the full Stage-1 E2E loop with a (fake) Worker; return a summary dict.

    See the module docstring for the exact event sequence. Traverses BOTH predicate branches
    (>=1 FailureNode AND >=1 CandidateAccepted) and ends with a HandoffGenerated bundle + a
    verified replay. Returns:

        {accepted, failed, accepted_head, tape_tip, branches_covered, handoff_bundle}

    branches_covered == (accepted >= 1 and failed >= 1).
    """
    if not isinstance(spec, dict):
        raise TypeError("spec must be a dict")
    modules = spec.get("modules") or []
    if not modules:
        raise ValueError("spec must declare at least one module under 'modules'")
    module_id = modules[0]["module_id"]
    writer_id = spec.get("writer_id") or "W1"

    # A unique scratch root for the candidate worktrees (isolated per atom). The Micro Tape lives
    # at tape_dir (a SEPARATE SHA-256 repo); candidate worktrees are normal Macro git repos.
    scratch_root = tempfile.mkdtemp(prefix="tos_loop_run_")

    # --- substrate: init the Micro Tape + boot/adopt + sovereign goal/module accepts -----------
    tape = Tape.init(tape_dir, writer_id)
    boot.boot(tape, spec)
    boot.accept_goalstate(tape, {"goal": spec.get("goal")})
    boot.accept_module_plan(tape, {"module_id": module_id})

    # --- progressive atom expansion (active module only) ---------------------------------------
    atoms = planner.expand_atoms(tape, module_id)
    if max_atoms is not None:
        atoms = atoms[: max_atoms]

    failure_memory = capsule_mod.FailureMemory()

    accepted = 0
    failed = 0

    for ordinal, atom in enumerate(atoms):
        # Re-scope the proposed atom to a worktree-runnable candidate + frozen acceptance command.
        exec_atom = _executable_atom(atom, ordinal)

        # SHIELD: build the capsule injecting ONLY the relevant abstract rules (failure_memory
        # filters by atom/module relevance; raw failure detail never reaches the capsule).
        # WorkCapsuleBuilt is a PROPOSAL (PRESERVE): tape_tip advances, accepted_head does not.
        capsule = capsule_mod.build_capsule(tape, exec_atom, failure_memory=failure_memory)

        # AUTHORIZATION: record the dispatch as a PRESERVE Tape event (NOT a third-ref advance).
        # Authorized-vs-Accepted: this is the authorization lane; accepted_head is untouched.
        tape.append(
            _WORKER_DISPATCHED,
            {
                "capsule_id": capsule["capsule_id"],
                "atom_id": exec_atom.get("atom_id"),
                "worker_kind": "fake",
            },
        )

        # ISOLATE: a fresh worktree per atom (the FakeWorker git-inits a real Macro repo there).
        worktree = str(Path(scratch_root) / ("wt_%d" % ordinal))
        adapter = _adapter_for(worker, ordinal)
        receipt = adapter.run(capsule, worktree)

        # EVIDENCE: import the worker receipt (P5 target) and the Macro tree-OID anchor (P7 target).
        # Both are OBSERVATIONs (PRESERVE). The Macro anchor binds the candidate tree the predicate
        # checks against; bind it to the receipt's reported candidate tree_oid.
        evidence.import_receipt(tape, receipt)
        tree_oid = receipt.get("candidate", {}).get("tree_oid", "")
        if tree_oid:
            evidence.import_macro_observation(tape, {"tree_oid": tree_oid})

        # GATE: the deterministic Predicate re-runs the real mechanical checks over Tape bytes.
        result = predicate.evaluate(
            capsule=capsule,
            receipt=receipt,
            worktree=worktree,
            tape=tape,
            event_type=_ACCEPT_EVENT_TYPE,
        )

        # Record the predicate result on the Tape (OBSERVATION / PRESERVE).
        tape.append(
            _PREDICATE_EVALUATED,
            {
                "capsule_id": capsule["capsule_id"],
                "atom_id": exec_atom.get("atom_id"),
                "passed": bool(result.passed),
                "reason_digest": result.reason_digest,
            },
        )

        if result.passed:
            # PASS path: a SOVEREIGN_ACCEPT that advances accepted_head (predicate_pass=True).
            tape.append(
                _CANDIDATE_ACCEPTED,
                {
                    "capsule_id": capsule["capsule_id"],
                    "atom_id": exec_atom.get("atom_id"),
                    "tree_oid": tree_oid,
                    "reason_digest": result.reason_digest,
                },
                predicate_pass=True,
            )
            accepted += 1
        else:
            # FAIL path: failure-is-state. A FailureNode (OBSERVATION) lands on the Tape; tape_tip
            # advances, accepted_head does NOT. Then classify it so the shield injects the abstract
            # rule into the NEXT capsule (same module -> relevant).
            fn_payload = _failure_node_payload(exec_atom, result)
            tape.append(_FAILURE_NODE, fn_payload)
            failure_memory.classify(fn_payload)
            failed += 1

    # --- handoff + replay verification (S-7) ---------------------------------------------------
    bundle_dir = str(Path(scratch_root) / "handoff_bundle")
    handoff_bundle = replay.make_handoff_bundle(tape, bundle_dir)
    replay.verify_replay_equal(tape)

    return {
        "accepted": accepted,
        "failed": failed,
        "accepted_head": tape.accepted_head(),
        "tape_tip": tape.tape_tip(),
        "branches_covered": (accepted >= 1 and failed >= 1),
        "handoff_bundle": handoff_bundle,
    }


def run(spec: dict, tape) -> dict:
    """CLI adapter: `turingos loop` opens a Tape then calls this with (spec, tape).

    Delegates to run_loop against the tape's repo dir. The CLI's _open_tape may hand us a Tape
    whose dir does not yet exist as a Micro repo; run_loop calls Tape.init (idempotent) on it.
    """
    tape_dir = tape.repo_dir if hasattr(tape, "repo_dir") else str(tape)
    return run_loop(spec, tape_dir)
