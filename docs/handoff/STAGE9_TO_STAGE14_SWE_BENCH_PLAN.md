# Stage9-Stage14 SWE-bench Execution Plan

Status: proposed execution plan after Stage8 strict no-HITL loop fixture.

Scope guard:
- This plan does not claim TuringOS is closed, M2-enabled, or solve-rate complete.
- MicroTape remains the source of truth.
- Python benchmark tooling may orchestrate and collect evidence, but it must not own accepted truth.
- Every stage must ship with fresh MicroTape bundles and an external-auditable replay path.

## Stage9 — Native API Worker

Goal: replace blackbox CLI-only worker governance with tool-level whitebox receipts for SWE-bench-shaped repair attempts.

Required tools:
- `read_file`
- `list_dir`
- `grep`
- `apply_patch`
- `write_file`
- `run_command`

Acceptance:
- Every successful tool call appends `ToolCallReceipt` or the current registry-compatible receipt event.
- Every denied tool call appends `ToolCallDenied` or `FailureNode` when terminal.
- Every attempted tool call, including executed-but-failed calls, appends a registry-compatible receipt with status, exit/error class, stdout/stderr digests where applicable, and cost accounting.
- Examples that must be receipted: `run_command` nonzero, `grep` no match, `apply_patch` conflict, `write_file` I/O failure, path-scope denial, timeout.
- `CostEvent` includes prompt/completion/tool/tool-stdout cost.
- `WorkerReceiptImported` is assembled from tool receipts, not raw self-report.
- Terminal failed attempts append `FailureNode(progress=0)` and never move `accepted_head`.
- Forbidden test-file mutation is rejected before official evaluator acceptance.
- Strict MicroTape audit remains PASS.
- Worker-visible prompts and capsules pass the no-PPUT/no-heldout/no-hidden-predicate leakage scan.

Minimum deliverable:
- A deterministic Native API Worker fixture that performs at least four tool calls and produces one terminal accepted path.
- A failing fixture where a denied tool call produces `FailureNode(progress=0)`.
- Evidence directory: `evidence/bench/mini_swe_bench_stage9_native_api_worker_YYYYMMDD/`.

## Stage10 — Failure Taxonomy Expansion

Goal: turn SWE-bench failures into actionable RCA classes that can generate safe abstract repair guidance.

Initial taxonomy:
- `INSTALL_FAIL`
- `TEST_TIMEOUT`
- `WRONG_FILE`
- `NO_REPRO`
- `OVERBROAD_PATCH`
- `SEMANTIC_FAIL`
- `FLAKY_ORACLE`
- `DEPENDENCY_GAP`
- `CONTEXT_MISSING`
- `PATCH_APPLIES_BUT_WRONG`

Acceptance:
- Every failed attempt gets a `FailureNode` with one taxonomy class or `UNKNOWN`.
- Every classified terminal failure can produce a preserve-only/private `BroadcastRule` candidate.
- `BroadcastRuleActivated` is separate from candidate generation and only happens after predicate-gated acceptance, because it is a sovereign accepted event in the current registry.
- Raw logs remain private evidence; visible capsules receive abstract guidance only.
- Failure-memory audit proves source `FailureNode`, later capsule consumption, raw-log redaction, and hidden-predicate absence from MicroTape.
- Worker-visible prompts and capsules pass the no-PPUT/no-heldout/no-hidden-predicate leakage scan.

Minimum deliverable:
- Classification fixtures for each class.
- At least one real SWE-bench-shaped failure imported through official evaluator evidence.

## Stage11 — Loop-Until-PASS Runner

Goal: run repeated attempts for an instance until `CandidateAccepted` or budget exhaustion.

Loop shape:
1. build capsule;
2. run Native API Worker or external worker;
3. import official evaluator evidence;
4. append `FailureNode(progress=0)` or `CandidateAccepted`;
5. compress failure into abstract rule;
6. authorize retry;
7. rebuild capsule with consumed rule;
8. halt only on accept or budget exhaustion.

