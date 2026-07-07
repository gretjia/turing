# Stage12-Stage16 Recursive Audit Execution Plan

Status: proposed release train after Stage11 deterministic loop-until-PASS fixture.

Companion execution controller:

- `docs/handoff/STAGE12_TO_STAGE16_LOOP_ENGINEERING_EXECUTION_PLAN.md`

This file defines release gates. The companion execution controller defines the engineering loop used to run, recover, rerun, audit, and release each stage.

Base achieved state:

- Stage8 proved deterministic no-HITL loop closure fixture.
- Stage9 proved Native API Worker tool receipt fixture.
- Stage10 proved failure taxonomy fixture.
- Stage11 proved deterministic no-HITL loop-until-PASS causal fixture.

Scope guard:

- This plan does not claim SWE-bench superiority, full autonomy, M2 enablement, or hosted/commercial readiness.
- MicroTape remains the source of truth.
- Benchmark summaries, dashboards, manifests, and local JSON are projections.
- No stage is released by local tests alone.
- Each stage must produce fresh GitHub-visible evidence and an independent recursive audit before the next stage starts.
- DeepSeek/Grok/Codex/other model credentials must be passed only through local environment or operator-native login and must never enter tape, logs, CAS, prompts, manifests, or evidence.

## Core Illusion

TuringOS physically becomes stronger only when failed attempts are converted into replayable MicroTape state that changes a later attempt without moving truth early.

## Data Flow Layout

```text
SWE-bench instance
  -> WorkCapsuleBuilt
  -> Worker/tool attempts
  -> WorkerReceiptImported / ToolReceiptAppended
  -> MacroObservationImported
  -> OfficialEvaluatorEvidenceImported
  -> FailureNode or CandidateAccepted
  -> FailureCertificate / BroadcastRuleActivated
  -> RetryAuthorized / MarketRouter route decision
  -> next WorkCapsuleBuilt
  -> terminal CandidateAccepted or budget terminal FailureNode
  -> terminal MarketSettled / RewardDistributed
  -> final PPUTAccounted
  -> micro_tape.bundle
  -> strict replay auditor
  -> independent recursive audit
```

## Stage Gate Contract

Every stage must satisfy this sequence before the next stage starts:

1. Create fresh evidence under `evidence/bench/<stage_name>_YYYYMMDD/`.
2. Include `README.md` with exact reproduction commands.
3. Include `bundle_manifest.json`, `bundle_sha256s.txt`, and per-instance `micro_tape.bundle`.
4. Run strict MicroTape audit with:

   ```bash
   python3 tools/bench/audit_micro_tape_decision_dag.py \
     --strict-vpput \
     --strict-terminal-market \
     --require-authorization-head \
     --coverage <stage>/turingos/substrate_coverage.json \
     --out-dir <stage>/micro_tape_audit_strict
   ```

5. Run the stage-specific auditor(s).
6. Run scoped secret scan. Any real credential-shaped value in evidence is a blocker.
7. Run a local independent recursive audit agent on the exact evidence path.
8. Fix all blocking findings.
9. Commit and push.
10. Confirm remote branch SHA equals local HEAD.
11. Re-run the independent recursive audit on the final exact commit SHA and evidence path after all fixes.
12. External auditor reviews the exact GitHub SHA and evidence path.
13. Only an external or designated independent audit PASS on the exact pushed SHA releases the next stage.

No PASS, no HALT. No stage may reinterpret `loop_eval_summary.json`, CI green, worker self-report, market price, PPUT, or exit code as Micro truth.

Strict gate dominance:

- any strict audit field that is not `PASS` is a release blocker;
- any `NOT_RUN`, `BLOCKED`, `LEGACY_MISSING`, `WARN`, `PARTIAL`, or missing strict field means `release_next_stage: NO`;
- any missing stage-specific audit JSON means `release_next_stage: NO`;
- any missing `independent_recursive_audit.md` means `release_next_stage: NO`;
- any prompt/capsule leakage finding means `release_next_stage: NO`;
- static-only external review may produce useful findings but cannot release the next stage.

Terminal failure-path accounting:

- every unsolved, failed, incomplete, timed-out, or budget-exhausted instance must append terminal `PPUTAccounted(progress=0)`;
- terminal failure PPUT must include `terminal_event_id` pointing to the terminal `FailureNode`, budget-exhausted event, or registry-equivalent terminal failure event;
- no unsolved instance may have `CandidateAccepted`;
- no failed branch may have progress greater than zero.

Prompt/capsule shielding blocker:

- every stage must scan actual worker-visible prompt/capsule bytes, not synthetic safe strings;
- PPUT formula, VPPUT formula, heldout IDs, hidden predicates, raw failure logs, official solution hints, gold patches, credentials, signing material, and auth cache paths are release blockers if visible.

## Stage12 — Real 20-task Loop-until-PASS Scale

Goal: run the Stage11 loop runner on a real 20-task SWE-bench subset.

This is the first scale check after deterministic loop closure. It is not statistically powered and must not be used to claim product superiority.

Required evidence:

