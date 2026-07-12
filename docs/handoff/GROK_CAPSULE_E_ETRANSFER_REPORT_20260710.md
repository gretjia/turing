# CAPSULE E — E-transfer Stage Market vs Atomic (Confirmatory) Report

**Status ceiling: ADDRESSED** (implementer delivery; not CLOSED / RELEASED / RATIFIED).  
**Nature: confirmatory experiment with orchestrator-frozen prereg (§4).**  
**Language ban: no “learned a function” / “学到函数” claims.** Interpretation authority is with the orchestrator.

| Item | Value |
|---|---|
| Worktree | `/home/zephryj/turingos_backup/work/grok_etransfer` |
| Branch | `etransfer/grok-20260710` |
| Base (C tip) | `dcd0eed5ca49cef74b8a9c25153c4e9d9a8c991f` |
| C HANDOFF head | `aae97ca1fe8955fc43c65801a7061c29824a1f6b` (ancestor of base) |
| Dispatch | `CAPSULE_E_ETRANSFER_grok_20260710.md` |
| Official outcome | **`NOT_RUN_STARVED`** |

---

## 1. Question (frozen)

B′ showed price levels do not transfer across distribution shift. This experiment tests whether **stage-level statistics** (composable sub-decision Q under a GLOBAL bucket) transfer to unseen task families better than an **atomic 12-route** market under the same GLOBAL bucket and fractional reward.

---

## 2. Design (executed as frozen)

| Element | Implementation |
|---|---|
| Pool | S01 ∪ S02 (100 instances) |
| Family | `instance_id` prefix before `__` |
| Split | TRAIN if first byte of `SHA256("etransfer-split.v1"‖family)` even; HELDOUT if odd |
| Ranking | Within family: historical accept-pass DESC (stageA 5 + stageBprime 4), then `instance_id` ASC; ≤25 per side |
| Stream | All TRAIN (family name ASC) then all HELDOUT |
| Arm **T** | depth-k staged market; `domain_bucket` forced GLOBAL (`task_family="GLOBAL"` → `global`); τ=0.5; `--fractional-reward`; cold start; live backup |
| Arm **A** | live_driver 12-route flat; process-local GLOBAL domain_bucket; τ=0.5; `--fractional-reward`; cold start; live backup |
| Judgment domain | HELDOUT only |
| Metric | verify-side pass fraction \(v \in [0,1]\) |
| H-E1 | T > A on HELDOUT, Wilcoxon signed-rank exact one-sided, α=0.05 |

**Manifest:** `tools/econ_lab/runs/etransfer_20260710/etransfer_split_manifest.json`  
- TRAIN families: django, matplotlib, pylint-dev, sphinx-doc, sympy (25 tasks)  
- HELDOUT families: astropy, psf, pydata, pytest-dev, scikit-learn (25 tasks)  
- file sha256 `7564bb1c…` · fingerprint `1bc6725c…`

---

## 3. SPEC GATE

| # | Predicate | Result |
|---|---|---|
| 1 | Constitution sha + governance GREEN + C `blocked=[]` | **PASS** |
| 2 | ADR-ECON-005 draft / 006 / 003 + CAPSULE B memo | **PASS** |
| 3 | pytest + cargo `turing-economy` + gate_f4 | **PASS** |

---

## 4. Implementation (NEW FILES ONLY)

| Path | Role |
|---|---|
| `tools/econ_lab/depthk/etransfer_build_split.py` | Family split + stream manifest |
| `tools/econ_lab/depthk/etransfer_driver.py` | T-arm GLOBAL stage market (imports depth_driver helpers; does not edit it) |
| `tools/econ_lab/depthk/etransfer_flat_driver.py` | A-arm GLOBAL flat wrapper (process-local monkeypatch of `derive_domain_bucket` / multi-shard load; does not edit live_driver.py) |
| `tools/econ_lab/depthk/etransfer_readout.py` | Prereg readout (frozen sha before first real call) |
| `tools/econ_lab/run_etransfer.sh` | Launcher (arm concurrency 2, smoke/full) |
| `tools/econ_lab/runs/etransfer_20260710/` | Artifacts root `{T,A,smoke}/` + readout |

