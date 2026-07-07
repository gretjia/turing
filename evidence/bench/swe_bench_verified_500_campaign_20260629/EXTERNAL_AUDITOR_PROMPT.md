# External Audit Prompt: SWE-bench Verified 500 Campaign Controller

Audit the pinned GitHub commit and this evidence root:

`evidence/bench/swe_bench_verified_500_campaign_20260629/`

## Scope

This packet is a campaign controller and launch-gate scaffold. It freezes the
Verified 500 manifest into 10 sealed 50-task shards with 10-task IPQC windows.
It does not run the campaign, does not claim official leaderboard equivalence,
and does not claim full score.

## Required Verdict Shape

```text
verified_500_manifest_freeze: PASS|FAIL
one_shot_500_forbidden: PASS|FAIL
official_harness_identity_gate_required: PASS|FAIL
repo_local_evaluator_marked_official: FAIL if true
gold_patch_shortcut_allowed: FAIL if true
campaign_execution_started: FAIL if true
official_campaign_launch_ready: NO unless upstream Docker run_evaluation evidence exists
internal_rehearsal_ready: YES|NO
```

## Files To Inspect

- `CAMPAIGN_README.md`
- `CLAIM_BOUNDARY.json`
- `campaign_config.json`
- `task_manifest.json`
- `manifest_audit.json`
- `dataset_descriptor.json`
- `official_harness_descriptor.json`
- `shards/S00..S09/shard_manifest.json`
- `plans/PL-20260629-swebench-verified-500-campaign.md`
- `tools/bench/build_verified_500_manifest.py`
- `tools/bench/audit_verified_500_manifest.py`
- `tools/bench/audit_official_harness_identity.py`
- `tools/bench/build_predictions_jsonl.py`
- `tools/bench/audit_gold_patch_guard.py`
- `tools/bench/run_swebench_shard.py`
- `tools/bench/audit_swebench_shard.py`
- `tools/bench/audit_swebench_campaign.py`

## Questions

1. Does `task_manifest.json` contain exactly 500 unique instances?
2. Does every task belong to exactly one shard `S00..S09`?
3. Does every shard contain exactly 50 tasks?
4. Is `one_shot_500_run` explicitly `FORBIDDEN`?
5. Is the audit atom 50 tasks, not 100 or 500?
6. Are 10-task IPQC windows required?
7. Does the packet avoid claiming campaign execution?
8. Does it require upstream SWE-bench Docker `python -m swebench.harness.run_evaluation` before official launch?
9. Does it prevent repo-local evaluator evidence from being marked official?
10. Does it forbid dataset gold patches or official solution patches as candidate sources?
11. Are full-score and leaderboard-equivalence claims forbidden before final gates?
12. Does the existing readiness packet still block official Phase G launch until official harness identity is proven?

## Expected Static Outcome

This packet may be accepted as:

```text
campaign_controller_scaffold: PASS
verified_500_manifest_sharding: PASS
official_campaign_execution: NOT_STARTED
official_campaign_launch: BLOCKED_PENDING_UPSTREAM_DOCKER_HARNESS_EVIDENCE
```

It must not be accepted as an executed official SWE-bench campaign.
