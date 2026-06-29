# Official SWE-bench Docker Harness Qualification

Current status: PASS.

The upstream SWE-bench Docker harness qualification packet is:

```text
evidence/bench/swe_bench_official_harness_qualification_20260629/
```

It records:

```text
official_harness_kind: upstream_swebench_docker
command: python -m swebench.harness.run_evaluation
single_instance_probe: PASS
phase_f_20_initial_replay: BLOCKED, 19/20
phase_f_11885_repair: PASS
phase_f_20_repaired_replay: PASS, 20/20
release_next_phase_g: true
```

External reference boundary:

- SWE-bench harness documentation describes the evaluator as Docker-based:
  https://www.swebench.com/SWE-bench/reference/harness/
- SWE-bench evaluation guide names `python -m swebench.harness.run_evaluation`
  as the main evaluation entrypoint:
  https://www.swebench.com/SWE-bench/guides/evaluation/
- SWE-bench `run_evaluation.py` is the upstream harness entrypoint:
  https://github.com/princeton-nlp/SWE-bench/blob/main/swebench/harness/run_evaluation.py
- OpenAI's SWE-bench Verified description says both FAIL_TO_PASS and
  PASS_TO_PASS tests are required to fully resolve an issue:
  https://openai.com/index/introducing-swe-bench-verified/

## Evidence Satisfied

The qualification packet contains:

- predictions JSONL with worker-derived unified diffs;
- exact `python -m swebench.harness.run_evaluation` command;
- SWE-bench package version;
- dataset name and split;
- Docker/raw harness logs archive digest;
- run_evaluation stdout/stderr digests;
- upstream `evaluation_results` path and digest;
- per-instance `FAIL_TO_PASS`, `PASS_TO_PASS`, and `resolved` results in the
  archived upstream harness reports;
- repaired `django__django-11885` worker-derived patch evidence;
- upstream repaired Phase F 20-task `evaluation_results` with 20/20 resolved.

## Required Auditor Predicate

`tools/bench/audit_full_swe_bench_readiness.py` must continue to block official
campaign launch unless Phase F reports:

```text
official_harness_kind == upstream_swebench_docker
upstream_swebench_official_docker_harness == true
official_harness_command contains python -m swebench.harness.run_evaluation
docker_required == true
docker_build_logs_present == true
evaluation_results_present == true
pass_to_pass_checked == true
fail_to_pass_checked == true
repo_local_evaluator_claim == false
```

## Forbidden Shortcuts

- Do not use the dataset gold patch as `model_patch`.
- Do not use official solution patches as candidate patches.
- Do not treat repo-local `tools/bench/evaluate_django_swe_bench_patches.py` as
  upstream SWE-bench official evaluation.
- Do not claim leaderboard equivalence from internal replay.
- Do not rewrite old Stage16/Stage16R/Phase F MicroTape bundles; supersede them
  with fresh evidence.
