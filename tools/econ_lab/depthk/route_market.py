#!/usr/bin/env python3
"""WP-H4 — route market driver (ADR-ECON-007 Decision 2/4/5; RES_ROUTE_lockIn_remedy_design
_20260710.md L2 "路线成为一等定价对象").

Nature: exploratory construction, offline-fixture only (this WP's own red line: "无真实
worker/评分调用 -- 全离线fixture"). This driver never calls a real worker/scoring harness; it
only exercises the route-stage market (key derivation, softmax/argmax selection, the Decision
2 pause mask, and the Decision 4 falsified-route report) through `econ_fold_cli`'s new
route subcommands.

Architecture (ADR-ECON-007 Decision 5 / ADR-ECON-005 Decision 1 precedent):
  route = a labeled composition of the three depth-k stage choices it commits to
  route market key = (domain_bucket, "route", route_id), route_id = JCS-SHA256 of the
    route descriptor -- reuses `StageRoutingKey`/`stage_option_id` verbatim (zero new
    Rust selection math; see `crates/turing-economy/src/routing_fold.rs`'s WP-H4 section)
  pause mask (Decision 2): a RouteFuseTripped event pauses its route's candidacy for
    `pause_validity_window` ordinal ticks from `event_ordinal`; the mask NEVER writes Q
    (`econ_fold_cli fold-and-suggest-route` filters candidates before selection runs, and
    node_states in its response prove the filtered-out route's (Q, N, P) is untouched)
  route falsification (Decision 4): `route_falsified` builds the structured, proposal_only
    abandonment report -- this driver never emits a bare error-out for a route it gives up on

File-partition discipline (WP-H4 red line): lives under tools/econ_lab/depthk/; does **not**
import, read, or modify tools/econ_lab/monitor/ or tools/econ_lab/live_driver.py (Lane A
territory) -- every helper this file needs (sha256 digesting, CLI subprocess plumbing) is
self-contained, mirroring depth_driver.py's own "duplicated rather than imported across a
file-partition boundary" precedent.

`--priors` (warm-start P injection): same semantics as `live_driver.py`'s Stage B' `--priors`
flag (ADR-ECON-003 Decision 6.1/7.6) -- a JSON file that is either the pinned
`{"priors": {"<route_label>": p, ...}}` shape or a bare `{"<route_label>": p, ...}` mapping,
`p` a probability in `[0, 1]`. Each named route's warm-start `P` seeds its
`(domain_bucket, route_scaffold)` node's *first* fold appearance only (Decision 6.1:
"P 在节点首次创建时定格") -- the P-injection formula itself lives entirely in the pre-existing
Rust `initial_prices` fold plumbing this file's `initial_prices` request field feeds; this
file only turns the priors JSON into that field's wire shape (no formula re-derived here).

Usage:
  python3 tools/econ_lab/depthk/route_market.py --offline-mock --out /tmp/route_market_mock
  python3 tools/econ_lab/depthk/route_market.py --offline-mock --out /tmp/x --priors priors.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[3]

DRIVER_SCHEMA = "econ_lab.depthk.route_market.verdict.v1"
EVIDENCE_CLASS_OFFLINE = "OFFLINE_MOCK"

#: Q32.32 fixed-point unit, mirrored from
#: `crates/turing-economy/src/routing_fold.rs::Q32_ONE` (ADR-ECON-003 Decision 4: "全程
#: Q32.32 定点") -- an encoding-only constant, not a re-derivation of any economic formula
#: (same rationale as `live_driver.py`'s own identically-named constant).
_Q32_ONE = 1 << 32


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(label: str) -> str:
    return "sha256:" + sha256_hex(label.encode("utf-8"))


def find_default_cli_bin() -> Path:
    for profile in ("debug", "release"):
        candidate = REPO_ROOT / "target" / profile / "econ_fold_cli"
        if candidate.exists():
            return candidate
    raise SystemExit(
        "econ_fold_cli binary not found under target/{debug,release}; run "
        "`cargo build --bin econ_fold_cli -p turing-economy` first"
    )


def call_cli(cli_bin: Path, subcommand: str, request: dict[str, Any]) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            [str(cli_bin), subcommand],
            input=json.dumps(request).encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            f"econ_fold_cli {subcommand} failed (timed out after {error.timeout}s)"
        ) from error
    if proc.returncode != 0:
        raise RuntimeError(
            f"econ_fold_cli {subcommand} failed (exit {proc.returncode}): "
            f"{proc.stderr.decode('utf-8', 'replace')}"
        )
    return json.loads(proc.stdout.decode("utf-8"))


# ---------------------------------------------------------------------------
# Route descriptors (v0 fixture routes; ADR-ECON-007 Decision 5's frozen depth-k stage
# option space, composed into whole routes for this driver's own smoke fixture -- not an
# ADR-pinned "the" route set, just this driver's own exploratory candidate list).
# ---------------------------------------------------------------------------

ROUTE_DESCRIPTORS: dict[str, dict[str, str]] = {
    "conservative_repair": {"context": "minimal", "repair": "single_shot", "verify": "none"},
    "iterative_repair": {"context": "source_context", "repair": "loop", "verify": "none"},
    "verified_iterative_repair": {
        "context": "source_context",
        "repair": "loop",
        "verify": "self_check",
    },
}


def derive_route_keys(
    cli_bin: Path, task_family: Optional[str], route_labels: list[str]
) -> tuple[str, dict[str, dict[str, str]]]:
    """Return (domain_bucket, {route_label: {"route_id":.., "route_scaffold":..}})."""
    routes_request = [
        {"route_label": label, **ROUTE_DESCRIPTORS[label]} for label in route_labels
    ]
    response = call_cli(
        cli_bin,
        "derive-route-keys",
        {
            "schema": "econ_fold_cli.derive_route_keys.request.v1",
            "task_family": task_family,
            "routes": routes_request,
        },
    )
    bucket = response["domain_bucket"]
    mapping: dict[str, dict[str, str]] = {}
    for row in response["route_keys"]:
        mapping[row["route_label"]] = {
            "route_id": row["route_id"],
            "route_scaffold": row["route_scaffold"],
        }
    return bucket, mapping


# ---------------------------------------------------------------------------
# --priors warm-start P injection (ADR-ECON-003 Decision 6.1/7.6 semantics, reused verbatim
# from `live_driver.py`'s own `--priors` flag -- see this file's module doc). Self-contained
# (not imported from live_driver.py, per the WP-H4 file-partition red line).
# ---------------------------------------------------------------------------


def load_route_priors(priors_path: Path) -> tuple[dict[str, float], str]:
    """Load a route warm-start priors file. Accepts both `{"priors": {"<route_label>": p,
    ...}}` and a bare `{"<route_label>": p, ...}` mapping (same two shapes
    `live_driver.py::load_stage_b_prime_priors` accepts) -- never guessed beyond these two
    shapes. Returns `(priors_map, file_sha256_hex)`; the sha256 is computed over the raw file
    bytes (before JSON parsing), exactly reproducible by an independent `sha256sum` of the
    same path (migration/provenance evidence, ADR-ECON-003 Decision 7.6)."""
    raw_bytes = priors_path.read_bytes()
    file_sha256 = sha256_hex(raw_bytes)
    parsed = json.loads(raw_bytes.decode("utf-8"))
    if isinstance(parsed, dict) and "priors" in parsed and isinstance(parsed["priors"], dict):
        priors_map = parsed["priors"]
    elif isinstance(parsed, dict):
        priors_map = parsed
    else:
        raise ValueError(f"--priors file {priors_path} must be a JSON object")
    return {str(k): float(v) for k, v in priors_map.items()}, file_sha256


def _p_float_to_q32_mantissa_decimal(p: float) -> str:
    """`p` (a `[0, 1]` probability) -> its Q32.32 fixed-point mantissa as a decimal-literal
    string (the exact wire shape `econ_fold_cli`'s `InitialPriceInput.p_q32` parses). Clamped
    to `[0, 1]` first (Decision 6.1: "clamp 到 [0,1]"); truncated toward zero on the
    fixed-point scale (Decision 4's rounding convention throughout this file's Rust
    counterpart), mirroring `live_driver.py`'s identically-named helper exactly."""
    clamped = max(0.0, min(1.0, p))
    return str(int(clamped * _Q32_ONE))


def route_initial_prices(
    priors_map: dict[str, float],
    *,
    domain_bucket: str,
    route_keys: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    """One `initial_prices` entry per route named in `priors_map` AND present in
    `route_keys` (a route named in the priors file but not in this run's candidate set is
    simply skipped -- open/no-op, not an error). A route absent from `priors_map` needs no
    explicit entry: the CLI's own `q_eff_for_key` fallback already applies `P = 0.5` to any
    key with no `initial_prices` entry and no fold history."""
    entries: list[dict[str, Any]] = []
    for label, p in priors_map.items():
        if label not in route_keys:
            continue
        entries.append(
            {
                "domain_bucket": domain_bucket,
                "scaffold_id": route_keys[label]["route_scaffold"],
                "p_q32": _p_float_to_q32_mantissa_decimal(p),
            }
        )
    return entries


# ---------------------------------------------------------------------------
# Route-stage selection + settlement + fuse-trip / falsification wrappers.
# ---------------------------------------------------------------------------


def fold_and_select_route(
    cli_bin: Path,
    *,
    domain_bucket: str,
    route_keys: dict[str, dict[str, str]],
    route_labels: list[str],
    committed_routing_events: list[dict[str, Any]],
    instance_id: str,
    pause_validity_window: int,
    as_of_event_ordinal: int,
    initial_prices: Optional[list[dict[str, Any]]] = None,
    router_mode: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """One route-layer softmax/argmax selection over `route_labels`, with the Decision 2
    pause mask applied (CLI single source of truth: this file re-derives no key/selection
    math itself)."""
    candidate_routes = []
    for label in route_labels:
        sid = route_keys[label]["route_scaffold"]
        candidate_routes.append(
            {
                "route_id": label,
                "market_id": f"route:{domain_bucket}:{sid}",
                "expected_failure_domain": "swe_bench_worker_repair",
                "requested_tokens": 12000,
                "domain_bucket": domain_bucket,
                "scaffold_id": sid,
            }
        )
    tape_fingerprint = digest(
        "|".join(
            sorted(
                e.get("RoutingPriorUpdated", {}).get("event_hash", "")
                for e in committed_routing_events
            )
        )
    )
    response = call_cli(
        cli_bin,
        "fold-and-suggest-route",
        {
            "schema": "econ_fold_cli.fold_and_suggest_route.request.v1",
            "committed_routing_events": committed_routing_events,
            "initial_prices": initial_prices or [],
            "candidate_routes": candidate_routes,
            "price_signal_hash": digest(f"price-signal.v1:route-market:{tape_fingerprint}"),
            "pput_prior_hash": digest(f"pput-prior.v1:route-market:{instance_id}"),
            "trigger_event_hash": digest(f"trigger-event.v1:route-market:{instance_id}"),
            "router_mode": router_mode or {"kind": "SoftmaxArgmaxBypass"},
            "pause_validity_window": pause_validity_window,
            "as_of_event_ordinal": as_of_event_ordinal,
        },
    )
    return response


def settle_route(
    cli_bin: Path,
    *,
    domain_bucket: str,
    route_scaffold: str,
    verify_verdict: bool,
    instance_id: str,
    run_label: str,
) -> dict[str, Any]:
    """Independent-verifier settlement on one route node (ADR-ECON-003 Decision 2/6, reused
    verbatim -- `build-routing-prior-updated` is a pre-existing, untouched subcommand)."""
    attestation = digest(
        json.dumps(
            {
                "schema": "route_market.settlement.attestation.v1",
                "instance_id": instance_id,
                "route_scaffold": route_scaffold,
                "verify_verdict": verify_verdict,
                "run_label": run_label,
            },
            sort_keys=True,
        )
    )
    build = call_cli(
        cli_bin,
        "build-routing-prior-updated",
        {
            "schema": "econ_fold_cli.build_routing_prior_updated.request.v1",
            "route_domain": domain_bucket,
            "route_scaffold": route_scaffold,
            "verdict": bool(verify_verdict),
            "verdict_source_id": "verifier:route_market_offline_fixture",
            "verifier_attestation_hash": attestation,
        },
    )
    return build["event"]


def build_route_fuse_tripped(
    cli_bin: Path,
    *,
    domain_bucket: str,
    route_scaffold: str,
    detector_rule_id: str,
    diagnostic_label: str,
    event_ordinal: int,
) -> dict[str, Any]:
    """ADR-ECON-007 Decision 2/3: `diagnostic_label` is hashed, never carried raw, onto the
    tape (Decision 3's no-numeric-leak discipline applied to the tape itself, not just the
    agent-visible message -- see `RouteFuseTripped.diagnostic_digest`'s own doc comment)."""
    build = call_cli(
        cli_bin,
        "build-route-fuse-tripped",
        {
            "schema": "econ_fold_cli.build_route_fuse_tripped.request.v1",
            "route_domain": domain_bucket,
            "route_scaffold": route_scaffold,
            "detector_rule_id": detector_rule_id,
            "diagnostic_digest": digest(diagnostic_label),
            "event_ordinal": event_ordinal,
        },
    )
    return build["event"]


def build_route_falsified(
    cli_bin: Path,
    *,
    route_id: str,
    attempts: int,
    verifier_evidence: list[str],
    detector_events: list[str],
    remaining_candidates: list[str],
    recommendation: str,
) -> dict[str, Any]:
    """ADR-ECON-007 Decision 4: the ONLY legal product of a route abandonment in this
    driver -- never a bare error-out."""
    build = call_cli(
        cli_bin,
        "build-route-falsified",
        {
            "schema": "econ_fold_cli.build_route_falsified.request.v1",
            "route_id": route_id,
            "attempts": attempts,
            "verifier_evidence": verifier_evidence,
            "detector_events": detector_events,
            "remaining_candidates": remaining_candidates,
            "recommendation": recommendation,
        },
    )
    return build["event"]


# ---------------------------------------------------------------------------
# Offline-mock run: deterministic, zero worker/API calls (WP-H4 red line).
# ---------------------------------------------------------------------------


def run_offline_mock(
    out_dir: Path,
    cli_bin: Path,
    *,
    priors_path: Optional[Path] = None,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    route_labels = list(ROUTE_DESCRIPTORS.keys())
    task_family = "Astropy/Astropy"
    domain_bucket, route_keys = derive_route_keys(cli_bin, task_family, route_labels)

    priors_map: dict[str, float] = {}
    priors_sha256: Optional[str] = None
    initial_prices: list[dict[str, Any]] = []
    if priors_path is not None:
        priors_map, priors_sha256 = load_route_priors(priors_path)
        initial_prices = route_initial_prices(
            priors_map, domain_bucket=domain_bucket, route_keys=route_keys
        )

    committed: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []

    # Step 1: un-paused selection over all three routes (cold-start / priors-seeded).
    # ArgmaxBypass (not Uniform) so an injected --priors P is actually observable in the
    # selection outcome: SoftmaxUniform (τ=∞) ignores Q/P entirely by construction, which
    # would make this step a no-op demonstration of the --priors flag's own effect.
    sel_1 = fold_and_select_route(
        cli_bin,
        domain_bucket=domain_bucket,
        route_keys=route_keys,
        route_labels=route_labels,
        committed_routing_events=committed,
        instance_id="mock__step1",
        pause_validity_window=5,
        as_of_event_ordinal=0,
        initial_prices=initial_prices,
        router_mode={"kind": "SoftmaxArgmaxBypass"},
    )
    chosen_1 = sel_1["budget_suggestion"]["route_id"]
    steps.append(
        {
            "step": "cold_start_selection",
            "chosen_route": chosen_1,
            "paused_route_ids": sel_1["paused_route_ids"],
            "budget_suggestion": sel_1["budget_suggestion"],
        }
    )

    # Step 2: independent-verifier PASS settlement on the chosen route (Decision 2: Q's
    # only update source), THEN a RouteFuseTripped fuse trip on that SAME route at ordinal
    # 1 (Decision 2: the detector's own signal, disjoint from the settlement above).
    chosen_scaffold = route_keys[chosen_1]["route_scaffold"]
    settle_event = settle_route(
        cli_bin,
        domain_bucket=domain_bucket,
        route_scaffold=chosen_scaffold,
        verify_verdict=True,
        instance_id="mock__step1",
        run_label="route_market_offline_mock",
    )
    committed.append(settle_event)

    trip_event = build_route_fuse_tripped(
        cli_bin,
        domain_bucket=domain_bucket,
        route_scaffold=chosen_scaffold,
        detector_rule_id="detector:loop_v1",
        diagnostic_label=f"loop detected on route {chosen_1}",
        event_ordinal=1,
    )
    committed.append(trip_event)

    # Step 3: re-select WHILE the trip is still active (as_of within [1, 1+5]) -- the
    # previously-chosen route must be excluded even though its Q is now higher.
    sel_2 = fold_and_select_route(
        cli_bin,
        domain_bucket=domain_bucket,
        route_keys=route_keys,
        route_labels=route_labels,
        committed_routing_events=committed,
        instance_id="mock__step2_paused",
        pause_validity_window=5,
        as_of_event_ordinal=3,
        initial_prices=initial_prices,
        router_mode={"kind": "SoftmaxUniform"},
    )
    steps.append(
        {
            "step": "selection_while_paused",
            "chosen_route": sel_2["budget_suggestion"]["route_id"],
            "paused_route_ids": sel_2["paused_route_ids"],
            "budget_suggestion": sel_2["budget_suggestion"],
        }
    )

    # Step 4: re-select AFTER the pause window has fully elapsed -- the route must be
    # eligible again.
    sel_3 = fold_and_select_route(
        cli_bin,
        domain_bucket=domain_bucket,
        route_keys=route_keys,
        route_labels=route_labels,
        committed_routing_events=committed,
        instance_id="mock__step3_expired",
        pause_validity_window=5,
        as_of_event_ordinal=7,
        initial_prices=initial_prices,
        router_mode={"kind": "SoftmaxUniform"},
    )
    steps.append(
        {
            "step": "selection_after_expiry",
            "chosen_route": sel_3["budget_suggestion"]["route_id"],
            "paused_route_ids": sel_3["paused_route_ids"],
            "budget_suggestion": sel_3["budget_suggestion"],
        }
    )

    # Step 5: a different route is abandoned -- the ONLY legal product is a RouteFalsified
    # report (Decision 4), never a bare error-out.
    falsified_label = next(label for label in route_labels if label != chosen_1)
    falsified_event = build_route_falsified(
        cli_bin,
        route_id=route_keys[falsified_label]["route_id"],
        attempts=2,
        verifier_evidence=[digest(f"verifier-evidence:{falsified_label}:attempt-1")],
        detector_events=[digest(f"detector-event:{falsified_label}:attempt-1")],
        remaining_candidates=[
            route_keys[label]["route_id"] for label in route_labels if label != falsified_label
        ],
        recommendation="escalate to GRILL-ME for route-set reconsideration",
    )
    committed.append(falsified_event)

    verdict = {
        "schema": DRIVER_SCHEMA,
        "mode": "offline_mock",
        "evidence_class": EVIDENCE_CLASS_OFFLINE,
        "domain_bucket": domain_bucket,
        "route_keys": route_keys,
        "priors_path": str(priors_path) if priors_path else None,
        "priors_sha256": priors_sha256,
        "steps": steps,
        "assertions": {
            "chosen_1_is_paused_in_step2": chosen_1 in steps[1]["paused_route_ids"],
            "pause_excludes_the_higher_q_route": (
                chosen_1 in steps[1]["paused_route_ids"]
                and steps[1]["chosen_route"] != chosen_1
            ),
            "route_reeligible_after_expiry": steps[2]["paused_route_ids"] == [],
            "falsified_report_is_proposal_only": bool(
                committed[-1].get("RouteFalsified", {}).get("proposal_only") is True
            ),
            "q_untouched_by_trip_note": (
                "the pause mask's non-interference with (Q, N, P) is verified by the Rust "
                "cross-check test cli_fold_and_suggest_route_pause_mask_excludes_tripped_"
                "route_and_never_touches_q (crates/turing-economy/tests/"
                "econ_fold_cli_cross_check.rs), not re-derived in this Python driver"
            ),
        },
        "committed_routing_events_count": len(committed),
        "worker_calls_used": 0,
        "significance_claims": "NONE — exploratory offline fixture only",
    }
    (out_dir / "verdict.json").write_text(
        json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "committed_routing_events.json").write_text(
        json.dumps(committed, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return verdict


def main() -> None:
    parser = argparse.ArgumentParser(description="WP-H4 route market driver (offline only)")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--econ-fold-cli", type=Path, default=None)
    parser.add_argument(
        "--offline-mock",
        action="store_true",
        help="deterministic offline mock (0 worker calls; the only supported mode -- "
        "WP-H4's red line forbids real worker/scoring calls)",
    )
    parser.add_argument(
        "--priors",
        type=Path,
        default=None,
        help="route warm-start P (ADR-ECON-003 Decision 6.1/7.6, --priors semantics reused "
        "from live_driver.py): path to a JSON file, either "
        '{"priors": {"<route_label>": p, ...}} or a bare {"<route_label>": p, ...} mapping',
    )
    args = parser.parse_args()

    if not args.offline_mock:
        raise SystemExit(
            "must pass --offline-mock (WP-H4 red line: no real worker/scoring calls; "
            "this driver has no other mode)"
        )

    cli_bin = args.econ_fold_cli or find_default_cli_bin()
    if not cli_bin.exists():
        raise SystemExit(f"econ_fold_cli not found at {cli_bin}; build it first")

    verdict = run_offline_mock(args.out, cli_bin, priors_path=args.priors)

    print(
        json.dumps(
            {
                "status": "ADDRESSED",
                "worker_calls_used": verdict["worker_calls_used"],
                "out": str(args.out),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
