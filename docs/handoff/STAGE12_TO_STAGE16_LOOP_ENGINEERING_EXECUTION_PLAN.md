# Stage12-Stage16 Loop Engineering Execution Plan

Status: proposed operational execution plan after Stage11.

Companion documents:

- `docs/handoff/STAGE12_TO_STAGE16_RECURSIVE_AUDIT_PLAN.md`
- `docs/handoff/EXTERNAL_AUDITOR_PROMPT_STAGE12_TO_STAGE16.md`

This document is the engineering controller. The recursive audit plan defines release gates; this file defines how each stage is actually run, repaired, audited, and advanced.

## Core Illusion

TuringOS becomes stronger only when a failed real attempt is converted into replayable MicroTape state that changes a later attempt, while truth still moves only through predicate-approved Micro events.

## Non-Negotiable Boundaries

- MicroTape is the source of truth.
- `tape_tip` advances on all valid events.
- `authorization_head` advances only on `AUTHORIZATION + PASS`.
- `accepted_head` advances only on `SOVEREIGN_ACCEPT + PASS`.
- Authorization is permission, not completion.
- Market, PPUT, projections, CI, worker exit code, model self-report, benchmark summaries, and dashboards never move `accepted_head`.
- Failed, incomplete, timed-out, budget-exhausted, or unsolved attempts have `Progress_i = 0`.
- Solved attempts require official evaluator PASS, terminal `CandidateAccepted`, and post-terminal final `PPUTAccounted(progress=1)`.
- All agents, all branches, all failed proposals, all tool stdout/stderr context, all reranks, all abandoned routes, and wall time count in cost.
- Worker-visible prompts and capsules must not contain hidden predicates, PPUT/VPPUT formulas, heldout IDs, raw failure logs, official solution hints, gold patches, credentials, auth caches, signing material, or private-key paths.
- Provider credentials are env-only or operator-native-login-only. They must never enter tape, logs, CAS, prompts, manifests, or evidence.
- Old Stage4-Stage11 evidence is immutable history. New stages may read it but must not rewrite or reclassify old bundles.

## Data Flow Layout

```text
StageContract
  -> TaskManifest
  -> AcceptanceCommands
  -> WorkCapsuleBuilt
  -> WorkerDispatchAuthorized / RetryAuthorized
  -> Worker or Native API Tool Calls
  -> ToolCallReceipt / ToolCallDenied
  -> WorkerReceiptImported
  -> MacroObservationImported
  -> OfficialEvaluatorEvidenceImported
  -> FailureNode or CandidateAccepted
  -> FailureCertificate
  -> BroadcastRuleActivated or budget terminal
  -> MarketSettled / RewardDistributed
  -> PPUTAccounted(final)
  -> micro_tape.bundle
  -> strict MicroTape audit
  -> stage-specific audits
  -> independent recursive audit
  -> external exact-SHA audit
  -> release_next_stage decision
```

The physical bottleneck is not model throughput. The bottleneck is whether the next state can be reconstructed from MicroTape and whether that state changes later routing, capsules, or tool use without leaking forbidden information.

## Outer Loop

```python
stage = 12
while stage <= 16:
    contract = freeze_stage_contract(stage)
    write_acceptance_commands(contract)

    while True:
        run_stage_work(contract)
        import_all_evidence_to_microtape(contract)
        run_strict_microtape_audit(contract)
        run_stage_specific_audits(contract)
        run_secret_and_prompt_shield_audits(contract)
        run_independent_recursive_audit(contract)

        if local_release_packet_is_clean(contract):
            commit_and_push(contract)
            verify_remote_sha_equals_local_head(contract)
            run_or_request_exact_sha_external_audit(contract)

            if external_audit_release_next_stage(contract) == "YES":
                stage += 1
                break

        findings = collect_blocking_findings(contract)
        append_failure_nodes_or_project_findings(findings)
        apply_minimal_recovery_patch(findings)
        continue
```

