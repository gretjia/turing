# External Auditor Prompt: Stage16R

Audit exact pushed SHA. Stage16R may claim only the frozen 20-task shard repair, not full SWE-bench.

Check:
1. Exactly seven repair bundles exist and match `bundle_sha256s.txt`.
2. The seven instance IDs exactly equal the Stage16 unsolved list.
3. Strict MicroTape audit PASS.
4. Each repair bundle imports Stage16 terminal failure evidence.
5. Each repair bundle has FailureCertificate -> BroadcastRuleActivated -> WorkCapsuleBuilt consuming rule.
6. Official PASS precedes CandidateAccepted.
7. Final PPUT progress=1 follows CandidateAccepted and counts all CostEvent tokens.
8. MarketSettled and RewardDistributed are terminal and preserve-only.
9. no-HITL counters are zero and fallback authorization is false.
10. `full_swe_bench_score_claim_allowed` remains false.
