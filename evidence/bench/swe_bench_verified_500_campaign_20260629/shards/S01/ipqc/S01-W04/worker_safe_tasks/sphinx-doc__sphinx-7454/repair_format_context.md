Retry constraint for sphinx-doc__sphinx-7454.

The previous candidate was rejected only because the unified diff was malformed:
`patch fragment without header at line 21`.

Regenerate a complete valid unified diff only. Keep every changed hunk inside the
source files already selected for this task:

- sphinx/ext/autodoc/__init__.py
- sphinx/util/typing.py
- sphinx/util/inspect.py

Do not edit tests, docs, packaging, lockfiles, or generated files. Do not include
markdown fences, prose, ellipses, or truncated hunks. Each file section must have
proper `diff --git`, `---`, `+++`, and hunk headers, and each separated hunk must
start with its own valid `@@ -old,count +new,count @@` header.
