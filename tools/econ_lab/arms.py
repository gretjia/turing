"""WP7 E-harness arm simulator (design doc R1.1 §7 WP7 row; PREREG_ECON_emergence_
experiments_20260707.md §1). Implements the five experiment arms named there:

  * ``main``          -- full backup (Q updates via the independent verifier's verdict).
  * ``frozen_backup``  -- critic #4 correction: Q *never* updates, the whole run long;
                          selection ranks purely on the cold-start prior P.
  * ``static_oracle``  -- one round-robin, equal-exposure calibration round (accept-side
                          judged) before formal counting, then that ranking is frozen for
                          the rest of the run.
  * ``placebo``        -- every selection uses the same deterministic seed-derivation
                          formula but picks uniformly at random, ignoring Q entirely.
  * ``tau_fixed``      -- the tau-sweep arm group (design doc §3 E-price-tau): backup is
                          active exactly like ``main``, but at one fixed tau (no
                          annealing), swept over the public grid below.

Node-state fold = ADR-ECON-003 Decision 6 (`node.py`); selection = Decision 4
(`selection.py`); held-out split / independent verifier = Decision 2 (`verifier/`).

Scope note (reported, not silently assumed): ``main``/``tau_fixed`` here take a single
caller-supplied fixed tau per run, matching the E-price-tau/E-anneal experiment shape in
the design doc, rather than the full tau(N) annealing + N_eff-floor hysteresis schedule
(ADR-ECON-003 Decision 3), whose measurement module (WP5) is not yet merged into this
branch's base (`hci/software3-20260705`) as of this harness's authorship. `node.Ledger`
is schedule-agnostic, so wiring the real tau(N)/N_eff-floor schedule in later is a
plug-in point, not a rewrite: it only requires the caller to supply the schedule function
in place of the constant `tau` used below.

Addendum (2026-07-08, defect record -- independent audit 2026-07-07 finding B4): the
static_oracle calibration round reads ``outcomes[chosen]["accept"]`` for every
calibration trial regardless of ``split_side`` (that read is retained and hereby
documented: the calibration round is accept-judged on all stream-head trials, including
verify-side ones), but its calibration settlement events also carried a non-None accept
outcome, so ``pass_at_budget`` / ``n_accept_settled`` counted the calibration round in
the formal headline metric -- contradicting "before formal counting" above and biasing
static_oracle vs the other arms whenever the stream head skews easy/hard. Fixed by
excluding events with ``side == "calibration"`` from both formal counters (here and in
``runner.run_stream``); calibration mechanics (label reads, ranking freeze, event
recording) are unchanged, and aggregates for arms/streams with zero calibration trials
are byte-identical to before the fix (pinned by tests/test_econ_lab_audit_fixes.py).
"""
from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import selection  # noqa: E402
from node import Ledger  # noqa: E402
from verifier.split import ACCEPT_SIDE, VERIFY_SIDE, split_side  # noqa: E402
from verifier.independent_verifier import verify as independent_verify  # noqa: E402

# Design doc §3 E-price-tau's public sweep grid ("扫固定 τ∈{0,0.5,1,2,∞}"). ``None``
# denotes tau=inf in this module's convention (see `selection.tau_mode`).
TAU_SWEEP_GRID = (0, 0.5, 1, 2, None)

_BACKUP_ACTIVE_KINDS = ("main", "tau_fixed")


@dataclass(frozen=True)
class ArmSpec:
    name: str
    kind: str  # "main" | "frozen_backup" | "static_oracle" | "placebo" | "tau_fixed"
    tau: Optional[float] = None


@dataclass
class SelectionEvent:
    step: int
    scaffold_id: str
    side: str  # "accept" | "verify" | "calibration"
    accept_pass: Optional[bool]
    q_eff_snapshot: Optional[Dict[str, float]]


@dataclass
class BucketTrace:
    scaffolds: List[str]
    p_priors: Dict[str, float]
    events: List[SelectionEvent] = field(default_factory=list)


def _event_hash(case_id: str, scaffold_id: str) -> str:
    return "sha256:" + hashlib.sha256(f"{case_id}:{scaffold_id}".encode("utf-8")).hexdigest()


def _freeze_oracle_ranking(calibration_stats: Dict[str, List[int]]) -> List[str]:
    """Static-oracle ranking: descending calibration-round pass-rate, lexicographic
    scaffold_id tie-break (same convention as `selection.select_softmax`'s cumulative
    order)."""

    def rate(sid: str) -> float:
        n, s = calibration_stats[sid]
        return (s / n) if n else 0.0

    return sorted(calibration_stats.keys(), key=lambda sid: (-rate(sid), sid))


