# Stage11 Loop-until-PASS Qualification

Scope: deterministic SWE-bench-shaped protocol fixture for the no-HITL repair loop.

This is not a solve-rate claim and not a statistical benchmark. It proves the causal chain:

```text
failed attempt
-> FailureNode
-> FailureCertificate
-> BroadcastRuleActivated
-> RetryAuthorized
-> next WorkCapsuleBuilt consumes rule
-> official PASS
-> CandidateAccepted
-> terminal MarketSettled / RewardDistributed
-> final PPUTAccounted(progress=1)
```

No external model API key is used in this fixture. External CLI/API workers remain a later capability path.

## Evidence

- Loop manifest: `loop_manifest.json`
- Bundle manifest: `bundle_manifest.json`
- Bundle SHA-256 list: `bundle_sha256s.txt`
- Strict MicroTape audit: `micro_tape_audit_strict/micro_tape_decision_dag_audit.json`
- Decision DAG markdown: `micro_tape_audit_strict/micro_tape_decision_dag.md`
- Decision DAG DOT: `micro_tape_audit_strict/micro_tape_decision_dag.dot`
- Loop-until-PASS audit: `loop_until_pass_audit.json`
- Failure memory activation audit: `failure_memory_activation_audit.json`
- Real classifier audit: `real_classifier_audit.json`
- Secret scan summary: `secret_scan_summary.txt`
- Strict summary: `strict_audit_summary.md`

## Bundles

```text
sha256:47cc03074a8407edb8e4ad412e173e43077170b108d60853edf2397d3037f266  evidence/bench/mini_swe_bench_stage11_loop_until_pass_20260628/turingos/instances/stage11_case_1/micro_tape.bundle
sha256:88497d0f1da090c7bfa2c3caaaa2f20ebd2a31ad69c239c82140dd838a2a7ae6  evidence/bench/mini_swe_bench_stage11_loop_until_pass_20260628/turingos/instances/stage11_case_2/micro_tape.bundle
sha256:b2c728fff389438027de218e778e52a46aa85a07dadfa5478bdb31a41fe52eb8  evidence/bench/mini_swe_bench_stage11_loop_until_pass_20260628/turingos/instances/stage11_case_3/micro_tape.bundle
```

## Reproduction

From repo root:

```bash
ROOT=evidence/bench/mini_swe_bench_stage11_loop_until_pass_20260628

python3 tools/bench/run_mini_swe_bench_substrate_smoke.py \
  --loop-until-pass-fixture \
  --authorization-mode required \
  --out-dir "$ROOT" \
  --limit 3

python3 tools/bench/audit_micro_tape_decision_dag.py \
  --strict-vpput \
  --strict-terminal-market \
  --require-authorization-head \
  --coverage "$ROOT/turingos/substrate_coverage.json" \
  --out-dir "$ROOT/micro_tape_audit_strict"

python3 tools/bench/audit_loop_until_pass.py \
  --coverage "$ROOT/turingos/substrate_coverage.json" \
  --out "$ROOT/loop_until_pass_audit.json"

python3 tools/bench/audit_failure_memory_activation.py \
  --coverage "$ROOT/turingos/substrate_coverage.json" \
  --out "$ROOT/failure_memory_activation_audit.json"

python3 tools/bench/audit_real_classifier.py \
  --coverage "$ROOT/turingos/substrate_coverage.json" \
  --out "$ROOT/real_classifier_audit.json"
```

## Status

```text
strict_microtape: PASS
loop_until_pass_audit: PASS
failure_memory_activation_audit: PASS
real_classifier_audit: PASS
```

## Boundaries

Stage11 proves deterministic loop causality and auditability. It does not prove SWE-bench solve-rate, multi-agent routing, or external API worker capability.