- `evidence/bench/mini_swe_bench_stage12_20task_loop_YYYYMMDD/`
- one `micro_tape.bundle` per instance;
- `stage12_aggregate_report.json`;
- `stage12_vpput_report.json`;
- `loop_until_pass_audit.json`;
- `failure_memory_activation_audit.json`;
- `real_classifier_audit.json`;
- `strict_audit_summary.md`;
- `independent_recursive_audit.md`.

Acceptance:

- sample size is exactly 20;
- smaller dry runs may be recorded as useful PARTIAL evidence but cannot PASS Stage12 and cannot release Stage13;
- every instance has a bundle and SHA-256 digest;
- every solved task has `OfficialEvaluatorEvidenceImported(result=PASS) -> CandidateAccepted -> final PPUTAccounted(progress=1)`;
- every unsolved/budget-exhausted task has no `CandidateAccepted` and terminal `PPUTAccounted(progress=0, terminal_event_id=<terminal failure/budget event>)`;
- every failed attempt before a retry has `FailureNode` and `FailureCertificate`;
- every retry decision is `RetryAuthorized` or registry-equivalent authorization;
- `human_interventions_by_class=0` for normal P2/P3 tasks;
- no hidden manual patch, manual approval, or manual rerun selection;
- aggregate VPPUT derives from tape cost/time only;
- no solve-rate superiority or statistical significance claim.

Release blockers:

- any missing bundle;
- any accepted task without official PASS;
- any failed task with progress > 0;
- any manual patch/approval/rerun selection not represented as explicit human route;
- any secret in evidence;
- any external model key in prompt/log/tape/evidence;
- any prompt/capsule leakage finding;
- fewer than 20 tasks.

Recursive audit prompt:

Ask the independent auditor to verify all 20 bundles from GitHub evidence, classify solved/unsolved paths, recompute strict status, inspect no-HITL fields, and explicitly state whether Stage12 is only scale evidence or makes an invalid capability claim.

## Stage13 — Native API Worker Receipts Hardening

Goal: move from deterministic tool-receipt fixtures toward real whitebox tool operation.

Required tools:

- `read_file`
- `list_dir`
- `grep`
- `apply_patch`
- `write_file`
- `run_command`

Required evidence:

- `evidence/bench/mini_swe_bench_stage13_native_api_worker_hardening_YYYYMMDD/`
- real or deterministic tasks where the Native API Worker performs multiple tool calls;
- `native_api_worker_audit.json`;
- `tool_receipt_conservation_audit.json`;
- `prompt_leakage_audit.json`;
- strict MicroTape audit;
- independent recursive audit.

Acceptance:

- every attempted tool call has a registry-compatible receipt;
- executed-but-failed calls are receipted, including `grep` no match, `run_command` nonzero, `apply_patch` conflict, timeout, path denial, and write failure;
- `WorkerReceiptImported` is assembled from tool receipts;
- tool stdout/stderr hashes and cost are counted in `CostEvent` / final PPUT;
- forbidden file mutation generates denial/failure before evaluator acceptance;
- external CLI worker remains PARTIAL provenance; Native API Worker may claim whitebox receipt coverage only for its own tools;
- no worker-visible prompt contains PPUT formula, heldout IDs, hidden predicates, raw logs, gold patches, or official solution hints.

Release blockers:

- any tool action without receipt;
- any failed tool action disappearing from tape;
- any final PPUT missing tool stdout/context cost;
- any `WorkerReceiptImported` self-report not traceable to tool receipt IDs;
- any prompt leakage finding.

Recursive audit prompt:

Ask the auditor to pick several bundles and trace each final worker receipt back to individual tool receipts, including failed tool calls, then verify final PPUT cost conservation.

## Stage14 — Corpus-level Failure Memory

Goal: prove that failure memory works across tasks, not only inside one fixture.

Required evidence:

- `evidence/bench/mini_swe_bench_stage14_corpus_failure_memory_YYYYMMDD/`
- `failure_cluster_audit.json`;
- `broadcast_rule_efficacy_audit.json`;
- `cross_task_memory_lineage.md`;
- strict MicroTape audit;
- independent recursive audit.

Acceptance:

- repeated failure classes are reduced from MicroTape bundles only;
- global `BroadcastRuleActivated` requires a declared threshold such as `N >= 3` same-class failures or a high-confidence rule with a declared confidence function and explicit sample floor;
- every activated rule references source `FailureNode` IDs;
- every future capsule consuming a global rule records `consumed_broadcast_rule_ids`;
- raw logs remain private evidence; visible capsules receive only abstract instructions;
- efficacy report compares pre-rule and post-rule failure recurrence without claiming causality beyond sample support.

Release blockers:

- any broadcast rule with raw log text;
- any rule without source failure nodes;
- any rule activated from projection-only state;
- any efficacy overclaim;
- any repeated failure not represented on tape;
- any prompt/capsule leakage finding.

Recursive audit prompt:

Ask the auditor to trace at least two activated rules from source failures to future capsule consumption and verify that no raw logs, hidden predicates, PPUT internals, heldout labels, or solution hints are visible.

## Stage15 — Multi-agent / Market Router

Goal: introduce route diversity and market-guided budget allocation without letting market signals become truth.

Routes:

