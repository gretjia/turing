//! PART C.1 lens 6 (authority/boundary finder, INV-9/10/18) — adversarial attack tests
//! against `reducer::apply`, the sole authority for "did a sovereign head advance?"
//! (`crates/turing-kernel/src/reducer.rs`).
//!
//! Attack model: assume every OUTER layer (registry integrity, admission-layer
//! `admit_head_effect`, the append algorithm's registry lookup) has already been
//! bypassed or is buggy, and an attacker can call the pure `reducer::apply` function
//! directly with an arbitrary (`class`, `head_effect`, `product`) triple — including
//! combinations that should be structurally impossible per the closed registry (e.g.
//! `EventClass::Economy` paired with `HeadEffect::Advance`). This is the deepest
//! possible probe of INV-9 ("no code path moves accepted_head off an economy event")
//! because it does not rely on the registry actually being well-formed; it tests the
//! reducer's OWN defensive fallback.
//!
//! No proptest/quickcheck dependency exists in this workspace: this is a hand-rolled
//! exhaustive sweep (the state space is small — 7 classes x 2 head_effects x 3
//! products = 42 combinations) plus a fixed-seed pseudo-random fuzz over `PreState`
//! head values, per the capsule's "no Math.random / no time seed" rule.

use turing_contracts::envelope::{HeadEffect, PredicateProduct};
use turing_contracts::registry::EventClass;

use turing_kernel::reducer::{self, HeadMoved, PreState};

/// Fixed, hard-coded seed (capsule rule: no time/OS randomness). xorshift64* PRNG.
const SEED: u64 = 0x4155_5448_4F52_4954u64; // "AUTHORIT"-ish, arbitrary but fixed.

struct Xorshift64(u64);
impl Xorshift64 {
    fn next_u64(&mut self) -> u64 {
        let mut x = self.0;
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        self.0 = x;
        x
    }
}

fn mu(tag: u64) -> String {
    format!("mu:{:064x}", tag)
}

const ALL_CLASSES: [EventClass; 7] = [
    EventClass::SovereignAccept,
    EventClass::Authorization,
    EventClass::Proposal,
    EventClass::Observation,
    EventClass::Receipt,
    EventClass::Failure,
    EventClass::Economy,
];
const ALL_EFFECTS: [HeadEffect; 2] = [HeadEffect::Advance, HeadEffect::Preserve];
const ALL_PRODUCTS: [PredicateProduct; 3] = [
    PredicateProduct::Pass,
    PredicateProduct::Fail,
    PredicateProduct::NotRun,
];

fn arbitrary_pre(rng: &mut Xorshift64) -> PreState {
    PreState {
        tape_tip: Some(mu(rng.next_u64())),
        authorization_head: if rng.next_u64() % 2 == 0 {
            Some(mu(rng.next_u64()))
        } else {
            None
        },
        accepted_head: if rng.next_u64() % 2 == 0 {
            Some(mu(rng.next_u64()))
        } else {
            None
        },
        authority_epoch: rng.next_u64() % 1_000,
        parent_sequence: Some(rng.next_u64() % 1_000_000),
    }
}

