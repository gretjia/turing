# Phase G Full SWE-bench Verified 500 Manifest Freeze

This packet freezes the full SWE-bench Verified 500 task manifest for the next sealed campaign. It does not run the campaign and does not claim a full score.

The raw parquet is not committed because rows contain official patch/test-patch material. The manifest commits the Hugging Face dataset repo SHA, parquet SHA-256 digest, and all 500 instance IDs.

Scope: SWE-bench Verified full 500, not SWE-bench classic 2294.
