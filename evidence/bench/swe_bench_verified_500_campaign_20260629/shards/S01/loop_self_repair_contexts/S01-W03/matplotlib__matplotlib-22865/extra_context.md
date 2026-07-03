# M3.P6 Candidate-Audit Self-Repair Context

Previous worker candidate audit status: FAIL.

Audit failure:

```text
candidate patch does not apply to source snapshot: Checking patch lib/matplotlib/colorbar.py...
error: patch failed: lib/matplotlib/colorbar.py:565
error: lib/matplotlib/colorbar.py: patch does not apply
```

Repair instruction:

- Produce a new source-only unified diff for this same task.
- Use the worker-visible problem statement and audited source context only.
- Keep the patch focused on `lib/matplotlib/colorbar.py`.
- Do not include whitespace-only hunks.
- Prefer one small hunk anchored on exact audited source:

```text
        self.dividers.set_segments(
            np.dstack([X, Y])[1:-1] if self.drawedges else [])

    def _add_solids_patches(self, X, Y, C, mappable):
        hatches = mappable.hatches * len(C)  # Have enough hatches.
        patches = []
```

- Return only a valid unified diff with matching file headers and hunk headers.
