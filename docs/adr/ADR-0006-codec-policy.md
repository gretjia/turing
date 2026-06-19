# ADR-0006 — Canonical codec policy `turingos.jcs.v1`

**Status:** Accepted (Stage 0). **Layer:** 3 (project codec policy). **Contract:** `contracts/codec_policy.md`.

## Context
Art. I.1 requires *some* hard, byte-deterministic codec. The prior plan wrongly framed **ASCII specifically**
as constitutional. ASCII is one implementation of byte-determinism — a project policy.

## Decision
`turingos.jcs.v1`: RFC 8785 (JCS) canonicalization; **ASCII-only load-bearing keys** (non-ASCII key →
reject); **no floats** (load-bearing numbers are integers; any float → reject); `content_digest =
"sha256:"+hex(sha256(canonical_bytes))`. Identity split: `event_id = "mu:"+oid` (ASCII `mu:` per CLAUDE.md
override of Greek `μ:`), distinct from the semantic `content_digest`. For ASCII keys, Python `sorted()` ==
RFC 8785 UTF-16 order (a property the ASCII policy buys us).

## Consequences
- Changing the codec = schema migration + project ADR revision, **NOT** a constitution amendment unless
  `constitution.md` itself changes.
- Byte-determinism makes replay byte-equal (S-1/S-7).

## Constitution
Art. I.1 (byte-deterministic gate). NOT Art.-level for ASCII (§5.6 citation discipline).
