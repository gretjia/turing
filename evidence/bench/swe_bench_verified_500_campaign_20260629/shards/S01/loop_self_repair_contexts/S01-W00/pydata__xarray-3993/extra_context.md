# M3.P6 Candidate-Audit Self-Repair Context

Previous worker candidate audit status: FAIL.

Audit failure:

```text
candidate patch does not apply to source snapshot: error: corrupt patch at line 13
```

Repair instruction:

- Produce a new source-only unified diff for this same task.
- Use the worker-visible problem statement and audited source context only.
- Keep the patch focused on `xarray/core/dataarray.py`.
- Avoid unrelated documentation, example, whitespace, and formatting changes.
- Return only a valid unified diff with matching file headers and hunk headers.
