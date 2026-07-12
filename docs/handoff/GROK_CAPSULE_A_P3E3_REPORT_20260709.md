# CAPSULE A — P3-E3 Grok Report (2026-07-09)

**Status ceiling: ADDRESSED** (implementer; no CLOSED/RELEASED/RATIFIED claims).

**Worktree:** `/home/zephryj/turingos_backup/work/grok_p3e3`  
**Branch:** `p3e3/grok-20260709`  
**Baseline:** `0ebd7ad`  
**Capsule dispatch:** `PROJECT_PLAN_…/dispatch/CAPSULE_A_P3E3_grok_20260709.md` sha `f9ec8b78…`

This report records process, gate evidence, and the single frozen readout outcome.  
**No interpretation beyond CAPSULE A §4 outcome mapping** — analysis rights remain with the orchestrator.

---

## 1. What was built

| Piece | Path |
|---|---|
| Stream manifest (PHASE1@22 then PHASE2) | `tools/econ_lab/analysis/p3e3_stream_manifest.json` |
| S01+S02 pooled priors | `tools/econ_lab/analysis/p3e3_priors_s01s02.json` |
| Frozen readout (§4 verbatim) | `tools/econ_lab/analysis/p3e3_readout.py` |
| Driver extensions | `tools/econ_lab/live_driver.py` (`--stream-manifest`, `--reset-at-task-index`) |
| Launcher | `tools/econ_lab/run_p3e3.sh` |
| Offline tests | `tests/test_p3e3_driver.py` |
| S03 packets | `evidence/bench/.../shards/S03/ipqc/**/task_packet.json` (50) |
| Full run | `tools/econ_lab/runs/p3e3_20260709/{L,Z,R}/` |
| Readout (once) | `tools/econ_lab/runs/p3e3_20260709/P3E3_READOUT.json` |
| HANDOFF | `HANDOFF_CAPSULE_A.json` |

### Arms (all τ=0.5, same priors, same stream)

| Arm | Semantics | Flags |
|---|---|---|
| L | live backup | — |
| Z | frozen backup | `--frozen-backup` |
| R | live + reset at switch | `--reset-at-task-index 22` |

Switch point: task index **22** (0-based) after PHASE1 families  
`{astropy, django, pydata, pytest-dev}` (22) and before PHASE2  
`{matplotlib, scikit-learn, sphinx-doc, sympy}` (28).

---

## 2. SPEC GATE (entry)

| # | Predicate | Result | Evidence |
|---|---|---|---|
| 1 | Constitution sha | **PASS** exit 0 | `sha256sum -c` → OK (`a0174ef8…`) |
| 2 | Governance | **PASS** exit 0 | `verify_alignment.sh` → GREEN |
| 3 | Spec shas | **PASS** | ADR-ECON-003 `b6a33f9292458dfb…`; phase3 `ea2870070776c7de…`; limits `f7a9bfd4f315c8ba…`; PREREG present |
| 4 | Baseline tests | **PASS** | pytest live_driver suite exit 0; `cargo test -p turing-economy` exit 0; `gate_f4` F4_LEAK_PASS |

Environment traps handled: scoring via `~/.turingos/swebench-venv/bin/python`; secrets via `source ~/.turingos/secrets.env` (values never written to files); Docker concurrency arm-parallel 2, harness workers 1; Rust `turing` binary linked for JCS owner (`target/debug/turing` → existing fce_integration build) after broken editable install path.

---

## 3. Execution sequence

1. Worktree `grok_p3e3` at `0ebd7ad`, branch `p3e3/grok-20260709`.
2. Materialize S03 windows W00–W04 + audit each window → all PASS; 50/50 packets.
3. Zero-overlap proof vs S01/S02 → both intersections empty.
4. Content fingerprint: `e0d965a8eff0fcb4f147edbe2ef4463805108bd3551fead5556f05d8e9882012`.
5. Driver + priors + stream + readout + offline tests.
6. **Prereg freeze:** readout sha `bf9faca4b2d0b5a2ab3298e80a3c13bb360fb35df9449e16f87cc905df26b5b3` written to HANDOFF **before** first real call.
7. Smoke: L/Z/R × 1 task (3 real calls) — worker→score→settle OK; meta flags correct.
8. Full run: `run_p3e3.sh` — L/Z/R each 50 tasks, wall ~5.5 h.
9. Single readout → `P3E3_READOUT.json`.

