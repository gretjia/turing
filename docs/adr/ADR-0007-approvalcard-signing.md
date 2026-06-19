# ADR-0007 — ApprovalCard byte/hash model + SigningBackend seam

**Status:** Accepted (Stage 0). **Layer:** 3. **Contract:** `contracts/approval_card.md`.

## Context
The prior plan's four-way byte-equality (`canonical_bytes == visible_card_hash == signed == gate-consumed`)
is a **mathematical category error** — a hash/signature are functions of the bytes, not byte-equal to them.

## Decision
One `canonical_bytes` (JCS of signed load-bearing fields, ASCII keys, no floats; display/localization copy
EXCLUDED). `visible_card_hash = sha256(canonical_bytes)` (derived, shown to human). `signature =
sign(canonical_bytes)` (derived). The gate/replay consume the SAME `canonical_bytes`, re-derive the hash,
re-verify the signature. Fail-closed on expiry/revocation/nonce-replay/signer-change/target-head-change/
evidence-set-change/epoch-change. `SigningBackend` abstracted day one: 1.0 ships `InProcSigningBackend`;
`OSKeyringSigningBackend` (1.x) and `HardwareSigningBackend` (2.0) are reserved behind the seam.

## Consequences
- `key_id`/`authority_epoch`/`signature_route` are first-class signed fields → stronger backends are additive.
- Real keyring/hardware signing is BLOCKED (BLK-4) and out of 1.0 loop-completeness; merge=human-confirmed
  is recorded as a PRESERVE Tape event.

## Constitution
Art. I.1 (fail-closed hard gates), Art. V (open meta seam).
