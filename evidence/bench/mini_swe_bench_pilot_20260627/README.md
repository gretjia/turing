# Mini SWE-bench Grok Pilot Evidence

This directory contains the independently verifiable artifacts for the 2026-06-27 two-task SWE-bench Verified Mini pilot.

Status: `PILOT_ONLY_NOT_STATISTICALLY_POWERED`

Requirement verdict: `FAIL_TURINGOS_NOT_SIGNIFICANTLY_AHEAD`

Official SWE-bench harness result:

- `direct_grok_baseline`: 1/2 resolved, 1 empty patch
- `turingos_grok_worker`: 1/2 resolved, 1 empty patch
- paired McNemar exact p-value: 1.0

Hygiene-guarded result:

- `direct_grok_baseline`: 0/2 valid resolved, because the resolved patch modifies a test file
- `turingos_grok_worker`: 1/2 valid resolved, source-only patch
- paired McNemar exact p-value: 1.0

The hygiene result is a useful signal, but it is not statistically significant at this sample size.

Primary machine-readable summary:

- `pilot_result.json`

Reproducibility artifacts:

- `direct_grok_baseline.predictions.jsonl`
- `turingos_grok_worker.predictions.jsonl`
- `official_summary_direct_grok_baseline.json`
- `official_summary_turingos_grok_worker.json`
- `official_summary_gold_smoke.json`
- `official_report_direct_grok_baseline_django__django-11815.json`
- `official_report_turingos_grok_worker_django__django-11815.json`
- `patches/*.patch.diff`

The exact verification commands used for the pilot are recorded in `pilot_result.json` under `independent_verify_commands`.
