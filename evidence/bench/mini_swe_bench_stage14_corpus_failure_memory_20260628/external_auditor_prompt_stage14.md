# External Auditor Prompt — Stage14

Repository: https://github.com/gretjia/turing
Branch: goal/mini-swe-bench-grok-worker
Commit SHA: <EXACT_PUSHED_SHA>
Stage: Stage14 Corpus-Level Failure Memory
Evidence root: `evidence/bench/mini_swe_bench_stage14_corpus_failure_memory_20260628`

Audit scope: verify Stage14 only. Do not convert this PASS into solve-rate, statistical superiority, full SWE-bench score, or causal efficacy.

Required checks:

1. Download and verify bundle SHA-256 digests from `bundle_sha256s.txt`.
2. Run strict MicroTape audit with `--strict-vpput --strict-terminal-market --require-authorization-head` over `turingos/substrate_coverage.json`.
3. Run `audit_corpus_failure_memory.py`.
4. Confirm at least three source `FailureNode` IDs resolve from MicroTape bundles and share failure class `CONTEXT_MISSING`.
5. Confirm `BroadcastRuleActivated` references those source failures, declares the threshold met, and carries only abstract guidance.
6. Confirm a later `WorkCapsuleBuilt` consumes the activated rule via `consumed_broadcast_rule_ids`.
7. Confirm raw logs, hidden predicates, PPUT/VPPUT internals, heldout labels, official solution hints, gold patches, auth caches, API keys, signing material, and credentials are absent from visible rule and capsule payloads.
8. Confirm the efficacy report is bounded and sets `causal_claim_allowed=false`.
9. Confirm Market/PPUT/projection events never move `accepted_head`.
10. Return `release_next_stage: YES` only if every strict field and every stage-specific audit is PASS and you can fetch/verify bundles.

