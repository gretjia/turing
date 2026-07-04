# Operator Command Set v1

The fixed verb set is:

```text
VIEW_STATUS
VIEW_PANOVIEW
EXPLAIN_EVENT
EXPLAIN_BLOCKER
REPLAY_VERIFY
AUDIT_INVARIANTS
PROPOSE_INTENT
PROPOSE_GOAL
PROPOSE_CAPSULE
APPROVE_CAPSULE
DISPATCH_WORKER
OBSERVE_CAPSULE
REJECT_CANDIDATE
REQUEST_MACRO_AUTH
APPROVE_CANDIDATE
HELP
```

Every command is represented as `typed_command.v1` with source heads, risk,
confirmation route, approval requirement, default dry-run behavior, truth-write
capability, expected receipt, and replay command.

Mutation-shaped verbs return `approval_required` or
`human_signature_required` unless a real OS-keyring or hardware-backed approval
event already exists.
