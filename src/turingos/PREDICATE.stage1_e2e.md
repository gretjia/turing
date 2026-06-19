# PREDICATE — Stage 1 E2E (the BOOT milestone) ship gate

**Goal (plan §6.2):** close the **entire** loop once, end-to-end, with a **fake/manual Worker** (deterministic
stub) — no real vendor adapter, no GitHub. Prove the *machine* is a complete, replayable, constitution-compatible
Turing loop before any external dependency. **A green Stage 1 = the BOOT milestone.**

**Depends on:** Foundation kernel shipped + loop modules (BOOT/PLANNER/CAPSULE+FailureMemory/WORKER+fake/
REDUCE+PANORAMA/EXPLORE+HumanSteer/SIGN) shipped.

## The loop driven (both predicate branches)
BOOT/ADOPT → GoalStateAccepted + ModulePlanAccepted (SOVEREIGN_ACCEPT) → progressive Atom expansion (active
module only) → Shielded Work Capsule built → dispatch to the fake Worker → candidate in an isolated worktree →
import Receipt → deterministic Predicate → **at least one `FailureNode`** (PRESERVE: tape_tip advances,
accepted_head does not) **AND at least one `CandidateAccepted`** (ADVANCE: accepted_head FF-advances) →
FailureClass → abstract rule → scoped re-injection into the next capsule → re-reduce WorkGraph → Panorama
updated → `HandoffGenerated` → fresh-process replay rebuilds the identical accepted state from the Tape alone.

## acceptance_commands (frozen — the gate)
```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'   # all unit tests green
PYTHONPATH=src python3 tests/integration/loop_e2e.py                  # the full-loop driver gate (below)
```

## Mechanical assertions (S-3 + S-4 + S-7 GATEs on the real loop)
1. **Loop completeness** — every sovereignty-boundary change lands as an event on the Tape; the run traverses
   BOTH predicate branches (≥1 FailureNode AND ≥1 CandidateAccepted).
2. **S-3 (predicate determinism + correctness)** — two evaluations on identical inputs → identical boolean +
   identical reason_digest; each negative case FAILs with the correct machine-readable reason and emits a
   FailureNode; PASS emits CandidateAccepted + advances accepted_head; **no quality/taste/UI** in the gate.
3. **S-4 (shield)** — raw failure → FailureClass → abstract rule → only the **relevant** rule injected into the
   next capsule (demonstrated against a history with ≥2 unrelated classes); NO raw private payload / worker
   stdout / unrelated rule leaks into the capsule; raw evidence stays on the Tape (reachable, not broadcast).
4. **S-7 (replay + handoff)** — two independent replays produce byte-identical accepted state, WorkGraph, q_t;
   deleting any projection/sqlite cache does not change the result (Tape-canonical); the HandoffGenerated bundle
   replays to the same state in a fresh process → ReplayVerified.
5. **Conservation** — `WorkGraph == derive(q_t, tape_t, declared Macro observations)` holds at every tick;
   `view == derive_from_tape(tape)` for the panorama projection.
6. **Authorized-vs-Accepted** — the panorama never renders an authorization (dispatch) as "accepted/done".
7. **Forbidden-pattern clean** — the 7 临时违宪 release-audit items all absent.

## On PASS
**FREEZE the 18-event registry count** (S-7 has now validated the first E2E loop — Stage-1 freeze rule).
Write `evidence/stage1/MANIFEST.sha256` + Shipgate-1 receipt. This is the milestone.
