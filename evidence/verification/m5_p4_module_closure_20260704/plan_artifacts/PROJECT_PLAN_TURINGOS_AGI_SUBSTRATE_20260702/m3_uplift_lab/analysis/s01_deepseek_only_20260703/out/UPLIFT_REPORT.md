# M3 Uplift Analysis Report

- Evidence class: REAL_HARNESS_OUTPUTS
- Fixture: false
- Tasks: 50
- Workers: deepseek-v4-pro__same-provider-source-context-worker

## Confirmatory Tests

| Test | Delta | p | CI low | CI high | Holm reject |
|---|---:|---:|---:|---:|---|
| H1 B>A | 0.040000 | 0.726562 | -0.060000 | 0.160000 | False |
| H2 B>C | 0.000000 | 1.000000 | -0.100000 | 0.100000 | False |

## MDE Statement

Pre-registered design is powered for large effects: one worker on 50 paired tasks has roughly 15-23 percentage point MDE depending on harm rate; pooling 2-3 workers targets roughly 6-14 percentage points before task-clustering inflation.

## Claim Boundary

Absolute solve rates are not capability claims. Fixture outputs are not performance evidence.
