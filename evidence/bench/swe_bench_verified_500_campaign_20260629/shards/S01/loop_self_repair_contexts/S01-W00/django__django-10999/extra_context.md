# M3.P6 Candidate-Audit Self-Repair Context

Previous worker candidate audit status: FAIL.

Audit failure:

```text
candidate patch is not a unified diff
```

Repair instruction:

- Produce a new source-only unified diff for this same task.
- Use the worker-visible problem statement and audited source context only.
- Keep the patch focused on `django/utils/dateparse.py`.
- The relevant audited source block is:

```text
standard_duration_re = re.compile(
    r'^'
    r'(?:(?P<days>-?\d+) (days?, )?)?'
    r'((?:(?P<hours>-?\d+):)(?=\d+:\d+))?'
    r'(?:(?P<minutes>-?\d+):)?'
    r'(?P<seconds>-?\d+)'
    r'(?:\.(?P<microseconds>\d{1,6})\d{0,6})?'
    r'$'
)
```

- Return only a valid unified diff with matching file headers and hunk headers.
