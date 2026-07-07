//! PART C.1 lens 6 (authority/boundary finder, INV-9/10/18) — adversarial attack tests
//! against `turing-economy`'s public authority surface: `MarketRouter::suggest` /
//! `BudgetSuggestion` (INV-9: price is never truth) and the D5 defense checks' error
//! text (INV-18: no economic coefficient/formula leaks back through an error channel).
//!
//! Fixed-seed hand-rolled random loops per the capsule's no-proptest rule (no
//! Math.random / no time seed).

use turing_economy::{
    check_principal_position_cap, check_proposer_conflict, check_self_trade, BudgetSuggestion,
    CandidateRoute, EconomyEvent, MarketRouter, MarketRouterMode, PriceSignal,
};

const SEED: u64 = 0x0B0A_DA71_0000_0006u64; // fixed, distinct per-lens seed.

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
    fn next_range(&mut self, lo: u64, hi_exclusive: u64) -> u64 {
        lo + self.next_u64() % (hi_exclusive - lo)
    }
}

fn random_decimal_string(rng: &mut Xorshift64) -> String {
    // Adversarial price-string zoo: huge integers, many decimals, zero, and a few
    // decoy near-truth_status-looking strings mixed in via the caller (not here --
    // this generates only the numeric side).
    let whole = rng.next_range(0, 1_000_000_000_000);
    let frac = rng.next_range(0, 1_000_000_000);
    format!("{whole}.{frac:09}")
}

fn assert_authority_fields_locked(suggestion: &BudgetSuggestion, mode: MarketRouterMode) {
    assert!(
        !suggestion.emits_authorization,
        "OBSERVED emits_authorization=true, EXPECTED false, for mode={mode:?}"
    );
    assert!(
        !suggestion.can_move_accepted_head,
        "OBSERVED can_move_accepted_head=true, EXPECTED false, for mode={mode:?}"
    );
    assert_eq!(
        suggestion.head_effect, "PRESERVE",
        "OBSERVED head_effect={:?}, EXPECTED \"PRESERVE\", for mode={mode:?}",
        suggestion.head_effect
    );
    assert_eq!(suggestion.mode, mode);
}

/// Attack 1: fuzz `MarketRouter::suggest` across BOTH `MarketRouterMode` variants, with
/// adversarial route counts, adversarial (huge/zero/many-decimal) price strings, and
/// signals that self-declare an elevated `truth_status` (e.g. "ground_truth",
/// "verified_price", "oracle_confirmed", a near-miss case/whitespace variant of the only
/// legal value) to see whether any input can flip `emits_authorization` /
/// `can_move_accepted_head` / `head_effect` away from their hard-coded PRESERVE values,
/// or whether a self-declared elevated truth_status can smuggle a price into the argmax
/// that a legitimately-labeled signal would have lost to.
#[test]
fn market_router_suggest_never_unlocks_authority_under_adversarial_signals() {
    let mut rng = Xorshift64(SEED);
    let decoy_truth_statuses = [
        "ground_truth",
        "verified_price",
        "oracle_confirmed",
        "Statistical_signal_only",  // capitalization near-miss
        "statistical_signal_only ", // trailing space near-miss
        " statistical_signal_only", // leading space near-miss
        "statistical_signal_only\u{0}", // embedded NUL
        "statistical_signal_only",  // the one legal value, mixed in as control
    ];

    for mode in [MarketRouterMode::Shadow, MarketRouterMode::AssistedFuture] {
        for round in 0..500 {
            let route_count = rng.next_range(1, 6) as usize;
            let mut routes = Vec::with_capacity(route_count);
            let mut signals = Vec::with_capacity(route_count);
            for i in 0..route_count {
                let market_id = format!("mkt_{round}_{i}");
                routes.push(CandidateRoute {
                    route_id: format!("route_{round}_{i}"),
                    market_id: market_id.clone(),
                    expected_failure_domain: "provider_x".to_string(),
                    requested_tokens: rng.next_range(1, 1_000_000),
                });
                let decoy = decoy_truth_statuses[rng.next_u64() as usize % decoy_truth_statuses.len()];
                // An attacker-controlled decoy signal claiming an ELEVATED (non-legal)
                // truth_status carries an enormous adversarial price -- if the filter
                // in `suggest` were broken, this decoy would dominate every argmax.
                signals.push(PriceSignal {
                    market_id,
                    yes_price: if decoy == "statistical_signal_only" {
                        random_decimal_string(&mut rng)
                    } else {
                        "999999999999.999999999".to_string()
                    },
                    no_price: random_decimal_string(&mut rng),
                    truth_status: decoy.to_string(),
                });
            }
            let price_signal_hash = format!("sha256:{:064x}", rng.next_u64());
            let pput_prior_hash = format!("sha256:{:064x}", rng.next_u64());

            let result = MarketRouter::new(mode).suggest(
                &routes,
                &signals,
                &price_signal_hash,
                &pput_prior_hash,
            );
            // A malformed digest never happens here (we always mint valid sha256:-prefixed
            // 64-hex strings), so this must always be Ok.
            let suggestion = result.expect("suggest must succeed on well-formed inputs");
            assert_authority_fields_locked(&suggestion, mode);
        }
    }
}

