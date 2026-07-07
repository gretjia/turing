# Phase F Repair Loop

Scope: repair-loop decision packet for Phase F evaluator proof.

This packet does not rewrite Stage16R or claim full SWE-bench status. It records that Phase F cannot release Phase G until the Stage16R repair artifacts are superseded by worker-derived unified diffs and executable official evaluator logs.

Result:
- status: BLOCKED
- repair_target_count: 7
- replayable_repair_bundle_count: 0
- release_next_phase_g: False
- full_swe_bench_score_claim_allowed: false
- full_dataset_claim_allowed: false
- leaderboard_equivalence_claim_allowed: false

Repair targets:
- django__django-11790
- django__django-11815
- django__django-11964
- django__django-12209
- django__django-12273
- django__django-12308
- django__django-12325

Blockers:
- existing_stage16r_microtape_hashes_bind_non_replayable_fixture_text
- old_tape_cannot_be_rewritten_without_violating_immutable_evidence_boundary
- fresh worker-derived unified diffs and official evaluator logs are required

Acceptance commands:

```bash
python3 -m py_compile \
  tools/bench/audit_phase_f_repair_loop.py \
  tools/bench/build_phase_f_repair_loop.py \
  tools/bench/audit_phase_f_evaluator_proof.py

pytest \
  tests/test_phase_f_repair_loop.py \
  tests/test_phase_f_evaluator_proof.py \
  -q

python3 tools/bench/audit_phase_f_repair_loop.py \
  --phase-f-root evidence/bench/swe_bench_phase_f_evaluator_proof_20260628 \
  --root evidence/bench/swe_bench_phase_f_repair_loop_20260628 \
  --out /tmp/turingos_phase_f_repair_loop_audit.json
```
