# ADR-M4-007 - Provider Receipt Binding

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
  - path: /home/zephryj/turingos_backup/work/turing/tools/bench/run_mini_swe_bench_substrate_smoke.py
    sha256: f4848a6a83ef55b6dbcfb49099613be155419c883033024f54fcc659daf9c9b8
status_ceiling: ADDRESSED
```

## Context

The candidate providers expose per-call inline usage, while org-level usage or cost APIs are admin-key, plan, or provider dependent. BILLING_COMPLETE therefore cannot depend on unavailable organization APIs. ADR-M1-004 owns the CostEvent.v2 schema; this record binds only M4's read-side verification.

## Decision

`provider_receipt_inline` requires the complete provider-specific usage field set, a non-empty reported model, a non-empty provider request id, request and response digests, and the pinned price-table digest. Missing elements must be downgraded at write time; if M4 sees a mislabeled inline event, the metric script hard-fails. `provider_usage_api_reconciled` may be assigned only by a post-hoc pass that cites the Layer-2 bucket reference and tolerance, never rescuing an inadmissible run. Costing is deterministic ceiling arithmetic per provider, model, and token class against the pinned integer price table. Streaming is forbidden in measured arms unless usage is guaranteed.

## Consequences

BILLING_COMPLETE is reachable from response bodies alone. Recomputed costs are byte-identical and never undercounted. DeepSeek cache economics and Anthropic cache classes remain token-class-specific. This ADR is subordinated to ADR-M1-004 for tape schema authority.
