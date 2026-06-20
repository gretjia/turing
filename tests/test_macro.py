"""Unit tests for the GitHub MacroAdapter — the merge=human-confirmed gate (no live gh calls)."""
import unittest

from turingos import macro


class TestMacroMergeGate(unittest.TestCase):
    def test_merge_refuses_without_human_confirm(self):
        # The constitutional gate: a Macro merge is human-confirmed; absent a recorded confirm event, refuse.
        with self.assertRaises(macro.MacroError):
            macro.merge("owner/repo", 1, human_confirm_event_id="")

    def test_merge_refuses_with_none_confirm(self):
        with self.assertRaises(macro.MacroError):
            macro.merge("owner/repo", 1, human_confirm_event_id=None)


if __name__ == "__main__":
    unittest.main()
