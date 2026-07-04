# ADR-M5-005 - Release Eligibility Gate and Disjunction Ban

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
  - path: /home/zephryj/turingos_backup/work/turing/docs/handoff/STAGE12_TO_STAGE16_RECURSIVE_AUDIT_PLAN.md
    sha256: 7f6466c5a98fd2e000e23f425e32806213600ac3d987396fdbacd15a18a9de6f
status_ceiling: ADDRESSED
```

## Context

The G6 KPI requires mechanical impossibility of release without an external artifact. RES_M5 identifies the prior release-boundary hatch as the literal phrase `external or designated independent`.

## Decision

Only `assert_release_eligible.sh` may produce `RELEASE_ELIGIBLE.json`, and it must require a validating certificate, subject digest match, PASS verdict, complete custody, identity disjointness, and anchoring. Implementer-written lifecycle claims without that artifact are defects. The ClosureCertificate validator permanently rejects the disjunctive hatch class, including the literal phrase `external or designated independent`.

## Consequences

The negative test is part of the gate, not documentation. The F1 hatch class cannot silently return because it is in the validator corpus forever. Release attempts leave machine-readable acceptance or refusal evidence.
