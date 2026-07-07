//! WP5 (design doc R1.1 §7; ADR-ECON-003 Decision 3): the `N_eff` (effective independent
//! signal count) / `H_lineage` (Shannon entropy of routed-lineage selection) measurement
//! module -- the always-on monoculture guardrail *input*.
//!
//! **Scope (do not re-derive arbitration here):** this module computes N_eff/H_lineage
//! *estimates only*. `routing_fold::arbitrate_anneal_mode` and `routing_fold::FloorConfig`
//! (WP3, already merged) remain the sole floor-arbitration authority -- ADR-ECON-003
//! Decision 3's "N_eff 地板赢...仲裁者" hook. This module's [`NEffHLineage::Computed`]
//! `n_eff_q32` is meant to be *fed into* that existing hook by the caller, never
//! reimplemented here.
//!
//! Deterministic, tape-fold-only (Art 0.2): every function is a total function of its
//! explicit `&[LineageSettlement]` argument alone -- no I/O, no live-random, no wall-clock,
//! no hidden/global state. Every intermediate accumulator is a `BTreeMap`/`BTreeSet`, so the
//! result never depends on the caller's input ordering (only on which `(lineage_id,
//! settlement_index, verdict)` triples are present).
//!
//! **Numeric method (documented, not a hidden invention):** ADR-ECON-003 Decision 3 pins
//! `N_eff = (Sigma lambda_i)^2 / Sigma lambda_i^2` over the *eigenvalues* of the window's
//! Pearson correlation matrix `C`, but never requires actually diagonalizing `C`. For any
//! real symmetric matrix `C = Q * Lambda * Q^T` (`Q` orthogonal):
//!   - `trace(C) = trace(Lambda) = Sigma lambda_i` (similarity-invariant trace), and
//!   - `Sigma_{i,j} C_ij^2 = trace(C^T * C) = trace(C^2) = trace(Q * Lambda^2 * Q^T) =
//!     trace(Lambda^2) = Sigma lambda_i^2` (Frobenius norm is basis-independent).
//!
//! So `N_eff = trace(C)^2 / Sigma_{i,j} C_ij^2`, computed directly from `C`'s *entries*, is
//! *exactly* the pinned eigenvalue formula -- not an approximation of it -- and needs only
//! the already-pinned Q32.32 primitives (`q32_mul`, `q32_from_ratio`), never an
//! independently-invented eigensolver. (Contrast `routing_fold::log2_q32`'s "known spec gap"
//! doc note: no analogous gap exists here, because this route introduces no new numerical
//! method beyond exact rational arithmetic over integer counts.)
//!
//! Because every settlement result is binary (PASS=1/FAIL=0), the correlation-matrix
//! entries reduce to exact integer ratios with no square root anywhere: for two lineages
//! `i`, `j` restricted to `m` common settlement indices, with `c_i`/`c_j` = counts of
//! `true` verdicts and `co_count` = count of indices where *both* are `true`:
//!   - `Cov(i,j) = co_count/m - (c_i/m)*(c_j/m) = (co_count*m - c_i*c_j) / m^2`
//!   - `Var(i) = (c_i/m)*(1 - c_i/m) = c_i*(m - c_i) / m^2` (Bernoulli variance identity)
//!   - `C_ij = Cov(i,j) / sqrt(Var(i)*Var(j))`, so
//!     `C_ij^2 = Cov(i,j)^2 / (Var(i)*Var(j)) = (co_count*m - c_i*c_j)^2 /
//!     (c_i*(m-c_i)*c_j*(m-c_j))` -- the `m^4` cancels exactly, no fractional/irrational
//!     intermediate ever appears.
//!
//! **Degenerate-input conventions (ADR-ECON-003 Decision 3, verbatim where pinned):**
//! - Fewer than 8 common settlement indices in the window -> the whole window is reported
//!   [`NEffHLineage::NotEnoughData`] (not a floor violation, not computed).
//! - A single active lineage -> `N_eff := 1` by literal ADR override, bypassing the general
//!   correlation machinery entirely.
//! - A zero-variance result vector's Pearson correlation (including with itself) counts as
//!   0, per the ADR's amendment #7 -- so a constant lineage's diagonal entry is 0, not the
//!   usual self-correlation of 1.
//! - **Documented extension beyond the ADR's literal text:** if *every* active lineage is
//!   constant on the common indices (`trace(C) = 0`), the formula above degenerates to
//!   `0/0`. This module defines that case as `N_eff := 1` (total agreement is the
//!   monoculture extreme -- design doc §1.5's "N_eff→1 = monoculture" -- not an undefined
//!   value), rather than erroring. This is the one place this module goes beyond what
//!   ADR-ECON-003 pins verbatim; flagged here for owner review.

