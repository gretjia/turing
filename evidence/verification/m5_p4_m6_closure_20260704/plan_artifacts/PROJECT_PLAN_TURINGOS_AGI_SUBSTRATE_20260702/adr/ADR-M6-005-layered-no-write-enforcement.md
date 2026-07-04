# ADR-M6-005 - Layered No-Write Enforcement

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

G7 requires zero head-moving UI paths. Static checks alone are insufficient because the CLI currently has access to write-capable tape types and static tools can miss indirect writes or local allow attributes.

## Decision

No-write enforcement is layered. M6.P3 must add dependency-direction checks, clippy disallowed methods and types, and a self-testing grep gate over operator surfaces. M6.P4 must add dynamic head-conservation and read-only-filesystem command matrices. The project may claim zero head-moving paths only when both static and dynamic gates are green.

## Consequences

The console cannot rely on review discipline for no-write behavior. Hidden writes must either be caught by static gates or become physically visible in dynamic tests.
