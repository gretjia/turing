# ADR-M3-03 — Statistical Analysis Plan

```yaml
status: accepted-addressed
decision-makers:
  - orchestrator
date: 2026-07-02
authority_level: 4
constitution_articles:
  - Art. 0.2 Tape Canonical
evidence:
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/research/RES_M3_worker_uplift_laboratory.md
    sha256: b88c5298ee8733caa4959dca336dd320f65eaaf19351ccffd00653576118e8b6
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/m3_uplift_lab/analysis/analyze_uplift.py
    sha256: 8abd1b2c902bf100913e0c6e950988d2e06046607cb055f46d79de9e7d5462ec
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/m3_uplift_lab/analysis/dryrun_fixture/out/UPLIFT_REPORT.json
    sha256: 08d139b58e43225c6f26371ddd7098ebc6e16646ce7507b856f87bfd24a850b4
status_ceiling: ADDRESSED
```

## Context

The outcome is paired binary resolution on the same tasks. Unpaired solve-rate tests throw away pairing and inflate degrees of freedom. With n=50 per worker, small effects are underpowered, so the pre-registration must publish MDE and confidence intervals rather than imply that a null means no effect.

## Decision

Confirmatory tests are H1: B > A and H2: B > C. Use exact McNemar on pooled worker-task pairs with Holm ordering H1 then H2. Report effect sizes as delta with 10,000-replicate cluster-by-task bootstrap 95% CIs and an MDE statement. Arm D is a manipulation check, not a hypothesis. Per-worker, difficulty-stratified, and cost-normalized tables are exploratory.

## Consequences

The final report can be re-run from harness outputs using the frozen stdlib analysis script. "TuringOS improves workers" remains forbidden unless H1 is positive and significant under the pre-registered rule.
