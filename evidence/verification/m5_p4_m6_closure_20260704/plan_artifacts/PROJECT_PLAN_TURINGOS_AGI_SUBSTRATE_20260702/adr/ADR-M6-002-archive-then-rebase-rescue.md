# ADR-M6-002 - Archive Then Rebase Rescue

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
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/rescue/operator_console_v1/M6_P0a_VERDICT.json
    sha256: c1a623d270622a217d7655d388a7b3984a9a4ba47fd90a9d7e045da236549004
  - path: /home/zephryj/turingos_backup/work/turing/evidence/hci/operator_console_v1_rescue_20260702/M6_P0b_VERDICT.json
    sha256: f4f2f0e2ee1025c4f699cfa80e726e760ddb9af6b711bd9b6aa6d9b00324aaf4
status_ceiling: ADDRESSED
```

## Context

The console work existed as a dirty second clone at base `6b9daad`, and RES_M6 recorded that the tracked patch applied cleanly to the active repo head observed on 2026-07-02. M6.P0a and M6.P0b preserved the work as a labeled rescue archive before any rebase or behavior change.

## Decision

Use archive-then-rebase for rescue. The original archive remains immutable evidence. After ADR-M6-001 is owner-accepted, M6.P2 may apply the archived patch and untracked files to the planned feature branch, regenerate evidence at the new base, run the required Rust and Python tests, and commit the result citing the M6 ADRs.

## Consequences

The old console bytes are preserved for recovery and comparison, while any future branch evidence must be regenerated at its actual base. Merge remains gated on M6.P5, not on the archive itself.
