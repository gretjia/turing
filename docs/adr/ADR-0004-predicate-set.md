# ADR-0004 — Deterministic Predicate check set

**Status:** Accepted (Stage 0). **Layer:** 3. **Contract:** `contracts/predicate_set.md`.

## Context
Art. I.1 requires hard, mechanically-decidable, byte-deterministic gates. The prior plan risked "predicate
creep" — quality/taste sneaking into the boolean gate.

## Decision
Freeze a **closed** check set: schema valid, parent/tip (FF), capsule scope, worktree isolation, receipt
hash, declared tests, Macro anchor, replay equality, accepted-state advance rule (+ codec ascii/no-float
guard). Output `{0,1}` over Tape bytes; two runs on identical inputs yield identical boolean + identical
reason digest. **No quality/UI/taste check is ever in this set** — such concerns are RiskFinding / human
review. Every evaluation emits `PredicateEvaluated`; PASS→accept event (advance), FAIL→FailureNode (no advance).

## Consequences
- The PCP-degradation path is reserved behind the same `f: X→{0,1}` interface (additive).
- S-3 asserts determinism + correct failure reasons + no taste in the gate.

## Constitution
Art. I.1. Avoids 临时违宪 #3 (predicate bypass) and #5 (NL faking a gate).
