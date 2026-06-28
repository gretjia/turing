# Stage8 Strict Audit Summary

## Result

```text
overall: PASS
replay_structural_integrity: PASS
bundle_accessibility: PASS
basic_ref_reconstruction: PASS
git_topology: PASS
canonical_payload_hash: PASS
registry_head_effect: PASS
accepted_head_authority: PASS
authorization_head: PASS
terminal_golden_path_anchors_to_accepted_head: PASS
failed_progress_zero: PASS
accepted_final_progress_one: PASS
cost_conservation_all_branches: PASS
vpput_accounting: PASS
economic_timing: PASS
market_accounting_correctness: PASS
constitutional_protocol_audit: PASS
```

## Event Counts

```text
SystemConstitutionAccepted: 1
GoalStateProposed: 1
AtomAuthorized: 1
WorkerDispatchAuthorized: 2
WorkCapsuleBuilt: 2
WorkerReceiptImported: 2
MacroObservationImported: 2
OfficialEvaluatorEvidenceImported: 2
FailureNode: 1
FailureCertificate: 1
BroadcastRuleActivated: 1
RetryAuthorized: 1
CandidateAccepted: 1
MarketSettled: 1
RewardDistributed: 1
CostEvent: 2
PPUTAccounted: 2
```

## Key IDs

```text
first_failure_event_id: mu:1a72efcf70b4346431ffca6b2abf08871600e0066004359bf2e38c056bc3ed03
broadcast_rule_event_id: mu:05687ad0830093285eef0697caffb94bba8484a2e0edc161f9acc378df9aa12e
retry_policy_event_id: mu:3cc056d939a1fea9dc1f978233bc45b519660faa26fba5edd71020ce1f6f2f38
terminal_candidate_accepted_event_id: mu:f17c61a1217408519a377288290c32702e56571264ee2da1c7f442d12695e9ae
accepted_head: mu:f17c61a1217408519a377288290c32702e56571264ee2da1c7f442d12695e9ae
authorization_head: mu:0a6725e9fadbad11a449190e02a295d66b8fbacf26a00c32b213793427c7ca40
```

## Scope

This is a Stage8 protocol fixture. It proves replayable no-HITL retry causality and failure-memory injection on a SWE-bench-shaped MicroTape. It does not claim statistical solve-rate or real model capability uplift.
