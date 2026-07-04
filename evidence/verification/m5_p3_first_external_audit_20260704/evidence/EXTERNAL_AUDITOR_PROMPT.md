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
phase_f_20_initial_official_replay: BLOCKED, completed 20/20 but resolved 19/20
phase_f_11885_repair: PASS
phase_f_20_repaired_official_replay: PASS, completed 20/20 and resolved 20/20
release_next_phase_g: YES
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
- `phase_f_20_run/evaluation_results.json`
- `phase_f_20_run/phase_f_20_official_replay_audit.json`
- `phase_f_20_run/stdout.txt`
- `phase_f_20_run/stderr.txt`
- `phase_f_20_run/harness_logs_raw.tar.gz`
- `phase_f_11885_repair/candidate.patch`
- `phase_f_11885_repair/repair_audit.json`
- `phase_f_11885_repair/harness_logs_raw.tar.gz`
- `predictions_phase_f_20_repaired.jsonl`
- `phase_f_20_repaired_run/evaluation_results.json`
- `phase_f_20_repaired_run/phase_f_20_repaired_official_replay_audit.json`
- `phase_f_20_repaired_run/stdout.txt`
- `phase_f_20_repaired_run/stderr.txt`
- `phase_f_20_repaired_run/harness_logs_raw.tar.gz`
- `official_eval_replay_audit.json`

## Questions

1. Does the packet invoke upstream `python -m swebench.harness.run_evaluation`?
2. Is the dataset `princeton-nlp/SWE-bench_Verified`?
3. Is repo-local evaluator output forbidden as official evidence?
4. Are predictions worker-derived and free of dataset gold patch sources?
5. Did the single-instance probe run through upstream Docker harness?
6. Does the probe show patch application, FAIL_TO_PASS, PASS_TO_PASS, and resolved=true?
7. Is the probe explicitly marked not sufficient for Phase G release?
8. Does the packet preserve the initial 19/20 BLOCKED replay as historical evidence?
9. Are full-score and leaderboard-equivalence claims forbidden?
10. Are stdout/stderr/report/logs digest-bound?
11. Does `evaluation_results.json` show submitted=20, completed=20, errors=0, resolved=19, unresolved=1?
12. Is `django__django-11885` the only unresolved id?
13. Does the `django__django-11885` per-instance report show FAIL_TO_PASS success but PASS_TO_PASS failures?
14. Does `phase_f_11885_repair/repair_audit.json` show a worker-derived repair resolved `django__django-11885`?
15. Does `phase_f_20_repaired_run/evaluation_results.json` show submitted=20, completed=20, errors=0, resolved=20, unresolved=0?
16. Does `official_harness_qualification_audit.json` report PASS and `release_next_phase_g: true`?

## Required Next Action

Regenerate or audit the full readiness gate with this qualification root. If it
reports READY, the next loop is the 10-shard x 50-task official SWE-bench
Verified campaign. Do not claim a completed campaign, full score, or leaderboard
equivalence before final campaign gates pass.
