# CAPSULE C — Fractional Verify Reward Substrate Report (2026-07-10)

**Status ceiling: ADDRESSED** (implementer; no CLOSED/RELEASED/RATIFIED claims).  
**Nature: base construction only — no experimental claims.**

**Worktree:** `/home/zephryj/turingos_backup/work/grok_fractional`  
**Branch:** `fractional/grok-20260710`  
**Baseline:** `4fb5263`  
**Dispatch:** `CAPSULE_C_FRACTIONAL_grok_20260710.md` sha `23e8608b…`  
**Spec:** ADR-ECON-006 (proposed)

D/E capsules fork from this delivery commit.

---

## 1. What was implemented (ADR-ECON-006)

| Item | Location |
|---|---|
| `S` as Q32.32 non-negative sum; `Q_eff=(P·N0+S)/(N0+N)` | `crates/turing-economy/src/routing_fold.rs` `NodeState` |
| `verdict_fraction_q32` ADDITIVE on `RoutingPriorUpdated` (v1 absent → binary fallback) | `lib.rs` + schema v2 fractional constructor |
| Exact clawback `S ← S − v_original` | fold outstanding map stores fraction |
| Mode mix hard error (binary vs fractional) | `EconomyError::RoutingFoldRewardModeMix` |
| CLI `build-routing-prior-updated` accepts optional fraction | `econ_fold_cli.rs` (old requests byte-path unchanged for binary) |
| `--fractional-reward` on flat + stage drivers | `live_driver.py`, `depthk/depth_driver.py` |
| `verify_pass_fraction` on live_split_verifier | `tools/econ_lab/verifier/live_split_verifier.py` |

Hand fixture (unit test): `v=0.5` twice → `S=Q32_ONE`, `Q_eff=(0.5+1.0)/3=0.5`.

---

## 2. SPEC GATE

| # | Result | Evidence |
|---|---|---|
| Constitution sha | PASS | `a0174ef8…` OK |
| Governance | PASS | GREEN |
| ADR-ECON-006 + 003 + 005 draft read | PASS | paths under PROJECT_PLAN / docs/handoff |
| Baseline pytest + cargo + F4 | PASS | suite green at entry and ship |

---

## 3. Smoke (budget ≤6)

| Path | Calls | Result |
|---|---:|---|
| flat `live_driver` initial 2 tasks | 1 | fractional meta True; v=0 applied |
| flat `live_driver` 4 tasks (hunt nontrivial) | 4 | **nontrivial** `astropy__astropy-14369` `verify_pass_fraction≈0.9947`, `verdict_fraction_q32=4272302560` |
| stage `depth_driver` 1 task | 1 | worker+score ran, fractional_reward=True; credit withheld (`not_enough_tests`) |
| stage offline S accum (CLI only, 0 calls) | 0 | three stage nodes n=2, s_q32=Q32_ONE after two half-rewards |

**Total real worker calls: 6 / 6.**

Nontrivial fraction observed: **true** (flat path).

Artifacts: `tools/econ_lab/runs/fractional_smoke_20260710/{flat,flat_more,stage,stage_offline_s_accum}/`.

---

## 4. SHIP GATE

| # | Predicate | Result |
|---|---|---|
| 1 | cargo green + fixture math + mode mix + clawback | PASS |
| 2 | flat fractional full chain + stage smoke + offline S accum | PASS (with stage credit note) |
| 3 | pytest suite + gate_f4 | PASS |
| 4 | commit on branch, subject ≤50, no push | PASS (at commit) |
| 5 | HANDOFF_CAPSULE_C.json | PASS |
| 6 | this report | PASS |

---

## 5. Notes for D/E consumers

1. Default remains **binary**; pass `--fractional-reward` explicitly.
2. Fractional events use `schema_id=routing_prior_updated.v2` and identity hash schema v2.
3. Mixing binary and fractional events on one fold tape is a **hard error**.
4. Stage real smoke in this budget window did not credit-assign (verify side empty on that task); offline CLI proves stage-key S accumulation under fractional events.
5. **No significance claims.** Merge authority remains with orchestrator.

---

## 6. Ceiling

**ADDRESSED.** Ready for CAPSULE D/E to base-branch from this tip.
