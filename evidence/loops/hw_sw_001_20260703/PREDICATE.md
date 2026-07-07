# PREDICATE — HW-SW-001..003 (gate must pass first try once predicate is correct)

All commands run from the worktree root. WORK_ROOT resolution in every script:
`WORK_ROOT="${TURINGOS_WORK_ROOT:-/home/zephryj/turingos_backup/work}"` (P0-pragmatic default, overridable —
tooling only, not substrate).

## Atom HW-SW-001 — Art. 0.2 traceability audit
A1. `./scripts/audit-art-0-2-traceability.sh` → exit 0. Checks, in order:
    (a) matrix doc exists at $WORK_ROOT/docs/roadmap/secure_os_18_month/02_software_sufficiency_proof.md
        and its §1.3 table has exactly 10 data rows, Commit 1..10 each present once;
    (b) every row's "violation closed" cell matches the constitutional V-code sets:
        1→V-01,V-06,V-18; 2→V-02,V-03,V-22; 3→V-04,V-05,V-15,V-16; 4→V-03,V-09,V-13; 5→V-08a,V-17;
        6→V-07; 7→V-08b,V-22; 8→V-10,V-11,V-14; 9→V-19,V-21; 10→V-18,V-24;
    (c) real source anchors resolve (grep -q): ApprovalByteSurfaces, SignatureRoute, HardwareFuture,
        "trait SigningBackend" in crates/turing-approval/src/lib.rs; refs/turingos/tape_tip in
        crates/turing-loop/src/lib.rs; file exists crates/turing-replay/tests/replay_determinism.rs;
    (d) head-order (conditional): if `git for-each-ref refs/turingos/tape_tip` non-empty →
        require accepted_head ancestor-or-equal authorization_head ancestor-or-equal tape_tip
        (git merge-base --is-ancestor); else print "head-order: N/A (no tape refs in dev checkout)".
    `--commit N` flag: run only row N's checks (matrix row + its anchors).
A2. `python3 -m pytest tests/audit/test_art_0_2_traceability.py -v` → all pass. The pytest mirror
    independently parses the table (no shelling to A1's script for the row checks — no self-reference),
    asserts the 10-row/V-code contract, AND asserts `./scripts/audit-art-0-2-traceability.sh` exits 0.
    Negative vectors inside the test: a tampered copy of the table (row deleted / V-code mutated) written
    to tmp_path must make the parser reject.

## Atom HW-SW-002 — sufficiency audits + IPQC calculator + harness doc
B1. `bash scripts/calc-ipqc-interval.sh 480 0.08`  → stdout exactly `33`
    `bash scripts/calc-ipqc-interval.sh 420 0.10`  → `25`  (floor clamp: 420*0.05=21 → 25)
    `bash scripts/calc-ipqc-interval.sh 1200 0.02` → `156` (1200*0.13)
    `bash scripts/calc-ipqc-interval.sh 480 0.20`  → `25`  (min(0.10,f) clamp: 480*0.05=24 → 25)
    `bash scripts/calc-ipqc-interval.sh abc 0.1`   → exit 2, usage on stderr. Integer-only awk/bc math;
    oracle vectors fixed here, not derived from the implementation (R-BIND).
B2. `./scripts/audit-approval-bytes-equivalence.sh` → exit 0: greps the four byte-surface fields on
    ApprovalByteSurfaces in crates/turing-approval/src/lib.rs, then `cargo test -p turing-approval` green.
B3. `./scripts/audit-no-macro-as-micro.sh` → exit 0: `cargo test -p turing-kernel --test accepted_head
    --test authorization_head --test head_effect_tamper` and `cargo test -p turing-replay --test
    replay_determinism` green (verify exact --test names against files before writing; bind to real names).
    `--scope projections` flag: grep-only fast mode asserting reducer is the sole head-mover
    (no `refs/turingos/accepted_head` write sites outside crates/turing-kernel/ and crates/turing-git-tape/).
B4. `docs/loop_harness/README.md` exists; contains the canonical IPQC formula string
    `max(25, floor(eta_steps * (0.15 - min(0.10, failure_rate))))`, the scripts/calc-ipqc-interval.sh path,
    tier rules (Tier 0–4, high_risk downgrade), the v1.4 8-step list, the ready-block shape, and the
    supersession note for `.grok/skills/**` (founder instruction 2026-07-03).

## Atom HW-SW-003 — substrate freeze + forbidden-file guard
C1. `./scripts/audit-substrate-freeze.sh` → exit 0: substrate_freeze_manifest.toml pins sha256 of:
    constitution (must equal a0174ef8a2be6914f86ea8e594e022c7ca6a4221ed63535d65a997e096ca3ad0),
    crates/turing-approval/src/lib.rs, crates/turing-replay/src/lib.rs,
    crates/turing-git-tape/src/head_set.rs, crates/turing-git-tape/src/append.rs,
    crates/turing-kernel/src/reducer.rs — recomputed and compared. `--manifest <path>` override for tests.
    Manifest changes require a commit message containing `REPIN:` + rationale (documented in manifest header).
C2. `./scripts/audit-forbidden-files.sh --staged` → exit 0 on clean staging; exit 1 if staged paths match
    forbidden set: `**/00_authority/**`, `*constitution_root_law.md*`, `PROGRESS_TRACKER.md` pinned docs.
    `--check <path>` mode: `./scripts/audit-forbidden-files.sh --check turing_v5/pack_v5_3_1/00_authority/constitution_root_law.md` → exit 1.
C3. `.githooks/pre-commit` exists, executable, invokes audit-forbidden-files.sh --staged and
    audit-substrate-freeze.sh; `bash .githooks/pre-commit` → exit 0 on clean tree. README one-liner:
    `git config core.hooksPath .githooks`. `.gitignore` gains `.turingos/`.

## Red-first (R-REDFIRST)
Before implementing any script: commit tests/audit/test_art_0_2_traceability.py + this PREDICATE/CONTEXT,
run gate, capture failing output to evidence/loops/hw_sw_001_20260703/red_first.txt, commit it.
Then implement to green. Red commit must not be squashed.

## Mini-Recovery triggers
Any acceptance command failing twice on the same cause; cargo test names not found (rebind, don't fake);
any command touching constitution_root_law.md; forbidden-file guard self-trip; head-order violation when
refs exist. On trigger: 3-why RCA → targeted fix → rerun full gate → one rule to LESSONS.md.
