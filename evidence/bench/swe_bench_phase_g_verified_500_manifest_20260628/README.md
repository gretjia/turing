# Phase G SWE-bench Verified 500 Manifest Freeze

This packet freezes the SWE-bench Verified 500 task manifest. It does not run
the campaign and does not claim a full score.

After the 2026-06-28 external audit, this manifest may be used for an internal
sealed rehearsal. It is not sufficient to launch an official SWE-bench campaign
until upstream Docker harness evidence is added.

The raw parquet is not committed because rows contain official patch/test-patch material. The manifest commits the Hugging Face dataset repo SHA, parquet SHA-256 digest, and all 500 instance IDs.

Scope: SWE-bench Verified full 500, not SWE-bench classic 2294.

The manifest no longer treats the repo-local target-test runner as the official
SWE-bench harness. Upstream official harness identity is explicitly pending:

```text
official_harness_kind: pending_upstream_swebench_docker
official_harness_digest_status: PENDING_UPSTREAM_SWEBENCH_DOCKER_QUALIFICATION
internal_replay_harness_kind: repo_local_django_target_test_replay
```

Current claim boundary:

```text
phase_g_verified_500_manifest_freeze: PASS
phase_g_internal_sealed_rehearsal_ready_claim_allowed: true
phase_g_official_swebench_campaign_ready_claim_allowed: false
full_swe_bench_verified_campaign_ready_claim_allowed: false
full_swe_bench_score_claim_allowed_before_run: false
leaderboard_equivalence_claim_allowed_before_run: false
required_next_action_before_official_campaign: upstream_swebench_docker_harness_qualification
```
