# ADR-M2-006 - Non-Halting Evidence Taxonomy

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

The witness must include non-halting examples without implying that the system decides the halting problem.

## Decision

Non-halting evidence is classified as C1 static HALT-unreachability, C2 exact deterministic state recurrence, or C3 budget-bounded observation. C3 may only say the program did not halt within the recorded budget. State hashes exclude the step index so recurrence is mechanically checkable.

## Consequences

Every non-halting artifact must name its certificate class. Stronger language than the certificate supports is forbidden.
