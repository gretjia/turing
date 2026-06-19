"""turingos.worker — the WorkerAdapter seam (ADR-WORKER-001).

The Worker is the ONLY place candidate code is produced. It is held behind an
adapter seam so the substrate is worker-agnostic: a fake/manual worker (Stage 1),
a subprocess CLI worker, or a future real vendor worker all present the SAME
interface and emit the SAME adapter-agnostic receipt (turingos.receipt.v1, S-6).

Public seam (frozen, contracts/INTERFACES.md worker/adapter.py + worker/fake.py):

    class WorkerAdapter(abc.ABC){ worker_id; run(capsule, worktree) -> receipt dict }
    def dispatch(adapter, capsule, worktree, *, timeout_s) -> receipt
    class FakeWorker(WorkerAdapter)   # deterministic stub (worker.fake)

Receipt != acceptance: a worker self-report is recorded for audit but never trusted
as the gate — the deterministic Predicate kernel re-derives/re-runs everything.
"""
from __future__ import annotations

from .adapter import WorkerAdapter, dispatch

__all__ = ["WorkerAdapter", "dispatch", "FakeWorker"]


def __getattr__(name):  # lazy re-export to avoid an import cycle at module load
    if name == "FakeWorker":
        from .fake import FakeWorker

        return FakeWorker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
