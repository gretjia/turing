# ADR-M3-02 — Pre-Registered Four-Arm Experiment On S01

```yaml
status: accepted-addressed
decision-makers:
  - orchestrator
date: 2026-07-02
authority_level: 4
constitution_articles:
  - Art. 0.2 Tape Canonical
  - Art. III.4 Goodhart shielding
evidence:
  - path: /home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_verified_500_campaign_20260629/shards/S01/shard_manifest.json
    sha256: 68261be554042a3ca38454211d98014fc305b77ebff200414d9bb3d0e7c3a3ec
  - path: /home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_verified_500_campaign_20260629/dataset_descriptor.json
    sha256: 8dde6fef97ef978d5e973a6c3e75cd46f464b5681e85e6b8f7b86edeb269d1e2
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/m3_uplift_lab/PREREGISTRATION.md
    sha256: 0846e4d1e1f42e6e6374a39f73e7c2ced531441c4aa50ebdb3758a5b3d966f89
status_ceiling: ADDRESSED
```

## Context

R2 requires a controlled measurement of whether the substrate improves weak workers. S00 is old-policy-contaminated, and the Django-only Stage16 shard is not a valid generalization set. S01 is an untouched 50-task, 10-repo shard with only `shard_manifest.json` present.

## Decision

Use S01 as the confirmatory shard. Run four arms: A worker-alone, B full TuringOS loop, C B minus failure-memory injection, and D deterministic fake floor. Pre-register hypotheses, task order, budgets, roster, rerun rules, analysis code, and stop conditions before any worker call. Shared S01 task order is manifest order. Arm D runs first; any D solve stops the experiment for root cause.

## Consequences

The experiment measures a differential, not absolute capability. A null or negative result is still a valid measurement. S01 becomes spent for confirmatory use once frozen.
