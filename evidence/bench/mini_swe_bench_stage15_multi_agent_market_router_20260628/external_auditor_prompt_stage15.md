# External Auditor Prompt: Stage15

Audit exact GitHub SHA after push. Do not audit local claims or summaries as truth.

Scope:
- `tools/bench/audit_market_router.py`
- `tools/bench/run_mini_swe_bench_substrate_smoke.py`
- `tests/test_stage15_market_router.py`
- `evidence/bench/mini_swe_bench_stage15_multi_agent_market_router_20260628/`

Questions:
1. Can the fresh `micro_tape.bundle` be fetched from GitHub and verified with `git bundle verify` / `git fsck --strict` through the project auditor?
2. Does strict MicroTape audit report PASS for all required fields?
3. Does MarketRouter choose between at least two routes from replayed MicroTape events rather than coverage metadata?
4. Is `MarketPriceBroadcast` preserve-only, non-authoritative, and price-not-truth acknowledged?
5. Do market/reward/PPUT events avoid moving `accepted_head`?
6. Are terminal `MarketSettled` and `RewardDistributed` ordered after terminal official evidence / `CandidateAccepted`?
7. Is route diversity enforced with numeric floor/cap policy?
8. Does terminal reputation consume terminal VPPUT only?
9. Are all route branch costs counted in final `PPUTAccounted`?
10. Are there any secrets, credential-shaped values, hidden predicates, raw failure logs, PPUT formula details, heldout labels, or official solution hints in visible evidence?

Required verdict shape:

```text
Stage15 strict MicroTape: PASS|PARTIAL|FAIL
MarketRouter shadow mode: PASS|PARTIAL|FAIL
Price-not-truth: PASS|PARTIAL|FAIL
Route diversity: PASS|PARTIAL|FAIL
Reputation terminal VPPUT basis: PASS|PARTIAL|FAIL
Branch cost conservation: PASS|PARTIAL|FAIL
Release to Stage16: YES|NO
```

Claim boundary:
Stage15 may pass as a market-router protocol fixture. It must not be interpreted as a solve-rate, full-SWE-bench, or product capability claim.
