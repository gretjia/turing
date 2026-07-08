"""B1 remedy acceptance (ADR-ECON-003 Decision 4; INDEPENDENT_AUDIT_ECON_LAB_20260707.md
B1; owner decision: conform the Rust kernel to the ADR pin): Rust <-> Python selection
parity.

Before the fix, `derive_selection_seed_u64` (crates/turing-economy/src/lib.rs) dropped the
pinned `trigger_event_hash` seed input while the Python reference
(`tools/econ_lab/selection.py::derive_u`) implemented the full Decision-4 formula, so the
two implementations could NEVER agree on a sampled selection for identical trials -- and no
test could prove parity. This file is that previously-impossible proof: for a grid of fixed
inputs (multiple route sets, multiple trigger_event_hash values, tau in {0, inf, finite})
it computes the selection with the Python reference and asserts the real `econ_fold_cli`
binary (the ONE bridge the live driver uses, backed by `MarketRouter::suggest`) picks the
identical route for the identical fold state.

Exactness notes (why these fixtures are chosen the way they are):
  * Seed/u parity is byte-exact by construction (same SHA-256 payload, same LE-u64 slice).
  * tau=0 (argmax bypass) and tau=inf (uniform) parity is exact for any inputs.
  * Finite-tau parity: the Python reference uses IEEE-754 `math.exp` while the kernel uses
    the pinned Q32.32 `exp2` polynomial (selection.py's own docstring reports this); the
    two weight vectors differ by ~1e-3 relative, so agreement is only guaranteed when the
    sampled `u` does not fall inside that error band around a CDF boundary. The fixed
    fixtures below were verified to sit outside those bands; they are deterministic
    forever, so this cannot flake -- but do not add new finite-tau fixtures without
    re-checking their margins.
  * P priors are dyadic fractions (k/2^m, m <= 9) so the Q32.32 mantissa, the CLI's
    9-decimal yes_price encoding, and the Python float are all the *same* exact value
    (no representation drift feeding the two implementations different Q_eff inputs).
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ECON_LAB = REPO / "tools" / "econ_lab"
CLI_BIN = REPO / "target" / "debug" / "econ_fold_cli"

sys.path.insert(0, str(ECON_LAB))

import selection  # noqa: E402

Q32_ONE = 1 << 32

PRICE_SIGNAL_HASH = "sha256:" + hashlib.sha256(b"parity-price-signal").hexdigest()
PPUT_PRIOR_HASH = "sha256:" + hashlib.sha256(b"parity-pput-prior").hexdigest()
TRIGGER_HASHES = [
    "sha256:" + hashlib.sha256(f"parity-trigger-{i}".encode()).hexdigest() for i in range(4)
]

DOMAIN_BUCKET = "parity_bucket"

# route_id -> P prior (dyadic, m <= 9; see module docstring). Includes a 2-route exact tie
# (argmax first-wins parity), a 3-route and a 4-route set.
ROUTE_SETS: dict[str, dict[str, float]] = {
    "three_distinct": {"route_a": 0.75, "route_b": 0.5, "route_c": 0.25},
    "four_mixed": {"route_d": 0.125, "route_e": 0.625, "route_f": 0.5, "route_g": 0.875},
    "two_way_tie": {"route_h": 0.5, "route_i": 0.5},
}

# tau grid: 0 = argmax mode bypass, inf = uniform, plus two finite values whose Q32.32
# mantissas are exact (0.5 * 2^32, 2.0 * 2^32).
TAUS = [0.0, math.inf, 0.5, 2.0]


def _skip_unless_cli_built() -> None:
    if not CLI_BIN.exists():
        pytest.skip("econ_fold_cli not built; run `cargo build --bin econ_fold_cli -p turing-economy` first")


def _run_cli(subcommand: str, request: dict) -> dict:
    proc = subprocess.run(
        [str(CLI_BIN), subcommand],
        input=json.dumps(request).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert proc.returncode == 0, (
        f"econ_fold_cli {subcommand} failed (exit {proc.returncode}): "
        f"{proc.stderr.decode('utf-8', 'replace')}"
    )
    return json.loads(proc.stdout.decode("utf-8"))


def _scaffold_id_for(route_id: str) -> str:
    # Free-form routing-key string (the CLI treats it as an opaque key component).
    return f"scaffold:sha256:parity-{route_id}"


def _router_mode_for(tau: float) -> dict:
    if tau == 0:
        return {"kind": "SoftmaxArgmaxBypass"}
    if math.isinf(tau):
        return {"kind": "SoftmaxUniform"}
    mantissa = int(tau * Q32_ONE)
    assert mantissa / Q32_ONE == tau, f"finite tau {tau} must be Q32.32-exact for this parity test"
    return {"kind": "SoftmaxFinite", "tau_q32_mantissa": mantissa}


def _fold_and_suggest_route(
    routes: dict[str, float],
    tau: float,
    trigger_event_hash: str,
    committed_routing_events: list[dict] | None = None,
) -> str:
    request = {
        "schema": "econ_fold_cli.fold_and_suggest.request.v2",
        "committed_routing_events": committed_routing_events or [],
        "initial_prices": [
            {
                "domain_bucket": DOMAIN_BUCKET,
                "scaffold_id": _scaffold_id_for(route_id),
                "p_q32": str(int(p * Q32_ONE)),
            }
            for route_id, p in routes.items()
        ],
        "candidate_routes": [
            {
                "route_id": route_id,
                "market_id": f"mkt_{route_id}",
                "expected_failure_domain": "parity_test",
                "requested_tokens": 100,
                "domain_bucket": DOMAIN_BUCKET,
                "scaffold_id": _scaffold_id_for(route_id),
            }
            for route_id in routes
        ],
        "price_signal_hash": PRICE_SIGNAL_HASH,
        "pput_prior_hash": PPUT_PRIOR_HASH,
        "trigger_event_hash": trigger_event_hash,
        "router_mode": _router_mode_for(tau),
    }
    response = _run_cli("fold-and-suggest", request)
    return response["budget_suggestion"]["route_id"]


def _python_reference_route(routes: dict[str, float], tau: float, trigger_event_hash: str) -> str:
    route_ids = list(routes)  # input order == candidate_routes order (argmax parity)
    u = selection.derive_u(PRICE_SIGNAL_HASH, PPUT_PRIOR_HASH, route_ids, trigger_event_hash)
    return selection.select(route_ids, routes, tau if not math.isinf(tau) else None, u)


# ---------------------------------------------------------------------------
# The parity grid: 3 route sets x 4 taus x 4 trigger hashes = 48 cross-checked selections.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("set_name", sorted(ROUTE_SETS))
@pytest.mark.parametrize("tau", TAUS)
def test_selection_parity_python_reference_vs_cli(set_name: str, tau: float) -> None:
    _skip_unless_cli_built()
    routes = ROUTE_SETS[set_name]
    for trigger in TRIGGER_HASHES:
        expected = _python_reference_route(routes, tau, trigger)
        actual = _fold_and_suggest_route(routes, tau, trigger)
        assert actual == expected, (
            f"Rust/Python selection diverged: set={set_name} tau={tau} trigger={trigger[:16]}... "
            f"python={expected} cli={actual}"
        )


def test_trigger_event_hash_varies_cli_selection_end_to_end() -> None:
    """Seed sensitivity through the whole subprocess bridge: with everything else fixed,
    different trigger_event_hash values must produce more than one distinct selection
    (uniform regime, so the pick is a pure function of the seed). This is the exact
    property that was impossible pre-B1 (the Rust seed ignored the trigger entirely, so
    the CLI returned one constant route here)."""
    _skip_unless_cli_built()
    routes = ROUTE_SETS["four_mixed"]
    picks = {
        _fold_and_suggest_route(routes, math.inf, trigger) for trigger in TRIGGER_HASHES
    }
    assert len(picks) > 1, (
        f"CLI selection ignored trigger_event_hash across {len(TRIGGER_HASHES)} distinct "
        f"triggers (always picked {picks})"
    )


def test_selection_parity_with_committed_fold_events() -> None:
    """Same parity, but with a non-empty committed tape so the CLI's Q_eff comes from the
    real (Q, N, P) fold rather than the N=0 initial-price identity: two verified successes
    for route_b lift its Q_eff to (0.5 + 2)/(1 + 2) -- argmax must pick it in both
    implementations, and the uniform pick (Q-independent) must also agree. Finite tau is
    deliberately excluded: the folded Q_eff (5/6) is not exactly representable in both
    numeric systems, which only matters for softmax weight parity (see module docstring)."""
    _skip_unless_cli_built()
    routes = {"route_a": 0.75, "route_b": 0.5, "route_c": 0.25}
    lifted = "route_b"

    events = []
    for i in range(2):
        built = _run_cli(
            "build-routing-prior-updated",
            {
                "schema": "econ_fold_cli.build_routing_prior_updated.request.v1",
                "route_domain": DOMAIN_BUCKET,
                "route_scaffold": _scaffold_id_for(lifted),
                "verdict": True,
                "verdict_source_id": "verifier:parity-test",
                "verifier_attestation_hash": "sha256:"
                + hashlib.sha256(f"parity-attestation-{i}".encode()).hexdigest(),
            },
        )
        events.append(built["event"])

    # Python-side fold identity (ADR-ECON-003 Decision 6.2, N0=1): Q_eff = (P + S)/(1 + N).
    q_by_route = dict(routes)
    q_by_route[lifted] = (routes[lifted] + 2.0) / 3.0

    for tau in (0.0, math.inf):
        for trigger in TRIGGER_HASHES[:2]:
            route_ids = list(routes)
            u = selection.derive_u(PRICE_SIGNAL_HASH, PPUT_PRIOR_HASH, route_ids, trigger)
            expected = selection.select(
                route_ids, q_by_route, tau if not math.isinf(tau) else None, u
            )
            actual = _fold_and_suggest_route(routes, tau, trigger, committed_routing_events=events)
            assert actual == expected, (
                f"Rust/Python selection diverged on folded tape: tau={tau} "
                f"trigger={trigger[:16]}... python={expected} cli={actual}"
            )
    # And the argmax winner must actually be the lifted route (fold really happened).
    assert (
        _fold_and_suggest_route(routes, 0.0, TRIGGER_HASHES[0], committed_routing_events=events)
        == lifted
    )
