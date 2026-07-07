# ADR-M4-002 - H-VPPUT Cost Classes

```yaml
status: accepted-addressed
decision-makers:
  - Codex orchestrator
date: 2026-07-03
authority_level: 4
constitution_articles:
  - Art. 0.3 Auditability
evidence:
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/research/RES_M4_self_improvement_metrics.md
    sha256: a21178f2af435d7add39927abbe49b5b4825c24478c3eba2e1b358992c6ca2e8
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/modules/MODULE_M4_self_improvement.md
    sha256: 87a6262e63991c56daa22297aee3a42e0ededf08b2a0846356f371e5bf468e15
  - path: /home/zephryj/turingos_backup/work/turing/src/turingos/schemas.py
    sha256: b4e5708ac3014de681a666a25afd9d4836d4f860b4d0cd4ad54c65e80ab1c815
status_ceiling: ADDRESSED
```

## Context

Intent G5 permits billing-complete or explicitly bounded cost. The live hazard is incomplete or legacy cost data being laundered into a headline point estimate, especially existing `estimated_tokens` and `unspecified` provenance strings.

## Decision

Run class is computed mechanically from `cost_source_kind`. Runs with only `provider_receipt_inline` or `provider_usage_api_reconciled` events are BILLING_COMPLETE and may produce a point estimate. Runs with one or more well-formed `bounded_estimate` events and no unspecified, fixture-in-real, or non-enum events are BOUNDED and publish only a lower-bound H-VPPUT via upper-bound cost. All other runs are INADMISSIBLE and are excluded with explicit per-run rows. The class breakdown is mandatory in the report headline, and pre-M1c tapes are permanently inadmissible for H-VPPUT.

## Consequences

Mixed-class point estimates are unrepresentable in the report schema. Exclusions are visible and countable. Historical non-receipt numbers can appear only in a labeled legacy appendix outside H-VPPUT.
