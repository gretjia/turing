# External Audit Prompt: Official SWE-bench Harness Qualification

Audit this evidence root:

`evidence/bench/swe_bench_official_harness_qualification_20260629/`

## Scope

This packet qualifies the upstream SWE-bench Docker harness path. It is not a
Phase G release packet and not a 500-task campaign result.

Current expected verdict:

```text
official_harness_module_installed: PASS
single_instance_upstream_probe: PASS
phase_f_20_official_replay: BLOCKED
release_next_phase_g: NO
full_score_claim: FORBIDDEN
leaderboard_equivalence_claim: FORBIDDEN
```

## Files To Inspect

- `official_harness_qualification.json`
- `official_harness_qualification_audit.json`
- `environment_preflight.json`
- `predictions_phase_f_20.jsonl`
- `harness/swebench_package_descriptor.json`
- `harness/run_evaluation_help.txt`
- `probe_django_11790/official_harness_probe_audit.json`
- `probe_django_11790/evaluation_summary.json`
- `probe_django_11790/per_instance_report.json`
- `probe_django_11790/harness_logs_raw.tar.gz`

## Questions

1. Does the packet invoke upstream `python -m swebench.harness.run_evaluation`?
2. Is the dataset `princeton-nlp/SWE-bench_Verified`?
3. Is repo-local evaluator output forbidden as official evidence?
4. Are predictions worker-derived and free of dataset gold patch sources?
5. Did the single-instance probe run through upstream Docker harness?
6. Does the probe show patch application, FAIL_TO_PASS, PASS_TO_PASS, and resolved=true?
7. Is the probe explicitly marked not sufficient for Phase G release?
8. Does the main qualification audit remain BLOCKED until full Phase F 20 official replay artifacts exist?
9. Are full-score and leaderboard-equivalence claims forbidden?
10. Are stdout/stderr/report/logs digest-bound?

## Required Next Action

Run the full Phase F 20-task upstream SWE-bench Docker replay and bind:

- official `evaluation_results`;
- stdout/stderr digests;
- Docker build/cache logs;
- per-instance reports;
- FAIL_TO_PASS and PASS_TO_PASS for every accepted task.

Only then may readiness be regenerated for official Phase G.