`git diff <C-tip> --name-only` is empty for tracked paths; only new allowed paths were added.

---

## 5. Prereg freeze

| Field | Value |
|---|---|
| Readout sha256 | `70fe44a80dd5c23e13b808a270638a12cabee44bc22a02e37735e798f021831b` |
| Frozen at (UTC) | `2026-07-10T06:00:51Z` |
| Before first real call | **true** (smoke started after freeze record) |
| Self-test | `SELF_TEST_PASS` (all four outcomes + floors) |
| Readouts after data | **exactly one** → `ETRANSFER_READOUT.json` |

---

## 6. Smoke

1 TRAIN task × 2 arms (`django__django-10999`).

| Arm | domain_bucket | fractional | note |
|---|---|---|---|
| T | `global` | true | stage chain + 3 credit events; sample \(v \approx 0.667\) |
| A | `global` | true | flat settle; same instance |

`GLOBAL_KEY_PROOF PASS`.

---

## 7. Full run

| Arm | Status | Tasks | Worker calls | domain |
|---|---|---:|---:|---|
| T | DONE | 50 | 50 | `global` on every task; RPU `route_domain=global` |
| A | DONE | 50 | 40 | `domain_buckets_observed=["global"]` |

Budget used **92 / 115** (smoke 2 + full T 50 + full A 40).

Arm concurrency 2; harness `--max_workers 1` (driver default).

---

## 8. Prereg readout (once)

### Starvation floors

| Arm | Floor | Result |
|---|---|---|
| **T** | each stage node TRAIN \(N \ge 5\) | **PASS** — all six nodes \(N \in [5,12]\) |
| **A** | per-route TRAIN \(N\) median \(\ge 3\) | **FAIL** — median \(= 1.0\) |

**Official outcome: `NOT_RUN_STARVED`.** H-E1 not judged.

Note (does not change outcome): frozen A check keyed on `selected_route_id` (instance-scoped string). Recompute with `selected_arm::selected_lineage` over the same TRAIN settlements also yields median \(N=1.0\) (still STARVED).

### Quality floors (secondary; not used after starvation fail)

Settled fraction \(0.8\times\) planned failed on multiple arm/side cells (e.g. T TRAIN 17/25, T HELDOUT 18/25, A TRAIN 17/25). Would map to `NOT_RUN_INSUFFICIENT` if starvation had passed.

### Descriptive only (no significance)

| Side | mean \(v\) T | mean \(v\) A |
|---|---:|---:|
| TRAIN | ~0.533 | ~0.230 |
| HELDOUT | ~0.440 | ~0.502 |

Paired HELDOUT \(n=17\) diffs; frozen Wilcoxon one-sided \(p=0.5\) (not used under NOT_RUN).

Credit assignment v0 equal-share across stage nodes (CAPSULE B memo R1 ceiling) applies on T.

---

## 9. SHIP GATE

| # | Predicate | Result |
|---|---|---|
| 1 | Split manifest + recompute | **PASS** |
| 2 | Existing files zero modify | **PASS** |
| 3 | GLOBAL evidence both arms | **PASS** |
| 4 | Readout self-test + freeze before first call | **PASS** |
| 5 | Smoke + full + one readout | **PASS** |
| 6 | Tests green; commit; no push | **PASS** (at commit) |
| 7 | HANDOFF + this report | **PASS** |

`NOT_RUN_STARVED` is a valid prereg terminal mapping (not a runtime BLOCKED). Confirmatory claim H-E1 is **not** supported because floors failed.

---

## 10. Deliverables

- `HANDOFF_CAPSULE_E.json`
- `docs/handoff/GROK_CAPSULE_E_ETRANSFER_REPORT_20260710.md`
- `tools/econ_lab/runs/etransfer_20260710/{T,A,smoke,ETRANSFER_READOUT.json,etransfer_split_manifest.json}`
- New `etransfer_*` drivers / readout / `run_etransfer.sh`

**No push. No merge. Ceiling ADDRESSED only.**
