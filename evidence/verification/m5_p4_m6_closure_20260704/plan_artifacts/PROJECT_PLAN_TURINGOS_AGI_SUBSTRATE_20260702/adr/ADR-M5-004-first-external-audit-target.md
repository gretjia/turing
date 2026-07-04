# ADR-M5-004 - First External Audit Target

```yaml
status: accepted-addressed
decision-makers:
  - Codex orchestrator
date: 2026-07-03
authority_level: 4
constitution_articles:
  - Art. 0.3 Auditability
  - Intent section 2 G6
evidence:
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/research/RES_M5_independent_verification.md
    sha256: 8893bd16ab7e881faf024b83c8ec11b4c552687fe8122f4bec1a967add79e869
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/modules/MODULE_M5_independent_verification.md
    sha256: 041a3bfd4875fcdf9dc200106bb14b4cd2e127c1c35ed3b8cde6d4580a096b43
status_ceiling: ADDRESSED
```

## Context

RES_M5 compares candidate first-audit roots. Stage12 is tainted by repo-local evaluator false-positive risk, while the upstream harness qualification root is the narrowest and best-evidenced existing packet candidate.

## Decision

M5.P3 packages `/home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_official_harness_qualification_20260629/` as the first external exact-SHA audit target. The packet adds the complete manifest the root lacks, offers digest-depth and full-replay-depth verification, and retains the historical `EXPECTED_VERDICT` block only under a compute-verdict-first runbook rule. Historical source roots are never edited.

## Consequences

The first audit targets the program's strongest narrow claim. A FAIL is a valid phase outcome that routes to repair and resubmission. G6 still requires an external PASS artifact before the module gate can satisfy the headline KPI.
