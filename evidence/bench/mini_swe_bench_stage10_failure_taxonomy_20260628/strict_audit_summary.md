# Stage10 Strict Audit Summary

## MicroTape Strict Result

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

## Failure Taxonomy Result

```text
status: PASS
classes_seen: 10
all_failures_have_failure_node: true
all_failures_have_broadcast_rule_candidate: true
broadcast_candidates_preserve_only: true
raw_logs_not_broadcast: true
```

The auditor performs a recursive string scan of each `broadcast_rule_candidate` and fails on raw log, hidden predicate, PPUT/heldout, or credential-like markers.

## Scope

This Stage10 fixture proves taxonomy coverage and preserve-only broadcast-rule candidates for failed paths. It does not claim repair ability or solve-rate.
