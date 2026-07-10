//! WP-H4 (ADR-ECON-007 Decision 2 "检测器信号与经济奖励解耦"): the deterministic pause
//! mask a `RouteFuseTripped` event sequence folds into. Pure, total, tape-fold-only (Art
//! 0.2) -- every function here is a function of its explicit arguments alone (an event
//! sequence, a caller-supplied validity window, and an "as-of" evaluation point), never
//! live-random, never a hidden/global counter.
//!
//! Scope discipline (Decision 2, verbatim): "检测器熔断不写 Q...经济 Q 的唯一更新源仍是
//! 独立验证器结算". This module therefore never touches `routing_fold::NodeState` /
//! `(Q, N, P)` in any way -- it only computes which routes are currently paused, and
//! [`filter_paused_candidates`] only narrows a `CandidateRoute` slice *before* it reaches
//! `MarketRouter::suggest`. The Q/N/S fold (`routing_fold::fold_routing_state`) is a fully
//! separate, untouched code path fed only by `RoutingPriorUpdated`/`RoutingPriorClawback`
//! (independent-verifier settlement, ADR-ECON-003 Decision 2/6) -- `RouteFuseTripped` is
//! never translated into a `RoutingFoldEvent` anywhere in this crate.
//!
//! Known spec gap (reported, not guessed): ADR-ECON-007 Decision 2 pins the *behavior*
//! ("暂停至事件序号+时效") but not an exact wire schema for `RouteFuseTripped`'s ordinal
//! input. This module threads an explicit `event_ordinal: u64` per trip (the same "explicit
//! caller-supplied logical-clock position, never a hidden tape-position counter" discipline
//! `diversity_metrics::LineageSettlement::settlement_index` already establishes elsewhere in
//! this crate), rather than inventing an implicit tape-index counter of its own.

use std::collections::BTreeMap;

use crate::routing_fold::RoutingKey;
use crate::{CandidateRoute, EconomyEvent};

/// One fold input translated from a committed `EconomyEvent::RouteFuseTripped` tape event
/// (WP-H4). `event_ordinal` is the trip's caller-supplied logical-clock position (see the
/// module-level "Known spec gap" note).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RouteFuseTripFoldEvent {
    pub key: RoutingKey,
    pub event_ordinal: u64,
}

/// Caller-supplied pause validity window (ADR-ECON-007 Decision 2 "掩码时效(A 区公开常数)
/// 过期"). Not hardcoded in this module -- the concrete value only ever appears in test
/// fixtures / the caller's own B-zone config mechanism (Art III.4/F4), mirroring
/// `routing_fold::AnnealConfig`/`FloorConfig`'s existing "caller-supplied, never a literal
/// in this source file" discipline.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RoutePauseConfig {
    /// Number of ordinal ticks a single trip's pause remains in force, counted inclusively
    /// from `event_ordinal` (so a route tripped at ordinal `t` with `validity_window = w` is
    /// paused for every `as_of_ordinal` in `[t, t + w]`).
    pub validity_window: u64,
}

/// Deterministically translate one committed `EconomyEvent` into this module's fold input
/// contract (mirrors `routing_fold::economy_event_to_routing_fold_event`'s seam discipline).
/// Every non-`RouteFuseTripped` variant maps to `None` -- this function invents no new
/// semantics, it only relays the fields `EconomyEvent::route_fuse_tripped` already crafted.
#[must_use]
pub fn economy_event_to_route_fuse_trip(event: &EconomyEvent) -> Option<RouteFuseTripFoldEvent> {
    match event {
        EconomyEvent::RouteFuseTripped(tripped) => Some(RouteFuseTripFoldEvent {
            key: RoutingKey {
                domain_bucket: tripped.route_domain.clone(),
                scaffold_id: tripped.route_scaffold.clone(),
            },
            event_ordinal: tripped.event_ordinal,
        }),
        _ => None,
    }
}

