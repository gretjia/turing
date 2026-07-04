# M3 Worker Uplift Laboratory Preregistration

Status: FROZEN for M3.P1. This packet is not a worker-call authorization.

Frozen at: 2026-07-03T00:00:00Z. The freeze is valid only together with `M3_P1_FREEZE_RECORD.json`, `PREREGISTRATION.sha256`, the independent ACK artifact, and the digest tape event. Any roster, price, shard, analysis, budget, or hypothesis change requires a new preregistration before worker or pilot calls.

## Evidence Class

- `PREREGISTRATION.md`: frozen preregistration packet.
- `PRICE_TABLE.json`: frozen integer micro-USD provider price table, re-checked against official provider docs on 2026-07-03.
- `analysis/analyze_uplift.py`: frozen stdlib-only analysis script.
- `analysis/dryrun_fixture/`: FIXTURE synthetic harness-shaped inputs and dry-run outputs.
- `M3_P1_INDEPENDENT_ACK.json`: independent verifier ACK required before worker calls.
- `M3_P1_DIGEST_TAPE_EVENT.json`: preregistration digest recorded on a SHA-256 Micro Tape event before worker calls.

## Hypotheses

- H1 primary: pooled across workers, `resolved(B) > resolved(A)`.
- H2 secondary: pooled across workers, `resolved(B) > resolved(C)`.
- Arm D is a manipulation check only: any resolved task in deterministic floor output is STOP plus root cause.
- Tests are two-sided exact McNemar tests over paired worker-task outcomes. H1 is tested at alpha 0.025; H2 is tested at alpha 0.05 only if H1 passes. Effect sizes are deltas with 10,000-replicate cluster-by-task bootstrap 95% CIs.

## Arms

- A: weak worker alone, capsule-only, no checkout, no TuringOS loop, no failure memory.
- B: full TuringOS loop with worker-safe capsule and failure-memory broadcast rules enabled.
- C: same as B except failure-memory injection disabled. The ablation-honesty audit must show the only B-vs-C capsule delta is the broadcast-rules section.
- D: deterministic fake floor through the full B pipeline. It runs first.

## Frozen Confirmatory Shard

S01 is the confirmatory shard.

- Manifest path: `/home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_verified_500_campaign_20260629/shards/S01/shard_manifest.json`
- Manifest sha256: `68261be554042a3ca38454211d98014fc305b77ebff200414d9bb3d0e7c3a3ec`
- Dataset descriptor path: `/home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_verified_500_campaign_20260629/dataset_descriptor.json`
- Dataset descriptor sha256: `8dde6fef97ef978d5e973a6c3e75cd46f464b5681e85e6b8f7b86edeb269d1e2`
- Source dataset digest: `sha256:43ed5a3d1d98da36472c1ade65ddd2085d7b4ff694fcaf6a023a07c5c1f32f21`
- Source dataset repo sha: `91aa3ed51b709be6457e12d00300a6a596d4c6a3`

S01 task order is manifest order:

1. `scikit-learn__scikit-learn-11578`
2. `sphinx-doc__sphinx-10614`
3. `sympy__sympy-12489`
4. `astropy__astropy-13579`
5. `django__django-10999`
6. `matplotlib__matplotlib-20859`
7. `psf__requests-2931`
8. `pydata__xarray-3993`
9. `pylint-dev__pylint-6528`
10. `pytest-dev__pytest-5787`
11. `scikit-learn__scikit-learn-12585`
12. `sphinx-doc__sphinx-10673`
13. `sympy__sympy-13031`
14. `astropy__astropy-13977`
15. `django__django-11066`
16. `matplotlib__matplotlib-21568`
17. `psf__requests-5414`
18. `pydata__xarray-4075`
19. `pylint-dev__pylint-6903`
20. `pytest-dev__pytest-5809`
21. `scikit-learn__scikit-learn-12682`
22. `sphinx-doc__sphinx-11445`
23. `sympy__sympy-13091`
24. `astropy__astropy-14096`
25. `django__django-11087`
26. `matplotlib__matplotlib-22719`
27. `psf__requests-6028`
28. `pydata__xarray-4094`
29. `pylint-dev__pylint-7080`
30. `pytest-dev__pytest-5840`
31. `scikit-learn__scikit-learn-12973`
32. `sphinx-doc__sphinx-11510`
33. `sympy__sympy-13372`
34. `astropy__astropy-14182`
35. `django__django-11095`
36. `matplotlib__matplotlib-22865`
37. `pydata__xarray-4356`
38. `pylint-dev__pylint-7277`
39. `pytest-dev__pytest-6197`
40. `scikit-learn__scikit-learn-13124`
41. `sphinx-doc__sphinx-7440`
42. `sympy__sympy-13480`
43. `astropy__astropy-14309`
44. `django__django-11099`
45. `matplotlib__matplotlib-22871`
46. `pydata__xarray-4629`
47. `pylint-dev__pylint-8898`
48. `pytest-dev__pytest-6202`
49. `scikit-learn__scikit-learn-13135`
50. `sphinx-doc__sphinx-7454`

## Pilot Calibration Shard

S02 is reserved for the deterministic 10-task arm-A pilot.

- Manifest path: `/home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_verified_500_campaign_20260629/shards/S02/shard_manifest.json`
- Manifest sha256: `e708a512648808da37b30626b7f00f9913769621b6c078fb700e9127f5eee01e`

Pilot task order is the first 10 S02 manifest entries:

1. `sympy__sympy-13551`
2. `astropy__astropy-14365`
3. `django__django-11119`
4. `matplotlib__matplotlib-23299`
5. `pydata__xarray-4687`
6. `pytest-dev__pytest-7205`
7. `scikit-learn__scikit-learn-13142`
8. `sphinx-doc__sphinx-7462`
9. `sympy__sympy-13615`
10. `astropy__astropy-14369`

