# External Retrospective Auditor Prompt — TuringOS Project Review

Date: 2026-07-04  
Workspace root: `/home/zephryj/turingos_backup/work`  
Repository: `https://github.com/gretjia/turing`  
Current branch at prompt creation: `hci/operator-console-v1-rebased`  
Current HEAD at prompt creation: `3476c12a8b5f0ae268596c8db289f2bef135277c`  

## 0. Mission for the External Auditor

Audit TuringOS from its original constitutional/project-plan state through the
current HCI/M6 closure packet and SWE-bench campaign stop.

Do not audit this as a benchmark score report. Audit it as a long-running attempt
to build a constitution-bound, replayable, self-reflecting LLM-backed computation
substrate.

Core question:

```text
Has TuringOS stayed on track toward a universal, replayable, failure-preserving,
audit-first operating substrate, or has it drifted into benchmark chasing,
dashboard truth, or frontier-model substitution?
```

Use this prompt as a checklist. If you cannot clone, run, or verify bundles,
state that clearly and downgrade executable claims to static/artifact-level
review.

## 1. Core Illusion, Data Flow, and Runtime Truth Boundary

### Core Illusion

TuringOS is not the LLM. TuringOS is the paper, pencil, rubber, and discipline:
it records every relevant signal on MicroTape, uses predicates and signatures to
decide sovereign state, compresses failure into reusable memory, and lets
black-box workers propose candidate worlds without letting them become truth.

### Core Data Shapes

```text
MicroTape bundle        append-only Git object graph / replay substrate
tape_tip                all valid events
authorization_head      AUTHORIZATION + PASS events only
accepted_head           SOVEREIGN_ACCEPT + PASS events only
event registry          closed event_type -> class/head_effect/schema mapping
WorkCapsule             bounded worker-visible task specification
WorkerReceipt           worker output / patch / tool result evidence
FailureNode             failed path, progress=0, still preserved on tape
FailureCertificate      classified, replayable failure evidence
BroadcastRule           abstract memory derived from failures, no raw logs
CandidateAccepted       sovereign acceptance only after official PASS
Market/Reward/PPUT      preserve-only economic/statistical projections
HCI projection          read-only/operator projection, never source of truth
```

### Runtime Truth Boundary

Allowed source of truth:

```text
MicroTape + registry + canonical codec + replay reducer + REQUIRED evidence
```

Not allowed as source of truth:

```text
dashboard
HCI projection
worker self-report
CI green
repo-local target test runner presented as official SWE-bench
market price
reward event
PPUT/VPPUT metric
loop_eval_summary.json
chat transcript
frontier-model confidence
```

## 2. Authority and Alignment Files to Inspect

Paths below are relative to `/home/zephryj/turingos_backup/work` unless noted.

### Workspace-level files

- `AGENTS.md`  
  Workspace instruction: use `TOP_ALIGNMENT_PROJECT_BOOK.md` as top alignment,
  but do not treat it as ratified, OG-10 signed, or M2-enabling.

- `README.md`  
  Current local handover.

- `TOP_ALIGNMENT_PROJECT_BOOK.md`  
  Proposed top alignment project book. Status must remain proposed/pending unless
  an actual ratification artifact is found.

### Constitution/root-law copies

- `turingos_research/Reference Docs/Turingos宪法.md`  
  Main local Chinese constitution reference.

- `turing_v5/pack_v5_3_1/00_authority/constitution_root_law.md`  
  Pack/root-law copy. At previous inspection this matched the Chinese reference
  by SHA-256.

- `turingos_research/TURINGOS_GREENFIELD_FULL_ARCHITECTURE_PACK_V5_3_1/00_authority/constitution_root_law.md`

- `turingos_research/ORIGINAL_CONSTITUTION.md`  
  Similar content but different Markdown escaping/formatting. Do not assume byte
  identity with the root-law copy.

Audit question:

```text
Which constitution byte string is the canonical root law for this audit?
Is any file OG-10 signed or human-ratified, or only locally stored?
```

### Original and revised project books

- `turingos_research/PROJECT_PLAN/TURINGOS_1_0_CORE_PROJECT_PLAN.md`
- `turingos_research/TURINGOS_FOUNDATION_PROJECT_BOOK_REVISED_2026-06-25.md`
- `turingos_research/TURINGOS_FOUNDATION_PROJECT_BOOK_REVISED_2026-06-26_CONSTITUTION_ALIGNED.md`
- `docs/project_books/PROJECT_BOOK_TURINGOS_AGENT_ECONOMY_RUNTIME_v1_0.md`
- `turing/docs/project_books/TURINGOS_AGENT_ECONOMY_RUNTIME_GREENFIELD_v1_0.md`

