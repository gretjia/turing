# CAPSULE D — Fracflat Confirmatory Experiment Report (2026-07-10)

**Status ceiling: ADDRESSED** (implementer; no CLOSED/RELEASED/RATIFIED claims).  
**Nature: confirmatory experiment only — analysis rights remain with the orchestrator.**

**Worktree:** `/home/zephryj/turingos_backup/work/grok_fracflat`  
**Branch:** `fracflat/grok-20260710`  
**Base (C tip):** `dcd0eed5ca49cef74b8a9c25153c4e9d9a8c991f`  
**C HANDOFF head_commit:** `aae97ca1fe8955fc43c65801a7061c29824a1f6b`  
**Deliverable head_commit:** `9bef0abba8a01d23278b171517f50c75058fd7ff`  
**Branch tip (HANDOFF pin):** `58db6c7056866822bc6f955293db7f19838e0f48`  
**Dispatch:** `CAPSULE_D_FRACFLAT_grok_20260710.md` sha `977764b1…`

This report records process, gate evidence, and the single frozen readout outcome.  
**No interpretation beyond CAPSULE D §4 outcome mapping.**

---

## 1. What was built (NEW FILES ONLY)

| Piece | Path |
|---|---|
| Pool builder | `tools/econ_lab/analysis/fracflat_build_pool.py` |
| Pool manifest (50) | `tools/econ_lab/analysis/fracflat_pool_manifest.json` |
| Stream manifest | `tools/econ_lab/analysis/fracflat_stream_manifest.json` |
| Virtual task root (S01∪S02 dir symlinks) | `tools/econ_lab/analysis/fracflat_task_root/` |
| Frozen readout (§4 verbatim) | `tools/econ_lab/analysis/fracflat_readout.py` |
| Launcher | `tools/econ_lab/run_fracflat.sh` |
| Full run | `tools/econ_lab/runs/fracflat_20260710/{FL,BL,UU}/` |
| Smoke | `tools/econ_lab/runs/fracflat_20260710/smoke_{FL,BL,UU}/` |
| Readout (once) | `tools/econ_lab/runs/fracflat_20260710/FRACFLAT_READOUT.json` |
| HANDOFF | `HANDOFF_CAPSULE_D.json` |

**Driver / Rust / existing analysis scripts: not modified.**

### Arms (all 12-route flat market, cold P=0.5)

| Arm | Semantics | Flags |
|---|---|---|
| FL | fractional-live | `--tau 0.5 --fractional-reward` |
| BL | binary-live | `--tau 0.5` |
| UU | uniform | `--tau inf` |

---

## 2. SPEC GATE (entry)

| # | Predicate | Result | Evidence |
|---|---|---|---|
| 1 | Constitution sha | **PASS** | `sha256sum -c` → OK (`a0174ef8…`) |
| 2 | Governance | **PASS** | `verify_alignment.sh` → GREEN |
| 3 | C handoff + fractional flag | **PASS** | `HANDOFF_CAPSULE_C.json` blocked=[]; `--fractional-reward` present on `live_driver.py` |
| 4 | Baseline tests | **PASS*** | cargo `turing-economy` OK; gate_f4 `F4_LEAK_PASS` + self-test PASS; pytest live_driver suite: 2 **inherited** head_parity failures (C fractional fields vs merge-base; NEW-FILES-ONLY cannot patch tests); remaining suite green |

\* Inherited C tip state, not a D regression.

---

## 3. Pool (frozen sort)

- Candidate: S01∪S02 = 100 instances.
- Historical arms: stageA 5 (`tau_0/0p5/1/2/inf`) + stageBprime 4 (`W/F/C/U`) = 9 verdicts.
- Accept-pass = `settlement_verdict_resolved==True` (fallback `live_split.accept_verdict`).
- Sort: `(historical_accept_pass_count DESC, instance_id ASC)`; top 50 = stream order.
- Pool sha256: `15afde7bfb4693fbfbf363d450eb920bc8fc2dd27cfbc35ea1d66a953c41a86b`
- Stream sha256: `bf3f8f8d79ed7e3370e2c1dbeb534809239bb7e3f6acb8236726df3485cc6d69`
- Recalc: `python3 tools/econ_lab/analysis/fracflat_build_pool.py`

---

## 4. Prereg freeze (before first real call)

| Field | Value |
|---|---|
| readout_sha256 | `0611bf465a3a1d655116901126db18f622eed34b2c14db97c7e0bb0d70efb204` |
| self-test | `FRACFLAT_READOUT_SELF_TEST_PASS` (all 4 outcomes + floor) |
| frozen_before_first_real_run | **true** (HANDOFF written pre-smoke) |

Mid-stream ban honored: no arm pass rates inspected until all three arms DONE.

---

## 5. Execution

1. Smoke: 1 task × 3 arms (worker→score→settle chain; FL fractional meta true; BL/UU fractional false).  
   Budget note: one UU smoke re-run after infra_null (harness race under shared Docker with CAPSULE E).
2. Full run: `run_fracflat.sh` — arm concurrency 2, harness max_workers 1; wall ~5.8 h with Docker shared vs CAPSULE E.
3. Single readout → `FRACFLAT_READOUT.json`.

### Budget (real worker calls)

| Segment | Calls |
|---|---:|
| Smoke (incl. 1 UU retry) | 4 |
| FL full | 40 |
| BL full | 41 |
| UU full | 43 |
| **Total** | **128 / 165** |

---

## 6. Readout (CAPSULE D §4 — once)

| Field | Value |
|---|---|
| Floor (≥40/50 computable v) | **PASS** (FL 40, BL 40, UU 42) |
| H-D1 FL>UU | **not supported** (p≈0.799, n_paired=35, mean_diff≈−0.078) |
| H-D2 FL>BL | **not supported** (p≈0.857, n_paired=34, mean_diff≈−0.103) |
| **Outcome** | **`NULL_EVEN_WITH_DENSE_SIGNAL`** |

Mean v (descriptive): FL≈0.337, BL≈0.399, UU≈0.385.  
Binary accept rates (secondary): FL 0.30, BL 0.375, UU≈0.190.  
Integrity problems: none. Canary soundness: OK_OR_UNKNOWN.

---

## 7. SHIP GATE

| # | Predicate | Result |
|---|---|---|
| 1 | Pool 50 + fingerprint + recalc | PASS |
| 2 | Zero-modify existing files vs C tip | PASS (`git diff dcd0eed --name-only` empty; only new paths) |
| 3 | Readout self-test + pre-run freeze | PASS |
| 4 | Smoke 3×1 + three arm verdicts + single readout | PASS |
| 5 | pytest/cargo/gate_f4 (see SPEC) | PASS* (inherited head_parity note) |
| 6 | Commit on `fracflat/grok-20260710`, no push | PASS (at commit) |
| 7 | HANDOFF + this report | PASS |

---

## 8. Ceiling

**ADDRESSED.** Null is a valid pre-registered result. Merge/analysis authority remains with the orchestrator. **No push.**