Each worker must land in the 15-45% arm-A baseline band on these 10 tasks or be replaced under this logged rule before S01 is touched. Pilot results are excluded from confirmatory analysis.

## Frozen Roster And Canary Rule

The frozen roster is:

- `deepseek-v4-flash`, non-thinking mode, provider `deepseek`, required.
- `gpt-5.4-nano-2026-03-17`, provider `openai`, required.
- `claude-haiku-4-5-20251001`, provider `anthropic`, optional third family.

The price table is `PRICE_TABLE.json`. Provider-echoed model strings are not inferred from docs. The first execution step for M3.P4 must perform a canary call for each included worker before the S02 pilot. If `model_reported` differs from the frozen model ID or documented alias relationship, the worker is not allowed to run S02/S01 until an independent verifier records a restart, replacement, or re-registration disposition. `deepseek-chat` and `deepseek-reasoner` are forbidden aliases.

## Budgets

Use the frozen loop budget profile from:

- `/home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_phase_g_verified_500_manifest_20260628/loop_manifest.json`
- sha256 `d7df2b48e5eb0de72c9e9e1a99751218ce045c9df5e0825dc2d5d9f6a3220922`

Per instance:

- Max attempts: 5.
- Max tokens: 400000.
- Max wall seconds: 7200.

Program ceiling:

- Max total tokens: 200000000.
- Max total wall seconds: 3600000.
- Retry max: 5.
- Budget terminal event: `BudgetExhausted`.

Budgets are identical across arms. Actual provider usage and computed integer micro-USD costs are reported from receipts.

## Receipts

Every live LLM call must append a `turingos.worker_call_receipt.v1` event carried inside or alongside the M1c-owned CostEvent.v2 schema. Minimum fields: arm, instance ID, attempt, provider, endpoint base URL, requested model, provider-reported model, provider request ID, request/response sha256, verbatim provider usage, final price-table digest, integer micro-USD cost, `cost_source_kind`, wall-clock ms, and timestamp.

Live calls use `cost_source_kind: provider_receipt_inline`. Fixture calls use `cost_source_kind: fixture`. `cost_source_kind: unspecified` and floating-point monetary values are invalid.

Secrets, API keys, Authorization headers, org IDs, payment identifiers, and raw provider debug logs must never appear on tape or in evidence bodies.

## Scoring

Only upstream `swebench==4.1.0` Docker harness outputs decide `resolved`.

- Qualified harness evidence: `/home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_official_harness_qualification_20260629/phase_f_20_run/evaluation_results.json`
- Qualified result sha256: `259c12e0d06cd9094d6fdc5fa3ddeb970a280989f347f90572a8a874c2b529b4`
- Dataset name to pin at run time: one of the two known aliases, selected only after digest assertion against `sha256:43ed5a3d1d98da36472c1ade65ddd2085d7b4ff694fcaf6a023a07c5c1f32f21`.
- Required flags: `--split test`, `--max_workers 2`, `--timeout 1800`, `--cache_level env`, default `swebench` namespace.

Repo-local evaluators are advisory-only and never feed analysis inputs.

## Rerun And Exclusion Policy

Each prediction is scored once. Rerun only upstream harness `error_ids` and `incomplete_ids`, at most twice, with single-instance commands logged. Persistent harness errors are excluded pairwise across all arms before analysis. `resolved` and `unresolved` outcomes are never re-rolled. Pairwise exclusions above 10% trigger abort-and-restart under a new preregistration.

## Worker-Safe Packets And Leakage

Packets must be materialized by the audited tool only after asserting the dataset digest. The supervisor must not open raw dataset rows. Leakage audit and gold-patch guard must PASS before any worker call. Gold patches enter only inside the upstream harness after predictions are frozen.

## Analysis

Use only `analysis/analyze_uplift.py` over upstream harness `evaluation_results.json` files. The script is stdlib-only and writes `UPLIFT_REPORT.json` and `UPLIFT_REPORT.md`. The synthetic dry-run fixture is labeled FIXTURE and has no performance meaning.

MDE statement to report verbatim: one worker on 50 paired tasks has roughly 15-23 percentage point MDE depending on harm rate; pooling 2-3 workers targets roughly 6-14 percentage points before task-clustering inflation. A null or negative result is a valid measurement.

## Stop Conditions

- Arm D resolves any task.
- Dataset digest assertion fails.
- Leakage audit or gold-patch guard fails.
- Model reported string changes without verifier disposition.
- More than 10% pairwise exclusions would be required.
- Budget ceiling is reached.
- Receipt schema or cost provenance is unavailable.
- A required canary call cannot record `provider_receipt_inline` cost provenance.

## Claim Boundary

This experiment measures differential uplift only. Absolute solve rates are not capability claims. "TuringOS improves workers" is forbidden unless H1 passes with positive direction under the preregistered rule. A null or negative result remains a valid M3 measurement.

## Freeze Checklist

1. Official provider prices were rechecked on 2026-07-03 and pinned in `PRICE_TABLE.json`.
2. M1c CostEvent.v2 is landed and the receipt fields conform to the M1c-owned schema.
3. S01/S02 manifests, dataset descriptor, loop manifest, ADR-M3-01..05, price table, and analysis script are hash-locked in `M3_P1_FREEZE_RECORD.json`.
4. The fixture dry-run output is included and labeled FIXTURE.
5. `PREREGISTRATION.sha256` is the sha256 of `M3_P1_FREEZE_RECORD.json`.
6. Independent verifier ACK is recorded before any worker call.
7. The preregistration digest is recorded on a SHA-256 Micro Tape event before any worker call.
