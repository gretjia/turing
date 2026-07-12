#!/usr/bin/env python3
"""P3-E3 frozen statistical readout (CAPSULE A §4 preregistration).

FROZEN before any S03 real full-run verdict is produced. Judgment logic must
implement CAPSULE A §4 verbatim; defects found at readout time are recorded as
BLOCKED / dated addenda, never silently patched.

Arms (all on S03 stream, tau=0.5, same S01+S02 pooled priors):
  L  live backup throughout
  Z  frozen backup throughout (--frozen-backup)
  R  live backup + fold reset at task index 22 (--reset-at-task-index 22)

Pre-registered hypotheses, paired exact one-sided McNemar (binomial), Bonferroni
alpha' = 0.05/2 = 0.025, judgment domain = PHASE2 tasks only (28 instances):
  H-E3a: L > Z
  H-E3b: L > R

Quality floors (any fail -> NOT_RUN, no partial judgment):
  each arm full-stream settled >= 40/50 AND PHASE2 settled >= 22/28.

Outcome map (frozen):
  both supported  -> CONTINUITY_AND_FLUCTUATION_SUPPORTED
  only E3a        -> FLUCTUATION_YES_CONTINUITY_UNPROVEN
  only E3b        -> CONTINUITY_YES_VS_FROZEN_UNPROVEN
  neither         -> NULL_HONEST_RECORD

Secondary (descriptive only; no significance claims): t½ price re-convergence
half-life on PHASE2 routes; PHASE1 three-arm rates; canary counts; L-arm
post-switch rank-inversion event table.

Ceiling: ADDRESSED. Null is a valid result.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ARMS = ["L", "Z", "R"]
ALPHA = 0.05
ALPHA_PRIME = ALPHA / 2  # 0.025
MIN_SETTLED_FULL = 40
MIN_SETTLED_PHASE2 = 22
PLANNED_N = 50
PHASE2_N = 28
SWITCH_INDEX = 22

PHASE1_FAMILIES = frozenset({"astropy", "django", "pydata", "pytest-dev"})
PHASE2_FAMILIES = frozenset({"matplotlib", "scikit-learn", "sphinx-doc", "sympy"})


def family_of(instance_id: str) -> str:
    return instance_id.split("__", 1)[0]


def load_stream_phase2_ids(manifest_path: Path | None) -> list[str] | None:
    if manifest_path is None or not manifest_path.exists():
        return None
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "phase2_instance_ids" in data:
        return list(data["phase2_instance_ids"])
    if isinstance(data, dict) and "instance_ids" in data:
        ids = list(data["instance_ids"])
        return ids[SWITCH_INDEX:]
    return None


def load_arm(path: Path) -> dict:
    v = json.loads(path.read_text(encoding="utf-8"))
    per_instance = {}
    task_order = []
    for task in v.get("tasks", []):
        iid = task.get("instance_id")
        task_order.append(iid)
        sv = None
        verify = None
        for d in task.get("dispatches", []):
            if d.get("settlement_verdict_resolved") is not None:
                sv = d["settlement_verdict_resolved"]
            if "verify_verdict" in d:
                verify = d["verify_verdict"]
            lsv = d.get("live_split_verdict") or {}
            if verify is None and isinstance(lsv, dict) and "verify_verdict" in lsv:
                verify = lsv["verify_verdict"]
        route = task.get("budget_suggestion", {}).get("route_id", "")
        per_instance[iid] = {
            "pass": (bool(sv) if sv is not None else None),
            "route": route,
            "verify": verify,
            "family": family_of(iid) if isinstance(iid, str) else None,
        }
    vs = v.get("verifier_summary", {})
    meta = v.get("stage_b_prime_meta", {})
    return {
        "per_instance": per_instance,
        "task_order": task_order,
        "meta": meta,
        "canary_count": vs.get("canary_count"),
        "not_enough_tests_count": vs.get("not_enough_tests_count"),
        "raw": v,
    }


def integrity(arms: dict, priors_sha: str | None) -> list[str]:
    problems = []
    if arms["Z"]["meta"].get("frozen_backup") is not True:
        problems.append("arm Z frozen_backup is not true")
    for a in ("L", "R"):
        if arms[a]["meta"].get("frozen_backup") is True:
            problems.append(f"arm {a} unexpectedly frozen")
    if arms["R"]["meta"].get("reset_at_task_index") != SWITCH_INDEX:
        problems.append(
            f"arm R reset_at_task_index != {SWITCH_INDEX}: "
            f"{arms['R']['meta'].get('reset_at_task_index')}"
        )
    if arms["R"]["meta"].get("reset_at") != SWITCH_INDEX:
        problems.append(
            f"arm R reset_at (applied) != {SWITCH_INDEX}: {arms['R']['meta'].get('reset_at')}"
        )
    for a in ("L", "Z"):
        if arms[a]["meta"].get("reset_at_task_index") not in (None,):
            # L/Z must not request a reset
            if arms[a]["meta"].get("reset_at_task_index") is not None:
                problems.append(f"arm {a} unexpectedly has reset_at_task_index")
    if priors_sha:
        for a in ARMS:
            if arms[a]["meta"].get("priors_sha256") != priors_sha:
                problems.append(f"arm {a} priors_sha256 != pinned priors file sha")
    sets = {a: set(arms[a]["per_instance"]) for a in ARMS}
    if len(set(map(frozenset, sets.values()))) != 1:
        problems.append("arms do not share an identical instance set")
    return problems


def phase_filter(per_instance: dict, phase2_ids: set[str] | None, phase: str) -> dict:
    out = {}
    for iid, rec in per_instance.items():
        fam = rec.get("family") or family_of(iid)
        if phase == "phase2":
            if phase2_ids is not None:
                if iid in phase2_ids:
                    out[iid] = rec
            elif fam in PHASE2_FAMILIES:
                out[iid] = rec
        else:  # phase1
            if phase2_ids is not None:
                if iid not in phase2_ids:
                    out[iid] = rec
            elif fam in PHASE1_FAMILIES:
                out[iid] = rec
    return out


def paired_test(left: dict, right: dict) -> dict:
    """Exact one-sided McNemar: H1 left > right, P(X >= b | n=b+c, p=0.5)."""
    b = c = 0
    for iid, lr in left.items():
        rr = right.get(iid)
        if rr is None or lr["pass"] is None or rr["pass"] is None:
            continue
        if lr["pass"] and not rr["pass"]:
            b += 1
        elif not lr["pass"] and rr["pass"]:
            c += 1
    n = b + c
    p = sum(math.comb(n, i) for i in range(b, n + 1)) / (2 ** n) if n else None
    return {
        "b_left_pass_right_fail": b,
        "c_left_fail_right_pass": c,
        "n_discordant": n,
        "p_one_sided": p,
    }


def arm_rate(per_instance: dict) -> dict:
    settled = [r["pass"] for r in per_instance.values() if r["pass"] is not None]
    return {
        "n_settled": len(settled),
        "k_pass": sum(bool(x) for x in settled),
        "rate": (sum(bool(x) for x in settled) / len(settled)) if settled else None,
        "infra_null": sum(1 for r in per_instance.values() if r["pass"] is None),
        "n_total": len(per_instance),
    }


def t_half_descriptive(arm: dict, phase2_ids: set[str] | None) -> dict:
    """Descriptive t½ approximation (Phase 3 §4): for each route that appears in PHASE2,
    estimate how many PHASE2 settlements until |Q_eff - empirical| halves from the
    post-switch starting gap. Uses analysis-side Decision 6 recompute; no significance.
    """
    p2 = phase_filter(arm["per_instance"], phase2_ids, "phase2")
    # Preserve stream order from the arm's task_order when available.
    order = [iid for iid in arm.get("task_order", []) if iid in p2]
    if not order:
        order = sorted(p2)
    # Track per-route S/N after switch; P0 from first observed route's absence -> 0.5
    S: dict[str, float] = {}
    N: dict[str, int] = {}
    first_gap: dict[str, float] = {}
    half_at: dict[str, int | None] = {}
    empirical: dict[str, list[int]] = {}

    # First pass: collect empirical per-route settle outcomes over PHASE2
    for iid in order:
        rec = p2[iid]
        parts = (rec.get("route") or "").split("::")
        route = f"{parts[1]}::{parts[2]}" if len(parts) == 3 else None
        if route is None or rec["pass"] is None:
            continue
        empirical.setdefault(route, []).append(int(bool(rec["pass"])))

    true_rate = {
        r: (sum(vs) / len(vs) if vs else None) for r, vs in empirical.items()
    }

    for idx, iid in enumerate(order):
        rec = p2[iid]
        parts = (rec.get("route") or "").split("::")
        route = f"{parts[1]}::{parts[2]}" if len(parts) == 3 else None
        if route is None or rec["pass"] is None:
            continue
        if route not in S:
            S[route] = 0.0
            N[route] = 0
            # At first appearance post-switch, Q_eff ≈ P (no post-reset history);
            # without the true injected P per route here we use 0.5 as descriptive default
            # when priors not supplied to this helper (caller may refine).
            q0 = 0.5
            tr = true_rate.get(route)
            if tr is not None:
                first_gap[route] = abs(q0 - tr)
                half_at[route] = None
        N[route] += 1
        S[route] += int(bool(rec["pass"]))
        q = (0.5 * 1 + S[route]) / (1 + N[route])  # Decision 6 with P=0.5 descriptive
        tr = true_rate.get(route)
        if tr is None or route not in first_gap:
            continue
        gap0 = first_gap[route]
        if gap0 <= 0:
            half_at[route] = 0
            continue
        if half_at[route] is None and abs(q - tr) <= gap0 / 2:
            half_at[route] = N[route]

    return {
        "per_route_settlements_to_half_gap": half_at,
        "note": "descriptive only; uses P=0.5 baseline for Q_eff recompute when priors not inlined",
    }


def rank_inversions_descriptive_L(l_arm: dict, priors: dict, phase2_ids: set[str] | None) -> list[dict]:
    """Descriptive: bottom-half prior routes attaining top-1 Q_eff after the switch on L."""
    p0 = dict(priors)
    if not p0:
        return []
    order_routes = sorted(p0, key=lambda r: -p0[r])
    bottom_half = set(order_routes[len(order_routes) // 2 :])
    S = {r: 0.0 for r in p0}
    N = {r: 0 for r in p0}
    events = []
    p2 = phase_filter(l_arm["per_instance"], phase2_ids, "phase2")
    seq = [iid for iid in l_arm.get("task_order", []) if iid in p2] or sorted(p2)
    for idx, iid in enumerate(seq):
        rec = p2[iid]
        parts = (rec.get("route") or "").split("::")
        route = f"{parts[1]}::{parts[2]}" if len(parts) == 3 else None
        if route is None or rec.get("verify") is None:
            continue
        if route not in p0:
            continue
        N[route] += 1
        S[route] += int(bool(rec["verify"]))
        q = {r: (p0[r] * 1 + S[r]) / (1 + N[r]) for r in p0}
        top = max(q, key=lambda r: q[r])
        if top in bottom_half and N[top] > 0:
            events.append(
                {
                    "phase2_ordinal": idx,
                    "instance_id": iid,
                    "route": top,
                    "q_eff": round(q[top], 4),
                }
            )
            bottom_half.discard(top)
    return events


def judge(arms: dict, priors: dict, *, priors_sha: str | None, phase2_ids: list[str] | None) -> dict:
    problems = integrity(arms, priors_sha)
    if problems:
        return {"p3e3_outcome": "NOT_RUN_INTEGRITY", "problems": problems}

    p2_set = set(phase2_ids) if phase2_ids is not None else None
    stats_full = {a: arm_rate(arms[a]["per_instance"]) for a in ARMS}
    stats_p2 = {
        a: arm_rate(phase_filter(arms[a]["per_instance"], p2_set, "phase2")) for a in ARMS
    }
    stats_p1 = {
        a: arm_rate(phase_filter(arms[a]["per_instance"], p2_set, "phase1")) for a in ARMS
    }

    floor_fail = []
    for a in ARMS:
        if stats_full[a]["n_settled"] < MIN_SETTLED_FULL:
            floor_fail.append(f"{a} full settled {stats_full[a]['n_settled']} < {MIN_SETTLED_FULL}")
        if stats_p2[a]["n_settled"] < MIN_SETTLED_PHASE2:
            floor_fail.append(f"{a} phase2 settled {stats_p2[a]['n_settled']} < {MIN_SETTLED_PHASE2}")
    if floor_fail:
        return {
            "p3e3_outcome": "NOT_RUN_INSUFFICIENT_SETTLEMENTS",
            "floor_failures": floor_fail,
            "arm_stats_full": stats_full,
            "arm_stats_phase2": stats_p2,
            "arm_stats_phase1": stats_p1,
        }

    l_p2 = phase_filter(arms["L"]["per_instance"], p2_set, "phase2")
    z_p2 = phase_filter(arms["Z"]["per_instance"], p2_set, "phase2")
    r_p2 = phase_filter(arms["R"]["per_instance"], p2_set, "phase2")

    tests = {
        "H_E3a_L_gt_Z": paired_test(l_p2, z_p2),
        "H_E3b_L_gt_R": paired_test(l_p2, r_p2),
    }
    supported = {
        h: (t["p_one_sided"] is not None and t["p_one_sided"] < ALPHA_PRIME)
        for h, t in tests.items()
    }
    if supported["H_E3a_L_gt_Z"] and supported["H_E3b_L_gt_R"]:
        outcome = "CONTINUITY_AND_FLUCTUATION_SUPPORTED"
    elif supported["H_E3a_L_gt_Z"]:
        outcome = "FLUCTUATION_YES_CONTINUITY_UNPROVEN"
    elif supported["H_E3b_L_gt_R"]:
        outcome = "CONTINUITY_YES_VS_FROZEN_UNPROVEN"
    else:
        outcome = "NULL_HONEST_RECORD"

    canaries = {a: arms[a]["canary_count"] for a in ARMS}
    soundness_flag = any(
        isinstance(c, int) and c > 5 for c in canaries.values()
    )

    return {
        "p3e3_outcome": outcome,
        "arm_stats_full": stats_full,
        "arm_stats_phase2": stats_p2,
        "arm_stats_phase1": stats_p1,
        "tests": tests,
        "supported": supported,
        "alpha_prime": ALPHA_PRIME,
        "judgment_domain": "PHASE2",
        "t_half_descriptive_L": t_half_descriptive(arms["L"], p2_set),
        "rank_inversions_descriptive_L_phase2": rank_inversions_descriptive_L(
            arms["L"], priors, p2_set
        ),
        "canaries": canaries,
        "soundness_flag": soundness_flag,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--run-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "runs/p3e3_20260709",
    )
    ap.add_argument(
        "--priors",
        type=Path,
        default=Path(__file__).parent / "p3e3_priors_s01s02.json",
    )
    ap.add_argument(
        "--stream-manifest",
        type=Path,
        default=Path(__file__).parent / "p3e3_stream_manifest.json",
    )
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()

    priors_sha = None
    priors_map = {}
    if args.priors.exists():
        raw = args.priors.read_bytes()
        import hashlib

        priors_sha = hashlib.sha256(raw).hexdigest()
        parsed = json.loads(raw.decode("utf-8"))
        priors_map = parsed.get("priors", parsed) if isinstance(parsed, dict) else {}

    phase2_ids = load_stream_phase2_ids(args.stream_manifest)
    arms = {}
    for a in ARMS:
        p = args.run_root / f"{a}/verdict.json"
        if not p.exists():
            result = {
                "schema": "econ_lab.p3e3_readout.v1",
                "p3e3_outcome": "NOT_RUN_MISSING_VERDICT",
                "missing": str(p),
                "status_ceiling": "ADDRESSED",
            }
            text = json.dumps(result, indent=2, sort_keys=True)
            print(text)
            if args.out:
                args.out.write_text(text + "\n", encoding="utf-8")
            return 1
        arms[a] = load_arm(p)

    result = {
        "schema": "econ_lab.p3e3_readout.v1",
        "frozen_by": "CAPSULE_A_P3E3_grok_20260709 §4",
        **judge(arms, priors_map, priors_sha=priors_sha, phase2_ids=phase2_ids),
        "status_ceiling": "ADDRESSED",
    }
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    return 0


def _mk(
    passes: dict,
    *,
    frozen: bool = False,
    reset_at_task_index=None,
    reset_at=None,
    sha: str = "deadbeef",
    order: list[str] | None = None,
) -> dict:
    per = {
        i: {
            "pass": p,
            "route": "x::armB::kimi",
            "verify": p,
            "family": family_of(i),
        }
        for i, p in passes.items()
    }
    return {
        "per_instance": per,
        "task_order": order or list(passes.keys()),
        "meta": {
            "priors_sha256": sha,
            "frozen_backup": frozen,
            "reset_at_task_index": reset_at_task_index,
            "reset_at": reset_at,
        },
        "canary_count": 0,
        "not_enough_tests_count": 0,
    }


def self_test() -> int:
    # Build 22 PHASE1 + 28 PHASE2 synthetic instance ids.
    p1 = [f"django__django-{10000 + i}" for i in range(8)]
    p1 += [f"astropy__astropy-{20000 + i}" for i in range(5)]
    p1 += [f"pydata__xarray-{30000 + i}" for i in range(6)]
    p1 += [f"pytest-dev__pytest-{40000 + i}" for i in range(3)]
    assert len(p1) == 22
    p2 = [f"matplotlib__matplotlib-{50000 + i}" for i in range(7)]
    p2 += [f"scikit-learn__scikit-learn-{60000 + i}" for i in range(7)]
    p2 += [f"sphinx-doc__sphinx-{70000 + i}" for i in range(7)]
    p2 += [f"sympy__sympy-{80000 + i}" for i in range(7)]
    assert len(p2) == 28
    all_ids = p1 + p2
    sha = "abc123"
    pri = {"armB::kimi": 0.6, "armA::qwen": 0.1}

    def full_passes(k_p2_pass: int, k_p1_pass: int = 10) -> dict:
        d = {}
        for i, iid in enumerate(p1):
            d[iid] = i < k_p1_pass
        for i, iid in enumerate(p2):
            d[iid] = i < k_p2_pass
        return d

    # 1. Both H-E3a and H-E3b supported: L strong on PHASE2, Z/R weak.
    l = _mk(full_passes(20), sha=sha, order=all_ids)
    z = _mk(full_passes(5), frozen=True, sha=sha, order=all_ids)
    r = _mk(
        full_passes(5),
        reset_at_task_index=22,
        reset_at=22,
        sha=sha,
        order=all_ids,
    )
    out = judge(
        {"L": l, "Z": z, "R": r},
        pri,
        priors_sha=sha,
        phase2_ids=p2,
    )
    assert out["p3e3_outcome"] == "CONTINUITY_AND_FLUCTUATION_SUPPORTED", out["p3e3_outcome"]

    # 2. Only E3a: L > Z, L == R on PHASE2.
    r2 = _mk(
        full_passes(20),
        reset_at_task_index=22,
        reset_at=22,
        sha=sha,
        order=all_ids,
    )
    out = judge({"L": l, "Z": z, "R": r2}, pri, priors_sha=sha, phase2_ids=p2)
    assert out["p3e3_outcome"] == "FLUCTUATION_YES_CONTINUITY_UNPROVEN", out["p3e3_outcome"]

    # 3. Only E3b (anomaly shape): L > R, L == Z.
    z3 = _mk(full_passes(20), frozen=True, sha=sha, order=all_ids)
    r3 = _mk(
        full_passes(5),
        reset_at_task_index=22,
        reset_at=22,
        sha=sha,
        order=all_ids,
    )
    out = judge({"L": l, "Z": z3, "R": r3}, pri, priors_sha=sha, phase2_ids=p2)
    assert out["p3e3_outcome"] == "CONTINUITY_YES_VS_FROZEN_UNPROVEN", out["p3e3_outcome"]

    # 4. Null: all equal.
    l4 = _mk(full_passes(8), sha=sha, order=all_ids)
    z4 = _mk(full_passes(8), frozen=True, sha=sha, order=all_ids)
    r4 = _mk(
        full_passes(8),
        reset_at_task_index=22,
        reset_at=22,
        sha=sha,
        order=all_ids,
    )
    out = judge({"L": l4, "Z": z4, "R": r4}, pri, priors_sha=sha, phase2_ids=p2)
    assert out["p3e3_outcome"] == "NULL_HONEST_RECORD", out["p3e3_outcome"]

    # 5. Floor: PHASE2 settled < 22 -> NOT_RUN
    def sparse_p2() -> dict:
        d = full_passes(0, k_p1_pass=20)
        # only 15 of phase2 settled (rest None)
        for i, iid in enumerate(p2):
            d[iid] = True if i < 15 else None
        return d

    l5 = _mk(sparse_p2(), sha=sha, order=all_ids)
    out = judge({"L": l5, "Z": z4, "R": r4}, pri, priors_sha=sha, phase2_ids=p2)
    assert out["p3e3_outcome"] == "NOT_RUN_INSUFFICIENT_SETTLEMENTS", out["p3e3_outcome"]

    # 6. Integrity: Z not frozen
    z6 = _mk(full_passes(5), frozen=False, sha=sha, order=all_ids)
    out = judge({"L": l, "Z": z6, "R": r}, pri, priors_sha=sha, phase2_ids=p2)
    assert out["p3e3_outcome"] == "NOT_RUN_INTEGRITY", out["p3e3_outcome"]

    # 7. Exact binomial sanity: b=8, c=1 -> p = 10/512
    left = {f"matplotlib__m-{i}": {"pass": True, "route": "", "verify": None} for i in range(8)}
    left.update({f"matplotlib__n-{i}": {"pass": False, "route": "", "verify": None} for i in range(1)})
    right = {f"matplotlib__m-{i}": {"pass": False, "route": "", "verify": None} for i in range(8)}
    right.update({f"matplotlib__n-{i}": {"pass": True, "route": "", "verify": None} for i in range(1)})
    t = paired_test(left, right)
    assert abs(t["p_one_sided"] - 10 / 512) < 1e-12, t

    # 8. alpha' pin
    assert ALPHA_PRIME == 0.025

    print("P3E3_READOUT_SELF_TEST_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
