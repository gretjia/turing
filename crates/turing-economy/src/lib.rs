//! Agent Economy CTF, AMM, market, and wallet projections.
//!
//! All load-bearing prices and balances are `decimal_string` values backed by fixed-point
//! integer math. This crate is a reducer/toolbox only; it does not move Micro heads.

use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use turing_contracts::identity::MicroOid;

/// WP3 (design doc R1.1 §7; ADR-ECON-003 Decisions 1/3/4/6): `(Q, N, P)` tape fold, τ(N)
/// annealing, N_eff floor arbitration hook. See module docs for scope.
pub mod routing_fold;

/// WP5 (design doc R1.1 §7; ADR-ECON-003 Decision 3): N_eff / H_lineage measurement --
/// the always-on monoculture guardrail *input* that feeds `routing_fold`'s existing floor
/// arbitration hook. See module docs for scope.
pub mod diversity_metrics;

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
    /// WP4 (design doc R1.1 §7 WP4/§4 G3; ADR-ECON-003 Decision 2/6): the independent
    /// verifier's (structurally separate from the ∏p accept predicate, per Decision 2)
    /// PASS/FAIL verdict on one routed scaffold attempt, additive and PRESERVE-class,
    /// following the same `ADDITIVE_AGENT_ECONOMY_V1_0` registry pattern as
    /// `PrincipalDeclared` above. Consumed only by `routing_fold::fold_routing_state`
    /// (via [`routing_fold::economy_events_to_routing_fold_events`]) to update a node's
    /// `(Q, N, P)` state; never moves `accepted_head`.
    RoutingPriorUpdated(RoutingPriorUpdated),
    /// WP4: an exact after-the-fact reversal of one earlier `RoutingPriorUpdated`
    /// (ADR-ECON-003 Decision 6.3 "clawback"), referenced by that event's own `event_hash`.
    /// Additive, PRESERVE-class, same registry pattern.
    RoutingPriorClawback(RoutingPriorClawback),
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

    /// WP4 (design doc R1.1 §7 WP4; ADR-ECON-003 Decision 2/6): construct an independent
    /// verifier's verdict event on one `(route_domain, route_scaffold)` routing key. Additive,
    /// PRESERVE-class, follows the `principal_declared` constructor's ADDITIVE_AGENT_ECONOMY_V1_0
    /// pattern above.
    ///
    /// `verdict_source_id` identifies which independent verifier instance produced the
    /// verdict (ADR-ECON-003 Decision 2.2: a structurally separate crate/binary from the
    /// ∏p accept predicate) -- opaque to this constructor, carries no formula/threshold value.
    /// `verifier_attestation_hash` must already be a `sha256:`-prefixed 64-hex digest (same
    /// format as `price_signal_hash`/`pput_prior_hash` above).
    ///
    /// `event_hash` is *derived*, not caller-supplied: a JCS-SHA256 digest over the event's
    /// own identity fields (Art 0.2 determinism -- the same five inputs always fold to the
    /// same `event_hash`, so a `RoutingPriorClawback` can reference it exactly and
    /// `routing_fold::fold_routing_state`'s duplicate-hash dedup is meaningful).
    pub fn routing_prior_updated(
        route_domain: impl Into<String>,
        route_scaffold: impl Into<String>,
        verdict: bool,
        verdict_source_id: impl Into<String>,
        verifier_attestation_hash: impl Into<String>,
    ) -> Result<Self, EconomyError> {
        let route_domain = route_domain.into();
        let route_scaffold = route_scaffold.into();
        let verdict_source_id = verdict_source_id.into();
        let verifier_attestation_hash = verifier_attestation_hash.into();
        validate_digest(&verifier_attestation_hash)?;

        let event_hash = routing_prior_event_hash(
            &route_domain,
            &route_scaffold,
            verdict,
            &verdict_source_id,
            &verifier_attestation_hash,
        )?;

        Ok(EconomyEvent::RoutingPriorUpdated(RoutingPriorUpdated {
            schema_id: "routing_prior_updated.v1".to_string(),
            event_type: "RoutingPriorUpdated".to_string(),
            head_effect: "PRESERVE".to_string(),
            route_domain,
            route_scaffold,
            verdict,
            verdict_source_id,
            verifier_attestation_hash,
            event_hash,
        }))
    }

    /// WP4 (ADR-ECON-003 Decision 6.3): an exact inverse of one earlier
    /// `RoutingPriorUpdated`, referenced by that event's own `event_hash` (as produced by
    /// [`Self::routing_prior_updated`]). Additive, PRESERVE-class. Validity of the
    /// reference (must exist, must not already be clawed back) is enforced downstream by
    /// `routing_fold::fold_routing_state`, not here -- this constructor only shapes the
    /// event.
    pub fn routing_prior_clawback(updated_event_hash: impl Into<String>) -> Result<Self, EconomyError> {
        let updated_event_hash = updated_event_hash.into();
        validate_digest(&updated_event_hash)?;
        Ok(EconomyEvent::RoutingPriorClawback(RoutingPriorClawback {
            schema_id: "routing_prior_clawback.v1".to_string(),
            event_type: "RoutingPriorClawback".to_string(),
            head_effect: "PRESERVE".to_string(),
            updated_event_hash,
        }))
    }
}

