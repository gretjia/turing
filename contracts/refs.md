# Contract: The Two Refs (B-1, ADR-0001) [Art. 0.4]

**Status:** frozen Stage-0 baseline. **NO third ref** (`authorization_head`) in 1.0 — ordinary
authorization is just a Tape event. `HEAD_t^{1.0} = accepted_head`.

| Ref | Advances on | Advance rule | Never moves on |
|---|---|---|---|
| `refs/turingos/tape_tip` | **ALL** valid Micro appends | every valid append (FF-only, `parent == prev_tape_tip`, schema-valid, `payload_hash` matches) advances it — **including FailureNodes**, rejections, observations, receipts, authorizations | nothing — universal append head; **moves even when `accepted_head` does not** [Art. 0.2/0.3] |
| `refs/turingos/accepted_head` | **only** `SOVEREIGN_ACCEPT`-class events | advances iff `registry[type].class == SOVEREIGN_ACCEPT` **AND** deterministic Predicate result `== PASS` over tape bytes. **NEVER** on HTTP 200, CI-green, merge success, `exit_code==0`, or any vendor self-report. FF-only, on-tape, never regresses, never forks. On FAIL/NOT_RUN: `Q_{t+1}=Q_t`, node still lands on `tape_tip` | any non-`SOVEREIGN_ACCEPT` event; failed/un-run predicates |

## Q_t triple [Art. 0.4]
- `tape_t` = the Git object graph of the SHA-256 Micro ChainTape.
- `HEAD_t` = `refs/turingos/accepted_head` (latest sovereignly-accepted world state path pointer).
- `q_t` = the reduced projection over those bytes (see `INTERFACES.md` reduce).

## Substrate [F-1]
- Real Git **Micro ChainTape**, native **SHA-256 object format** (`git init --object-format=sha256`).
- FF-only, append-only: `receive.denyNonFastForwards`, `receive.denyDeletes`, one non-merge commit per event.
- Mixed-hash push fails closed (sha256→sha1 = exit 128); same-hash push = exit 0 (S-1).

## Open seam
The `head_effect` field already distinguishes ADVANCE/PRESERVE, so adding the 3rd ref later (promote a
subset of PRESERVE authorizations to ADVANCE-on-`authorization_head`) is purely additive — no 1.0 contract
is rewritten. → 1.x permission system.

## UI/copy rule (binding) [App C §C.1.1]
Even with two refs, the UI MUST distinguish **Authorized vs Accepted**. It is FORBIDDEN to render an
authorization (worker dispatch / macro merge) as "accepted/completed/done". Allowed labels:
*Authorized, Pending execution, Awaiting receipt, Receipt matched, Accepted world state.*
