//! WP3 (design doc R1.1 §7; ADR-ECON-003 Decisions 1/3/4/6): the `(Q, N, P)` tape-derived
//! node state, the τ(N) annealing function, and the N_eff floor arbitration hook.
//!
//! Pure, deterministic, tape-fold-only (Art 0.2): every function here is a total function
//! of its explicit arguments, never live-random, never a hidden/global mutable. Concrete
//! B-zone parameter values (τ_hi/τ_lo/N_anneal, the N_eff floor/hysteresis thresholds) are
//! never hardcoded in this module -- every one of them is an explicit caller-supplied
//! argument, so this source file's comments, error text, and doc strings carry no
//! parameter *value* to leak (Art III.4, F4). The concrete numbers only ever appear in
//! test fixtures, never in production-facing code, comments, or error paths.
//!
//! Scope note: this module implements the fold and the arbitration hook only. The actual
//! `RoutingPriorUpdated` / `RoutingPriorClawback` `EconomyEvent` variants (and their
//! independent-verifier wiring per ADR-ECON-003 Decision 2) are WP4's deliverable (design
//! doc §7); [`RoutingFoldEvent`] is this fold's own input contract so WP3 is independently
//! testable ahead of WP4 -- WP4 need only translate committed tape events into it.
//!
//! Known spec gap (reported, not guessed): ADR-ECON-003 Decision 4 pins the `exp2f` cubic
//! polynomial but does not pin a `log2` polynomial, even though Decision 4 says "τ(N) 的幂
//! 用同一 exp2/log2 路径". [`log2_q32`] below is therefore implemented as a deterministic,
//! fixed-iteration-count bisection *inversion* of the already-pinned [`exp2_q32`] -- it
//! reuses only the pinned primitive, introduces no independently-invented polynomial
//! coefficients, and is fully deterministic (Art 0.2). If bit-for-bit reproducibility
//! *across independent implementations* becomes load-bearing (not just within this one),
//! this specific numerical method should be pinned by a follow-up ADR revision.

use std::collections::{BTreeMap, BTreeSet};

use serde::Serialize;
use unicode_normalization::UnicodeNormalization;

use crate::EconomyError;

// ---------------------------------------------------------------------------
// Q32.32 fixed-point primitives (ADR-ECON-003 Decision 4: "全程 Q32.32 定点(i128 中间量,
// 向零截断)"). Deliberately re-declared here (rather than imported) because WP1's
// equivalent private helpers live in a sibling worktree/branch not yet merged into this
// one; the orchestrator dedups at merge time. Kept private to this module.
// ---------------------------------------------------------------------------

/// Q32.32 fixed-point unit (`1.0`).
pub const Q32_ONE: i128 = 1i128 << 32;

/// Q32.32 fixed-point one-half (`0.5`), the uninformative-prior default (ADR-ECON-003
/// Decision 6.1: "否则 P = 0.5").
const Q32_HALF: i128 = Q32_ONE / 2;

/// Pinned `exp2f` polynomial coefficients (ADR-ECON-003 Decision 4), fixed-pointed via the
/// pinned truncation rule `floor(c_i * 2^32)`. `exp2f(f) = 1 + f*(c1 + f*(c2 + f*c3))`.
const EXP2F_C1_Q32: i128 = 2_977_044_471;
const EXP2F_C2_Q32: i128 = 1_031_477_962;
const EXP2F_C3_Q32: i128 = 239_780_565;

