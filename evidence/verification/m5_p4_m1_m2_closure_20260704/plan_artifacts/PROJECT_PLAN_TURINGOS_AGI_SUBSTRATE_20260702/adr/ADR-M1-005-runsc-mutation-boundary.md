# ADR-M1-005 - runsc Mutation Boundary and Sandbox Provenance

```yaml
status: accepted-addressed
decision-makers:
  - Codex orchestrator
date: 2026-07-02
authority_level: 4
constitution_articles:
  - Art. 0.2 Tape Canonical
  - Art. 0.3 Auditability
  - Art. III.4 Goodhart shielding
evidence:
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/modules/MODULE_M1_canonical_substrate.md
    sha256: ab3ffbe4fe1aa4a6e6d421c40b5fa9fd2b285e38c6653cd7412d6766bf8401e6
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/research/RES_M1_canonical_substrate_integrity.md
    sha256: 6a33aab542dd00b15b8f567fd379a772a5dd83b1223eae25cfa4dd1fd0e2f664
  - path: /home/zephryj/turingos_backup/work/turing/tools/bench/audit_micro_tape_decision_dag.py
    sha256: 1b0d2b64b10d54dfd3b0f9589461f3ef5f7bf30294991d0fc00e3795210e31e3
  - path: /home/zephryj/turingos_backup/work/turing/tools/bench/run_mini_swe_bench_substrate_smoke.py
    sha256: 1bdc2035d3409b31c208cf7921692160f70d422e1cab6a0ad214aeecbfeb07af
  - path: /home/zephryj/turingos_backup/work/turing/tests/test_micro_tape_decision_dag_audit.py
    sha256: b3a63e77870220122fe4cb6e5be7f3e98f486bad69101e01c96fc25ba7996d9b
  - path: /home/zephryj/turingos_backup/work/turing/pack/04_registries/event_registry_v5_3_1.json
    sha256: 9e1d514dbfb056f9d194d1ff4b1f52b8a93584f9fcaffec89461ed59db13c0f3
  - path: /home/zephryj/turingos_backup/work/turing/crates/turing-contracts/src/registry.rs
    sha256: 9b0a58ac9a591ea071248c2f300ab83e6e340029e6719abd7ea87d40ba95b6ea
  - path: /home/zephryj/turingos_backup/work/turing/crates/turing-kernel/tests/head_effect_tamper.rs
    sha256: baa460f799c5db3a23e3d2281afe34ff47da7146c052a3716b92d48276ea0bf2
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M1D_ARTIFACT_MANIFEST.sha256
    sha256: f49ee23497c0b33147eaebb0db7d8229005f3d74871091e454df10fc99100e93
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M1D_RUNSC_SELFTEST_TRANSCRIPT.txt
    sha256: 0b443676938693f35f8ad950c7b02e722c0a5d23770b601b5e8a8cca8b94082c
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M1D_STRICT_SANDBOX_AUDIT_TRANSCRIPT.txt
    sha256: 17777cf3ae4ab1b869a5c3e21b937247027b8e5b48ba622b5f4cbabeb3f00fc8
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M1D_HOST_ASSUMED_DRILL_TRANSCRIPT.txt
    sha256: 99db33d5c94c6f7da021687c7391181685cc33299c5435b1c861e2db3be3ec87
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M1D_REGISTRY_COUNTS_TRANSCRIPT.txt
    sha256: 25c5c4315064078cc5d27994e2f9fc12c70a760bba5f7d683cd07cebc5b17736
status_ceiling: ADDRESSED
```

## Context

RES_M1 requires substrate-driven mutation steps to run under gVisor where available and to record exceptions on tape. Before this increment, runsc was only an environment probe; mutation evidence did not make the boundary reconstructible from the Micro Tape.

On this host, `runsc --rootless --network=none do /bin/true` passes. Therefore HOST_ASSUMED during M1d evaluation on this host is not an acceptable green path; it is only a deliberately exercised exception drill.

## Decision

Adopt `runsc --rootless --network=none do` as the M1d mutation-boundary proof shape for new stage6 substrate fixture mutation events. The run-start self-test records `runsc_version`, `runsc_binary_sha256`, `network: none`, and `selftest_exit: 0` in each mutation event's `sandbox` block.

The mutation event set for this increment is `WorkerReceiptImported` and `MacroObservationImported`, matching the current benchmark tape points where worker patch output and macro diff observation enter the substrate. The strict auditor now exposes `--require-sandbox-provenance`; it fails mutation events missing a valid `sandbox` block, treats `HOST_ASSUMED` as WARN, and reports `sandbox_host_assumed_count`.

Add `SandboxBoundaryAssumed` as an OBSERVATION/PRESERVE registry row with `payload_schema_id: sandbox_boundary_assumed.v1`. If the runsc self-test cannot run, the stage6 builder emits this event before the mutation events and carries a digest-only `HOST_ASSUMED` sandbox block. The broken-path drill proves this path without treating it as a green M1 host outcome.

## Consequences

Stage6 strict fixture bundles now pass the CLI audit with `--strict-vpput --strict-terminal-market --require-authorization-head --require-sandbox-provenance` and `sandbox_host_assumed_count: 0` on this host. The upstream SWE-bench Docker scorer remains untouched. OCI-bundle/image pinning stays deferred to the omega track.

This ADR does not claim M1.G/G2 roll-up, real authorized run, real provider cost provenance, external verification, constitution-byte change, OG-10/genesis signature, M2 enablement, CLOSED, RELEASED, RATIFIED, or SHIPPED status.
