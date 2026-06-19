# Contract: The Append Envelope (B-2, ADR-0002) [Art. 0.2 / 0.3]

**Status:** frozen Stage-0 baseline. One micro Git commit per sovereignty-boundary change (no merge
commits, one event per commit). The 7-field envelope is present from day one; **5 are load-bearing in 1.0**,
2 are reserved forward-compat seams (`writer_id` fixed, `authority_epoch` deferred).

| Field | 1.0 status | Rule |
|---|---|---|
| `prev_tape_tip` | **REQUIRED** (load-bearing) | FF parent check: `parent == prev_tape_tip`. Reject non-FF. |
| `event_schema_id` | **REQUIRED** (load-bearing) | closed-world: `unknown_event_type => reject`. Identifies the event type + payload schema. |
| `payload_hash` | **REQUIRED** (load-bearing) | `= content_digest = sha256(JCS(payload))`. Recomputed and matched at append + replay. |
| `head_effect` | **REQUIRED, registry-derived** (load-bearing) | taken from `registry[event_type].class` → ADVANCE\|PRESERVE. **REJECT** any envelope whose carried `head_effect` disagrees. Never writer-trusted. |
| `accepted_head_before` | **REQUIRED** (load-bearing, audit/consistency) | the `accepted_head` the writer observed; MUST be ancestor-of-`tape_tip`. |
| `writer_id` | **RESERVED, fixed** | single active sovereign writer; recorded for audit/handoff. Position reserved for multi-writer identity check (1.x). |
| `authority_epoch` | **RESERVED, deferred** | not enforced in 1.0 (no fencing). Position reserved so lease/epoch activates later with no envelope migration (1.x). |

## Local guard checks 1.0 DOES enforce (the subset of the future server authority-guard)
1. **FF-only**: `parent == prev_tape_tip` (reject stale/non-FF → reread/retry path).
2. **schema-known**: `event_schema_id` ∈ registry, else reject.
3. **head_effect registry-derived**: carried value must equal `registry[type].class`; else reject.
4. **payload_hash match**: recompute `sha256(JCS(payload))`, must equal `payload_hash`; else reject.
5. **single-writer identity**: append admitted only if `writer_id == current_sovereign_writer` (from the
   latest boot/HandoffGenerated event on the Tape); wrong-writer rejected by the guard, not by convention (S-2).
6. **accepted_head_before** must be an ancestor of `tape_tip`.

## Advance rule
`accepted_head` advances to the new commit **iff** `head_effect == ADVANCE` (i.e. class == SOVEREIGN_ACCEPT)
**AND** the deterministic Predicate result for the gating event `== PASS`. Otherwise `accepted_head` is
unchanged and only `tape_tip` advances (failure-is-state).

## Open seam
The 7-field shape is the multi-writer-safe shape; activating `writer_id` identity + `authority_epoch`
fencing is additive, no migration (1.x). Promoting the local guard to a server `pre-receive` hook is a
deployment change, not a contract rewrite.