/// Q32.32 multiply, truncating toward zero (ADR-ECON-003 Decision 4), saturating instead
/// of panicking on the (practically unreachable at realistic magnitudes) overflow case.
///
/// `pub(crate)` (not private): WP5's `diversity_metrics` module reuses this primitive
/// rather than re-declaring it a second time now that both live in the same crate/branch
/// (the "re-declared rather than imported" rationale on `exp2_q32`/`log2_q32` below was
/// specifically about cross-worktree/branch separation during parallel WP1/WP3 development;
/// that constraint no longer applies to a module added after the merge).
pub(crate) fn q32_mul(a: i128, b: i128) -> i128 {
    match a.checked_mul(b) {
        Some(product) => product / Q32_ONE,
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
/// Total function: saturates to 0 / `i128::MAX` at extreme magnitudes rather than
/// panicking or overflowing.
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

/// `log2(x)` for `x > 0` in Q32.32 -- see the module-level "Known spec gap" note.
/// Deterministic fixed-iteration-count bisection against the pinned [`exp2_q32`]; never
/// reads any external state, never varies its iteration count by input.
///
/// `pub(crate)`: reused by WP5's `diversity_metrics` module for `H_lineage`'s Shannon-entropy
/// `log2` term (same crate, no re-declaration needed post-merge; see [`q32_mul`]'s note).
pub(crate) fn log2_q32(x: i128) -> i128 {
    debug_assert!(x > 0, "log2_q32 domain is x > 0");
    let mut lo: i128 = -(64 * Q32_ONE);
    let mut hi: i128 = 64 * Q32_ONE;
    for _ in 0..100 {
        let mid = lo + (hi - lo) / 2;
        if exp2_q32(mid) <= x {
            lo = mid;
        } else {
            hi = mid;
        }
    }
    lo
}

/// Build a Q32.32 fixed-point value from an exact integer ratio `numerator/denominator`
/// (ADR-ECON-003 Decision 4: fixed-point only, never IEEE-754 floats). Truncates toward
/// zero on any remainder (same rounding rule as the rest of Decision 4).
pub fn q32_from_ratio(numerator: i128, denominator: i128) -> Result<i128, EconomyError> {
    if denominator == 0 {
        return Err(EconomyError::DivisionByZero);
    }
    numerator
        .checked_mul(Q32_ONE)
        .map(|scaled| scaled / denominator)
        .ok_or(EconomyError::ArithmeticOverflow)
}

fn clamp_unit_interval(p_q32: i128) -> i128 {
    p_q32.clamp(0, Q32_ONE)
}

// ---------------------------------------------------------------------------
// Decision 1 -- scaffold_id / domain_bucket key functions.
// ---------------------------------------------------------------------------

/// `scaffold_descriptor.v1` (ADR-ECON-003 Decision 1): the normalized descriptor whose
/// JCS-SHA256 is `scaffold_id`.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ScaffoldDescriptor {
    pub decomposition_kind: String,
    pub toolchain: Vec<String>,
    pub team_spec: String,
    pub verify_loop: String,
}

/// `scaffold_id = "scaffold:sha256:" + hex(SHA256(JCS(descriptor)))` (ADR-ECON-003
/// Decision 1). JCS = the workspace's own `turing_contracts::jcs` codec (RFC 8785
/// restricted profile, integers only, no floats), per the ADR's "与既有 jcs.rs 同一实现".
pub fn scaffold_id(descriptor: &ScaffoldDescriptor) -> Result<String, EconomyError> {
    let value = serde_json::json!({
        "schema": "scaffold_descriptor.v1",
        "decomposition_kind": descriptor.decomposition_kind,
        "toolchain": descriptor.toolchain,
        "team_spec": descriptor.team_spec,
        "verify_loop": descriptor.verify_loop,
    });
    let canonical = turing_contracts::jcs::canonicalize(&value)
        .map_err(|e| EconomyError::InvalidRoutingKeyDescriptor(e.to_string()))?;
    Ok(format!(
        "scaffold:sha256:{}",
        turing_contracts::jcs::sha256_hex(&canonical)
    ))
}

/// `domain_bucket` (ADR-ECON-003 Decision 1): NFC-normalize + ASCII-lowercase + trim the
/// harness `task_family` label; missing (`None`) or blank-after-trim maps to `"default"`.
#[must_use]
pub fn domain_bucket(task_family: Option<&str>) -> String {
    let Some(raw) = task_family else {
        return "default".to_string();
    };
    let nfc: String = raw.nfc().collect();
    let lowered = nfc.to_ascii_lowercase();
    let trimmed = lowered.trim();
    if trimmed.is_empty() {
        "default".to_string()
    } else {
        trimmed.to_string()
    }
}

/// Fold key (ADR-ECON-003 Decision 1): `(domain_bucket, scaffold_id)`. `Ord` gives every
/// consumer (this fold, N_eff/H_lineage windows) one canonical deterministic iteration
/// order over the node map, independent of insertion order (Art 0.2).
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize)]
pub struct RoutingKey {
    pub domain_bucket: String,
    pub scaffold_id: String,
}

