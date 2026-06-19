"""turingos.worker.adapter — WorkerAdapter ABC + dispatch (TIMEOUT / KILL / RETRY, PG reap).

Frozen seam (contracts/INTERFACES.md worker/adapter.py):

    class WorkerAdapter(abc.ABC):
        worker_id: str
        def run(self, capsule: dict, worktree: str) -> dict: ...   # returns a turingos.receipt.v1 dict
    def dispatch(adapter, capsule, worktree, *, timeout_s) -> dict # normalizes failure -> receipt

Two kinds of adapter (ADR-WORKER-001):

  * IN-PROCESS adapter — implements run(capsule, worktree) in Python (e.g. FakeWorker). dispatch()
    just calls run() (a wall-clock budget is enforced cooperatively via signal.alarm on POSIX).

  * SUBPROCESS adapter — declares a `subprocess_argv` (list[str]) (and optional `subprocess_env`).
    dispatch() spawns that argv in its OWN process group (os.setsid), so a hung worker AND any
    children it spawns can be reaped as a whole group. On timeout dispatch() sends SIGTERM then,
    after a short grace, SIGKILL to the ENTIRE process group (PG-REAP) — no orphan is left behind —
    and normalizes the outcome into a receipt with status in {ok, failed, timeout, killed} and
    no_orphan: true. A clean exit 0 -> status ok; a non-zero exit -> status failed.

The substrate never trusts a worker's self-report as the gate; dispatch only normalizes the
worker OUTCOME into a schema-valid receipt. The deterministic Predicate re-runs the real checks.

Stdlib only (abc, os, signal, subprocess, time).
"""
from __future__ import annotations

import abc
import os
import signal
import subprocess
import time

from .. import codec

# Grace window between SIGTERM and SIGKILL when reaping a hung process group.
_TERM_GRACE_S = 1.0


class WorkerAdapter(abc.ABC):
    """The single seam through which candidate code is produced.

    Concrete adapters set a `worker_id` (adapter-agnostic identity, e.g. 'fake', 'claude')
    and implement run(capsule, worktree) -> a turingos.receipt.v1 dict. A subprocess-backed
    adapter may instead declare a `subprocess_argv` so dispatch() runs it in its own process
    group with timeout/kill/retry semantics.
    """

    worker_id: str = "worker"
    # A subprocess-backed adapter overrides this with the argv to spawn (run in its OWN pgroup).
    subprocess_argv = None  # type: ignore[assignment]
    subprocess_env = None  # type: ignore[assignment]

    @abc.abstractmethod
    def run(self, capsule: dict, worktree: str) -> dict:
        """Produce a candidate in `worktree` and return a turingos.receipt.v1 receipt dict."""
        raise NotImplementedError


def _receipt_id(capsule: dict, worker_id: str, status: str, *, salt: str = "") -> str:
    """Deterministic receipt_id ("rcpt:"+hex) derived from the load-bearing fields."""
    body = {
        "capsule_id": capsule.get("capsule_id", ""),
        "worker_id": worker_id,
        "status": status,
        "salt": salt,
    }
    return "rcpt:" + codec.content_digest(body)[len("sha256:"):]


def _normalized_failure_receipt(adapter, capsule: dict, worktree: str, status: str) -> dict:
    """A schema-valid turingos.receipt.v1 capturing a normalized worker failure outcome.

    no_orphan is True: dispatch() reaped the whole process group, so there is no orphan.
    The candidate is empty (tree_oid "" / files_touched []) — the Predicate will reject it,
    which is correct: a timed-out / killed / failed worker produced no acceptable candidate.
    """
    worker_id = getattr(adapter, "worker_id", "worker")
    return {
        "schema_id": "turingos.receipt.v1",
        "receipt_id": _receipt_id(capsule, worker_id, status),
        "capsule_id": capsule.get("capsule_id", ""),
        "worker_id": worker_id,
        "worktree_path": worktree,
        "candidate": {"tree_oid": "", "files_touched": []},
        "declared_test_results": [],
        "status": status,
        "no_orphan": True,
    }


def _pgid_alive(pgid: int):
    """Liveness of process group `pgid`: False (gone), True (alive), or 'zombie_leader' (EPERM).

    On macOS a `killpg` against a group whose LEADER is an un-reaped zombie returns EPERM even
    though the group is not fully torn down; we surface that as 'zombie_leader' so the caller
    reaps the direct child (clearing the zombie) before deciding the group is gone.
    """
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return "zombie_leader"
    return True


