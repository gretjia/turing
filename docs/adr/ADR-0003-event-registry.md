# ADR-0003 — 18-event registry, 3 classes (PROVISIONAL)

**Status:** Accepted-PROVISIONAL (Stage 0). **Layer:** 3. **Contract:** `contracts/event_registry.{json,md}`.

## Context
The >1.0 reference is a 46-event / 6-class closed "law". 1.0 needs only the journey-derived subset and the
one distinction that matters: *does this advance accepted state, or not.*

## Decision
Ship **18 journey-derived events** in **3 classes** (`SOVEREIGN_ACCEPT`/ADVANCE,
`PROPOSAL`/PRESERVE, `OBSERVATION`/PRESERVE). Closed-world (`unknown_event_type => reject`). `head_effect`
is registry-derived, never writer-trusted. Names append-only, never renumbered. The count is **PROVISIONAL**
and frozen ONLY after Stage-1 S-7 validates the first E2E loop.

## Consequences
- Growing toward the 46-event space is additive (1.x); never a frozen law.
- Re-splitting `AUTHORIZATION`/`RECEIPT`/`FAILURE` classes accompanies the future 3rd ref.

## Constitution
Subordinate to `constitution.md`; cites Art. 0.2/0.4, I.1 (predicate gates SOVEREIGN_ACCEPT).
