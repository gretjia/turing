# Contract: `turingos.jcs.v1` — Canonical Codec Policy (F-5, ADR-0006)

**Status:** frozen Stage-0 baseline. **Governance:** Layer-3 PROJECT codec policy — changing it requires a
schema migration + a project ADR revision, **NOT** a constitution amendment unless `constitution.md` itself
changes [plan §5.3 Fix 2; App C §C.2.3]. Art. I.1 requires *some* hard, byte-deterministic codec — it does
not name ASCII; ASCII is one implementation of byte-determinism.

## C-1 — Canonicalization
- `canonical_bytes(payload) = RFC 8785 (JCS)` byte string of the payload JSON object.
- No insignificant whitespace; object keys sorted by UTF-16 code-unit order; minimal string escaping.

## C-2 — ASCII-only load-bearing keys (versioned policy)
- Every **load-bearing key** in a payload MUST be ASCII (`^[\x20-\x7E]+$`, no control chars). A non-ASCII
  load-bearing key is **rejected** by the codec guard (ties S-3 ascii-key guard / GH-6 / NS-01).
- **Property the ASCII policy buys us:** for ASCII-only keys, Python `sorted()` (Unicode code-point order)
  equals RFC 8785 UTF-16 code-unit order — so key sorting is unambiguous and cheap.
- Load-bearing **string values** SHOULD be ASCII; display/localization copy is NOT load-bearing and lives
  OUTSIDE `canonical_bytes` (see `approval_card.md`).

## C-3 — No floats
- Load-bearing numbers MUST be integers. Any JSON float (`number` with a fractional/exponent part, or a
  Python `float`) in a load-bearing payload is **rejected**. Use integers or decimal strings instead.
  (Floats are non-deterministic across platforms — forbidden by byte-determinism.)

## C-4 — Semantic digest
- `content_digest(payload) = "sha256:" + hex(sha256(canonical_bytes(payload)))`.
- The digest is the SEMANTIC identity of a payload; it is recomputed and matched at append and at replay.

## C-5 — Identity split [Art. 0.4]
- `event_id = "mu:" + <git_commit_oid>` — the PHYSICAL Micro-node identity. **ASCII `mu:` prefix**
  (CLAUDE.md binding override of the plan's Greek `μ:`). Pattern `^mu:[0-9a-f]{64}$` (SHA-256 OIDs are 64 hex).
  The OID folds in author/committer/parent/timestamp/object-format and is **never** the semantic digest.
- `content_digest = sha256(JCS(payload))` — the SEMANTIC digest. Distinct from `event_id`.

## C-6 — Determinism contract
- `canonical_bytes` is a pure function of the payload's semantic content; two semantically-equal payloads
  produce byte-identical `canonical_bytes` and identical `content_digest`. This is what makes replay
  byte-equal (S-1 / S-7).