Audit question:

```text
Do these files consistently maintain proposed/pending status, or does any text
overclaim ratification, M2 enablement, closure, or release eligibility?
```

## 3. Planning and Handoff Files to Inspect

In repo `turing`:

- `docs/handoff/TURINGOS_PROJECT_RETROSPECTIVE_AND_EXTERNAL_AUDIT_PROMPT_20260702.md`
- `docs/handoff/STAGE12_TO_STAGE16_LOOP_ENGINEERING_EXECUTION_PLAN.md`
- `docs/handoff/STAGE12_TO_STAGE16_RECURSIVE_AUDIT_PLAN.md`
- `docs/handoff/STAGE12_TO_STAGE16_LOOP_ENGINEERING_PLAN_INDEPENDENT_AUDIT.md`
- `docs/handoff/EXTERNAL_AUDITOR_PROMPT_STAGE12_TO_STAGE16.md`
- `docs/handoff/FULL_SWE_BENCH_READY_LOOP_ENGINEERING_PLAN.md`
- `docs/handoff/EXTERNAL_RETROSPECTIVE_AUDITOR_PROMPT_20260704.md`

Expected finding:

```text
The project gradually shifted from broad claims toward scoped release packets,
strict audit gates, exact-SHA handoffs, and no-PASS-no-HALT discipline.
```

Counter-risk:

```text
The plans may now be stronger than the implementation. Distinguish plan-level
PASS from execution-level PASS.
```

## 4. Stage/Evidence Roots and Known Artifact Status

These statuses are derived from committed JSON artifacts, not from a fresh audit
performed while writing this prompt. You must re-run commands or downgrade the
claim if executable verification is required.

### MicroTape and loop substrate

| Scope | Key path | Artifact status to verify |
|---|---|---|
| Stage6 strict MicroTape protocol fixture | `turing/evidence/bench/mini_swe_bench_stage6_strict_microtape_20260628/` | `micro_tape_audit_strict/micro_tape_decision_dag_audit.json` reports `overall=PASS` |
| Stage7 real worker smoke | `turing/evidence/bench/mini_swe_bench_stage7_real_smoke_2task_20260628/` | real worker landing check, authorization legacy gap in older audit |
| Stage8 no-HITL loop fixture | `turing/evidence/bench/mini_swe_bench_stage8_real_no_hitl_loop_20260628/` | `no_hitl_loop_audit.json` reports `PASS` |
| Stage9 native API worker | `turing/evidence/bench/mini_swe_bench_stage9_native_api_worker_20260628/` | `native_api_worker_audit.json` reports `PASS` |
| Stage10 failure taxonomy | `turing/evidence/bench/mini_swe_bench_stage10_failure_taxonomy_20260628/` | `failure_taxonomy_audit.json` reports `PASS` |
| Stage11 loop-until-PASS | `turing/evidence/bench/mini_swe_bench_stage11_loop_until_pass_20260628/` | `loop_until_pass_audit.json` reports `PASS` |
| Stage12 20-task loop | `turing/evidence/bench/mini_swe_bench_stage12_20task_loop_20260628/` | `stage12_release_audit.json` reports `PASS` |
| Stage13 native API hardening | `turing/evidence/bench/mini_swe_bench_stage13_native_api_worker_hardening_20260628/` | `native_api_worker_audit.json` reports `PASS` |
| Stage14 corpus failure memory | `turing/evidence/bench/mini_swe_bench_stage14_corpus_failure_memory_20260628/` | `corpus_failure_memory_audit.json` reports `PASS` |
| Stage15 market router | `turing/evidence/bench/mini_swe_bench_stage15_multi_agent_market_router_20260628/` | `market_router_audit.json` reports `PASS` |

### Stage16 and Stage16R

- `turing/evidence/bench/swe_bench_stage16_full_sealed_20260628/`
  - `stage16_aggregate_report.json` reports `PASS`.
  - Must be scoped as a 20-task frozen Stage12 shard, not full SWE-bench.
  - It reported 13 solved and 7 unsolved.

