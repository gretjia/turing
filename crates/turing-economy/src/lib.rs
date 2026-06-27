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
}

impl EconomyEvent {
    pub fn market_created(
        market_id: impl Into<String>,
        pool_y: &str,
        pool_n: &str,
    ) -> Result<Self, EconomyError> {
        let pool = AmmPool::new(market_id.into(), pool_y, pool_n)?;
        let k = pool.k_string();
        Ok(EconomyEvent::MarketCreated(MarketCreated {
            schema_id: "market_created.v1".to_string(),
            event_type: "MarketCreated".to_string(),
            head_effect: "PRESERVE".to_string(),
            market_id: pool.market_id,
            initial_pool_y: pool.pool_y.to_decimal_string(),
            initial_pool_n: pool.pool_n.to_decimal_string(),
            k,
            truth_status: "statistical_signal_only".to_string(),
        }))
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
            invariant_k_before: self.k_string(),
            invariant_k_after: DecimalAmount::mul(pool_y_after, pool_n_after).to_decimal_string(),
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
            invariant_k_before: self.k_string(),
            invariant_k_after: DecimalAmount::mul(pool_y_after, pool_n_after).to_decimal_string(),
            effective_price: DecimalAmount::ratio(pay, get_n)?.to_decimal_string(),
        })
    }

    fn k_string(&self) -> String {
        DecimalAmount::mul(self.pool_y, self.pool_n).to_decimal_string()
    }
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
                    markets.insert(
                        created.market_id.clone(),
                        MarketProjection {
                            market_id: created.market_id.clone(),
                            pool_y: created.initial_pool_y.clone(),
                            pool_n: created.initial_pool_n.clone(),
                            status: "open".to_string(),
                            settlement_result: None,
                        },
                    );
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
                    market.status = "settled".to_string();
                    market.settlement_result = Some(settled.result.clone());
                }
                EconomyEvent::PositionMinted(_) | EconomyEvent::RewardDistributed(_) => {}
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
                EconomyEvent::RewardDistributed(reward) => {
                    let wallet = balances.entry(reward.agent_id.clone()).or_default();
                    wallet.coin += DecimalAmount::parse_non_negative(&reward.reward_coin)?;
                    wallet.coin -= DecimalAmount::parse_non_negative(&reward.slash_coin)?;
                }
                _ => {}
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

    fn mul(left: DecimalAmount, right: DecimalAmount) -> DecimalAmount {
        DecimalAmount {
            units: left.units * right.units / SCALE,
        }
    }

    fn mul_div(
        self,
        numerator: DecimalAmount,
        denominator: DecimalAmount,
    ) -> Result<DecimalAmount, EconomyError> {
        if denominator.is_zero() {
            return Err(EconomyError::DivisionByZero);
        }
        Ok(DecimalAmount {
            units: self.units * numerator.units / denominator.units,
        })
    }

    fn ratio(
        numerator: DecimalAmount,
        denominator: DecimalAmount,
    ) -> Result<DecimalAmount, EconomyError> {
        if denominator.is_zero() {
            return Err(EconomyError::DivisionByZero);
        }
        Ok(DecimalAmount {
            units: numerator.units * SCALE / denominator.units,
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
    ZeroPool,
    ZeroPay,
    DivisionByZero,
    UnknownMarket(String),
    InvalidMicroEventId(String),
    InvalidSettlementResult(String),
}

impl std::fmt::Display for EconomyError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            EconomyError::InvalidDecimalString(value) => {
                write!(f, "invalid decimal_string {value:?}")
            }
            EconomyError::ZeroPool => write!(f, "AMM pools must be non-zero"),
            EconomyError::ZeroPay => write!(f, "AMM pay_coin must be non-zero"),
            EconomyError::DivisionByZero => write!(f, "division by zero"),
            EconomyError::UnknownMarket(market_id) => write!(f, "unknown market {market_id:?}"),
            EconomyError::InvalidMicroEventId(id) => write!(f, "invalid Micro event id {id:?}"),
            EconomyError::InvalidSettlementResult(result) => {
                write!(f, "invalid settlement result {result:?}")
            }
        }
    }
}

impl std::error::Error for EconomyError {}