/// Order-preserving batch form of [`economy_event_to_route_fuse_trip`] (Art 0.2: never
/// reorders, never silently drops a malformed row -- there is nothing to reject here since
/// every field is already a plain `String`/`u64`, unlike the hash-parsing seam in
/// `routing_fold`).
#[must_use]
pub fn economy_events_to_route_fuse_trips(events: &[EconomyEvent]) -> Vec<RouteFuseTripFoldEvent> {
    events
        .iter()
        .filter_map(economy_event_to_route_fuse_trip)
        .collect()
}

/// Pure fold (ADR-ECON-007 Decision 2): `events` -> per-route "paused through ordinal" map,
/// containing only routes whose pause window `[event_ordinal, event_ordinal +
/// validity_window]` actually covers `as_of_ordinal` for at least one trip on that route --
/// so a trip that hasn't happened yet as of `as_of_ordinal`, or whose own window has already
/// elapsed, contributes nothing (this also correctly leaves a GAP unpaused between two
/// non-overlapping trips on the same route, rather than bridging it). Among the trips that
/// DO cover `as_of_ordinal`, the reported expiry is the MAX of their individual
/// `event_ordinal + validity_window` (a re-trip only ever extends the currently-active
/// pause, never shortens it). Total: `event_ordinal + validity_window` saturates rather than
/// overflowing (Art 0.2 -- no panic on adversarial/huge fixture inputs).
#[must_use]
pub fn compute_route_pause_mask(
    events: &[RouteFuseTripFoldEvent],
    config: &RoutePauseConfig,
    as_of_ordinal: u64,
) -> BTreeMap<RoutingKey, u64> {
    let mut paused_until: BTreeMap<RoutingKey, u64> = BTreeMap::new();
    for event in events {
        if event.event_ordinal > as_of_ordinal {
            continue; // this trip has not happened yet as of the query point.
        }
        let until = event.event_ordinal.saturating_add(config.validity_window);
        if as_of_ordinal > until {
            continue; // this trip's own validity window has already elapsed.
        }
        paused_until
            .entry(event.key.clone())
            .and_modify(|existing| {
                if until > *existing {
                    *existing = until;
                }
            })
            .or_insert(until);
    }
    paused_until
}

