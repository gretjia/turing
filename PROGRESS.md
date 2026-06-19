# PROGRESS — TuringOS 1.0 autonomous build ledger

> **Resume rule:** on any restart/compaction, read THIS file first. Never restart from zero.
> Authority: `CLAUDE.md` + the finalized plan (`turingos_research/TURINGOS_1_0_PLAN/`). Constitution = root law.

## Run header
- **As-of:** 2026-06-20
- **Mode:** autonomous, unattended, predicate-first, Verifier ≠ Implementer.
- **Routing:** `routing_decision.json` → `turing_full` + `horizon_mode:true`; `plan_depth=none` (plan is the approved canonical proposal — binding CLAUDE.md override).
- **Repo:** this git repo is the BUILD. The TuringOS **Micro Tape** is a SEPARATE native-SHA-256 git repo the code manages (never pushed to a forge).
- **Remote:** `origin = https://github.com/gretjia/turing` — push after Stage 0 and each shipped module.
- **Host:** macOS Darwin 27.0.0, git 2.54.0 (sha256-native ✓), python3 3.9.6 ✓, jq 1.7.1 ✓.

## Stage map (the PLAN governs — 4 stages)
- **Stage 0** — Freeze baseline contracts (B-1…B-5) + run S-1, S-2 PRE spikes. ← buildable now
- **Stage 1** — Fake/manual Worker drives FULL loop E2E + replay (S-3, S-4, S-7 GATEs) → freeze 18-event registry. **← THE MILESTONE** (BOOT: "fake/manual-worker full-loop E2E + replay/handoff green")
- **Stage 2** — ≥2 real Worker adapters + GitHub (S-5, S-6). **CREDENTIALED → BLOCKED** (see BLOCKED.md)
- **Stage 3** — Dogfood real pains. Depends on Stage 2. **BLOCKED**

## Build-module decomposition (derived from plan §4.1 M1–M17 + App E spikes; dependency-ordered)
Foundation (substrate — fully atomized, built first):
- [x] **MOD-CODEC**  (plan M2) — `turingos.jcs.v1`: JCS serialize, ASCII-key/no-float guard, `content_digest=sha256(JCS(payload))`. (no deps)
- [x] **MOD-REGISTRY** (plan M3) — 18 events, 3 classes, `registry[type].class`, closed-world `head_effect`. (no deps)
- [x] **MOD-TAPE** (plan M1) — SHA-256 Micro ChainTape, 2 refs, FF-only append, 7-field envelope guard (5 load-bearing), `accepted_head` advance rule, single-writer guard + handoff. (deps: CODEC, REGISTRY)  ← S-1, S-2 land here as GATEs
- [x] **MOD-PREDICATE** (plan M5) — deterministic predicate kernel over Tape bytes (9 checks). (deps: TAPE, REGISTRY, CODEC, schemas)  ← S-3 GATE
- [x] **MOD-EVIDENCE** (plan M10) — Receipt import + evidence digests + Macro anchor binding. (deps: TAPE, CODEC)
- [x] **MOD-REPLAY** (plan M16) — deterministic replay (byte-equal) + Handoff bundle. (deps: TAPE, REGISTRY, CODEC)  ← S-7 GATE
Loop (needed for Stage 1 E2E with fake worker):
- [x] **MOD-BOOT** (plan M4) — Project Spec as Boot INPUT; seed Q_0; SystemBootstrapped/ProjectAdopted/GoalStateAccepted/ModulePlanAccepted.
- [x] **MOD-PLANNER** (plan M6) — progressive Module→Atom expansion; AtomProposed.
- [x] **MOD-CAPSULE** (plan M7+M11) — Shielded Work Capsule + FailureMemory (FailureClass→abstract rule, scoped inject); WorkCapsuleBuilt.  ← S-4 GATE
- [x] **MOD-WORKER** (plan M8) — WorkerAdapter seam + **fake/manual deterministic Worker** + timeout/kill/retry (PG reap); WorkerDispatched/WorkerReceiptImported. (real ≥2 adapters = Stage 2/BLOCKED)
- [x] **MOD-REDUCE** (plan M14+M15) — reduce Tape→q_t, derive WorkGraph, Textual Panorama (Authorized-vs-Accepted labels).
- [x] **MOD-EXPLORE** (plan M12+M13) — Exploration Archive/Promote + HumanSteerInjected.
- [x] **MOD-SIGN** (plan M17) — SigningBackend seam + ApprovalCard canonical_bytes→hash/signature derivation (in-proc deterministic signer; keyring deferred).
- [x] **MOD-E2E** (Stage 1) — loop driver: drive full loop w/ fake worker through BOTH predicate branches; S-3/S-4/S-7 green; FREEZE registry.

## Status — 🎯 MILESTONE REACHED
- **stage:** Stage 0 ✅ · Foundation ✅ · **Stage 1 ✅ SHIPPED = THE MILESTONE** · Stage 2/3 ⛔ BLOCKED (credentialed)
- **milestone:** full locally-buildable scope + fake/manual-worker full-loop E2E + replay/handoff green.
  `loop_e2e.py` ALL_PASS (10/10): accepted=2, failed=1, both predicate branches; S-3/S-4/S-7 green;
  registry FROZEN v1.0.0. 373 unit tests OK. See `MILESTONE_REPORT.md` + `evidence/stage1/`.
- **modules_shipped:** [Stage-0 baseline; Foundation kernel (10 mods, 235 tests, kernel_smoke 10/10);
  Loop layer (boot/planner/capsule+FailureMemory/worker+fake/signing/explore/panorama/loop) — loop_e2e 10/10]
- **lessons:** LESSONS.md (LF-1 advance-requires-PASS, LF-2 replay-recompute, LF-3 glossary-beats-merge)
- **next_action:** NONE buildable locally — remaining work (Stage 2 real ≥2 adapters + GitHub; Stage 3 dogfood)
  is credential-gated → BLOCKED.md. To unblock: authorize the credentialed Worker+GitHub batch (one human input).
- **Test framework:** stdlib `unittest`. Import path: `PYTHONPATH=src` (+ root conftest.py).
- **Re-run gates any time:** `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'` ·
  `PYTHONPATH=src python3 tests/integration/loop_e2e.py` · `... kernel_smoke.py`.

### Shipgate 0 receipt — `evidence/stage0/`
- S-1 PRE: ALL_PASS (sha256 ✓ · failure-is-state ✓ · advance rule ✓ · mixed-hash exit128 ✓ · replay-equal ✓ · 2 refs ✓)
- S-2 PRE: ALL_PASS (single-writer guard ✓ · wrong-writer/non-FF reject ✓ · handoff changes writer ✓ · no epoch/lease ✓)
- Contracts: `contracts/` (10 files incl. INTERFACES.md glossary) · ADRs: `docs/adr/` (8). MANIFEST.sha256 verified OK.

## Discipline invariants (never traded)
predicate-first · no IMPLEMENT before PREDICATE.md + frozen acceptance_commands · Verifier ≠ Implementer · failure-on-tape · every spike → on-disk artifact + sha256 in MANIFEST.sha256 · BLOCKED stays BLOCKED · no assertion-of-done.
