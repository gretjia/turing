# Phase F Evaluator Proof

Scope: evaluator-artifact proof for the frozen Stage12 20-task shard after Stage16R.

This is not a full SWE-bench dataset, not a full SWE-bench score claim, and not a leaderboard-equivalence claim.

Result:
- status: PARTIAL
- task_count: 20
- artifact_microtape_digest_binding: True
- official_evaluator_executable_replay: False
- all_solved_tasks_have_reproducible_official_eval: False
- all_candidate_accepts_have_required_evidence: True
- release_next_phase_g: False
- full_swe_bench_score_claim_allowed: false
- full_dataset_claim_allowed: false

Known blockers:
- django__django-11790: Stage16R candidate artifact is digest-bound but not a replayable unified diff
- django__django-11790: Stage16R test patch artifact is digest-bound but not a replayable unified diff
- django__django-11815: Stage16R candidate artifact is digest-bound but not a replayable unified diff
- django__django-11815: Stage16R test patch artifact is digest-bound but not a replayable unified diff
- django__django-11964: Stage16R candidate artifact is digest-bound but not a replayable unified diff
- django__django-11964: Stage16R test patch artifact is digest-bound but not a replayable unified diff
- django__django-12209: Stage16R candidate artifact is digest-bound but not a replayable unified diff
- django__django-12209: Stage16R test patch artifact is digest-bound but not a replayable unified diff
- django__django-12273: Stage16R candidate artifact is digest-bound but not a replayable unified diff
- django__django-12273: Stage16R test patch artifact is digest-bound but not a replayable unified diff
- django__django-12308: Stage16R candidate artifact is digest-bound but not a replayable unified diff
- django__django-12308: Stage16R test patch artifact is digest-bound but not a replayable unified diff
- django__django-12325: Stage16R candidate artifact is digest-bound but not a replayable unified diff
- django__django-12325: Stage16R test patch artifact is digest-bound but not a replayable unified diff

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
