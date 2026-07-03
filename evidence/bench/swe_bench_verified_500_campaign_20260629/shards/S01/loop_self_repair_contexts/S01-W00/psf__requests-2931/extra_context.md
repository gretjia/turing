# M3.P6 Candidate-Audit Self-Repair Context

Previous worker candidate audit status: FAIL.

Audit failure:

```text
candidate patch does not apply to source snapshot: source snapshot missing diff path(s): requests/utils.py
```

Repair instruction:

- Produce a new source-only unified diff for this same task.
- Use the worker-visible problem statement and audited source context only.
- The audited source context for this task contains `requests/models.py`; keep the patch in that source file.
- Do not edit tests, fixtures, benchmark evidence, generated files, or evaluation files.
- Return only a valid unified diff with matching file headers and hunk headers.
