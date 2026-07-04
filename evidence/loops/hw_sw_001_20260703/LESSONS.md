# LESSONS — HW-SW-001..003 (rules_learned, REFLECT step)

1. TOML-key regex must include digits: `[a-zA-Z_]+` silently truncates keys like `sha256`
   (caught pre-gate in audit-substrate-freeze.sh awk parser; fixed to `[a-zA-Z0-9_]+`).
   Rule: any hand-rolled config parser gets a digit-bearing-key test vector before first use.
2. "Ready-block shape" has one authoritative definition: roadmap spec §8
   (docs/roadmap/secure_os_18_month/, `Activate AgenticForgeLoop v1.4 / TuringLoop` block).
   Rule: when a predicate names a term, the predicate author must pin its source doc;
   implementers must not define load-bearing terms from scratch (this one was caught at
   REFLECT and the harness README amended).
3. This repo's commit-validator hook rejects long/non-conventional subjects.
   Rule: conventional short subject + exact required strings in the commit body.
4. Background subagent completion cannot be inferred from PostToolUse hooks (they fire at
   launch); poll artifacts (commits, receipts) or wait for task-notifications.
