# ADR-M5-003 - Exact-SHA Release Packet

```yaml
status: accepted-addressed
decision-makers:
  - Codex orchestrator
date: 2026-07-03
authority_level: 4
constitution_articles:
  - Art. 0.3 Auditability
  - Art. III.4 Goodhart shielding
evidence:
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/research/RES_M5_independent_verification.md
    sha256: 8893bd16ab7e881faf024b83c8ec11b4c552687fe8122f4bec1a967add79e869
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/modules/MODULE_M5_independent_verification.md
    sha256: 041a3bfd4875fcdf9dc200106bb14b4cd2e127c1c35ed3b8cde6d4580a096b43
status_ceiling: ADDRESSED
```

## Context

Existing evidence roots carry partial manifests but do not provide a closed outsider-reexecution packet. FCE already names a packet builder CLI shape.

## Decision

A `turingos.release_packet.v1` packet contains `PACKET_MANIFEST.json`, sorted `MANIFEST.sha256` closure over every packet file, repo and tape bundles or pinned clone material, the gate's declared artifact list, `REEXECUTION.md`, `CLAIM_BOUNDARY.json`, and the auditor runbook. The builder writes the manifest last, self-tests clean/tamper discrimination, accepts `--root` and `--sha`, prints `packet_sha256`, copies from evidence roots, and never modifies source evidence. Repairs produce new packets at new SHAs.

## Consequences

Audits become re-executions over digest-bound packets rather than prose reviews. Packet completeness becomes mechanically checkable. FCE can consume the same builder surface.
