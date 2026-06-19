"""Contract tests for turingos.panorama (stdlib unittest, NOT pytest).

These capture the frozen panorama contract from contracts/INTERFACES.md (panorama.py section)
and the binding UI/copy rule in contracts/refs.md (App C §C.1.1):

  * render(tape) -> str  — a TEXT panorama over the DERIVED projection only:
        q_t       = turingos.reduce.reduce_qt(tape)
        workgraph = turingos.reduce.derive_workgraph(q_t, tape, [])
    The renderer owns NO truth: it MUST NOT append to / mutate the tape (tape_tip unchanged).

  * It MUST distinguish Authorized vs Accepted. Allowed labels:
        Authorized, Pending execution, Awaiting receipt, Receipt matched, Accepted world state.
    FORBIDDEN: rendering an authorization (WorkerDispatched / macro merge) as
    'accepted' / 'completed' / 'done'. A WorkerDispatched is shown under an Authorized-style
    label, never under Accepted.

  * The default render() works WITHOUT the optional 'textual' package; importing panorama
    must succeed whether or not 'textual' is installed.

A small real Tape is built directly via Tape.append (boot + goal + module + atom + dispatch),
since boot.py / planner.py are not yet implemented. Each test uses a UNIQUE tmp dir under
/tmp/tos_panorama_t so parallel agents never collide.

Run: PYTHONPATH=src python3 -m unittest tests.test_panorama -v
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
import unittest

from turingos.tape import Tape
from turingos import reduce as reduce_mod
from turingos import panorama


# The five labels the UI/copy rule (refs.md App C §C.1.1) permits.
_ALLOWED_LABELS = (
    "Authorized",
    "Pending execution",
    "Awaiting receipt",
    "Receipt matched",
    "Accepted world state",
)
# Words it is FORBIDDEN to apply to a WorkerDispatched authorization.
_FORBIDDEN_AUTH_WORDS = ("accepted", "completed", "done")


class PanoramaTestBase(unittest.TestCase):
    def setUp(self):
        # UNIQUE scratch dir per test under /tmp/tos_panorama_t so parallel cases never collide.
        base = os.path.join(tempfile.gettempdir(), "tos_panorama_t")
        os.makedirs(base, exist_ok=True)
        self.root = tempfile.mkdtemp(prefix="case_", dir=base)
        self.repo = os.path.join(self.root, "micro_tape")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _boot(self, writer_id="W1"):
        tape = Tape.init(self.repo, writer_id)
        tape.append("SystemBootstrapped", {"kind": "boot"}, predicate_pass=True)
        return tape

    def _full_tape(self, writer_id="W1"):
        """boot + goal + module + atom — the canonical minimal q_t-populating tape."""
        tape = self._boot(writer_id)
        tape.append(
            "GoalStateAccepted",
            {"goal_id": "G1", "title": "ship the loop"},
            predicate_pass=True,
        )
        tape.append(
            "ModulePlanAccepted",
            {"module_id": "M3", "title": "predicate kernel"},
            predicate_pass=True,
        )
        tape.append("AtomProposed", {"atom_id": "A1", "module_id": "M3"})
        return tape

    def _tape_with_dispatch(self, writer_id="W1"):
        """full tape + a WorkerDispatched authorization (PRESERVE — moves tape_tip, NOT accepted_head)."""
        tape = self._full_tape(writer_id)
        tape.append(
            "WorkerDispatched",
            {"atom_id": "A1", "worker_id": "fake-1", "worktree": "/tmp/wt/A1"},
        )
        return tape


class TestRenderBasics(PanoramaTestBase):
    def test_render_returns_str(self):
        tape = self._full_tape()
        out = panorama.render(tape)
        self.assertIsInstance(out, str)
        self.assertTrue(out.strip(), "render() must produce non-empty text")

    def test_render_includes_accepted_head(self):
        # The panorama must surface accepted_head (HEAD_t = the sovereignly-accepted world state).
        tape = self._full_tape()
        out = panorama.render(tape)
        acc = tape.accepted_head()
        self.assertIsNotNone(acc)
        self.assertIn(acc, out, "render() must include the accepted_head oid")

    def test_render_includes_at_least_one_allowed_label(self):
        tape = self._tape_with_dispatch()
        out = panorama.render(tape)
        self.assertTrue(
            any(label in out for label in _ALLOWED_LABELS),
            f"render() must use at least one allowed label of {_ALLOWED_LABELS}",
        )

    def test_render_works_on_empty_tape(self):
        # A bare repo (no events) must still render a str, not raise.
        tape = Tape.init(self.repo, "W1")
        out = panorama.render(tape)
        self.assertIsInstance(out, str)


class TestAuthorizedVsAccepted(PanoramaTestBase):
    def test_dispatch_not_rendered_as_accepted_or_done(self):
        # Binding: a WorkerDispatched authorization MUST NOT be rendered as accepted/completed/done.
        # We locate the line(s) mentioning the dispatch and assert none of the forbidden words
        # are applied to it.
        tape = self._tape_with_dispatch()
        out = panorama.render(tape)
        lower = out.lower()
        for line in lower.splitlines():
            if "workerdispatched" in line or "dispatch" in line:
                for bad in _FORBIDDEN_AUTH_WORDS:
                    self.assertNotIn(
                        bad,
                        line,
                        f"a WorkerDispatched line must not contain {bad!r}: {line!r}",
                    )

    def test_dispatch_shown_under_authorized_style_label(self):
        # The dispatch must appear under an Authorized-style label (Authorized / Pending execution
        # / Awaiting receipt), never under 'Accepted world state'.
        tape = self._tape_with_dispatch()
        out = panorama.render(tape)
        auth_style = ("Authorized", "Pending execution", "Awaiting receipt")
        # find the dispatch line and confirm an authorized-style label is present in the render
        self.assertTrue(
            any(label in out for label in auth_style),
            "a dispatch must be presented under an Authorized-style label",
        )
        # and the dispatch itself must be visible
        self.assertIn("dispatch", out.lower())

    def test_accepted_label_not_attached_to_authorization(self):
        # 'Accepted world state' must describe accepted_head, never the WorkerDispatched node.
        tape = self._tape_with_dispatch()
        out = panorama.render(tape)
        for line in out.splitlines():
            if "Accepted world state" in line:
                self.assertNotIn(
                    "WorkerDispatched",
                    line,
                    "the Accepted-world-state label must not be applied to a WorkerDispatched node",
                )

    def test_authorized_and_accepted_are_distinct_in_output(self):
        # The two concepts must be visibly distinguished: the render carries an authorized-style
        # label AND an accepted-world-state label, and they are different strings.
        tape = self._tape_with_dispatch()
        out = panorama.render(tape)
        self.assertIn("Accepted world state", out)
        self.assertTrue(
            any(label in out for label in ("Authorized", "Pending execution", "Awaiting receipt")),
            "the render must visibly distinguish Authorized from Accepted",
        )


class TestNoWriteBack(PanoramaTestBase):
    def test_render_does_not_change_tape_tip(self):
        # The renderer owns NO truth: rendering must NOT append or move a ref.
        tape = self._tape_with_dispatch()
        tip_before = tape.tape_tip()
        acc_before = tape.accepted_head()
        n_before = len(tape.walk())
        panorama.render(tape)
        self.assertEqual(tape.tape_tip(), tip_before, "render must not move tape_tip")
        self.assertEqual(tape.accepted_head(), acc_before, "render must not move accepted_head")
        self.assertEqual(len(tape.walk()), n_before, "render must not append events")

    def test_render_is_deterministic(self):
        # Same tape bytes => byte-equal panorama (derived projection, no clock/host leakage).
        tape = self._tape_with_dispatch()
        self.assertEqual(panorama.render(tape), panorama.render(tape))


class TestTextualOptional(PanoramaTestBase):
    def test_import_works_without_textual(self):
        # Importing panorama must succeed whether or not 'textual' is installed. Simulate absence
        # by blocking the import and re-importing the module in a clean module cache.
        import builtins
        import importlib
        import sys

        real_import = builtins.__import__

        def _blocked_import(name, *args, **kwargs):
            if name == "textual" or name.startswith("textual."):
                raise ImportError("textual is not installed (simulated)")
            return real_import(name, *args, **kwargs)

        saved = {k: v for k, v in sys.modules.items() if k == "textual" or k.startswith("textual.")}
        for k in list(saved):
            del sys.modules[k]
        sys.modules.pop("turingos.panorama", None)
        builtins.__import__ = _blocked_import
        try:
            mod = importlib.import_module("turingos.panorama")
            self.assertTrue(hasattr(mod, "render"))
            # render must still work with textual absent.
            tape = self._full_tape()
            self.assertIsInstance(mod.render(tape), str)
        finally:
            builtins.__import__ = real_import
            sys.modules.pop("turingos.panorama", None)
            sys.modules.update(saved)
            importlib.import_module("turingos.panorama")

    def test_has_textual_flag_is_bool(self):
        # The module exposes a guarded flag indicating whether the optional Textual app is available.
        self.assertIsInstance(panorama.HAS_TEXTUAL, bool)


if __name__ == "__main__":
    unittest.main()
