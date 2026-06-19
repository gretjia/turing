"""turingos.cli — the `turingos` command-line entrypoint (M12 E2E + spike driver).

Frozen Stage-0 interface (contracts/INTERFACES.md cli.py section):

    turingos tape-init <dir>
    turingos append <dir> <event_type> <payload.json>
    turingos predicate evaluate --capsule <c> --receipt <r> --worktree <w> --tape <dir> --event-type <t>
    turingos replay --tape <dir> --out <dir>
    turingos handoff generate --tape <dir> --out <dir>
    turingos panorama --tape <dir>
    turingos loop --spec <spec.json> --tape <dir>   # Stage-1 E2E driver (thin shim here)

This module is a THIN WIRE: it parses argv and delegates to the already-frozen kernel
(tape.Tape, predicate.evaluate, replay.replay/make_handoff_bundle, reduce.reduce_qt). It adds
NO new policy — every load-bearing decision (head_effect, the predicate verdict, the replay
invariant) lives in the kernel modules, never here. The CLI only chooses inputs, surfaces the
kernel's result on stdout, and maps it to a process exit code.

Exit-code contract:
  * 0  — the operation succeeded (and, for `predicate evaluate`, the gate PASSED).
  * 1  — a kernel error (RejectedAppend / GuardReject / SchemaInvalid / bad input), or a FAIL
         verdict from `predicate evaluate` (a FAIL is a legitimate, non-crashing result).
  * 2  — argparse usage error (unknown subcommand / missing required arg); raised by argparse.

`tape-init` establishes the SHA-256 Micro repo; the FIRST `append` must be a writer-establishing
SystemBootstrapped, after which the CLI reads `current_writer()` so every later append carries the
sovereign writer the guard admits (single active writer — S-2).

Stdlib only (`argparse`, `json`, `sys`, `pathlib`).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import reduce as _reduce
from . import predicate as _predicate
from . import replay as _replay
from .errors import TuringOSError
from .tape import Tape

# Default sovereign writer id used to OPEN a Tape handle and to seed the genesis boot. After the
# first SystemBootstrapped, the CLI resolves the live writer from the Tape (current_writer()).
_DEFAULT_WRITER = "cli-writer"


# --- small IO helpers -------------------------------------------------------


def _load_json(path: str) -> dict:
    """Read + parse a JSON file; raise TuringOSError on a missing/invalid file (-> exit 1)."""
    p = Path(path)
    if not p.exists():
        raise TuringOSError(f"file not found: {path}")
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise TuringOSError(f"cannot read {path}: {exc}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise TuringOSError(f"invalid JSON in {path}: {exc}") from exc


def _print(obj) -> None:
    """Emit one canonical-ish JSON line on stdout (sorted keys, stable for scripting)."""
    print(json.dumps(obj, sort_keys=True, ensure_ascii=False))


def _open_tape(tape_dir: str) -> Tape:
    """Open a Tape handle whose writer_id is the live sovereign writer (or the seed for genesis)."""
    tape = Tape(tape_dir, _DEFAULT_WRITER)
    # If the tape already has a writer-establishing event, adopt it so the FF/identity guard admits.
    if tape.tape_tip() is not None:
        try:
            tape = Tape(tape_dir, tape.current_writer())
        except TuringOSError:
            # No boot event yet (e.g. tip exists but unreadable): fall back to the seed writer.
            pass
    return tape


# --- subcommand handlers ----------------------------------------------------


def _cmd_tape_init(args) -> int:
    """`tape-init <dir>` — create the SHA-256 Micro repo + the two refs + FF config."""
    tape = Tape.init(args.dir, _DEFAULT_WRITER)
    _print({"ok": True, "tape": tape.repo_dir, "object_format": tape.object_format()})
    return 0


def _cmd_append(args) -> int:
    """`append <dir> <event_type> <payload.json>` — append one event; advance tape_tip.

    ADVANCE (SOVEREIGN_ACCEPT) event types require an asserted deterministic Predicate PASS — pass
    `--predicate-pass` to assert it. The kernel still enforces the invariant: an ADVANCE without a
    PASS is RejectedAppend (a failed accept must be emitted as a FailureNode, never a stuck advance).
    """
    payload = _load_json(args.payload)
    tape = _open_tape(args.dir)
    predicate_pass = True if args.predicate_pass else None
    event_id = tape.append(args.event_type, payload, predicate_pass=predicate_pass)
    _print({
        "ok": True,
        "event_id": event_id,
        "event_type": args.event_type,
        "tape_tip": tape.tape_tip(),
        "accepted_head": tape.accepted_head(),
    })
    return 0


def _cmd_predicate_evaluate(args) -> int:
    """`predicate evaluate ...` — run the deterministic gate; exit 0 on PASS, 1 on FAIL."""
    capsule = _load_json(args.capsule)
    receipt = _load_json(args.receipt)
    tape = _open_tape(args.tape)
    result = _predicate.evaluate(
        capsule=capsule,
        receipt=receipt,
        worktree=args.worktree,
        tape=tape,
        event_type=args.event_type,
    )
    _print({
        "passed": result.passed,
        "reason_digest": result.reason_digest,
        "reasons": list(result.reasons),
    })
    return 0 if result.passed else 1


def _cmd_replay(args) -> int:
    """`replay --tape <dir> --out <dir>` — Tape-only replay; write the rebuilt state; exit 0."""
    tape = _open_tape(args.tape)
    state = _replay.replay(tape)
    dump = {
        "accepted_head": state.accepted_head,
        "q_t": state.q_t,
        "workgraph": state.workgraph,
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "replay_state.json").write_text(
        json.dumps(dump, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    _print({"ok": True, "accepted_head": state.accepted_head, "out": str(out)})
    return 0


def _cmd_handoff_generate(args) -> int:
    """`handoff generate --tape <dir> --out <dir>` — record handoff + write a self-contained bundle."""
    tape = _open_tape(args.tape)
    bundle = _replay.make_handoff_bundle(tape, args.out)
    _print({
        "ok": True,
        "bundle": bundle,
        "accepted_head": tape.accepted_head(),
        "tape_tip": tape.tape_tip(),
    })
    return 0


def _cmd_panorama(args) -> int:
    """`panorama --tape <dir>` — print q_t plus the Authorized-vs-Accepted labels (text view)."""
    tape = _open_tape(args.tape)
    q_t = _reduce.reduce_qt(tape)
    accepted_head = tape.accepted_head()
    tape_tip = tape.tape_tip()
    # In 1.0 there is NO authorization_head: ordinary authorization is a PRESERVE Tape event, so the
    # "Authorized" frontier is the live tape_tip and the "Accepted" frontier is accepted_head.
    _print({
        "panorama": True,
        "accepted_head": accepted_head,
        "authorized_head": tape_tip,
        "labels": {
            "accepted": accepted_head,
            "authorized": tape_tip,
        },
        "q_t": q_t,
    })
    return 0


def _cmd_loop(args) -> int:
    """`loop --spec <spec.json> --tape <dir>` — Stage-1 E2E driver (thin shim until loop.py lands).

    The full driver lives in turingos.loop (a separate module). If it is present we delegate; until
    then this surfaces a clear, non-crashing 'not wired yet' so the CLI contract is honest.
    """
    try:
        from . import loop as _loop  # noqa: WPS433 (optional module, may not exist yet)
    except ImportError:
        _print({"ok": False, "error": "loop driver (turingos.loop) is not available yet"})
        return 1
    spec = _load_json(args.spec)
    tape = _open_tape(args.tape)
    result = _loop.run(spec, tape)  # type: ignore[attr-defined]
    _print({"ok": True, "result": result})
    return 0


# --- parser -----------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="turingos", description="TuringOS 1.0 CLI")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    p_init = sub.add_parser("tape-init", help="create a SHA-256 Micro Tape repo + the two refs")
    p_init.add_argument("dir", help="directory for the Micro Tape repo")
    p_init.set_defaults(func=_cmd_tape_init)

    p_append = sub.add_parser("append", help="append one event (advances tape_tip)")
    p_append.add_argument("dir", help="Micro Tape repo directory")
    p_append.add_argument("event_type", help="registry event type (closed-world)")
    p_append.add_argument("payload", help="path to a JSON payload file")
    p_append.add_argument("--predicate-pass", action="store_true", dest="predicate_pass",
                          help="assert a deterministic Predicate PASS (required for ADVANCE events)")
    p_append.set_defaults(func=_cmd_append)

    p_pred = sub.add_parser("predicate", help="deterministic predicate operations")
    pred_sub = p_pred.add_subparsers(dest="predicate_command", metavar="<op>")
    p_eval = pred_sub.add_parser("evaluate", help="run the P0..P9 gate (exit 0=PASS, 1=FAIL)")
    p_eval.add_argument("--capsule", required=True, help="capsule JSON path")
    p_eval.add_argument("--receipt", required=True, help="receipt JSON path")
    p_eval.add_argument("--worktree", required=True, help="candidate worktree path")
    p_eval.add_argument("--tape", required=True, help="Micro Tape repo directory")
    p_eval.add_argument("--event-type", required=True, dest="event_type",
                        help="the event type being gated (e.g. CandidateAccepted)")
    p_eval.set_defaults(func=_cmd_predicate_evaluate)

    p_replay = sub.add_parser("replay", help="Tape-only replay; write rebuilt state")
    p_replay.add_argument("--tape", required=True, help="Micro Tape repo directory")
    p_replay.add_argument("--out", required=True, help="output directory for the rebuilt state")
    p_replay.set_defaults(func=_cmd_replay)

    p_handoff = sub.add_parser("handoff", help="single-writer handoff operations")
    handoff_sub = p_handoff.add_subparsers(dest="handoff_command", metavar="<op>")
    p_hgen = handoff_sub.add_parser("generate", help="record handoff + write a self-contained bundle")
    p_hgen.add_argument("--tape", required=True, help="Micro Tape repo directory")
    p_hgen.add_argument("--out", required=True, help="output directory for the handoff bundle")
    p_hgen.set_defaults(func=_cmd_handoff_generate)

    p_pan = sub.add_parser("panorama", help="print q_t + Authorized-vs-Accepted labels")
    p_pan.add_argument("--tape", required=True, help="Micro Tape repo directory")
    p_pan.set_defaults(func=_cmd_panorama)

    p_loop = sub.add_parser("loop", help="Stage-1 E2E loop driver")
    p_loop.add_argument("--spec", required=True, help="loop spec JSON path")
    p_loop.add_argument("--tape", required=True, help="Micro Tape repo directory")
    p_loop.set_defaults(func=_cmd_loop)

    return parser


def main(argv=None) -> int:
    """Parse argv and dispatch to the matching subcommand handler; return a process exit code.

    Returns nonzero (without raising) on a kernel error or a FAIL predicate verdict. argparse usage
    errors (unknown subcommand / missing required arg) raise SystemExit(2) as argparse does by design.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    # A bare invocation (no subcommand) or a parent command with no chosen op has no `func`.
    func = getattr(args, "func", None)
    if func is None:
        parser.print_usage(sys.stderr)
        return 2

    try:
        return func(args)
    except TuringOSError as exc:
        # Kernel-level failure (rejected append, schema invalid, bad input): honest nonzero exit.
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
