//! HW-SW-005 B1 — property suite over the four approval byte surfaces.
//!
//! ZERO external dependencies: the randomness is a seeded in-file xorshift64*
//! PRNG (const SEED below), so Cargo.lock stays byte-identical. Two invariants:
//!   1. honest cards: the four byte surfaces are identical and a real signature
//!      verifies (Completeness = 1, zero honest rejections).
//!   2. tampered cards: every tamper class is rejected (Soundness, zero tamper
//!      acceptances), and no verification path ever panics.
//!
//! RED-FIRST skeleton: honest-path property + tamper class (a). The remaining
//! tamper classes (b)-(f) and the ≥1024 mutation-case sweep land in HW-SW-005.

use turing_approval::{
    ApprovalCard, ApprovalPayload, AuthorityKeySet, DisplayCopy, InMemoryTestSigningBackend,
    SignatureEnvelope, SignatureRoute, SigningBackend, verify_signature_with_authority_keys,
};

/// Deterministic seed for the in-file PRNG. Recorded so every run is
/// reproducible without any external crate.
const SEED: u64 = 0x5347_3139_4150_5031; // "SG19APP1" flavored, nonzero.

/// Minimum cases per property (predicate B1 requires N >= 1024).
const CASES: usize = 1024;

/// xorshift64* — a self-contained PRNG (no external dependency).
struct Rng {
    state: u64,
}

impl Rng {
    fn new(seed: u64) -> Self {
        // xorshift64* requires a nonzero state.
        Rng {
            state: if seed == 0 { 0x9E37_79B9_7F4A_7C15 } else { seed },
        }
    }

    fn next_u64(&mut self) -> u64 {
        let mut x = self.state;
        x ^= x >> 12;
        x ^= x << 25;
        x ^= x >> 27;
        self.state = x;
        x.wrapping_mul(0x2545_F491_4F6C_DD1D)
    }

    fn below(&mut self, n: u64) -> u64 {
        self.next_u64() % n
    }

    fn ascii_word(&mut self, min_len: usize, max_len: usize) -> String {
        const CHARSET: &[u8] = b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-:./";
        let span = (max_len - min_len + 1) as u64;
        let len = min_len + self.below(span) as usize;
        (0..len)
            .map(|_| CHARSET[self.below(CHARSET.len() as u64) as usize] as char)
            .collect()
    }

    fn hex_digest(&mut self) -> String {
        const HEX: &[u8] = b"0123456789abcdef";
        let body: String = (0..64)
            .map(|_| HEX[self.below(16) as usize] as char)
            .collect();
        format!("sha256:{body}")
    }
}

/// Builds a random but VALID approval card: schema fixed at v2, route
/// InMemoryTest, valid sha256 digests, random contents everywhere else.
fn random_valid_card(rng: &mut Rng) -> ApprovalCard {
    let digest_count = rng.below(3) as usize; // 0..=2
    let evidence_digests = (0..digest_count).map(|_| rng.hex_digest()).collect();
    let payload = ApprovalPayload {
        schema_id: "approval_payload.v2".to_string(),
        approval_id: rng.ascii_word(1, 24),
        authority_epoch: rng.next_u64() % 1_000_000,
        action: rng.ascii_word(1, 24),
        subject_id: rng.ascii_word(1, 32),
        evidence_digests,
        risk_class: rng.ascii_word(1, 4),
        signature_route: SignatureRoute::InMemoryTest,
    };
    ApprovalCard::new(
        payload,
        DisplayCopy {
            title_zh: rng.ascii_word(1, 8),
            body_en: rng.ascii_word(1, 32),
        },
    )
}

/// Signs a card and returns (signature, trusted key set, key_id) for verifying.
fn sign_and_trust(rng: &mut Rng, card: &ApprovalCard) -> (SignatureEnvelope, AuthorityKeySet, String) {
    let key_id = format!("prop-{}", rng.ascii_word(4, 12));
    let backend = InMemoryTestSigningBackend::new(&key_id);
    let signature = backend.sign(card).expect("honest in-memory signature");
    let trusted = AuthorityKeySet::from_record(
        backend
            .authority_key_record(card.payload().authority_epoch)
            .expect("trusted authority key record"),
    );
    (signature, trusted, key_id)
}

#[test]
fn honest_path_identity_holds() {
    let mut rng = Rng::new(SEED);
    for i in 0..CASES {
        let card = random_valid_card(&mut rng);

        let surfaces = card.byte_surfaces().expect("canonical byte surfaces");
        assert_eq!(
            surfaces.canonical_bytes, surfaces.visible_card_hash_bytes,
            "case {i}: canonical vs visible-card-hash bytes diverged"
        );
        assert_eq!(
            surfaces.canonical_bytes, surfaces.signed_bytes,
            "case {i}: canonical vs signed bytes diverged"
        );
        assert_eq!(
            surfaces.canonical_bytes, surfaces.gate_replay_bytes,
            "case {i}: canonical vs gate-replay bytes diverged"
        );

        let (signature, trusted, key_id) = sign_and_trust(&mut rng, &card);
        verify_signature_with_authority_keys(&card, &signature, &trusted, &key_id)
            .unwrap_or_else(|error| panic!("case {i}: honest card rejected: {error}"));
    }
}

#[test]
fn mutation_class_a_payload_field_is_rejected() {
    let mut rng = Rng::new(SEED ^ 0x00A);
    for i in 0..CASES {
        let card = random_valid_card(&mut rng);
        let (signature, trusted, key_id) = sign_and_trust(&mut rng, &card);

        // (a) payload string field tamper: rebuild the card with a mutated
        // `action`, verify the ORIGINAL signature against the tampered card.
        let mut tampered_payload = card.payload().clone();
        tampered_payload.action = format!("{}!tampered", tampered_payload.action);
        let tampered = ApprovalCard::new(tampered_payload, card.display_copy().clone());

        let result =
            verify_signature_with_authority_keys(&tampered, &signature, &trusted, &key_id);
        assert!(
            result.is_err(),
            "case {i}: tamper class (a) payload field was ACCEPTED"
        );
    }
}