use std::collections::{BTreeMap, BTreeSet};

use crate::EconomyError;
use crate::routing_fold::{Q32_ONE, log2_q32, q32_from_ratio, q32_mul};

/// ADR-ECON-003 Decision 3: sliding window size per `domain_bucket`, in already-settled
/// events. A defining constant of the estimator itself (like Decision 6's `N0 = 1`), not a
/// B-zone tunable -- hardcoded here rather than threaded in by the caller.
pub const WINDOW_SETTLEMENTS: usize = 64;

/// ADR-ECON-003 Decision 3: "公共结算索引 < 8 时该窗口记 NOT_ENOUGH_DATA". A defining
/// constant of the estimator's data-sufficiency gate (distinct from, and unrelated to, the
/// N_eff/H_lineage A-zone *floor* values, which live in `routing_fold::FloorConfig` and are
/// never referenced by this module at all).
pub const MIN_COMMON_SETTLEMENT_INDICES: usize = 8;

/// One settled outcome for one routing lineage, tagged by the shared settlement ordinal it
/// was evaluated on (ADR-ECON-003 Decision 3: "对齐到共同结算索引" -- e.g. the same
/// experiment-harness task/round evaluated by multiple arms/lineages in parallel, per design
/// doc §3's rank-inversion ladder). This module is deliberately agnostic to which lineage-
/// identity scheme the caller uses (a `routing_fold::RoutingKey`, an experiment-arm id,
/// etc.) -- it never invents an identity convention beyond what ADR-ECON-003 pins.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub struct LineageSettlement {
    pub lineage_id: String,
    pub settlement_index: u64,
    /// PASS = `true`, FAIL = `false` (ADR-ECON-003 Decision 3).
    pub verdict: bool,
}

/// N_eff/H_lineage measurement result for one window (ADR-ECON-003 Decision 3).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NEffHLineage {
    /// Fewer than [`MIN_COMMON_SETTLEMENT_INDICES`] common settlement indices in the window.
    /// Not a constitutional violation, not a floor breach -- just insufficient data.
    NotEnoughData,
    Computed {
        n_eff_q32: i128,
        h_lineage_q32: i128,
    },
}

/// The last [`WINDOW_SETTLEMENTS`] records of an already-tape-ordered history (ADR-ECON-003
/// Decision 3: "不足 W 用现有全部"). Pure slice operation, no reordering.
#[must_use]
pub fn window_tail(history: &[LineageSettlement]) -> &[LineageSettlement] {
    let start = history.len().saturating_sub(WINDOW_SETTLEMENTS);
    &history[start..]
}

