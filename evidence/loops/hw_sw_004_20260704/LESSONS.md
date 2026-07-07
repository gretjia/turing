# LESSONS — HW-SW-004..006 (security audit REFLECT step)

Verdict driving these rules: SECURE, no merge blockers; three hardening items
applied post-gate. Rules for future signing-path atoms:

1. **Algorithm-binding invariant until schema v3.** While the algorithm does
   not ride the signed payload bytes, the trusted-key registry lookup
   `(key_id, authority_epoch, signature_route)` MUST map to exactly one
   algorithm. No second-algorithm key (e.g. EcdsaP256) may enter the
   `AuthorityKeySet` on any route until schema v3 binds algorithm into the
   signed bytes. State the invariant in the security doc, not just in code
   comments.

2. **Advisory-vs-control distinction.** A negotiation/policy API that `sign()`
   does not require is ADVISORY, not a runtime control. Say so explicitly in
   both the doc and the API doc comment, and name the planned enforcement
   close (`sign_negotiated(&NegotiatedRoute, card)` wrapper, additive,
   deferred). Never let a reader mistake a call-site convention for a
   cryptographic guarantee.

3. **Tamper suites must include key-substitution classes, not only byte
   flips.** Flipping bytes in existing fields misses the attack where a
   mathematically valid attacker artifact is substituted wholesale (class (g):
   envelope verifying_key + fingerprint replaced with an attacker keypair,
   key_id/epoch/route unchanged). The defense is the registry cross-check
   (record fields vs envelope fields), and it must carry the same seeded
   >=1024-case discipline as the byte-flip classes.
