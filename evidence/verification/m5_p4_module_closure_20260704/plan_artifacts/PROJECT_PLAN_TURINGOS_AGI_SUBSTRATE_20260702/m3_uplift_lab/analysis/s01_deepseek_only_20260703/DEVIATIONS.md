# M3.P7 Deviations

Status: COMPLETE for the reregistered DeepSeek-only S01 analysis.

## Recorded Deviations

1. The original M3 preregistration defined a heterogeneous worker roster. The executed measurement is the forward-only reregistered DeepSeek-only same-provider source-context continuation authorized by `M3_P4_DEEPSEEK_ONLY_REREGISTRATION.md`, `M3_P5_DEEPSEEK_SOURCE_REPAIR_CONTINUATION.md`, and `M3_P6_DEEPSEEK_LOOP_CONTINUATION.md`.
2. Arm A is the DeepSeek source-context repair result from M3.P5, not the original heterogeneous Arm A.
3. Arms B and C are DeepSeek source-context loop arms. Arm B includes the delimited abstract broadcast-rules section; Arm C contains the same delimited section without rules.
4. Official upstream SWE-bench reports include 450 non-submitted Verified split tasks in `incomplete_ids`. For frozen analysis, S01-scoped derived `evaluation_results.json` files preserve submitted S01 outcomes and set `incomplete_ids` to submitted tasks not completed. This produced zero pairwise exclusions.

## Claim Boundary

This analysis does not claim the original heterogeneous-worker preregistration was executed byte-identically. It does not claim TuringOS improves workers because H1 did not pass the preregistered rule. It does not claim external verification, release, ratification, M2 enablement, OG-10 signature, genesis signature, or constitution-byte change.