**Mid-stream ban honored:** no arm pass rates inspected until all three arms DONE.

---

## 4. SHIP GATE

| # | Predicate | Result | Evidence |
|---|---|---|---|
| 1 | S03 50 + audit + zero overlap + fingerprint | **PASS** | count=50; audits PASS; ∩S01=∩S02=0; fp above |
| 2 | Driver tests + baseline green | **PASS** | `test_p3e3_driver.py` + suite pytest 0; cargo 0; F4 PASS |
| 3 | Smoke 3×1 | **PASS** | `runs/p3e3_smoke_20260709/{L,Z,R}/verdict.json` |
| 4 | Readout self-test + pre-run freeze | **PASS** | `P3E3_READOUT_SELF_TEST_PASS`; sha match HANDOFF |
| 5 | Three verdicts + readout once | **PASS** | `runs/p3e3_20260709/{L,Z,R}/verdict.json` + `P3E3_READOUT.json` |
| 6 | Commit on branch, no push | **PASS** (at commit time) | see git log; **no push** |
| 7 | Deliverables | **PASS** | HANDOFF + this report + runs tree |

---

## 5. Run meta integrity (post-hoc, structural only)

| Arm | tasks | real_calls | frozen_backup | reset_at | priors_sha | stream_sha |
|---|---:|---:|---|---|---|---|
| L | 50 | 42 | false | null | `5bae2a64…` | `d9dca4dc…` |
| Z | 50 | 46 | **true** | null | same | same |
| R | 50 | 47 | false | **22** | same | same |

Quality floors (from readout): every arm full settled ≥40/50 and PHASE2 settled ≥22/28 → judgment allowed.

Worker call budget: **138 / 165** (smoke 3 + full 42+46+47).

---

## 6. Frozen readout outcome (single judgment)

**`p3e3_outcome`: `NULL_HONEST_RECORD`**

| Hypothesis | Supported (α'=0.025) | McNemar (PHASE2) |
|---|---|---|
| H-E3a L > Z | **false** | b=0, c=0, n=0, p=null |
| H-E3b L > R | **false** | b=1, c=1, n=2, p=0.75 |

Secondary (descriptive only; **no significance claims**):

- PHASE1/PHASE2 rates recorded in `P3E3_READOUT.json` `arm_stats_*`
- Canaries: L=1, Z=0, R=1 (`soundness_flag=false`)
- t½ descriptive + one L PHASE2 rank-inversion event listed in readout JSON

**Null is a valid pre-registered result.** No further narrative here.

---

## 7. Gaps / notes for orchestrator

1. Launcher shell aggregate returned exit 1 once despite all three `status.json` showing `DONE`/`exit:0` — likely early `tee` failure creating `launcher.log` before `mkdir -p` completed under `set -o pipefail` in the outer wrapper; arm drivers themselves succeeded.
2. Full-arm `real_worker_calls_made` < 50 on L/Z/R because some dispatches are infra_null / non-COMPLETED (still counted toward settlement floors where applicable).
3. Smoke used single-winner `max-tasks=1` (not `--smoke` 4-lineage mode) to keep smoke ≤3 calls; R reset firing proven offline + full-run `reset_at=22`.
4. Host `turing` Python editable install pointed at a deleted path; resolved by linking existing Rust `turing` binary into worktree `target/debug/turing` for JCS (no constitution/package mutation).
5. **Not pushed. Not merged.** Merge authority remains with orchestrator.

---

## 8. Deliverable checklist

- [x] `HANDOFF_CAPSULE_A.json`
- [x] `docs/handoff/GROK_CAPSULE_A_P3E3_REPORT_20260709.md`
- [x] `tools/econ_lab/runs/p3e3_20260709/{L,Z,R}/`
- [x] `tools/econ_lab/runs/p3e3_20260709/P3E3_READOUT.json`
- [x] Prereg freeze before real runs
- [x] Budget ≤165 (used 138)
- [x] No push / no merge
- [x] Ceiling ADDRESSED
