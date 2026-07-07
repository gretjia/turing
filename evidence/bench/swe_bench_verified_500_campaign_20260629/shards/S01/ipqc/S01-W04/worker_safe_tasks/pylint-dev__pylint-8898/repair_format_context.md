Retry constraint for pylint-dev__pylint-8898.

The previous candidate was rejected only because the unified diff was corrupt:
`error: corrupt patch at line 113`.

Regenerate a complete valid unified diff only. Keep every changed hunk inside:

- pylint/config/argument.py

Do not edit tests, docs, packaging, lockfiles, or generated files. Do not include
markdown fences, prose, ellipses, or truncated hunks. Every hunk must include a
valid `@@ -old,count +new,count @@` header and enough unchanged context to apply
cleanly to the provided source snapshot.