// ---------------------------------------------------------------------------
// Decision 6 -- (Q, N, P) node state, tape pure fold.
// ---------------------------------------------------------------------------

/// Per-`RoutingKey` node state (ADR-ECON-003 Decision 6): `P` (frozen prior), `N` (visit /
/// settlement count), `S` (verified-success sum). `Q_eff` is derived on read, never
/// stored, so the same information is never double-counted.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct NodeState {
    p_q32: i128,
    n: u64,
    s: u64,
}

impl NodeState {
    #[must_use]
    pub fn p_q32(&self) -> i128 {
        self.p_q32
    }

    #[must_use]
    pub fn n(&self) -> u64 {
        self.n
    }

    #[must_use]
    pub fn s(&self) -> u64 {
        self.s
    }

    /// `Q_eff = (P*N0 + S) / (N0+N)`, `N0 = 1` (ADR-ECON-003 Decision 6.2), Q32.32,
    /// truncated toward zero. `N=0` reduces exactly to `Q_eff = P` (pure prior); as `N`
    /// grows, `Q_eff` approaches the empirical success rate.
    #[must_use]
    pub fn q_eff_q32(&self) -> i128 {
        let numerator = self.p_q32 + (self.s as i128) * Q32_ONE;
        let denominator = 1i128 + self.n as i128;
        numerator / denominator
    }
}

/// A single applied fold input (ADR-ECON-003 Decision 6). WP4 translates committed
/// `EconomyEvent::RoutingPriorUpdated` / `RoutingPriorClawback` tape events into this
/// contract; this module never reads `EconomyEvent` directly.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RoutingFoldEvent {
    /// Independent-verifier verdict (ADR-ECON-003 Decision 2/6.2). `event_hash` uniquely
    /// identifies this update for clawback dedup (Decision 6.3).
    PriorUpdated {
        key: RoutingKey,
        verdict: bool,
        event_hash: [u8; 32],
    },
    /// Exact inverse of one earlier `PriorUpdated`, referenced by its `event_hash`
    /// (ADR-ECON-003 Decision 6.3). At most one clawback per original event.
    Clawback { updated_event_hash: [u8; 32] },
}

