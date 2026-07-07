# Stage 2 Mini SWE-bench Ramp — 3 Task Smoke

Date: 2026-06-27

This is the first scaled real-worker ramp after the one-task smoke. It is not the full Mini SWE-bench run and does not support a statistically significant superiority claim.

## Setup

- Tasks: first 3 rows from `/tmp/turingos-swebench-data/verified-mini-50.jsonl`
- Repos: all `django/django`
- Worker model: Grok CLI `grok-build`
- Turn budget: 50
- TuringOS worker arm: real `turingd`, `turing-execd`, `turing-mcp`, `turing-marketd`, `turing-pputd`, `turing-viewd`
- MetaAI: DeepSeek `deepseek-v4-pro`, real API call, no authority
- Patch evaluation: apply worker patch, apply SWE-bench `test_patch`, run `FAIL_TO_PASS` target tests

## Substrate Result

- TuringOS substrate coverage audit: `PASS`
- TuringOS substrate with MetaAI audit: `PASS`
- Scientific status: `SUBSTRATE_COVERAGE_READY_WITH_META_AI`
- Required modules M0-M17 all exercised across 3 real worker runs
- Required processes all exercised: `turingd`, `turing-execd`, `turing-mcp`, `turing-marketd`, `turing-pputd`, `turing-viewd`, `grok_cli`
- Micro truth guard: all candidate writes stayed behind predicate gate as `FailureNode`; worker exit code and self-report did not move `accepted_head`

## Patch Evaluation

| Instance | TuringOS | Direct Grok | Notes |
| --- | --- | --- | --- |
| `django__django-11790` | PASS | FAIL | TuringOS target tests passed; direct patch failed target tests. |
| `django__django-11815` | FAIL | FAIL | Both arms modified tests, causing official `test_patch` conflict. |
| `django__django-11848` | PASS | PASS | Both arms passed target tests. |

Aggregate:

- TuringOS: 2 / 3
- Direct Grok baseline: 1 / 3
- Discordant pairs: TuringOS-only win = 1, Direct-only win = 0
- Statistical claim: none. This is a smoke ramp; n=3 is not statistically meaningful.

## MetaAI Review

DeepSeek `deepseek-v4-pro` review file:

- `meta_ai_review_deepseek_v4_pro.json`
- Status: `PASS`
- Review verdict: `PASS`
- Authority: `none`
- Credential material: `env_only_not_serialized`

Note: MetaAI says the evidence is meaningful, but it does not settle truth and does not authorize a significant-lead claim.

## Reproduce Key Checks

```bash
python3 tools/bench/audit_mini_swe_bench_substrate_coverage.py \
  --coverage evidence/bench/mini_swe_bench_stage2_3task_20260627/turingos/substrate_coverage.json \
  --out /tmp/stage2-substrate-audit-with-meta.json \
  --min-sample-size 3 \
  --worker-process grok_cli \
  --meta-ai-review evidence/bench/mini_swe_bench_stage2_3task_20260627/meta_ai_review_deepseek_v4_pro.json
```

```bash
python3 tools/bench/evaluate_django_swe_bench_patches.py \
  --tasks-jsonl /tmp/turingos-swebench-data/verified-mini-50.jsonl \
  --limit 3 \
  --turingos-dir evidence/bench/mini_swe_bench_stage2_3task_20260627/turingos \
  --direct-dir evidence/bench/mini_swe_bench_stage2_3task_20260627/direct \
  --out /tmp/stage2-patch-eval-recheck \
  --work-root /tmp/turingos_django_patch_eval_stage2_recheck \
  --venv /tmp/turingos-django-swebench-venv
```

Micro Tape bundles:

```bash
for bundle in evidence/bench/mini_swe_bench_stage2_3task_20260627/turingos/instances/*/micro_tape.bundle; do
  git bundle verify "$bundle"
done
```

## Next Ramp

Move to 5 or 8 tasks next. Keep the same paired protocol and stop if:

- substrate coverage drops below PASS,
- MetaAI does not run,
- patch evaluation has infrastructure ERROR,
- worker modifies tests repeatedly,
- TuringOS loses paired target-test performance.