def pass_at_budget(trace: BucketTrace) -> Optional[float]:
    """Fraction of formally settled accept-side selections that passed. ``None`` if the
    bucket had no formal accept-side settlement at all (NOT_ENOUGH_DATA, not zero).
    Calibration-round events (``side == "calibration"``, static_oracle only) are
    excluded from this formal counter (addendum 2026-07-08 in the module docstring)."""
    settled = [
        e for e in trace.events if e.accept_pass is not None and e.side != "calibration"
    ]
    if not settled:
        return None
    return sum(1 for e in settled if e.accept_pass) / len(settled)


def simulate_bucket(bucket_name: str, bucket_fixture: dict, arm: ArmSpec) -> BucketTrace:
    scaffolds = sorted(bucket_fixture["scaffolds"].keys())
    p_priors = {sid: bucket_fixture["scaffolds"][sid]["p_prior"] for sid in scaffolds}
    trials = bucket_fixture["trials"]
    ledger = Ledger()
    trace = BucketTrace(scaffolds=scaffolds, p_priors=p_priors)

    calibration_len = len(scaffolds) if arm.kind == "static_oracle" else 0
    calibration_stats: Dict[str, List[int]] = {sid: [0, 0] for sid in scaffolds}
    oracle_ranking: Optional[List[str]] = None

    for step, trial in enumerate(trials):
        case_id = trial["case_id"]
        side = split_side(case_id)

        if arm.kind == "static_oracle" and step < calibration_len:
            chosen = scaffolds[step % len(scaffolds)]
            accept_outcome = bool(trial["outcomes"][chosen]["accept"])
            calibration_stats[chosen][0] += 1
            calibration_stats[chosen][1] += int(accept_outcome)
            trace.events.append(SelectionEvent(step, chosen, "calibration", accept_outcome, None))
            continue

        if arm.kind == "static_oracle" and oracle_ranking is None:
            oracle_ranking = _freeze_oracle_ranking(calibration_stats)

        q_by_route = {
            sid: ledger.get((bucket_name, sid), p_priors[sid]).q_eff() for sid in scaffolds
        }

        if arm.kind == "placebo":
            u = selection.derive_u(
                trial["price_signal_hash"], trial["pput_prior_hash"], scaffolds, trial["trigger_event_hash"]
            )
            chosen = selection.select_uniform(scaffolds, u)
        elif arm.kind == "static_oracle":
            chosen = oracle_ranking[0]
        else:
            u = selection.derive_u(
                trial["price_signal_hash"], trial["pput_prior_hash"], scaffolds, trial["trigger_event_hash"]
            )
            chosen = selection.select(scaffolds, q_by_route, arm.tau, u)

        accept_pass: Optional[bool] = None
        if side == ACCEPT_SIDE:
            accept_pass = bool(trial["outcomes"][chosen]["accept"])
        elif side == VERIFY_SIDE and arm.kind in _BACKUP_ACTIVE_KINDS:
            witnesses = trial["outcomes"][chosen]["verify_witnesses"]
            v = independent_verify(witnesses)
            ledger.update((bucket_name, chosen), _event_hash(case_id, chosen), v, p_priors[chosen])

        q_snapshot = {
            sid: ledger.get((bucket_name, sid), p_priors[sid]).q_eff() for sid in scaffolds
        }
        trace.events.append(SelectionEvent(step, chosen, side, accept_pass, q_snapshot))

    return trace


def load_bucket_trace_fixture(data: dict) -> BucketTrace:
    """Load a hand-constructed `SelectionEvent`/`BucketTrace` fixture (schema
    ``econ_lab.inversion_fixture.v1``) directly, bypassing the arm simulator -- used for
    unit-testing `inversion.count_confirmed_inversions` against a manually authored,
    fully deterministic event sequence."""
    events = [
        SelectionEvent(
            step=e["step"],
            scaffold_id=e["scaffold_id"],
            side=e["side"],
            accept_pass=e["accept_pass"],
            q_eff_snapshot=e["q_eff_snapshot"],
        )
        for e in data["events"]
    ]
    return BucketTrace(scaffolds=list(data["scaffolds"]), p_priors=dict(data["p_priors"]), events=events)
