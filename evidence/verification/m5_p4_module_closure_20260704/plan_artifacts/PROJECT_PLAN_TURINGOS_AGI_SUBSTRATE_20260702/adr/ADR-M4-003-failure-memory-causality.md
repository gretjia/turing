# ADR-M4-003 - Failure-Memory Causal Claim Discipline

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
  - path: /home/zephryj/turingos_backup/work/turing/tools/bench/audit_failure_memory_activation.py
    sha256: dfaa95a3733c7ed4291acc0b450177db7fc943d3d8c9a1e49a029138713b6b71
status_ceiling: ADDRESSED
```

## Context

The audit found lineage evidence for failure-memory mechanics but no causal evidence of efficacy. The repository's stage14 artifact already records that lineage-only observations do not allow causal claims, while M3 pre-registers the B-vs-C ablation contrast as the causal test.

## Decision

M4's confirmatory causal content is only a digest-pinned verbatim copy of M3's pre-registered H2 result. M4 performs no new confirmatory statistics. Mechanism analyses such as dose-response over consumed rules, memory-cost accounting, and lineage tables are allowed only when stamped `label: EXPLORATORY` and `causal_claim_allowed: false`. The sentence that failure memory causally improves solve probability is permitted only if M3 H2 passed in the positive direction.

## Consequences

The causal layer has no post-hoc analyst degrees of freedom. A null H2 result still yields a valid honest-null report. Exploratory artifacts can inform later budget design without contaminating confirmatory claims.
