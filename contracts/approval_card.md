# Contract: ApprovalCard byte/hash model + SigningBackend seam (B-5/B.4, ADR-0007)

**Status:** frozen Stage-0 baseline. The prior plan's four-way byte-equality
(`canonical_bytes == visible_card_hash == signed == gate-consumed`) is a **mathematically wrong category
error** and is retired. A hash and a signature are *functions of* the bytes, never byte-equal to them.

## The corrected model (binding)
```
canonical_bytes   := JCS(load-bearing signed fields, ASCII keys, no floats)   # the ONE signed input
                                                                              # display/localization copy EXCLUDED
visible_card_hash := sha256(canonical_bytes)        # DERIVED digest, shown to the human (NOT the bytes)
signature         := sign(canonical_bytes)          # DERIVED over the SAME bytes (NOT the bytes)
gate / replay     := re-derive sha256(canonical_bytes) AND verify(signature, canonical_bytes)
                                                    # consumes the SAME canonical_bytes; re-derives + re-verifies
```

## Signed load-bearing fields (in `canonical_bytes`)
`action_kind`, `target` (OID/locator), `evidence_set_digest`, `risk_class`, `expires_at`, `nonce`,
Micro context (`tape_tip`, `accepted_head`, `authority_epoch`), `signature_route`, `key_id`.
**EXCLUDED:** display copy, EN/中文 explanation, renderer layout — these perturb none of the derived values.

## Invariants
1. Exactly **one** `canonical_bytes`.
2. `visible_card_hash` and `signature` are **derived from** it; not byte-equal to it or to each other.
3. The gate and replay both **re-derive** the hash and **verify** the signature over that same `canonical_bytes`.
4. **Fail-closed** [Art. I.1]: expiry, revocation, nonce replay, signer change, target-head change,
   evidence-set change, and `authority_epoch` change each fail closed. An unavailable/revoked signer cannot merge.

## SigningBackend seam (open interface)
- `SigningBackend` is abstracted from day one. **1.0 implementation:** an in-process deterministic signer
  (`InProcSigningBackend`) sufficient for local fake-worker E2E; **`OSKeyringSigningBackend` (1.x)** and
  **`HardwareSigningBackend` (2.0)** are reserved backends behind the same seam — never a rewrite.
- `key_id`, `authority_epoch`, `signature_route` are first-class signed fields, so a stronger authority
  path or hardware route can be added without rewriting `canonical_bytes`, the hash derivation, or replay.

## 1.0 scope note
1.0 needs ONLY this derivation. Real OS-keyring/hardware signing is BLOCKED (credentialed → BLK-4) and out
of 1.0 loop-completeness scope; the merge=human-confirmed act is recorded as a PRESERVE Tape event.
