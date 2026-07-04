# ADR-M3-05 — Upstream SWE-bench Harness Is Sole Scorer

```yaml
status: accepted-addressed
decision-makers:
  - orchestrator
date: 2026-07-02
authority_level: 4
constitution_articles:
  - Art. 0.2 Tape Canonical
evidence:
  - path: /home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_official_harness_qualification_20260629/phase_f_20_run/evaluation_results.json
    sha256: 259c12e0d06cd9094d6fdc5fa3ddeb970a280989f347f90572a8a874c2b529b4
  - path: /home/zephryj/turingos_backup/work/TURINGOS_RETROSPECTIVE_AUDIT_FINDINGS_20260702.md
    sha256: c4eb450454b984af9c8f99cfb294e9a2fa536853f6f37c6237e3cc07c594eea7
status_ceiling: ADDRESSED
```

## Context

The repo-local evaluator produced a demonstrated false positive on `django__django-11885`. For this program, only the upstream `swebench==4.1.0` Docker harness can determine `resolved`.

## Decision

Use `python -m swebench.harness.run_evaluation` in the already-qualified configuration as the sole scorer. Pin dataset name plus content digest, Docker namespace, `--cache_level env`, `--timeout 1800`, and `--max_workers 2`. Each prediction is scored once. Rerun only `error_ids` and `incomplete_ids`, at most twice, with logged single-instance retry commands. Persistent harness errors are excluded pairwise across all arms. `resolved` and `unresolved` are never re-rolled.

## Consequences

Analysis inputs are official harness outputs only. Repo-local evaluators remain advisory and never feed the measurement.
