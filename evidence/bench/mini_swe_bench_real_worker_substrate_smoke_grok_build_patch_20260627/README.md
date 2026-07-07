# Real Worker Substrate Smoke — 2026-06-27

This is a one-task, real-worker substrate smoke, not the 50-task Mini SWE-bench comparison.

## Result

- Task: `django__django-11790`
- Worker: Grok CLI, model `grok-build`
- Worker ID: `worker:sha256:2f5c5c807942e287608e0df621f02cab5f815cc2fe9770ca65bb48b45cce1137`
- Real patch produced: yes
- Coverage audit: `PASS`
- Substrate status without MetaAI: `SUBSTRATE_COVERAGE_READY`
- Substrate status with MetaAI: `SUBSTRATE_COVERAGE_READY_WITH_META_AI`
- MetaAI: DeepSeek `deepseek-v4-pro`, real API call, review verdict `WARN`
- Predicate write event: `FailureNode`
- `accepted_head` advanced by worker/exit code: no
- Direct Grok baseline on the same task also produced a passing target-test patch.

## Why Predicate Stayed Closed

The smoke deliberately keeps `candidate.verify_write` behind a failing predicate until the official evaluator result is imported as tape evidence. Grok output, exit code, local target tests, and benchmark labels are not accepted truth.

The current result is a substrate-lighting result, not a statistically meaningful benchmark result. It proves real worker + MetaAI + tape/economy/PPUT/projection can run on a SWE-bench task. It does not prove TuringOS significantly beats direct Grok baseline.

## Independent Verification Commands

```bash
python3 tools/bench/audit_mini_swe_bench_substrate_coverage.py \
  --coverage evidence/bench/mini_swe_bench_real_worker_substrate_smoke_grok_build_patch_20260627/substrate_coverage.json \
  --out /tmp/turingos-real-worker-substrate-audit-recheck.json \
  --min-sample-size 1 \
  --worker-process grok_cli
```

With MetaAI:

```bash
python3 tools/bench/audit_mini_swe_bench_substrate_coverage.py \
  --coverage evidence/bench/mini_swe_bench_real_worker_substrate_smoke_grok_build_patch_20260627/substrate_coverage.json \
  --out /tmp/turingos-real-worker-substrate-audit-with-meta-recheck.json \
  --min-sample-size 1 \
  --worker-process grok_cli \
  --meta-ai-review evidence/bench/mini_swe_bench_real_worker_substrate_smoke_grok_build_patch_20260627/meta_ai_review_deepseek_v4_pro.json
```

```bash
git bundle verify \
  evidence/bench/mini_swe_bench_real_worker_substrate_smoke_grok_build_patch_20260627/instances/django__django-11790/micro_tape.bundle
rm -rf /tmp/turingos-real-worker-micro-tape.git
git clone --mirror \
  evidence/bench/mini_swe_bench_real_worker_substrate_smoke_grok_build_patch_20260627/instances/django__django-11790/micro_tape.bundle \
  /tmp/turingos-real-worker-micro-tape.git
git --git-dir /tmp/turingos-real-worker-micro-tape.git fsck
```

Official-test local check performed in `/tmp/turingos-django-11790-eval`:

```bash
git clone --filter=blob:none --no-checkout https://github.com/django/django.git /tmp/turingos-django-11790-eval
git -C /tmp/turingos-django-11790-eval checkout b1d6b35e146aea83b171c1b921178bbaae2795ed
git -C /tmp/turingos-django-11790-eval apply \
  evidence/bench/mini_swe_bench_real_worker_substrate_smoke_grok_build_patch_20260627/instances/django__django-11790/worker_logs/diff.patch
# Apply the task's SWE-bench test_patch from /tmp/turingos-swebench-data/verified-mini-50.jsonl.
PYTHONPATH=/tmp/turingos-django-11790-eval \
  /tmp/turingos-django-11790-venv/bin/python \
  /tmp/turingos-django-11790-eval/tests/runtests.py \
  auth_tests.test_forms.AuthenticationFormTest.test_username_field_max_length_defaults_to_254 \
  auth_tests.test_forms.AuthenticationFormTest.test_username_field_max_length_matches_user_model \
  --verbosity 2
```

Observed output:

```text
Ran 2 tests in 0.018s
OK
```

## Artifacts

- `substrate_smoke_result.json`
- `substrate_coverage.json`
- `substrate_coverage_audit.json`
- `substrate_coverage_audit_with_meta.json`
- `meta_ai_review_deepseek_v4_pro.json`
- `official_eval_target_tests.json`
- `instances/django__django-11790/worker_logs/command.json`
- `instances/django__django-11790/worker_logs/diff.patch`
- `instances/django__django-11790/worker_logs/done.json`
- `instances/django__django-11790/micro_tape.bundle`
- `instances/django__django-11790/micro_tape_refs.txt`
- `instances/django__django-11790/project/.turingos/*_projection.json`
- `direct_baseline_django__django-11790/*`