/// Pure fold: `(initial_prices, events) -> per-key NodeState` (ADR-ECON-003 Decision 6).
/// Deterministic given its inputs (Art 0.2): the same event sequence replayed against the
/// same `initial_prices` always yields a byte-identical result. `initial_prices` supplies
/// the AMM-derived `P` for a key's *first* appearance only (Decision 6.1: "P 在节点首次
/// 创建时定格"); a key with no entry there gets the uninformative `P = 0.5` prior.
///
/// Total, never silently absorbing an invalid state (ADR-ECON-003 Decision 6.4/6.3): a
/// duplicate `event_hash`, a clawback of an unknown/already-clawed-back hash, or a counter
/// underflow/overflow is a hard fold error, never swallowed.
pub fn fold_routing_state(
    initial_prices: &BTreeMap<RoutingKey, i128>,
    events: &[RoutingFoldEvent],
) -> Result<BTreeMap<RoutingKey, NodeState>, EconomyError> {
    let mut nodes: BTreeMap<RoutingKey, NodeState> = BTreeMap::new();
    // event_hash -> (key, verdict) for every update seen and not yet clawed back.
    let mut outstanding: BTreeMap<[u8; 32], (RoutingKey, bool)> = BTreeMap::new();
    let mut clawed_back: BTreeSet<[u8; 32]> = BTreeSet::new();

    for event in events {
        match event {
            RoutingFoldEvent::PriorUpdated {
                key,
                verdict,
                event_hash,
            } => {
                if outstanding.contains_key(event_hash) || clawed_back.contains(event_hash) {
                    return Err(EconomyError::RoutingFoldDuplicateEventHash);
                }
                let node = nodes.entry(key.clone()).or_insert_with(|| {
                    let p_q32 = initial_prices
                        .get(key)
                        .copied()
                        .map(clamp_unit_interval)
                        .unwrap_or(Q32_HALF);
                    NodeState { p_q32, n: 0, s: 0 }
                });
                node.n = node
                    .n
                    .checked_add(1)
                    .ok_or(EconomyError::RoutingFoldCounterOverflow)?;
                if *verdict {
                    node.s = node
                        .s
                        .checked_add(1)
                        .ok_or(EconomyError::RoutingFoldCounterOverflow)?;
                }
                outstanding.insert(*event_hash, (key.clone(), *verdict));
            }
            RoutingFoldEvent::Clawback {
                updated_event_hash,
            } => {
                let (key, verdict) = outstanding
                    .remove(updated_event_hash)
                    .ok_or(EconomyError::RoutingFoldUnknownClawbackTarget)?;
                clawed_back.insert(*updated_event_hash);
                let node = nodes
                    .get_mut(&key)
                    .ok_or(EconomyError::RoutingFoldUnknownClawbackTarget)?;
                node.n = node
                    .n
                    .checked_sub(1)
                    .ok_or(EconomyError::RoutingFoldNegativeCounter)?;
                if verdict {
                    node.s = node
                        .s
                        .checked_sub(1)
                        .ok_or(EconomyError::RoutingFoldNegativeCounter)?;
                }
            }
        }
    }
    Ok(nodes)
}

// ---------------------------------------------------------------------------
// Decision 3/4 -- τ(N) annealing + N_eff floor arbitration hook.
// ---------------------------------------------------------------------------

/// Caller-supplied annealing configuration (ADR-ECON-003 Decision 5 B-zone parameters:
/// τ_hi, τ_lo, N_anneal). Deliberately *not* hardcoded in this module -- every concrete
/// value is threaded in explicitly by the caller (who reads it from the B-zone config
/// mechanism, out of this module's scope), so this source file never carries a parameter
/// value that could leak through a doc string or error path (Art III.4, F4).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct AnnealConfig {
    pub tau_hi_q32: i128,
    pub tau_lo_q32: i128,
    pub n_anneal: u64,
}

/// `τ(N) = τ_hi·(τ_lo/τ_hi)^min(1, N/N_anneal)` (design doc §1.2; ADR-ECON-003 Decision 6
/// references this as the annealing formula gated by Decision 3's floor arbitration).
/// `N=0` returns exactly `τ_hi` (no approximation error: the zero exponent short-circuits
/// before `exp2`/`log2` are invoked at all).
pub fn tau_anneal_q32(n: u64, cfg: &AnnealConfig) -> Result<i128, EconomyError> {
    if cfg.n_anneal == 0 || cfg.tau_hi_q32 <= 0 || cfg.tau_lo_q32 <= 0 {
        return Err(EconomyError::RoutingFoldInvalidAnnealConfig);
    }
    if n == 0 {
        return Ok(cfg.tau_hi_q32);
    }
    let ratio_q32 = {
        let scaled = (n as i128)
            .checked_mul(Q32_ONE)
            .ok_or(EconomyError::ArithmeticOverflow)?;
        (scaled / cfg.n_anneal as i128).min(Q32_ONE)
    };
    let log2_ratio_q32 = log2_q32(cfg.tau_lo_q32) - log2_q32(cfg.tau_hi_q32);
    let exponent_times_log2 = q32_mul(ratio_q32, log2_ratio_q32);
    Ok(q32_mul(cfg.tau_hi_q32, exp2_q32(exponent_times_log2)))
}

