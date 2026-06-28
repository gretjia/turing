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
Phase F evaluator proof: PARTIAL
Phase F repair loop: BLOCKED
Full SWE-bench readiness: BLOCKED
Full SWE-bench campaign: NOT STARTED
Full SWE-bench score claim: FORBIDDEN
```

Next required action:

```text
Generate fresh Stage16R-real evaluator bundles for the 7 repair targets:
- django__django-11790
- django__django-11815
- django__django-11964
- django__django-12209
- django__django-12273
- django__django-12308
- django__django-12325
```

Those bundles must be worker-derived and must include unified candidate diffs,
official test patches, apply logs, official evaluator command, stdout/stderr
digests, environment/harness/dataset descriptors, fresh MicroTape evidence, and
bundle SHA. Old Stage16R bundles must remain immutable.

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
