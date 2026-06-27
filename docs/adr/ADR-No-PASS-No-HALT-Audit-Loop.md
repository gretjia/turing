# ADR: No PASS, No HALT Audit Loop

Status: Accepted for external-audit-driven hardening.

## Core Illusion

The runtime did not fail multiple audits because Rust tests were absent; it failed because the loop treated local test green as a halt condition while the external auditor was checking authority category errors.

## Reflection

The repeated misses had the same shape:

- A test hook escaped into a production authority path. `InMemoryTest` was explicit, but it still reached real `turingd` authorization RPCs and moved `authorization_head`.
- A cryptographic equation was mistaken for sovereign authority. An envelope-provided public key proves that some key signed bytes; it does not prove that this key is authorized for `(key_id, signature_route, authority_epoch)`.
- Fixes were scoped to the newest symptom, not to the invariant class. Removing the environment variable did not also prove that every production authority route rejected test custody.
- Verification stopped at `cargo test --workspace`. That proves the checked-in local expectations, not that the auditor’s exact GitHub-served threat model has passed.
- The branch was pushed after self-verification without an explicit “external PASS required” halt predicate.

## Data Flow Layout

```text
AuditFinding
  id: B4.public_key_trust | B4.test_custody | ...
  source_sha: git oid
  authority_boundary: approval | predicate | daemon_ingress | projection
  exploit_shape: text
  expected_invariant: text
  red_test: command + test name
  fix_commit: git oid|null
  external_status: OPEN | ADDRESSED | PASS

AuditAttempt
  attempt_id: sha256(canonical finding ledger + source_sha)
  source_sha: git oid
  local_gate_receipts: [command, exit_code, output_hash]
  static_search_receipts: [pattern, expected_empty]
  pushed_sha: git oid
  auditor_sha: git oid|null
  auditor_verdict: OPEN | PASS|null

HaltPredicate
  local_gates_pass: bool
  remote_sha_matches_local: bool
  external_auditor_pass: bool
  no_open_blockers: bool
```

Micro Tape remains the truth substrate for runtime state. The audit ledger is a development-control projection until the runtime has native AuditFinding/AuditAttempt event schemas; it must not move `accepted_head`.

## Loop

```text
while true:
  read latest external auditor findings
  normalize each finding into an AuditFinding record

  for every OPEN finding:
    write a RED test or static reproducer for the exact exploit shape
    run the reproducer and confirm it fails on the current SHA
    patch the smallest authority boundary that enforces the invariant
    run the reproducer and focused legitimate-behavior tests

  run global local gates:
    cargo fmt --all -- --check
    cargo test --workspace
    git diff --check
    static searches for the exact old bypass patterns

  if any local gate fails:
    append/update AuditAttempt as LOCAL_FAIL
    continue

  push branch
  verify remote branch SHA equals local HEAD
  request external audit on exact pushed SHA

  if external auditor returns PASS:
    halt

  append/update AuditAttempt as EXTERNAL_OPEN with the new findings
  continue
```

## Halt Rule

No external PASS, no HALT.

Local commands can only move a finding from `OPEN` to `ADDRESSED`. Only an external auditor verdict on the exact pushed SHA can move it to `PASS`. A branch is not merge-ready while any blocking finding is `OPEN` or merely `ADDRESSED`.

## Micro-End-To-End Model

The smallest useful loop is:

1. Red-test the exact auditor exploit.
2. Patch one authority boundary.
3. Run focused tests plus `cargo test --workspace`.
4. Push.
5. Confirm remote SHA.
6. Wait for external PASS.
7. If not PASS, continue from step 1.

## Final Self-Check

```text
core_illusion: local green is not external authority
core_data_shapes: AuditFinding, AuditAttempt, HaltPredicate
micro_end_to_end_model: red exploit -> patch -> local gates -> push -> external PASS
single_source_of_truth: Git SHA for source; external auditor verdict for audit closure
new_infrastructure_bottleneck: none; document first, native tape events later
runtime_truth_boundary: audit loop does not move accepted_head
```
