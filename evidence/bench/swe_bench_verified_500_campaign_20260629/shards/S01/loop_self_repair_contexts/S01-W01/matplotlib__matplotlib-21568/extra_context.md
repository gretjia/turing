# M3.P6 Candidate-Audit Self-Repair Context

Previous worker candidate audit status: FAIL.

Audit failure:

```text
candidate patch does not apply to source snapshot: error: corrupt patch at line 31
```

Repair instruction:

- Produce a new source-only unified diff for this same task.
- Use the worker-visible problem statement and audited source context only.
- Keep the patch focused on `lib/matplotlib/dates.py`.
- Do not edit documentation, `AutoDateFormatter`, or unrelated formatter code.
- Prefer one or two small hunks anchored on exact audited source.
- The audited `_wrap_in_tex` block is:

```text
def _wrap_in_tex(text):
    p = r'([a-zA-Z]+)'
    ret_text = re.sub(p, r'}$\1$\\mathdefault{', text)

    # Braces ensure dashes are not spaced like binary operators.
    ret_text = '$\\mathdefault{'+ret_text.replace('-', '{-}')+'}$'
    ret_text = ret_text.replace('$\\mathdefault{}$', '')
    return ret_text
```

- The audited ConciseDateFormatter TeX return block is:

```text
        if self.show_offset:
            # set the offset string:
            self.offset_string = tickdatetime[-1].strftime(offsetfmts[level])
            if self._usetex:
                self.offset_string = _wrap_in_tex(self.offset_string)

        if self._usetex:
            return [_wrap_in_tex(l) for l in labels]
        else:
            return labels
```

- Return only a valid unified diff with matching file headers and hunk headers.
- Do not remove or include `def get_offset(self):` in the patch hunk.
- Prefer changing only the `return [_wrap_in_tex(l) for l in labels]` line if you edit the ConciseDateFormatter block.
- If you include the `show_offset` block as context, preserve its nested `if self._usetex:` lines exactly.