This is the large loop. It halts only after Stage16 has an exact-SHA external audit PASS for the declared Stage16 scope. It does not halt on local test green, independent agent optimism, model self-report, or a partial static review.

## Per-Stage Micro Loop

Every stage runs the same internal loop:

1. **Intent**: write the stage contract, task set, allowed files, forbidden files, risk class, claim boundary, and acceptance commands before running code.
2. **Acceptance First**: create or confirm the exact local commands that will prove the stage. If a command cannot exist yet, implement the auditor before implementing the runner.
3. **Run**: execute the smallest stage task set that can prove the contract. Dry runs are allowed, but dry runs cannot release the stage unless the contract explicitly says so.
4. **Import**: all relevant cost, time, failure, market, PPUT, worker, tool, macro, official evaluator, and retry evidence must enter MicroTape.
5. **Verify**: run strict MicroTape audit, stage-specific auditors, prompt shield audit, secret scan, and deterministic negative controls.
6. **Compress**: reduce failures into `FailureCertificate`, `FailureCluster`, or `BroadcastRuleActivated` when the stage requires learning.
7. **Broadcast/Shield**: inject only abstract rules into later capsules. Raw logs and hidden predicates remain private evidence.
8. **Mini-Recovery**: classify any failing gate and patch minimally. Do not broaden scope to hide the failure.
9. **Push**: after local audits pass, commit, push, and verify remote SHA.
10. **Independent Audit**: produce `independent_recursive_audit.md` for the exact pushed SHA and evidence path.
11. **External Release**: send the external auditor prompt. Only exact-SHA PASS with `release_next_stage: YES` advances the outer loop.
12. **Pause/Blocked Check**: pause only if the current stage is externally released or if a blocker is explicitly recorded with evidence and cannot be resolved without new human input.

## Stage State Machine

```text
PLANNED
  -> ACCEPTANCE_WRITTEN
  -> RUNNING
  -> LOCAL_AUDIT_FAIL
  -> RECOVERY_PATCHED
  -> RUNNING
  -> LOCAL_PASS
  -> PUSHED
  -> INDEPENDENT_PASS
  -> EXTERNAL_REVIEW
  -> EXTERNAL_PASS
  -> RELEASED
```

Allowed non-release states:

- `LOCAL_PARTIAL`: useful evidence but no release.
- `INDEPENDENT_PARTIAL`: local auditor found scope or evidence gaps.
- `EXTERNAL_PARTIAL`: external auditor found gaps; same stage repeats.
- `BLOCKED`: same blocker reproduced across recovery attempts and cannot be resolved without human/environment change.

Blocked does not mean PASS. It means the outer loop pauses at the same stage.

## Finding Classes and Recovery Policy

| Finding class | Minimal recovery |
| --- | --- |
| `STRICT_REPLAY_FAIL` | Fix event shape/reducer/auditor mismatch; regenerate only fresh stage bundles. |
| `AUTHORIZATION_HEAD_MISSING` | Add real stage-scope test authority or OS-keyring path; never fall back silently to auto. |
| `ACCEPTED_HEAD_UNSAFE` | Stop stage; fix predicate/evidence derivation before any new benchmark run. |
| `FINAL_PPUT_MISSING` | Append terminal final PPUT from tape-derived cost/time after terminal event. |
| `FAILED_PROGRESS_NONZERO` | Fix VPPUT reducer; failed/incomplete paths must progress 0. |
| `MARKET_PRETERMINAL_REWARD` | Split pre-terminal proposal from terminal settlement; delay reward. |
| `COST_CONSERVATION_GAP` | Import missing branch/tool/stdout/context cost events, then rerun audit. |
| `PROMPT_LEAKAGE` | Fix shield compiler and regenerate visible prompts; old leaked evidence remains failed evidence. |
| `SECRET_LEAKAGE` | Stop; remove secret from future artifacts, rotate externally if real; never rewrite pushed evidence silently. |
| `OVERCLAIM` | Correct README/report scope and rerun independent audit. |
| `STATIC_ONLY_AUDIT` | Useful but cannot release next stage; obtain executable/fetching external audit. |
| `FLAKY_HARNESS` | Add flakiness evidence and terminal failure semantics; do not convert flake to PASS. |
| `WORKER_FAILURE` | Classify worker failure and append FailureNode; retry only by policy. |