/// Computes N_eff / H_lineage over `window_tail(history)` (ADR-ECON-003 Decision 3).
///
/// Total, never silently absorbing invalid input: two records with the same
/// `(lineage_id, settlement_index)` but different verdicts is a hard error
/// ([`EconomyError::DiversityMetricConflictingSettlement`]), never resolved by
/// last-write-wins.
pub fn compute_n_eff_and_h_lineage(
    history: &[LineageSettlement],
) -> Result<NEffHLineage, EconomyError> {
    let window = window_tail(history);

    // Per-lineage (settlement_index -> verdict) maps, rejecting contradictory duplicates.
    let mut per_lineage: BTreeMap<&str, BTreeMap<u64, bool>> = BTreeMap::new();
    for record in window {
        let entry = per_lineage.entry(record.lineage_id.as_str()).or_default();
        if let Some(existing) = entry.get(&record.settlement_index) {
            if *existing != record.verdict {
                return Err(EconomyError::DiversityMetricConflictingSettlement);
            }
        } else {
            entry.insert(record.settlement_index, record.verdict);
        }
    }

    // H_lineage: Shannon entropy (bits) of the *raw selection frequency* across every
    // window record (ADR-ECON-003 Decision 3: "窗口内被选中路由的 lineage 分布") -- always
    // computable from the whole window, independent of the common-index alignment N_eff
    // needs.
    let h_lineage_q32 = if window.is_empty() {
        0
    } else {
        let mut counts: BTreeMap<&str, i128> = BTreeMap::new();
        for record in window {
            *counts.entry(record.lineage_id.as_str()).or_insert(0) += 1;
        }
        shannon_entropy_bits_q32(&counts, window.len() as i128)?
    };

    let active_lineages: Vec<&str> = per_lineage.keys().copied().collect();

    if active_lineages.is_empty() {
        return Ok(NEffHLineage::NotEnoughData);
    }
    if active_lineages.len() == 1 {
        // ADR-ECON-003 Decision 3: "单 lineage 时 N_eff=1" -- literal override, bypasses the
        // common-index / correlation machinery below entirely.
        return Ok(NEffHLineage::Computed {
            n_eff_q32: Q32_ONE,
            h_lineage_q32,
        });
    }

    // Common settlement indices = intersection of every active lineage's index set
    // (ADR-ECON-003 Decision 3: "对齐到共同结算索引"); one shared alignment for the whole
    // window, matching the singular "该窗口记 NOT_ENOUGH_DATA" wording.
    let mut common: BTreeSet<u64> = per_lineage[active_lineages[0]].keys().copied().collect();
    for lineage in &active_lineages[1..] {
        let indices: BTreeSet<u64> = per_lineage[lineage].keys().copied().collect();
        common = common.intersection(&indices).copied().collect();
    }

    if common.len() < MIN_COMMON_SETTLEMENT_INDICES {
        return Ok(NEffHLineage::NotEnoughData);
    }

    let n_eff_q32 = n_eff_from_common_window(&per_lineage, &active_lineages, &common)?;

    Ok(NEffHLineage::Computed {
        n_eff_q32,
        h_lineage_q32,
    })
}

