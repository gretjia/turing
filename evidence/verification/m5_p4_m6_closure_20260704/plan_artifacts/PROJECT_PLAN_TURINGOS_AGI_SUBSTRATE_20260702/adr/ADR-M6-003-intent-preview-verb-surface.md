# ADR-M6-003 - Intent-Preview Verb Surface

```yaml
status: accepted-addressed
decision-makers:
  - Codex orchestrator
date: 2026-07-03
authority_level: 4
constitution_articles:
  - Art. 0.2 Tape Canonical
  - Art. III.4 Goodhart shielding
evidence:
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/research/RES_M6_hci_projection_console.md
    sha256: 55b138db6ab341252223d250b056a3915f8f963b2ae1f5f19eafcdee9e20813d
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/modules/MODULE_M6_hci_console.md
    sha256: 58e07e8453d4ee69db7df785da82d479da009a7910a07cf3d75a73a1ce13c763
status_ceiling: ADDRESSED
```

## Context

The preserved console has a closed 16-verb surface. Several verbs are command-shaped, but RES_M6 records that the implementation is behaviorally projection and dry-run preview: mutation-shaped verbs terminate at preview text and required external authorization routes.

## Decision

Keep the closed 16-verb surface as intent previews under HCI-A. The surface is named `typed_command.v1`, with `writes_truth: false`, `dry_run_default: true`, and no execution path. Text and docs must call these verbs previews or intent previews, not authority actions.

## Consequences

The existing tested surface remains useful as an owner-facing preview vocabulary, while HCI-B submission remains deferred to a later owner-approved ADR. Any future implementation that makes a verb move truth violates this ADR and must fail the no-write gates.
