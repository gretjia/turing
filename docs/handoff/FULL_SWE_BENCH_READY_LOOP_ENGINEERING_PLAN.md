# SWE-bench Verified 500 Loop Engineering Plan

Status: active execution controller after external downgrade of official
campaign readiness.

## Core Illusion

TuringOS is ready for an official SWE-bench campaign only when every launch
prerequisite is a replayable MicroTape-derived fact and the evaluator identity is
the upstream SWE-bench Docker harness, not a repo-local target-test runner.

## Data Flow Layout

```text
PhaseFRepairLoop(BLOCKED)
  -> fresh Stage16R-real evaluator bundles
  -> PhaseFInternalReplay(PASS, repo-local target-test replay)
  -> FullDatasetManifestFreeze(selection_policy=ALL)
  -> FullSweBenchReadinessAudit(BLOCKED for official, internal rehearsal allowed)
  -> UpstreamSweBenchDockerHarnessQualification
  -> OfficialCampaignReadinessAudit(READY only after run_evaluation evidence)
  -> Official SWE-bench sharded sealed campaign
  -> unsolved frontier repair loops
  -> full-score claim gate only if unsolved_count == 0
```

## Current State

```text
phase_f_internal_replay: PASS
phase_f_as_upstream_swebench_official: BLOCKED
stage16r_real_evaluator_loop: PASS, 7/7 repaired
phase_g_verified_500_manifest: PASS
official_swe_bench_campaign_readiness: BLOCKED
internal_rehearsal_readiness: READY
next_official_loop: official_swebench_docker_harness_qualification
internal_rehearsal_next_loop: start_phase_g_internal_rehearsal_over_verified_500_manifest
```

## Loop Controller

```python
while True:
    audit = audit_full_swe_bench_readiness()

    if audit.status == "READY" and audit.phase_g_official_campaign_launch:
        start_official_swebench_verified_500_sharded_sealed_campaign()
        break

    if audit.phase_g_internal_rehearsal_launch:
        # Allowed only as internal rehearsal. This never creates an official
        # SWE-bench score or leaderboard-equivalence claim.
        start_phase_g_internal_rehearsal_over_verified_500_manifest()
        continue

    if audit.next_loop == "official_swebench_docker_harness_qualification":
        run_upstream_swebench_docker_harness_qualification()
        regenerate_readiness()
        continue

    if audit.next_loop == "stage16r_real_evaluator_bundle_loop":
        run_fresh_stage16r_real_evaluator_bundles()
        rerun_phase_f_evaluator_proof()
        continue

    if audit.next_loop == "retry_remaining_stage16r_real_targets":
        retry_remaining_stage16r_real_targets()
        rerun_phase_f_evaluator_proof_when_all_repaired()
        continue

    if audit.next_loop == "rerun_phase_f_evaluator_proof":
        rerun_phase_f_evaluator_proof()
        continue

    if audit.next_loop == "phase_g_full_manifest_freeze":
        freeze_full_dataset_manifest()
        continue

    fix_readiness_audit_problems()
```

No state advances on local optimism. The loop only advances on audit JSON.

## Phase F-Real: Fresh Stage16R Internal Evaluator Bundles

Objective: supersede the seven hash-bound Stage16R fixture repair artifacts with
fresh worker-derived, repo-local target-test replay evidence.

Required per target:

- worker-derived `candidate.patch` that is a unified diff;
- official `test.patch` artifact and digest;
- internal evaluator command, harness commit/digest, dataset digest, environment
  digest;
- apply-candidate log/result;
- apply-test-patch log/result;
- target test command, exit code, stdout digest, stderr digest;
- fresh MicroTape bundle that imports the evaluator evidence;
- internal target-test PASS before `CandidateAccepted`;
- terminal `MarketSettled`, `RewardDistributed`, and final
  `PPUTAccounted(progress=1)` only after terminal acceptance;
- no old MicroTape rewrite and no dataset gold patch shortcut.

Release condition:

```text
audit_phase_f_evaluator_proof.status == PASS
phase_f_real_evaluator_proof_as_internal_replay == PASS
release_next_phase_g_as_internal_rehearsal == true
release_next_phase_g_as_official_campaign == false
```

Official campaign release additionally requires upstream SWE-bench Docker
harness evidence:

```text
python -m swebench.harness.run_evaluation
docker_build_logs_present == true
evaluation_results_present == true
FAIL_TO_PASS checked
PASS_TO_PASS checked
```

## Phase G: Full Manifest Freeze

Objective: freeze the real full SWE-bench manifest before any full run.

Required manifest properties:

- `selection_policy: ALL`;
- `task_count == official_dataset_task_count`;
- `len(instance_ids) == task_count`;
- no duplicate instance IDs;
- `excluded_instances: []`;
- `exclusion_reason: {}`;
- source dataset digest and official harness digest are SHA-256 bound;
- `authorization_mode: required`;
- no auto-authorization fallback;
- full-score claim disabled before run;
- acceptance commands include strict MicroTape and VPPUT audits.

## Official Campaign Launch Gate

The campaign starts only when:

```text
tools/bench/audit_full_swe_bench_readiness.py -> status READY
phase_g_official_campaign_launch == true
release_phase_g_as_official_campaign == true
official_harness_status == PASS
```

## Claim Boundary

Before the full campaign completes:

- no full SWE-bench score claim;
- no leaderboard-equivalence claim;
- no P1/P2 product claim;
- no provider-billing-complete VPPUT claim unless provider token receipts are
  present.

After the full campaign completes, a full-score claim is still allowed only if:

```text
full_dataset_task_count == official_dataset_task_count
unsolved_count == 0
every task has official PASS
every task has CandidateAccepted
every task has final PPUTAccounted(progress=1)
all branches, retries, failures, tool outputs, cost, and time derive from MicroTape
no-HITL counters remain zero
exact-SHA external audit releases the claim
```
