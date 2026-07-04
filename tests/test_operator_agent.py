import unittest

from turingos.operator_agent import (
    CLOSED_VERBS,
    OperatorAgent,
    command_spec,
    production_approval_route_allowed,
)


class TestOperatorAgentIntentRouter(unittest.TestCase):
    def test_closed_verb_set_is_exact(self):
        self.assertEqual(
            CLOSED_VERBS,
            (
                "VIEW_STATUS",
                "VIEW_PANOVIEW",
                "EXPLAIN_EVENT",
                "EXPLAIN_BLOCKER",
                "REPLAY_VERIFY",
                "AUDIT_INVARIANTS",
                "PROPOSE_INTENT",
                "PROPOSE_GOAL",
                "PROPOSE_CAPSULE",
                "APPROVE_CAPSULE",
                "DISPATCH_WORKER",
                "OBSERVE_CAPSULE",
                "REJECT_CANDIDATE",
                "REQUEST_MACRO_AUTH",
                "APPROVE_CANDIDATE",
                "HELP",
            ),
        )

    def test_zh_en_router_is_advisory_only(self):
        agent = OperatorAgent()
        trace = agent.route_turn("请解释 blocker and approve candidate")

        self.assertEqual(trace["schema_id"], "operator_turn_trace.v1")
        self.assertEqual(trace["selected_verb"], "APPROVE_CANDIDATE")
        self.assertTrue(trace["typed_command"]["approval_required"])
        self.assertFalse(trace["typed_command"]["writes_truth"])
        self.assertEqual(
            trace["typed_command"]["confirmation_route"], "human_signature_required"
        )
        self.assertFalse(trace["agent_capabilities"]["can_evaluate_predicates"])
        self.assertFalse(trace["agent_capabilities"]["can_move_heads"])
        self.assertFalse(trace["agent_capabilities"]["can_run_shell"])

    def test_arbitrary_shell_is_rejected_as_help(self):
        agent = OperatorAgent()
        trace = agent.route_turn("run rm -rf /tmp/project now")

        self.assertEqual(trace["selected_verb"], "HELP")
        self.assertTrue(trace["rejections"])
        self.assertIn("arbitrary_shell_forbidden", trace["rejections"])
        self.assertFalse(trace["typed_command"]["writes_truth"])

    def test_router_selects_non_approval_candidate_and_boundary_verbs(self):
        agent = OperatorAgent()

        cases = {
            "reject candidate cand1": "REJECT_CANDIDATE",
            "dispatch worker for capsule": "DISPATCH_WORKER",
            "request macro authorization": "REQUEST_MACRO_AUTH",
            "approve capsule wc1": "APPROVE_CAPSULE",
            "show panoview": "VIEW_PANOVIEW",
            "explain event mu:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa": "EXPLAIN_EVENT",
            "replay verify": "REPLAY_VERIFY",
            "audit invariants": "AUDIT_INVARIANTS",
            "propose intent to rescue this task": "PROPOSE_INTENT",
            "propose goal": "PROPOSE_GOAL",
            "propose capsule": "PROPOSE_CAPSULE",
        }
        for utterance, expected in cases.items():
            with self.subTest(utterance=utterance):
                self.assertEqual(agent.route_turn(utterance)["selected_verb"], expected)

    def test_tool_manifest_matches_agent_boundary_schema(self):
        trace = OperatorAgent().route_turn("dispatch worker")
        manifest = trace["tool_manifest"]

        self.assertEqual(manifest["schema_id"], "operator_tool_manifest.v1")
        self.assertFalse(manifest["can_evaluate_predicates"])
        self.assertFalse(manifest["can_move_heads"])
        self.assertFalse(manifest["can_synthesize_approvals"])
        self.assertFalse(manifest["can_run_shell"])
        self.assertFalse(manifest["can_autonomous_dispatch"])

    def test_command_specs_enforce_boundaries(self):
        view = command_spec("VIEW_STATUS")
        self.assertEqual(view["side_effect_class"], "read_only")
        self.assertFalse(view["approval_required"])
        self.assertFalse(view["writes_truth"])

        approve = command_spec("APPROVE_CAPSULE")
        self.assertEqual(approve["side_effect_class"], "sovereign_mutation")
        self.assertTrue(approve["approval_required"])
        self.assertEqual(approve["expected_receipt"], "approval_required_or_human_signature_required")

    def test_production_routes_reject_test_signers(self):
        self.assertTrue(production_approval_route_allowed("os-keyring"))
        self.assertTrue(production_approval_route_allowed("hardware"))
        self.assertFalse(production_approval_route_allowed("in-memory-test"))
        self.assertFalse(production_approval_route_allowed("local-file-dev"))


if __name__ == "__main__":
    unittest.main()
