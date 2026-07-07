# M3.P6 Candidate-Audit Self-Repair Context

Previous worker candidate audit status: FAIL.

Audit failure:

```text
candidate patch does not apply to source snapshot: error: corrupt patch at line 22
```

Repair instruction:

- Produce a new source-only unified diff for this same task.
- Use the worker-visible problem statement and audited source context only.
- Keep the patch focused on `sphinx/io.py`.
- Prefer one small hunk anchored on the audited `read_source` block:

```text
    def read_source(self, env: BuildEnvironment) -> str:
        """Read content from source and do post-process."""
        content = self.source.read()

        # emit "source-read" event
        arg = [content]
        env.events.emit('source-read', env.docname, arg)
        return arg[0]
```

- Do not include context-only hunks.
- Return only a valid unified diff with matching file headers and hunk headers.
