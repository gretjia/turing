# ADR-0001 — Two refs, no third (`tape_tip` + `accepted_head`)

**Status:** Accepted (Stage 0). **Layer:** 3 (project contract). **Contract:** `contracts/refs.md`.

## Context
The >1.0 reference ratifies 3 refs (adds `authorization_head`). The 2026-06-20 audit: *"authorization_head
is NOT a 1.0 constitutional requirement"* [Art. 0.4]. Only `tape_tip` + `accepted_head` are required.

## Decision
Implement exactly two refs on a native-SHA-256 Micro ChainTape. `tape_tip` advances on every valid append
(incl. FailureNodes); `accepted_head` advances only on a `SOVEREIGN_ACCEPT` event with a deterministic
Predicate PASS (FF-only, never regresses). `HEAD_t^{1.0} = accepted_head`. Ordinary authorization is a
PRESERVE Tape event, not a 3rd-ref advance.

## Consequences
- The `head_effect` ADVANCE/PRESERVE distinction makes the 3rd ref additive later (1.x) — no rewrite.
- UI must distinguish Authorized vs Accepted (forbidden to render an authorization as "done").

## Constitution
Art. 0.2 (Tape-canonical), 0.3 (failure-is-state), 0.4 (Q_t triple / HEAD as path).