- `turing/evidence/bench/swe_bench_stage16r_unsolved_repair_20260628/`
  - `stage16r_repair_audit.json` reports `PASS`.
  - It repaired the 7 Stage16 unsolved tasks.
  - It allows a 20-task-shard full-pass claim only.
  - It forbids full SWE-bench score and leaderboard-equivalence claims.

### Phase F / official harness / Phase G readiness

- `turing/evidence/bench/swe_bench_phase_f_repair_loop_20260628/`
  - Previous no-release blocker packet.

- `turing/evidence/bench/swe_bench_phase_f_evaluator_proof_real_20260628/`
  - Internal evaluator replay evidence.

- `turing/evidence/bench/swe_bench_stage16r_real_evaluator_20260628/`
- `turing/evidence/bench/swe_bench_stage16r_real_evaluator_completed_20260628/`
  - Real evaluator repair completion for the prior 7-target frontier.

- `turing/evidence/bench/swe_bench_phase_g_verified_500_manifest_20260628/`
  - Verified 500 manifest freeze.
  - Must show `task_count=500`, `selection_policy=ALL`, no hidden exclusions.

- `turing/evidence/bench/swe_bench_official_harness_qualification_20260629/`
  - Official SWE-bench Docker harness qualification.
  - `official_harness_qualification_audit.json` reports `PASS`.
  - Inspect:
    - `official_harness_qualification.json`
    - `probe_django_11790/official_harness_probe_audit.json`
    - `phase_f_20_run/evaluation_results.json`
    - `phase_f_20_run/phase_f_20_official_replay_audit.json`
    - `phase_f_11885_repair/candidate.patch`
    - `phase_f_11885_repair/repair_audit.json`
    - `phase_f_20_repaired_run/evaluation_results.json`
    - `phase_f_20_repaired_run/phase_f_20_repaired_official_replay_audit.json`
    - `official_eval_replay_audit.json`

- `turing/evidence/bench/swe_bench_full_readiness_20260628/`
  - Readiness packet. Earlier artifact says official campaign readiness READY.
  - Verify it is not used to claim full score or leaderboard equivalence.

### Verified 500 campaign controller and stop

- `turing/evidence/bench/swe_bench_verified_500_campaign_20260629/`
  - `CAMPAIGN_README.md`
  - `CLAIM_BOUNDARY.json`
  - `LOOP_ENGINEERING.md`
  - `EXTERNAL_AUDITOR_PROMPT.md`
  - `task_manifest.json`
  - `manifest_audit.json`
  - `TURING_COMPLETENESS_PROOF_OBLIGATIONS_20260629.md`
  - `SUPERVISOR_STOP_AUDIT_20260629.json`
  - `SUPERVISOR_STOP_AUDIT_20260629.md`
  - `predictions/shard_S00_predictions.jsonl`
  - `predictions/shard_S00_predictions_report.json`
  - `shards/S00/shard_manifest.json`
  - `shards/S00/shard_run_packet.json`
  - `shards/S00/ipqc/S00-W00/SUPERVISOR_TAINT_NOTE.md`
  - `shards/S00/ipqc/S00-W00/worker_safe_tasks/`
  - `shards/S00/ipqc/S00-W01/worker_safe_tasks/`
  - `shards/S00/ipqc/S00-W02/worker_safe_tasks/`
  - `shards/S00/ipqc/S00-W03/worker_safe_tasks/`
  - `shards/S00/ipqc/S00-W04/worker_safe_tasks/`

Known state to verify:

```text
Full Verified 500 campaign execution: NOT STARTED
S00 shard run gate: BLOCKED
predictions expected: 50
predictions present: 48
missing: pydata__xarray-3677, pylint-dev__pylint-6386
supervisor decision: STOP_SWE_BENCH_WORKER_GENERATION
reason: avoid making the campaign a frontier GPT worker ability test
```

## 5. HCI / M6 / M5.P4 Closure Packet

Current active branch at prompt creation:

```text
hci/operator-console-v1-rebased
HEAD: 3476c12a8b5f0ae268596c8db289f2bef135277c
```

Key packet:

- `turing/evidence/verification/m5_p4_m6_closure_20260704/`
  - `PACKET.json`
  - `PACKET_MANIFEST.sha256`
  - `REPO_ARTIFACTS.json`
  - `SOURCE_MAP.json`
  - `AUDITOR_PROMPT_TEMPLATE.md`
  - `packet_checks/run_m6_g_rollup_check.sh`

Key copied plan artifact root:

