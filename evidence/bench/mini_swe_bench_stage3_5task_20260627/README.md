# Stage 3 Mini SWE-bench Ramp — 5 Task Smoke

Date: 2026-06-27

This is the second scaled real-worker ramp. It expands from 3 to 5 tasks and uses the same paired protocol.

## Setup

- Tasks: first 5 rows from `/tmp/turingos-swebench-data/verified-mini-50.jsonl`
- Repos: all `django/django`
- Worker model: Grok CLI `grok-build`
- Turn budget: 50
- TuringOS arm: real daemon substrate with Micro Tape, market, PPUT, projections, predicate gate
- Direct arm: same Grok model and turn budget, no TuringOS substrate
- MetaAI: DeepSeek `deepseek-v4-pro`, real API call, no authority
- Patch evaluation: apply worker patch, apply SWE-bench `test_patch`, run `FAIL_TO_PASS` target tests

## Substrate Result

- TuringOS substrate coverage audit: `PASS`
- TuringOS substrate with MetaAI audit: `PASS`
- Scientific status: `SUBSTRATE_COVERAGE_READY_WITH_META_AI`
- Required modules M0-M17 all exercised across 5 real worker runs
- Required processes all exercised: `turingd`, `turing-execd`, `turing-mcp`, `turing-marketd`, `turing-pputd`, `turing-viewd`, `grok_cli`
- Candidate truth gate: all candidates stayed behind predicate as `FailureNode`; worker exit code and self-report did not move `accepted_head`

## Patch Evaluation

| Instance | TuringOS | Direct Grok | Notes |
| --- | --- | --- | --- |
| `django__django-11790` | FAIL | PASS | Regression versus Stage2; TuringOS patch failed target tests in this run. |
| `django__django-11815` | FAIL | FAIL | Both arms modified tests, causing official `test_patch` conflict. |
| `django__django-11848` | PASS | PASS | Both arms passed target tests. |
| `django__django-11880` | PASS | PASS | Both arms passed target tests. |
| `django__django-11885` | PASS | PASS | Both arms passed target tests; TuringOS worker exit was nonzero but patch passed. |

Aggregate:

- TuringOS: 3 / 5
- Direct Grok baseline: 4 / 5
- Statistical claim: none. This is still smoke scale, and TuringOS does not beat baseline in this round.

## Decision

Stop scaling at Stage3. Do not proceed to 8, 10, or 50 tasks until the TuringOS arm is fixed and rerun.

Reason: the Stage2 stop rule was triggered: TuringOS lost paired target-test performance.

## Failure Worklist

1. `django__django-11790`: TuringOS patch wrote `widget.attrs['maxlength'] = str(self.fields['username'].max_length)`, but the official target tests require integer `254` / `255`. Direct baseline wrote the integer value and passed.
2. `django__django-11815`: prevent workers from editing test files or classify test edits as overfit/invalid earlier.
3. Integrate official evaluator result as Micro Tape evidence before any `CandidateAccepted` path is enabled.
4. Add a worker stop contract so nonzero exit with a passing patch is classified explicitly instead of only inferred from logs.

## Reproduce Key Checks

```bash
python3 tools/bench/audit_mini_swe_bench_substrate_coverage.py \
  --coverage evidence/bench/mini_swe_bench_stage3_5task_20260627/turingos/substrate_coverage.json \
  --out /tmp/stage3-substrate-audit-with-meta.json \
  --min-sample-size 5 \
  --worker-process grok_cli \
  --meta-ai-review evidence/bench/mini_swe_bench_stage3_5task_20260627/meta_ai_review_deepseek_v4_pro.json
```

```bash
python3 tools/bench/evaluate_django_swe_bench_patches.py \
  --tasks-jsonl /tmp/turingos-swebench-data/verified-mini-50.jsonl \
  --limit 5 \
  --turingos-dir evidence/bench/mini_swe_bench_stage3_5task_20260627/turingos \
  --direct-dir evidence/bench/mini_swe_bench_stage3_5task_20260627/direct \
  --out /tmp/stage3-patch-eval-recheck \
  --work-root /tmp/turingos_django_patch_eval_stage3_recheck \
  --venv /tmp/turingos-django-swebench-venv
```

```bash
for bundle in evidence/bench/mini_swe_bench_stage3_5task_20260627/turingos/instances/*/micro_tape.bundle; do
  git bundle verify "$bundle"
done
```
