# ADR-M6-004 - Projection Integrity Audit

```yaml
status: accepted-addressed
decision-makers:
  - Codex orchestrator
date: 2026-07-03
authority_level: 4
constitution_articles:
  - Art. 0.2 Tape Canonical
  - Art. 0.3 Auditability
evidence:
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/research/RES_M6_hci_projection_console.md
    sha256: 55b138db6ab341252223d250b056a3915f8f963b2ae1f5f19eafcdee9e20813d
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/modules/MODULE_M6_hci_console.md
    sha256: 58e07e8453d4ee69db7df785da82d479da009a7910a07cf3d75a73a1ce13c763
status_ceiling: ADDRESSED
```

## Context

G7 requires every displayed value to be replayable from tape. Hash equality of a projection snapshot is not enough if new fields can appear without declared derivation or if the checker imports the same projection code it is auditing.

## Decision

Implement an independent projection-integrity audit that never imports `turing-projection`. The audit must perform shadow rebuild, independent head derivation, provenance-manifest closure for every displayed JSON pointer, render fidelity between text and JSON, and a worker-leakage grep for owner-only projection material.

## Consequences

Adding a displayed field requires declaring its derivation. The integrity verdict becomes a mechanical input to M6.P5 and M6.G, with NOT_RUN treated as a failing gate.
