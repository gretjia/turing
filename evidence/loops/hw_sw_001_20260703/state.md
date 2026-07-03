# HW-SW-001..003 — Execution State

## Checkpoint 1 — HW-SW-001 (Art. 0.2 traceability audit)
- A1 `./scripts/audit-art-0-2-traceability.sh` -> exit 0 (PASS: 10-row/V-code contract, PASS: source anchors, head-order: N/A no tape refs in dev checkout).
- A1 `--commit 5` -> exit 0; `--commit 99` (negative smoke) -> exit 1 FAIL as expected.
- A2 `python3 -m pytest tests/audit/test_art_0_2_traceability.py -v` -> 16 passed (independent parser, 10 V-code parametrized checks, 2 tampered-copy negative vectors, subprocess assertion of A1 exit 0).
- Status: ADDRESSED.

## Checkpoint 2 — HW-SW-002 (sufficiency audits + IPQC calculator + harness doc)
- B1 `scripts/calc-ipqc-interval.sh` all 5 oracle vectors exact: (480,0.08)=33,
  (420,0.10)=25, (1200,0.02)=156, (480,0.20)=25, (abc,0.1)=exit 2 usage on stderr.
  Pure integer/fixed-point math (scale 10000), no floating point.
- B2 `./scripts/audit-approval-bytes-equivalence.sh` -> exit 0: all four byte-surface
  fields present (canonical_bytes, visible_card_hash_bytes, signed_bytes,
  gate_replay_bytes); `cargo test -p turing-approval` 6 passed, 0 failed.
- B3 `./scripts/audit-no-macro-as-micro.sh` -> exit 0: `cargo test -p turing-kernel
  --test accepted_head --test authorization_head --test head_effect_tamper` (3+3+13
  passed) and `cargo test -p turing-replay --test replay_determinism` (3 passed), all
  green. No pre-existing cargo failures found. `--scope projections` -> exit 0 (grep
  confirmed no refs/turingos/accepted_head write-site code outside
  crates/turing-kernel/ and crates/turing-git-tape/; the one hit outside those dirs,
  crates/turing-contracts/src/registry.rs:86, is a doc comment, filtered out).
- B4 `docs/loop_harness/README.md` exists; contains the exact canonical IPQC formula
  string, the scripts/calc-ipqc-interval.sh path, Tier 0-4 + high_risk downgrade,
  the v1.4 8-step list, the ready-block shape, and the .grok/skills/** (2026-07-03)
  supersession note.
- Status: ADDRESSED.
