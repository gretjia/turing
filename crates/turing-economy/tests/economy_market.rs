use turing_economy::{
    AgentWalletProjection, AmmPool, EconomyEvent, MarketReplay, PositionMinted, RewardDistributed,
    WalletProjection, check_conservation, verify_swap_post_trade_invariant,
};

#[test]
fn ctf_conservation() {
    let event =
        EconomyEvent::position_minted("mkt_demo", "agent_a", "10.5").expect("position mint event");

    let minted = event.as_position_minted().expect("minted event");
    assert_eq!(minted.schema_id, "position_minted.v1");
    assert_eq!(minted.coin_in, "10.5");
    assert_eq!(minted.yes_out, "10.5");
    assert_eq!(minted.no_out, "10.5");
    assert_eq!(minted.invariant, "coin_in == yes_out == no_out");

    assert!(EconomyEvent::position_minted("mkt_demo", "agent_a", "1e3").is_err());
}

#[test]
fn amm_cpmm_buy_yes_and_buy_no() {
    let pool = AmmPool::new("mkt_demo", "100", "100").expect("pool");

    let buy_yes = pool.buy_yes("trader_a", "25").expect("buy YES");
    assert_eq!(buy_yes.side, "BUY_YES");
    assert_eq!(buy_yes.d_y, "-20");
    assert_eq!(buy_yes.d_n, "25");
    assert_eq!(buy_yes.get_y, "45");
    assert_eq!(buy_yes.pool_y_after, "80");
    assert_eq!(buy_yes.pool_n_after, "125");
    assert_eq!(buy_yes.invariant_k_before, "10000");
    assert_eq!(buy_yes.invariant_k_after, "10000");

    let buy_no = pool.buy_no("trader_b", "25").expect("buy NO");
    assert_eq!(buy_no.side, "BUY_NO");
    assert_eq!(buy_no.d_y, "25");
    assert_eq!(buy_no.d_n, "-20");
    assert_eq!(buy_no.get_n, "45");
    assert_eq!(buy_no.pool_y_after, "125");
    assert_eq!(buy_no.pool_n_after, "80");
    assert_eq!(buy_no.invariant_k_before, "10000");
    assert_eq!(buy_no.invariant_k_after, "10000");

    assert!(
        AmmPool::new("mkt_demo", "100", "100")
            .unwrap()
            .buy_yes("trader", "2.5")
            .is_ok()
    );
    assert!(AmmPool::new("mkt_demo", "100", "1e2").is_err());
}

