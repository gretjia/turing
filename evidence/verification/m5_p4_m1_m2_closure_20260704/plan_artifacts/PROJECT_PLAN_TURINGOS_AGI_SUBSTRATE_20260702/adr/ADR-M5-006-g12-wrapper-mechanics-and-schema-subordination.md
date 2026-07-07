# ADR-M5-006 - G12 Mechanics Reuse and Schema Subordination

```yaml
status: accepted-addressed
decision-makers:
  - Codex orchestrator
date: 2026-07-03
authority_level: 4
constitution_articles:
  - Art. 0.3 Auditability
  - Intent section 5 private-key red line
evidence:
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/research/RES_M5_independent_verification.md
    sha256: 8893bd16ab7e881faf024b83c8ec11b4c552687fe8122f4bec1a967add79e869
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/modules/MODULE_M5_independent_verification.md
    sha256: 041a3bfd4875fcdf9dc200106bb14b4cd2e127c1c35ed3b8cde6d4580a096b43
  - path: /home/zephryj/turingos_backup/work/TOP_ALIGNMENT_PROJECT_BOOK.md
    sha256: 927544a1444c4571a04f1b6bcca36a7ce92a43f9d5575c8ae3668765ef6a0cae
  - path: /home/zephryj/turingos_backup/work/turing/tools/headless/grok_verify.py
    sha256: be5b11fbbf09036efc71c8ab4c3c362abb3cab2fc7098afa4915013461730a83
  - path: /home/zephryj/turingos_backup/work/turing/tools/headless/claude_final_ratify.py
    sha256: 095fb9f580de6af4ac5cbd73ee862d42b477bd4081336ee7384da3b1437b5d54
  - path: /home/zephryj/turingos_backup/work/turing/tools/headless/headless_common.py
    sha256: a1e935adb12d0c0a6cb6ea3d5eaa6ec4b44a03ac5552a2287b9badeeb4ce95a5
status_ceiling: ADDRESSED
```

## Context

G12-A/G12-B wrappers already provide useful clean-clone, forbidden-claims, digest-capture, and clean/tampered fixture mechanics. They are still invoked by the implementer program on this host and therefore fail closure custody. The top alignment book also specifies an omega-track signed ClosureCertificate whose private key lives in verifier custody.

## Decision

Lift the G12 wrapper mechanics into M5 tooling and packet `REEXECUTION.md`, but never import their locally invoked authority. Locally run wrappers confer nothing above ADDRESSED-confidence. Verifier-side Ed25519 signing is the recorded v1.1 upgrade path only after the owner provisions a verifier key channel; keys are generated and held on the verifier machine, and this host uses public material only. Keep the plan certificate and omega-track signed certificate disjoint by `schema_id`, and flag the pair through M0/G1 subordination rather than silently merging them.

## Consequences

No wrapper rewrite is needed, no local key is introduced, and no authority leaks from G12 into M5. The omega-track stronger custody design remains reachable without invalidating unsigned certificates already issued.
