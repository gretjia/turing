"""WP7 rank-inversion metric.

Formal definition frozen by `research/PREREG_ECON_emergence_experiments_20260707.md` §4
("inversion 事件形式化定义(冻结...)"), reproduced here verbatim as three conditions,
all required for one *confirmed* inversion:

  (i)   cold-start P-rank of scaffold ``s`` sits in the bucket's lower half;
  (ii)  only through backup updates (accumulated `RoutingPriorUpdated`) does s's
        Q_eff-rank rise to #1 (a genuine flip away from whichever scaffold held rank 1
        immediately before);
  (iii) confirmation window = the next ``m=20`` selections in that bucket: s's pass
        count within the window versus the *displaced* original #1's historical
        pass-rate over its own last 20 settled results before being displaced, tested
        with a one-sided exact binomial test, H0: p_s <= p_hat_displaced, alpha=0.05.

``m=20`` and ``alpha=0.05`` are literal values pinned by that prereg section -- not
invented here, and not one of the four B-zone-forbidden families (tau/lambda/
N_eff-floor/H_lineage-floor/bucket-key): they are the public confirmation-window size
and significance level of a frozen, already-published experiment protocol.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Set

CONFIRMATION_WINDOW_M = 20  # PREREG §4: "确认窗口 ... m=20 次选择"
SIGNIFICANCE_ALPHA = 0.05  # PREREG §4: "单侧精确二项检验 ... α=0.05"


def one_sided_binomial_sf(k: int, n: int, p0: float) -> float:
    """Exact ``P(X >= k)`` for ``X ~ Binomial(n, p0)`` (no scipy dependency)."""
    if n == 0:
        return 1.0
    return sum(math.comb(n, i) * (p0 ** i) * ((1 - p0) ** (n - i)) for i in range(k, n + 1))


def cold_start_lower_half(p_priors: Dict[str, float]) -> Set[str]:
    """Condition (i): the set of scaffold_ids whose cold-start P-rank sits in the
    bucket's lower half (descending-P order, lexicographic scaffold_id tie-break --
    same convention `selection.py` uses for `sorted(route_ids)`)."""
    ordered = sorted(p_priors.items(), key=lambda kv: (-kv[1], kv[0]))
    k = len(ordered)
    return {sid for sid, _ in ordered[k // 2 :]}


@dataclass
class InversionEvent:
    scaffold_id: str
    displaced_scaffold_id: str
    flip_step: int
    p_value: float
    confirmed: bool


def _rank1(q_eff_snapshot: Dict[str, float]) -> str:
    return min(q_eff_snapshot.items(), key=lambda kv: (-kv[1], kv[0]))[0]


def detect_confirmed_inversions(trace) -> List[InversionEvent]:
    """Walk a `arms.BucketTrace`'s post-cold-start Q_eff-rank timeline and return every
    inversion event (confirmed or not) per PREREG §4 conditions (i)-(iii)."""
    lower_half = cold_start_lower_half(trace.p_priors)
    out: List[InversionEvent] = []
    prev_rank1 = None

    for i, ev in enumerate(trace.events):
        if ev.q_eff_snapshot is None:
            continue
        current_rank1 = _rank1(ev.q_eff_snapshot)

        if prev_rank1 is not None and current_rank1 != prev_rank1 and current_rank1 in lower_half:
            s = current_rank1
            displaced = prev_rank1

            window = trace.events[i + 1 : i + 1 + CONFIRMATION_WINDOW_M]
            k = sum(1 for w in window if w.scaffold_id == s and w.accept_pass is True)
            n = sum(1 for w in window if w.scaffold_id == s and w.accept_pass is not None)

            history = [
                w
                for w in trace.events[:i]
                if w.scaffold_id == displaced and w.accept_pass is not None
            ][-CONFIRMATION_WINDOW_M:]

            if history and n > 0:
                p0 = sum(1 for w in history if w.accept_pass) / len(history)
                p_value = one_sided_binomial_sf(k, n, p0)
                confirmed = p_value <= SIGNIFICANCE_ALPHA
            else:
                p_value, confirmed = 1.0, False

            out.append(InversionEvent(s, displaced, i, p_value, confirmed))

        prev_rank1 = current_rank1

    return out


def count_confirmed_inversions(trace) -> int:
    return sum(1 for e in detect_confirmed_inversions(trace) if e.confirmed)
