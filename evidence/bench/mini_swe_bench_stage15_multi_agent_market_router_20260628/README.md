# Stage15 Multi-Agent Market Router Fixture

Stage15 qualifies the multi-route MarketRouter protocol surface. It is not a solve-rate claim and not a statistical benchmark.

Scope:
- one fresh MicroTape bundle;
- two route types: `deterministic_control` and `native_api_worker`;
- MarketRouter suggestions are shadow budget/dispatch suggestions only;
- MarketRouter route decisions are derived from replayed MicroTape events, not coverage metadata;
- price, market, reward, and PPUT events cannot move `accepted_head`;
- terminal reputation is derived from terminal `RewardDistributed` / terminal VPPUT only;
- all route branch costs are counted in final PPUT.

Evidence:
- `turingos/instances/django__django-11790/micro_tape.bundle`
- `bundle_sha256s.txt`
- `micro_tape_audit_strict/micro_tape_decision_dag_audit.json`
- `market_router_audit.json`
- `route_diversity_audit.json`
- `agent_reputation_audit.json`
- `price_not_truth_audit.json`
- `branch_cost_conservation_audit.json`

Result:
- strict MicroTape audit: PASS
- MarketRouter audit: PASS
- route diversity: PASS
- agent reputation terminal VPPUT basis: PASS
- price-not-truth: PASS
- branch cost conservation: PASS

Reproduction commands:

```bash
python3 -m py_compile \
  tools/bench/audit_micro_tape_decision_dag.py \
  tools/bench/audit_market_router.py \
  tools/bench/run_mini_swe_bench_substrate_smoke.py

pytest tests/test_stage15_market_router.py tests/test_micro_tape_decision_dag_audit.py -q

python3 tools/bench/audit_micro_tape_decision_dag.py \
  --strict-vpput \
  --strict-terminal-market \
  --require-authorization-head \
  --coverage evidence/bench/mini_swe_bench_stage15_multi_agent_market_router_20260628/turingos/substrate_coverage.json \
  --out-dir /tmp/turingos_stage15_strict_verify

python3 tools/bench/audit_market_router.py \
  --coverage evidence/bench/mini_swe_bench_stage15_multi_agent_market_router_20260628/turingos/substrate_coverage.json \
  --out-dir /tmp/turingos_stage15_market_verify

cargo test -p turing-contracts registry::tests --quiet
```

Claim boundary:
- This stage proves market/router accounting and authority discipline on a fresh fixture.
- This stage does not prove SWE-bench solve-rate improvement.
- This stage does not claim full SWE-bench score.
- This stage does not let market price or PPUT become predicate truth.
