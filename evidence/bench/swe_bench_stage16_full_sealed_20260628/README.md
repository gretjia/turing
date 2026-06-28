# Stage16 Sealed Campaign Replay Packet

Artifact kind: `STAGE16_SHARD_SEALED_REPLAY`

Scope: sealed replay campaign over the frozen Stage12 20-task Verified Mini shard.

This is not a full SWE-bench score claim. `stage16_full_pass_claim_allowed` is `false` because `unsolved_count` is `7`.

Dataset boundary:
- not_full_swe_bench_dataset: true
- full_swe_bench_campaign_not_run: true
- full_score_claim_allowed: false
- next_required_stage: Stage16R

Results:
- run_count: 20
- solved_count: 13
- unsolved_count: 7
- stage16_replay_campaign_pass: True
- stage16_full_pass_claim_allowed: False

Reproduction commands:

```bash
python3 -m py_compile \
  tools/bench/audit_micro_tape_decision_dag.py \
  tools/bench/audit_stage16_sealed_campaign.py \
  tools/bench/build_stage16_sealed_campaign.py

pytest tests/test_stage16_sealed_campaign.py tests/test_micro_tape_decision_dag_audit.py -q

python3 tools/bench/audit_micro_tape_decision_dag.py \
  --strict-vpput \
  --strict-terminal-market \
  --require-authorization-head \
  --coverage evidence/bench/swe_bench_stage16_full_sealed_20260628/substrate_coverage.json \
  --out-dir /tmp/turingos_stage16_strict_verify

python3 tools/bench/audit_stage16_sealed_campaign.py \
  --root evidence/bench/swe_bench_stage16_full_sealed_20260628 \
  --out-dir /tmp/turingos_stage16_verify
```

Claim boundary:
- PASS means sealed replay campaign honesty and VPPUT/ref/market/no-HITL discipline.
- PASS does not mean full SWE-bench all-pass.
- Full-score claim is forbidden until `unsolved_count == 0`.
- Stage16R remains open for unsolved repair.
