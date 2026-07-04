# ADR-M5-007 - Negative Controls and Skeleton Subsumption

```yaml
status: accepted-addressed
decision-makers:
  - Codex orchestrator
date: 2026-07-03
authority_level: 4
constitution_articles:
  - Art. 0.3 Auditability
  - Art. III.4 Goodhart shielding
evidence:
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/research/RES_M5_independent_verification.md
    sha256: 8893bd16ab7e881faf024b83c8ec11b4c552687fe8122f4bec1a967add79e869
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/modules/MODULE_M5_independent_verification.md
    sha256: 041a3bfd4875fcdf9dc200106bb14b4cd2e127c1c35ed3b8cde6d4580a096b43
  - path: /home/zephryj/turingos_backup/work/turing/docs/handoff/STAGE12_TO_STAGE16_LOOP_ENGINEERING_EXECUTION_PLAN.md
    sha256: acc6e45d42b0e6aca9437156940880eb368909878c177944a2fd13604ec103b2
status_ceiling: ADDRESSED
```

## Context

The legacy release-packet skeleton listed negative controls and a `release_next_stage` field, but no tool instantiated the skeleton and the packet-internal verdict would be an implementer-writable self-closure channel.

## Decision

M5.P2 ships `make_negative_controls.sh` to produce five FIXTURE-labeled seeded-defect packets: tampered bundle byte, fabricated PASS contradicted by transcript, fixture mislabeled REAL, missing declared receipt, and stale repo SHA pin. The P2 gate requires 5/5 recorded audit FAILs with machine-readable reasons before any real submission, one owner-selected control may be submitted blind for auditor calibration, and FCE-S6 reuses the corpus. `turingos.release_packet.v1` subsumes every load-bearing legacy key while `release_next_stage` and packet-internal audit verdicts are lint rejects.

## Consequences

The audit protocol's sensitivity is evidence, not an assumption. The negative-control skeleton becomes consumed artifacts. No packet can carry its own release verdict.
