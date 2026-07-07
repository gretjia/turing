# M4 North-Star Report Skeleton

## Headline

- Run-class breakdown: `<n_billing_complete> BILLING_COMPLETE / <n_bounded> BOUNDED / <n_excluded> INADMISSIBLE`.
- Per-arm portfolio H-VPPUT or lower-bound H-VPPUT: `<transcribe from hvpput_report.v1.json>`.
- Δ_BC with CI: `<verbatim from M3 H2>`.
- MDE statement: `<verbatim from M3 pre-registration>`.

## Mandatory Direction Sentence

Use exactly one of the following templates and leave the unused templates in the skeleton record:

- Positive: Δ_BC = x [CI a,b], H2 passed at pre-registered α; failure-memory contribution is supported at this scale.
- Null: Δ_BC = x [CI includes 0]; the study was powered for MDE = y; smaller true effects are not excluded. No failure-memory efficacy claim is made.
- Negative: same as null plus "the point estimate is negative; a harm hypothesis was not pre-registered and is flagged for a future pre-registered study."

## Cost Provenance

| Arm | Run class | H-VPPUT field | Cost provenance note |
|---|---|---|---|
| A | `<BILLING_COMPLETE/BOUNDED/INADMISSIBLE>` | `<value or bound>` | `<receipt class summary>` |
| B | `<BILLING_COMPLETE/BOUNDED/INADMISSIBLE>` | `<value or bound>` | `<receipt class summary>` |
| C | `<BILLING_COMPLETE/BOUNDED/INADMISSIBLE>` | `<value or bound>` | `<receipt class summary>` |

## Exclusion Table

| Run or task | Reason | Event refs |
|---|---|---|
| `<none if empty>` | `<none if empty>` | `<none if empty>` |

## Deviation Table

| Deviation | Source | Disposition |
|---|---|---|
| `<none if empty>` | `<none if empty>` | `<none if empty>` |

## Claim Boundary

Fill `CLAIM_BOUNDARY.json` from `CLAIM_BOUNDARY.template.json`. H-VPPUT is a measurement-validity projection, not an absolute capability claim.
