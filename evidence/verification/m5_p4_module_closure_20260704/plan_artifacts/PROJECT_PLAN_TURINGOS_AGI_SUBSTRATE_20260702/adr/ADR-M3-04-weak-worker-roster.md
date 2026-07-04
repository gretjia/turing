# ADR-M3-04 — Weak-Worker Roster And Calibration

```yaml
status: accepted-addressed
decision-makers:
  - orchestrator
date: 2026-07-02
authority_level: 4
constitution_articles:
  - Art. 0.2 Tape Canonical
  - Art. III.4 Goodhart shielding
evidence:
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/m3_uplift_lab/PRICE_TABLE.json
    sha256: c2583e5120cbbaf2b06179e865f19ea5d466e7ed2ecb760244007c48538d5791
status_ceiling: ADDRESSED
```

## Context

The point of M3 is to measure substrate uplift, not frontier-worker capability. The roster must be weak enough to leave headroom, cheap enough to keep total spend bounded, provider-heterogeneous, and API-stable.

## Decision

Frozen roster: `deepseek-v4-flash` in non-thinking mode, `gpt-5.4-nano-2026-03-17` as the OpenAI nano-class worker, and optional `claude-haiku-4-5-20251001`. Each worker must be calibrated on the first 10 S02 manifest-order tasks in arm A. Workers outside the 15-45% baseline band are replaced under the logged rule before S01 is touched.

Prices and model IDs were re-verified from official provider docs on 2026-07-03 and pinned in the frozen price table. Any roster change after freeze forces re-registration.

## Consequences

Provider drift is detectable through `model_requested` and `model_reported`. Absolute solve rates remain contaminated-benchmark numbers and are not capability claims.
