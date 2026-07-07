# ADR-M2-001 - Machine Class for the TC Witness

```yaml
status: accepted-addressed
decision-makers:
  - Codex orchestrator
date: 2026-07-03
authority_level: 4
constitution_articles:
  - Art. 0.2 Tape Canonical
  - Art. 0.3 Auditability
evidence:
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/modules/MODULE_M2_tc_witness.md
    sha256: d9c0f93c47917f2fcc9b88ab2e0dd2f9118290ba63418aa008a328e1932fa631
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/research/RES_M2_turing_completeness_witness.md
    sha256: 1fa2c9c676c00e3f11c48cef4d98a1c55a1a888b77f3ffa4788afa9932a28713
  - path: /home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_verified_500_campaign_20260629/TURING_COMPLETENESS_PROOF_OBLIGATIONS_20260629.md
    sha256: 7be0980ee1a3ddf157f65096180c836341da548debcc93fe6957f355a7cf7cae
  - path: /home/zephryj/turingos_backup/work/turing/evidence/theory/turing_completeness_witness_20260703/programs/instruction_schema_registry.v1.json
    sha256: f905d003a043ef8500abc289635c4af898ac996451e9cc70ffbe2481dee3f5ac
status_ceiling: ADDRESSED
```

## Context

The frozen obligations file prescribes a two-counter Minsky-style witness with state `{program_counter, counter_a, counter_b, halted}`. RES_M2 records that general two-operand multiplication is not available with plain two-counter unary I/O without changing the model or using encoded I/O.

## Decision

Implement the witness around a two-counter Minsky machine for v1, with a generic interpreter core allowed internally. The tape-visible v1 state remains exactly `program_counter`, `counter_a`, `counter_b`, and `halted`. `multiply_small` means multiplication by a compile-time constant. General multiplication and universal-program demonstrations are deferred to explicitly labeled v2/stretch work.

## Consequences

TC0 freezes the v1 instruction registry and DECJZ semantics. Later claims must carry the Minsky/Godel-encoding caveat and must not claim general arithmetic expressiveness from the v1 examples alone.
