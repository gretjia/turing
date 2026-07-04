# PREDICATE — HW-SW-004..006 (all commands from worktree root; gate passes first try when correct)

## Atom HW-SW-004 — route+algorithm negotiation + key hierarchy doc
A1. `cargo test -p turing-approval route_negotiation` green, covering AT MINIMUM:
    - negotiate(SignatureRoute::OsKeyring, SignatureAlgorithm::Ed25519, &OsKeyringSigningBackend::new("k"))
      → Ok(NegotiatedRoute{route: OsKeyring, algorithm: Ed25519})
    - negotiate(_, EcdsaP256, <any default backend>) → Err(SigningError::RouteAlgorithmUnsupported{..})
      (default supported_algorithms() = [Ed25519])
    - negotiate(SignatureRoute::None, ..) → Err(RouteAlgorithmUnsupported)
    - NegotiatedRoute::assert_matches_card(&card) → Ok iff card.payload().signature_route == self.route,
      else Err(SigningError::NegotiationIdentityMismatch{expected, observed})
    - route-rides-bytes proof: build a card, get canonical_bytes(), assert the bytes contain
      `"signature_route"` and the route's serialized value; assert two cards differing ONLY in
      signature_route produce different canonical_bytes AND different signed_payload_hash.
A2. Additive-only lib.rs delta: `mod route_negotiation;` + `pub use route_negotiation::{...};`,
    exactly 2 new SigningError variants (RouteAlgorithmUnsupported{route: SignatureRoute,
    algorithm: SignatureAlgorithm}, NegotiationIdentityMismatch{expected: SignatureRoute,
    observed: SignatureRoute}), one default trait method
    `fn supported_algorithms(&self) -> &'static [SignatureAlgorithm] { &[SignatureAlgorithm::Ed25519] }`.
    EDIT-FORBIDDEN regions of lib.rs (zero diff lines): ApprovalPayload struct, ApprovalCard,
    canonical_bytes(), byte_surfaces(), ApprovalByteSurfaces, APPROVAL_PAYLOAD_SCHEMA_ID,
    verify_signature_with_authority_keys, existing SignatureRoute variants, all existing backends.
    Check: `git diff 4cedcdb..HEAD -- crates/turing-approval/src/lib.rs` reviewed + grep-asserted
    (e.g. `git diff ... | grep -c '^-'` — deletions only allowed if pure whitespace/none; record count).
A3. docs/security/key_hierarchy.md exists; must contain strings: "device key",
    "approval signing key", "never on tape", "rotation", "AK", "enclave", and a "schema v3" note
    stating algorithm-in-payload requires a schema bump (deferred, PlanLoop grilling item).
A4. Existing suite untouched-green: `cargo test -p turing-approval --test approval_card`.

## Atom HW-SW-005 — four-surface identity + mutation rejection (ZERO new deps)
B1. `cargo test -p turing-approval --test prop_approval_byte_surfaces` green:
    - In-file seeded PRNG (xorshift64* or similar, const SEED: u64 recorded in the file; no external
      crate). N ≥ 1024 cases per property.
    - honest_path_identity_holds: N random valid cards (random field contents, schema_id fixed v2,
      route InMemoryTest) → byte_surfaces(): canonical_bytes == visible_card_hash_bytes ==
      signed_bytes == gate_replay_bytes; sign via InMemoryTestSigningBackend::new;
      verify_signature_with_authority_keys → Ok. Completeness = 1: ZERO honest rejections allowed.
    - mutation_is_rejected, N cases across ALL these tamper classes (cycle through):
      (a) payload field tamper: mutate one byte in one payload string field after signing (rebuild
          card with tampered field) → verify Err; (b) envelope signed_payload_hash tamper → Err;
      (c) signature byte flip → Err; (d) authority_epoch mismatch → Err; (e) route swap
      (payload.signature_route changed post-sign) → Err; (f) key_id swap → Err.
      ZERO acceptances of tampered candidates. All rejections are Err — no panic (any panic fails the test).
B2. scripts/audit-approval-bytes-equivalence.sh extended to also run the B1 test; script still
    exits 0: `./scripts/audit-approval-bytes-equivalence.sh`.
B3. `git diff 4cedcdb..HEAD -- Cargo.lock` → EMPTY (zero-dep discipline held).

## Atom HW-SW-006 — feature-gated YubiKey skeleton (no device, no new deps)
C1. crates/turing-approval/Cargo.toml gains ONLY `[features]\nyubikey = []`.
C2. src/yubikey.rs behind `#[cfg(feature = "yubikey")]`: YubiKeySigningBackend implements
    SigningBackend; route() = SignatureRoute::HardwareFuture (concrete YubiKeyPiv variant deferred —
    documented in key_hierarchy.md); supported_algorithms() = &[Ed25519, EcdsaP256]; with no device
    every sign/authority_key_record/verify returns Err(SigningError::HardwareBackendUnavailable{..})
    — never panics. Tests (same feature gate): backend-unavailable path;
    negotiate(HardwareFuture, EcdsaP256, &yubikey_backend) → Ok (explicit fallback exists here);
    negotiate(_, EcdsaP256, &InMemoryTestSigningBackend::new("k")) → Err (no silent swap anywhere).
C3. Feature matrix green: `cargo test -p turing-approval` AND
    `cargo test -p turing-approval --features yubikey` AND
    `cargo build -p turing-approval --features yubikey`.

## Phase gate (after all atoms)
G1. `cargo test -p turing-replay --test replay_determinism` (SG-19 untouched)
G2. `./scripts/audit-approval-bytes-equivalence.sh`
G3. REPIN ceremony: substrate_freeze_manifest.toml updated with new lib.rs (and Cargo.toml if
    pinned) sha256 in a commit whose body contains `REPIN:` + rationale; then
    `./scripts/audit-substrate-freeze.sh` → exit 0 and `bash .githooks/pre-commit` → exit 0.
G4. `./scripts/audit-forbidden-files.sh --staged` → 0 on every commit (hook enforces).
G5. `bash PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/governance/verify_alignment.sh` → GREEN
    (run with cwd = workspace root /home/zephryj/turingos_backup/work).
G6. `cargo test --workspace` green (run ONCE at phase end; long — allow up to 20 min).

## Red-first (R-REDFIRST)
Commit tests first (route_negotiation tests + prop_approval_byte_surfaces skeleton with SEED and
at least the honest-path + one mutation class wired to the not-yet-existing API) → red run captured
to evidence/loops/hw_sw_004_20260704/red_first.txt → commit → implement to green. Never squash red.

## Mini-Recovery triggers
Any tampered candidate ACCEPTED (worst signal — halt + escalate to founder immediately, do not
self-fix silently); any honest candidate rejected (Completeness=1 broken); SG-19 replay break;
schema_id or edit-forbidden region appears in diff; Cargo.lock diff non-empty; forbidden-file trip;
same-cause double failure; any command touching constitution_root_law.md.
