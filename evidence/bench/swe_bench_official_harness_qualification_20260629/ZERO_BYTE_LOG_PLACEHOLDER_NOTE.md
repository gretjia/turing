# Zero-Byte Log Placeholder Note

M0.P5 classification date: 2026-07-02.

The files `logs/run_stdout.txt`, `logs/run_stderr.txt`, and
`logs/docker_build_or_cache.log` are historical zero-byte placeholders. They
contradict a naive reading of the packet-level `logs_present` fields, but the
packet's real upstream-harness logs are preserved at
`phase_f_20_repaired_run/harness_logs_raw.tar.gz`, which is the path named by
`official_harness_qualification.json`.

The placeholders are intentionally left byte-unchanged for history integrity.
Do not delete, fill, or cite them as the real harness logs.
