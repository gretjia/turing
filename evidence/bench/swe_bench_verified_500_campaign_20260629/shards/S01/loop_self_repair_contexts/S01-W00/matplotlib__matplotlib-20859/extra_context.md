# M3.P6 Candidate-Audit Self-Repair Context

Previous worker candidate audit status: FAIL.

Audit failure:

```text
candidate patch does not apply to source snapshot: error: corrupt patch at line 12
```

Repair instruction:

- Produce a new source-only unified diff for this same task.
- Use the worker-visible problem statement and audited source context only.
- Keep the patch focused on `lib/matplotlib/legend.py`.
- The audited local import and parent-type block is:

```text
        # local import only to avoid circularity
        from matplotlib.axes import Axes
        from matplotlib.figure import Figure

        super().__init__()
```

```text
        if isinstance(parent, Axes):
            self.isaxes = True
            self.axes = parent
            self.set_figure(parent.figure)
        elif isinstance(parent, Figure):
            self.isaxes = False
            self.set_figure(parent)
        else:
            raise TypeError("Legend needs either Axes or Figure as parent")
```

- If using `FigureBase`, make the local import and the `isinstance` check consistent.
- Do not add a separate unused `FigureBase` import while leaving `elif isinstance(parent, Figure)` unchanged.
- A minimal valid change would update the local figure import and the parent-type check in matching hunks.
- Preserve the `super().__init__()` context line between the local imports and the `if isinstance(parent, Axes):` block.
- Use two separate hunks:
  - one hunk anchored at the local import block ending with `super().__init__()`;
  - one hunk anchored at the parent-type block starting with `if isinstance(parent, Axes):`.
- Do not merge the local import and parent-type check into a single hunk.
- Do not include no-op hunks that remove and re-add the same line.
- Return only a valid unified diff with matching file headers and hunk headers.
