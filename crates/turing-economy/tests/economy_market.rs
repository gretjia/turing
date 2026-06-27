use turing_economy::{
    AgentWalletProjection, AmmPool, EconomyEvent, MarketReplay, RewardDistributed, WalletProjection,
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