/// The N_eff correlation-matrix computation (see module doc for the trace/Frobenius
/// identity and the exact-integer-ratio derivation). Requires `active_lineages.len() >= 2`
/// and `common.len() >= MIN_COMMON_SETTLEMENT_INDICES` (both already guaranteed by the sole
/// caller, [`compute_n_eff_and_h_lineage`]).
fn n_eff_from_common_window(
    per_lineage: &BTreeMap<&str, BTreeMap<u64, bool>>,
    active_lineages: &[&str],
    common: &BTreeSet<u64>,
) -> Result<i128, EconomyError> {
    let m = common.len() as i128;

    // c_i = count of `true` verdicts among the common indices, per active lineage.
    let mut c: BTreeMap<&str, i128> = BTreeMap::new();
    for &lineage in active_lineages {
        let map = &per_lineage[lineage];
        let count = common.iter().filter(|idx| map[idx]).count() as i128;
        c.insert(lineage, count);
    }

    // trace(C): a lineage's diagonal entry is 1 iff its restriction to the common indices
    // has nonzero variance (0 < c_i < m), else 0 (ADR-ECON-003 Decision 3 amendment #7:
    // zero-variance self-correlation counts as 0, not the usual 1).
    let has_variance = |count: i128| count > 0 && count < m;
    let trace_count: i128 = c.values().filter(|&&count| has_variance(count)).count() as i128;

    // Sigma_{i,j} C_ij^2: diagonal contributions (1^2 per variant lineage) plus off-diagonal
    // contributions (counted for both (i,j) and (j,i) by symmetry).
    let mut sumsq_q32: i128 = trace_count
        .checked_mul(Q32_ONE)
        .ok_or(EconomyError::ArithmeticOverflow)?;

    for (i, &lineage_i) in active_lineages.iter().enumerate() {
        let c_i = c[lineage_i];
        if !has_variance(c_i) {
            continue; // zero-variance row contributes 0 to every pair it's in.
        }
        let map_i = &per_lineage[lineage_i];
        for &lineage_j in &active_lineages[i + 1..] {
            let c_j = c[lineage_j];
            if !has_variance(c_j) {
                continue;
            }
            let map_j = &per_lineage[lineage_j];
            let co_count = common.iter().filter(|idx| map_i[idx] && map_j[idx]).count() as i128;

            // C_ij^2 = (co_count*m - c_i*c_j)^2 / (c_i*(m-c_i)*c_j*(m-c_j)) -- see module
            // doc; no sqrt anywhere.
            let diff = co_count
                .checked_mul(m)
                .and_then(|v| v.checked_sub(c_i.checked_mul(c_j)?))
                .ok_or(EconomyError::ArithmeticOverflow)?;
            let numerator = diff
                .checked_mul(diff)
                .ok_or(EconomyError::ArithmeticOverflow)?;
            let denominator = c_i
                .checked_mul(m - c_i)
                .and_then(|v| v.checked_mul(c_j))
                .and_then(|v| v.checked_mul(m - c_j))
                .ok_or(EconomyError::ArithmeticOverflow)?;
            let term_q32 = q32_from_ratio(numerator, denominator)?;
            let both_orderings = term_q32
                .checked_mul(2)
                .ok_or(EconomyError::ArithmeticOverflow)?;
            sumsq_q32 = sumsq_q32
                .checked_add(both_orderings)
                .ok_or(EconomyError::ArithmeticOverflow)?;
        }
    }

    if trace_count == 0 {
        // Every active lineage constant on the common indices (total agreement) --
        // documented convention, see module doc: the degenerate all-zero-variance case is
        // the monoculture extreme, so N_eff := 1 rather than an undefined 0/0.
        return Ok(Q32_ONE);
    }
    // N_eff = trace(C)^2 / Sigma C_ij^2 (see module doc). `sumsq_q32` is already Q32.32
    // (a real number scaled by `Q32_ONE`), so the plain-integer `trace_count^2` must itself
    // be pre-scaled by `Q32_ONE` before `q32_from_ratio` divides -- `q32_from_ratio(a, b)`
    // computes `a*Q32_ONE/b`, i.e. treats both `a` and `b` as *plain* integers, not
    // already-Q32.32 values. Passing `trace_sq_q32 = trace_sq*Q32_ONE` as the numerator
    // yields `trace_sq*Q32_ONE*Q32_ONE/sumsq_q32`, which is exactly
    // `trace_sq / (sumsq_q32/Q32_ONE)` expressed back in Q32.32 -- the correct two-Q32.32-
    // values division.
    let trace_sq = trace_count
        .checked_mul(trace_count)
        .ok_or(EconomyError::ArithmeticOverflow)?;
    let trace_sq_q32 = trace_sq
        .checked_mul(Q32_ONE)
        .ok_or(EconomyError::ArithmeticOverflow)?;
    q32_from_ratio(trace_sq_q32, sumsq_q32)
}

