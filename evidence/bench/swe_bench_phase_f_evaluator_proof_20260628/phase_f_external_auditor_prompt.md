# External Auditor Prompt: Phase F

Audit the exact pushed SHA. Phase F may claim evaluator-artifact binding for the frozen 20-task shard only.

Check:
1. `CLAIM_BOUNDARY.json` forbids full dataset, full SWE-bench score, and leaderboard-equivalence claims.
2. `patch_manifest.json` has exactly 20 patch entries.
3. Every candidate patch/test patch/stdout/stderr artifact exists and matches its SHA-256.
4. Every artifact appears as `required: true` in `required_evidence_manifest.json`.
5. Every evaluator entry references the MicroTape `OfficialEvaluatorEvidenceImported` and `CandidateAccepted` event IDs.
6. Every evaluator entry records command, harness digest, dataset digest, apply results, target exit code, and log digests.
7. `official_eval_replay_audit.json` reports PASS only if executable official replay is proven. PARTIAL is acceptable only when blockers are explicit and `release_next_phase_g=false`.

Verdict fields:
```text
phase_f_evaluator_artifact_binding: PASS|PARTIAL|FAIL
full_dataset_claim: FORBIDDEN|OVERCLAIM
leaderboard_equivalence_claim: FORBIDDEN|OVERCLAIM
release_next_phase_g: YES|NO
```
