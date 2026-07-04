# ADR-M4-005 - Honest-Null Reporting Freeze

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
  - path: /home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_verified_500_campaign_20260629/CLAIM_BOUNDARY.json
    sha256: a9f969c11802d3b851dc2c105c6fe0abc4fdb4662019a9b7e27d13e63cf36ead
status_ceiling: ADDRESSED
```

## Context

The strongest M4 drift temptation is choosing metric presentation or claim phrasing after seeing results. FCE-B1 explicitly treats a null phrased as "no effect" as a failure.

## Decision

The north-star report skeleton is frozen with the metric script before any M3 output is read. The skeleton includes the headline class breakdown, per-arm portfolio H-VPPUT or bounds, Delta_BC with confidence interval, the MDE statement verbatim from pre-registration, the three mandatory direction templates, the claim-boundary JSON fields, and always-present exclusion and deviation tables. The assembled report must diff-conform to that skeleton regardless of direction.

## Consequences

Outcome direction cannot change report shape. An honest null is a first-class publishable outcome. Verifiers can mechanically check conformance instead of relying on narrative intent.