## Release Packet

Every stage must produce:

```text
stage:
commit_sha:
branch:
evidence_root:
evidence_root_github_url:
bundle_manifest:
bundle_sha256s:
strict_audit_json:
stage_specific_audit_jsons:
independent_recursive_audit:
external_auditor_prompt:
commands_run:
local_verification_summary:
negative_controls:
claim_boundary:
open_risks:
release_next_stage:
```

No stage may release without GitHub-visible evidence and exact pushed SHA.

## Stage12 — Real 20-task Loop-until-PASS Scale

### Objective

Run the Stage11 loop-until-PASS runner on exactly 20 SWE-bench-shaped real tasks, preserving strict MicroTape replay and no-HITL accounting. This is scale/protocol evidence, not statistical superiority.

### Input State

- Stage11 deterministic loop-until-PASS fixture PASS.
- Stage10 taxonomy available for failure classes.
- Stage9 Native API Worker fixture available but not yet required for all 20 tasks.
- External CLI/API workers may be used only through env-only credentials or operator-native login.

### Stage12 Atoms

- `S12-A01`: freeze 20-task manifest and claim boundary.
- `S12-A02`: add stage runner mode for exactly 20 tasks; dry-run mode must mark itself PARTIAL.
- `S12-A03`: run attempts until `CandidateAccepted` or budget terminal for each task.
- `S12-A04`: import all official evaluator evidence, failures, retries, market, PPUT, and costs to tape.
- `S12-A05`: produce aggregate solved/unsolved and VPPUT reports from tape only.
- `S12-A06`: run strict and stage-specific audits.
- `S12-A07`: independent recursive audit on exact evidence.
- `S12-A08`: push and external release gate.

### Required Evidence

`evidence/bench/mini_swe_bench_stage12_20task_loop_YYYYMMDD/`

Required files:

- `README.md`
- `task_manifest.json`
- `loop_manifest.json`
- `bundle_manifest.json`
- `bundle_sha256s.txt`
- `stage12_aggregate_report.json`
- `stage12_vpput_report.json`
- `loop_until_pass_audit.json`
- `failure_memory_activation_audit.json`
- `real_classifier_audit.json`
- `micro_tape_audit_strict/micro_tape_decision_dag_audit.json`
- `secret_scan_summary.txt`
- `strict_audit_summary.md`
- `independent_recursive_audit.md`

### Acceptance

- exactly 20 bundles, one per task;
- every solved task has official PASS before `CandidateAccepted`;
- every unsolved, failed, incomplete, timed-out, or budget-exhausted task has no `CandidateAccepted` and terminal `PPUTAccounted(progress=0)`;
- every retry is authorized and appears on `authorization_head`;
- all failed attempts before acceptance have `FailureNode` and `FailureCertificate`;
- aggregate VPPUT derives from tape cost/time only;
- no hidden manual patch, approval, rerun selection, or auto-auth fallback;
- no statistical superiority claim.

### Recovery Loop

- If fewer than 20 tasks complete, mark PARTIAL, fix runner capacity, and rerun Stage12.
- If any task lacks a bundle, do not aggregate; repair export path and rerun.
- If any task has official PASS but no accepted head, fix candidate verify/write bridge.
- If any unsolved task has progress greater than zero, fix VPPUT reducer and regenerate fresh bundles.

### Release Gate

Stage12 releases Stage13 only after external exact-SHA audit says `release_next_stage: YES`. Static GitHub-only review cannot release Stage13.

## Stage13 — Native API Worker Receipts Hardening

### Objective

Make the whitebox Native API Worker the audited tool path. Every `read_file`, `list_dir`, `grep`, `apply_patch`, `write_file`, and `run_command` action must produce a tool receipt or denial, and final worker receipts must be traceable to those tool receipts.

