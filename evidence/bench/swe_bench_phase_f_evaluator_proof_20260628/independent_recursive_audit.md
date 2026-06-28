# Phase F Independent Recursive Audit

Verdict: PARTIAL

Phase F is correctly fail-closed as a `PARTIAL` packet, not a `PASS`.

The recorded audit reports:

- `artifact_microtape_digest_binding: true`
- `official_evaluator_executable_replay: false`
- `all_solved_tasks_have_reproducible_official_eval: false`
- `release_next_phase_g: false`

Scoped findings:

- PASS: Claim boundary is honest. Full dataset, full SWE-bench score, and leaderboard-equivalence claims are forbidden.
- PASS: Tests cover the prior false-negative classes: leaderboard overclaim, unsupported evaluator command, stdout hash drift, dataset count drift, extra patch entry, patch digest mismatch, and non-required evidence.
- PASS: The recorded Stage12 harness artifact is pinned and digest-matched while the current harness digest differs. The recorded artifact and `git show 49936f4a1101c561a3608714f32c41111f7a7619:tools/bench/evaluate_django_swe_bench_patches.py` both hash to `sha256:42455a8e6abbfa042c3c792de4a99c487742c2ce09acddc4ee401b212f222c55`.
- PARTIAL: The Stage16R repair artifacts are digest-bound to MicroTape but are fixture text, not replayable unified diffs. That is correctly treated as a blocker, not as reproducible official replay.

Independent verification run:

```bash
python3 tools/bench/audit_phase_f_evaluator_proof.py \
  --stage16-root evidence/bench/swe_bench_stage16_full_sealed_20260628 \
  --stage16r-root evidence/bench/swe_bench_stage16r_unsolved_repair_20260628 \
  --root evidence/bench/swe_bench_phase_f_evaluator_proof_20260628 \
  --out /tmp/turingos_phase_f_independent_audit.json

pytest tests/test_phase_f_evaluator_proof.py -q -p no:cacheprovider
```

Recursive audit conclusion:

```text
phase_f_evaluator_artifact_binding: PASS
official_evaluator_executable_replay: PARTIAL
release_next_phase_g: NO
full_dataset_claim: FORBIDDEN
leaderboard_equivalence_claim: FORBIDDEN
```

This packet may be committed as a clearly marked PARTIAL / no-release artifact. It must not release Phase G or claim official leaderboard equivalence until the Stage16R artifacts are replaced or superseded by actual replayable unified diffs and executable official evaluator logs.
