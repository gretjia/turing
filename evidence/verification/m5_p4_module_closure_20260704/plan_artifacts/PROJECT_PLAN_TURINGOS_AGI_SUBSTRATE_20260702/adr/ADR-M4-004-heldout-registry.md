# ADR-M4-004 - Held-Out Registry

```yaml
status: accepted-addressed
decision-makers:
  - Codex orchestrator
date: 2026-07-03
authority_level: 4
constitution_articles:
  - Art. III.4 Hidden evaluator discipline
evidence:
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/research/RES_M4_self_improvement_metrics.md
    sha256: a21178f2af435d7add39927abbe49b5b4825c24478c3eba2e1b358992c6ca2e8
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/modules/MODULE_M4_self_improvement.md
    sha256: 87a6262e63991c56daa22297aee3a42e0ededf08b2a0846356f371e5bf468e15
  - path: /home/zephryj/turingos_backup/work/turing/tools/bench/audit_prompt_leakage.py
    sha256: f59a4e712640151395575c28d00c3c7e7cec34d9ed24b5021bcdc945d61dfd21
status_ceiling: ADDRESSED
```

## Context

Held-out measurement was previously aspirational. The loop contract and prompt shield provide primitives, but no artifact defined the measurement set. Worker visibility of held-out membership or metric internals would violate the hidden-evaluator boundary.

## Decision

`heldout_task_registry.v1.json` is the sole task-selection input to H-VPPUT. It is generated from M3's frozen S01 shard manifest, embeds that manifest's sha256, and lives outside every worker-visible tree. The metric script hard-fails on any out-of-registry receipt. Leakage sweeps add `hvpput` and the registry filename to the existing `pput`, `vpput`, and `heldout` marker set.

## Consequences

FCE-B1 can assert both recomputation from the registry and lack of worker-visible registry path. Pilot and non-S01 contamination become structural failures, not reviewer judgment calls.