/// Exhaustive sweep of the full (class, head_effect, product) matrix, ADVERSARIALLY
/// including combinations the real registry would never actually pair (e.g. Economy +
/// Advance): the only two cells that may move a sovereign head are
/// (SovereignAccept, Advance, Pass) -> AcceptedHead and
/// (Authorization, Advance, Pass) -> AuthorizationHead. Every other one of the 42
/// cells -- crucially every (Economy, *, *) cell, including the adversarial
/// (Economy, Advance, Pass) that a corrupted registry row could in principle feed
/// in -- must yield HeadMoved::None and must NOT mutate accepted_head/authorization_head
/// away from the pre-state's carried-forward values.
#[test]
fn reducer_apply_never_moves_a_head_outside_the_two_legal_cells() {
    let mut rng = Xorshift64(SEED);
    let mut cases = 0usize;
    let mut economy_advance_pass_probed = false;

    for &class in &ALL_CLASSES {
        for &effect in &ALL_EFFECTS {
            for &product in &ALL_PRODUCTS {
                for _ in 0..20 {
                    cases += 1;
                    let pre = arbitrary_pre(&mut rng);
                    let new_oid = mu(rng.next_u64());
                    let decision = reducer::apply(&pre, class, effect, product, &new_oid);

                    // tape_tip always advances to the new event oid, unconditionally.
                    assert_eq!(decision.tape_tip, new_oid, "tape_tip must always advance");

                    let legal_advance =
                        effect == HeadEffect::Advance && product == PredicateProduct::Pass;

                    match (class, legal_advance) {
                        (EventClass::SovereignAccept, true) => {
                            assert_eq!(decision.head_moved, HeadMoved::AcceptedHead);
                            assert_eq!(decision.accepted_head, Some(new_oid.clone()));
                            assert_eq!(
                                decision.authorization_head, pre.authorization_head,
                                "authorization_head must not move on a SOVEREIGN_ACCEPT"
                            );
                        }
                        (EventClass::Authorization, true) => {
                            assert_eq!(decision.head_moved, HeadMoved::AuthorizationHead);
                            assert_eq!(decision.authorization_head, Some(new_oid.clone()));
                            assert_eq!(
                                decision.accepted_head, pre.accepted_head,
                                "accepted_head must not move on an AUTHORIZATION event"
                            );
                        }
                        _ => {
                            // Every other cell, INCLUDING every Economy cell (whether or
                            // not effect/product happen to look like an ADVANCE+PASS,
                            // which the real registry would never actually produce for
                            // an Economy row but which we adversarially force here):
                            // no head may move, and both heads must exactly equal the
                            // pre-state's forwarded values (no silent mutation, no
                            // head-swap).
                            assert_eq!(
                                decision.head_moved,
                                HeadMoved::None,
                                "class={class:?} effect={effect:?} product={product:?} \
                                 must never move a sovereign head"
                            );
                            assert_eq!(decision.accepted_head, pre.accepted_head);
                            assert_eq!(decision.authorization_head, pre.authorization_head);

                            if class == EventClass::Economy
                                && effect == HeadEffect::Advance
                                && product == PredicateProduct::Pass
                            {
                                economy_advance_pass_probed = true;
                            }
                        }
                    }
                    // authority_epoch is untouched by the base `apply` (only
                    // `apply_with_epoch` may bump it, and only for ProjectLawAmended).
                    assert_eq!(decision.authority_epoch, pre.authority_epoch);
                }
            }
        }
    }

    assert!(
        economy_advance_pass_probed,
        "the adversarial (Economy, Advance, Pass) cell -- an economy event with a \
         hypothetically-forged ADVANCE registry row that somehow PASSED predicates -- \
         must have actually been exercised by this sweep"
    );
    assert_eq!(cases, 7 * 2 * 3 * 20, "sweep covers the full adversarial matrix");
}

/// Narrower, explicit restatement of the single most safety-critical adversarial cell
/// for INV-9: an Economy-class event that (by hypothesis, contradicting the closed
/// registry) carries head_effect=ADVANCE and gets product=PASS must still produce
/// HeadMoved::None. This is the reducer's OWN last line of defense, independent of the
/// registry / admission layer both being correct.
#[test]
fn economy_class_can_never_move_accepted_head_even_under_forged_advance_pass() {
    let pre = PreState {
        tape_tip: Some(mu(1)),
        authorization_head: Some(mu(2)),
        accepted_head: Some(mu(3)),
        authority_epoch: 9,
        parent_sequence: Some(4),
    };
    let new_oid = mu(0xdead);
    let decision = reducer::apply(
        &pre,
        EventClass::Economy,
        HeadEffect::Advance,
        PredicateProduct::Pass,
        &new_oid,
    );
    assert_eq!(
        decision.head_moved,
        HeadMoved::None,
        "OBSERVED: {:?}. EXPECTED: HeadMoved::None (an Economy-class event must never \
         move accepted_head no matter what head_effect/product it is fed)",
        decision.head_moved
    );
    assert_eq!(decision.accepted_head, pre.accepted_head);
    assert_eq!(decision.authorization_head, pre.authorization_head);
}
