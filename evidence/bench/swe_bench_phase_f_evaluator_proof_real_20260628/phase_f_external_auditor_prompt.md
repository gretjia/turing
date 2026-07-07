# External Auditor Prompt: Phase F Internal Replay

Audit the exact pushed SHA. Phase F may claim internal evaluator-artifact binding for the frozen 20-task shard only.

It must not claim upstream SWE-bench official Docker harness equivalence unless
the packet contains `python -m swebench.harness.run_evaluation` evidence, Docker
logs, evaluation results, and both FAIL_TO_PASS and PASS_TO_PASS checks.

Check:
1. `CLAIM_BOUNDARY.json` forbids full dataset, full SWE-bench score, and leaderboard-equivalence claims.
2. `patch_manifest.json` has exactly 20 patch entries.
3. Every candidate patch/test patch/stdout/stderr artifact exists and matches its SHA-256.
4. Every artifact appears as `required: true` in `required_evidence_manifest.json`.
5. Every evaluator entry references the MicroTape `OfficialEvaluatorEvidenceImported` and `CandidateAccepted` event IDs.
6. Every evaluator entry records command, harness digest, dataset digest, apply results, target exit code, and log digests.
7. `official_eval_replay_audit.json` reports PASS only for internal replay unless upstream SWE-bench Docker harness evidence is present.

Verdict fields:
```text
phase_f_internal_evaluator_artifact_binding: PASS|PARTIAL|FAIL
phase_f_as_upstream_swebench_official: PASS|BLOCKED|FAIL
full_dataset_claim: FORBIDDEN|OVERCLAIM
leaderboard_equivalence_claim: FORBIDDEN|OVERCLAIM
release_next_phase_g_as_internal_rehearsal: YES|NO
release_next_phase_g_as_official_campaign: YES|NO
```