/// Shannon entropy in bits, Q32.32 (ADR-ECON-003 Decision 3: `H_lineage`). `-Sigma p*log2(p)`
/// over the nonzero-count buckets of `counts`, with `total` the sum of all counts.
fn shannon_entropy_bits_q32(
    counts: &BTreeMap<&str, i128>,
    total: i128,
) -> Result<i128, EconomyError> {
    let mut h_q32: i128 = 0;
    for &count in counts.values() {
        if count == 0 {
            continue;
        }
        let p_q32 = q32_from_ratio(count, total)?;
        let log2_p_q32 = log2_q32(p_q32);
        // log2_p_q32 <= 0 for p in (0,1], so negating p*log2(p) yields a non-negative bits
        // contribution.
        let term = q32_mul(p_q32, log2_p_q32);
        h_q32 = h_q32
            .checked_sub(term)
            .ok_or(EconomyError::ArithmeticOverflow)?;
    }
    Ok(h_q32)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::routing_fold::{AnnealMode, FloorConfig, arbitrate_anneal_mode};

    fn rec(lineage: &str, idx: u64, verdict: bool) -> LineageSettlement {
        LineageSettlement {
            lineage_id: lineage.to_string(),
            settlement_index: idx,
            verdict,
        }
    }

    // -- Empty / single-lineage / data-sufficiency edge cases --------------------------

    #[test]
    fn empty_history_is_not_enough_data() {
        assert_eq!(
            compute_n_eff_and_h_lineage(&[]).unwrap(),
            NEffHLineage::NotEnoughData
        );
    }

    // `log2_q32`/`exp2_q32` (shared from `routing_fold`) are exact at almost every point but
    // carry a few-ULP quantization artifact right at exact powers of two -- e.g.
    // `log2_q32(Q32_ONE) == 1`, not the mathematically exact `0` (empirically probed: the
    // fixed-iteration bisection's plateau at the low end of `exp2f_q32`'s polynomial can't
    // distinguish `y=0` from a handful of the smallest representable `y>0`). This is a much
    // tighter, distinct artifact from routing_fold's own documented `~1e-3` `exp2f`
    // approximation-error band; `H_LINEAGE_TOLERANCE_Q32` bounds it generously.
    const H_LINEAGE_TOLERANCE_Q32: i128 = Q32_ONE / 1_000_000_000;

    #[test]
    fn single_lineage_is_n_eff_one_by_literal_adr_override() {
        let history: Vec<_> = (0..10).map(|i| rec("a", i, i % 3 == 0)).collect();
        let result = compute_n_eff_and_h_lineage(&history).unwrap();
        match result {
            NEffHLineage::Computed {
                n_eff_q32,
                h_lineage_q32,
            } => {
                assert_eq!(n_eff_q32, Q32_ONE);
                assert!(
                    h_lineage_q32.abs() <= H_LINEAGE_TOLERANCE_Q32,
                    "single-lineage H_lineage should be ~0 bits, got {h_lineage_q32}"
                );
            }
            other => panic!("expected Computed, got {other:?}"),
        }
    }

    #[test]
    fn seven_common_indices_is_not_enough_data() {
        // Two lineages sharing exactly 7 common indices (below MIN_COMMON_SETTLEMENT_INDICES).
        let mut history = Vec::new();
        for i in 0..7u64 {
            history.push(rec("a", i, i % 2 == 0));
            history.push(rec("b", i, i % 2 == 1));
        }
        assert_eq!(
            compute_n_eff_and_h_lineage(&history).unwrap(),
            NEffHLineage::NotEnoughData
        );
    }

    #[test]
    fn eight_common_indices_is_computed_not_not_enough_data() {
        // Exactly at the MIN_COMMON_SETTLEMENT_INDICES boundary: must NOT be NotEnoughData.
        let mut history = Vec::new();
        for i in 0..8u64 {
            history.push(rec("a", i, i % 2 == 0));
            history.push(rec("b", i, i % 2 == 1));
        }
        let result = compute_n_eff_and_h_lineage(&history).unwrap();
        assert!(matches!(result, NEffHLineage::Computed { .. }));
    }

    #[test]
    fn conflicting_settlement_for_same_lineage_index_is_rejected() {
        let history = vec![rec("a", 0, true), rec("a", 0, false)];
        assert_eq!(
            compute_n_eff_and_h_lineage(&history),
            Err(EconomyError::DiversityMetricConflictingSettlement)
        );
    }

    #[test]
    fn same_verdict_repeated_at_same_index_is_not_a_conflict() {
        let history = vec![rec("a", 0, true), rec("a", 0, true), rec("b", 0, false)];
        assert!(compute_n_eff_and_h_lineage(&history).is_ok());
    }

    // -- Known correlation-matrix fixtures (design doc §7 WP5 acceptance criterion) -----

    #[test]
    fn two_perfectly_correlated_lineages_collapse_to_n_eff_one() {
        // b always equals a: 4 true / 4 false over 8 common indices, identical pattern.
        let pattern = [true, true, true, true, false, false, false, false];
        let mut history = Vec::new();
        for (i, &v) in pattern.iter().enumerate() {
            history.push(rec("a", i as u64, v));
            history.push(rec("b", i as u64, v));
        }
        let result = compute_n_eff_and_h_lineage(&history).unwrap();
        match result {
            NEffHLineage::Computed { n_eff_q32, .. } => {
                assert_eq!(
                    n_eff_q32, Q32_ONE,
                    "perfectly correlated pair must give N_eff = 1.0"
                );
            }
            other => panic!("expected Computed, got {other:?}"),
        }
    }

    #[test]
    fn two_independent_lineages_give_n_eff_two() {
        // a: [T,T,T,T,F,F,F,F] (c_a=4); b: [T,F,T,F,T,F,T,F] (c_b=4); co_count({both true})
        // = |{0,2}| = 2 = c_a*c_b/m -- exact zero Pearson correlation over 8 indices.
        let a = [true, true, true, true, false, false, false, false];
        let b = [true, false, true, false, true, false, true, false];
        let mut history = Vec::new();
        for i in 0..8u64 {
            history.push(rec("a", i, a[i as usize]));
            history.push(rec("b", i, b[i as usize]));
        }
        let result = compute_n_eff_and_h_lineage(&history).unwrap();
        match result {
            NEffHLineage::Computed { n_eff_q32, .. } => {
                assert_eq!(
                    n_eff_q32,
                    2 * Q32_ONE,
                    "two exactly-independent lineages must give N_eff = 2.0"
                );
            }
            other => panic!("expected Computed, got {other:?}"),
        }
    }

    #[test]
    fn three_mutually_independent_lineages_give_n_eff_three() {
        // Binary-counter columns over 8 rows (m=8): each column balanced 4/4, and every
        // pair's "both true" count is exactly 2 = c_i*c_j/m -- a standard orthogonal-array
        // construction giving pairwise-zero correlation for all 3 pairs simultaneously.
        let mut history = Vec::new();
        for i in 0..8u64 {
            history.push(rec("a", i, (i & 1) != 0));
            history.push(rec("b", i, (i & 2) != 0));
            history.push(rec("c", i, (i & 4) != 0));
        }
        let result = compute_n_eff_and_h_lineage(&history).unwrap();
        match result {
            NEffHLineage::Computed { n_eff_q32, .. } => {
                assert_eq!(
                    n_eff_q32,
                    3 * Q32_ONE,
                    "three mutually independent lineages must give N_eff = 3.0"
                );
            }
            other => panic!("expected Computed, got {other:?}"),
        }
    }

    #[test]
    fn all_constant_active_lineages_give_n_eff_one_by_documented_convention() {
        // Both lineages always PASS on all 8 common indices: zero variance for both, so
        // trace(C) = 0 and the pinned formula degenerates to 0/0. This module's documented
        // extension (see module doc) resolves that as N_eff := 1 (total-agreement
        // monoculture extreme), not an error.
        let mut history = Vec::new();
        for i in 0..8u64 {
            history.push(rec("a", i, true));
            history.push(rec("b", i, true));
        }
        let result = compute_n_eff_and_h_lineage(&history).unwrap();
        match result {
            NEffHLineage::Computed { n_eff_q32, .. } => {
                assert_eq!(n_eff_q32, Q32_ONE);
            }
            other => panic!("expected Computed, got {other:?}"),
        }
    }

    // -- H_lineage fixtures -------------------------------------------------------------

    #[test]
    fn uniform_two_way_lineage_distribution_gives_one_bit_of_entropy() {
        // 8 common indices (>= MIN_COMMON_SETTLEMENT_INDICES) so this hits `Computed`, not
        // `NotEnoughData`; H_lineage only cares about the raw 8-vs-8 selection-frequency
        // split (1.0 bit), independent of whatever N_eff this particular verdict pattern
        // happens to produce.
        let mut history = Vec::new();
        for i in 0..8u64 {
            history.push(rec("a", i, i % 2 == 0));
            history.push(rec("b", i, i % 2 == 1));
        }
        let result = compute_n_eff_and_h_lineage(&history).unwrap();
        match result {
            NEffHLineage::Computed { h_lineage_q32, .. } => {
                let diff = (h_lineage_q32 - Q32_ONE).abs();
                assert!(
                    diff <= H_LINEAGE_TOLERANCE_Q32,
                    "uniform 2-way split must give ~1.0 bit, got {h_lineage_q32}"
                );
            }
            other => panic!("expected Computed, got {other:?}"),
        }
    }

    #[test]
    fn skewed_lineage_distribution_entropy_matches_hand_computation_within_tolerance() {
        // 24 "a" + 8 "b" out of 32 (0.75 / 0.25 split): H = -0.75*log2(0.75) -
        // 0.25*log2(0.25) ~= 0.81127812 bits. "a" must have *at least* the 8 shared common
        // indices (a lineage can't have fewer settlements than the common-index
        // intersection it participates in), so the skew comes from 16 *extra* indices
        // unique to "a" (settlement_index 100..116) beyond the 8 shared with "b" -- the
        // window's per-lineage *record count* (H_lineage) and the common-index
        // *intersection* (N_eff) are related but distinct quantities by design.
        let mut history = Vec::new();
        for i in 0..8u64 {
            history.push(rec("a", i, true));
            history.push(rec("b", i, true));
        }
        for i in 100..116u64 {
            history.push(rec("a", i, i % 2 == 0));
        }
        let result = compute_n_eff_and_h_lineage(&history).unwrap();
        match result {
            NEffHLineage::Computed { h_lineage_q32, .. } => {
                let expected_q32 = (0.811_278_12_f64 * (Q32_ONE as f64)) as i128;
                let diff = (h_lineage_q32 - expected_q32).abs();
                let tolerance = Q32_ONE / 1000; // matches routing_fold's exp2f tolerance band
                assert!(
                    diff <= tolerance,
                    "h_lineage_q32={h_lineage_q32} expected~={expected_q32} diff={diff} tol={tolerance}"
                );
            }
            other => panic!("expected Computed, got {other:?}"),
        }
    }

    // -- Determinism (Art 0.2) -----------------------------------------------------------

    #[test]
    fn result_is_independent_of_input_ordering() {
        let a = [true, true, true, true, false, false, false, false];
        let b = [true, false, true, false, true, false, true, false];
        let mut forward = Vec::new();
        for i in 0..8u64 {
            forward.push(rec("a", i, a[i as usize]));
            forward.push(rec("b", i, b[i as usize]));
        }
        let mut shuffled = forward.clone();
        shuffled.reverse();
        // Interleave differently too, not just reverse.
        shuffled.rotate_left(3);

        let r1 = compute_n_eff_and_h_lineage(&forward).unwrap();
        let r2 = compute_n_eff_and_h_lineage(&shuffled).unwrap();
        assert_eq!(
            r1, r2,
            "same event set in a different order must fold identically"
        );
    }

    // -- "喂它,不要重造仲裁": this estimator's output driving the existing WP3 floor hook --

    #[test]
    fn monoculture_n_eff_feeds_routing_folds_existing_floor_arbitration_hook() {
        // Two perfectly-correlated lineages -> N_eff = 1.0, which must trip
        // routing_fold's *own*, already-merged floor-arbitration hook (this module never
        // reimplements that decision).
        let pattern = [true, true, true, true, false, false, false, false];
        let mut history = Vec::new();
        for (i, &v) in pattern.iter().enumerate() {
            history.push(rec("a", i as u64, v));
            history.push(rec("b", i as u64, v));
        }
        let n_eff_q32 = match compute_n_eff_and_h_lineage(&history).unwrap() {
            NEffHLineage::Computed { n_eff_q32, .. } => n_eff_q32,
            other => panic!("expected Computed, got {other:?}"),
        };

        // ADR-ECON-003 Decision 3 A-zone floor values (public by design, Art III.3) --
        // fine to use literally in test code (see routing_fold's own `test_floor_cfg`).
        let floor = FloorConfig {
            pause_at_or_below_q32: q32_from_ratio(2, 1).unwrap(),
            resume_at_or_above_q32: q32_from_ratio(9, 4).unwrap(),
        };
        let mode = arbitrate_anneal_mode(AnnealMode::Annealing, n_eff_q32, &floor);
        assert_eq!(
            mode,
            AnnealMode::Paused,
            "N_eff=1.0 (monoculture) must pause annealing via routing_fold's own hook"
        );
    }
}
