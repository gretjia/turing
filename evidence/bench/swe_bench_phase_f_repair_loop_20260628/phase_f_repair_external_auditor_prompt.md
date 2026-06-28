# External Auditor Prompt: Phase F Repair Loop

Audit the exact pushed SHA and this evidence root.

Expected scoped verdict for the current packet:

```text
phase_f_repair_loop_status: BLOCKED
release_next_phase_g: NO
gold_patch_shortcut: FORBIDDEN
old_stage16r_tape_rewrite: FORBIDDEN
required_next_action: fresh Stage16R-real evaluator bundles
```

Check that this packet does not claim full dataset, full SWE-bench score, leaderboard equivalence, or Phase G release.
