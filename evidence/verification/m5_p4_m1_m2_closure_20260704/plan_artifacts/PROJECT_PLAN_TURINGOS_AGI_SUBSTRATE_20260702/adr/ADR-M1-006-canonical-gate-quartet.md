# ADR-M1-006 - Canonical Gate Quartet

```yaml
status: accepted-addressed
decision-makers:
  - Codex orchestrator
date: 2026-07-02
authority_level: 4
constitution_articles:
  - Art. 0.2 Tape Canonical
  - Art. 0.3 Auditability
evidence:
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/modules/MODULE_M1_canonical_substrate.md
    sha256: ab3ffbe4fe1aa4a6e6d421c40b5fa9fd2b285e38c6653cd7412d6766bf8401e6
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/02_EXECUTION_PLAYBOOK.md
    sha256: 8d8b3c9c24f59df28c457de4ff32559e31f8998ad847ff7cf5676e347f3cf933
  - path: /home/zephryj/turingos_backup/work/turing/tools/ci/run_m1a_gates.sh
    sha256: dff6f06a679917e260d519c2c1c8df061054db0cbe08adfd6173b52a9217a9c4
  - path: /home/zephryj/turingos_backup/work/turing/tools/gates/gate_xcheck_jcs.sh
    sha256: 66b8f8756dccde0465b0bd7799d83d3dfd3e98b9fb5e40c9e6546c138268e3de
  - path: /home/zephryj/turingos_backup/work/turing/tools/gates/gate_singleton_codec.sh
    sha256: bfaeccd927db2d96ba421cbaa6c6dbc22ce43819bbc24b97f800447a7a161c5a
  - path: /home/zephryj/turingos_backup/work/turing/tools/gates/lint_no_second_codec.py
    sha256: 87e9bafc874b4ca9d7660012209d426fb86a5db6c99106dcc981d57ffe80e92d
  - path: /home/zephryj/turingos_backup/work/turing/tools/gates/gate_ref_lint.sh
    sha256: d5feee4f64d0826b0a02da06bae4be0ae5071c2d01d612ae5fd2fd83d708690b
  - path: /home/zephryj/turingos_backup/work/turing/.github/workflows/ci.yml
    sha256: ac5ce5436a5d9af15d15e696cac2791e7b981ad3e047a1eaa934161307ff246a
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M1A_GATE_SELF_TEST_TRANSCRIPT.txt
    sha256: bb79ea97d53316c4983b9fb885bd6c4c25623a846d51859fe5b347ac8e0f7578
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M1A_GATE_CLEAN_TRANSCRIPT.txt
    sha256: 139b4996967181d15d6367550415ba7c0c3119020c857cf5c53a9b3a1e21ca66
status_ceiling: ADDRESSED
```

## Context

The M1a recurrence risk is not just a missing test; it is the ability to add another canonical-byte writer or sovereign-ref writer without noticing. The gate must therefore be a quartet: cross-implementation bytes, grep singleton check, AST singleton check, and ref-lint.

## Decision

Add `tools/ci/run_m1a_gates.sh` as the local CI runner for M1a. It runs:

- `tools/gates/gate_xcheck_jcs.sh`: Python derived view and Rust owner emit identical canonical byte hex over `corpus_jcs_extended.jsonl`.
- `tools/gates/gate_singleton_codec.sh`: grep-level ban on canonical function definitions and canonical-shaped `json.dumps(... sort_keys=True, separators=...)` outside an allowlist.
- `tools/gates/lint_no_second_codec.py`: AST-level ban that catches aliased `json.dumps` calls and multiline canonical-shaped calls outside the same allowlist.
- `tools/gates/gate_ref_lint.sh`: ban on new `update-ref`/`REF_AUTHORIZATION_HEAD` sovereign-ref writers outside the designated writer and bounded legacy shims.

Each gate has `--self-test`, and `.github/workflows/ci.yml` runs both self-tests and clean gates.

Allowlist rationale:

- `src/turingos/codec.py`: derived Python view until M1e routes through Rust.
- `src/turingos/tape.py`: legacy Python Tape path; M1e demotes it to labeled fixture/compatibility.
- `src/turingos/replay.py`: replay manifest digest helper, not the substrate owner.
- `tools/bench/audit_micro_tape_decision_dag.py`: independent auditor by design.
- `tools/bench/audit_mini_swe_bench_plan.py`, `mini_swe_bench_grok_headless.py`, `prepare_stage12_run_plan.py`, `run_mini_swe_bench_substrate_smoke.py`: legacy bench/fixture/harness digest helpers pending later routing.
- `tools/headless/fixture_probe.py`, `grok_verify.py`, `headless_common.py`: verifier-packet digest helpers, not tape substrate canonical ownership.
- `crates/turing-git-tape/**`: designated sovereign-ref writer.

## Consequences

The gate quartet becomes a mandatory M1a CI runner and a bootstrap check once registered in tracker Program state. New canonical-byte or sovereign-ref code must either route through the owner or update the allowlist with an explicit migration reason that a fresh verifier can inspect.

This ADR does not claim M1.G/G2 is complete, external verification exists, constitution bytes changed, an OG-10/genesis signature exists, M2 is enabled, or any CLOSED, RELEASED, or RATIFIED status.
