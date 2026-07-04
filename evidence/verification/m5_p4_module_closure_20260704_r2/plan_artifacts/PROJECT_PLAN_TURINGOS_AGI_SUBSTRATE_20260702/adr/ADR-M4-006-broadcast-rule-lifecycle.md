# ADR-M4-006 - Broadcast-Rule Lifecycle and Retirement Proposal

```yaml
status: accepted-addressed
decision-makers:
  - Codex orchestrator
date: 2026-07-03
authority_level: 4
constitution_articles:
  - Art. II.1 Abstract broadcast discipline
  - Art. 0.3 Auditability
evidence:
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/research/RES_M4_self_improvement_metrics.md
    sha256: a21178f2af435d7add39927abbe49b5b4825c24478c3eba2e1b358992c6ca2e8
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/modules/MODULE_M4_self_improvement.md
    sha256: 87a6262e63991c56daa22297aee3a42e0ededf08b2a0846356f371e5bf468e15
  - path: /home/zephryj/turingos_backup/work/turing/tools/bench/audit_failure_taxonomy.py
    sha256: 6590f6fb6a4348b4d78880cf119bd28fd7b9b731e27b0e8f1774ec9c62f8f7ad
  - path: /home/zephryj/turingos_backup/work/turing/tools/bench/run_mini_swe_bench_substrate_smoke.py
    sha256: f4848a6a83ef55b6dbcfb49099613be155419c883033024f54fcc659daf9c9b8
status_ceiling: ADDRESSED
```

## Context

Five broadcast-rule lifecycle stages already exist on tape: failure-node mining, preserve-only certificates, cluster-gated activation, capsule consumption, and leakage-denylist enforcement. No retirement or deactivation mechanism exists, so the active set can only grow, creating Art. II.1 context-pollution and cost-inflation hazards.

## Decision

M4 adopts the Stage10 denylist plus attestation and recursive string sweep pattern for every rule surface it audits, extended with `hvpput` and the registry filename. Activation remains cluster-gated from same-class failures. M4 proposes, but does not land, a supervisor-side append-only `BroadcastRuleRetired` event with `rule_id`, reason enum, `evidence_ref`, and an active-set filter in `read_broadcast_rules`; M1 remains the schema owner. Retirement decisions may cite only EXPLORATORY artifacts because pruning is operational, not causal inference.

## Consequences

The lifecycle becomes replayable including exit once M1 accepts the schema addition. Per-stage claim ceilings keep lineage-proven protocol language separate from H2-gated efficacy language. M4 remains a read-side consumer and proposal author, not a tape schema writer.
