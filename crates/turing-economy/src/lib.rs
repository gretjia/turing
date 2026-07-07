//! Agent Economy CTF, AMM, market, and wallet projections.
//!
//! All load-bearing prices and balances are `decimal_string` values backed by fixed-point
//! integer math. This crate is a reducer/toolbox only; it does not move Micro heads.

use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};
use turing_contracts::identity::MicroOid;

const SCALE: i128 = 1_000_000_000;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum EconomyEvent {
    MarketCreated(MarketCreated),
    PositionMinted(PositionMinted),
    AmmSwapExecuted(AmmSwapExecuted),
    MarketSettled(MarketSettled),
    RewardDistributed(RewardDistributed),
    /// ADR-ECON-001 (owner-ratified 2026-07-07): additive, PRESERVE-class governance
    /// declaration that `agent_id` is a member of `principal_id`, following the same
    /// `ADDITIVE_AGENT_ECONOMY_V1_0` registry pattern as every other economy event above.
    /// Not automatic Sybil detection (out of scope per the ADR) -- an authority
    /// (ArchitectAI/owner) asserts the mapping; the D5 defenses below then resolve through it
    /// when aggregating, falling back to the literal `agent_id` when no declaration exists
    /// (back-compat with every pre-ADR-ECON-001 fixture/call site).
    PrincipalDeclared(PrincipalDeclared),
}

impl EconomyEvent {
    pub fn market_created(
        market_id: impl Into<String>,
        pool_y: &str,
        pool_n: &str,
    ) -> Result<Self, EconomyError> {
        let pool = AmmPool::new(market_id.into(), pool_y, pool_n)?;
        let k = pool.k_string()?;
        Ok(EconomyEvent::MarketCreated(MarketCreated {
            schema_id: "market_created.v1".to_string(),
            event_type: "MarketCreated".to_string(),
            head_effect: "PRESERVE".to_string(),
            market_id: pool.market_id,
            initial_pool_y: pool.pool_y.to_decimal_string(),
            initial_pool_n: pool.pool_n.to_decimal_string(),
            k,
            truth_status: "statistical_signal_only".to_string(),
            capsule_id: String::new(),
            proposer_id: String::new(),
            predicate_set_hash: String::new(),
        }))
    }

    /// D4/G-MKT-06 constructor: `MarketCreated` with the capsule binding and frozen
    /// predicate-set hash pinned at creation, so a proposer cannot weaken predicates after
    /// betting YES. Additive over [`Self::market_created`] (which leaves these three fields
    /// at their `#[serde(default)]` empty-string value for backward compatibility with every
    /// existing `MarketCreated` fixture that predates this design).
    pub fn market_created_for_capsule(
        market_id: impl Into<String>,
        pool_y: &str,
        pool_n: &str,
        capsule_id: impl Into<String>,
        proposer_id: impl Into<String>,
        predicate_set_hash: impl Into<String>,
    ) -> Result<Self, EconomyError> {
        let event = Self::market_created(market_id, pool_y, pool_n)?;
        let EconomyEvent::MarketCreated(mut created) = event else {
            unreachable!("market_created always returns EconomyEvent::MarketCreated")
        };
        created.capsule_id = capsule_id.into();
        created.proposer_id = proposer_id.into();
        created.predicate_set_hash = predicate_set_hash.into();
        Ok(EconomyEvent::MarketCreated(created))
    }

    pub fn position_minted(
        market_id: impl Into<String>,
        agent_id: impl Into<String>,
        coin_in: &str,
    ) -> Result<Self, EconomyError> {
        let coin = DecimalAmount::parse_non_negative(coin_in)?;
        Ok(EconomyEvent::PositionMinted(PositionMinted {
            schema_id: "position_minted.v1".to_string(),
            market_id: market_id.into(),
            agent_id: agent_id.into(),
            coin_in: coin.to_decimal_string(),
            yes_out: coin.to_decimal_string(),
            no_out: coin.to_decimal_string(),
            invariant: "coin_in == yes_out == no_out".to_string(),
        }))
    }

    pub fn market_settled(
        market_id: impl Into<String>,
        result: impl Into<String>,
        settlement_event_id: &str,
    ) -> Result<Self, EconomyError> {
        if MicroOid::parse(settlement_event_id).is_err() {
            return Err(EconomyError::InvalidMicroEventId(
                settlement_event_id.to_string(),
            ));
        }
        let result = result.into();
        if !matches!(result.as_str(), "YES" | "NO" | "INVALID") {
            return Err(EconomyError::InvalidSettlementResult(result));
        }
        Ok(EconomyEvent::MarketSettled(MarketSettled {
            schema_id: "market_settled.v1".to_string(),
            market_id: market_id.into(),
            result,
            settlement_event_id: settlement_event_id.to_string(),
            price_not_truth_ack: true,
        }))
    }

    #[must_use]
    pub fn as_position_minted(&self) -> Option<&PositionMinted> {
        match self {
            EconomyEvent::PositionMinted(event) => Some(event),
            _ => None,
        }
    }

