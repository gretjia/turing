# Recursive Audit — SWE-bench Verified 500 Readiness

Verdict: READY for official upstream SWE-bench Docker-harness sharded campaign
launch. This is a launch-readiness verdict only; it is not a completed
campaign, full-score, leaderboard-equivalence, or product-release verdict.

Findings:

- Phase F upstream SWE-bench Docker harness qualification is PASS:
  `python -m swebench.harness.run_evaluation` ran against
  `princeton-nlp/SWE-bench_Verified`, and the repaired 20-task Phase F replay
  resolved 20/20 with zero harness errors.
- The earlier Phase F internal target-test replay remains useful as internal
  evidence, but it is no longer the official launch gate.
- Stage16R-real evidence remains PASS for its scoped 7-target repair packet.
- The SWE-bench Verified 500 manifest freeze remains PASS: 500 instance ids,
  `selection_policy=ALL`, no exclusions, and digest-bound dataset descriptors.
- Official campaign launch is allowed only as a 10 shard x 50 task sealed
  campaign with 10-task IPQC windows and 50-task hard shard gates.
- Full-score, leaderboard-equivalence, P1/P2, and provider-billing-complete
  VPPUT claims remain forbidden until the campaign completes and final gates
  pass.

Current machine verdict:

```text
status: READY
phase_g_official_campaign_launch: true
phase_g_internal_rehearsal_launch: true
release_phase_g_as_official_campaign: true
release_phase_g_as_internal_rehearsal: true
next_loop: start_official_swebench_verified_500_sharded_sealed_campaign
internal_rehearsal_next_loop: start_phase_g_internal_rehearsal_over_verified_500_manifest
```

Required next action:

```text
Start the official SWE-bench Verified 500 campaign as sharded sealed execution:
10 shards x 50 tasks, 10-task IPQC windows, upstream Docker harness only, no
one-shot 500 run, no gold patch shortcut, no leaderboard-equivalence claim.
```

Forbidden claims until campaign final gates pass:

```text
full_swe_bench_score_claim_allowed=true
leaderboard_equivalence_claim_allowed=true
p1_p2_product_claim_allowed=true
provider_billing_complete_vpput_claim_allowed=true
```
