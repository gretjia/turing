# ADR-0002 — The append envelope (7 fields, 5 load-bearing)

**Status:** Accepted (Stage 0). **Layer:** 3. **Contract:** `contracts/append_envelope.md`.

## Context
The >1.0 reference mandates a 7-field envelope all load-bearing from day one (multi-writer-first). 1.0 is
single-writer; it needs only the subset that closes the loop, while keeping the multi-writer shape open.

## Decision
Carry all 7 fields; make **5 load-bearing** (`prev_tape_tip`, `event_schema_id`, `payload_hash`,
`head_effect`, `accepted_head_before`) and **2 reserved** (`writer_id` fixed to the single writer,
`authority_epoch` deferred/not enforced). Enforce a **local guard**: FF-only, schema-known, registry-derived
`head_effect`, `payload_hash` match, single-writer identity, `accepted_head_before` ancestor-of-`tape_tip`.
One non-merge commit per event.

## Consequences
- Activating `writer_id` identity + `authority_epoch` fencing is additive (1.x), no migration.
- The local guard promotes to a server `pre-receive` hook later — a deployment change, not a contract rewrite.

## Constitution
Art. 0.2 / 0.3.
