# ADR-M2-002 - Additive Registry Rows and Append Route

```yaml
status: accepted-addressed
decision-makers:
  - Codex orchestrator
date: 2026-07-03
authority_level: 4
constitution_articles:
  - Art. 0.2 Tape Canonical
  - Art. 0.4 Closed World Event Registry
evidence:
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/modules/MODULE_M2_tc_witness.md
    sha256: d9c0f93c47917f2fcc9b88ab2e0dd2f9118290ba63418aa008a328e1932fa631
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/research/RES_M2_turing_completeness_witness.md
    sha256: 1fa2c9c676c00e3f11c48cef4d98a1c55a1a888b77f3ffa4788afa9932a28713
  - path: /home/zephryj/turingos_backup/work/turing/evidence/theory/turing_completeness_witness_20260703/registry/additive_event_registry_rows_tc_witness_v1.json
    sha256: 2b71c8ca514ba3cc3bc0273a30c837603ff37ed9daf40bc6108b46e0d483fe87
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/governance/M2_TC0_EVENT_REGISTRY_SELF_CONSISTENCY_REPORT.md
    sha256: 87ae5582fd619be88a30ec9dbc14f6157bb71cf89b9c9e44fba86c68b31ba226
status_ceiling: ADDRESSED
```

## Context

The shared registry rejects unknown event names. The five TC witness events are not in the shared registry at TC0. The witness also needs one authorization-head ADVANCE event, which the legacy Python Tape writer cannot represent.

## Decision

Propose five additive rows with status `ADDITIVE_TC_WITNESS_V1`: `ComputationStarted`, `InstructionAuthorized`, `InstructionApplied`, `MachineStateObserved`, and `ComputationHalted`. `InstructionAuthorized` is the only AUTHORIZATION/ADVANCE row and targets `authorization_head`. Budget stops reuse the existing `BudgetExhausted` event. The TC witness emitter must append through the existing Rust three-ref append path rather than creating another canonical writer.

## Consequences

TC0 does not silently edit the shared registry. The M0-chain filing records that the current registry is self-consistent at 63 rows, and the proposed TC rows remain a separate artifact until accepted into the shared registry.
