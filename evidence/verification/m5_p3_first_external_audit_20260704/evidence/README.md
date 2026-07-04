# Official SWE-bench Harness Qualification

Status: PASS for Phase G official campaign launch readiness.

This packet proves the upstream SWE-bench Docker harness can run in this
environment and records the full Phase F 20-task official replay. The replay
initially completed without harness errors but resolved 19/20 tasks. The repair
loop then generated a fresh worker-derived patch for `django__django-11885` and
reran the full 20-task upstream SWE-bench Docker replay. The repaired replay
resolved 20/20 tasks with zero harness errors.

## Evidence

- Docker daemon available.
- `swebench` package installed locally in `.venv_swebench`, version recorded as
  4.1.0.
- `python -m swebench.harness.run_evaluation --help` recorded.
- A single-instance upstream harness probe ran:
  `django__django-11790`.
- The probe resolved the task and recorded FAIL_TO_PASS and PASS_TO_PASS.
- The initial Phase F 20-task upstream harness replay ran with:
  - submitted: 20
  - completed: 20
  - resolved: 19
  - unresolved: 1
  - errors: 0
- The unresolved target was `django__django-11885`.
- The repaired single-target probe resolved `django__django-11885`.
- The repaired full Phase F 20-task upstream harness replay ran with:
  - submitted: 20
  - completed: 20
  - resolved: 20
  - unresolved: 0
  - errors: 0
- Initial blocked replay evidence is bound under `phase_f_20_run/`.
- Repair evidence is bound under `phase_f_11885_repair/`.
- Repaired full replay evidence is bound under `phase_f_20_repaired_run/`.

## Blocking Gap

`official_harness_qualification_audit.json` is `PASS` because the repaired full
Phase F 20-task upstream Docker replay resolved all 20 targets.

```text
blockers: []
phase_f_resolved_count: 20
phase_f_unresolved_ids: []
required_next_action: regenerate_full_readiness_audit_with_official_harness_identity
release_next_phase_g: true
```

The old 19/20 replay remains preserved as historical blocker evidence. The
repair supersedes it; it does not rewrite old Stage16/Stage16R/Phase F
MicroTape or evaluator evidence.

## Claim Boundary

This is not a full SWE-bench campaign, not a full-score claim, and not
leaderboard-equivalent evidence.
