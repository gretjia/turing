# Contract: Deterministic Predicate Check Set (B-4, ADR-0004) [Art. I.1]

**Status:** frozen Stage-0 baseline. The Predicate that gates a `SOVEREIGN_ACCEPT` advance is
**mechanically-decidable only**, a boolean `f: X -> {0,1}` over Tape bytes. **Code quality / UI / taste is
NEVER a Predicate** — it is a RiskFinding or human review. A natural-language constraint may never fake a
hard gate. A human gate is necessary-not-sufficient: the Predicate over Tape bytes still governs the head move.

## The closed check set (the ONLY allowed checks, all mechanical)
| # | Check | FAIL reason code | Notes |
|---|---|---|---|
| P1 | **schema valid** | `schema_invalid` | payload validates against the event/capsule/receipt schema |
| P2 | **parent/tip correct** | `parent_mismatch` | `parent == prev_tape_tip` (FF-only) |
| P3 | **capsule scope respected** | `scope_violation` | candidate touches only declared `allowed_files` paths |
| P4 | **worktree isolation** | `isolation_violation` | no writes outside the candidate's worktree |
| P5 | **receipt hash match** | `receipt_hash_mismatch` | recomputed `sha256(JCS(receipt))` == imported `payload_hash` |
| P6 | **declared tests pass** | `test_fail` | the capsule's declared `acceptance_commands` exit 0 |
| P7 | **Macro anchor present & binds** | `anchor_mismatch` | declared Macro anchor present and binds the expected tree OID (ANCHOR_BINDS_HASH) |
| P8 | **replay equality** | `replay_mismatch` | re-derived `content_digest` matches; rebuilt accepted state byte-equal |
| P9 | **accepted-state advance rule** | `advance_rule_violation` | event class == SOVEREIGN_ACCEPT, FF-only, `accepted_head_before` ancestor-of-`tape_tip` |
| P0 | **ascii-key / no-float guard** | `ascii_key_violation` / `float_violation` | (codec guard, applies to every payload) |

## Determinism contract
- Two evaluations over identical inputs yield **identical boolean** AND **identical reason digest**
  (`reason_digest = sha256(JCS(sorted reason records))`). (S-3 determinism.)
- Every evaluation emits a `PredicateEvaluated` OBSERVATION on the Tape (records the boolean + reason digest).
- On PASS of a `SOVEREIGN_ACCEPT` event: emit `CandidateAccepted` (or the relevant accept event) → advance
  `accepted_head`. On FAIL: emit `FailureNode` (failure-is-state) → only `tape_tip` advances. Never a silent degrade.

## Forbidden in the predicate
No `quality`, `style`, `taste`, `ui_looks_good`, `reviewer_opinion`, or any NL/subjective check. Such concerns
are routed to a RiskFinding or human-review path, **never** the boolean gate (release-audit 临时违宪 #5).

## Open seam
The PCP-degradation path (Art. I.1.1, Completeness=1 / low soundness-error) is reserved behind the same
`f: X -> {0,1}` interface for future open-world checks — additive, not a rewrite.
