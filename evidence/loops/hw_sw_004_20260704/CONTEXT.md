# CONTEXT — HW-SW-004..006 Signing Hardening (Phase 2, secure OS roadmap)

Route: turing_full / plan lite / Tier 1 (high_risk) / horizon on. Founder authorized Phase 2
implementation 2026-07-04 ("I authorize you to implement as your original plan"). Draft commits on
branch turing/phase02-signing-hardening (single branch for the 3 sequential atoms — deviation from
the roadmap's 3-worktree plan, justified: 006 depends on 004, no parallelism to gain). Branched from
Phase 1 tip 4cedcdb so freeze manifest + audit scripts are present. Merge = sovereign decision.

## Verified API ground truth (librarian extraction 2026-07-04, crates/turing-approval/src/lib.rs)
- APPROVAL_PAYLOAD_SCHEMA_ID = "approval_payload.v2" (l.22). ApprovalPayload (35-44) has
  #[serde(deny_unknown_fields)] and fields: schema_id, approval_id, authority_epoch, action,
  subject_id, evidence_digests, risk_class, signature_route: SignatureRoute.
  ⇒ THE ROUTE ALREADY RIDES THE SIGNED BYTES. Adding an algorithm field = wire-breaking schema bump
  (v3) = OUT OF SCOPE (phase doc: stop & escalate). Algorithm identity binds via trusted-key record
  + negotiate()-before-sign; schema-v3 question recorded for PlanLoop grilling.
- ApprovalCard (52-56, private fields, .payload()/.with_display_copy()); canonical_bytes() (85) via
  turing_contracts::jcs::canonicalize; byte_surfaces() (99-109) → ApprovalByteSurfaces (112-119)
  fields: canonical_bytes, visible_card_hash_bytes, signed_bytes, gate_replay_bytes,
  visible_card_hash — the four byte surfaces are currently identical clones by construction.
- trait SigningBackend (181-202): key_id(), route(), exports_plaintext_key() (HAS DEFAULT — copy
  this pattern), sign(&ApprovalCard)->Result<SignatureEnvelope,SigningError>,
  authority_key_record(epoch), verify(card, sig, &AuthorityKeySet). `dyn SigningBackend` used
  NOWHERE in workspace — default method addition is safe.
- SignatureRoute (24-31): None, OsKeyring, LocalFileDev, InMemoryTest, HardwareFuture. Not
  non_exhaustive. Do NOT add variants this atom (wire vocabulary); YubiKey skeleton reports
  route() = HardwareFuture; concrete YubiKeyPiv variant deferred to device integration.
- SigningError (781-815): 9 variants incl. HardwareBackendUnavailable{slot_id}. Not non_exhaustive;
  NO exhaustive match on SigningError anywhere (grep-verified; only construction + one
  matches!(..{ .. })) — adding 2 variants is safe.
- Shared verify: verify_signature_with_authority_keys(card, signature, trusted_keys,
  expected_key_id) (921-988) — checks envelope schema, key_id, epoch, ROUTE match, recomputed
  digest(canonical_bytes) vs signed_payload_hash, trusted-key lookup by (key_id, epoch, route),
  then ed25519 verify. This is the gate-equivalent surface for tests.
- Real gate: crates/turing-daemons/src/lib.rs::sign_and_verify_approval (1699-1716) — OsKeyring-only
  route restriction + sign-then-self-verify before tape append. turing-daemons is OUT OF SCOPE
  (read-only); tests exercise verify_signature_with_authority_keys instead.
- Deterministic test seam: InMemoryTestSigningBackend::new(key_id) (257, signing) /
  ::verifier(key_id) (265, verify-only) share a process-global keyring keyed by key_id string.
- Cargo.toml: exact-pinned (=) deps; NO proptest anywhere in workspace; dev-deps only tempfile.
  DECISION: zero new dependencies — property suite uses a seeded in-file xorshift PRNG, ≥1024
  cases; Cargo.lock must show ZERO diff. [features] yubikey = [] (empty, no deps) is allowed.
- Existing tests to keep green: crates/turing-approval/tests/approval_card.rs (6 tests incl.
  approval_bytes_four_way_identity, epoch/forged-key/tamper rejections).
- Freeze manifest (Phase 1) pins crates/turing-approval/src/lib.rs sha256
  ce9d4676086aa9fb46270d80f1f958a432d9754f34d93e96c31f12dca6920751 — editing lib.rs REQUIRES the
  REPIN ceremony: update substrate_freeze_manifest.toml in a commit whose message body contains
  "REPIN:" + rationale. This is the guard working as designed, not an obstacle.
- Constitution: never touch; sha a0174ef8a2be6914f86ea8e594e022c7ca6a4221ed63535d65a997e096ca3ad0.
- Ceiling: ADDRESSED, pending sovereign accept. Commit style: conventional short subject (≤50
  chars), required exact strings in body (repo hook enforces).