/// `event_hash` for a `RoutingPriorUpdated` event (ADR-ECON-003 Decision 6.3 dedup key):
/// JCS-canonicalize the event's own identity fields and SHA-256 them, same codec used by
/// `routing_fold::scaffold_id` (`turing_contracts::jcs`). Pure function of its five
/// arguments only (Art 0.2) -- never reads clock/random/global state, so the same tape
/// replayed twice always derives byte-identical `event_hash`es.
fn routing_prior_event_hash(
    route_domain: &str,
    route_scaffold: &str,
    verdict: bool,
    verdict_source_id: &str,
    verifier_attestation_hash: &str,
) -> Result<String, EconomyError> {
    let value = serde_json::json!({
        "schema": "routing_prior_updated_identity.v1",
        "route_domain": route_domain,
        "route_scaffold": route_scaffold,
        "verdict": verdict,
        "verdict_source_id": verdict_source_id,
        "verifier_attestation_hash": verifier_attestation_hash,
    });
    let canonical = turing_contracts::jcs::canonicalize(&value)
        .map_err(|e| EconomyError::InvalidRoutingEventIdentity(e.to_string()))?;
    Ok(format!(
        "sha256:{}",
        turing_contracts::jcs::sha256_hex(&canonical)
    ))
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

/// WP4 (design doc R1.1 §7 WP4/§4 G3; ADR-ECON-003 Decision 2/6): one independent
/// verifier's PASS/FAIL verdict on a routed `(route_domain, route_scaffold)` attempt.
/// Additive, PRESERVE-class -- see [`EconomyEvent::routing_prior_updated`]. Consumed by
/// `routing_fold::economy_events_to_routing_fold_events` to feed
/// `routing_fold::fold_routing_state` (WP3's pre-existing seam); this struct itself never
/// carries a τ/λ/floor value (Art III.4/F4) -- only the routing key (as
/// caller-computed opaque strings; see `routing_fold::domain_bucket`/`scaffold_id` key
/// functions), the verdict bit, and the independent-verifier provenance.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RoutingPriorUpdated {
    pub schema_id: String,
    pub event_type: String,
    pub head_effect: String,
    /// The routed key's domain component (ADR-ECON-003 Decision 1 `domain_bucket` key
    /// function's *output value*, carried under a non-reserved field name -- see the F4
    /// gate's identifier-only scan surface, `tools/gates/gate_f4_econ_leakage.sh`).
    pub route_domain: String,
    /// The routed key's scaffold component (ADR-ECON-003 Decision 1 `scaffold_id` key
    /// function's *output value*; same field-naming rationale as `route_domain` above).
    pub route_scaffold: String,
    /// Independent verifier's verdict (ADR-ECON-003 Decision 2; `true` = PASS).
    pub verdict: bool,
    /// Identifies which independent verifier instance produced this verdict (ADR-ECON-003
    /// Decision 2.2: structurally separate from the ∏p accept predicate). Opaque string.
    pub verdict_source_id: String,
    /// `sha256:`-prefixed 64-hex attestation digest from the independent verifier.
    pub verifier_attestation_hash: String,
    /// JCS-SHA256 identity digest over this event's own fields (see
    /// [`EconomyEvent::routing_prior_updated`]); the dedup/reference key a later
    /// `RoutingPriorClawback` names.
    pub event_hash: String,
}

