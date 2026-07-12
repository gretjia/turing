#!/usr/bin/env python3
"""Fracflat frozen statistical readout (CAPSULE D §4 preregistration).

FROZEN before any real full-run verdict is produced. Judgment logic implements
CAPSULE D §4 verbatim; defects found at readout time are recorded as BLOCKED /
dated addenda, never silently patched.

Arms (all 12-route flat market, cold P=0.5):
  FL  --fractional-reward, live backup, tau=0.5
  BL  binary (no --fractional-reward), live backup, tau=0.5
  UU  tau=inf uniform, no fractional

Primary metric: per-task verify-side pass fraction v ∈ [0,1]
  (all arms including BL — BL uses v for metric only, not fold if binary).

Pre-registered hypotheses, paired Wilcoxon signed-rank exact one-sided,
Bonferroni α' = 0.05/2 = 0.025:
  H-D1: FL > UU
  H-D2: FL > BL

Quality floor: each arm ≥40/50 tasks with computable v; else NOT_RUN.

Outcome map (frozen):
  both supported  -> PRICE_LEARNING_WORKS_WITH_DENSE_SIGNAL
  only H-D1       -> LEARNING_YES_INGREDIENT_UNCLEAR
  only H-D2       -> INGREDIENT_YES_VS_UNIFORM_UNPROVEN
  neither         -> NULL_EVEN_WITH_DENSE_SIGNAL

Secondary (descriptive only; no significance): FL allocation entropy trajectory,
OOS allocation quality (BL/UU as external truth), canary counts, rank-inversion
event table.

Ceiling: ADDRESSED. Null is a valid result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ARMS = ["FL", "BL", "UU"]
ALPHA = 0.05
ALPHA_PRIME = ALPHA / 2  # 0.025
MIN_SETTLED = 40
PLANNED_N = 50


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_arm(path: Path) -> dict[str, Any]:
    v = json.loads(path.read_text(encoding="utf-8"))
    per_instance: dict[str, dict[str, Any]] = {}
    task_order: list[str] = []
    for task in v.get("tasks") or []:
        iid = task.get("instance_id")
        if not isinstance(iid, str):
            continue
        task_order.append(iid)
        v_frac = None
        binary_accept = None
        verify_binary = None
        route = (task.get("budget_suggestion") or {}).get("route_id", "")
        for d in task.get("dispatches") or []:
            if d.get("settlement_verdict_resolved") is not None:
                binary_accept = bool(d["settlement_verdict_resolved"])
            lsv = d.get("live_split_verdict") or {}
            if isinstance(lsv, dict):
                if "verify_pass_fraction" in lsv and lsv["verify_pass_fraction"] is not None:
                    v_frac = float(lsv["verify_pass_fraction"])
                if "verify_verdict" in lsv and lsv["verify_verdict"] is not None:
                    verify_binary = bool(lsv["verify_verdict"])
            # Some paths may put fraction on the dispatch itself
            if v_frac is None and d.get("verify_pass_fraction") is not None:
                v_frac = float(d["verify_pass_fraction"])
        # If fraction missing but verify binary present, map True->1.0 / False->0.0
        # only when harness produced a real binary verify (not infra-null).
        if v_frac is None and verify_binary is not None:
            # harness_error may leave verify false with empty tests — still a number
            v_frac = 1.0 if verify_binary else 0.0
        # Infra-null: no computable v
        if v_frac is None:
            # try scoring_result report absence
            pass
        per_instance[iid] = {
            "v": v_frac,
            "binary_accept": binary_accept,
            "verify_binary": verify_binary,
            "route": route,
        }
    meta = v.get("stage_b_prime_meta") or {}
    vs = v.get("verifier_summary") or {}
    return {
        "per_instance": per_instance,
        "task_order": task_order,
        "meta": meta,
        "canary_count": vs.get("canary_count"),
        "not_enough_tests_count": vs.get("not_enough_tests_count"),
        "raw": v,
        "real_worker_calls_made": v.get("real_worker_calls_made"),
        "task_count": v.get("task_count"),
    }


def extract_v(per_instance: dict[str, dict]) -> dict[str, float | None]:
    return {iid: rec.get("v") for iid, rec in per_instance.items()}


# ---------------------------------------------------------------------------
# Wilcoxon signed-rank exact one-sided
# ---------------------------------------------------------------------------


def _average_ranks(abs_vals: list[float]) -> list[float]:
    """Average ranks for |d|, 1-based ranks, ties get midrank."""
    n = len(abs_vals)
    order = sorted(range(n), key=lambda i: abs_vals[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs_vals[order[j + 1]] == abs_vals[order[i]]:
            j += 1
        # ranks i..j in 1-based sorted positions: (i+1)..(j+1)
        avg = (i + 1 + j + 1) / 2.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def wilcoxon_signed_rank_exact_one_sided(diffs: list[float]) -> dict[str, Any]:
    """Exact one-sided Wilcoxon signed-rank, H1: location of diffs > 0.

    Procedure:
      1. Drop zero differences.
      2. Rank |d_i| with average ranks for ties.
      3. W+ = sum of ranks where d_i > 0.
      4. Under H0 each sign is independent fair coin; p = P(W+ >= W+_obs)
         via exact subset-sum enumeration (DP).

    Returns dict with W_plus, n_nonzero, p_one_sided, n_pos, n_neg, n_zero.
    """
    n_zero = sum(1 for d in diffs if d == 0.0)
    nonzero = [d for d in diffs if d != 0.0]
    n = len(nonzero)
    if n == 0:
        return {
            "W_plus": 0.0,
            "n_nonzero": 0,
            "n_pos": 0,
            "n_neg": 0,
            "n_zero": n_zero,
            "p_one_sided": None,
            "method": "exact_empty",
        }

    abs_vals = [abs(d) for d in nonzero]
    ranks = _average_ranks(abs_vals)
    n_pos = sum(1 for d in nonzero if d > 0)
    n_neg = n - n_pos
    w_plus = sum(r for d, r in zip(nonzero, ranks) if d > 0)

    # Exact null: DP over subset sums of ranks (positive-sign contributions).
    # Use integer keys in half-rank units (ranks are k/2).
    scaled = [int(round(r * 2)) for r in ranks]
    w_obs_scaled = int(round(w_plus * 2))

    # ways[s] = number of sign assignments with scaled W+ == s
    ways: Counter[int] = Counter({0: 1})
    for s_r in scaled:
        nxt: Counter[int] = Counter()
        for s, c in ways.items():
            nxt[s] += c  # negative sign: rank not in W+
            nxt[s + s_r] += c  # positive sign
        ways = nxt

    total = 1 << n
    counted = sum(ways.values())
    if counted != total:
        # Should never happen
        raise RuntimeError(f"wilcoxon DP cardinality mismatch {counted} != {total}")

    ge = sum(c for s, c in ways.items() if s >= w_obs_scaled)
    p = ge / total

    return {
        "W_plus": w_plus,
        "n_nonzero": n,
        "n_pos": n_pos,
        "n_neg": n_neg,
        "n_zero": n_zero,
        "p_one_sided": p,
        "method": "exact_signed_rank_dp",
        "alpha_prime": ALPHA_PRIME,
        "supported": p is not None and p <= ALPHA_PRIME,
    }


def paired_wilcoxon(left_v: dict[str, float | None], right_v: dict[str, float | None]) -> dict[str, Any]:
    """Paired diffs d_i = v_left - v_right on instances where both v computable."""
    pairs = []
    ids = []
    for iid in sorted(set(left_v) & set(right_v)):
        lv, rv = left_v[iid], right_v[iid]
        if lv is None or rv is None:
            continue
        pairs.append(float(lv) - float(rv))
        ids.append(iid)
    result = wilcoxon_signed_rank_exact_one_sided(pairs)
    result["n_paired"] = len(pairs)
    result["mean_diff"] = (sum(pairs) / len(pairs)) if pairs else None
    result["median_diff"] = (
        sorted(pairs)[len(pairs) // 2] if pairs else None
    )
    return result


# ---------------------------------------------------------------------------
# Arm summaries / integrity / outcome
# ---------------------------------------------------------------------------


def arm_v_summary(per_instance: dict[str, dict]) -> dict[str, Any]:
    vals = [r["v"] for r in per_instance.values() if r.get("v") is not None]
    accepts = [r["binary_accept"] for r in per_instance.values() if r.get("binary_accept") is not None]
    return {
        "n_total": len(per_instance),
        "n_computable_v": len(vals),
        "mean_v": (sum(vals) / len(vals)) if vals else None,
        "n_binary_accept_settled": len(accepts),
        "k_binary_accept": sum(bool(x) for x in accepts),
        "binary_accept_rate": (sum(bool(x) for x in accepts) / len(accepts)) if accepts else None,
        "infra_null_v": sum(1 for r in per_instance.values() if r.get("v") is None),
    }


def integrity(arms: dict[str, dict]) -> list[str]:
    problems: list[str] = []
    # FL must record fractional_reward True
    if arms["FL"]["meta"].get("fractional_reward") is not True:
        problems.append("arm FL fractional_reward is not true")
    # BL/UU must not be fractional
    for a in ("BL", "UU"):
        if arms[a]["meta"].get("fractional_reward") is True:
            problems.append(f"arm {a} unexpectedly fractional_reward=true")
    # UU tau is uniform — meta may not record tau; soft check via run_label
    for a in ARMS:
        if arms[a]["meta"].get("frozen_backup") is True:
            problems.append(f"arm {a} unexpectedly frozen_backup")
    sets = {a: set(arms[a]["per_instance"]) for a in ARMS}
    # Instance sets should match stream; allow subset if some arms truncated
    if any(len(s) == 0 for s in sets.values()):
        problems.append("one or more arms have empty instance set")
    return problems


def map_outcome(h_d1: bool, h_d2: bool) -> str:
    if h_d1 and h_d2:
        return "PRICE_LEARNING_WORKS_WITH_DENSE_SIGNAL"
    if h_d1 and not h_d2:
        return "LEARNING_YES_INGREDIENT_UNCLEAR"
    if h_d2 and not h_d1:
        return "INGREDIENT_YES_VS_UNIFORM_UNPROVEN"
    return "NULL_EVEN_WITH_DENSE_SIGNAL"


def secondary_descriptive(arms: dict[str, dict]) -> dict[str, Any]:
    """Descriptive only — no significance claims (CAPSULE D §4)."""
    # FL allocation entropy trajectory: Shannon entropy of selected routes over stream.
    fl = arms["FL"]
    order = fl.get("task_order") or sorted(fl["per_instance"])
    route_counts: Counter[str] = Counter()
    entropy_traj = []
    for iid in order:
        rec = fl["per_instance"].get(iid) or {}
        route = rec.get("route") or ""
        if route:
            route_counts[route] += 1
        total = sum(route_counts.values())
        if total == 0:
            entropy_traj.append(None)
            continue
        h = 0.0
        for c in route_counts.values():
            p = c / total
            if p > 0:
                h -= p * math.log(p, 2)
        entropy_traj.append({"after_n": total, "H_bits": h, "n_distinct_routes": len(route_counts)})

    # Canary counts
    canaries = {a: arms[a].get("canary_count") for a in ARMS}

    # Rank-inversion events (descriptive): FL mean v vs route selection order not computed
    # deeply without Q_eff tape; report canary + route frequency only.
    route_freq = dict(sorted(route_counts.items(), key=lambda kv: (-kv[1], kv[0])))

    return {
        "fl_route_entropy_trajectory_tail": entropy_traj[-5:] if entropy_traj else [],
        "fl_route_frequency": route_freq,
        "canary_counts": canaries,
        "canary_soundness_flag": (
            "SOUNDNESS_FLAG"
            if any(isinstance(c, int) and c > 5 for c in canaries.values())
            else "OK_OR_UNKNOWN"
        ),
        "note": "Secondary metrics are descriptive only; no significance claims.",
    }


def run_readout(arm_paths: dict[str, Path], pool_sha: str | None = None) -> dict[str, Any]:
    arms = {a: load_arm(arm_paths[a]) for a in ARMS}
    problems = integrity(arms)

    summaries = {a: arm_v_summary(arms[a]["per_instance"]) for a in ARMS}
    floor_ok = all(summaries[a]["n_computable_v"] >= MIN_SETTLED for a in ARMS)

    fl_v = extract_v(arms["FL"]["per_instance"])
    bl_v = extract_v(arms["BL"]["per_instance"])
    uu_v = extract_v(arms["UU"]["per_instance"])

    h_d1 = paired_wilcoxon(fl_v, uu_v)  # FL > UU
    h_d2 = paired_wilcoxon(fl_v, bl_v)  # FL > BL

    if not floor_ok:
        outcome = "NOT_RUN"
        h_d1_sup = False
        h_d2_sup = False
    else:
        h_d1_sup = bool(h_d1.get("supported"))
        h_d2_sup = bool(h_d2.get("supported"))
        outcome = map_outcome(h_d1_sup, h_d2_sup)

    result = {
        "schema": "econ_lab.fracflat_readout.v1",
        "capsule": "D",
        "prereg": {
            "primary_metric": "verify_pass_fraction v in [0,1]",
            "hypotheses": {
                "H-D1": "FL > UU (paired Wilcoxon exact one-sided)",
                "H-D2": "FL > BL (paired Wilcoxon exact one-sided)",
            },
            "alpha_prime": ALPHA_PRIME,
            "floor": f"each arm n_computable_v >= {MIN_SETTLED}/{PLANNED_N}",
            "outcome_map": {
                "both": "PRICE_LEARNING_WORKS_WITH_DENSE_SIGNAL",
                "only_H-D1": "LEARNING_YES_INGREDIENT_UNCLEAR",
                "only_H-D2": "INGREDIENT_YES_VS_UNIFORM_UNPROVEN",
                "neither": "NULL_EVEN_WITH_DENSE_SIGNAL",
                "floor_fail": "NOT_RUN",
            },
        },
        "pool_manifest_sha256": pool_sha,
        "integrity_problems": problems,
        "arm_summaries": summaries,
        "floor_ok": floor_ok,
        "H-D1_FL_gt_UU": h_d1,
        "H-D2_FL_gt_BL": h_d2,
        "H-D1_supported": h_d1_sup if floor_ok else False,
        "H-D2_supported": h_d2_sup if floor_ok else False,
        "outcome": outcome,
        "secondary_descriptive": secondary_descriptive(arms),
        "budget": {
            "real_worker_calls_made_by_arm": {
                a: arms[a].get("real_worker_calls_made") for a in ARMS
            }
        },
        "meta_by_arm": {a: arms[a]["meta"] for a in ARMS},
    }
    return result


# ---------------------------------------------------------------------------
# Self-test (all outcomes + floor) — no real verdict I/O
# ---------------------------------------------------------------------------


def _synthetic_verdict(
    instance_vs: dict[str, float | None],
    *,
    fractional: bool,
    run_label: str,
) -> dict:
    tasks = []
    for iid, v in instance_vs.items():
        lsv = {
            "schema": "econ_lab.live_split_verifier.verdict.v1",
            "verify_pass_fraction": v,
            "verify_verdict": (v == 1.0) if v is not None else None,
            "accept_verdict": (v == 1.0) if v is not None else None,
            "accept_test_ids": [],
            "verify_test_ids": [],
            "canary": False,
            "not_enough_tests": False,
            "harness_error_reason": None,
        }
        tasks.append(
            {
                "instance_id": iid,
                "budget_suggestion": {"route_id": f"{iid}::armA::deepseek"},
                "dispatches": [
                    {
                        "settlement_verdict_resolved": (v == 1.0) if v is not None else None,
                        "live_split_verdict": lsv,
                    }
                ],
            }
        )
    return {
        "tasks": tasks,
        "task_count": len(tasks),
        "stage_b_prime_meta": {
            "schema": "econ_lab.stage_b_prime_meta.v1",
            "fractional_reward": fractional,
            "frozen_backup": False,
            "run_label": run_label,
        },
        "verifier_summary": {"canary_count": 0, "not_enough_tests_count": 0},
        "real_worker_calls_made": len(instance_vs),
    }


def self_test() -> None:
    """Cover all four outcomes + floor NOT_RUN."""
    # Shared instance ids
    ids = [f"inst-{i:02d}" for i in range(50)]

    def write_arms(tmpdir: Path, fl, bl, uu, frac_fl=True):
        paths = {}
        for label, data, frac in (
            ("FL", fl, frac_fl),
            ("BL", bl, False),
            ("UU", uu, False),
        ):
            p = tmpdir / label / "verdict.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(
                json.dumps(_synthetic_verdict(data, fractional=frac, run_label=label), indent=2)
                + "\n",
                encoding="utf-8",
            )
            paths[label] = p
        return paths

    import tempfile

    # 1) Both supported: FL strictly better than BL and UU on many pairs
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        fl = {iid: 0.9 for iid in ids}
        bl = {iid: 0.1 for iid in ids}
        uu = {iid: 0.2 for iid in ids}
        # a few ties / zeros
        fl[ids[0]] = 0.5
        bl[ids[0]] = 0.5
        uu[ids[0]] = 0.5
        r = run_readout(write_arms(td_path, fl, bl, uu))
        assert r["floor_ok"], r
        assert r["outcome"] == "PRICE_LEARNING_WORKS_WITH_DENSE_SIGNAL", r["outcome"]
        assert r["H-D1_supported"] and r["H-D2_supported"]

    # 2) Only H-D1: FL > UU but FL == BL
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        fl = {iid: 0.8 for iid in ids}
        bl = {iid: 0.8 for iid in ids}
        uu = {iid: 0.1 for iid in ids}
        r = run_readout(write_arms(td_path, fl, bl, uu))
        assert r["outcome"] == "LEARNING_YES_INGREDIENT_UNCLEAR", r["outcome"]
        assert r["H-D1_supported"] and not r["H-D2_supported"]

    # 3) Only H-D2: FL > BL but FL == UU
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        fl = {iid: 0.8 for iid in ids}
        bl = {iid: 0.1 for iid in ids}
        uu = {iid: 0.8 for iid in ids}
        r = run_readout(write_arms(td_path, fl, bl, uu))
        assert r["outcome"] == "INGREDIENT_YES_VS_UNIFORM_UNPROVEN", r["outcome"]
        assert r["H-D2_supported"] and not r["H-D1_supported"]

    # 4) Neither: all equal
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        fl = {iid: 0.5 for iid in ids}
        bl = {iid: 0.5 for iid in ids}
        uu = {iid: 0.5 for iid in ids}
        r = run_readout(write_arms(td_path, fl, bl, uu))
        assert r["outcome"] == "NULL_EVEN_WITH_DENSE_SIGNAL", r["outcome"]
        assert not r["H-D1_supported"] and not r["H-D2_supported"]

    # 5) Floor fail: only 30 computable v on FL
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        fl = {iid: (0.9 if i < 30 else None) for i, iid in enumerate(ids)}
        bl = {iid: 0.1 for iid in ids}
        uu = {iid: 0.1 for iid in ids}
        r = run_readout(write_arms(td_path, fl, bl, uu))
        assert not r["floor_ok"]
        assert r["outcome"] == "NOT_RUN", r["outcome"]

    # 6) Wilcoxon unit: known small example
    # diffs = [1, 2, 3, -1] -> abs ranks 1.5? wait abs: 1,2,3,1 -> ranks 1.5,3,4,1.5
    # pos: 1,2,3 ranks 1.5+3+4=8.5; n=4; total 16
    # W+ distributions...
    res = wilcoxon_signed_rank_exact_one_sided([1.0, 2.0, 3.0, -1.0])
    assert res["n_nonzero"] == 4
    assert res["n_zero"] == 0
    assert abs(res["W_plus"] - 8.5) < 1e-9, res
    assert 0.0 < res["p_one_sided"] <= 1.0

    # All positive small
    res2 = wilcoxon_signed_rank_exact_one_sided([1.0, 2.0, 3.0])
    # W+ = 1+2+3 = 6; only 1 of 8 assignments has W+>=6 (all positive)
    assert res2["W_plus"] == 6.0
    assert abs(res2["p_one_sided"] - 1 / 8) < 1e-12, res2

    # All zero
    res3 = wilcoxon_signed_rank_exact_one_sided([0.0, 0.0])
    assert res3["p_one_sided"] is None
    assert res3["n_zero"] == 2

    print("FRACFLAT_READOUT_SELF_TEST_PASS")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--run-root", type=Path, default=None, help="runs/fracflat_20260710")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--pool-sha256", default=None)
    args = ap.parse_args(argv)

    if args.self_test:
        self_test()
        return 0

    if args.run_root is None:
        print("error: --run-root required (or --self-test)", file=sys.stderr)
        return 2

    arm_paths = {a: args.run_root / a / "verdict.json" for a in ARMS}
    for a, p in arm_paths.items():
        if not p.is_file():
            print(f"error: missing {p}", file=sys.stderr)
            return 2

    result = run_readout(arm_paths, pool_sha=args.pool_sha256)
    out = args.out or (args.run_root / "FRACFLAT_READOUT.json")
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8")
    print(json.dumps({"status": "WROTE_READOUT", "path": str(out), "outcome": result["outcome"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