- `turing/evidence/verification/m5_p4_m6_closure_20260704/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/`
  - `02_EXECUTION_PLAYBOOK.md`
  - `PROGRESS_TRACKER.md`
  - `modules/MODULE_M5_independent_verification.md`
  - `modules/MODULE_M6_hci_console.md`
  - `research/RES_M5_independent_verification.md`
  - `research/RES_M6_hci_projection_console.md`
  - `adr/ADR-M5-001-closure-certificate-unsigned.md`
  - `adr/ADR-M5-002-custody-separation-properties.md`
  - `adr/ADR-M5-003-exact-sha-release-packet.md`
  - `adr/ADR-M5-004-first-external-audit-target.md`
  - `adr/ADR-M5-005-release-eligibility-gate.md`
  - `adr/ADR-M5-006-g12-wrapper-mechanics-and-schema-subordination.md`
  - `adr/ADR-M5-007-negative-controls-and-skeleton-subsumption.md`
  - `adr/ADR-M6-001-adopt-hci-a-projection-route.md`
  - `adr/ADR-M6-002-archive-then-rebase-rescue.md`
  - `adr/ADR-M6-003-intent-preview-verb-surface.md`
  - `adr/ADR-M6-004-projection-integrity-audit.md`
  - `adr/ADR-M6-005-layered-no-write-enforcement.md`
  - `adr/ADR-M6-006-cli-json-presentation.md`
  - `m6_hci/M6_P1_ROUTE_ACCEPTANCE_RESULT.json`
  - `evidence/session_20260702/M6G_GATE_VERDICT.json`
  - `evidence/session_20260702/M6G_ARTIFACT_ROLLUP.json`
  - `evidence/session_20260702/M6G_M5_P4_HANDOFF_PACKET.json`
  - `evidence/session_20260702/M6G_DRIFT_CHECKLIST.md`

Known state from artifacts:

```text
M6.G status: ADDRESSED
status ceiling: ADDRESSED
HCI route: HCI-A projection route accepted
displayed values replayable: true
zero head-moving paths static and dynamic: true
branch committed/archived: true
external verification: NOT YET GRANTED by packet itself
HCI-B/write-capable console: NOT AUTHORIZED
SHIPPED/RELEASED/RATIFIED/M2/FCE.RUN/OG-10: NOT CLAIMED
```

Audit question:

```text
Does the M5.P4 packet correctly queue M6.G for custody-separated closure without
self-certifying external verification?
```

## 6. Tools and Tests to Inspect

### MicroTape / SWE-bench / campaign tools

- `turing/tools/bench/audit_micro_tape_decision_dag.py`
- `turing/tools/bench/audit_stage16_sealed_campaign.py`
- `turing/tools/bench/audit_stage16r_repair.py`
- `turing/tools/bench/audit_official_harness_qualification.py`
- `turing/tools/bench/build_official_harness_qualification.py`
- `turing/tools/bench/audit_full_swe_bench_readiness.py`
- `turing/tools/bench/audit_swebench_campaign.py`
- `turing/tools/bench/build_verified_500_campaign_controller.py`
- `turing/tools/bench/audit_gold_patch_guard.py`
- `turing/tools/bench/run_swebench_shard.py`

Some file names may differ slightly by current branch. If a listed file is
missing, report it; do not infer a PASS.

### HCI / M6 tools

- `turing/tools/hci/audit_projection_integrity.py`
- `turing/tools/hci/gate_hci_no_write.sh`
- `turing/tools/hci/make_fixture_micro_tape.py`
- `turing/tools/hci/run_hci_gates.sh`
- `turing/tools/release/build_m5_p4_m6_packet.py`

### Tests

- `turing/tests/test_micro_tape_decision_dag_audit.py`
- `turing/tests/test_stage8_no_hitl_loop_audits.py`
- `turing/tests/test_stage10_failure_taxonomy.py`
- `turing/tests/test_stage11_loop_until_pass.py`
- `turing/tests/test_stage12_release_audit.py`
- `turing/tests/test_stage13_native_api_worker.py`
- `turing/tests/test_stage15_market_router.py`
- `turing/tests/test_stage16_sealed_campaign.py`
- `turing/tests/test_stage16r_unsolved_repair.py`
- `turing/tests/test_official_harness_qualification.py`
- `turing/tests/test_full_swe_bench_readiness.py`
- `turing/tests/test_swebench_campaign_manifest.py`
- `turing/tests/test_swebench_campaign_audit.py`
- `turing/tests/test_hci_no_write_gate.py`
- `turing/tests/test_hci_projection_integrity.py`
- `turing/tests/test_m5_p4_m6_github_audit_packet.py`

