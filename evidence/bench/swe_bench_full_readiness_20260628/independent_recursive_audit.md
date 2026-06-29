# Independent Recursive Audit — SWE-bench Verified 500 Readiness

Verdict: BLOCKED for official campaign launch; READY only for internal sealed
rehearsal.

Findings:

- Phase F real evidence remains useful as TuringOS internal target-test replay:
  `status=PASS`, artifact binding present, and no full-score/full-dataset or
  leaderboard claim is allowed.
- Phase F is not upstream SWE-bench official Docker harness evidence. The
  evaluator is repo-local `tools/bench/evaluate_django_swe_bench_patches.py`,
  not `python -m swebench.harness.run_evaluation`; Docker build logs,
  upstream evaluation results, and explicit FAIL_TO_PASS/PASS_TO_PASS checks are
  not present.
- Stage16R-real evidence remains PASS for its scoped 7-target repair packet.
- The SWE-bench Verified 500 manifest freeze remains PASS: 500 instance ids,
  `selection_policy=ALL`, no exclusions, and digest-bound dataset descriptors.
- Official campaign launch is blocked by
  `upstream_swebench_docker_harness_required`.
- Internal sealed rehearsal is allowed with the existing manifest and internal
  replay evidence, as long as it is named and claim-bound as internal rehearsal.

Current machine verdict:

```text
status: BLOCKED
phase_g_official_campaign_launch: false
phase_g_internal_rehearsal_launch: true
release_phase_g_as_official_campaign: false
release_phase_g_as_internal_rehearsal: true
next_loop: official_swebench_docker_harness_qualification
internal_rehearsal_next_loop: start_phase_g_internal_rehearsal_over_verified_500_manifest
```

Required next action:

```text
Generate upstream SWE-bench Docker harness evidence using
python -m swebench.harness.run_evaluation, including Docker logs, evaluation
results, FAIL_TO_PASS and PASS_TO_PASS checks, environment/harness/dataset
descriptors, stdout/stderr digests, and MicroTape evidence imports.
```

Forbidden claims until then:

```text
phase_g_official_campaign_launch=true
upstream_swebench_official_docker_harness=true
full_swe_bench_score_claim_allowed=true
leaderboard_equivalence_claim_allowed=true
p1_p2_product_claim_allowed=true
provider_billing_complete_vpput_claim_allowed=true
```