### Input State

- Stage12 exact 20-task scale released.
- Stage9 tool receipt fixture exists and is used as characterization, not proof for Stage13.

### Stage13 Atoms

- `S13-A01`: define `ToolCallReceipt` and `ToolCallDenied` coverage checklist for all six tools.
- `S13-A02`: harden Native API Worker execution path so failed tool calls are also receipted.
- `S13-A03`: assemble `WorkerReceiptImported` from tool receipt IDs only.
- `S13-A04`: include tool stdout/stderr/context costs in PPUT cost reducer.
- `S13-A05`: add prompt/capsule byte shield audit over actual worker-visible bytes.
- `S13-A06`: run at least one accepted path and one failed path using Native API Worker.
- `S13-A07`: run strict, native worker, tool conservation, prompt leakage, and independent audits.

### Required Evidence

`evidence/bench/mini_swe_bench_stage13_native_api_worker_hardening_YYYYMMDD/`

Required files:

- `native_api_worker_audit.json`
- `tool_receipt_conservation_audit.json`
- `prompt_leakage_audit.json`
- `tool_call_lineage.md`
- standard strict audit and bundle manifests.

### Acceptance

- every attempted tool action has a receipt or denial;
- no failed tool action disappears from tape;
- `WorkerReceiptImported` references tool receipt IDs;
- failed `grep`, denied write, apply conflict, nonzero command, timeout, and forbidden path mutation are covered by negative controls;
- final PPUT includes tool stdout/stderr/context costs;
- external CLI workers remain PARTIAL provenance and are not upgraded by this stage.

### Recovery Loop

- Missing receipt: instrument the tool boundary and rerun.
- Receipt without cost: fix cost reducer and rerun.
- Prompt leakage: fix shield compiler, regenerate prompts, rerun.
- Self-reported worker receipt: reject and rebuild receipt from tool IDs.

### Release Gate

Stage13 releases Stage14 only after exact-SHA external audit confirms tool receipt conservation and prompt shielding.

## Stage14 — Corpus-level Failure Memory

### Objective

Turn repeated failures across tasks into activated broadcast rules that future capsules consume, without broadcasting raw logs or hidden scoring information.

### Input State

- Stage12 provides task-scale failures and attempts.
- Stage13 provides tool-level receipts and richer failure evidence.

### Stage14 Atoms

- `S14-A01`: reduce failure clusters from MicroTape bundles only.
- `S14-A02`: require activation threshold, for example `N >= 3` same-class failures or declared high-confidence function with sample floor.
- `S14-A03`: append `BroadcastRuleActivated` with source failure node IDs.
- `S14-A04`: inject activated rules into later `WorkCapsuleBuilt`.
- `S14-A05`: verify visible capsules include abstract guidance only.
- `S14-A06`: measure bounded efficacy without causal overclaim.
- `S14-A07`: run corpus memory, leakage, efficacy, strict, and independent audits.

### Required Evidence

`evidence/bench/mini_swe_bench_stage14_corpus_failure_memory_YYYYMMDD/`

Required files:

- `failure_cluster_audit.json`
- `broadcast_rule_efficacy_audit.json`
- `cross_task_memory_lineage.md`
- `broadcast_rule_visibility_audit.json`
- standard strict audit and bundle manifests.

### Acceptance

- failure clusters derive from MicroTape only;
- activated rules reference source `FailureNode` IDs;
- later capsules record `consumed_broadcast_rule_ids`;
- raw logs remain private evidence;
- visible rule text excludes hidden predicates, PPUT/VPPUT internals, heldout labels, official solution hints, and credentials;
- efficacy claims include sample size and uncertainty and avoid overclaiming causality.

### Recovery Loop

- Rule without source failures: reject activation and rerun reducer.
- Raw log in visible capsule: fix shield and mark leaked run as failed evidence.
- Efficacy overclaim: lower claim scope and rerun independent audit.
- Projection-only cluster: fix reducer to read bundles.

### Release Gate

