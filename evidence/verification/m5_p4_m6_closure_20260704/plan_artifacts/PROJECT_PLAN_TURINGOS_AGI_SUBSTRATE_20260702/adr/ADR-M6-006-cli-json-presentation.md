# ADR-M6-006 - CLI and JSON Presentation

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

The preserved console is a plain CLI loop. RES_M6 rejects a web surface for this increment and defers richer TUI work because G7 is about replayable projection evidence, not product experience.

## Decision

Keep presentation as plain CLI with stdin/stdout behavior and add a verbatim `--json` mode for `operator_view_snapshot.v1`. Text renderers must include `micro_repo` so deterministic demo output cannot be mistaken for a real tape.

## Consequences

Agents, shell scripts, and auditors can consume the same snapshot bytes. A later TUI may format the same snapshot contract if it derives nothing; any web surface requires a new owner-approved ADR.