    /// ADR-ECON-001: authority-declared association of `agent_id` with `principal_id`. PRESERVE
    /// (never moves `accepted_head`), additive over every existing economy event.
    pub fn principal_declared(
        principal_id: impl Into<String>,
        agent_id: impl Into<String>,
    ) -> Self {
        EconomyEvent::PrincipalDeclared(PrincipalDeclared {
            schema_id: "principal_declared.v1".to_string(),
            event_type: "PrincipalDeclared".to_string(),
            head_effect: "PRESERVE".to_string(),
            principal_id: principal_id.into(),
            agent_id: agent_id.into(),
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MarketCreated {
    pub schema_id: String,
    pub event_type: String,
    pub head_effect: String,
    pub market_id: String,
    pub initial_pool_y: String,
    pub initial_pool_n: String,
    pub k: String,
    pub truth_status: String,
    /// D4/G-MKT-06: the capsule this market resolves ("will capsule X land
    /// `CandidateAccepted` by tick T?"). Empty string on markets predating this field
    /// (`#[serde(default)]`) -- those markets are simply not G-MKT-06-gate-eligible.
    #[serde(default)]
    pub capsule_id: String,
    /// D5 proposer-conflict rule: the capsule's proposer, frozen at market creation so
    /// `market.swap`/`market.mint` can enforce the "no self-shorting your own capsule"
    /// defense without an external principal registry. Empty string means "no proposer
    /// bound" (proposer-conflict check is a no-op for such markets).
    #[serde(default)]
    pub proposer_id: String,
    /// D4/G-MKT-06: `sha256:` + hex over the capsule's predicate-check-id set as of market
    /// creation (see `turing_predicate::candidate_predicate_set_hash`). Frozen here so
    /// `MarketSettled` can be refused if the predicate set was weakened between market
    /// creation and settlement. Empty string means "not frozen" (pre-dates this field).
    #[serde(default)]
    pub predicate_set_hash: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PositionMinted {
    pub schema_id: String,
    pub market_id: String,
    pub agent_id: String,
    pub coin_in: String,
    pub yes_out: String,
    pub no_out: String,
    pub invariant: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AmmSwapExecuted {
    pub schema_id: String,
    pub market_id: String,
    pub trader_id: String,
    pub side: String,
    pub pay_coin: String,
    pub d_y: String,
    pub d_n: String,
    pub get_y: String,
    pub get_n: String,
    pub pool_y_before: String,
    pub pool_n_before: String,
    pub pool_y_after: String,
    pub pool_n_after: String,
    pub invariant_k_before: String,
    pub invariant_k_after: String,
    pub effective_price: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MarketSettled {
    pub schema_id: String,
    pub market_id: String,
    pub result: String,
    pub settlement_event_id: String,
    pub price_not_truth_ack: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RewardDistributed {
    pub schema_id: String,
    pub market_id: String,
    pub agent_id: String,
    pub reward_coin: String,
    pub slash_coin: String,
    pub reason: String,
}

/// ADR-ECON-001 (owner-ratified 2026-07-07, additive): authority-declared "these agent_ids are
/// the same economic principal" association. `market_id`-independent by design (a principal
/// declaration is a governance fact about identity, not scoped to one market). Consumed by
/// `resolve_principal`/`principal_position`/`check_self_trade`/`check_proposer_conflict`.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PrincipalDeclared {
    pub schema_id: String,
    pub event_type: String,
    pub head_effect: String,
    pub principal_id: String,
    pub agent_id: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AmmPool {
    pub market_id: String,
    pool_y: DecimalAmount,
    pool_n: DecimalAmount,
}

impl AmmPool {
    pub fn new(
        market_id: impl Into<String>,
        pool_y: &str,
        pool_n: &str,
    ) -> Result<Self, EconomyError> {
        let pool_y = DecimalAmount::parse_non_negative(pool_y)?;
        let pool_n = DecimalAmount::parse_non_negative(pool_n)?;
        if pool_y.is_zero() || pool_n.is_zero() {
            return Err(EconomyError::ZeroPool);
        }
        Ok(AmmPool {
            market_id: market_id.into(),
            pool_y,
            pool_n,
        })
    }

    pub fn buy_yes(
        &self,
        trader_id: impl Into<String>,
        pay_coin: &str,
    ) -> Result<AmmSwapExecuted, EconomyError> {
        let pay = DecimalAmount::parse_non_negative(pay_coin)?;
        if pay.is_zero() {
            return Err(EconomyError::ZeroPay);
        }
        let d_y_abs = pay.mul_div(self.pool_y, pay + self.pool_n)?;
        let pool_y_after = self.pool_y - d_y_abs;
        let pool_n_after = self.pool_n + pay;
        assert_k_non_decreasing(self.pool_y, self.pool_n, pool_y_after, pool_n_after)?;
        let get_y = pay + d_y_abs;
        Ok(AmmSwapExecuted {
            schema_id: "amm_swap_executed.v1".to_string(),
            market_id: self.market_id.clone(),
            trader_id: trader_id.into(),
            side: "BUY_YES".to_string(),
            pay_coin: pay.to_decimal_string(),
            d_y: (-d_y_abs).to_decimal_string(),
            d_n: pay.to_decimal_string(),
            get_y: get_y.to_decimal_string(),
            get_n: "0".to_string(),
            pool_y_before: self.pool_y.to_decimal_string(),
            pool_n_before: self.pool_n.to_decimal_string(),
            pool_y_after: pool_y_after.to_decimal_string(),
            pool_n_after: pool_n_after.to_decimal_string(),
            invariant_k_before: self.k_string()?,
            invariant_k_after: DecimalAmount::mul(pool_y_after, pool_n_after)?.to_decimal_string(),
            effective_price: DecimalAmount::ratio(pay, get_y)?.to_decimal_string(),
        })
    }

    pub fn buy_no(
        &self,
        trader_id: impl Into<String>,
        pay_coin: &str,
    ) -> Result<AmmSwapExecuted, EconomyError> {
        let pay = DecimalAmount::parse_non_negative(pay_coin)?;
        if pay.is_zero() {
            return Err(EconomyError::ZeroPay);
        }
        let d_n_abs = pay.mul_div(self.pool_n, pay + self.pool_y)?;
        let pool_y_after = self.pool_y + pay;
        let pool_n_after = self.pool_n - d_n_abs;
        assert_k_non_decreasing(self.pool_y, self.pool_n, pool_y_after, pool_n_after)?;
        let get_n = pay + d_n_abs;
        Ok(AmmSwapExecuted {
            schema_id: "amm_swap_executed.v1".to_string(),
            market_id: self.market_id.clone(),
            trader_id: trader_id.into(),
            side: "BUY_NO".to_string(),
            pay_coin: pay.to_decimal_string(),
            d_y: pay.to_decimal_string(),
            d_n: (-d_n_abs).to_decimal_string(),
            get_y: "0".to_string(),
            get_n: get_n.to_decimal_string(),
            pool_y_before: self.pool_y.to_decimal_string(),
            pool_n_before: self.pool_n.to_decimal_string(),
            pool_y_after: pool_y_after.to_decimal_string(),
            pool_n_after: pool_n_after.to_decimal_string(),
            invariant_k_before: self.k_string()?,
            invariant_k_after: DecimalAmount::mul(pool_y_after, pool_n_after)?.to_decimal_string(),
            effective_price: DecimalAmount::ratio(pay, get_n)?.to_decimal_string(),
        })
    }

    fn k_string(&self) -> Result<String, EconomyError> {
        Ok(DecimalAmount::mul(self.pool_y, self.pool_n)?.to_decimal_string())
    }
}

/// D6 post-trade predicate: `pool_y' * pool_n' >= k` (equality up to pool-favoring dust).
/// Rounding in `mul_div` truncates toward zero, and every operand here is non-negative
/// (`DecimalAmount::parse_non_negative` rejects negatives at every call site), so truncation is
/// always a floor: the trader never receives more than the exact rational output, and the
/// invariant can only grow (or hold exactly), never shrink. This function re-derives `k` from the
/// before/after pool states and hard-fails a swap that would violate that direction — the
/// in-process assertion call site for the money-pump defense.
fn assert_k_non_decreasing(
    pool_y_before: DecimalAmount,
    pool_n_before: DecimalAmount,
    pool_y_after: DecimalAmount,
    pool_n_after: DecimalAmount,
) -> Result<(), EconomyError> {
    let k_before = DecimalAmount::mul(pool_y_before, pool_n_before)?;
    let k_after = DecimalAmount::mul(pool_y_after, pool_n_after)?;
    if k_after < k_before {
        return Err(EconomyError::PostTradeInvariantViolated {
            k_before: k_before.to_decimal_string(),
            k_after: k_after.to_decimal_string(),
        });
    }
    Ok(())
}

/// Checkable audit-path form of [`assert_k_non_decreasing`]: re-verifies the D6 post-trade
/// predicate against an already-recorded [`AmmSwapExecuted`] event (e.g. one read back off a
/// tape), so `turing audit market` can catch a forged or corrupted swap event whose recorded
/// `pool_*_after` fields would have violated pool-favoring rounding, even though the in-process
/// assertion in `buy_yes`/`buy_no` already prevents this crate from ever emitting one.
pub fn verify_swap_post_trade_invariant(swap: &AmmSwapExecuted) -> Result<(), EconomyError> {
    let pool_y_before = DecimalAmount::parse_non_negative(&swap.pool_y_before)?;
    let pool_n_before = DecimalAmount::parse_non_negative(&swap.pool_n_before)?;
    let pool_y_after = DecimalAmount::parse_non_negative(&swap.pool_y_after)?;
    let pool_n_after = DecimalAmount::parse_non_negative(&swap.pool_n_after)?;
    assert_k_non_decreasing(pool_y_before, pool_n_before, pool_y_after, pool_n_after)
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MarketReplay {
    pub source: String,
    pub markets: BTreeMap<String, MarketProjection>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MarketProjection {
    pub market_id: String,
    pub pool_y: String,
    pub pool_n: String,
    pub status: String,
    pub settlement_result: Option<String>,
}

impl MarketReplay {
    pub fn from_tape_events(events: &[EconomyEvent]) -> Result<Self, EconomyError> {
        let mut markets = BTreeMap::new();
        for event in events {
            match event {
                EconomyEvent::MarketCreated(created) => {
                    // CONFIRMED-bug-#3 fix (INV-11/INV-2 boundary, "duplicate MarketCreated
                    // revives a settled market"): this used to be an unconditional
                    // `BTreeMap::insert`, so a second `MarketCreated` for the same market_id
                    // (e.g. re-appended by a writer with tape access, since no uniqueness check
                    // exists anywhere upstream) silently discarded the first projection --
                    // including a prior `status = "settled"` -- and reset it back to "open".
                    // That let a market be settled a second time with a conflicting result
                    // (direct INV-2 double-redemption hazard). A `MarketCreated` is a one-time
                    // per-market event by design (D2); replay now keeps the FIRST one only,
                    // making a duplicate a harmless no-op instead of a status-reopening write.
                    markets.entry(created.market_id.clone()).or_insert_with(|| {
                        MarketProjection {
                            market_id: created.market_id.clone(),
                            pool_y: created.initial_pool_y.clone(),
                            pool_n: created.initial_pool_n.clone(),
                            status: "open".to_string(),
                            settlement_result: None,
                        }
                    });
                }
                EconomyEvent::AmmSwapExecuted(swap) => {
                    let market = markets
                        .get_mut(&swap.market_id)
                        .ok_or_else(|| EconomyError::UnknownMarket(swap.market_id.clone()))?;
                    market.pool_y = swap.pool_y_after.clone();
                    market.pool_n = swap.pool_n_after.clone();
                }
                EconomyEvent::MarketSettled(settled) => {
                    let market = markets
                        .get_mut(&settled.market_id)
                        .ok_or_else(|| EconomyError::UnknownMarket(settled.market_id.clone()))?;
                    // CONFIRMED-bug-#4 fix (INV-4/INV-17 class, "view != replay(view)"): this
                    // used to unconditionally overwrite status/settlement_result on EVERY
                    // MarketSettled, so a second, conflicting MarketSettled for an
                    // already-settled market flipped the reported settlement_result even
                    // though WalletProjection (the real financial ledger) already treats a
                    // second settle as a true no-op (it clears positions on the first settle).
                    // First-settle-wins now, matching WalletProjection's own idempotency.
                    if market.status != "settled" {
                        market.status = "settled".to_string();
                        market.settlement_result = Some(settled.result.clone());
                    }
                }
                EconomyEvent::PositionMinted(_)
                | EconomyEvent::RewardDistributed(_)
                | EconomyEvent::PrincipalDeclared(_) => {}
            }
        }
        Ok(MarketReplay {
            source: "micro_tape_only".to_string(),
            markets,
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WalletProjection {
    pub source: String,
    pub wallets: BTreeMap<String, AgentWalletProjection>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AgentWalletProjection {
    pub agent_id: String,
    pub coin_balance: String,
    pub yes_positions: BTreeMap<String, String>,
    pub no_positions: BTreeMap<String, String>,
}

impl WalletProjection {
    pub fn from_tape_events(events: &[EconomyEvent]) -> Result<Self, EconomyError> {
        let mut balances: BTreeMap<String, WalletInternal> = BTreeMap::new();
        for event in events {
            match event {
                EconomyEvent::PositionMinted(mint) => {
                    let wallet = balances.entry(mint.agent_id.clone()).or_default();
                    let coin = DecimalAmount::parse_non_negative(&mint.coin_in)?;
                    wallet.coin -= coin;
                    wallet.add_yes(
                        &mint.market_id,
                        DecimalAmount::parse_non_negative(&mint.yes_out)?,
                    );
                    wallet.add_no(
                        &mint.market_id,
                        DecimalAmount::parse_non_negative(&mint.no_out)?,
                    );
                }
                EconomyEvent::AmmSwapExecuted(swap) => {
                    // D7: a swap debits the trader's Coin (the pay side) and credits whichever
                    // outcome side they bought (the get side). `get_y`/`get_n` already carry the
                    // full amount the trader ends up holding for this trade (pay-side tokens
                    // implicitly minted then swapped into the pool never land in the trader's own
                    // position — see AmmPool::buy_yes/buy_no), so no separate pay-side token debit
                    // is needed beyond the Coin debit.
                    let wallet = balances.entry(swap.trader_id.clone()).or_default();
                    wallet.coin -= DecimalAmount::parse_non_negative(&swap.pay_coin)?;
                    wallet.add_yes(
                        &swap.market_id,
                        DecimalAmount::parse_non_negative(&swap.get_y)?,
                    );
                    wallet.add_no(
                        &swap.market_id,
                        DecimalAmount::parse_non_negative(&swap.get_n)?,
                    );
                }
                EconomyEvent::MarketSettled(settled) => {
                    // D7: winning outcome tokens redeem 1:1 to Coin; losing tokens go to 0. An
                    // "INVALID" result has no winning side (per the constructor's validated
                    // result set: YES | NO | INVALID) — conservatively, no side is redeemed rather
                    // than inventing an unspecified refund mechanism; this can only ever
                    // under-redeem relative to minted Coin, never over-redeem, so it cannot
                    // violate the conservation predicate below.
                    for wallet in balances.values_mut() {
                        let yes_amount = wallet
                            .yes_positions
                            .remove(&settled.market_id)
                            .unwrap_or_default();
                        let no_amount = wallet
                            .no_positions
                            .remove(&settled.market_id)
                            .unwrap_or_default();
                        match settled.result.as_str() {
                            "YES" => wallet.coin += yes_amount,
                            "NO" => wallet.coin += no_amount,
                            _ => {}
                        }
                    }
                }
                EconomyEvent::RewardDistributed(reward) => {
                    let wallet = balances.entry(reward.agent_id.clone()).or_default();
                    wallet.coin += DecimalAmount::parse_non_negative(&reward.reward_coin)?;
                    wallet.coin -= DecimalAmount::parse_non_negative(&reward.slash_coin)?;
                }
                EconomyEvent::MarketCreated(_) | EconomyEvent::PrincipalDeclared(_) => {}
            }
        }

        let wallets = balances
            .into_iter()
            .map(|(agent_id, wallet)| {
                let projection = AgentWalletProjection {
                    agent_id: agent_id.clone(),
                    coin_balance: wallet.coin.to_decimal_string(),
                    yes_positions: format_positions(wallet.yes_positions),
                    no_positions: format_positions(wallet.no_positions),
                };
                (agent_id, projection)
            })
            .collect();
        Ok(WalletProjection {
            source: "micro_tape_only".to_string(),
            wallets,
        })
    }
}

/// D7 conservation report for a single market: `minted_coin` is the sum of every
/// `PositionMinted.coin_in` on that market (the trader-backed Coin actually locked into CTF
/// mints); `declared_subsidy` is the governance liquidity seeded at `MarketCreated`
/// (`initial_pool_y + initial_pool_n` — D2's "subsidy is the verification-attention budget", not
/// agent capital); `redeemed_coin` is the total Coin actually paid out across all wallets at the
/// market's `MarketSettled` event (winning-side positions only, per D7). `holds` is
/// `redeemed_coin <= minted_coin + declared_subsidy`; markets never settled have no redemption
/// yet, so they trivially hold.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MarketConservationReport {
    pub market_id: String,
    pub minted_coin: String,
    pub declared_subsidy: String,
    pub redeemed_coin: String,
    pub holds: bool,
}

#[derive(Debug, Default, Clone, PartialEq, Eq)]
struct MarketConservationInternal {
    minted_coin: DecimalAmount,
    minted_yes: DecimalAmount,
    minted_no: DecimalAmount,
    declared_subsidy: DecimalAmount,
    redeemed_coin: DecimalAmount,
    /// CONFIRMED-bug-#2 fix (candidate 1): sum of every `AmmSwapExecuted.pay_coin` on this
    /// market. A swap's `pay_coin` is genuine trader-backed Coin locked into the pool (an
    /// implicit CTF mint per `WalletProjection::from_tape_events`'s own doc comment), so it is
    /// real backing that `holds` must count, on top of `minted_coin`/`declared_subsidy`.
    /// Omitting it previously made `check_conservation` strictly more pessimistic than reality:
    /// a perfectly healthy, high-swap-volume market could be false-positive-flagged as broken.
    swap_pay_coin: DecimalAmount,
    /// CONFIRMED-bug-#2 fix (candidate 2, headline): sum of every
    /// `RewardDistributed.reward_coin` on this market. `reward_coin` becomes real spendable
    /// `Coin` in `WalletProjection` with no constructor invariant, no cap, and (before this fix)
    /// no conservation visibility at all — a completely unconstrained, audit-invisible
    /// Coin-creation channel that defeats INV-3 ("Σ赎回 ≤ Σ铸造 + Σ补贴"). It is now folded into
    /// the same "Coin paid out must be backed" side of the ledger as `redeemed_coin`, so an
    /// unbacked reward now surfaces as `holds == false` instead of being invisible.
    reward_coin: DecimalAmount,
    /// CONFIRMED-bug-#2 fix (candidate 2): sum of every `RewardDistributed.slash_coin` on this
    /// market. A slash destroys real spendable Coin (`WalletProjection` debits it), so it is
    /// counted as backing symmetrically with `minted_coin`/`declared_subsidy`/`swap_pay_coin`.
    slash_coin: DecimalAmount,
    /// CONFIRMED-bug-#4 fix (INV-4/INV-17 class, "view != replay(view)"): whether a
    /// `MarketSettled` has already been folded for this market. Before this fix,
    /// `yes_positions`/`no_positions` were never cleared after a settle, so a second,
    /// conflicting `MarketSettled` for the same market re-summed the still-present positions
    /// and added them AGAIN into `redeemed_coin` -- inflating the reported redemption from an
    /// event that paid nobody anything extra, and could flip a healthy market's `holds` to
    /// `false`. Guarding on this flag makes a duplicate settle a true no-op here too, matching
    /// `WalletProjection`'s own first-settle-wins idempotency.
    settled: bool,
}

/// CONFIRMED-bug-#2 fix (candidate 3): ensures every `market_id` this function ever observes —
/// from *any* event variant, not only `MarketCreated` — is tracked in both `order` (so it is
/// never silently dropped from the returned report) and `markets` (so its ledger exists to be
/// mutated). Before this fix, `order` was only pushed to inside the `MarketCreated` match arm,
/// so a market minted/swapped/settled without its `MarketCreated` event present in the given
/// slice (forged tape, truncated/paginated read, or any upstream loader bug) evaded the audit
/// entirely: not `holds == false`, but completely absent from the output.
fn ensure_tracked<'a>(
    order: &mut Vec<String>,
    markets: &'a mut BTreeMap<String, MarketConservationInternal>,
    market_id: &str,
) -> &'a mut MarketConservationInternal {
    if !markets.contains_key(market_id) {
        order.push(market_id.to_string());
    }
    markets.entry(market_id.to_string()).or_default()
}

/// The D7 conservation predicate, checkable over a raw event slice (real tape or fixture) so
/// `turing audit market` (E0.3) can call it directly instead of re-implementing the bookkeeping.
///
/// Three things are verified:
/// 1. **Mint invariant, aggregated** (defense in depth — `EconomyEvent::position_minted`
///    already enforces `coin_in == yes_out == no_out` per event at construction time, but a tape
///    is untrusted input, so this re-derives and checks the aggregate per market too, hard-failing
///    on `MintInvariantViolated` if a forged/corrupted event slipped the per-event check).
/// 2. **Settlement conservation**: for every `MarketSettled` event, the Coin paid out (winning
///    redemptions plus any `RewardDistributed.reward_coin`) must not exceed the Coin backed into
///    the market (`minted_coin + declared_subsidy + swap_pay_coin + slash_coin`) for that market.
///    This is reported per market (`holds: bool`) rather than hard-erroring, so a caller can
///    report every market's status rather than stopping at the first failure.
/// 3. **Every observed market_id is reported** (candidate 3 fix): a market is never silently
///    dropped from the output just because its `MarketCreated` event is missing from the slice.
pub fn check_conservation(
    events: &[EconomyEvent],
) -> Result<Vec<MarketConservationReport>, EconomyError> {
    let mut markets: BTreeMap<String, MarketConservationInternal> = BTreeMap::new();
    let mut yes_positions: BTreeMap<(String, String), DecimalAmount> = BTreeMap::new();
    let mut no_positions: BTreeMap<(String, String), DecimalAmount> = BTreeMap::new();
    let mut order: Vec<String> = Vec::new();

    for event in events {
        match event {
            EconomyEvent::MarketCreated(created) => {
                let pool_y = DecimalAmount::parse_non_negative(&created.initial_pool_y)?;
                let pool_n = DecimalAmount::parse_non_negative(&created.initial_pool_n)?;
                ensure_tracked(&mut order, &mut markets, &created.market_id).declared_subsidy =
                    pool_y + pool_n;
            }
            EconomyEvent::PositionMinted(mint) => {
                let coin_in = DecimalAmount::parse_non_negative(&mint.coin_in)?;
                let yes_out = DecimalAmount::parse_non_negative(&mint.yes_out)?;
                let no_out = DecimalAmount::parse_non_negative(&mint.no_out)?;
                if coin_in != yes_out || yes_out != no_out {
                    return Err(EconomyError::MintInvariantViolated(mint.market_id.clone()));
                }
                let market = ensure_tracked(&mut order, &mut markets, &mint.market_id);
                market.minted_coin += coin_in;
                market.minted_yes += yes_out;
                market.minted_no += no_out;
                if market.minted_coin != market.minted_yes || market.minted_yes != market.minted_no
                {
                    return Err(EconomyError::MintInvariantViolated(mint.market_id.clone()));
                }
                *yes_positions
                    .entry((mint.market_id.clone(), mint.agent_id.clone()))
                    .or_default() += yes_out;
                *no_positions
                    .entry((mint.market_id.clone(), mint.agent_id.clone()))
                    .or_default() += no_out;
            }
            EconomyEvent::AmmSwapExecuted(swap) => {
                let get_y = DecimalAmount::parse_non_negative(&swap.get_y)?;
                let get_n = DecimalAmount::parse_non_negative(&swap.get_n)?;
                let pay_coin = DecimalAmount::parse_non_negative(&swap.pay_coin)?;
                *yes_positions
                    .entry((swap.market_id.clone(), swap.trader_id.clone()))
                    .or_default() += get_y;
                *no_positions
                    .entry((swap.market_id.clone(), swap.trader_id.clone()))
                    .or_default() += get_n;
                ensure_tracked(&mut order, &mut markets, &swap.market_id).swap_pay_coin +=
                    pay_coin;
            }
            EconomyEvent::MarketSettled(settled) => {
                // CONFIRMED-bug-#4 fix: a second, conflicting MarketSettled for an
                // already-settled market must be a no-op here too (see the `settled` field
                // doc comment above) -- do not re-sum positions or add to redeemed_coin again.
                let already_settled = markets
                    .get(&settled.market_id)
                    .map(|market| market.settled)
                    .unwrap_or(false);
                if !already_settled {
                    let mut redeemed = DecimalAmount::default();
                    let side_positions = match settled.result.as_str() {
                        "YES" => Some(&yes_positions),
                        "NO" => Some(&no_positions),
                        _ => None,
                    };
                    if let Some(side_positions) = side_positions {
                        for ((market_id, _agent_id), amount) in side_positions {
                            if market_id == &settled.market_id {
                                redeemed += *amount;
                            }
                        }
                    }
                    let market = ensure_tracked(&mut order, &mut markets, &settled.market_id);
                    market.redeemed_coin += redeemed;
                    market.settled = true;
                }
            }
            EconomyEvent::RewardDistributed(reward) => {
                let reward_coin = DecimalAmount::parse_non_negative(&reward.reward_coin)?;
                let slash_coin = DecimalAmount::parse_non_negative(&reward.slash_coin)?;
                let market = ensure_tracked(&mut order, &mut markets, &reward.market_id);
                market.reward_coin += reward_coin;
                market.slash_coin += slash_coin;
            }
            // ADR-ECON-001: a principal declaration is an identity fact, not a coin-flow event;
            // it carries no market_id and never affects mint/redemption conservation math.
            EconomyEvent::PrincipalDeclared(_) => {}
        }
    }

    Ok(order
        .into_iter()
        .filter_map(|market_id| markets.remove(&market_id).map(|market| (market_id, market)))
        .map(|(market_id, market)| {
            let paid_out = market.redeemed_coin + market.reward_coin;
            let backed = market.minted_coin
                + market.declared_subsidy
                + market.swap_pay_coin
                + market.slash_coin;
            let holds = paid_out <= backed;
            MarketConservationReport {
                market_id,
                minted_coin: market.minted_coin.to_decimal_string(),
                declared_subsidy: market.declared_subsidy.to_decimal_string(),
                redeemed_coin: market.redeemed_coin.to_decimal_string(),
                holds,
            }
        })
        .collect())
}

// --- D5 defenses (agent-market, built day one, all checkable pre-append) -------------------

/// D5 self-trade prevention. A CPMM has no literal order-book counterparty (every trade is
/// against the pool, not another named principal), so the design's "existing opposite-side
/// principal in the same batch" rule is realized here as: a trader may not take the opposite
/// side of the SAME market immediately after their own most recent swap on it, with no other
/// principal's swap interposed (that interposition is what defines a fresh "clearing round").
/// This is exactly the wash-trade pattern D5 targets: paying the pool's slippage to yourself
/// on both sides extracts subsidized k-growth with zero genuine directional signal. Trading
/// the SAME side again, or trading opposite AFTER another principal has traded, is allowed.
///
/// ADR-ECON-001 (owner-ratified 2026-07-07, additive): the "last trader" tracker below now
/// compares resolved principals (via [`resolve_principal`]), not literal `trader_id` strings, so
/// an authority-declared puppet identity trading the interposing swap no longer resets the
/// tracker for its real principal. No declaration present -> resolves to the literal id,
/// identical to pre-ADR-ECON-001 behavior (back-compat).
pub fn check_self_trade(
    events: &[EconomyEvent],
    market_id: &str,
    trader_id: &str,
    side: &str,
) -> Result<(), EconomyError> {
    let query_principal = resolve_principal(events, trader_id);
    let mut last: Option<(String, String)> = None;
    for event in events {
        if let EconomyEvent::AmmSwapExecuted(swap) = event
            && swap.market_id == market_id
        {
            last = Some((
                resolve_principal(events, &swap.trader_id),
                swap.side.clone(),
            ));
        }
    }
    if let Some((last_principal, last_side)) = last
        && last_principal == query_principal
        && last_side != side
    {
        return Err(EconomyError::SelfTradeRejected(format!(
            "{trader_id} (principal {query_principal}) already holds {last_side} in the open clearing round for {market_id}; cannot also take {side} against the same pool with no other principal trading in between"
        )));
    }
    Ok(())
}

/// D5 principal-level position cap: aggregates a principal's total minted + swapped exposure
/// on `market_id` (existing on-tape positions plus the pending `pending_yes`/`pending_no` a
/// caller is about to add) and rejects if either side would exceed `cap`.
///
/// **Sybil-splitting (ADR-ECON-001, owner-ratified 2026-07-07, additive):** `principal_id` is
/// resolved through any [`EconomyEvent::PrincipalDeclared`] events present on `events` (see
/// [`resolve_principal`]) before aggregating, so an authority (ArchitectAI/owner) that has
/// declared several `agent_id`s to be the same principal gets them aggregated together here.
/// This is governance declaration + predicate enforcement, not automatic Sybil detection (out
/// of scope per the ADR): a puppet `agent_id` with no declaration on the given `events` tape
/// still resolves to itself, identical to pre-ADR-ECON-001 behavior (back-compat).
pub fn check_principal_position_cap(
    events: &[EconomyEvent],
    market_id: &str,
    principal_id: &str,
    pending_yes: &str,
    pending_no: &str,
    cap: &str,
) -> Result<(), EconomyError> {
    let cap = DecimalAmount::parse_non_negative(cap)?;
    let (mut yes, mut no) = principal_position(events, market_id, principal_id)?;
    yes += DecimalAmount::parse_non_negative(pending_yes)?;
    no += DecimalAmount::parse_non_negative(pending_no)?;
    if yes > cap || no > cap {
        return Err(EconomyError::PrincipalPositionCapExceeded(format!(
            "{principal_id} would hold yes={} no={} on {market_id}, exceeding principal cap {}",
            yes.to_decimal_string(),
            no.to_decimal_string(),
            cap.to_decimal_string()
        )));
    }
    Ok(())
}

/// D5 proposer-conflict rule: a capsule's proposer may not hold NO on its own market above a
/// de-minimis cap ("betting against your own claimed work is the honest-signal direction;
/// betting YES on it is fine and is the point"). Measured as NET NO exposure (`no - yes`,
/// floored at zero) rather than raw `no_position`, so the proposer's own CTF mint -- which by
/// construction always yields `yes_out == no_out` (see [`EconomyEvent::position_minted`]) --
/// never trips this on its own; only a directional swap into NO creates net NO exposure. A
/// no-op (`Ok`) when `trader_id` does not resolve to the same principal as `proposer_id`, or
/// `proposer_id` is empty (market not bound to a proposer, e.g. a pre-D4 fixture).
///
/// ADR-ECON-001 (owner-ratified 2026-07-07, additive): the no-op guard and the aggregation below
/// both compare/resolve through [`resolve_principal`], so a puppet `agent_id` declared (via
/// [`EconomyEvent::PrincipalDeclared`] on the given `events`) to be the same principal as
/// `proposer_id` is caught even though its literal `trader_id` differs. No declaration -> falls
/// back to literal string comparison, identical to pre-ADR-ECON-001 behavior (back-compat).
pub fn check_proposer_conflict(
    events: &[EconomyEvent],
    market_id: &str,
    proposer_id: &str,
    trader_id: &str,
    pending_yes: &str,
    pending_no: &str,
    de_minimis_cap: &str,
) -> Result<(), EconomyError> {
    if proposer_id.is_empty()
        || resolve_principal(events, trader_id) != resolve_principal(events, proposer_id)
    {
        return Ok(());
    }
    let cap = DecimalAmount::parse_non_negative(de_minimis_cap)?;
    let (mut yes, mut no) = principal_position(events, market_id, proposer_id)?;
    yes += DecimalAmount::parse_non_negative(pending_yes)?;
    no += DecimalAmount::parse_non_negative(pending_no)?;
    let net_no = if no > yes {
        no - yes
    } else {
        DecimalAmount::default()
    };
    if net_no > cap {
        return Err(EconomyError::ProposerConflictRejected(format!(
            "proposer {proposer_id} would hold net NO {} on its own market {market_id}, exceeding de-minimis {}",
            net_no.to_decimal_string(),
            cap.to_decimal_string()
        )));
    }
    Ok(())
}

/// ADR-ECON-001 (owner-ratified 2026-07-07, additive): resolves `agent_id` to its
/// authority-declared principal by scanning `events` for a matching
/// [`EconomyEvent::PrincipalDeclared`] (last declaration on the tape wins, so a governance
/// correction later on the same tape supersedes an earlier one). Falls back to `agent_id`
/// itself when no declaration names it -- exactly the pre-ADR-ECON-001 `principal_id ==
/// agent_id` behavior, so every existing caller/fixture that never emits `PrincipalDeclared`
/// is unaffected (back-compat).
fn resolve_principal(events: &[EconomyEvent], agent_id: &str) -> String {
    events
        .iter()
        .rev()
        .find_map(|event| match event {
            EconomyEvent::PrincipalDeclared(declared) if declared.agent_id == agent_id => {
                Some(declared.principal_id.clone())
            }
            _ => None,
        })
        .unwrap_or_else(|| agent_id.to_string())
}

/// Shared aggregation for the two principal-scoped D5 checks above: existing minted +
/// swapped (yes, no) exposure for `principal_id` on `market_id`, from the tape alone.
///
/// ADR-ECON-001 (owner-ratified 2026-07-07, additive): both the query identity and each
/// candidate event's actor identity are resolved through [`resolve_principal`] before
/// comparing, so declared puppet `agent_id`s aggregate under their real principal. With no
/// `PrincipalDeclared` events on `events`, every resolution is a no-op and this is byte-for-byte
/// the pre-ADR-ECON-001 literal-string match (back-compat).
fn principal_position(
    events: &[EconomyEvent],
    market_id: &str,
    principal_id: &str,
) -> Result<(DecimalAmount, DecimalAmount), EconomyError> {
    let query_principal = resolve_principal(events, principal_id);
    let (mut yes, mut no) = (DecimalAmount::default(), DecimalAmount::default());
    for event in events {
        match event {
            EconomyEvent::PositionMinted(mint)
                if mint.market_id == market_id
                    && resolve_principal(events, &mint.agent_id) == query_principal =>
            {
                yes += DecimalAmount::parse_non_negative(&mint.yes_out)?;
                no += DecimalAmount::parse_non_negative(&mint.no_out)?;
            }
            EconomyEvent::AmmSwapExecuted(swap)
                if swap.market_id == market_id
                    && resolve_principal(events, &swap.trader_id) == query_principal =>
            {
                yes += DecimalAmount::parse_non_negative(&swap.get_y)?;
                no += DecimalAmount::parse_non_negative(&swap.get_n)?;
            }
            _ => {}
        }
    }
    Ok((yes, no))
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum MarketRouterMode {
    Shadow,
    AssistedFuture,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CandidateRoute {
    pub route_id: String,
    pub market_id: String,
    pub expected_failure_domain: String,
    pub requested_tokens: u64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PriceSignal {
    pub market_id: String,
    pub yes_price: String,
    pub no_price: String,
    pub truth_status: String,
}

/// G2 (`RES_ECON_emergence_toplevel_design_20260707.md` §4 "价格活化" row; spec source
/// `ADR-ECON-003` Decision 6.1): `AmmSwapExecuted.effective_price` is a `pub` field that
/// (per the design doc's full-repo audit) has zero downstream readers today -- every
/// `PriceSignal` consumed by `MarketRouter::suggest` is instead hand-built from an
/// RPC-supplied static input (see `turing-daemons::parse_signals` and
/// `turing-qualification`'s `PriceSignal` construction). This function makes the AMM pool
/// state already committed to the tape into a second, tape-derived price source, without
/// touching either existing call site: both keep constructing `PriceSignal` exactly as
/// before, so this is purely additive (RPC static-input path remains the fallback per the
/// design doc's WP2 row and ADR-ECON-003 Decision 6.1's `P = 0.5` no-information branch for
/// markets this function has no opinion on).
///
/// Pure function, deterministic fold over `events` in tape order (Art 0.2: no I/O, no
/// live-random, no wall-clock, no map/set iteration-order dependence -- the intermediate
/// accumulator is a `BTreeMap` keyed by `market_id` and the final `Vec` is emitted in that
/// same sorted key order). For each `market_id` that has at least one `AmmSwapExecuted` in
/// `events`, the *last such event in tape order* determines the derived yes-side price
/// (ADR-ECON-003 Decision 6.1: "取最近一次 AmmSwapExecuted.effective_price 的 yes
/// 侧"): a `BUY_YES` swap's `effective_price` already denominates the yes side directly;
/// a `BUY_NO` swap's `effective_price` denominates the no side, so it is complemented
/// (`1 - price`) to read as a yes-side price. Both readings are clamped to `[0, 1]`
/// (Decision 6.1: "clamp 到 [0,1]") because a late-stage swap that nearly drains one side of
/// the pool can otherwise push the raw ratio outside the unit interval. `no_price` is
/// reported as the clamped complement of `yes_price`, and `truth_status` is always
/// `"statistical_signal_only"` -- the same literal `MarketCreated`/`PriceBroadcast` already
/// use everywhere else in this crate to mark a price as a statistical signal, never ground
/// truth (Art I.1). Markets with no `AmmSwapExecuted` in `events` emit no signal at all
/// (absence, not a zero/default price) so callers can distinguish "no AMM-derived price yet"
/// from "AMM says 0".
///
/// Because this is a pure fold over already-committed tape events with no hidden state, it
/// satisfies the conservation invariant the design doc requires verbatim: calling it twice
/// on the same tape slice -- i.e. re-deriving it as if the tape had been read back out of
/// storage and replayed -- always produces the identical `Vec<PriceSignal>`
/// (`tests/economy_market.rs::derive_price_signals_conservation_replay_equality`).
pub fn derive_price_signals(events: &[EconomyEvent]) -> Result<Vec<PriceSignal>, EconomyError> {
    let mut latest_yes_price: BTreeMap<String, DecimalAmount> = BTreeMap::new();
    for event in events {
        if let EconomyEvent::AmmSwapExecuted(swap) = event {
            let price = DecimalAmount::parse_non_negative(&swap.effective_price)?;
            let yes_price = match swap.side.as_str() {
                "BUY_NO" => clamp_unit_interval(unit_amount() - price),
                _ => clamp_unit_interval(price),
            };
            latest_yes_price.insert(swap.market_id.clone(), yes_price);
        }
    }
    Ok(latest_yes_price
        .into_iter()
        .map(|(market_id, yes_price)| {
            let no_price = clamp_unit_interval(unit_amount() - yes_price);
            PriceSignal {
                market_id,
                yes_price: yes_price.to_decimal_string(),
                no_price: no_price.to_decimal_string(),
                truth_status: "statistical_signal_only".to_string(),
            }
        })
        .collect())
}

/// `DecimalAmount` representation of `1.0`, used only by [`derive_price_signals`]'s
/// yes/no-complement and `[0, 1]` clamp arithmetic.
fn unit_amount() -> DecimalAmount {
    DecimalAmount { units: SCALE }
}

/// Clamps a `DecimalAmount` into `[0, 1]` (see [`derive_price_signals`]).
fn clamp_unit_interval(amount: DecimalAmount) -> DecimalAmount {
    if amount.units < 0 {
        DecimalAmount { units: 0 }
    } else if amount.units > SCALE {
        unit_amount()
    } else {
        amount
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BudgetSuggestion {
    pub schema_id: String,
    pub mode: MarketRouterMode,
    pub route_id: String,
    pub market_id: String,
    pub price_signal_hash: String,
    pub pput_prior_hash: String,
    pub diversity_policy_hash: String,
    pub max_tokens: u64,
    pub emits_authorization: bool,
    pub can_move_accepted_head: bool,
    pub head_effect: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct MarketRouter {
    mode: MarketRouterMode,
}

impl MarketRouter {
    #[must_use]
    pub fn new(mode: MarketRouterMode) -> Self {
        MarketRouter { mode }
    }

    pub fn suggest(
        &self,
        routes: &[CandidateRoute],
        signals: &[PriceSignal],
        price_signal_hash: &str,
        pput_prior_hash: &str,
    ) -> Result<BudgetSuggestion, EconomyError> {
        validate_digest(price_signal_hash)?;
        validate_digest(pput_prior_hash)?;
        if routes.is_empty() {
            return Err(EconomyError::NoCandidateRoutes);
        }

        let mut best: Option<(&CandidateRoute, DecimalAmount)> = None;
        for route in routes {
            let yes_price = signals
                .iter()
                .find(|signal| {
                    signal.market_id == route.market_id
                        && signal.truth_status == "statistical_signal_only"
                })
                .map(|signal| DecimalAmount::parse_non_negative(&signal.yes_price))
                .transpose()?
                .unwrap_or_default();
            if best
                .as_ref()
                .is_none_or(|(_, best_price)| yes_price > *best_price)
            {
                best = Some((route, yes_price));
            }
        }
        let route = best
            .map(|(route, _)| route)
            .ok_or(EconomyError::NoCandidateRoutes)?;
        Ok(BudgetSuggestion {
            schema_id: "budget_allocated.v1".to_string(),
            mode: self.mode,
            route_id: route.route_id.clone(),
            market_id: route.market_id.clone(),
            price_signal_hash: price_signal_hash.to_string(),
            pput_prior_hash: pput_prior_hash.to_string(),
            diversity_policy_hash:
                "sha256:0000000000000000000000000000000000000000000000000000000000000000"
                    .to_string(),
            max_tokens: route.requested_tokens,
            emits_authorization: false,
            can_move_accepted_head: false,
            head_effect: "PRESERVE".to_string(),
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PriceBroadcast {
    pub schema_id: String,
    pub market_id: String,
    pub yes_price: String,
    pub no_price: String,
    pub price_signal_hash: String,
    pub truth_status: String,
    pub head_effect: String,
}

impl PriceBroadcast {
    pub fn new(
        market_id: impl Into<String>,
        yes_price: &str,
        no_price: &str,
        price_signal_hash: &str,
    ) -> Result<Self, EconomyError> {
        validate_digest(price_signal_hash)?;
        let yes_price = DecimalAmount::parse_non_negative(yes_price)?;
        let no_price = DecimalAmount::parse_non_negative(no_price)?;
        Ok(PriceBroadcast {
            schema_id: "market_price_broadcast.v1".to_string(),
            market_id: market_id.into(),
            yes_price: yes_price.to_decimal_string(),
            no_price: no_price.to_decimal_string(),
            price_signal_hash: price_signal_hash.to_string(),
            truth_status: "statistical_signal_only".to_string(),
            head_effect: "PRESERVE".to_string(),
        })
    }

    #[must_use]
    pub fn worker_visible_summary(&self) -> String {
        format!(
            "Market {} broadcasts YES price {} and NO price {} as a statistical signal.",
            self.market_id, self.yes_price, self.no_price
        )
    }
}

#[derive(Debug, Default, Clone, PartialEq, Eq)]
struct WalletInternal {
    coin: DecimalAmount,
    yes_positions: BTreeMap<String, DecimalAmount>,
    no_positions: BTreeMap<String, DecimalAmount>,
}

impl WalletInternal {
    fn add_yes(&mut self, market_id: &str, amount: DecimalAmount) {
        *self.yes_positions.entry(market_id.to_string()).or_default() += amount;
    }

    fn add_no(&mut self, market_id: &str, amount: DecimalAmount) {
        *self.no_positions.entry(market_id.to_string()).or_default() += amount;
    }
}

fn format_positions(positions: BTreeMap<String, DecimalAmount>) -> BTreeMap<String, String> {
    positions
        .into_iter()
        .map(|(market_id, amount)| (market_id, amount.to_decimal_string()))
        .collect()
}

#[derive(Debug, Default, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
struct DecimalAmount {
    units: i128,
}

impl DecimalAmount {
    fn parse_non_negative(raw: &str) -> Result<Self, EconomyError> {
        if raw.is_empty() || raw.contains('e') || raw.contains('E') || raw.starts_with('-') {
            return Err(EconomyError::InvalidDecimalString(raw.to_string()));
        }
        let mut split = raw.split('.');
        let whole = split
            .next()
            .ok_or_else(|| EconomyError::InvalidDecimalString(raw.to_string()))?;
        let fraction = split.next();
        if split.next().is_some() || whole.is_empty() {
            return Err(EconomyError::InvalidDecimalString(raw.to_string()));
        }
        if !whole.bytes().all(|b| b.is_ascii_digit()) {
            return Err(EconomyError::InvalidDecimalString(raw.to_string()));
        }
        let whole_units = whole
            .parse::<i128>()
            .map_err(|_| EconomyError::InvalidDecimalString(raw.to_string()))?
            .checked_mul(SCALE)
            .ok_or_else(|| EconomyError::InvalidDecimalString(raw.to_string()))?;
        let fraction_units = match fraction {
            Some("") => return Err(EconomyError::InvalidDecimalString(raw.to_string())),
            Some(fraction) => {
                if fraction.len() > 9 || !fraction.bytes().all(|b| b.is_ascii_digit()) {
                    return Err(EconomyError::InvalidDecimalString(raw.to_string()));
                }
                let padded = format!("{fraction:0<9}");
                padded
                    .parse::<i128>()
                    .map_err(|_| EconomyError::InvalidDecimalString(raw.to_string()))?
            }
            None => 0,
        };
        Ok(DecimalAmount {
            units: whole_units + fraction_units,
        })
    }

    fn is_zero(self) -> bool {
        self.units == 0
    }

    /// INV-7 fix: the intermediate product `left.units * right.units` can exceed `i128::MAX`
    /// for organically reachable pool/pay magnitudes (e.g. pool = pay = 2e10 decimal already
    /// overflows, since raw units are scaled by SCALE=1e9). A bare `*` either panics (dev
    /// profile, `overflow-checks = true`) or silently wraps to a corrupted value (release
    /// profile, `overflow-checks = false` by default with no workspace override) — in the
    /// release case the corrupted, wrapped value is exactly what gets written to the tape and
    /// then re-validated by `assert_k_non_decreasing`/`verify_swap_post_trade_invariant`, which
    /// re-derive `k` with the same vulnerable multiply and are therefore blind to the
    /// corruption. `checked_mul` never panics and never wraps; on overflow we surface a
    /// explicit `ArithmeticOverflow` error so the caller (`buy_yes`/`buy_no`) cleanly refuses
    /// the trade instead of emitting a corrupted swap event, in both dev and release profiles.
    fn mul(left: DecimalAmount, right: DecimalAmount) -> Result<DecimalAmount, EconomyError> {
        let product = left
            .units
            .checked_mul(right.units)
            .ok_or(EconomyError::ArithmeticOverflow)?;
        Ok(DecimalAmount {
            units: product / SCALE,
        })
    }

    fn mul_div(
        self,
        numerator: DecimalAmount,
        denominator: DecimalAmount,
    ) -> Result<DecimalAmount, EconomyError> {
        if denominator.is_zero() {
            return Err(EconomyError::DivisionByZero);
        }
        let product = self
            .units
            .checked_mul(numerator.units)
            .ok_or(EconomyError::ArithmeticOverflow)?;
        Ok(DecimalAmount {
            units: product / denominator.units,
        })
    }

    fn ratio(
        numerator: DecimalAmount,
        denominator: DecimalAmount,
    ) -> Result<DecimalAmount, EconomyError> {
        if denominator.is_zero() {
            return Err(EconomyError::DivisionByZero);
        }
        let product = numerator
            .units
            .checked_mul(SCALE)
            .ok_or(EconomyError::ArithmeticOverflow)?;
        Ok(DecimalAmount {
            units: product / denominator.units,
        })
    }

    fn to_decimal_string(self) -> String {
        let negative = self.units < 0;
        let abs = self.units.abs();
        let whole = abs / SCALE;
        let mut fraction = format!("{:09}", abs % SCALE);
        while fraction.ends_with('0') {
            fraction.pop();
        }
        let sign = if negative { "-" } else { "" };
        if fraction.is_empty() {
            format!("{sign}{whole}")
        } else {
            format!("{sign}{whole}.{fraction}")
        }
    }
}

impl std::ops::Add for DecimalAmount {
    type Output = DecimalAmount;

    fn add(self, rhs: Self) -> Self::Output {
        DecimalAmount {
            units: self.units + rhs.units,
        }
    }
}

impl std::ops::AddAssign for DecimalAmount {
    fn add_assign(&mut self, rhs: Self) {
        self.units += rhs.units;
    }
}

impl std::ops::Sub for DecimalAmount {
    type Output = DecimalAmount;

    fn sub(self, rhs: Self) -> Self::Output {
        DecimalAmount {
            units: self.units - rhs.units,
        }
    }
}

impl std::ops::SubAssign for DecimalAmount {
    fn sub_assign(&mut self, rhs: Self) {
        self.units -= rhs.units;
    }
}

impl std::ops::Neg for DecimalAmount {
    type Output = DecimalAmount;

    fn neg(self) -> Self::Output {
        DecimalAmount { units: -self.units }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum EconomyError {
    InvalidDecimalString(String),
    InvalidDigest(String),
    ZeroPool,
    ZeroPay,
    DivisionByZero,
    ArithmeticOverflow,
    UnknownMarket(String),
    NoCandidateRoutes,
    InvalidMicroEventId(String),
    InvalidSettlementResult(String),
    PostTradeInvariantViolated { k_before: String, k_after: String },
    MintInvariantViolated(String),
    SelfTradeRejected(String),
    PrincipalPositionCapExceeded(String),
    ProposerConflictRejected(String),
}

impl std::fmt::Display for EconomyError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            EconomyError::InvalidDecimalString(value) => {
                write!(f, "invalid decimal_string {value:?}")
            }
            EconomyError::InvalidDigest(digest) => write!(f, "invalid digest {digest:?}"),
            EconomyError::ZeroPool => write!(f, "AMM pools must be non-zero"),
            EconomyError::ZeroPay => write!(f, "AMM pay_coin must be non-zero"),
            EconomyError::DivisionByZero => write!(f, "division by zero"),
            EconomyError::ArithmeticOverflow => write!(
                f,
                "arithmetic overflow: intermediate product exceeds i128 range (INV-7)"
            ),
            EconomyError::UnknownMarket(market_id) => write!(f, "unknown market {market_id:?}"),
            EconomyError::NoCandidateRoutes => write!(f, "no candidate routes available"),
            EconomyError::InvalidMicroEventId(id) => write!(f, "invalid Micro event id {id:?}"),
            EconomyError::InvalidSettlementResult(result) => {
                write!(f, "invalid settlement result {result:?}")
            }
            EconomyError::PostTradeInvariantViolated { k_before, k_after } => {
                write!(
                    f,
                    "post-trade invariant violated: k_after {k_after} < k_before {k_before} (rounding favored the trader)"
                )
            }
            EconomyError::MintInvariantViolated(market_id) => {
                write!(
                    f,
                    "mint invariant violated for market {market_id:?}: coin_in != yes_out or yes_out != no_out"
                )
            }
            EconomyError::SelfTradeRejected(detail) => {
                write!(f, "D5 self-trade prevention: {detail}")
            }
            EconomyError::PrincipalPositionCapExceeded(detail) => {
                write!(f, "D5 principal position cap: {detail}")
            }
            EconomyError::ProposerConflictRejected(detail) => {
                write!(f, "D5 proposer-conflict rule: {detail}")
            }
        }
    }
}

impl std::error::Error for EconomyError {}

fn validate_digest(value: &str) -> Result<(), EconomyError> {
    let rest = value
        .strip_prefix("sha256:")
        .ok_or_else(|| EconomyError::InvalidDigest(value.to_string()))?;
    if rest.len() != 64 || !rest.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err(EconomyError::InvalidDigest(value.to_string()));
    }
    Ok(())
}
