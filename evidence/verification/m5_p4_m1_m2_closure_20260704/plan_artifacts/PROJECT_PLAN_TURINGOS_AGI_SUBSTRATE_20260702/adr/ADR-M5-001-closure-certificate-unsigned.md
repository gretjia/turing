# ADR-M5-001 - ClosureCertificate.v1 Unsigned JSON and Anchoring

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
status_ceiling: ADDRESSED
```

## Context

G6 requires a certificate issued by a custody-separated verifier, while the program red line keeps private keys off this host. RES_M5 section 2.1 records the F1 failure mode: same-session "independent" audits existed, but no external verdict artifact or certificate schema existed.

## Decision

Use `turingos.closure_certificate.v1` as plain JSON: subject block, verifier identity, six mandatory custody booleans, commands with literal exit codes, closed verdict enum `{PASS, FAIL}`, and `status_semantics.implementer_ceiling: ADDRESSED`. The certificate is created in verifier custody and anchored by recording its sha256 through an implementer-independent channel before any in-repo mirror. The attestation shape follows subject-digest binding so a future verifier-side signed upgrade is field-preserving, but no signing key is generated or stored on this host.

## Consequences

Implementer self-issuance is schema-invalid instead of merely forbidden. Authenticity rests on custody plus anchoring for this increment, with residual risk versus cryptographic signatures recorded here. Validation is `sha256sum` plus a stdlib script.
