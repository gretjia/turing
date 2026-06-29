# Official SWE-bench Harness Qualification

Status: BLOCKED for Phase G official campaign release.

This packet proves the upstream SWE-bench Docker harness can run in this
environment for a single selected instance. It does not prove the full Phase F
20-task official replay and does not release Phase G.

## Evidence

- Docker daemon available.
- `swebench` package installed locally in `.venv_swebench`, version recorded as
  4.1.0.
- `python -m swebench.harness.run_evaluation --help` recorded.
- A single-instance upstream harness probe ran:
  `django__django-11790`.
- The probe resolved the task and recorded FAIL_TO_PASS and PASS_TO_PASS.

## Blocking Gap

`official_harness_qualification_audit.json` remains `BLOCKED` because the full
Phase F 20-task upstream Docker replay has not been run and bound as evidence.

## Claim Boundary

This is not a full SWE-bench campaign, not a full-score claim, and not
leaderboard-equivalent evidence.
