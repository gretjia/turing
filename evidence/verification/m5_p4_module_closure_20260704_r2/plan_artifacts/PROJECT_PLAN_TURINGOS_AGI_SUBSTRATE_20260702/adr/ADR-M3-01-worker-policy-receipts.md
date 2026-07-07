# ADR-M3-01 — Worker Policy: Receipts And Worker Identity

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
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/research/RES_M3_worker_uplift_laboratory.md
    sha256: b88c5298ee8733caa4959dca336dd320f65eaaf19351ccffd00653576118e8b6
  - path: /home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/modules/MODULE_M3_uplift_lab.md
    sha256: 370720e22721178ea782910f917d9e4566be8696766000a841fadbed3ac295da
status_ceiling: ADDRESSED
```

## Context

The M3 experiment is invalid unless every worker call records the worker identity, provider-echoed model, provider request ID, usage, request/response digests, integer micro-USD cost, wall-clock, and `cost_source_kind` on tape. Prior benchmark-adjacent predictions used prose-only identity such as `turingos-internal-rehearsal`, which leaves the substrate unable to reconstruct who did the work or what it cost.

## Decision

Every benchmark-adjacent LLM call must produce a receipt event conforming to the M1c-owned CostEvent.v2 seam and the M3 worker-call receipt fields. Prediction files must encode `model_name_or_path` as `worker__arm__experiment`, for example `deepseek-v4-flash__armB__uplift-v1`. API keys, authorization headers, org IDs, and secrets never appear on tape or in evidence bodies.

M1c has landed CostEvent.v2 and M3 consumes it verbatim. This ADR is accepted-addressed for M3.P1 freeze. No worker call may run until the frozen preregistration digest is independently ACKed and recorded on tape.

## Consequences

Runs without receipts are invalid and cannot be quoted. H-VPPUT and G5 get billing-grounded cost inputs. The worker adapter becomes a hard prerequisite before any arm execution.
