# Official SWE-bench Docker Harness Qualification

Current status: REQUIRED NEXT ACTION.

The current Phase F packet proves TuringOS internal target-test replay. It does
not prove upstream SWE-bench official Docker evaluation. Official campaign
launch remains blocked by:

```text
upstream_swebench_docker_harness_required
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

## Required Evidence

Before `phase_g_official_campaign_launch` can become true, create a fresh
qualification packet that contains:

- predictions JSONL with worker-derived unified diffs;
- exact `python -m swebench.harness.run_evaluation` command;
- SWE-bench package version or upstream harness commit;
- dataset name, split, repo SHA, and parquet SHA-256;
- Docker image id/digest;
- Docker build logs digest;
- run_evaluation stdout/stderr digests;
- upstream `evaluation_results` path and digest;
- per-instance `FAIL_TO_PASS` result;
- per-instance `PASS_TO_PASS` result;
- per-instance `resolved: true|false`;
- MicroTape `OfficialEvaluatorEvidenceImported` events referencing those
  evidence descriptors;
- `CandidateAccepted` only when upstream `resolved == true`.

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
