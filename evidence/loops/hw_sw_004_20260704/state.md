# STATE — HW-SW-004..006 signing-path hardening

Branch: turing/phase02-signing-hardening (from Phase 1 tip 4cedcdb).
Git identity: TuringLoop Implementer <zephryj@icloud.com> (local).
Ceiling: ADDRESSED (pending sovereign accept).

## RED-FIRST (R-REDFIRST) — DONE
- Wrote tests/route_negotiation.rs (A1) + tests/prop_approval_byte_surfaces.rs
  (SEED=0x5347313941503150 xorshift64*, honest-path + tamper class (a)).
- Combined run failed to compile (missing negotiate/NegotiatedRoute/
  SignatureAlgorithm/2 SigningError variants/supported_algorithms). cargo
  exit 101. Captured -> red_first.txt.
- Commit: (see git log) "test: hw-sw-004-005 red-first signing tests".

## Checkpoint 1 — HW-SW-004 : DONE
- src/route_negotiation.rs: SignatureAlgorithm{Ed25519,EcdsaP256},
  NegotiatedRoute{route,algorithm} with identity_field() + assert_matches_card(),
  negotiate(route, algorithm, &dyn SigningBackend) — None route / route!=backend.route()
  / unsupported algorithm all -> Err(RouteAlgorithmUnsupported); no silent swap.
- lib.rs ADDITIVE: `mod route_negotiation;` + `pub use {negotiate, NegotiatedRoute,
  SignatureAlgorithm}`; 2 SigningError variants (RouteAlgorithmUnsupported,
  NegotiationIdentityMismatch) + Display arms; supported_algorithms() default (Ed25519).
  git diff 4cedcdb: 29 additions, 0 deletions, no forbidden region redefined.
- docs/security/key_hierarchy.md: all A3 strings present (device key / approval
  signing key / never on tape / rotation / AK / enclave / schema v3).
- A1 route_negotiation 7 passed; A4 approval_card 6 passed; A2 additive-only verified.

## Checkpoint 2 — HW-SW-005 : DONE
- tests/prop_approval_byte_surfaces.rs complete: SEED=0x5347313941503150,
  xorshift64* PRNG, no external crate. honest_path_identity_holds (1024 cases:
  four surfaces identical + honest verify Ok, zero rejections). mutation_is_rejected
  (1024 cases cycling all six tamper classes (a) payload field, (b) signed_payload_hash,
  (c) signature byte flip, (d) authority_epoch, (e) route swap, (f) key_id swap;
  zero acceptances, no panic).
- scripts/audit-approval-bytes-equivalence.sh extended with an explicit
  --test prop_approval_byte_surfaces run; script exit 0.
- B3: git diff 4cedcdb -- Cargo.lock EMPTY (zero-dep discipline held).

## Checkpoint 3 — HW-SW-006 : DONE
- Cargo.toml: [features] yubikey = [] (empty, no deps).
- src/yubikey.rs behind #[cfg(feature="yubikey")]: YubiKeySigningBackend impl
  SigningBackend; route()=HardwareFuture; supported_algorithms()=[Ed25519,EcdsaP256];
  sign/authority_key_record/verify all Err(HardwareBackendUnavailable), never panic.
  Feature-gated tests: unavailable path; negotiate(HardwareFuture,EcdsaP256,&yubikey)=Ok;
  negotiate(_,EcdsaP256,&InMemoryTest)=Err (no silent swap).
- lib.rs additive: #[cfg(feature="yubikey")] pub mod yubikey; (diff 31 add, 0 del).
- C3: default suite green; --features yubikey +3 tests green; build --features
  yubikey green. Cargo.lock zero-diff.

## REPIN + PHASE GATE : DONE
- REPIN: substrate_freeze_manifest.toml lib.rs sha256
  ce9d46...20751 -> c76965...c3a7 (commit dd32754, body has "REPIN:"). Cargo.toml
  left unpinned (out of REPIN scope; manifest pins no Cargo.toml today).
- Phase gate (transcript in gate_receipt.txt), all exit 0:
  G1 replay_determinism (SG-19) ok; G2 audit-approval-bytes-equivalence ok;
  G3a audit-substrate-freeze + G3b .githooks/pre-commit ok; G4 forbidden-files
  --staged ok; G5 verify_alignment.sh (cwd=work root) GREEN; G6 cargo test
  --workspace ok, 0 failures.
- Cargo.lock zero-diff vs 4cedcdb throughout.

## Commit SHAs
- a4c9bd2 test: hw-sw-004-005 red-first signing tests
- 69d0bb3 feat: hw-sw-004 route negotiation
- 1ca8e2b feat: hw-sw-005 four-surface mutation suite
- 77a5d12 feat: hw-sw-006 yubikey skeleton
- dd32754 chore: hw-sw-004..006 repin approval lib.rs (REPIN:)
