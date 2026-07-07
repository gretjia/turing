# M4 North-Star Report

## Headline

- Run-class breakdown: 150 BILLING_COMPLETE / 0 BOUNDED / 0 INADMISSIBLE.
- Per-arm portfolio H-VPPUT: A: 0.000236136; B: 0.000401378; C: 0.000669797.
- Δ_BC with CI: 0.0 [-0.10, 0.10]; p=1.0; blocked_by_h1=true.
- MDE statement: Pre-registered design is powered for large effects: one worker on 50 paired tasks has roughly 15-23 percentage point MDE depending on harm rate; pooling 2-3 workers targets roughly 6-14 percentage points before task-clustering inflation.

## Mandatory Direction Sentence

Δ_BC = 0.0 [CI includes 0]; the study was powered for MDE = Pre-registered design is powered for large effects: one worker on 50 paired tasks has roughly 15-23 percentage point MDE depending on harm rate; pooling 2-3 workers targets roughly 6-14 percentage points before task-clustering inflation; smaller true effects are not excluded. No failure-memory efficacy claim is made.

Skeleton record retained from the frozen template:

- Positive: Δ_BC = x [CI a,b], H2 passed at pre-registered α; failure-memory contribution is supported at this scale.
- Null: Δ_BC = x [CI includes 0]; the study was powered for MDE = y; smaller true effects are not excluded. No failure-memory efficacy claim is made.
- Negative: same as null plus "the point estimate is negative; a harm hypothesis was not pre-registered and is flagged for a future pre-registered study."

## Cost Provenance

| Arm | Run class | H-VPPUT field | Cost provenance note |
|---|---|---|---|
| A | BILLING_COMPLETE | 0.000236136 | 50 provider_receipt_inline DeepSeek usage receipts; CostEvent.v2 aggregate-ceiling recomputation; conservation reconciliation PASS. |
| B | BILLING_COMPLETE | 0.000401378 | 50 provider_receipt_inline DeepSeek usage receipts; CostEvent.v2 aggregate-ceiling recomputation; conservation reconciliation PASS. |
| C | BILLING_COMPLETE | 0.000669797 | 50 provider_receipt_inline DeepSeek usage receipts; CostEvent.v2 aggregate-ceiling recomputation; conservation reconciliation PASS. |

## Exclusion Table

| Run or task | Reason | Event refs |
|---|---|---|
| <none> | <none> | <none> |

## Deviation Table

| Deviation | Source | Disposition |
|---|---|---|
| Deterministic CostEvent.v2 aggregate-ceiling metric correction | `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/m4_self_improvement/M4_P1_METRIC_CORRECTION_RECORD.json` | Recorded in M4.P1 correction record; original freeze remains preserved; correction is receipt-shape-driven, not outcome-driven. |
| Legacy lifecycle auditors not applicable to M3 DeepSeek continuation | `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/m4_self_improvement/real_s01_deepseek_20260703/audits/legacy_lifecycle_auditors_not_applicable.json` | Recorded deviation; artifact-level substitute audit only; no external verification claim. |

## Claim Boundary

`/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/m4_self_improvement/real_s01_deepseek_20260703/CLAIM_BOUNDARY.json` sha256 `7192b99ca6d6494d27e755c48730b209a108b6ee80a848c063522f81eb03452f`.

H-VPPUT is a measurement-validity projection, not an absolute capability claim.