#[test]
fn market_replay_from_tape_events() {
    let created = EconomyEvent::market_created("mkt_demo", "100", "100").expect("market created");
    let swap = AmmPool::new("mkt_demo", "100", "100")
        .expect("pool")
        .buy_yes("trader_a", "25")
        .expect("swap");
    let settled = EconomyEvent::market_settled(
        "mkt_demo",
        "YES",
        "mu:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    .expect("settlement");

    let replay =
        MarketReplay::from_tape_events(&[created, EconomyEvent::AmmSwapExecuted(swap), settled])
            .expect("market replay");

    assert_eq!(replay.source, "micro_tape_only");
    assert_eq!(replay.markets["mkt_demo"].pool_y, "80");
    assert_eq!(replay.markets["mkt_demo"].pool_n, "125");
    assert_eq!(replay.markets["mkt_demo"].status, "settled");
    assert_eq!(
        replay.markets["mkt_demo"].settlement_result.as_deref(),
        Some("YES")
    );
}

#[test]
fn wallet_projection_replay_from_tape_events() {
    let mint = EconomyEvent::position_minted("mkt_demo", "agent_a", "10").expect("mint");
    let reward = EconomyEvent::RewardDistributed(RewardDistributed {
        schema_id: "reward_distributed.v1".to_string(),
        market_id: "mkt_demo".to_string(),
        agent_id: "agent_a".to_string(),
        reward_coin: "3".to_string(),
        slash_coin: "1.5".to_string(),
        reason: "PREDICATE_SETTLEMENT".to_string(),
    });

    let projection = WalletProjection::from_tape_events(&[mint, reward]).expect("wallet replay");
    let wallet: &AgentWalletProjection = projection.wallets.get("agent_a").expect("wallet");

    assert_eq!(projection.source, "micro_tape_only");
    assert_eq!(wallet.coin_balance, "-8.5");
    assert_eq!(wallet.yes_positions["mkt_demo"], "10");
    assert_eq!(wallet.no_positions["mkt_demo"], "10");
}

/// E1.wallet — D7: `AmmSwapExecuted` must debit the trader's Coin (the pay side) and credit the
/// outcome side they bought (the get side); a subsequent `MarketSettled` must redeem the winning
/// side 1:1 to Coin and zero the losing side out of the projection entirely.
#[test]
fn wallet_projection_moves_balances_on_swap_and_settlement() {
    let mint = EconomyEvent::position_minted("mkt_demo", "trader_a", "100").expect("mint");
    let swap = AmmPool::new("mkt_demo", "100", "100")
        .expect("pool")
        .buy_yes("trader_a", "25")
        .expect("swap");
    assert_eq!(swap.pay_coin, "25");
    assert_eq!(swap.get_y, "45");
    assert_eq!(swap.get_n, "0");
    let settled = EconomyEvent::market_settled(
        "mkt_demo",
        "YES",
        "mu:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    .expect("settlement");

    let projection =
        WalletProjection::from_tape_events(&[mint, EconomyEvent::AmmSwapExecuted(swap), settled])
            .expect("wallet replay");
    let wallet = projection.wallets.get("trader_a").expect("wallet");

    // Coin debited: -100 (mint) - 25 (swap pay) + redeemed winning YES (100 minted + 45 bought =
    // 145) = 20.
    assert_eq!(wallet.coin_balance, "20");
    // Winning side (YES) is redeemed and removed from the live projection.
    assert!(!wallet.yes_positions.contains_key("mkt_demo"));
    // Losing side (NO, 100 from the mint) is zeroed out (removed), never redeemed.
    assert!(!wallet.no_positions.contains_key("mkt_demo"));
}

/// D7 conservation predicate: `redeemed_coin <= minted_coin + declared_subsidy` must hold across
/// a full lifecycle (create -> mint -> swap -> settle) on a real, non-degenerate market.
#[test]
fn conservation_holds_across_a_full_market_lifecycle() {
    let created = EconomyEvent::market_created("mkt_demo", "100", "100").expect("market created");
    let mint_a = EconomyEvent::position_minted("mkt_demo", "trader_a", "100").expect("mint a");
    let mint_b = EconomyEvent::position_minted("mkt_demo", "trader_b", "50").expect("mint b");
    let swap = AmmPool::new("mkt_demo", "100", "100")
        .expect("pool")
        .buy_yes("trader_a", "25")
        .expect("swap");
    let settled = EconomyEvent::market_settled(
        "mkt_demo",
        "YES",
        "mu:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    .expect("settlement");

    let events = vec![
        created,
        mint_a,
        mint_b,
        EconomyEvent::AmmSwapExecuted(swap.clone()),
        settled,
    ];
    let report = check_conservation(&events).expect("conservation check");
    assert_eq!(report.len(), 1);
    let market = &report[0];
    assert_eq!(market.market_id, "mkt_demo");
    assert_eq!(market.minted_coin, "150");
    assert_eq!(market.declared_subsidy, "200");
    // Only trader_a's YES redeems (100 minted + 45 bought = 145); trader_b's YES (50, losing NO
    // is discarded, but trader_b never bought more YES) also redeems: 50 + 145 = 195.
    assert_eq!(market.redeemed_coin, "195");
    assert!(market.holds, "conservation should hold: {market:?}");

    // The recorded swap also satisfies the D6 post-trade predicate independently.
    assert!(verify_swap_post_trade_invariant(&swap).is_ok());
}

/// Adversarial: a forged tape with a mint whose `coin_in`/`yes_out`/`no_out` disagree must be
/// hard-rejected by the aggregate mint-invariant check, not silently accepted.
#[test]
fn conservation_rejects_a_forged_mint_invariant_violation() {
    let created = EconomyEvent::market_created("mkt_demo", "100", "100").expect("market created");
    let forged_mint = EconomyEvent::PositionMinted(PositionMinted {
        schema_id: "position_minted.v1".to_string(),
        market_id: "mkt_demo".to_string(),
        agent_id: "attacker".to_string(),
        coin_in: "10".to_string(),
        yes_out: "10".to_string(),
        no_out: "999".to_string(), // forged: no_out != yes_out
        invariant: "coin_in == yes_out == no_out".to_string(),
    });

    let result = check_conservation(&[created, forged_mint]);
    assert!(
        result.is_err(),
        "forged mint with yes_out != no_out must be rejected"
    );
}

/// Adversarial: a forged tape whose `MarketSettled` redeems more Coin than was ever minted plus
/// the declared subsidy must be flagged (`holds == false`), not silently reported as passing.
#[test]
fn conservation_flags_over_redemption_beyond_minted_plus_subsidy() {
    let created = EconomyEvent::market_created("mkt_demo", "10", "10").expect("market created");
    let mint = EconomyEvent::position_minted("mkt_demo", "trader_a", "5").expect("mint");
    // Forge a swap event that credits far more YES than any real pool of this size could ever
    // produce (a corrupted/forged event, not one derived from AmmPool::buy_yes).
    let forged_swap = turing_economy::AmmSwapExecuted {
        schema_id: "amm_swap_executed.v1".to_string(),
        market_id: "mkt_demo".to_string(),
        trader_id: "trader_a".to_string(),
        side: "BUY_YES".to_string(),
        pay_coin: "1".to_string(),
        d_y: "-1".to_string(),
        d_n: "1".to_string(),
        get_y: "10000".to_string(),
        get_n: "0".to_string(),
        pool_y_before: "10".to_string(),
        pool_n_before: "10".to_string(),
        pool_y_after: "9".to_string(),
        pool_n_after: "11".to_string(),
        invariant_k_before: "100".to_string(),
        invariant_k_after: "99".to_string(),
        effective_price: "0.1".to_string(),
    };
    let settled = EconomyEvent::market_settled(
        "mkt_demo",
        "YES",
        "mu:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    .expect("settlement");

    let events = vec![
        created,
        mint,
        EconomyEvent::AmmSwapExecuted(forged_swap.clone()),
        settled,
    ];
    let report = check_conservation(&events).expect("conservation check runs");
    assert_eq!(report.len(), 1);
    assert!(
        !report[0].holds,
        "over-redemption must be flagged, not silently pass: {:?}",
        report[0]
    );

    // The forged swap's own post-trade invariant is *also* independently violated (k shrank).
    assert!(verify_swap_post_trade_invariant(&forged_swap).is_err());
}

/// Parses a non-negative `decimal_string` (as produced by this crate's fixed-point formatting,
/// SCALE = 1e9) into exact integer "units" for lossless comparison in tests, without needing
/// float parsing (which could mask a genuine sub-epsilon money-pump leak).
fn parse_units_exact(raw: &str) -> i128 {
    const SCALE: i128 = 1_000_000_000;
    let mut split = raw.split('.');
    let whole: i128 = split.next().unwrap_or("0").parse().expect("whole part");
    let fraction = match split.next() {
        Some(fraction) => {
            let padded = format!("{fraction:0<9}");
            padded[..9].parse::<i128>().expect("fraction part")
        }
        None => 0,
    };
    whole * SCALE + fraction
}

/// D6 money-pump defense: repeat a rounding-favorable trade against a thin pool many times and
/// assert the pool's constant-product invariant `k` never decreases across the sequence — i.e.
/// truncation-toward-zero rounding in `mul_div` never lets the trader extract pool value. Uses a
/// deliberately small pool and payment sizes (alternating 1 and 3 against a pool of 1000) chosen
/// to force non-exact (truncating) division on most iterations.
#[test]
fn repeated_rounding_favorable_trades_cannot_extract_pool_value() {
    let mut pool = AmmPool::new("mkt_demo", "1000", "1000").expect("pool");
    let mut previous_k = parse_units_exact("1000000"); // 1000 * 1000, the pool's starting k

    for i in 0..500u32 {
        let pay = if i % 7 == 0 { "3" } else { "1" };
        let swap = pool.buy_yes("trader", pay).expect("buy_yes should succeed");
        assert!(
            verify_swap_post_trade_invariant(&swap).is_ok(),
            "post-trade invariant must hold on iteration {i}: {swap:?}"
        );
        let k_after = parse_units_exact(&swap.invariant_k_after);
        assert!(
            k_after >= previous_k,
            "k must never decrease (money pump): iteration {i}, before={previous_k}, after={k_after}"
        );
        previous_k = k_after;
        pool = AmmPool::new("mkt_demo", &swap.pool_y_after, &swap.pool_n_after).expect("re-pool");
    }
}