Acceptance:
- `human_interventions_by_class=0` for normal P2/P3 benchmark tasks.
- All failed branches have `Progress_i=0`.
- Accepted final PPUT has `progress=1` after terminal `CandidateAccepted`.
- Budget exhaustion is terminal, replayable, and does not move `accepted_head`.
- no-HITL audit proves retry decisions came from tape reducer or policy.
- Worker-visible prompts and capsules pass the no-PPUT/no-heldout/no-hidden-predicate leakage scan.

Minimum deliverable:
- Two instances: one accepts after retry, one halts by budget.
- Strict audit PASS per bundle.

## Stage12 — 20-task Scale

Goal: scale from fixture-level proof to a 20-task SWE-bench subset with replayable VPPUT and failure reuse metrics.

Claim boundary: 20-task results are protocol and scale evidence only. They are not statistically powered and must not be used for significance, product solve-rate, or comparative superiority claims.

Metrics:
- solve rate;
- total token cost;
- wall time;
- VPPUT;
- retry count;
- failure-class distribution;
- failure-memory reuse rate;
- strict replay pass rate.

Acceptance:
- Every instance has `micro_tape.bundle`.
- Aggregate replay passes from bundles only.
- Every unsolved task has progress 0.
- Every solved task has official PASS -> `CandidateAccepted` -> final `PPUTAccounted(progress=1)`.
- Reused failure rules are traceable from source failure nodes to later capsules.
- Worker-visible prompts and capsules pass the no-PPUT/no-heldout/no-hidden-predicate leakage scan.

Minimum deliverable:
- `evidence/bench/mini_swe_bench_stage12_20task_YYYYMMDD/`.
- Paired direct-worker baseline is recorded separately and never used as MicroTape truth.

## Stage13 — Multi-agent / Market Router

Goal: add worker route diversity while preserving price-not-truth.

Routes:
- Native API Worker;
- Grok CLI worker;
- Codex worker if available;
- deterministic fake/control worker for fixtures.

Acceptance:
- MarketRouter chooses between at least two routes from tape-derived historical stats.
- Market and PPUT affect route/budget suggestion only.
- `MarketSettled` only occurs after terminal basis.
- `RewardDistributed` references terminal `MarketSettled`.
- Agent reputation consumes only terminal VPPUT.
- No market/price/PPUT event moves `accepted_head`.
- Worker-visible prompts and capsules pass the no-PPUT/no-heldout/no-hidden-predicate leakage scan.

Minimum deliverable:
- 5-task multi-route dry run with strict replay PASS and market audit PASS.

## Stage14 — Full SWE-bench Campaign

Goal: sealed full run with replayable truth, VPPUT, and final patch digest per instance.

Acceptance:
- Every instance has a MicroTape bundle.
- Every unsolved instance has `Progress_i=0`.
- Every solved instance has official PASS -> `CandidateAccepted` -> final `PPUTAccounted(progress=1)`.
- All cost/time/branches/tool outputs derive from tape.
- `loop_eval_summary.json` is not truth.
- Replay auditor reconstructs:
  - `tape_tip`;
  - `authorization_head`;
  - `accepted_head`;
  - terminal golden path;
  - VPPUT;
  - final patch digest;
  - final market settlement;
  - failure-memory lineage.
- Worker-visible prompts and capsules pass the no-PPUT/no-heldout/no-hidden-predicate leakage scan.

Minimum deliverable:
- Full bundle manifest with SHA-256 digest per bundle.
- Aggregate report with confidence intervals only when sample size supports them.

## Cross-stage Gates

Each stage must include:
- acceptance commands in README;
- strict MicroTape audit JSON;
- no secret material in artifacts;
- no PPUT formula, heldout IDs, hidden predicates, or raw failure logs in worker-visible prompts/capsules;
- no rewrite of older stage bundles;
- independent recursive audit prompt and response;
- explicit open risks.

No stage may claim PASS unless the exact pushed SHA and evidence path can be independently read from GitHub.
