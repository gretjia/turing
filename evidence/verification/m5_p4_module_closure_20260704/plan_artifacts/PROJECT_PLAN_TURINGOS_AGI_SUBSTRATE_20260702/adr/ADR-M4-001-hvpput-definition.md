# ADR-M4-001 - H-VPPUT Operational Definition

```yaml
status: accepted-addressed
decision-makers:
  - Codex orchestrator
date: 2026-07-03
authority_level: 4
constitution_articles:
  - Art. 0.3 Auditability
  - Art. III.4 Hidden evaluator discipline
evidence:
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/research/RES_M4_self_improvement_metrics.md
    sha256: a21178f2af435d7add39927abbe49b5b4825c24478c3eba2e1b358992c6ca2e8
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/modules/MODULE_M4_self_improvement.md
    sha256: 87a6262e63991c56daa22297aee3a42e0ededf08b2a0846356f371e5bf468e15
  - path: /home/zephryj/turingos_backup/work/turing/docs/adr/ADR-PPUT-North-Star.md
    sha256: 92e6ed2229971c67ec302862fb14cb8d9330bb98773b0717b5a548ffb49ce977
status_ceiling: ADDRESSED
```

## Context

The accepted north-star ADR defines verified PPUT as progress divided by all counted cost and wall time, but audit finding F7 found the current denominator is word-count estimated and therefore not billing-grounded. The tape codec rejects floats, so the metric must be a recomputable analysis projection over integer tape inputs rather than a tape event.

## Decision

H-VPPUT uses money-denominated CostEvent.v2 receipts. For each task, cost is the sum of `computed_cost_microusd` across all receipts for that task, including failed attempts, and time is the sum of `wall_clock_ms`. A frozen stdlib-only script computes H-VPPUT from tape receipts, upstream harness outcomes, and the held-out registry only. It emits exact integer numerator and denominator pairs plus decimal strings in derived analysis JSON, never JSON floats and never tape bytes. Portfolio ratio-of-sums aggregates are the reported quantities; per-task ratios are audit table material only.

## Consequences

F7's measurability defect is closed only as an implementer-addressed measurement mechanism. FCE-B1 can recompute the metric byte-for-byte from the same inputs. M1c receipt provenance remains a hard dependency for real-input H-VPPUT.
