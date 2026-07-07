# CONTEXT — HW-SW-001..003 Substrate Lockdown (Phase 1, secure OS roadmap)

Route: turing_full / plan lite / horizon_mode on / require_predicate satisfied by PREDICATE.md.
Worktree: turing/.turingos/worktrees/hw-sw-001, branch turing/hw-sw-001-substrate-lockdown (from 0ca9726).

## Ground facts (verified 2026-07-03)
- Workspace root (TURINGOS_WORK_ROOT): /home/zephryj/turingos_backup/work
- Constitution: turing_v5/pack_v5_3_1/00_authority/constitution_root_law.md
  sha256 = a0174ef8a2be6914f86ea8e594e022c7ca6a4221ed63535d65a997e096ca3ad0 (human-sudo only; never edit)
- Traceability matrix (real contract the audit binds to):
  docs/roadmap/secure_os_18_month/02_software_sufficiency_proof.md §1.3, markdown table starting line ~190,
  columns: Commit | Constitutional violation closed | Software-only artifact | Future hardware hook |
  Acceptance command | Roadmap phase. Exactly 10 data rows (Commit 1..10), V-codes like "V-01, V-06, V-18".
- Real symbol anchors (grep targets, verified):
  crates/turing-approval/src/lib.rs: "approval_payload.v2" (l.22), SignatureRoute::HardwareFuture (l.30),
    ApprovalByteSurfaces (l.113), trait SigningBackend (l.181), HardwareSigningBackend (l.702)
  crates/turing-loop/src/lib.rs:20: REF_TAPE_TIP = "refs/turingos/tape_tip"
  crates/turing-git-tape/src/head_set.rs (SG-18 torn-read guard), crates/turing-git-tape/src/append.rs
  crates/turing-replay/tests/replay_determinism.rs (SG-19), crates/turing-replay/src/lib.rs
  crates/turing-kernel/tests/{accepted_head.rs,authorization_head.rs,head_effect_tamper.rs}
  crates/turing-kernel/src/reducer.rs (only head-mover)
- Dev repo has NO refs/turingos/* (count 0) → head-order audit is conditional: enforce ordering only when
  refs/turingos/tape_tip exists (runtime tape repos); absence in a dev checkout is N/A, not a violation.
- pytest 7.2.1 via python3 -m pytest; tests/ is the Python test tree (conftest.py at repo root).
- scripts/ currently holds only install-local.sh.
- Founder instruction 2026-07-03: do NOT use `.grok/skills/**`; harness docs live at docs/loop_harness/
  in this repo; calc-ipqc-interval.sh lives at scripts/calc-ipqc-interval.sh. The unified `loop` skill
  (v2.0) is the single harness entrance; roadmap references to `.grok/skills/**` are superseded.
- Canonical TuringOS IPQC formula: ipqc_interval = max(25, floor(eta_steps * (0.15 - min(0.10, failure_rate)))).
  (Distinct from the harness-internal checkpoint formula; this one is the roadmap/TuringOS-native contract.)
- Implementer ceiling: ADDRESSED. No CLOSED/RELEASED/RATIFIED self-claims anywhere.
- Status: this run may produce draft commits on the phase branch only; merge target selection and
  sovereign accept belong to the founder.
