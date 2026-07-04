"""Operator Agent v1: deterministic advisory router for typed commands.

Natural language may select or explain a command, but this module never evaluates
predicates, moves heads, signs approvals, dispatches workers, or runs shell.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256


CLOSED_VERBS = (
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
)

_APPROVAL_REQUIRED = {
    "APPROVE_CAPSULE",
    "DISPATCH_WORKER",
    "REJECT_CANDIDATE",
    "REQUEST_MACRO_AUTH",
    "APPROVE_CANDIDATE",
}

_SOVEREIGN_MUTATION = {"APPROVE_CAPSULE", "APPROVE_CANDIDATE"}
_AUTHORIZATION = {"REJECT_CANDIDATE", "REQUEST_MACRO_AUTH"}
_PROPOSAL = {"PROPOSE_INTENT", "PROPOSE_GOAL", "PROPOSE_CAPSULE"}


@dataclass(frozen=True)
class OperatorAgent:
    """Classify a turn into one closed typed command."""

    def route_turn(self, utterance: str) -> dict:
        verb, rejections = _route_utterance(utterance)
        spec = command_spec(verb)
        return {
            "schema_id": "operator_turn_trace.v1",
            "operator_intent": {
                "schema_id": "operator_intent.v1",
                "utterance_digest": "sha256:" + sha256(utterance.encode()).hexdigest(),
                "selected_verb": verb,
                "router": "deterministic_zh_en_v1",
            },
            "selected_verb": verb,
            "typed_command": spec,
            "tool_manifest": tool_manifest(),
            "agent_capabilities": {
                "can_classify": True,
                "can_explain": True,
                "can_propose": True,
                "can_trace_turns": True,
                "can_evaluate_predicates": False,
                "can_move_heads": False,
                "can_synthesize_approvals": False,
                "can_run_shell": False,
                "can_autonomous_dispatch": False,
            },
            "advisory_confidence": "0.70",
            "rejections": rejections,
        }


def command_spec(verb: str) -> dict:
    if verb not in CLOSED_VERBS:
        raise ValueError(f"unknown operator verb: {verb!r}")
    approval_required = verb in _APPROVAL_REQUIRED
    side_effect_class = _side_effect_class(verb)
    confirmation_route = (
        "human_signature_required"
        if verb in {"APPROVE_CAPSULE", "REQUEST_MACRO_AUTH", "APPROVE_CANDIDATE"}
        else "approval_required"
        if approval_required
        else "none"
    )
    return {
        "schema_id": "typed_command.v1",
        "verb": verb,
        "side_effect_class": side_effect_class,
        "source_heads": ["tape_tip", "authorization_head", "accepted_head"],
        "preconditions": (
            [
                "operator_view_snapshot.v1 is fresh",
                "real approval event exists or return approval_required",
            ]
            if approval_required
            else ["operator_view_snapshot.v1 is fresh"]
        ),
        "risk_class": "P1" if approval_required else "P0",
        "confirmation_route": confirmation_route,
        "approval_required": approval_required,
        "dry_run_default": True,
        "writes_truth": False,
        "expected_receipt": (
            "approval_required_or_human_signature_required"
            if approval_required
            else "read_only_receipt"
        ),
        "replay_command": "turing replay --verify",
    }


def tool_manifest() -> dict:
    return {
        "schema_id": "operator_tool_manifest.v1",
        "commands": [command_spec(verb) for verb in CLOSED_VERBS],
        "can_evaluate_predicates": False,
        "can_move_heads": False,
        "can_synthesize_approvals": False,
        "can_run_shell": False,
        "can_autonomous_dispatch": False,
    }


def production_approval_route_allowed(route: str) -> bool:
    return route in {"os-keyring", "hardware", "hardware-future"}


def _side_effect_class(verb: str) -> str:
    if verb in _SOVEREIGN_MUTATION:
        return "sovereign_mutation"
    if verb == "DISPATCH_WORKER":
        return "worker_dispatch"
    if verb == "OBSERVE_CAPSULE":
        return "observation"
    if verb in _AUTHORIZATION:
        return "authorization"
    if verb in _PROPOSAL:
        return "proposal_only"
    return "read_only"


def _route_utterance(utterance: str) -> tuple[str, list[str]]:
    lower = utterance.lower()
    rejections: list[str] = []
    if any(token in lower for token in ("rm -rf", "shell", "bash", "sh -c", "subprocess")):
        rejections.append("arbitrary_shell_forbidden")
        return "HELP", rejections
    if "reject" in lower and "candidate" in lower:
        return "REJECT_CANDIDATE", rejections
    if "dispatch" in lower or "worker" in lower:
        return "DISPATCH_WORKER", rejections
    if "macro" in lower and ("auth" in lower or "authorization" in lower):
        return "REQUEST_MACRO_AUTH", rejections
    if "approve" in lower and "capsule" in lower:
        return "APPROVE_CAPSULE", rejections
    if any(token in lower for token in ("approve", "candidate", "\u6279\u51c6")):
        return "APPROVE_CANDIDATE", rejections
    if any(token in lower for token in ("blocker", "\u963b\u585e")):
        return "EXPLAIN_BLOCKER", rejections
    if "event" in lower:
        return "EXPLAIN_EVENT", rejections
    if any(token in lower for token in ("panoview", "\u5168\u666f")):
        return "VIEW_PANOVIEW", rejections
    if any(token in lower for token in ("status", "\u72b6\u6001")):
        return "VIEW_STATUS", rejections
    if "replay" in lower:
        return "REPLAY_VERIFY", rejections
    if "audit" in lower:
        return "AUDIT_INVARIANTS", rejections
    if "intent" in lower:
        return "PROPOSE_INTENT", rejections
    if "capsule" in lower:
        return "PROPOSE_CAPSULE", rejections
    if "goal" in lower:
        return "PROPOSE_GOAL", rejections
    return "HELP", rejections


def as_plain_dict(value) -> dict:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return dict(value)