/// Annealing mode (ADR-ECON-003 Decision 3 hysteresis). Threaded explicitly through the
/// fold (never a hidden/global variable) so the whole pipeline stays a pure function of
/// already-committed inputs (Art 0.2): the caller carries `AnnealMode` forward exactly
/// like `N`/`S` above, deterministically reconstructable from tape.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AnnealMode {
    Annealing,
    Paused,
}

/// Caller-supplied N_eff floor/hysteresis thresholds (ADR-ECON-003 Decision 3). Q32.32.
/// Not hardcoded here (see the module-level note) -- the caller supplies these from
/// wherever the A-zone floor constants are published.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct FloorConfig {
    /// Enter/stay `Paused` once `N_eff <= pause_at_or_below_q32`.
    pub pause_at_or_below_q32: i128,
    /// Resume `Annealing` only once `N_eff >= resume_at_or_above_q32` (hysteresis band;
    /// strictly greater than `pause_at_or_below_q32` in any valid configuration).
    pub resume_at_or_above_q32: i128,
}

/// "N_eff 地板赢" (ADR-ECON-003 Decision 3 / design §1.5): pure, total, deterministic step
/// function of `(prev_mode, n_eff_q32, floor)` alone -- no other input can override it.
pub fn arbitrate_anneal_mode(
    prev_mode: AnnealMode,
    n_eff_q32: i128,
    floor: &FloorConfig,
) -> AnnealMode {
    match prev_mode {
        AnnealMode::Paused => {
            if n_eff_q32 >= floor.resume_at_or_above_q32 {
                AnnealMode::Annealing
            } else {
                AnnealMode::Paused
            }
        }
        AnnealMode::Annealing => {
            if n_eff_q32 <= floor.pause_at_or_below_q32 {
                AnnealMode::Paused
            } else {
                AnnealMode::Annealing
            }
        }
    }
}