/// WP4 (ADR-ECON-003 Decision 6.3): exact after-the-fact reversal of one earlier
/// `RoutingPriorUpdated`. Additive, PRESERVE-class.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RoutingPriorClawback {
    pub schema_id: String,
    pub event_type: String,
    pub head_effect: String,
    /// References the `event_hash` of the `RoutingPriorUpdated` being reversed.
    pub updated_event_hash: String,
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
                | EconomyEvent::PrincipalDeclared(_)
                // WP4: independent-verifier routing-prior events are not market state
                // (no market_id, no coin flow) -- they only feed `routing_fold`'s (Q, N, P)
                // fold, a separate projection entirely.
                | EconomyEvent::RoutingPriorUpdated(_)
                | EconomyEvent::RoutingPriorClawback(_) => {}
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
                EconomyEvent::MarketCreated(_)
                | EconomyEvent::PrincipalDeclared(_)
                | EconomyEvent::RoutingPriorUpdated(_)
                | EconomyEvent::RoutingPriorClawback(_) => {}
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
            // WP4: routing-prior events are likewise not coin-flow (no market_id, no
            // minted/redeemed/reward coin) -- excluded from conservation math for the same
            // reason, symmetric with PrincipalDeclared above.
            EconomyEvent::PrincipalDeclared(_)
            | EconomyEvent::RoutingPriorUpdated(_)
            | EconomyEvent::RoutingPriorClawback(_) => {}
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
    /// ADR-ECON-003 (design doc R1.1 §1.2/§4 G1): deterministic seeded softmax(Q/τ)
    /// selection. τ configuration lives on `MarketRouter` (see `new_softmax`), never on
    /// this marker -- the mode label itself is A-zone ("a softmax route exists" is public
    /// per ADR-ECON-003 Decision 5), while the τ value stays B-zone (Art III.4).
    Softmax,
}

/// Q32.32 fixed-point τ mantissa for `SoftmaxTemperature::Finite` (ADR-ECON-003 Decision 4).
/// B-zone (Art III.4): the wrapped value must never be echoed into any agent-visible
/// surface (error message / log / `BudgetSuggestion` field / tool schema / doc).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TauQ32(u64);

impl TauQ32 {
    /// `raw_q32_mantissa` = round(τ · 2^32); must be strictly positive. τ=0 is not a valid
    /// `Finite` value -- use `SoftmaxTemperature::ArgmaxBypass` instead (ADR-ECON-003
    /// Decision 4 "τ=0 = 模式旁路"), so "bypass" is a type-level state, not a runtime check
    /// against a magic zero.
    pub fn new(raw_q32_mantissa: u64) -> Result<Self, EconomyError> {
        if raw_q32_mantissa == 0 {
            return Err(EconomyError::InvalidSoftmaxTemperature);
        }
        Ok(TauQ32(raw_q32_mantissa))
    }

    fn raw_q32(self) -> i128 {
        self.0 as i128
    }
}

/// Selection temperature for `MarketRouterMode::Softmax` (ADR-ECON-003 Decision 4 extreme
/// -- and limit-- semantics). B-zone (Art III.4): callers must never echo the wrapped
/// configuration into any agent-visible surface.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SoftmaxTemperature {
    /// τ=0: mode-bypass -- routes through the exact same argmax code path as
    /// `Shadow`/`AssistedFuture` (ADR-ECON-003 Decision 4).
    ArgmaxBypass,
    /// 0 < τ < ∞.
    Finite(TauQ32),
    /// τ=∞: uniform distribution over the sorted `route_id` order (ADR-ECON-003 Decision 4).
    Uniform,
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

/// ADR-ECON-003 Decision 5 A-zone artifact (design doc §7 WP5): the committed public
/// diversity policy document whose SHA-256 digest replaces the previous all-zero
/// `diversity_policy_hash` placeholder. Embedded at compile time (same `include_str!`
/// pattern already used by `turing-contracts` for its pinned pack registries), so the
/// hash below is always computed from the exact bytes of this file, never hand-typed.
///
/// Deliberately A-zone only: this document states that the monoculture guardrail exists
/// and is enforced, without restating any B-zone quantity (Art III.4) -- see the
/// document's own text for the exact scope boundary.
const DIVERSITY_POLICY_DOCUMENT: &str =
    include_str!("../../../docs/policy/DIVERSITY-POLICY-v1.md");

