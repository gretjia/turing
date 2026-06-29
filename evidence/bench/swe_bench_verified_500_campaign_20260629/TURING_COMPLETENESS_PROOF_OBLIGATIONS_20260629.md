# Turing Completeness Proof Obligations - 2026-06-29

## Current Verdict

```text
turingos_can_claim_turing_complete_today: NO
turingos_has_replayable_loop_substrate_evidence: YES
formal_universal_computation_witness: REQUIRED
```

SWE-bench execution, even if successful, cannot prove Turing completeness. It
can prove compatibility with a software-engineering benchmark and the integrity
of TuringOS evidence/replay gates. Turing completeness is a mathematical claim
about expressiveness. It needs a construction proof.

## Required Construction

Use a minimal universal model, preferably a two-counter Minsky machine, because
it is small and easier to audit than an arbitrary programming language.

The proof must define:

```text
MachineState:
  program_counter
  counter_a
  counter_b
  halted

Instruction:
  INC counter -> next_pc
  DECJZ counter -> zero_pc | nonzero_pc
  HALT

MicroTape event sequence:
  ComputationStarted
  InstructionAuthorized
  InstructionApplied
  MachineStateObserved
  ComputationHalted
```

The reducer must reconstruct the current `MachineState` only from MicroTape
events. No projection, dashboard, test summary, or worker claim may be a source
of truth.

## Proof Gates

```text
TC-01 closed instruction schema registry
TC-02 each step event carries prev_state_hash and next_state_hash
TC-03 reducer replay equals reference interpreter for bounded programs
TC-04 branch behavior tested with zero and nonzero counters
TC-05 loop behavior tested with a terminating multiplication/addition program
TC-06 halt behavior tested and prevents further accepted machine-state advance
TC-07 tampered step event is rejected
TC-08 dropped event changes final state and is detected
TC-09 repeated replay from bundle reproduces identical final state
TC-10 independent recursive audit runs from clean clone
```

## Minimal Witness Programs

```text
copy_a_to_b
add_a_b
multiply_small
branch_zero_nonzero
known_halting_busy_loop_with_budget
```

The witness does not need to solve SWE-bench. Its role is to prove that the
TuringOS state/tape/reducer loop can represent unbounded discrete computation
subject to available time and budget.

## What Existing Evidence Already Supports

Existing Stage6 through Stage16R/Phase F evidence supports these prerequisites:

```text
MicroTape bundles can be externally discovered.
Git topology and ref reconstruction can be audited.
accepted_head and authorization_head are separable.
market/PPUT are preserve-only statistical/economic signals.
failure branches can remain on tape with progress=0.
worker-visible packets can be shielded from gold/test metadata.
official harness identity can be gated before campaign execution.
```

These are necessary engineering foundations. They are not sufficient for a
formal Turing-completeness claim.

## Next Loop

```text
Stage TC0: freeze schemas and claim boundary for computation witness.
Stage TC1: implement reference two-counter interpreter.
Stage TC2: implement MicroTape event emitter and reducer.
Stage TC3: run witness programs and export bundles.
Stage TC4: audit replay equivalence and tamper rejection.
Stage TC5: independent recursive audit from GitHub.
```

Only after TC4/TC5 can TuringOS make a scoped claim:

```text
TuringOS has a MicroTape-backed computation witness capable of simulating a
universal two-counter machine, subject to time and budget.
```
