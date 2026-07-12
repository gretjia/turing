"""WP7 deterministic selection primitive (ADR-ECON-003 Decision 4: "确定性选择:种子派生
+ 数值定点 + 极限语义"). Seed derivation and the limit semantics (tau=0 mode bypass,
tau=inf uniform, finite-tau softmax over ``sorted(route_ids)``) are copied verbatim from
that Decision; nothing here is invented.

Reference-level caveat (reported, not silently assumed): this module computes softmax
with ordinary IEEE-754 floats via ``math.exp``, not the pinned Q32.32 fixed-point
primitives Decision 4 requires for the production kernel (owned by WP1/WP3's
`crates/turing-economy/src/routing_fold.rs` and the `suggest` softmax branch). This
harness only needs same-process, same-input determinism to satisfy its own single-arm
replay test -- it is analysis tooling driving experiment arms, not the consensus-critical
routing path. If bit-for-bit cross-implementation parity with the production kernel ever
becomes load-bearing for the harness, this module should shell out to / FFI into the real
crate instead of re-deriving the arithmetic; that gap is tracked here, not hidden.
"""
from __future__ import annotations

import hashlib
import math
from typing import Dict, Mapping, Optional, Sequence

# ADR-ECON-003 Decision 4 seed domain separator, copied verbatim.
SEED_DOMAIN_SEPARATOR = "routing-select.v1"

ARGMAX = "argmax"
UNIFORM = "uniform"
FINITE = "finite"


def derive_u(
    price_signal_hash: str,
    pput_prior_hash: str,
    route_ids: Sequence[str],
    trigger_event_hash: str,
) -> float:
    """ADR-ECON-003 Decision 4:
    ``u64 = LE(SHA256(seed_domain ‖ price_signal_hash ‖ pput_prior_hash ‖
    join(sorted(route_ids), NUL) ‖ trigger_event_hash)[0..8]); u = u64 / 2**64``.
    All inputs are already-committed literals, so identical inputs reproduce an
    identical ``u`` in this process (Art 0.2 replay determinism, harness-level).
    """
    sorted_ids = "\x00".join(sorted(route_ids))
    payload = (
        SEED_DOMAIN_SEPARATOR + price_signal_hash + pput_prior_hash + sorted_ids + trigger_event_hash
    ).encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    u64 = int.from_bytes(digest[:8], "little")
    return u64 / float(2 ** 64)


def tau_mode(tau: Optional[float]) -> str:
    """ADR-ECON-003 Decision 4 limit semantics: ``tau == 0`` is the argmax mode bypass,
    ``tau is None`` (this module's stand-in for "at or beyond the uniform threshold") or
    ``tau == math.inf`` is the uniform regime, anything else must be a positive finite
    temperature."""
    if tau == 0:
        return ARGMAX
    if tau is None or tau == math.inf:
        return UNIFORM
    if tau <= 0:
        raise ValueError("tau must be > 0 in the finite-tau regime")
    return FINITE


def _require_route_ids(route_ids: Sequence[str]) -> None:
    """Degenerate-input guard (not a Decision-4 semantic: selection over zero routes is
    undefined in every regime). Raising here replaces the previous silent-``None`` return
    from :func:`select_argmax` and the bare ``IndexError`` out of :func:`_inverse_cdf`;
    behavior on any non-empty pool is unchanged."""
    if not route_ids:
        raise ValueError("empty route_ids")


def select_argmax(route_ids: Sequence[str], q_by_route: Mapping[str, float]) -> str:
    """tau=0 mode bypass (Decision 4): "不走 softmax,直接调用现行 argmax 代码路径
    ...严格 `>` 平局保先" over *input order* (mirrors economy:989-1007's convention:
    the first route in ``route_ids`` input order with a strictly greater Q wins ties)."""
    _require_route_ids(route_ids)
    best = None
    best_q = None
    for rid in route_ids:
        q = q_by_route[rid]
        if best_q is None or q > best_q:
            best, best_q = rid, q
    return best


def _inverse_cdf(sorted_ids: Sequence[str], weights: Sequence[float], u: float) -> str:
    total = sum(weights)
    if total <= 0:
        # Degenerate (e.g. all-zero weights): fall back to uniform over the same
        # lexicographic order rather than dividing by zero.
        weights = [1.0] * len(sorted_ids)
        total = float(len(sorted_ids))
    threshold = u * total
    cumulative = 0.0
    for rid, w in zip(sorted_ids, weights):
        cumulative += w
        if threshold < cumulative:
            return rid
    return sorted_ids[-1]


def select_uniform(route_ids: Sequence[str], u: float) -> str:
    """tau=inf mode (Decision 4): uniform inverse-CDF over ``sorted(route_ids)``."""
    _require_route_ids(route_ids)
    sorted_ids = sorted(route_ids)
    return _inverse_cdf(sorted_ids, [1.0] * len(sorted_ids), u)


def select_softmax(
    route_ids: Sequence[str], q_by_route: Mapping[str, float], tau: float, u: float
) -> str:
    """finite tau>0 (Decision 4): softmax(Q/tau) inverse-CDF, cumulative order =
    ``sorted(route_ids)`` (same order the seed derivation hashes over)."""
    _require_route_ids(route_ids)
    sorted_ids = sorted(route_ids)
    scaled = [q_by_route[rid] / tau for rid in sorted_ids]
    shift = max(scaled)  # numerically-stabilizing shift only; does not change the result
    exp_vals = [math.exp(v - shift) for v in scaled]
    return _inverse_cdf(sorted_ids, exp_vals, u)


def select(
    route_ids: Sequence[str],
    q_by_route: Mapping[str, float],
    tau: Optional[float],
    u: float,
) -> str:
    """Dispatch across the three Decision-4 regimes."""
    mode = tau_mode(tau)
    if mode == ARGMAX:
        return select_argmax(route_ids, q_by_route)
    if mode == UNIFORM:
        return select_uniform(route_ids, u)
    return select_softmax(route_ids, q_by_route, tau, u)
