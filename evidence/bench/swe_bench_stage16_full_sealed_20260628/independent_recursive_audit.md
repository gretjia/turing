# Stage16 Independent Recursive Audit

Verdict: PASS for scoped sealed replay campaign.

Release status: PASS

Stage16 replay campaign: PASS

Stage16 full-score claim: FORBIDDEN because `unsolved_count = 7` and `stage16_full_pass_claim_allowed = false`.

Key checks:
- all 20 listed bundles exist and SHA-256 values match `bundle_sha256s.txt`;
- strict MicroTape audit PASS, including VPPUT, market accounting, cost conservation, authorization head, accepted head authority, and failed/accepted progress gates;
- aggregate report reconstructs `run_count=20`, `solved_count=13`, `unsolved_count=7`, `problems=[]`;
- solved runs have official PASS before `CandidateAccepted` and final PPUT `progress=1`;
- unsolved runs have no `CandidateAccepted`, terminal failure path, and final PPUT `progress=0`;
- total CostEvent tokens independently reconstructed as `7880`, with final PPUT totals matching run costs;
- terminal official evidence / accept-or-failure precedes `MarketSettled`, which precedes `RewardDistributed`;
- no-HITL counters are zero and fallback is false;
- failure-memory lineage is present;
- scoped secret scan PASS; no obvious credential-shaped values found.

Commands reported by auditor:

```bash
python3 tools/bench/audit_stage16_sealed_campaign.py --root evidence/bench/swe_bench_stage16_full_sealed_20260628 --out-dir /tmp/turingos_stage16_audit_verify
python3 tools/bench/audit_micro_tape_decision_dag.py --strict-vpput --strict-terminal-market --require-authorization-head --coverage evidence/bench/swe_bench_stage16_full_sealed_20260628/substrate_coverage.json --out-dir /tmp/turingos_stage16_strict_verify
pytest tests/test_stage16_sealed_campaign.py tests/test_micro_tape_decision_dag_audit.py -q
```

Open risks:
- directory name contains `full`, but README/report correctly state this is not a full SWE-bench score claim;
- `stage16_market_audit.json` is terse; stronger evidence is in bundle-derived audit logic and strict MicroTape report.
