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

## Checkpoint 3 — HW-SW-003 (substrate freeze + forbidden-file guard)
- C1 `./scripts/audit-substrate-freeze.sh` -> exit 0: substrate_freeze_manifest.toml
  pins real sha256sum digests (constitution + 5 crate source anchors), all recomputed
  and matched; constitution digest independently checked against the pinned
  a0174ef8...ca3ad0 value. Fixed a real bug found while proving this: the manifest's
  awk key-parser used `[a-zA-Z_]+` which does not match digit-bearing keys like
  `sha256`, silently truncating the parse; fixed to `[a-zA-Z0-9_]+`.
  `--manifest <path>` override verified with a deliberately tampered copy -> exit 1.
- C2 `./scripts/audit-forbidden-files.sh --staged` -> exit 0 on the current clean
  staging area. `--check turing_v5/pack_v5_3_1/00_authority/constitution_root_law.md`
  -> exit 1 (negative vector, as required). `--check scripts/calc-ipqc-interval.sh`
  -> exit 0 (benign path sanity check).
- C3 `.githooks/pre-commit` exists, executable, invokes audit-forbidden-files.sh
  --staged then audit-substrate-freeze.sh; `bash .githooks/pre-commit` -> exit 0 on
  clean tree. Enable one-liner (`git config core.hooksPath .githooks`) documented in
  docs/loop_harness/README.md. `.gitignore` gains a `.turingos/` line (repo already
  had `/.turingos/` root-anchored; appended the literal unanchored form per spec).
- Status: ADDRESSED.

## Full gate — A1..C3 in sequence
- Ran every acceptance command from PREDICATE.md A1..C3 once, sequentially, on the
  first attempt after all three atoms landed. Full transcript in
  evidence/loops/hw_sw_001_20260703/gate_receipt.txt.
- Result: every command matched its PREDICATE-specified outcome exactly (A1 full=0,
  A1 --commit 1=0, A2 pytest=0/16 passed, B1 vec1..4=0 with exact oracle values
  33/25/156/25, B1 vec5=2, B2=0, B3 default=0, B3 --scope projections=0, B4 doc
  present, C1=0, C2 --staged=0, C2 --check negative vector=1, C3 pre-commit=0).
- No failures, no rework, no LESSONS.md entry required.
- Status: HW-SW-001..003 ADDRESSED, pending sovereign accept.
