---
name: econ-lab-review-checklist
description: Review focus areas for tools/econ_lab (live_driver resume/determinism): verdict.json byte-parity is a hard contract; check atomic-write gaps on checkpoint JSON files
metadata:
  type: project
---

tools/econ_lab reviews should treat verdict.json byte-parity (fresh vs --resume) as a hard requirement — guarded by tests/test_live_driver_head_parity.py and tests/test_live_driver_resume.py, and stated in module docstrings.

**Why:** WP9c resume semantics require replay to reproduce identical state; the 2026-07-07 audit found the main gaps were (a) non-atomic `write_text` of settlement.json/worker_receipt.json + unguarded `json.loads` on the resume read path (kill-during-write => resume crash), and (b) resume's `_read_scoring_report` accepting any existing aggregated report as COMPLETED while the fresh path also gates on subprocess returncode.

**How to apply:** when reviewing changes here, check every checkpoint/artifact JSON for tmp+rename atomic writes and JSONDecodeError handling on read, and diff fresh vs resume code paths key-by-key for verdict-shape divergence (e.g. `primary_attempt_status` on the deepseek fallback reconstruction). All deterministic math must go through econ_fold_cli, never re-derived in Python.
