"""WP7 (design doc `research/RES_ECON_emergence_toplevel_design_20260707.md` R1.1 §7
WP7 row; formulas pinned by `adr/ADR-ECON-003-emergence-routing-spec-pins.md` Decision 6):
the ``(Q, N, P)`` tape-fold node state used by the E-harness's arm simulator
(`tools/econ_lab/arms.py`).

This is a harness-level *reference* fold for the experiment runner, not the production
kernel: `crates/turing-economy/src/routing_fold.rs` (WP3) owns the real Q32.32
fixed-point tape fold wired into the economy crate. This module exists so the harness can
drive the five experiment arms and the rank-inversion metric without depending on a
not-yet-merged Rust crate; every formula below is copied verbatim from ADR-ECON-003
Decision 6, not invented.

No formula/threshold here is invented: everything traces to ADR-ECON-003 Decision 6.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple

# ADR-ECON-003 Decision 6.2: "N₀ = 1(单位伪计数)" -- a pinned pseudo-count constant, not
# one of the four B-zone-forbidden families (tau/lambda/N_eff-floor/H_lineage-floor/
# bucket-key); it is the published prior-weight constant itself.
N0 = 1


class FoldError(Exception):
    """Raised when a fold operation would violate the (N, S) non-negativity invariant
    (ADR-ECON-003 Decision 6.4) or the at-most-once-clawback invariant (Decision 6.3).
    Carries no economic parameter *value* -- only structural fold-integrity text."""


@dataclass(frozen=True)
class NodeState:
    """A single ``(domain_bucket, scaffold_id)`` node's ``(P, N, S)`` state
    (ADR-ECON-003 Decision 6 preamble). ``p`` is fixed at node creation (Decision 6.1:
    "P 在节点首次创建时定格; 此后 ... 不再改 P") and is never mutated by this class --
    only ``n``/``s`` change via :meth:`apply_update` / :meth:`apply_clawback`.
    """

    p: float
    n: int = 0
    s: int = 0

    def q_eff(self) -> float:
        """ADR-ECON-003 Decision 6.2: ``Q_eff = (P*N0 + S) / (N0 + N)``."""
        return (self.p * N0 + self.s) / (N0 + self.n)

    def apply_update(self, v: int) -> "NodeState":
        """ADR-ECON-003 Decision 6.2: a ``RoutingPriorUpdated`` verdict ``v`` in {0,1}
        drives ``N <- N+1, S <- S+v``."""
        if v not in (0, 1):
            raise FoldError("routing prior update verdict must be 0 or 1")
        return NodeState(p=self.p, n=self.n + 1, s=self.s + v)

    def apply_clawback(self, v: int) -> "NodeState":
        """ADR-ECON-003 Decision 6.3: an exact inverse of one earlier update:
        ``N <- N-1, S <- S-v``. Raises :class:`FoldError` (BLOCKED, never silently
        clamped) if this would drive either counter negative (Decision 6.4)."""
        if v not in (0, 1):
            raise FoldError("routing prior clawback verdict must be 0 or 1")
        new_n, new_s = self.n - 1, self.s - v
        if new_n < 0 or new_s < 0:
            raise FoldError("fold invariant violated: clawback would drive N or S negative")
        return NodeState(p=self.p, n=new_n, s=new_s)


NodeKey = Tuple[str, str]  # (domain_bucket, scaffold_id)


@dataclass
class Ledger:
    """Keyed ``(domain_bucket, scaffold_id)`` node states plus the backup-event dedup
    sets required by ADR-ECON-003 Decision 6.3 ("同一原事件至多 clawback 一次") and the
    implicit "an update event_hash is applied at most once" invariant it depends on."""

    states: Dict[NodeKey, NodeState] = field(default_factory=dict)
    _applied_hashes: set = field(default_factory=set)
    _clawed_back_hashes: set = field(default_factory=set)

    def get(self, key: NodeKey, default_p: float) -> NodeState:
        return self.states.get(key, NodeState(p=default_p))

    def update(self, key: NodeKey, event_hash: str, v: int, default_p: float) -> NodeState:
        if event_hash in self._applied_hashes:
            raise FoldError("duplicate RoutingPriorUpdated event_hash applied twice")
        state = self.get(key, default_p).apply_update(v)
        self.states[key] = state
        self._applied_hashes.add(event_hash)
        return state

    def clawback(self, key: NodeKey, ref_event_hash: str, v: int, default_p: float) -> NodeState:
        if ref_event_hash not in self._applied_hashes:
            raise FoldError("clawback references an unknown RoutingPriorUpdated event_hash")
        if ref_event_hash in self._clawed_back_hashes:
            raise FoldError("duplicate clawback of the same RoutingPriorUpdated event_hash")
        state = self.get(key, default_p).apply_clawback(v)
        self.states[key] = state
        self._clawed_back_hashes.add(ref_event_hash)
        return state
