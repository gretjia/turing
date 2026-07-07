# Mini SWE-bench Full-Run Readiness Evidence

Date: 2026-06-27

Verdict: `BLOCKED_DO_NOT_RUN_FULL_COMPARISON_YET`

The 50-task scientific plan gate passes, but the TuringOS substrate coverage gate fails.
A full model run at this point would measure a Grok prompt wrapper, not the complete
TuringOS Agent Economy Runtime substrate.

Artifacts:

- `verified-mini-50-plan.json`: paired 50-task dry-run plan.
- `verified-mini-50-plan-audit.json`: clean auditor result for the scientific plan.
- `verified-mini-50-substrate-coverage.json`: current runner substrate coverage matrix.
- `verified-mini-50-substrate-coverage-audit.json`: independent coverage audit result.

Key results:

- Plan audit: `PASS`, `READY_FOR_REAL_BENCHMARK`, 50 paired tasks.
- Substrate coverage audit: `FAIL`, `SUBSTRATE_COVERAGE_BLOCKED`.
- Current TuringOS arm coverage only reaches plan/capsule/worker prompt and Grok CLI.
- Missing coverage includes Micro Tape, turingd, turing-execd, turing-mcp,
  turing-marketd, turing-pputd, turing-viewd, predicate gate, market replay,
  PPUT accounting, projection rebuild, and candidate accept/reject truth gate.

Supervision decision:

Do not launch the full 50-task benchmark until the TuringOS arm emits coverage proving the
real path:

`GoalStateProposed -> WorkCapsuleBuilt -> MarketCreated/BudgetAllocated -> WorkerReceiptImported -> MacroObservationImported -> CandidateAccepted or FailureNode -> MarketSettled -> PPUTAccounted -> ReplayVerified`

and calls the required daemon/process roles in the TuringOS arm.
