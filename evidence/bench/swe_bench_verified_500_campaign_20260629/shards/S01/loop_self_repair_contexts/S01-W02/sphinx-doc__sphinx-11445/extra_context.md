# M3.P6 Candidate-Audit Self-Repair Context

Previous worker candidate audit status: FAIL.

Audit failure:

```text
candidate patch does not apply to source snapshot: Checking patch sphinx/transforms/i18n.py...
error: patch failed: sphinx/transforms/i18n.py:102
error: sphinx/transforms/i18n.py: patch does not apply
```

Repair instruction:

- Produce a new source-only unified diff for this same task.
- Use the worker-visible problem statement and audited source context only.
- Keep the patch focused on `sphinx/transforms/i18n.py`.
- Do not edit comments only.
- Prefer one small hunk anchored on the exact audited `update_title_mapping` block:

```text
            if old_name != new_name:
                # if name would be changed, replace node names and
                # document nameids mapping with new name.
                names = section_node.setdefault('names', [])
                names.append(new_name)
                # Original section name (reference target name) should be kept to refer
                # from other nodes which is still not translated or uses explicit target
                # name like "`text to display <explicit target name_>`_"..
```

- Return only a valid unified diff with matching file headers and hunk headers.