Audit instruction:

```text
Do not trust artifact PASS alone. If you can run the tests, run the relevant
commands and report exact output. If tests are too expensive or environment
blocked, state NOT_RUN and scope your verdict.
```

## 7. Known Test/Eval Status Before Your Audit

Known from artifacts:

```text
Stage6 strict MicroTape audit: PASS
Stage8 no-HITL audit: PASS
Stage9 native API worker audit: PASS
Stage10 failure taxonomy audit: PASS
Stage11 loop-until-PASS audit: PASS
Stage12 release audit: PASS
Stage13 native API hardening audit: PASS
Stage14 corpus failure memory audit: PASS
Stage15 market router audit: PASS
Stage16 20-task sealed shard audit: PASS
Stage16R 7-target repair audit: PASS
Official harness qualification audit: PASS
M6.G local gate verdict: ADDRESSED, not externally verified
S00 Verified 500 campaign shard: BLOCKED at 48/50 predictions
```

Known not proven:

```text
Full SWE-bench Verified 500 execution: NOT STARTED
Full score: NOT PROVEN
Leaderboard equivalence: FORBIDDEN
Provider-billing-complete VPPUT: NOT PROVEN
Turing completeness: NOT PROVEN
HCI-B/write-capable console: NOT AUTHORIZED
M2 enablement / OG-10 ratification: NOT CLAIMED
```

## 8. What We Found So Far

Positive findings:

```text
1. The project learned from overclaim drift. Broad PASS was repeatedly downgraded
   to scoped PASS/PARTIAL/BLOCKED where appropriate.
2. MicroTape moved from "readable bundle" toward strict replay verifier:
   Git topology, registry-driven head_effect, canonical hash, 7-field append,
   three refs, terminal accepted_head, VPPUT, and market terminality.
3. Failure is preserved as state. Failed runs get FailureNode and progress=0.
4. Market and PPUT are now treated as preserve-only signals, not truth.
5. Stage16R closed the 20-task shard gap without claiming full SWE-bench.
6. Repo-local evaluator was correctly demoted after auditor objection, and an
   upstream SWE-bench Docker harness qualification packet was added.
7. The full Verified 500 controller uses shard/IPQC gates rather than one-shot
   500 execution.
8. The current supervisor stopped frontier-model worker generation because it
   was becoming a test of the strongest worker, not the substrate.
9. HCI has been pulled back toward HCI-A projection-only, with no-write gates and
   projection integrity checks.
```

Concerns:

```text
1. Many artifacts are protocol fixtures, not proof of full production autonomy.
2. Artifact-level no-HITL counters are not physical-world proof of no human
   influence.
3. Failure-memory lineage is stronger than failure-memory efficacy evidence.
4. VPPUT is internally conserved but not necessarily provider-billing-complete.
5. External CLI worker provenance remains PARTIAL.
6. Full Verified 500 has not been executed.
7. The Turing-completeness claim remains a separate formal/executable proof
   obligation and cannot be derived from SWE-bench.
8. HCI must not become a shadow authority store or hidden state projection.
```

## 9. What Is Left

Minimum next obligations:

```text
1. External retrospective audit of this whole arc.
2. Custody-separated audit of M5.P4/M6.G packet.
3. Turing-completeness witness independent from SWE-bench.
4. Worker policy decision before resuming SWE-bench:
   - do not use only frontier GPT-5.5/xhigh if the goal is to test TuringOS;
   - consider weak/heterogeneous workers such as DeepSeek/Flash/non-thinking
     modes or controlled API/fake workers.
5. If SWE-bench resumes:
   - finish S00 50/50 predictions under worker policy;
   - re-run gold-patch guard;
   - use upstream Docker run_evaluation;
   - keep shard gate blocked until evidence is complete.
6. HCI route must stay projection-only unless a new signed/ratified route
   explicitly authorizes write-capable operator behavior.
```

## 10. Questions for the External Auditor

Please answer these directly:

1. Does the project history show real improvement in claim discipline, or only
   better wording?
2. Are the original constitution and project books correctly represented as
   local/proposed artifacts rather than ratified authority?
3. Does strict MicroTape replay support the current claims?
4. Are any dashboards, HCI views, market events, reward events, CI results, or
   worker outputs implicitly acting as source of truth?
