# Phase F Internal Evaluator Replay Proof

Scope: TuringOS internal evaluator replay proof for the frozen Stage12 20-task shard after Stage16R.

This is not the upstream SWE-bench Docker evaluator, not a full SWE-bench dataset, not a full SWE-bench score claim, and not a leaderboard-equivalence claim.

The repo-local Django target-test runner is useful internal Macro evidence. It
does not release an official SWE-bench campaign. Official readiness still
requires `python -m swebench.harness.run_evaluation` evidence, Docker logs,
evaluation results, and both FAIL_TO_PASS and PASS_TO_PASS checks.

Result:
- status: PASS
- task_count: 20
- artifact_microtape_digest_binding: True
- official_evaluator_executable_replay: True
- phase_f_real_evaluator_proof_as_internal_replay: PASS
- phase_f_real_evaluator_proof_as_official_swebench: BLOCKED
- all_solved_tasks_have_reproducible_internal_replay: True
- all_candidate_accepts_have_required_evidence: True
- release_next_phase_g: False
- release_next_phase_g_as_internal_rehearsal: True
- release_next_phase_g_as_official_campaign: False
- full_swe_bench_score_claim_allowed: false
- full_dataset_claim_allowed: false

Known blockers:
- none

Reproduction commands:

```bash
python3 -m py_compile \
  tools/bench/audit_phase_f_evaluator_proof.py \
  tools/bench/build_phase_f_evaluator_proof.py \
  tools/bench/audit_micro_tape_decision_dag.py \
  tools/bench/audit_stage16r_repair.py

pytest \
  tests/test_phase_f_evaluator_proof.py \
  tests/test_stage16r_unsolved_repair.py \
  tests/test_stage16_sealed_campaign.py \
  tests/test_micro_tape_decision_dag_audit.py \
  -q

python3 tools/bench/audit_phase_f_evaluator_proof.py \
  --stage16-root evidence/bench/swe_bench_stage16_full_sealed_20260628 \
  --stage16r-root evidence/bench/swe_bench_stage16r_unsolved_repair_20260628 \
  --root evidence/bench/swe_bench_phase_f_evaluator_proof_20260628 \
  --out /tmp/turingos_phase_f_official_eval_replay_audit.json
```
