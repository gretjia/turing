# Mini SWE-bench Stage5 10-task Ramp

Date: 2026-06-27

Base code SHA before this ramp: `922bcab3f25e38c58d22af1a42994b0f244290f9`

This is a real-worker 8/10-task ramp for the TuringOS + Grok headless worker benchmark track. It is not a full SWE-bench Verified Mini claim and it is not statistically significant.

## Verdict

- Stage4 8-task gate: TuringOS `7/8`, direct Grok `5/8`.
- Stage5 10-task combined gate: TuringOS `9/10`, direct Grok `7/10`.
- Paired outcomes: both pass `7`, TuringOS-only `2`, direct-only `0`, both fail `1`.
- McNemar exact two-sided p-value recorded as `0.5`; this is smoke-scale directional evidence only.
- Stop condition: none for the 8/10 ramp.
- Next gate may expand only after preserving the same evidence import, prompt shielding, and MetaAI audit path.

## Incremental Tasks

The Stage5 incremental run used rows 9-10 from `/tmp/turingos-swebench-data/verified-mini-50.jsonl`:

- `django__django-12039`
- `django__django-12050`

Both arms used `grok-build`, max turns `50`, and real Grok CLI headless execution.

## Results

| Instance | TuringOS | Direct | Micro write | Pair |
| --- | --- | --- | --- | --- |
| `django__django-11790` | PASS | FAIL | CandidateAccepted | TuringOS-only |
| `django__django-11815` | PASS | FAIL | CandidateAccepted | TuringOS-only |
| `django__django-11848` | PASS | PASS | CandidateAccepted | Both pass |
| `django__django-11880` | PASS | PASS | CandidateAccepted | Both pass |
| `django__django-11885` | PASS | PASS | CandidateAccepted | Both pass |
| `django__django-11951` | PASS | PASS | CandidateAccepted | Both pass |
| `django__django-11964` | FAIL | FAIL | FailureNode | Both fail |
| `django__django-11999` | PASS | PASS | CandidateAccepted | Both pass |
| `django__django-12039` | PASS | PASS | CandidateAccepted | Both pass |
| `django__django-12050` | PASS | PASS | CandidateAccepted | Both pass |

## Substrate Coverage

For the incremental Stage5 TuringOS arm, the independent coverage auditor reports:

- verdict: `PASS`
- scientific status: `SUBSTRATE_COVERAGE_READY`
- modules M0-M17: all called for both incremental tasks
- processes: `turingd`, `turing-execd`, `turing-mcp`, `turing-marketd`, `turing-pputd`, `turing-viewd`, `grok_cli`

The raw coverage file records the pre-official-evidence predicate gate as `FailureNode`; the final predicate result after official evidence import is recorded in `patch_eval_incremental/patch_eval_summary.json` under `micro_tape_import`.

## MetaAI Review

DeepSeek MetaAI review:

- provider: `deepseek`
- model: `deepseek-v4-pro`
- status: `PASS`
- authority: `none`
- accepted_head_authority: `false`
- credential material: `env_only_not_serialized`
- review verdict: `PASS`

MetaAI review is advisory evidence only. It cannot move Micro heads and cannot settle truth.

## Reproduction Commands

Direct incremental arm:

```bash
python3 tools/bench/run_direct_grok_baseline_smoke.py \
  --tasks-jsonl evidence/bench/mini_swe_bench_stage5_10task_20260627/tasks_9_10.jsonl \
  --out-dir evidence/bench/mini_swe_bench_stage5_10task_20260627/direct_incremental \
  --limit 2 \
  --model grok-build \
  --max-turns 50 \
  --worker-timeout-s 1800 \
  --worktree-root /tmp/turingos_direct_grok_stage5_10task_incremental
```

TuringOS incremental arm:

```bash
python3 tools/bench/run_mini_swe_bench_substrate_smoke.py \
  --tasks-jsonl evidence/bench/mini_swe_bench_stage5_10task_20260627/tasks_9_10.jsonl \
  --out-dir evidence/bench/mini_swe_bench_stage5_10task_20260627/turingos_incremental \
  --limit 2 \
  --worker-mode grok \
  --model grok-build \
  --max-turns 50 \
  --worker-timeout-s 1800 \
  --broadcast-rules-file evidence/bench/mini_swe_bench_stage5_10task_20260627/combined_broadcast_rules.json
```

Official evaluator + Micro evidence import:

```bash
python3 tools/bench/evaluate_django_swe_bench_patches.py \
  --tasks-jsonl evidence/bench/mini_swe_bench_stage5_10task_20260627/tasks_9_10.jsonl \
  --limit 2 \
  --turingos-dir evidence/bench/mini_swe_bench_stage5_10task_20260627/turingos_incremental \
  --direct-dir evidence/bench/mini_swe_bench_stage5_10task_20260627/direct_incremental \
  --out evidence/bench/mini_swe_bench_stage5_10task_20260627/patch_eval_incremental \
  --work-root /tmp/turingos_django_patch_eval_stage5_10task_incremental \
  --venv /tmp/turingos-django-swebench-venv \
  --substrate-coverage evidence/bench/mini_swe_bench_stage5_10task_20260627/turingos_incremental/substrate_coverage.json \
  --import-turingos-evidence \
  --daemon-bin-dir target/debug
```

MetaAI review, with the key supplied only through the environment:

```bash
python3 tools/bench/run_deepseek_meta_review.py \
  --evidence-dir evidence/bench/mini_swe_bench_stage5_10task_20260627 \
  --out evidence/bench/mini_swe_bench_stage5_10task_20260627/meta_ai_review_deepseek_v4_pro.json \
  --timeout-s 180
```

Coverage audit with MetaAI:

```bash
python3 tools/bench/audit_mini_swe_bench_substrate_coverage.py \
  --coverage evidence/bench/mini_swe_bench_stage5_10task_20260627/turingos_incremental/substrate_coverage.json \
  --out evidence/bench/mini_swe_bench_stage5_10task_20260627/substrate_coverage_audit_with_meta.json \
  --min-sample-size 2 \
  --worker-process grok_cli \
  --meta-ai-review evidence/bench/mini_swe_bench_stage5_10task_20260627/meta_ai_review_deepseek_v4_pro.json
```

## Key Evidence Files

- `loop_eval_summary.json`
- `patch_eval_incremental/patch_eval_summary.json`
- `combined_broadcast_rules.json`
- `turingos_incremental/substrate_coverage.json`
- `turingos_incremental/substrate_coverage_audit.json`
- `substrate_coverage_audit_with_meta.json`
- `meta_ai_review_deepseek_v4_pro.json`
