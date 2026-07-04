# Approval Signing Key Hierarchy (HW-SW-004)

TuringOS approval signatures are sovereignty-bearing. This document fixes the
key hierarchy, custody, and rotation rules for the signing path, and records why
the signing **algorithm** is negotiated out-of-band rather than carried in the
signed payload today.

## Hierarchy (root of trust downward)

1. **Device key** — machine-scoped root held in the OS keyring
   (`SignatureRoute::OsKeyring`, backed by `secret-tool` / platform secret
   service). The device key never leaves the keyring; the process reads a
   handle, not exportable plaintext. It is the anchor that binds an approval
   signing key to a physical operator machine.

2. **Approval signing key** — an Ed25519 key, **per-sovereign** (one per
   authority identity/epoch), used to sign the canonical `ApprovalPayload`
   bytes. Its public half is published as an `AuthorityKeyRecord`
   (key_id + authority_epoch + route + verifying_key); verification trusts the
   record, never an envelope-provided public key. The private half lives behind
   the device key (OsKeyring) in production and, for development only, in a
   `0600` local-file store (`SignatureRoute::LocalFileDev`, which is the only
   route that exports plaintext key material and is never a production route).

3. **Future hardware-backed keys** — reserved, not yet wired to a device:
   - **AK** (attestation key) and TPM/secure-**enclave**-resident keys, which
     sign without ever exposing private material.
   - **YubiKey** PIV keys (`SignatureRoute::HardwareFuture` today; a concrete
     `YubiKeyPiv` route variant is deferred to device integration to avoid
     churning the signed-byte wire vocabulary). See `src/yubikey.rs` (feature
     `yubikey`): with no device present every operation returns
     `HardwareBackendUnavailable` and never panics.

## Custody and the never-on-tape rule

- Private key material is **never on tape**: no signing seed, keyring secret, or
  YubiKey PIN is ever written to the git tape, an approval card, a
  `SignatureEnvelope`, or any evidence artifact. Only public
  `AuthorityKeyRecord`s and signatures are tape-visible.
- Plaintext export is a backend property (`exports_plaintext_key()`); only
  `LocalFileDev` returns `true`, and it is dev-only. OsKeyring, InMemoryTest, and
  hardware routes never export plaintext.
- Localized display copy is deliberately outside the signed payload.

## Rotation

- **Rotation** is expressed through `authority_epoch`: a new epoch means a new
  `AuthorityKeyRecord` and a new approval signing key; the trusted-key set is
  looked up by `(key_id, authority_epoch, route)`, so an old key cannot sign for
  a new epoch and a rotated key cannot back-sign an old epoch.
- The device key rotates by re-provisioning the OS keyring entry; hardware keys
  rotate by re-enrolling the slot. Rotation never rewrites historical signed
  bytes — old signatures remain verifiable against their epoch's record.

## Algorithm identity and the schema v3 deferral

The signing route already rides the signed canonical bytes
(`ApprovalPayload.signature_route`), so a route swap changes the bytes and the
signed hash and is caught by verification. The **algorithm** does **not** ride
the payload today.

Adding an `algorithm` field to `ApprovalPayload` would be a **schema v3** wire
break (the payload uses `#[serde(deny_unknown_fields)]` and a fixed
`approval_payload.v2` schema id). That change is **deferred** and recorded as a
PlanLoop grilling item. Until then, algorithm identity binds out-of-band via:

- `SigningBackend::supported_algorithms()` (default Ed25519-only), and
- `negotiate(route, algorithm, backend)` run **before** signing, which errors
  (`RouteAlgorithmUnsupported`) rather than silently swapping route or
  downgrading algorithm, producing a `NegotiatedRoute` whose
  `assert_matches_card` re-checks the route against the signed payload
  (`NegotiationIdentityMismatch` on disagreement).

When schema v3 lands, the negotiated algorithm should move into the signed
payload so it rides the same bytes as the route.
