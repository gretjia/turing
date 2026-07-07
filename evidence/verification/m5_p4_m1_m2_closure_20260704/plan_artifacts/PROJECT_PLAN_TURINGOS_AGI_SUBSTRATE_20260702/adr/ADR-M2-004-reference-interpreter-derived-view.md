# ADR-M2-004 - Reference Interpreter as Derived View

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
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/modules/MODULE_M2_tc_witness.md
    sha256: d9c0f93c47917f2fcc9b88ab2e0dd2f9118290ba63418aa008a328e1932fa631
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/research/RES_M2_turing_completeness_witness.md
    sha256: 1fa2c9c676c00e3f11c48cef4d98a1c55a1a888b77f3ffa4788afa9932a28713
  - path: /home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_verified_500_campaign_20260629/TURING_COMPLETENESS_PROOF_OBLIGATIONS_20260629.md
    sha256: 7be0980ee1a3ddf157f65096180c836341da548debcc93fe6957f355a7cf7cae
status_ceiling: ADDRESSED
```

## Context

TC gates require replay to equal an independent reference interpreter. A reference that writes tapes or shares production code would create another canonical owner and weaken the independence claim.

## Decision

The Python reference interpreter lives under `tools/theory/`, stays small and stdlib-only, and is a derived-view checker only. It emits state-hash traces for comparison and never appends to a tape. The mandatory DECJZ test checks that zero jumps without decrement and nonzero decrements before jumping.

## Consequences

TC1 must include a lint proving `tools/theory/` contains no tape append calls. Differential equality compares full traces, not only final states.