/// `"sha256:" + hex(SHA256(DIVERSITY_POLICY_DOCUMENT))` (design doc §7 WP5 acceptance:
/// "hash == 公开策略文档 sha256"). A pure function of the embedded document bytes only,
/// so it is deterministic and tape-reconstructable (Art 0.2) exactly like every other
/// digest in this module.
#[must_use]
pub fn diversity_policy_hash() -> String {
    let mut hasher = Sha256::new();
    hasher.update(DIVERSITY_POLICY_DOCUMENT.as_bytes());
    format!("sha256:{:x}", hasher.finalize())
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
    /// Only consulted when `mode == MarketRouterMode::Softmax`; ignored otherwise. Defaults
    /// to `ArgmaxBypass` (ADR-ECON-003's own τ=0 mode-bypass semantics) so an unconfigured
    /// `Softmax` router has a safe, spec-defined default rather than a fabricated τ value
    /// (ADR-ECON-003 Decision 5 B-zone mechanism).
    softmax_temperature: SoftmaxTemperature,
}

impl MarketRouter {
    #[must_use]
    pub fn new(mode: MarketRouterMode) -> Self {
        MarketRouter {
            mode,
            softmax_temperature: SoftmaxTemperature::ArgmaxBypass,
        }
    }

    /// Construct a `Softmax`-mode router with an explicit τ configuration (ADR-ECON-003
    /// Decision 4/5). The `temperature` value is B-zone (Art III.4): callers must never
    /// echo it back through any agent-visible surface.
    #[must_use]
    pub fn new_softmax(temperature: SoftmaxTemperature) -> Self {
        MarketRouter {
            mode: MarketRouterMode::Softmax,
            softmax_temperature: temperature,
        }
    }

    /// The router's mode label. A-zone (ADR-ECON-003 Decision 5): safe to surface.
    #[must_use]
    pub fn mode(&self) -> MarketRouterMode {
        self.mode
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

        let mut priced_routes: Vec<(&CandidateRoute, DecimalAmount)> =
            Vec::with_capacity(routes.len());
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
            priced_routes.push((route, yes_price));
        }

        // Mode branch (ADR-ECON-003 Decision 4): `Shadow`/`AssistedFuture` and the
        // `Softmax`+`ArgmaxBypass` (τ=0) case all run the *identical* argmax code path, so
        // τ=0 is byte-for-byte equivalent to the pre-existing argmax behavior by
        // construction, not by separately re-implemented logic that merely agrees on paper.
        let route = match (self.mode, self.softmax_temperature) {
            (MarketRouterMode::Softmax, SoftmaxTemperature::Finite(tau)) => {
                softmax_select(&priced_routes, tau, price_signal_hash, pput_prior_hash)
            }
            (MarketRouterMode::Softmax, SoftmaxTemperature::Uniform) => {
                uniform_select(&priced_routes, price_signal_hash, pput_prior_hash)
            }
            _ => argmax_select(&priced_routes),
        };
        Ok(BudgetSuggestion {
            schema_id: "budget_allocated.v1".to_string(),
            mode: self.mode,
            route_id: route.route_id.clone(),
            market_id: route.market_id.clone(),
            price_signal_hash: price_signal_hash.to_string(),
            pput_prior_hash: pput_prior_hash.to_string(),
            diversity_policy_hash: diversity_policy_hash(),
            max_tokens: route.requested_tokens,
            emits_authorization: false,
            can_move_accepted_head: false,
            head_effect: "PRESERVE".to_string(),
        })
    }
}

/// Exact pre-Softmax argmax selection (unchanged logic, factored out so the `Softmax`
/// `ArgmaxBypass` (τ=0) branch calls the *same* code, guaranteeing byte-for-byte parity
/// rather than a separately-maintained lookalike).
fn argmax_select<'a>(priced_routes: &[(&'a CandidateRoute, DecimalAmount)]) -> &'a CandidateRoute {
    let mut best: Option<(&CandidateRoute, DecimalAmount)> = None;
    for &(route, yes_price) in priced_routes {
        if best
            .as_ref()
            .is_none_or(|(_, best_price)| yes_price > *best_price)
        {
            best = Some((route, yes_price));
        }
    }
    best.map(|(route, _)| route)
        .expect("priced_routes is non-empty: suggest() rejects empty routes before calling this")
}

