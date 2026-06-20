"""Unit tests for the smart dispatch router (fast-by-default cost/effort tiering)."""
import unittest

from turingos import dispatch_router as R


def cap(**kw):
    base = {"allowed_files": ["a.py"]}
    base.update(kw)
    return base


class TestDispatchRouter(unittest.TestCase):
    def test_default_is_fast(self):
        self.assertEqual(R.select_tier(cap()), "fast")

    def test_medium_risk_or_breadth_is_standard(self):
        self.assertEqual(R.select_tier(cap(risk_class="medium")), "standard")
        self.assertEqual(R.select_tier(cap(allowed_files=["a", "b", "c"])), "standard")

    def test_high_risk_or_wide_is_deep(self):
        self.assertEqual(R.select_tier(cap(risk_class="high")), "deep")
        self.assertEqual(R.select_tier(cap(allowed_files=list("abcde"))), "deep")

    def test_retry_escalates_one_tier(self):
        # injected_rules present => this atom already failed cheaply => escalate one tier
        self.assertEqual(R.select_tier(cap(injected_rules=[{"failure_class": "x", "rule": "y"}])), "standard")
        self.assertEqual(
            R.select_tier(cap(risk_class="medium", injected_rules=[{"failure_class": "x", "rule": "y"}])), "deep")

    def test_explicit_tier_overrides(self):
        self.assertEqual(R.select_tier(cap(tier="deep")), "deep")

    def test_fast_flags_are_cheap_per_worker(self):
        # claude must NOT default to opus; codex must lower reasoning effort.
        self.assertIn("sonnet", R.worker_flags("claude", "fast"))
        self.assertIn("low", " ".join(R.worker_flags("claude", "fast")))
        self.assertIn("model_reasoning_effort=low", R.worker_flags("codex", "fast"))
        self.assertTrue(R.worker_flags("agy", "fast"))
        self.assertIn("grok-composer-2.5-fast", R.worker_flags("grok", "fast"))

    def test_deep_uses_strong_models(self):
        self.assertIn("opus", R.worker_flags("claude", "deep"))
        self.assertIn("model_reasoning_effort=high", R.worker_flags("codex", "deep"))

    def test_unknown_worker_no_flags(self):
        self.assertEqual(R.worker_flags("nope", "fast"), [])


if __name__ == "__main__":
    unittest.main()
