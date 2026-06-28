# Stage13 Independent Recursive Audit

Auditor: Zeno, independent sub-agent

Date: 2026-06-28

Scope: local Stage13 evidence root before commit/push:

`evidence/bench/mini_swe_bench_stage13_native_api_worker_hardening_20260628/`

## Verdict

PASS for Stage13 Native API Worker receipt hardening evidence.

No Stage13 evidence blocker was found. This verdict is scoped to receipt hardening and does not claim solve-rate, statistical superiority, full SWE-bench score, or FULL provenance for external CLI workers.

## Checks

- Strict MicroTape audit: PASS, all status fields PASS, `strict_findings: []`.
- `native_api_worker_audit.json`: PASS.
- `tool_receipt_conservation_audit.json`: PASS.
- `prompt_leakage_audit.json`: PASS.
- Regenerated all four audit reports from local tools; regenerated JSON matched the checked-in artifacts.
- Bundle SHA-256 digests matched `bundle_sha256s.txt`:
  - `0044db5afb946f22eaa5b8c713152aaac16ecf80fc15b6bb6fc38e2ca5e02b47`
  - `9f64731b45c18a5bb04f983d7484fbdfe91c7fb34abdb3283b853adb011d7ce5`
- Credential-shaped secret scan over all Stage13 files, including bundle bytes: `credential_pattern_hits=0`.
- Claim boundary is scoped to Stage13 only in `README.md` and `external_auditor_prompt_stage13.md`.
- No solve-rate or full-score overclaim found; matching text is used as explicit disclaimer language.

## Commands Reported By Auditor

```bash
sha256sum evidence/bench/mini_swe_bench_stage13_native_api_worker_hardening_20260628/turingos/instances/django__django-12039/micro_tape.bundle \
  evidence/bench/mini_swe_bench_stage13_native_api_worker_hardening_20260628/turingos/instances/django__django-12050/micro_tape.bundle

jq checks over strict/native/tool/prompt audit JSONs

python regeneration of strict MicroTape/native/tool/prompt audits plus credential-pattern scan

rg -n -i -a "solve-rate|full-score|..." evidence/bench/mini_swe_bench_stage13_native_api_worker_hardening_20260628

cmp -s bundle_manifest.json worker_manifest.json

cmp -s bundle_manifest.json turingos/substrate_coverage.json

pytest -q tests/test_stage13_native_api_hardening.py

git status --short
```

## Release Readiness

Stage13 can be committed and pushed for external exact-SHA audit.

Files that must be included:

- `evidence/bench/mini_swe_bench_stage13_native_api_worker_hardening_20260628/`
- `tools/bench/audit_prompt_leakage.py`
- `tools/bench/audit_tool_receipt_conservation.py`
- `tests/test_stage13_native_api_hardening.py`
- `tools/bench/run_mini_swe_bench_substrate_smoke.py`

