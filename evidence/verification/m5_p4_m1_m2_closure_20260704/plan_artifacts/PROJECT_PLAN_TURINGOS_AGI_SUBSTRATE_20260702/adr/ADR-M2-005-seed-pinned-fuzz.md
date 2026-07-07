# ADR-M2-005 - Seed-Pinned Fuzz Campaign

```yaml
status: accepted-addressed
decision-makers:
  - Codex orchestrator
date: 2026-07-03
authority_level: 4
constitution_articles:
  - Art. 0.3 Auditability
evidence:
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/modules/MODULE_M2_tc_witness.md
    sha256: d9c0f93c47917f2fcc9b88ab2e0dd2f9118290ba63418aa008a328e1932fa631
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/research/RES_M2_turing_completeness_witness.md
    sha256: 1fa2c9c676c00e3f11c48cef4d98a1c55a1a888b77f3ffa4788afa9932a28713
status_ceiling: ADDRESSED
```

## Context

The TC witness needs adversarial coverage beyond named examples while preserving replayability and dependency discipline.

## Decision

Gate evidence uses a stdlib `random.Random(seed)` generator with a recorded manifest containing generator version, seed, program count, maximum program length, and maximum step budget. Hypothesis or proptest may be used only as local bug-hunting aids and never as cited gate evidence.

## Consequences

TC3/TC4 fuzz evidence can be replayed byte-identically from its manifest. Shrinking databases and tool-specific hidden state are excluded from gate evidence.
