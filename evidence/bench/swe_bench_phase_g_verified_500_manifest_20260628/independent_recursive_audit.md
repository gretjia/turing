# Independent Recursive Audit — Phase G Verified 500 Manifest

Verdict: manifest freeze PASS; official campaign launch BLOCKED; internal
sealed rehearsal allowed.

Findings:

- The SWE-bench Verified 500 manifest is frozen with `selection_policy=ALL`,
  500 instance ids, no exclusions, and digest-bound dataset descriptors.
- The repo-local target-test runner is recorded only as an internal replay
  harness. Upstream SWE-bench official harness digest is explicitly pending
  qualification.
- The manifest does not run the campaign and does not claim a full score.
- The current Phase F evaluator proof is repo-local TuringOS internal replay,
  not upstream SWE-bench Docker harness evidence.
- Therefore this manifest may be used for an internal sealed rehearsal only.
- Official campaign launch requires upstream SWE-bench harness qualification:
  `python -m swebench.harness.run_evaluation`, Docker logs,
  `evaluation_results`, FAIL_TO_PASS and PASS_TO_PASS checks, and regenerated
  readiness.

Machine boundary:

```text
phase_g_verified_500_manifest_freeze: PASS
phase_g_internal_sealed_rehearsal_ready_claim_allowed: true
phase_g_official_swebench_campaign_ready_claim_allowed: false
full_swe_bench_verified_campaign_ready_claim_allowed: false
full_swe_bench_score_claim_allowed_before_run: false
leaderboard_equivalence_claim_allowed_before_run: false
```
