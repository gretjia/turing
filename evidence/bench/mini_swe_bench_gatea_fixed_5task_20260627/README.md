# Gate A Fixed Mini SWE-bench Smoke — 5 Tasks

Date: 2026-06-27

This run repeats the Stage3 5-task stop set without scaling to 8/10/50. It applies the Gate A fixes:

- official evaluator evidence is imported to Micro Tape as `OfficialEvaluatorEvidenceImported`
- `candidate.verify_write` consumes that evidence before `CandidateAccepted`
- SWE-bench worker capsules and grants forbid benchmark/official test-file edits
- actual `visible_prompt.txt` bytes are sent through PPUT prompt shielding
- Stage3 failures are reduced into abstract BroadcastRules and injected into the next worker prompt
- Mini-Recovery reruns only the two failed TuringOS tasks and counts them as extra worker attempts

## Results

First pass:

- TuringOS + Grok: 3 / 5
- Direct Grok baseline: 4 / 5

Mini-Recovery:

- TuringOS recovery on failed tasks: 2 / 2

Final loop result:

- TuringOS + Grok loop: 5 / 5 across 7 worker attempts
- Direct Grok baseline: 4 / 5 across 5 worker attempts

This is a smoke result, not a statistically significant benchmark claim. The sample size is 5 and `loop_eval_summary.json` declares `none_smoke_only_n_equals_5_not_statistically_significant`.

## Evidence

- `turingos/substrate_coverage.json`
- `turingos/substrate_coverage_audit.json`
- `patch_eval/patch_eval_summary.json`
- `recovery/patch_eval/patch_eval_summary.json`
- `loop_eval_summary.json`
- `meta_ai_review_deepseek_v4_pro.json`
- `substrate_coverage_audit_with_meta.json`

MetaAI review:

- provider: DeepSeek
- model: `deepseek-v4-pro`
- authority: none
- accepted-head authority: false
- verdict: PASS

## Reproduce

Substrate coverage with MetaAI:

```bash
python3 tools/bench/audit_mini_swe_bench_substrate_coverage.py \
  --coverage evidence/bench/mini_swe_bench_gatea_fixed_5task_20260627/turingos/substrate_coverage.json \
  --out /tmp/gatea-substrate-audit-with-meta.json \
  --min-sample-size 5 \
  --worker-process grok_cli \
  --meta-ai-review evidence/bench/mini_swe_bench_gatea_fixed_5task_20260627/meta_ai_review_deepseek_v4_pro.json
```

Initial evaluator replay:

```bash
python3 tools/bench/evaluate_django_swe_bench_patches.py \
  --tasks-jsonl /tmp/turingos-swebench-data/verified-mini-50.jsonl \
  --limit 5 \
  --turingos-dir evidence/bench/mini_swe_bench_gatea_fixed_5task_20260627/turingos \
  --direct-dir evidence/bench/mini_swe_bench_stage3_5task_20260627/direct \
  --out /tmp/gatea-patch-eval-recheck \
  --work-root /tmp/turingos_django_patch_eval_gatea_recheck \
  --venv /tmp/turingos-django-swebench-venv \
  --substrate-coverage evidence/bench/mini_swe_bench_gatea_fixed_5task_20260627/turingos/substrate_coverage.json \
  --import-turingos-evidence \
  --daemon-bin-dir target/debug
```

Recovery evaluator replay:

```bash
python3 tools/bench/evaluate_django_swe_bench_patches.py \
  --tasks-jsonl evidence/bench/mini_swe_bench_gatea_fixed_5task_20260627/recovery/failed_2_tasks.jsonl \
  --limit 2 \
  --turingos-dir evidence/bench/mini_swe_bench_gatea_fixed_5task_20260627/recovery/turingos \
  --direct-dir evidence/bench/mini_swe_bench_stage3_5task_20260627/direct \
  --out /tmp/gatea-recovery-patch-eval-recheck \
  --work-root /tmp/turingos_django_patch_eval_gatea_recovery_recheck \
  --venv /tmp/turingos-django-swebench-venv \
  --substrate-coverage evidence/bench/mini_swe_bench_gatea_fixed_5task_20260627/recovery/turingos/substrate_coverage.json \
  --import-turingos-evidence \
  --daemon-bin-dir target/debug
```
