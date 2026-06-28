# Full SWE-bench Ready Loop Engineering Plan

Status: active execution controller after Phase F repair-loop blocker.

## Core Illusion

TuringOS is ready for full SWE-bench only when every launch prerequisite is a
replayable MicroTape-derived fact, not a shard fixture, local summary, or
repair-loop intention.

## Data Flow Layout

```text
PhaseFRepairLoop(BLOCKED)
  -> fresh Stage16R-real evaluator bundles
  -> PhaseFEvaluatorProof(PASS, executable official replay)
  -> FullDatasetManifestFreeze(selection_policy=ALL)
  -> FullSweBenchReadinessAudit(READY)
  -> Full SWE-bench sharded sealed campaign
  -> unsolved frontier repair loops
  -> full-score claim gate only if unsolved_count == 0
```

## Current State

```text
phase_f_evaluator_proof: PARTIAL
phase_f_repair_loop: BLOCKED
stage16r_real_evaluator_loop: PARTIAL, 2/7 repaired
full_swe_bench_readiness: BLOCKED
next_loop: retry_remaining_stage16r_real_targets
```

## Loop Controller

```python
while True:
    audit = audit_full_swe_bench_readiness()

    if audit.status == "READY":
        start_full_swe_bench_sharded_sealed_campaign()
        break

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

## Phase F-Real: Fresh Stage16R Evaluator Bundles

Objective: supersede the seven hash-bound Stage16R fixture repair artifacts with
fresh worker-derived, executable-evaluator evidence.

Required per target:

- worker-derived `candidate.patch` that is a unified diff;
- official `test.patch` artifact and digest;
- official evaluator command, harness commit/digest, dataset digest, environment
  digest;
- apply-candidate log/result;
- apply-test-patch log/result;
- target test command, exit code, stdout digest, stderr digest;
- fresh MicroTape bundle that imports the evaluator evidence;
- official PASS before `CandidateAccepted`;
- terminal `MarketSettled`, `RewardDistributed`, and final
  `PPUTAccounted(progress=1)` only after terminal acceptance;
- no old MicroTape rewrite and no dataset gold patch shortcut.

Release condition:

```text
audit_phase_f_evaluator_proof.status == PASS
official_evaluator_executable_replay == true
release_next_phase_g == true
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

## Full Campaign Launch Gate

The campaign starts only when:

```text
tools/bench/audit_full_swe_bench_readiness.py -> status READY
full_swe_bench_ready == true
release_phase_g == true
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
