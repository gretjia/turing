//! HW-SW-005 B1 — property suite over the four approval byte surfaces.
//!
//! ZERO external dependencies: the randomness is a seeded in-file xorshift64*
//! PRNG (const SEED below), so Cargo.lock stays byte-identical. Two invariants:
//!   1. honest cards: the four byte surfaces are identical and a real signature
//!      verifies (Completeness = 1, ZERO honest rejections).
//!   2. tampered cards: every tamper class (a)-(f) is rejected (Soundness, ZERO
//!      tamper acceptances), and no verification path ever panics (a panic
//!      fails the test).

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

/// Flips exactly one hex character after `prefix`, keeping valid hex and length
/// (so the field still decodes but is a different value). Never panics.
fn flip_one_hex(field: &str, prefix: &str, rng: &mut Rng) -> String {
    let hex = field.strip_prefix(prefix).unwrap_or(field);
    let mut chars: Vec<char> = hex.chars().collect();
    if chars.is_empty() {
        return field.to_string();
    }
    let idx = rng.below(chars.len() as u64) as usize;
    // Guarantee a real change: '0' -> '1', anything else -> '0'.
    chars[idx] = if chars[idx] == '0' { '1' } else { '0' };
    let flipped: String = chars.into_iter().collect();
    format!("{prefix}{flipped}")
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
fn sign_and_trust(
    rng: &mut Rng,
    card: &ApprovalCard,
) -> (SignatureEnvelope, AuthorityKeySet, String) {
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
        // Completeness = 1: an honest card MUST verify.
        verify_signature_with_authority_keys(&card, &signature, &trusted, &key_id)
            .unwrap_or_else(|error| panic!("case {i}: honest card rejected: {error}"));
    }
}

#[test]
fn mutation_is_rejected() {
    let mut rng = Rng::new(SEED ^ 0xDEAD_BEEF);
    // Cover all six tamper classes; cycle through them across >=1024 cases.
    for i in 0..CASES {
        let card = random_valid_card(&mut rng);
        let (mut signature, trusted, key_id) = sign_and_trust(&mut rng, &card);

        // Default candidate is the honest one; each class perturbs exactly one
        // surface. `cand_card` is what we hand to verify (some classes rebuild
        // the card, others tamper the envelope in place).
        let class = i % 6;
        let cand_card: ApprovalCard = match class {
            0 => {
                // (a) payload string field tamper -> rebuild card, verify old sig.
                let mut p = card.payload().clone();
                p.action = format!("{}!x", p.action);
                ApprovalCard::new(p, card.display_copy().clone())
            }
            1 => {
                // (b) envelope signed_payload_hash tamper.
                signature.signed_payload_hash =
                    flip_one_hex(&signature.signed_payload_hash, "sha256:", &mut rng);
                card.clone()
            }
            2 => {
                // (c) signature byte flip.
                signature.signature = flip_one_hex(&signature.signature, "ed25519:", &mut rng);
                card.clone()
            }
            3 => {
                // (d) authority_epoch mismatch (envelope drifts from payload).
                signature.authority_epoch = signature.authority_epoch.wrapping_add(1);
                card.clone()
            }
            4 => {
                // (e) route swap: payload.signature_route changed post-sign.
                let mut p = card.payload().clone();
                p.signature_route = SignatureRoute::OsKeyring;
                ApprovalCard::new(p, card.display_copy().clone())
            }
            _ => {
                // (f) key_id swap on the envelope.
                signature.key_id = format!("{}-swapped", signature.key_id);
                card.clone()
            }
        };

        let result =
            verify_signature_with_authority_keys(&cand_card, &signature, &trusted, &key_id);
        // Soundness: ZERO tampered candidates may be accepted. All rejections
        // are `Err` (any panic in verify would already have failed the test).
        assert!(
            result.is_err(),
            "case {i}: tamper class ({}) was ACCEPTED",
            (b'a' + class as u8) as char
        );
    }
}
