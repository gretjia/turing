# External Auditor Prompt: Full SWE-bench Readiness

Audit the exact pushed SHA and the GitHub-visible evidence paths.

Primary files:

- `tools/bench/audit_full_swe_bench_readiness.py`
- `tests/test_full_swe_bench_readiness.py`
- `docs/handoff/FULL_SWE_BENCH_READY_LOOP_ENGINEERING_PLAN.md`
- `.claude/agent-memory/full_swe_bench_loop_reflection.md`
- `AGENTS.md`
- `evidence/bench/swe_bench_full_readiness_20260628/full_swe_bench_readiness_audit.json`
- `evidence/bench/swe_bench_phase_f_repair_loop_20260628/phase_f_repair_loop_audit.json`
- `evidence/bench/swe_bench_phase_f_evaluator_proof_20260628/official_eval_replay_audit.json`

Expected current verdict:

```text
full_swe_bench_readiness_status: BLOCKED
release_phase_g: NO
next_loop: stage16r_real_evaluator_bundle_loop
overclaim_detected: NO
safe_to_publish_as_readiness_blocker: YES
```

Audit questions:

1. Does the readiness audit block full SWE-bench launch while Phase F evaluator
   proof is PARTIAL?
2. Does it block while the Phase F repair loop is BLOCKED and the seven
   Stage16R targets lack replayable unified diffs?
3. Does it prevent repair-loop structural PASS from directly releasing Phase G?
4. Does it require a full dataset manifest with `selection_policy=ALL`, no
   exclusions, frozen task IDs, dataset digest, and harness digest before
   readiness?
5. Does it forbid full-score and leaderboard-equivalence claims before the full
   campaign completes?
6. Does AGENTS/memory now instruct future agents to read the readiness and
   reflection files before SWE-bench work?
7. Are old Stage16R bundles still immutable?
8. Are dataset gold patches still forbidden as repair candidate sources?
9. Are the tests sufficient to catch current blocker drift, missing full
   manifest, and full-score overclaim?
10. Is the correct next loop fresh Stage16R-real evaluator bundles, not full
    dataset execution?