/// ADR-ECON-003 Decision 4 domain separator for the deterministic softmax-selection seed.
/// B-zone (Art III.4): must never be echoed into an error/log/schema/doc surface.
const ROUTING_SELECT_SEED_DOMAIN: &str = "routing-select.v1";

/// `u64 = LE(SHA256(domain ‖ price_signal_hash ‖ pput_prior_hash ‖ join(sorted(route_ids),
/// "\x00"))[0..8])` (ADR-ECON-003 Decision 4). All inputs are already-committed
/// caller-supplied literals, so identical inputs reproduce identical bytes (Art 0.2).
fn derive_selection_seed_u64(
    price_signal_hash: &str,
    pput_prior_hash: &str,
    sorted_route_ids: &[&str],
) -> u64 {
    let mut hasher = Sha256::new();
    hasher.update(ROUTING_SELECT_SEED_DOMAIN.as_bytes());
    hasher.update(price_signal_hash.as_bytes());
    hasher.update(pput_prior_hash.as_bytes());
    hasher.update(sorted_route_ids.join("\0").as_bytes());
    let digest = hasher.finalize();
    u64::from_le_bytes(
        digest[0..8]
            .try_into()
            .expect("sha256 digest is always >= 8 bytes"),
    )
}

/// Q32.32 fixed-point unit (ADR-ECON-003 Decision 4: "全程 Q32.32 定点(i128 中间量,向零截断)").
const Q32_ONE: i128 = 1i128 << 32;

/// floor(1.4426950408889634 * 2^32); `exp(x)` is computed as `exp2(x * log2(e))`
/// (ADR-ECON-003 Decision 4). log2(e) is a public math constant, not a B-zone coefficient.
const LOG2E_Q32: i128 = 6_196_328_018;

/// Pinned `exp2f` polynomial coefficients (ADR-ECON-003 Decision 4), fixed-pointed via the
/// pinned truncation rule `floor(c_i * 2^32)`. `exp2f(f) = 1 + f*(c1 + f*(c2 + f*c3))`.
const EXP2F_C1_Q32: i128 = 2_977_044_471;
const EXP2F_C2_Q32: i128 = 1_031_477_962;
const EXP2F_C3_Q32: i128 = 239_780_565;

fn decimal_to_q32(amount: DecimalAmount) -> i128 {
    amount
        .units
        .checked_mul(Q32_ONE)
        .map(|scaled| scaled / SCALE)
        .unwrap_or(i128::MAX)
}

/// Q32.32 multiply, truncating toward zero (ADR-ECON-003 Decision 4), saturating instead of
/// panicking on the (practically unreachable at realistic magnitudes) overflow case.
fn q32_mul(a: i128, b: i128) -> i128 {
    match a.checked_mul(b) {
        Some(product) => product / Q32_ONE,
        None if (a >= 0) == (b >= 0) => i128::MAX,
        None => i128::MIN,
    }
}

/// Q32.32 divide, truncating toward zero (ADR-ECON-003 Decision 4); `b` is always a
/// strictly-positive τ mantissa here (`TauQ32` rejects zero at construction).
fn q32_div(a: i128, b: i128) -> i128 {
    if b == 0 {
        return i128::MAX;
    }
    match a.checked_mul(Q32_ONE) {
        Some(scaled) => scaled / b,
        None if (a >= 0) == (b >= 0) => i128::MAX,
        None => i128::MIN,
    }
}

/// `exp2f(f) = 1 + f*(c1 + f*(c2 + f*c3))` for `f` in Q32.32 `[0, Q32_ONE)` (ADR-ECON-003
/// Decision 4 pinned polynomial).
fn exp2f_q32(f: i128) -> i128 {
    let t2 = EXP2F_C2_Q32 + q32_mul(f, EXP2F_C3_Q32);
    let t1 = EXP2F_C1_Q32 + q32_mul(f, t2);
    Q32_ONE + q32_mul(f, t1)
}

