# TuringOS 1.0 — Frozen Project Contracts (Stage 0 baseline)

> **Governance placement (read first).** Everything in `contracts/` is a **versioned PROJECT contract,
> SUBORDINATE to the constitution** — NOT "law", NOT a constitution amendment. The constitution governs THE
> MACHINE; these contracts govern the event/state shape of ONE project loop on the machine.
> Slogan: *"Constitution governs the machine. Project Spec governs one project on the machine."*

## Contracts (the small baseline — plan §6.1 B-1…B-5)
| File | Pins | Plan ref |
|---|---|---|
| `refs.md` | B-1 — the two refs (`tape_tip` + `accepted_head`); no 3rd ref | App C §C.1, Art. 0.4 |
| `append_envelope.md` | B-2 — 7-field envelope, 5 load-bearing; local guard | App C §C.2.3, Art. 0.2/0.3 |
| `event_registry.json` + `.md` | B-3 — 18 events, 3 classes, ADVANCE/PRESERVE (PROVISIONAL) | App C §C.3 |
| `predicate_set.md` | B-4 — the 9 mechanical checks; no quality/taste | App C §C.3.2, Art. I.1 |
| `capsule.schema.json` + `receipt.schema.json` | B-5 — Shielded Capsule + adapter-agnostic Receipt | App B, Art. III/I.1 |
| `codec_policy.md` | `turingos.jcs.v1` — JCS + ASCII keys + no floats | App C §C.2.3 |
| `approval_card.md` | ApprovalCard byte/hash model + SigningBackend seam | App B §B.4 |
| `INTERFACES.md` | the frozen Python API surface (build glossary) | derived from plan §4.1 |

## ADRs
See `docs/adr/` — one ADR per contract, plus **ADR-WORKER-001** (the cited Worker-role ADR).

## Binding wording (verbatim, replaces prior-plan text)
1. **Worker** is a TuringOS 1.0 **PROJECT role defined by ADR-WORKER-001**; **Art. V.1.2 defines ArchitectAI, not Worker AI.**
2. **ASCII-only keys** are a versioned 1.0 **CODEC POLICY**; change = schema migration + project ADR, not a constitution amendment.
3. **Registry** is the **authoritative versioned PROJECT contract, subordinate to the constitution** — never "law".
4. **WorkGraph = derived projection** of serialized `q_t` + `tape_t` + declared Macro observations (never `q_t = WorkGraph`).
5. **ApprovalCard:** one `canonical_bytes`; `visible_card_hash` + `signature` are DERIVED from it, never byte-equal.
6. **Identity prefix** is ASCII `mu:` (not Greek `μ:`) — CLAUDE.md binding override.

## Forbidden — the 临时违宪 release audit (never ship these)
failure off-Tape · projection as hidden truth · blackbox bypassing the Predicate · accepted state not
rebuildable from Tape · NL faking a hard gate · overwriting/deleting history · mistaking project Spec for the constitution.

## Freeze status
The 18-event registry count is **PROVISIONAL** and is frozen ONLY after Stage-1's S-7 validates the first
E2E loop. Until then, treat the count as open.