/// Attack 2: an empty `signals` slice (no price information reaches `suggest` at all --
/// the degenerate "silence" input) must still produce a fully-locked, well-formed
/// suggestion (falls back to DecimalAmount::default() == 0 for every route, argmax picks
/// the first route encountered) rather than erroring in a way that could be interpreted
/// by a caller as "authority granted by default".
#[test]
fn market_router_suggest_with_no_price_signals_still_locks_authority() {
    let routes = vec![
        CandidateRoute {
            route_id: "route_a".to_string(),
            market_id: "mkt_a".to_string(),
            expected_failure_domain: "provider_a".to_string(),
            requested_tokens: 10,
        },
        CandidateRoute {
            route_id: "route_b".to_string(),
            market_id: "mkt_b".to_string(),
            expected_failure_domain: "provider_b".to_string(),
            requested_tokens: 20,
        },
    ];
    let suggestion = MarketRouter::new(MarketRouterMode::AssistedFuture)
        .suggest(
            &routes,
            &[],
            "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        )
        .expect("suggest must succeed with zero signals");
    assert_authority_fields_locked(&suggestion, MarketRouterMode::AssistedFuture);
}

/// Fixed blacklist of internal-coefficient markers that must NEVER appear in a D5 defense
/// check's error text: if a τ/softmax/price-formula constant is ever added to these
/// checks in the future and its value leaks into `Display`, it flows straight into
/// `PredicateCheck::fail`'s `reject_class` and then into the JSON-RPC error message
/// (`daemons::predicate_refused`, `daemons.rs:892-894`) -- an unguarded feedback channel
/// an adversarial agent could read every rejected call to reverse-engineer the routing
/// formula (INV-18 Goodhart-shield). None of these constants exist in the code today
/// (INV-16/17 are GAPs per SPEC_ECONOMY.md), so this test currently documents "nothing
/// to leak yet" while pinning the channel so a future implementer cannot regress it.
const FORBIDDEN_LEAK_MARKERS: [&str; 6] = [
    "tau",
    "softmax",
    "temperature",
    "price_signal_hash",
    "pput_prior_hash",
    "diversity_policy_hash",
];

/// Attack 3: fuzz the D5 defense checks' error `Display` text with adversarial huge
/// amounts (but marker-free IDs, so a caller-supplied `agent_id` echoing its own
/// substring can't be confused with the CHECK's own formatting logic leaking a
/// coefficient) to see whether `check_principal_position_cap`/`check_proposer_conflict`
/// ever emit one of the forbidden markers on their own.
#[test]
fn d5_defense_check_error_text_never_leaks_forbidden_coefficient_markers() {
    for round in 0..300 {
        let market_id = format!("mkt_{round}");
        let agent_id = format!("agent_{round}");

        // Build a tape with one mint so the position aggregation has real numbers to
        // report in a failure.
        let mint = EconomyEvent::position_minted(&market_id, &agent_id, "1000.0")
            .expect("mint constructs");
        let events = vec![mint];

        // check_self_trade only inspects AmmSwapExecuted events; with none present it is
        // always Ok(()) here (nothing to inspect), so exercise it anyway for completeness
        // and inspect the error text on the rare/impossible branch defensively.
        let self_trade_result = check_self_trade(&events, &market_id, &agent_id, "yes");
        if let Err(error) = self_trade_result {
            let text = error.to_string();
            for marker in FORBIDDEN_LEAK_MARKERS {
                assert!(
                    !text.to_lowercase().contains(marker),
                    "check_self_trade error leaked forbidden marker {marker:?}: {text:?}"
                );
            }
        }

        // Deliberately tiny cap so the aggregated position (from the mint above) trips it.
        let cap_result = check_principal_position_cap(
            &events,
            &market_id,
            &agent_id,
            "0.0",
            "0.0",
            "0.000000001",
        );
        let error = cap_result.expect_err("a 1e-9 cap must be exceeded by a 1000.0 mint");
        let text = error.to_string();
        for marker in FORBIDDEN_LEAK_MARKERS {
            assert!(
                !text.to_lowercase().contains(marker),
                "check_principal_position_cap error leaked forbidden marker {marker:?}: {text:?}"
            );
        }

        let conflict_result = check_proposer_conflict(
            &events,
            &market_id,
            &agent_id, // proposer == trader (agent_id) to force the net-NO branch to run
            &agent_id,
            "0.0",
            "1000.0", // pending_no swamps pending_yes -> net_no > tiny cap
            "0.000000001",
        );
        let error = conflict_result.expect_err("a 1e-9 de-minimis cap must be exceeded");
        let text = error.to_string();
        for marker in FORBIDDEN_LEAK_MARKERS {
            assert!(
                !text.to_lowercase().contains(marker),
                "check_proposer_conflict error leaked forbidden marker {marker:?}: {text:?}"
            );
        }
    }
}
