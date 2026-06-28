# External Auditor Prompt — Phase G Full SWE-bench Verified 500 Manifest Freeze

Audit this GitHub path:

- evidence/bench/swe_bench_phase_g_verified_500_manifest_20260628/

Questions:
1. Does task_manifest freeze exactly 500 SWE-bench Verified instance IDs with selection_policy=ALL?
2. Is the dataset digest bound to Hugging Face repo SHA 91aa3ed51b709be6457e12d00300a6a596d4c6a3?
3. Does it avoid committing raw gold patches while preserving digest/instance-id auditability?
4. Are authorization_mode required, no auto fallback, no manual patch/rerun, and strict MicroTape acceptance commands present?
5. Does CLAIM_BOUNDARY forbid full-score, leaderboard-equivalence, P1/P2, and provider-billing-complete VPPUT claims before a sealed run?
6. Is this SWE-bench Verified 500 scope, not classic SWE-bench 2294?
