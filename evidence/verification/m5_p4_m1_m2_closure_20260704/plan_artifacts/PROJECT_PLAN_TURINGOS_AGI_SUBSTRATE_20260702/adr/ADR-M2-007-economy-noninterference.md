# ADR-M2-007 - Economy Non-Interference Gate

```yaml
status: accepted-addressed
decision-makers:
  - Codex orchestrator
date: 2026-07-03
authority_level: 4
constitution_articles:
  - Art. 0.3 Auditability
  - Art. III.4 Goodhart shielding
evidence:
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/modules/MODULE_M2_tc_witness.md
    sha256: d9c0f93c47917f2fcc9b88ab2e0dd2f9118290ba63418aa008a328e1932fa631
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/research/RES_M2_turing_completeness_witness.md
    sha256: 1fa2c9c676c00e3f11c48cef4d98a1c55a1a888b77f3ffa4788afa9932a28713
status_ceiling: ADDRESSED
```

## Context

G3 requires that market, PPUT, and HCI surfaces cannot affect computation transitions. A prose assertion would be too weak.

## Decision

TC4 must include three checks: interleave-invariance with legal PRESERVE economy events, a sabotage reducer that proves the test is non-vacuous, and a static read-surface lint that the witness reducer consumes only TC witness events plus `BudgetExhausted`.

## Consequences

The witness reducer cannot consult market, PPUT, or HCI events for state transitions. Any non-interference survivor is a gate failure and must remain in evidence.