/// Filter `routes` against an already-computed pause mask (ADR-ECON-007 Decision 2: "掩码
/// 作用于 suggest 候选集过滤,不碰 Q"). `route_key` maps a candidate route to the
/// `RoutingKey` the mask is keyed on -- this module has no opinion on how a route's market
/// key is derived (same "caller supplies the mapping" discipline as
/// `crates/turing-economy/src/bin/econ_fold_cli.rs`'s `CandidateRouteInput.domain_bucket`/
/// `scaffold_id` fields). Pure, total: never mutates `routing_fold::NodeState` / `(Q, N, S)`
/// in any way -- it only narrows which `CandidateRoute`s are passed on to
/// `MarketRouter::suggest`/`suggest_with_stage`. Order-preserving over `routes`.
#[must_use]
pub fn filter_paused_candidates(
    routes: &[CandidateRoute],
    route_key: impl Fn(&CandidateRoute) -> RoutingKey,
    paused: &BTreeMap<RoutingKey, u64>,
) -> Vec<CandidateRoute> {
    routes
        .iter()
        .filter(|route| !paused.contains_key(&route_key(route)))
        .cloned()
        .collect()
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

    fn trip(bucket: &str, scaffold: &str, ordinal: u64) -> RouteFuseTripFoldEvent {
        RouteFuseTripFoldEvent {
            key: key(bucket, scaffold),
            event_ordinal: ordinal,
        }
    }

    // -- determinism -----------------------------------------------------------------

    #[test]
    fn compute_route_pause_mask_is_deterministic_across_repeated_runs() {
        let events = vec![
            trip("code_review", "route:sha256:aaa", 10),
            trip("code_review", "route:sha256:bbb", 12),
        ];
        let cfg = RoutePauseConfig { validity_window: 5 };
        let run1 = compute_route_pause_mask(&events, &cfg, 14);
        let run2 = compute_route_pause_mask(&events, &cfg, 14);
        assert_eq!(run1, run2);
        assert_eq!(run1.len(), 2);
    }

    // -- expiry: the core "时效过期" acceptance property -------------------------------

    #[test]
    fn pause_is_active_through_the_inclusive_expiry_ordinal_then_lifts() {
        let events = vec![trip("code_review", "route:sha256:aaa", 10)];
        let cfg = RoutePauseConfig { validity_window: 5 };
        let route_key = key("code_review", "route:sha256:aaa");

        // Tripped at 10, validity 5 -> paused for as_of in [10, 15] inclusive.
        for as_of in [10u64, 11, 13, 15] {
            let mask = compute_route_pause_mask(&events, &cfg, as_of);
            assert!(
                mask.contains_key(&route_key),
                "route must be paused at as_of={as_of}"
            );
        }
        // Ordinal 16 is one past expiry: mask must be empty (pause lifted).
        let mask_after = compute_route_pause_mask(&events, &cfg, 16);
        assert!(
            !mask_after.contains_key(&route_key),
            "route must no longer be paused once the validity window has fully elapsed"
        );
    }

    #[test]
    fn zero_validity_window_pauses_only_at_the_exact_trip_ordinal() {
        let events = vec![trip("code_review", "route:sha256:aaa", 10)];
        let cfg = RoutePauseConfig { validity_window: 0 };
        let route_key = key("code_review", "route:sha256:aaa");

        assert!(compute_route_pause_mask(&events, &cfg, 10).contains_key(&route_key));
        assert!(!compute_route_pause_mask(&events, &cfg, 11).contains_key(&route_key));
        assert!(!compute_route_pause_mask(&events, &cfg, 9).contains_key(&route_key));
    }

    #[test]
    fn a_re_trip_extends_but_never_shortens_the_pause() {
        let route_key = key("code_review", "route:sha256:aaa");
        let cfg = RoutePauseConfig { validity_window: 5 };

        // Earlier trip at ordinal 20 (until 25) after an initial trip at ordinal 10
        // (until 15): the mask must report the LATER (larger) expiry, never the earlier one.
        let events = vec![
            trip("code_review", "route:sha256:aaa", 10),
            trip("code_review", "route:sha256:aaa", 20),
        ];
        let mask = compute_route_pause_mask(&events, &cfg, 24);
        assert_eq!(mask.get(&route_key).copied(), Some(25));

        // Order in the input slice must not matter (Art 0.2: pure function of the event
        // multiset for this fold, not of arrival order).
        let events_reordered = vec![
            trip("code_review", "route:sha256:aaa", 20),
            trip("code_review", "route:sha256:aaa", 10),
        ];
        let mask_reordered = compute_route_pause_mask(&events_reordered, &cfg, 24);
        assert_eq!(mask, mask_reordered);
    }

    #[test]
    fn a_gap_between_two_non_overlapping_trips_is_correctly_unpaused() {
        // Trip 1: [10, 15]. Trip 2: [20, 25]. Ordinal 17 sits in the GAP between them and
        // must NOT be reported as paused (regression: a naive "max(until) across all trips"
        // reduction would incorrectly bridge the gap and report paused-through-25 at 17).
        let route_key = key("code_review", "route:sha256:aaa");
        let cfg = RoutePauseConfig { validity_window: 5 };
        let events = vec![
            trip("code_review", "route:sha256:aaa", 10),
            trip("code_review", "route:sha256:aaa", 20),
        ];
        assert!(!compute_route_pause_mask(&events, &cfg, 17).contains_key(&route_key));
        assert!(compute_route_pause_mask(&events, &cfg, 15).contains_key(&route_key));
        assert!(compute_route_pause_mask(&events, &cfg, 20).contains_key(&route_key));
    }

    #[test]
    fn a_trip_that_has_not_happened_yet_does_not_pause_the_route() {
        let route_key = key("code_review", "route:sha256:aaa");
        let cfg = RoutePauseConfig { validity_window: 100 };
        let events = vec![trip("code_review", "route:sha256:aaa", 50)];
        assert!(!compute_route_pause_mask(&events, &cfg, 10).contains_key(&route_key));
        assert!(compute_route_pause_mask(&events, &cfg, 50).contains_key(&route_key));
    }

    #[test]
    fn saturates_rather_than_overflowing_on_adversarial_ordinals() {
        let events = vec![trip("code_review", "route:sha256:aaa", u64::MAX - 1)];
        let cfg = RoutePauseConfig { validity_window: 10 };
        let mask = compute_route_pause_mask(&events, &cfg, u64::MAX);
        let route_key = key("code_review", "route:sha256:aaa");
        assert_eq!(mask.get(&route_key).copied(), Some(u64::MAX));
    }

    // -- filter-only-not-Q: the core Decision 2 acceptance property ---------------------

    #[test]
    fn filter_paused_candidates_only_narrows_the_candidate_list_never_touches_q() {
        let routes = vec![
            CandidateRoute {
                route_id: "route_a".to_string(),
                market_id: "mkt_a".to_string(),
                expected_failure_domain: "provider_x".to_string(),
                requested_tokens: 100,
            },
            CandidateRoute {
                route_id: "route_b".to_string(),
                market_id: "mkt_b".to_string(),
                expected_failure_domain: "provider_x".to_string(),
                requested_tokens: 100,
            },
        ];
        let mut paused = BTreeMap::new();
        paused.insert(key("default", "route:sha256:a"), 999);

        let route_key = |r: &CandidateRoute| {
            if r.route_id == "route_a" {
                key("default", "route:sha256:a")
            } else {
                key("default", "route:sha256:b")
            }
        };
        let filtered = filter_paused_candidates(&routes, route_key, &paused);
        assert_eq!(filtered.len(), 1);
        assert_eq!(filtered[0].route_id, "route_b");
        // Every field on the surviving candidate is byte-identical to the input (a pure
        // filter, never a value-mutating transform -- the "not Q" half of the property:
        // there is no Q/N/S anywhere in a CandidateRoute for this to touch in the first
        // place, and this assertion pins that the filter doesn't invent new fields either).
        assert_eq!(filtered[0], routes[1]);
    }

    #[test]
    fn empty_mask_is_a_no_op_filter() {
        let routes = vec![CandidateRoute {
            route_id: "route_a".to_string(),
            market_id: "mkt_a".to_string(),
            expected_failure_domain: "provider_x".to_string(),
            requested_tokens: 100,
        }];
        let paused = BTreeMap::new();
        let filtered = filter_paused_candidates(&routes, |_| key("default", "x"), &paused);
        assert_eq!(filtered, routes);
    }

    // -- EconomyEvent translation seam --------------------------------------------------

    #[test]
    fn economy_event_translation_only_recognizes_route_fuse_tripped() {
        let tripped = EconomyEvent::route_fuse_tripped(
            "code_review",
            "route:sha256:aaa",
            "detector:loop_v1",
            "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            7,
        )
        .expect("route_fuse_tripped constructs");
        let translated =
            economy_event_to_route_fuse_trip(&tripped).expect("RouteFuseTripped translates");
        assert_eq!(translated.key, key("code_review", "route:sha256:aaa"));
        assert_eq!(translated.event_ordinal, 7);

        let unrelated = EconomyEvent::principal_declared("principal_x", "agent_y");
        assert!(economy_event_to_route_fuse_trip(&unrelated).is_none());

        let batch = economy_events_to_route_fuse_trips(&[tripped, unrelated]);
        assert_eq!(batch.len(), 1);
    }
}
