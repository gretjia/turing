# ADR-M5-002 - Custody Separation Properties

```yaml
status: accepted-addressed
decision-makers:
  - Codex orchestrator
date: 2026-07-03
authority_level: 4
constitution_articles:
  - Art. 0.3 Auditability
  - Intent section 2 G6
evidence:
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/research/RES_M5_independent_verification.md
    sha256: 8893bd16ab7e881faf024b83c8ec11b4c552687fe8122f4bec1a967add79e869
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/modules/MODULE_M5_independent_verification.md
    sha256: 041a3bfd4875fcdf9dc200106bb14b4cd2e127c1c35ed3b8cde6d4580a096b43
status_ceiling: ADDRESSED
```

## Context

Audit R5 demands an operator and environment with no shared session state. The F1 pattern satisfied an ambiguous "independent" label while preserving implementer custody and context.

## Decision

External verification requires all six custody booleans: fresh clone from the packet, no shared conversation state, no implementer transcript, own credentials, cross-family-or-human verifier, and verifier-custody output with prior anchoring. Tier E1, a different human operator, is required for the first external audit and final certification. Tier E2, an owner-provisioned cross-family account, is acceptable for module closures. Internal fresh-context agents remain phase-level confidence tools and can never issue a ClosureCertificate.

## Consequences

Externality becomes testable at validation time. The owner-provided auditor channel remains an explicit dependency. Same-program subagents and locally invoked verifier wrappers stay below closure authority.