/// `exp2(y) = 2^floor(y) * exp2f(frac(y))` for `y` in Q32.32 (ADR-ECON-003 Decision 4).
/// Total function: saturates to 0 / `i128::MAX` at the (unreachable in the softmax
/// max-subtracted usage below, since `y <= 0` there) extreme ends rather than panicking.
fn exp2_q32(y: i128) -> i128 {
    let floor_part = y.div_euclid(Q32_ONE);
    let frac = y.rem_euclid(Q32_ONE);
    let base = exp2f_q32(frac);
    if floor_part >= 0 {
        if floor_part >= 96 {
            i128::MAX
        } else {
            base << (floor_part as u32)
        }
    } else {
        let negated = -floor_part;
        if negated >= 127 {
            0
        } else {
            base >> (negated as u32)
        }
    }
}

/// Inverse-CDF sample over `weighted` (already in the sorted-`route_id` accumulation order
/// required by ADR-ECON-003 Decision 4) against the deterministic seed `u64_seed`. Total
/// function: the last element's cumulative weight always equals the total, and
/// `total * 2^64 > u64_seed * total` always holds for `u64_seed < 2^64`, so the loop always
/// returns from inside; the trailing `expect` is unreachable given non-empty input.
fn weighted_inverse_cdf_select<'a>(
    weighted: &[(&'a CandidateRoute, i128)],
    u64_seed: u64,
) -> &'a CandidateRoute {
    let total: i128 = weighted.iter().map(|(_, weight)| *weight).sum();
    let mut cumulative: i128 = 0;
    for &(route, weight) in weighted {
        cumulative += weight;
        let lhs = cumulative.checked_mul(1i128 << 64);
        let rhs = (u64_seed as i128).checked_mul(total);
        match (lhs, rhs) {
            (Some(lhs), Some(rhs)) if lhs > rhs => return route,
            (None, _) | (_, None) => return route,
            _ => {}
        }
    }
    weighted
        .last()
        .map(|(route, _)| *route)
        .expect("weighted is non-empty: suggest() rejects empty routes before calling this")
}

/// `MarketRouterMode::Softmax` with `SoftmaxTemperature::Finite(tau)`: `Q_eff = yes_price`
/// (WP1 scope -- the (Q,N,P) tape fold is WP3; selection here reuses the same price basis
/// the pre-existing argmax path already used), `selection = softmax(Q_eff/τ)` sampled via
/// the deterministic seed (ADR-ECON-003 Decision 4).
fn softmax_select<'a>(
    priced_routes: &[(&'a CandidateRoute, DecimalAmount)],
    temperature: TauQ32,
    price_signal_hash: &str,
    pput_prior_hash: &str,
) -> &'a CandidateRoute {
    let mut sorted: Vec<(&CandidateRoute, DecimalAmount)> = priced_routes.to_vec();
    sorted.sort_by(|a, b| a.0.route_id.cmp(&b.0.route_id));

    let tau_q32 = temperature.raw_q32();
    let x_values: Vec<i128> = sorted
        .iter()
        .map(|(_, price)| q32_div(decimal_to_q32(*price), tau_q32))
        .collect();
    let max_x = x_values.iter().copied().max().unwrap_or(0);

    let weighted: Vec<(&CandidateRoute, i128)> = sorted
        .iter()
        .zip(x_values.iter())
        .map(|((route, _), &x)| {
            let shifted = x - max_x; // <= 0: softmax(x) == softmax(x - max(x)), exact identity
            let exponent = q32_mul(shifted, LOG2E_Q32);
            (*route, exp2_q32(exponent))
        })
        .collect();

    let route_ids: Vec<&str> = sorted
        .iter()
        .map(|(route, _)| route.route_id.as_str())
        .collect();
    let seed = derive_selection_seed_u64(price_signal_hash, pput_prior_hash, &route_ids);
    weighted_inverse_cdf_select(&weighted, seed)
}

