# Full SWE-bench Loop Reflection

Date: 2026-06-28

## Reflection

The repeated audit failures were not primarily benchmark failures. They were
drift failures:

- treating local green tests as closure while external auditors checked category
  errors;
- turning useful PARTIAL evidence into broad PASS language;
- allowing fixture/protocol PASS to sound like real-world evaluator proof;
- letting repair-loop structure look like a Phase G release condition;
- importing official evaluator PASS evidence without enough executable
  evaluator artifacts for external replay;
- describing 20-task shard results with names that could be read as full
  SWE-bench results.

The correction is to keep every loop stop machine-readable and narrower than the
ambition. The ambition is an LLM-backed TuringOS that can keep computing,
reflecting, compressing failure, and retrying under MicroTape constraints for as
much time and budget as the operator grants. SWE-bench full score is a frontier
for improving the substrate, not the substrate itself.

## Updated Memory

Current truth:

```text
Phase F evaluator proof: PASS, executable official evaluator replay
Phase F repair loop: superseded by fresh Stage16R-real completed packet
Stage16R real evaluator loop: PASS, 7/7 repaired
SWE-bench Verified 500 manifest freeze: PASS
Full SWE-bench readiness: READY to start sealed Verified 500 campaign
Full SWE-bench campaign: NOT STARTED
Full SWE-bench score claim: FORBIDDEN
```

Next required action:

```text
Start the SWE-bench Verified 500 sharded sealed campaign.

Do not call readiness a result. Every task must still produce a MicroTape
bundle. Full-score remains forbidden until all 500 have official PASS,
CandidateAccepted, final PPUT progress=1, no-HITL counters zero, and exact-SHA
external audit release.
```

The Stage16R-real completed packet consolidates seven fresh worker-derived
repair bundles. `django__django-12209` uses an explicit evaluator target fallback
because the local `FAIL_TO_PASS` label is malformed; the evidence payload records
`target_selection_source=test_patch_module_fallback_after_label_import_failure`.
Old Stage16/Stage16R bundles remain immutable.

## Self-Improvement Rules

1. Write the release gate before expanding the benchmark.
2. Treat `BLOCKED`, `PARTIAL`, `WARN`, `LEGACY_MISSING`, and static-only audit as
   no-release states.
3. Do not collapse adjacent gates. Repair-loop PASS only permits rerunning Phase
   F evaluator proof; it never releases Phase G directly.
4. Do not let natural-language summaries become truth. The machine JSON verdict
   controls the next loop.
5. Do not use old fixture artifacts to prove executable official evaluator
   replay.
6. Do not freeze a full dataset manifest before Phase F evaluator proof can
   release the manifest-freeze loop.
7. Every future success claim must include exact SHA, GitHub evidence path,
   commands run, and the relevant audit JSON path.
