# HW-SW-001..003 — Execution State

## Checkpoint 1 — HW-SW-001 (Art. 0.2 traceability audit)
- A1 `./scripts/audit-art-0-2-traceability.sh` -> exit 0 (PASS: 10-row/V-code contract, PASS: source anchors, head-order: N/A no tape refs in dev checkout).
- A1 `--commit 5` -> exit 0; `--commit 99` (negative smoke) -> exit 1 FAIL as expected.
- A2 `python3 -m pytest tests/audit/test_art_0_2_traceability.py -v` -> 16 passed (independent parser, 10 V-code parametrized checks, 2 tampered-copy negative vectors, subprocess assertion of A1 exit 0).
- Status: ADDRESSED.