Stage14 releases Stage15 only after external audit traces at least two rules from source failures to future capsule consumption.

## Stage15 — Multi-agent / Market Router

### Objective

Introduce route diversity and tape-derived MarketRouter budget decisions while preserving price-not-truth. Market may route attention; predicate remains the truth gate.

### Input State

- Stage12 loop runner works at 20-task scale.
- Stage13 tool receipts provide whitebox branch costs.
- Stage14 provides failure memory and rule consumption.

### Stage15 Atoms

- `S15-A01`: define route types and worker profiles with hash-form worker IDs.
- `S15-A02`: derive route stats from terminal VPPUT, cost, latency, failure class, and compliance.
- `S15-A03`: make MarketRouter choose among at least two route types.
- `S15-A04`: enforce diversity floor and budget cap.
- `S15-A05`: record abandoned branch costs.
- `S15-A06`: settle market only after terminal evidence/accept/failure.
- `S15-A07`: update reputation only from terminal VPPUT.
- `S15-A08`: run market, route diversity, reputation, strict, and independent audits.

### Required Evidence

`evidence/bench/mini_swe_bench_stage15_multi_agent_market_router_YYYYMMDD/`

Required files:

- `market_router_audit.json`
- `route_diversity_audit.json`
- `agent_reputation_audit.json`
- `price_not_truth_audit.json`
- `branch_cost_conservation_audit.json`
- standard strict audit and bundle manifests.

### Acceptance

- at least two route types are exercised;
- route decisions derive from tape historical stats, not off-tape projection truth;
- route choice affects budget/dispatch suggestion only;
- market/price/PPUT never advances `accepted_head`;
- `MarketSettled` and `RewardDistributed` are terminal-basis only;
- reputation consumes terminal VPPUT only;
- abandoned route/branch costs count in final VPPUT;
- diversity floor prevents pure price collapse.

### Recovery Loop

- Reward before terminal basis: fix settlement split and rerun.
- Reputation from progress PPUT: reject and recompute from final VPPUT only.
- Single route collapse: enforce diversity floor and rerun.
- Off-tape route stats: rebuild stats from bundles.

### Release Gate

Stage15 releases Stage16 only after exact-SHA external audit verifies price-not-truth, terminal reward, and route diversity from bundles.

## Stage16 — Full SWE-bench Sealed Campaign

### Objective

Run the sealed full SWE-bench campaign with replayable truth, VPPUT, final patch digest, cost conservation, failure memory lineage, market settlement, and no hidden HITL.

### Input State

- Stage12 loop scale released.
- Stage13 tool receipts released.
- Stage14 corpus memory released.
- Stage15 multi-agent market/router released.

### Stage16 Atoms

- `S16-A01`: freeze full task manifest, model/worker matrix, budget profile, and claim boundary before run.
- `S16-A02`: run sealed campaign with no manual per-instance intervention.
- `S16-A03`: export one MicroTape bundle per instance.
- `S16-A04`: derive aggregate solved/unsolved/VPPUT from bundles only.
- `S16-A05`: produce final patch digest and terminal golden path per solved instance.
- `S16-A06`: produce terminal failure/budget state and progress 0 per unsolved instance.
- `S16-A07`: run strict, market, failure memory, no-HITL, secret, and aggregate replay audits.
- `S16-A08`: write external auditor prompt with exact GitHub URLs.
- `S16-A09`: run independent recursive audit and external exact-SHA audit.

### Required Evidence

`evidence/bench/swe_bench_stage16_full_sealed_YYYYMMDD/`

Required files:

- `README.md`
- `task_manifest.json`
- `bundle_manifest.json`
- `bundle_sha256s.txt`
- per-instance `micro_tape.bundle`
- `stage16_aggregate_report.json`
- `stage16_vpput_report.json`
- `stage16_replay_audit.json`
- `stage16_market_audit.json`
- `stage16_failure_memory_audit.json`
- `stage16_no_hitl_audit.json`
- `stage16_secret_scan_summary.txt`
- `stage16_external_auditor_prompt.md`
- `independent_recursive_audit.md`