- Native API Worker;
- external CLI/API worker where available;
- deterministic control worker;
- optional second real model worker if credentials are supplied by environment only.

Required evidence:

- `evidence/bench/mini_swe_bench_stage15_multi_agent_market_router_YYYYMMDD/`
- `market_router_audit.json`;
- `route_diversity_audit.json`;
- `agent_reputation_audit.json`;
- strict MicroTape audit;
- independent recursive audit.

Acceptance:

- MarketRouter chooses among at least two route types from tape-derived historical stats;
- route choice and budget are suggestions/authorization inputs only;
- `MarketSettled` only occurs after terminal official evidence / terminal accept / terminal failure;
- `RewardDistributed` references terminal `MarketSettled`;
- reputation consumes terminal VPPUT only;
- no price/market/PPUT event advances `accepted_head`;
- diversity floor prevents all budget collapsing to one route solely from price;
- all branch costs and abandoned attempts count in VPPUT.

Release blockers:

- any market event moving `accepted_head`;
- any reward before terminal settlement;
- any reputation update from pre-terminal PPUT;
- any route decision based on off-tape projection truth;
- any hidden prompt leakage between agents;
- any prompt/capsule leakage finding.

Recursive audit prompt:

Ask the auditor to reconstruct route selection, market settlement, reward distribution, and final accepted path from bundles only, then verify price-not-truth and terminal-only reputation.

## Stage16 — Full SWE-bench Sealed Campaign

Goal: run the sealed full SWE-bench campaign with replayable truth, VPPUT, final patch digest, and failure memory lineage per instance.

Required evidence:

- `evidence/bench/swe_bench_stage16_full_sealed_YYYYMMDD/`
- `bundle_manifest.json`;
- `bundle_sha256s.txt`;
- per-instance `micro_tape.bundle`;
- `stage16_aggregate_report.json`;
- `stage16_vpput_report.json`;
- `stage16_replay_audit.json`;
- `stage16_market_audit.json`;
- `stage16_failure_memory_audit.json`;
- `stage16_secret_scan_summary.txt`;
- `stage16_external_auditor_prompt.md`;
- independent recursive audit.

Acceptance:

- every instance has a MicroTape bundle;
- every unsolved instance has terminal `PPUTAccounted(progress=0, terminal_event_id=<terminal failure/budget event>)`;
- every solved instance has official PASS, terminal `CandidateAccepted`, and final `PPUTAccounted(progress=1)`;
- all failed attempts, retries, branches, workers, tool stdout/stderr contexts, and abandoned proposals count in cost;
- replay auditor reconstructs `tape_tip`, `authorization_head`, `accepted_head`, terminal golden path, VPPUT, final patch digest, market settlement, and failure-memory lineage;
- `loop_eval_summary.json` is never used as truth;
- aggregate solve-rate and VPPUT include confidence intervals only where statistically valid;
- no hidden HITL;
- no secrets.

Full-score claim gate:

- `stage16_replay_campaign_pass` is not the same as a full-score claim.
- `stage16_full_pass_claim_allowed` requires `unsolved_count == 0`.
- if `unsolved_count > 0`, Stage16 can only claim sealed campaign replay PASS and must open Stage16R unsolved repair loop;
- any full-score or "SWE-bench all pass" claim with `unsolved_count > 0` is OVERCLAIM.

Release blockers:

- any missing bundle;
- any solved task without official PASS;
- any unsolved task with progress > 0;
- any cost branch not counted;
- any hidden manual intervention;
- any overclaim beyond evidence;
- any auditor inability to fetch GitHub evidence paths.
- any prompt/capsule leakage finding.

Recursive audit prompt:

The Stage16 external auditor prompt must be written into the evidence directory and must include exact GitHub URLs, commit SHA, branch, bundle manifest path, strict audit paths, reproduction commands, and explicit claim boundaries.

## External Audit Release Protocol

For each stage, the release report must include:

```text
stage:
commit_sha:
branch:
evidence_root_github_url:
strict_audit_json_github_url:
stage_specific_audit_json_urls:
bundle_manifest_url:
bundle_sha256s_url:
independent_recursive_audit_url:
commands_run:
local_verification_summary:
open_risks:
claim_boundary:
```

The external auditor must be instructed to mark verdicts as:

```text
PASS          stage scope genuinely proven
PARTIAL       useful evidence, but one or more declared claims not proven
FAIL          blocking contradiction, missing evidence, or truth-boundary violation
OVERCLAIM     evidence may be valid, but README/report claims exceed proof
```

## Final Self-Check

```text
core_illusion: TuringOS improves only when failures become replayable state that changes later attempts
core_data_shapes: micro_tape.bundle, strict audit JSON, stage-specific audit JSON, bundle manifest, recursive audit
micro_end_to_end_model: attempt -> failure -> rule -> retry -> accept/budget -> final PPUT -> strict audit -> recursive audit
single_source_of_truth: MicroTape bundles at exact GitHub SHA
new_infrastructure_bottleneck: none; use existing benchmark tooling and auditors until real scale forces a new service
runtime_truth_boundary: official evidence + predicate moves accepted_head; market/PPUT/projections never do
```
