# ADR-M6-001 - Adopt HCI-A Projection Route

```yaml
status: accepted-addressed
decision-makers:
  - owner
date: 2026-07-03
authority_level: 4
constitution_articles:
  - Art. 0.2 Tape Canonical
  - Art. 0.3 Auditability
  - Art. III.4 Goodhart shielding
evidence:
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/research/RES_M6_hci_projection_console.md
    sha256: 55b138db6ab341252223d250b056a3915f8f963b2ae1f5f19eafcdee9e20813d
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/modules/MODULE_M6_hci_console.md
    sha256: 58e07e8453d4ee69db7df785da82d479da009a7910a07cf3d75a73a1ce13c763
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/01_PROJECT_INTENT.md
    sha256: 5d1b923dcd358da12dad701d54f5bf5485f4d906be41a17ff3509caf03c15c3a
  - path: /home/zephryj/turingos_backup/work/TURINGOS_RETROSPECTIVE_AUDIT_FINDINGS_20260702.md
    sha256: c4eb450454b984af9c8f99cfb294e9a2fa536853f6f37c6237e3cc07c594eea7
status_ceiling: ADDRESSED
```

## Context

M6 exists to repair audit finding F6: an operator console branch was implemented before the HCI route was accepted. RES_M6 and MODULE_M6 recommend HCI-A with intent previews: the console projects and explains tape-derived state, but it is not an authority path and does not submit commands into truth.

The owner route decision is reserved by the tracker. Owner acceptance was recorded by zephryj on 2026-07-04 for the HCI-A projection-only route.

This acceptance does not change constitution bytes, does not provide a genesis/OG-10 signature, does not enable M2, does not authorize HCI-B, and does not authorize any write-capable console behavior.

## Decision

Adopt HCI-A as the projection-only route for this program increment. The console may render MicroTape-derived state and preview intent-shaped verbs, but `can_write_truth` and `writes_truth` remain schema constants false.

HCI-B is deferred. It may be reopened only after the M1 canonical-writer/authorization question is closed by the relevant gate, the M2 TC witness is independently audited, the M5 external ClosureCertificate machinery is live, and a new owner-approved ADR routes submissions through the same authority path as every other proposer.

HCI-C is forbidden for this increment.

## Consequences

The project can preserve and audit the existing console work without granting it authority. The accepted route keeps operator visibility separate from authorization and sovereign acceptance, and unblocks M6.P2 at the HCI-A projection-only ceiling.
