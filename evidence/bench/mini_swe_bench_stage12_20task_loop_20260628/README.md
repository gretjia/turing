# Stage12 20-Task Loop-Until-PASS Release Packet

Scope: Stage12 20-task scale/protocol evidence for the TuringOS SWE-bench pipeline.

This evidence root now contains both the original A01/A02 frozen contract files and the A03 generated release evidence. The release evidence includes 20 fresh MicroTape bundles, refreshed after official evaluator import, plus strict MicroTape and Stage12 release audits. Stage12 remains a scale/protocol gate: it is not statistically powered, makes no product superiority claim, makes no full SWE-bench score claim, and does not upgrade external CLI worker provenance to FULL.

Stage12-A03 used the frozen task list from `tasks_20.jsonl`, the runner command with `--stage12-real-loop`, and the evaluator command with `--stage12-loop-until-pass`. The test-scope authority bridge is selected only by `--authority-provider test-local` together with `--authorization-mode required`; it directly appends benchmark-scope AUTHORIZATION events to MicroTape and does not loosen production `turingd` approval RPCs, which still require OsKeyring.

`audit_stage12_release.py` is the local Stage12 release gate. It recomputes strict MicroTape audit from the same coverage bundle paths, compares supplied strict-audit bundle hashes against recomputed hashes, rejects relabeled fixture payload markers inside bundles, and rejects fewer-than-20, manual-intervention, or non-PASS strict evidence.

## Source

- Source dataset: `/tmp/turingos-swebench-data/verified-mini-50.jsonl`
- Source dataset digest: `sha256:cafe0f03f7f6db133e98ad259f3a1cd0c6a59dce6965ddcb6e220df8b376ba5d`
- Selection policy: first 20 rows from the frozen source before any Stage12 run
- Original Stage12 plan base commit SHA: `38bae9971863db9196643084a926a7590c157cce`

## Release Result

- Local Stage12 release audit: `PASS`
- Run count: `20`
- Solved count: `13`
- Unsolved / budget-terminal count: `7`
- Strict MicroTape audit: `PASS`
- Authorization head: `PASS`
- VPPUT accounting: `PASS`
- Terminal market / reward accounting: `PASS`
- Constitutional protocol audit: `PASS`

See `strict_audit_summary.md`, `stage12_release_audit.json`, and `micro_tape_audit_strict/micro_tape_decision_dag_audit.json` for exact machine-readable evidence.

## Key Files

- `task_manifest.json`
- `loop_manifest.json`
- `tasks_20.jsonl`
- `stage12_run_plan.json`
- `substrate_coverage.json`
- `bundle_sha256s.txt`
- `stage12_release_audit.json`
- `micro_tape_audit_strict/micro_tape_decision_dag_audit.json`
- `strict_audit_summary.md`
- `external_auditor_prompt_stage12.md`
- `instances/<instance>/micro_tape.bundle`

## Reproduction Commands

Run these commands from the repository root.

```bash
python3 -m py_compile \
  tools/bench/audit_micro_tape_decision_dag.py \
  tools/bench/audit_stage12_release.py

python3 tools/bench/audit_micro_tape_decision_dag.py \
  --strict-vpput \
  --strict-terminal-market \
  --require-authorization-head \
  --coverage evidence/bench/mini_swe_bench_stage12_20task_loop_20260628/substrate_coverage.json \
  --out-dir /tmp/turingos_stage12_external_strict_audit

python3 tools/bench/audit_stage12_release.py \
  --root evidence/bench/mini_swe_bench_stage12_20task_loop_20260628 \
  --coverage evidence/bench/mini_swe_bench_stage12_20task_loop_20260628/substrate_coverage.json \
  --strict-audit /tmp/turingos_stage12_external_strict_audit/micro_tape_decision_dag_audit.json \
  --out /tmp/turingos_stage12_external_release_audit.json
```

Expected release audit result: `PASS`, `run_count=20`, `solved_count=13`, `unsolved_count=7`, `problems=[]`.

## Historical A01/A02 Files

The original pre-run contract files remain in this root for provenance: `stage12_a02_report.json`, `independent_recursive_audit.md`, and `independent_recursive_audit_stage12_a02.md`. They document the frozen manifest and pre-run command plan. They are not the current post-run release gate; use the reproduction commands above and `external_auditor_prompt_stage12.md` for release review.
