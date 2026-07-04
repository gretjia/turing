# ADR-M2-003 - Universality Argument and Claim Boundary

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
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/modules/MODULE_M2_tc_witness.md
    sha256: d9c0f93c47917f2fcc9b88ab2e0dd2f9118290ba63418aa008a328e1932fa631
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/research/RES_M2_turing_completeness_witness.md
    sha256: 1fa2c9c676c00e3f11c48cef4d98a1c55a1a888b77f3ffa4788afa9932a28713
  - path: /home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_verified_500_campaign_20260629/TURING_COMPLETENESS_PROOF_OBLIGATIONS_20260629.md
    sha256: 7be0980ee1a3ddf157f65096180c836341da548debcc93fe6957f355a7cf7cae
status_ceiling: ADDRESSED
```

## Context

G3 needs an executable computation witness, not a mechanized theorem. The obligations file permits a bounded claim only after TC gates pass, and RES_M2 requires an explicit distinction between empirical execution evidence and literature-backed machine-class universality.

## Decision

The TC evidence root will separate: interpreter correctness evidence, bounded witness executions, citational universality of the machine class, and the final substrate claim. Any future `THEORY.md` and `CLAIM_BOUNDARY.json` must state the Minsky/Godel-encoding caveat and must keep `turing_completeness_claim_allowed: false` until TC-10 external evidence exists.

## Consequences

TC0 and later implementer artifacts may say the witness machinery is being built or tested. They may not say the system is Turing-complete, proved complete, released, externally verified, or shipped.