/// `MarketRouterMode::Softmax` with `SoftmaxTemperature::Uniform` (τ=∞): uniform
/// distribution over the sorted `route_id` order, sampled via the same deterministic seed
/// derivation (ADR-ECON-003 Decision 4).
fn uniform_select<'a>(
    priced_routes: &[(&'a CandidateRoute, DecimalAmount)],
    price_signal_hash: &str,
    pput_prior_hash: &str,
) -> &'a CandidateRoute {
    let mut sorted: Vec<(&CandidateRoute, DecimalAmount)> = priced_routes.to_vec();
    sorted.sort_by(|a, b| a.0.route_id.cmp(&b.0.route_id));
    let weighted: Vec<(&CandidateRoute, i128)> =
        sorted.iter().map(|(route, _)| (*route, Q32_ONE)).collect();
    let route_ids: Vec<&str> = sorted
        .iter()
        .map(|(route, _)| route.route_id.as_str())
        .collect();
    let seed = derive_selection_seed_u64(price_signal_hash, pput_prior_hash, &route_ids);
    weighted_inverse_cdf_select(&weighted, seed)
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
    /// `TauQ32::new` rejected a zero mantissa (ADR-ECON-003 Decision 4: τ=0 must go through
    /// `SoftmaxTemperature::ArgmaxBypass`, not `Finite`). Carries no numeric value (F4).
    InvalidSoftmaxTemperature,
    /// WP3 (ADR-ECON-003 Decision 1): `scaffold_id`'s JCS canonicalization rejected the
    /// descriptor. Carries only the generic codec diagnostic, never a routing-key value.
    InvalidRoutingKeyDescriptor(String),
    /// WP3 (ADR-ECON-003 Decision 6.3): a `RoutingFoldEvent::PriorUpdated` reused an
    /// `event_hash` already seen (either still outstanding or already clawed back).
    RoutingFoldDuplicateEventHash,
    /// WP3 (ADR-ECON-003 Decision 6.3): a `RoutingFoldEvent::Clawback` referenced an
    /// `event_hash` that was never applied, or was already clawed back once.
    RoutingFoldUnknownClawbackTarget,
    /// WP3 (ADR-ECON-003 Decision 6.4): a fold counter (`N`/`S`) would go negative.
    RoutingFoldNegativeCounter,
    /// WP3: a fold counter (`N`/`S`) would overflow its integer width.
    RoutingFoldCounterOverflow,
    /// WP3 (ADR-ECON-003 Decision 5/6): `AnnealConfig` was degenerate (zero `N_anneal`, or
    /// a non-positive τ bound). Carries no numeric value (F4).
    RoutingFoldInvalidAnnealConfig,
    /// WP4 (ADR-ECON-003 Decision 6): `EconomyEvent::routing_prior_updated`'s JCS
    /// canonicalization of its own identity fields rejected the input. Carries only the
    /// generic codec diagnostic, never a routing-key or verdict value.
    InvalidRoutingEventIdentity(String),
    /// WP4 (ADR-ECON-003 Decision 2/6): `routing_fold::economy_events_to_routing_fold_events`
    /// found a `RoutingPriorUpdated`/`RoutingPriorClawback` hash field that does not parse
    /// as 32 raw bytes (i.e. is not a `sha256:` + 64-hex digest of the expected width).
    RoutingFoldMalformedEventHash,
    /// WP5 (ADR-ECON-003 Decision 3): the same `(lineage_id, settlement_index)` pair
    /// appeared twice in a `diversity_metrics` estimation window with two different
    /// verdicts -- a malformed/contradictory input, never silently resolved by
    /// last-write-wins.
    DiversityMetricConflictingSettlement,
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
            EconomyError::InvalidSoftmaxTemperature => {
                write!(f, "invalid softmax temperature configuration")
            }
            EconomyError::InvalidRoutingKeyDescriptor(detail) => {
                write!(f, "invalid routing-key descriptor: {detail}")
            }
            EconomyError::RoutingFoldDuplicateEventHash => {
                write!(f, "routing fold: duplicate event_hash")
            }
            EconomyError::RoutingFoldUnknownClawbackTarget => {
                write!(f, "routing fold: unknown or already-applied clawback target")
            }
            EconomyError::RoutingFoldNegativeCounter => {
                write!(f, "routing fold: counter would go negative")
            }
            EconomyError::RoutingFoldCounterOverflow => {
                write!(f, "routing fold: counter overflow")
            }
            EconomyError::RoutingFoldInvalidAnnealConfig => {
                write!(f, "routing fold: invalid annealing configuration")
            }
            EconomyError::InvalidRoutingEventIdentity(detail) => {
                write!(f, "invalid routing-event identity: {detail}")
            }
            EconomyError::RoutingFoldMalformedEventHash => {
                write!(f, "routing fold: malformed event hash")
            }
            EconomyError::DiversityMetricConflictingSettlement => {
                write!(
                    f,
                    "diversity metrics: conflicting settlement verdicts for the same lineage/index"
                )
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