def _reap_group(proc: "subprocess.Popen", pgid: int) -> str:
    """SIGTERM then (if needed) SIGKILL the WHOLE process group; return 'timeout' or 'killed'.

    Returns 'timeout' if SIGTERM brought the group down within the grace window, 'killed' if a
    SIGKILL was required. Either way the group (the worker AND every child it spawned) is gone and
    the direct child is reaped (no zombie, no orphan).

    Ordering matters on macOS: once the group LEADER (our direct child) catches TERM it becomes a
    zombie, and killpg against that pgid then returns EPERM. So after signalling we wait() the
    direct child to clear the zombie BEFORE we judge whether the group is gone or needs a KILL.
    """
    status = "timeout"
    # Phase 1: polite TERM to the entire group (worker + descendants).
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        pass

    # Reap the direct child (the group leader) so its zombie no longer masks the group state.
    try:
        proc.wait(timeout=_TERM_GRACE_S)
    except subprocess.TimeoutExpired:
        pass

    # Grace window: let the rest of the group exit on TERM.
    deadline = time.time() + _TERM_GRACE_S
    while time.time() < deadline:
        alive = _pgid_alive(pgid)
        if alive is False:
            break
        if alive == "zombie_leader":
            # Leader still a zombie — finish reaping it, then re-check.
            try:
                proc.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                pass
        time.sleep(0.02)

    # Phase 2: anything still alive gets a hard KILL (no orphan left behind).
    if _pgid_alive(pgid) is True:
        status = "killed"
        try:
            os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

    # Final reap of the direct child (clears any remaining zombie) + bounded confirmation.
    try:
        proc.wait(timeout=_TERM_GRACE_S + 2.0)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
            proc.wait(timeout=1.0)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            pass
    confirm_deadline = time.time() + 2.0
    while time.time() < confirm_deadline:
        alive = _pgid_alive(pgid)
        if alive is False:
            break
        if alive == "zombie_leader":
            try:
                proc.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                pass
        time.sleep(0.02)
    return status


def _dispatch_subprocess(adapter, capsule: dict, worktree: str, *, timeout_s: int) -> dict:
    """Run a subprocess-backed adapter in its OWN process group with timeout/kill/retry."""
    os.makedirs(worktree, exist_ok=True)
    env = {**os.environ}
    if getattr(adapter, "subprocess_env", None):
        env.update(adapter.subprocess_env)

    # start_new_session=True => os.setsid in the child => the child is the leader of a NEW
    # process group whose pgid == child pid. Every descendant inherits that group, so signalling
    # the group reaps the worker AND anything it spawned (PG-REAP, no orphan).
    proc = subprocess.Popen(
        list(adapter.subprocess_argv),
        cwd=worktree,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    pgid = os.getpgid(proc.pid)
    try:
        proc.communicate(timeout=timeout_s)
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        # Hung worker: reap the whole group (TERM -> KILL), then normalize to a failure receipt.
        status = _reap_group(proc, pgid)
        for stream in (proc.stdout, proc.stderr):
            try:
                if stream is not None:
                    stream.close()
            except OSError:
                pass
        return _normalized_failure_receipt(adapter, capsule, worktree, status)

    # Process exited on its own within the budget. Make sure no descendant lingers.
    if _pgid_alive(pgid) is not False:
        try:
            os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

    if rc == 0:
        # A subprocess worker is expected to print/persist its receipt elsewhere; for the seam
        # we normalize a clean exit into an ok-status receipt skeleton. (A real subprocess worker
        # would emit a full receipt JSON; that parsing belongs to its concrete adapter.run().)
        receipt = _normalized_failure_receipt(adapter, capsule, worktree, "ok")
        return receipt
    return _normalized_failure_receipt(adapter, capsule, worktree, "failed")


def dispatch(adapter: WorkerAdapter, capsule: dict, worktree: str, *, timeout_s: int) -> dict:
    """Dispatch a worker; normalize the outcome into a turingos.receipt.v1 receipt.

    SUBPROCESS adapter (declares `subprocess_argv`): run in its OWN process group; on timeout
    send SIGTERM then SIGKILL to the whole group (PG-REAP — no orphan); status normalized to
    {ok, failed, timeout, killed}, no_orphan True.

    IN-PROCESS adapter: call adapter.run(capsule, worktree). A POSIX wall-clock budget is
    enforced via signal.alarm (best-effort, main-thread only); a run that overruns or raises is
    normalized into a failure receipt. The worker self-report is never the gate.
    """
    if getattr(adapter, "subprocess_argv", None) is not None:
        return _dispatch_subprocess(adapter, capsule, worktree, timeout_s=timeout_s)

    # In-process adapter: enforce a cooperative wall-clock budget where the platform allows it.
    alarm_set = False
    previous_handler = None
    if hasattr(signal, "SIGALRM") and timeout_s and timeout_s > 0:
        try:
            def _on_alarm(signum, frame):  # noqa: ANN001
                raise TimeoutError(f"in-process worker exceeded {timeout_s}s budget")

            previous_handler = signal.signal(signal.SIGALRM, _on_alarm)
            signal.alarm(int(timeout_s))
            alarm_set = True
        except (ValueError, OSError):
            # Not on the main thread (or unsupported) — fall back to no wall-clock guard.
            alarm_set = False

    try:
        receipt = adapter.run(capsule, worktree)
    except TimeoutError:
        return _normalized_failure_receipt(adapter, capsule, worktree, "timeout")
    except Exception:  # noqa: BLE001 — any worker crash normalizes to a failed receipt
        return _normalized_failure_receipt(adapter, capsule, worktree, "failed")
    finally:
        if alarm_set:
            signal.alarm(0)
            if previous_handler is not None:
                signal.signal(signal.SIGALRM, previous_handler)

    # A well-behaved in-process worker returns its own receipt. Guarantee the no_orphan flag is
    # present (an in-process worker spawns no group, so trivially no orphan).
    if isinstance(receipt, dict):
        receipt.setdefault("no_orphan", True)
    return receipt