/// `τ_eff` (ADR-ECON-003 Decision 3): `τ_hi` while `Paused`, else the `τ(N)` annealing
/// formula. "地板赢" is structural here: [`arbitrate_anneal_mode`] must be called first,
/// and while it reports `Paused` this function never even evaluates [`tau_anneal_q32`], so
/// the selection law cannot trade away the diversity floor for exploitation no matter how
/// large `N` has grown.
pub fn tau_eff_q32(
    n: u64,
    mode: AnnealMode,
    anneal_cfg: &AnnealConfig,
) -> Result<i128, EconomyError> {
    match mode {
        AnnealMode::Paused => Ok(anneal_cfg.tau_hi_q32),
        AnnealMode::Annealing => tau_anneal_q32(n, anneal_cfg),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn key(bucket: &str, scaffold: &str) -> RoutingKey {
        RoutingKey {
            domain_bucket: bucket.to_string(),
            scaffold_id: scaffold.to_string(),
        }
    }

    fn event_hash(tag: u8) -> [u8; 32] {
        let mut h = [0u8; 32];
        h[0] = tag;
        h
    }

    // -- Decision 1: key functions ------------------------------------------------

    #[test]
    fn scaffold_id_is_deterministic_and_distinct() {
        let a = ScaffoldDescriptor {
            decomposition_kind: "linear".to_string(),
            toolchain: vec!["rustc".to_string(), "cargo".to_string()],
            team_spec: "solo".to_string(),
            verify_loop: "cargo-test".to_string(),
        };
        let b = ScaffoldDescriptor {
            decomposition_kind: "tree".to_string(),
            ..a.clone()
        };
        let id_a1 = scaffold_id(&a).expect("scaffold_id(a) 1");
        let id_a2 = scaffold_id(&a).expect("scaffold_id(a) 2");
        let id_b = scaffold_id(&b).expect("scaffold_id(b)");
        assert_eq!(id_a1, id_a2, "same descriptor must fold to the same id");
        assert_ne!(id_a1, id_b, "different descriptor must fold to a different id");
        assert!(id_a1.starts_with("scaffold:sha256:"));
    }

    #[test]
    fn domain_bucket_normalizes_case_and_whitespace() {
        assert_eq!(domain_bucket(Some("  Coding_Task  ")), "coding_task");
        assert_eq!(domain_bucket(Some("")), "default");
        assert_eq!(domain_bucket(Some("   ")), "default");
        assert_eq!(domain_bucket(None), "default");
        // NFC: composed vs. decomposed forms of the same visible string must match.
        let composed = "\u{00e9}"; // "é" (single code point)
        let decomposed = "e\u{0301}"; // "e" + combining acute accent
        assert_eq!(domain_bucket(Some(composed)), domain_bucket(Some(decomposed)));
    }

    // -- Decision 6: fold determinism ----------------------------------------------

    #[test]
    fn fold_is_deterministic_across_repeated_runs() {
        let k1 = key("code_review", "scaffold:sha256:aaa");
        let k2 = key("code_review", "scaffold:sha256:bbb");
        let mut prices = BTreeMap::new();
        prices.insert(k1.clone(), q32_from_ratio(3, 4).unwrap());

        let events = vec![
            RoutingFoldEvent::PriorUpdated {
                key: k1.clone(),
                verdict: true,
                event_hash: event_hash(1),
            },
            RoutingFoldEvent::PriorUpdated {
                key: k2.clone(),
                verdict: false,
                event_hash: event_hash(2),
            },
            RoutingFoldEvent::PriorUpdated {
                key: k1.clone(),
                verdict: false,
                event_hash: event_hash(3),
            },
            RoutingFoldEvent::Clawback {
                updated_event_hash: event_hash(2),
            },
        ];

        let run1 = fold_routing_state(&prices, &events).expect("fold run 1");
        let run2 = fold_routing_state(&prices, &events).expect("fold run 2");
        assert_eq!(run1.len(), run2.len());
        for (k, node1) in &run1 {
            let node2 = run2.get(k).expect("same key present in both runs");
            assert_eq!(node1.p_q32(), node2.p_q32());
            assert_eq!(node1.n(), node2.n());
            assert_eq!(node1.s(), node2.s());
        }

        // Post-clawback semantics: k2's single PriorUpdated was exactly reversed.
        let n2 = run1.get(&k2).expect("k2 present");
        assert_eq!(n2.n(), 0);
        assert_eq!(n2.s(), 0);

        // k1: two updates (verdict true, then false), P frozen at first observation.
        let n1 = run1.get(&k1).expect("k1 present");
        assert_eq!(n1.n(), 2);
        assert_eq!(n1.s(), 1);
        assert_eq!(n1.p_q32(), q32_from_ratio(3, 4).unwrap());
    }

    #[test]
    fn fold_defaults_uninformative_prior_when_no_price_supplied() {
        let k = key("code_review", "scaffold:sha256:ccc");
        let prices = BTreeMap::new();
        let events = vec![RoutingFoldEvent::PriorUpdated {
            key: k.clone(),
            verdict: true,
            event_hash: event_hash(9),
        }];
        let nodes = fold_routing_state(&prices, &events).expect("fold");
        assert_eq!(nodes.get(&k).unwrap().p_q32(), Q32_ONE / 2);
    }

    #[test]
    fn fold_rejects_duplicate_clawback_and_unknown_target() {
        let k = key("code_review", "scaffold:sha256:ddd");
        let prices = BTreeMap::new();
        let good = vec![
            RoutingFoldEvent::PriorUpdated {
                key: k.clone(),
                verdict: true,
                event_hash: event_hash(5),
            },
            RoutingFoldEvent::Clawback {
                updated_event_hash: event_hash(5),
            },
        ];
        assert!(fold_routing_state(&prices, &good).is_ok());

        let double_clawback = vec![
            RoutingFoldEvent::PriorUpdated {
                key: k.clone(),
                verdict: true,
                event_hash: event_hash(6),
            },
            RoutingFoldEvent::Clawback {
                updated_event_hash: event_hash(6),
            },
            RoutingFoldEvent::Clawback {
                updated_event_hash: event_hash(6),
            },
        ];
        assert_eq!(
            fold_routing_state(&prices, &double_clawback),
            Err(EconomyError::RoutingFoldUnknownClawbackTarget)
        );

        let unknown_target = vec![RoutingFoldEvent::Clawback {
            updated_event_hash: event_hash(7),
        }];
        assert_eq!(
            fold_routing_state(&prices, &unknown_target),
            Err(EconomyError::RoutingFoldUnknownClawbackTarget)
        );

        let duplicate_update_hash = vec![
            RoutingFoldEvent::PriorUpdated {
                key: k.clone(),
                verdict: true,
                event_hash: event_hash(8),
            },
            RoutingFoldEvent::PriorUpdated {
                key: k.clone(),
                verdict: false,
                event_hash: event_hash(8),
            },
        ];
        assert_eq!(
            fold_routing_state(&prices, &duplicate_update_hash),
            Err(EconomyError::RoutingFoldDuplicateEventHash)
        );
    }

    // -- Decision 4/6: τ(N) annealing ----------------------------------------------

    fn test_anneal_cfg() -> AnnealConfig {
        // Test-only constants, numerically equal to the ADR-ECON-003 Decision 5
        // EXPERIMENTAL STARTING values (plan-directory documented, not secrets).
        // Production code never hardcodes them: AnnealConfig is caller-supplied.
        AnnealConfig {
            tau_hi_q32: q32_from_ratio(2, 1).unwrap(),
            tau_lo_q32: q32_from_ratio(1, 4).unwrap(),
            n_anneal: 32,
        }
    }

    #[test]
    fn tau_anneal_at_zero_visits_is_exactly_tau_hi() {
        let cfg = test_anneal_cfg();
        assert_eq!(tau_anneal_q32(0, &cfg).unwrap(), cfg.tau_hi_q32);
    }

    #[test]
    fn tau_anneal_at_saturation_is_close_to_tau_lo() {
        let cfg = test_anneal_cfg();
        let tau_at_n_anneal = tau_anneal_q32(cfg.n_anneal, &cfg).unwrap();
        let diff = (tau_at_n_anneal - cfg.tau_lo_q32).abs();
        // ADR-ECON-003 Decision 4 documents ~1e-3 relative approximation error from the
        // pinned exp2f cubic; allow a generous tolerance band well above that.
        let tolerance = cfg.tau_lo_q32 / 100; // 1% of τ_lo
        assert!(
            diff <= tolerance,
            "tau(N_anneal) should approach tau_lo within tolerance, diff_q32={diff} tolerance_q32={tolerance}"
        );
    }

    #[test]
    fn tau_anneal_is_monotonically_non_increasing_in_n() {
        let cfg = test_anneal_cfg();
        let mut prev = tau_anneal_q32(0, &cfg).unwrap();
        for n in [1u64, 2, 4, 8, 16, 24, 32, 64, 128] {
            let cur = tau_anneal_q32(n, &cfg).unwrap();
            assert!(
                cur <= prev,
                "tau_anneal must not increase as N grows: n={n} prev={prev} cur={cur}"
            );
            prev = cur;
        }
    }

    #[test]
    fn tau_anneal_rejects_degenerate_config() {
        let mut cfg = test_anneal_cfg();
        cfg.n_anneal = 0;
        assert_eq!(
            tau_anneal_q32(5, &cfg),
            Err(EconomyError::RoutingFoldInvalidAnnealConfig)
        );
    }

    // -- Decision 3: N_eff floor arbitration hook, "floor wins" -------------------

    fn test_floor_cfg() -> FloorConfig {
        // Deliberately the ADR-ECON-003 Decision 3 A-zone floor values -- the A-zone
        // floor is fixed and PUBLIC by design (Art III.3), so testing with the real
        // values is correct, not a leak.
        FloorConfig {
            pause_at_or_below_q32: q32_from_ratio(2, 1).unwrap(),
            resume_at_or_above_q32: q32_from_ratio(9, 4).unwrap(), // 2.0 + 0.25 hysteresis band
        }
    }

    #[test]
    fn floor_wins_pauses_annealing_when_n_eff_hits_floor_and_holds_through_hysteresis() {
        let cfg = test_anneal_cfg();
        let floor = test_floor_cfg();

        // A constructed N_eff -> floor event sequence (design doc §7 WP3 acceptance
        // criterion): starts diverse (Annealing), collapses to the floor (must Pause),
        // ticks up a little but stays inside the hysteresis band (must stay Paused even
        // though N_eff is no longer falling), then clears the resume threshold (may
        // resume annealing).
        let n_eff_sequence_q32: Vec<i128> = vec![
            q32_from_ratio(4, 1).unwrap(), // 4.0: healthy diversity
            q32_from_ratio(3, 1).unwrap(), // 3.0: still healthy
            q32_from_ratio(2, 1).unwrap(), // 2.0: hits the floor exactly
            q32_from_ratio(21, 10).unwrap(), // 2.1: inside hysteresis band
            q32_from_ratio(9, 4).unwrap(), // 2.25: clears resume threshold
        ];

        let mut mode = AnnealMode::Annealing;
        let mut modes = Vec::with_capacity(n_eff_sequence_q32.len());
        for n_eff in &n_eff_sequence_q32 {
            mode = arbitrate_anneal_mode(mode, *n_eff, &floor);
            modes.push(mode);
        }

        assert_eq!(modes[0], AnnealMode::Annealing);
        assert_eq!(modes[1], AnnealMode::Annealing);
        assert_eq!(modes[2], AnnealMode::Paused, "N_eff at floor must pause");
        assert_eq!(
            modes[3],
            AnnealMode::Paused,
            "hysteresis band must hold Paused even as N_eff ticks up"
        );
        assert_eq!(
            modes[4],
            AnnealMode::Annealing,
            "crossing the resume threshold must resume annealing"
        );

        // The core "floor wins" property: while Paused, tau_eff is exactly tau_hi
        // regardless of how large N has grown (i.e., annealing can never trade away the
        // diversity floor for exploitation, no matter how much exploitation history N
        // encodes).
        let large_n = 10_000u64;
        let tau_while_paused = tau_eff_q32(large_n, AnnealMode::Paused, &cfg).unwrap();
        assert_eq!(tau_while_paused, cfg.tau_hi_q32);

        let tau_while_annealing = tau_eff_q32(large_n, AnnealMode::Annealing, &cfg).unwrap();
        assert!(
            tau_while_annealing < cfg.tau_hi_q32,
            "once resumed, a large N should anneal tau below tau_hi"
        );
    }

    #[test]
    fn floor_wins_is_a_pure_function_of_n_eff_alone() {
        let floor = test_floor_cfg();
        // Same (prev_mode, n_eff, floor) must always produce the same next mode,
        // independent of call order / how many times it's re-evaluated (Art 0.2).
        let below = q32_from_ratio(1, 1).unwrap();
        let m1 = arbitrate_anneal_mode(AnnealMode::Annealing, below, &floor);
        let m2 = arbitrate_anneal_mode(AnnealMode::Annealing, below, &floor);
        assert_eq!(m1, m2);
        assert_eq!(m1, AnnealMode::Paused);
    }
}
