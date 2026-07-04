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

## Checkpoint 3 — HW-SW-006 : PENDING
## REPIN + PHASE GATE : PENDING