5. Is HCI-A projection-only the correct route now?
6. Does the M6.G packet correctly stop at ADDRESSED pending M5.P4 external
   closure?
7. Should the project prioritize a Turing-completeness witness before resuming
   SWE-bench?
8. Is the S00 stop justified because frontier-worker generation had stopped
   being a substrate test?
9. What worker policy would make future SWE-bench runs scientifically useful?
10. Which tests/evals did you actually run, and which did you only inspect?
11. What exact evidence is missing before any full SWE-bench claim?
12. What exact evidence is missing before any Turing-complete claim?

## 11. Required Auditor Verdict Schema

Return a JSON object:

```json
{
  "audit_kind": "external_retrospective",
  "repo_url": "https://github.com/gretjia/turing",
  "branch": "hci/operator-console-v1-rebased",
  "commit_sha": "<exact sha audited>",
  "local_clone_and_tests_run": true,
  "static_only_limitations": [],
  "project_history_review": "PASS|PARTIAL|FAIL",
  "original_plan_status_understood": "PASS|PARTIAL|FAIL",
  "constitution_ratification_claim": "NONE|CLAIMED|UNCLEAR",
  "microtape_strict_replay": "PASS|PARTIAL|FAIL|NOT_RUN",
  "loop_engineering_discipline": "PASS|PARTIAL|FAIL",
  "stage6_to_stage16_artifacts": "PASS|PARTIAL|FAIL|NOT_RUN",
  "official_swebench_harness_identity": "PASS|PARTIAL|FAIL|NOT_RUN",
  "verified_500_campaign_status": "NOT_STARTED|BLOCKED|RUNNING|COMPLETE|UNCLEAR",
  "hci_m6_status": "ADDRESSED|EXTERNALLY_VERIFIED|FAIL|UNCLEAR",
  "hci_route_recommendation": "HCI_A_PROJECTION_ONLY|HCI_B_OPERATOR_CONSOLE|HCI_C_PRODUCT|OTHER",
  "turing_completeness_claim_allowed": false,
  "full_swebench_score_claim_allowed": false,
  "leaderboard_equivalence_claim_allowed": false,
  "release_next_step": "YES|NO",
  "recommended_next_step": "",
  "blockers": [],
  "questions_for_owner": []
}
```

## 12. Suggested Commands

Adjust if the repository layout has changed. Record exact stdout/stderr.

```bash
git clone https://github.com/gretjia/turing.git
cd turing
git checkout <exact_sha>

git status --short

# Packet integrity for M6 closure packet.
sha256sum -c evidence/verification/m5_p4_m6_closure_20260704/PACKET_MANIFEST.sha256
bash evidence/verification/m5_p4_m6_closure_20260704/packet_checks/run_m6_g_rollup_check.sh

# Representative Python tests.
pytest \
  tests/test_micro_tape_decision_dag_audit.py \
  tests/test_stage8_no_hitl_loop_audits.py \
  tests/test_stage10_failure_taxonomy.py \
  tests/test_stage11_loop_until_pass.py \
  tests/test_stage12_release_audit.py \
  tests/test_stage16_sealed_campaign.py \
  tests/test_official_harness_qualification.py \
  tests/test_full_swe_bench_readiness.py \
  tests/test_swebench_campaign_manifest.py \
  tests/test_swebench_campaign_audit.py \
  tests/test_hci_no_write_gate.py \
  tests/test_hci_projection_integrity.py \
  tests/test_m5_p4_m6_github_audit_packet.py \
  -q

# Representative HCI gates.
bash tools/hci/run_hci_gates.sh --out-dir /tmp/turingos_hci_gates

# Campaign gate should remain blocked while S00 has 48/50 predictions.
python tools/bench/audit_swebench_campaign.py \
  --root evidence/bench/swe_bench_verified_500_campaign_20260629
```

If any command is unavailable, stale, or requires large external resources,
report that as `NOT_RUN` rather than inferring PASS.

## 13. Final Self-Check for Auditor

Before final verdict, answer:

```text
core_illusion:
core_data_shapes:
micro_end_to_end_model:
single_source_of_truth:
new_infrastructure_bottleneck:
runtime_truth_boundary:
```

Expected high-level answer:

```text
TuringOS is on track only if MicroTape remains the truth boundary, HCI remains a
projection, workers remain candidate generators, and benchmark execution remains
a stress test of the substrate rather than a frontier-model score chase.
```
