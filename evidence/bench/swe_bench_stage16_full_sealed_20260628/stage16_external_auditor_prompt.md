# External Auditor Prompt: Stage16

Audit the exact pushed GitHub SHA. Do not trust local summaries.

Evidence root: `evidence/bench/swe_bench_stage16_full_sealed_20260628/`

Required files:
- `evidence/bench/swe_bench_stage16_full_sealed_20260628/bundle_manifest.json`
- `evidence/bench/swe_bench_stage16_full_sealed_20260628/micro_tape_audit_strict/micro_tape_decision_dag_audit.json`
- `stage16_aggregate_report.json`
- `stage16_vpput_report.json`
- `stage16_replay_audit.json`
- `stage16_market_audit.json`
- `stage16_failure_memory_audit.json`
- `stage16_no_hitl_audit.json`
- `stage16_secret_scan_summary.txt`

Questions:
1. Can every listed `micro_tape.bundle` be fetched from GitHub and does its SHA-256 match `bundle_sha256s.txt`?
2. Does strict MicroTape audit PASS?
3. Does `stage16_aggregate_report.json` reconstruct solved/unsolved only from bundles?
4. Are solved instances exactly official PASS -> CandidateAccepted -> final PPUT progress=1?
5. Are unsolved instances exactly no CandidateAccepted -> terminal failure/budget -> final PPUT progress=0?
6. Does all cost come from CostEvent totals and final PPUT totals?
7. Are market settlement/reward terminal and non-sovereign?
8. Are no-HITL counters zero?
9. Is `stage16_full_pass_claim_allowed` false when unsolved_count > 0?
10. Does README avoid any full-score/all-pass claim?

Required verdict:
```text
stage16_replay_campaign: PASS|PARTIAL|FAIL
stage16_full_score_claim: ALLOWED|FORBIDDEN|OVERCLAIM
release_status: PASS|PARTIAL|FAIL|OVERCLAIM
```