### Acceptance

- every instance has a MicroTape bundle and SHA-256 digest;
- solved iff official PASS precedes `CandidateAccepted` and final PPUT progress is 1;
- unsolved/incomplete/budget-exhausted iff no `CandidateAccepted` and terminal PPUT progress is 0;
- all costs from all agents, branches, failed proposals, tool stdout/stderr context, reranks, and abandoned routes are counted;
- replay reconstructs `tape_tip`, `authorization_head`, `accepted_head`, terminal golden path, final patch digest, VPPUT, market settlement, and failure-memory lineage;
- no hidden HITL;
- aggregate claims include confidence intervals only where statistically valid;
- no loop summary, dashboard, projection, CI result, or worker self-report is truth.

### Recovery Loop

- Missing bundle: stop aggregate report and regenerate export.
- Any solved path missing official PASS: fix predicate/evidence bridge before proceeding.
- Any unsolved progress > 0: fix VPPUT reducer and regenerate fresh bundle.
- Any cost gap: import missing cost evidence and rerun strict audit.
- Any hidden HITL: mark campaign invalid for no-HITL claim; rerun sealed campaign only after controller fix.
- Any overclaim: correct report scope and rerun independent audit.

### Final Release Gate

Stage16 is complete only after an external exact-SHA auditor can fetch GitHub evidence, verify bundle digests, replay or reason through MicroTape, and return `PASS` for Stage16 scope. If the external auditor cannot fetch bundles, the campaign may be artifact-coherent but is not externally released.

## Independent Recursive Audit Pattern

After local audits and before external audit, run an independent agent with this invariant-focused brief:

```text
Audit the exact stage evidence from the pushed SHA. Do not trust local claims.
Check:
- all strict MicroTape fields are PASS;
- required stage-specific audits exist and PASS;
- no stage claim exceeds evidence;
- every solved/unsolved path satisfies VPPUT semantics;
- every authorization/acceptance ref follows three-ref law;
- every market/reward/PPUT event is terminal where required;
- every prompt/capsule is shielded;
- no secrets appear in evidence;
- old bundles were not rewritten;
- release_next_stage should be YES only if all required evidence is GitHub-visible and exact-SHA.
Return PASS/PARTIAL/FAIL/OVERCLAIM with blocking findings.
```

The independent audit is not a substitute for external release. It is a local adversarial loop that prevents wasting an external audit cycle on known gaps.

## External Auditor Prompt Generation

For each stage, create a stage-specific auditor prompt from `docs/handoff/EXTERNAL_AUDITOR_PROMPT_STAGE12_TO_STAGE16.md` with:

```text
<EXACT_PUSHED_SHA>
<STAGE>
<GITHUB_URL_TO_EVIDENCE_ROOT>
<STRICT_AUDIT_JSON_URL>
<BUNDLE_MANIFEST_URL>
<BUNDLE_SHA256S_URL>
<STAGE_SPECIFIC_AUDIT_URLS>
<THIS_EXECUTION_PLAN_URL>
```

The prompt must ask the auditor to inspect this execution plan and the recursive audit plan. If the actual stage evidence deviates from either plan, the auditor should treat that as a finding.

## Final Self-Check

```text
core_illusion: failed attempts become replayable state that changes later attempts without moving truth early
core_data_shapes: StageContract, TaskManifest, MicroTape bundle, ToolReceipt, FailureNode, FailureCertificate, BroadcastRuleActivated, MarketSettled, PPUTAccounted, strict audit JSON
micro_end_to_end_model: run attempt -> import evidence -> reject/accept -> compress failure -> retry -> final PPUT -> audit -> exact-SHA external release
single_source_of_truth: MicroTape bundles at exact GitHub SHA
new_infrastructure_bottleneck: none yet; keep using existing runner/auditor files until real scale forces service extraction
runtime_truth_boundary: only official evidence plus predicate-approved Micro events move accepted_head; market/PPUT/projections remain derived signals
```
