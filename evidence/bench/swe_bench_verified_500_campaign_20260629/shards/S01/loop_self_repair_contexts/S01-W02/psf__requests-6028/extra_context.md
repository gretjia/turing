# M3.P6 Candidate-Audit Self-Repair Context

Previous worker candidate audit status: FAIL.

Audit failure:

```text
candidate patch does not apply to source snapshot: Checking patch requests/models.py...
error: patch failed: requests/models.py:563
error: requests/models.py: patch does not apply
```

Repair instruction:

- Produce a new source-only unified diff for this same task.
- Use the worker-visible problem statement and audited source context only.
- Keep the patch focused on `requests/models.py`.
- Do not include no-op hunks that remove and re-add the same line.
- Prefer a small hunk anchored on exact audited source around `prepare_content_length`:

```text
    def prepare_content_length(self, body):
        """Prepare Content-Length header based on request method and body"""
        if body is not None:
            length = super_len(body)
            if length:
                # If length exists, set it. Otherwise, we fallback
                # to Transfer-Encoding: chunked.
                self.headers['Content-Length'] = builtin_str(length)
        elif self.method not in ('GET', 'HEAD') and self.headers.get('Content-Length') is None:
            # Set Content-Length to 0 for methods that can have a body
            # but don't provide one. (i.e. not GET or HEAD)
            self.headers['Content-Length'] = '0'
```

- Return only a valid unified diff with matching file headers and hunk headers.
