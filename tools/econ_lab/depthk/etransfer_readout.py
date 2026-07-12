#!/usr/bin/env python3
"""CAPSULE E — preregistered readout (frozen before first real call).

Judgment domain = HELDOUT only; metric = verify pass fraction v ∈ [0,1].
H-E1: T > A on HELDOUT, Wilcoxon signed-rank exact one-sided, α=0.05.
Starvation floors:
  T arm: each stage node TRAIN N ≥ 5
  A arm: per-route TRAIN N median ≥ 3
  else STARVED → NOT_RUN_STARVED
Quality floors:
  HELDOUT settled ≥ 0.8×|HELDOUT|; TRAIN settled ≥ 0.8×|TRAIN| per arm
  else NOT_RUN_INSUFFICIENT
Outcomes:
  STAGE_MECHANISM_TRANSFERS | NO_STAGE_TRANSFER_ADVANTAGE
  | NOT_RUN_STARVED | NOT_RUN_INSUFFICIENT

Never claims "learned a function" / 学到函数.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
from itertools import product
from pathlib import Path
from typing import Any, Optional

ALPHA = 0.05
T_STAGE_N_FLOOR = 5
A_ROUTE_N_MEDIAN_FLOOR = 3
SETTLED_FRAC_FLOOR = 0.8

ARMS = ("T", "A")
STAGE_NODES = [
    "context:minimal",
    "context:source_context",
    "repair:single_shot",
    "repair:loop",
    "verify:none",
    "verify:self_check",
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_v_from_task(task: dict[str, Any]) -> Optional[float]:
    """Primary metric: verify-side pass fraction v∈[0,1]."""
    # depthk / etransfer stage record
    if task.get("verify_pass_fraction") is not None and task.get("live_split_verdict"):
        live = task["live_split_verdict"] or {}
        if live.get("not_enough_tests"):
            return None
        if live.get("verify_pass_fraction") is not None:
            return float(live["verify_pass_fraction"])
        if task.get("verify_pass_fraction") is not None:
            return float(task["verify_pass_fraction"])

    live = task.get("live_split_verdict")
    if isinstance(live, dict) and live:
        if live.get("not_enough_tests"):
            return None
        if live.get("verify_pass_fraction") is not None:
            return float(live["verify_pass_fraction"])
        if live.get("verify_verdict") is not None:
            return 1.0 if live["verify_verdict"] else 0.0

    # flat live_driver dispatches
    for d in task.get("dispatches") or []:
        lsv = d.get("live_split_verdict") or {}
        if not lsv:
            continue
        if lsv.get("not_enough_tests"):
            return None
        if lsv.get("verify_pass_fraction") is not None:
            return float(lsv["verify_pass_fraction"])
        if lsv.get("verify_verdict") is not None:
            return 1.0 if lsv["verify_verdict"] else 0.0

    # last resort: accept settlement (not preferred; still usable floor counting)
    if task.get("settlement_verdict_resolved") is not None:
        return 1.0 if task["settlement_verdict_resolved"] else 0.0
    for d in task.get("dispatches") or []:
        if d.get("settlement_verdict_resolved") is not None:
            return 1.0 if d["settlement_verdict_resolved"] else 0.0
    return None


def task_side(task: dict[str, Any], split: dict[str, Any]) -> str:
    if task.get("side") in ("TRAIN", "HELDOUT"):
        return task["side"]
    iid = task.get("instance_id")
    if iid in set(split.get("train_instance_ids") or []):
        return "TRAIN"
    if iid in set(split.get("heldout_instance_ids") or []):
        return "HELDOUT"
    return "UNKNOWN"


def per_instance_v(verdict: dict[str, Any], split: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for task in verdict.get("tasks") or []:
        iid = task.get("instance_id")
        if not iid:
            continue
        out[iid] = {
            "v": extract_v_from_task(task),
            "side": task_side(task, split),
            "task": task,
        }
    return out


def mean_or_none(xs: list[float]) -> Optional[float]:
    return (sum(xs) / len(xs)) if xs else None


def wilcoxon_signed_rank_exact_one_sided(diffs: list[float]) -> dict[str, Any]:
    """Exact one-sided Wilcoxon signed-rank: H1 median(diff) > 0.

    Uses midranks for |diff| ties; zeros dropped. Enumerates all 2^n sign assignments
    for the non-zero observations (n ≤ 25 planned).
    """
    nonzero = [d for d in diffs if d != 0]
    n = len(nonzero)
    if n == 0:
        return {
            "n_nonzero": 0,
            "W_plus": 0.0,
            "p_one_sided": None,
            "note": "all_zero_or_empty_diffs",
        }

    abs_vals = [abs(d) for d in nonzero]
    # midranks
    order = sorted(range(n), key=lambda i: abs_vals[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs_vals[order[j + 1]] == abs_vals[order[i]]:
            j += 1
        # ranks i+1 .. j+1 (1-based)
        avg = (i + 1 + j + 1) / 2.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1

    signs = [1 if d > 0 else -1 for d in nonzero]
    w_plus = sum(r for r, s in zip(ranks, signs) if s > 0)

    # exact null: each rank independently + or - with p=0.5
    # P(W+ >= observed)
    count_ge = 0
    total = 1 << n
    # For n up to 25, enumerate; use bit masks
    rank_arr = ranks
    for mask in range(total):
        w = 0.0
        for bit in range(n):
            if mask & (1 << bit):
                w += rank_arr[bit]
        if w + 1e-12 >= w_plus:
            count_ge += 1
    p = count_ge / total
    return {
        "n_nonzero": n,
        "W_plus": w_plus,
        "p_one_sided": p,
        "method": "exact_enumeration_midranks",
    }


def starvation_check_T(verdict: dict[str, Any], split: dict[str, Any]) -> dict[str, Any]:
    """T arm: each stage node TRAIN N ≥ 5."""
    train_n = dict(verdict.get("stage_node_train_n") or {})
    # Recompute from tasks if missing
    if not train_n:
        train_n = {k: 0 for k in STAGE_NODES}
        for task in verdict.get("tasks") or []:
            if task_side(task, split) != "TRAIN":
                continue
            if not task.get("credit_events") and not task.get("credit_events_count"):
                continue
            choices = task.get("stage_choices") or {}
            for stage, opt in choices.items():
                key = f"{stage}:{opt}"
                train_n[key] = train_n.get(key, 0) + 1

    missing = [k for k in STAGE_NODES if train_n.get(k, 0) < T_STAGE_N_FLOOR]
    # Also check nodes that never appear
    for k in STAGE_NODES:
        train_n.setdefault(k, 0)
    ok = all(train_n.get(k, 0) >= T_STAGE_N_FLOOR for k in STAGE_NODES)
    return {
        "arm": "T",
        "floor": T_STAGE_N_FLOOR,
        "stage_node_train_n": {k: int(train_n.get(k, 0)) for k in STAGE_NODES},
        "starved_nodes": missing if not ok else [],
        "ok": ok,
    }


def starvation_check_A(verdict: dict[str, Any], split: dict[str, Any]) -> dict[str, Any]:
    """A arm: per-route TRAIN N median ≥ 3."""
    route_n: dict[str, int] = {}
    for task in verdict.get("tasks") or []:
        if task_side(task, split) != "TRAIN":
            continue
        # count credit only when settlement resolved (fold update applied)
        credited = False
        for d in task.get("dispatches") or []:
            if d.get("settlement_verdict_resolved") is not None and not (
                (d.get("live_split_verdict") or {}).get("not_enough_tests")
            ):
                # fractional path always writes event when resolved under live_driver
                credited = True
            if d.get("backup_update") is not None or d.get("routing_prior_updated_event") is not None:
                credited = True
            if d.get("_routing_prior_updated_event") is not None:
                credited = True
        # live_driver stores event separately; check settlement presence
        if any(
            d.get("settlement_verdict_resolved") is not None
            for d in (task.get("dispatches") or [])
        ):
            credited = True
        if not credited:
            continue
        route = task.get("selected_route_id") or ""
        if not route:
            arm = task.get("selected_arm")
            lin = task.get("selected_lineage")
            if arm and lin:
                route = f"{arm}::{lin}"
        if not route:
            continue
        route_n[route] = route_n.get(route, 0) + 1

    # 12-route space may have zero-N routes; include zeros for known routes if scaffold_ids present
    if verdict.get("scaffold_ids"):
        for arm, by_lin in verdict["scaffold_ids"].items():
            for lin in by_lin:
                route_n.setdefault(f"{arm}::{lin}", 0)

    counts = list(route_n.values()) if route_n else [0]
    median_n = float(statistics.median(counts))
    ok = median_n >= A_ROUTE_N_MEDIAN_FLOOR
    return {
        "arm": "A",
        "floor_median": A_ROUTE_N_MEDIAN_FLOOR,
        "route_train_n": dict(sorted(route_n.items())),
        "median_train_n": median_n,
        "n_routes_observed": len(route_n),
        "ok": ok,
    }


def quality_floor(
    per: dict[str, dict[str, Any]],
    *,
    planned: list[str],
    side: str,
) -> dict[str, Any]:
    planned_set = set(planned)
    settled = [
        iid
        for iid, row in per.items()
        if iid in planned_set and row["side"] == side and row["v"] is not None
    ]
    n_planned = len(planned)
    n_settled = len(settled)
    need = math.ceil(SETTLED_FRAC_FLOOR * n_planned) if n_planned else 0
    return {
        "side": side,
        "n_planned": n_planned,
        "n_settled": n_settled,
        "need": need,
        "ok": n_settled >= need,
    }


def descriptive_secondary(
    t_per: dict[str, dict[str, Any]],
    a_per: dict[str, dict[str, Any]],
    t_verdict: dict[str, Any],
    split: dict[str, Any],
) -> dict[str, Any]:
    def side_mean(per: dict[str, dict[str, Any]], side: str) -> Optional[float]:
        xs = [row["v"] for row in per.values() if row["side"] == side and row["v"] is not None]
        return mean_or_none(xs)

    # Stage choice distributions TRAIN vs HELDOUT for T
    def stage_dist(side: str) -> dict[str, dict[str, int]]:
        dist: dict[str, dict[str, int]] = {}
        for iid, row in t_per.items():
            if row["side"] != side:
                continue
            choices = (row["task"] or {}).get("stage_choices") or {}
            for stage, opt in choices.items():
                dist.setdefault(stage, {})
                dist[stage][opt] = dist[stage].get(opt, 0) + 1
        return dist

    canary_t = 0
    canary_a = 0
    for row in t_per.values():
        live = (row["task"] or {}).get("live_split_verdict") or {}
        canary_t += int(bool(live.get("canary")))
    for row in a_per.values():
        for d in (row["task"] or {}).get("dispatches") or []:
            canary_a += int(bool((d.get("live_split_verdict") or {}).get("canary")))

    return {
        "train_mean_v": {"T": side_mean(t_per, "TRAIN"), "A": side_mean(a_per, "TRAIN")},
        "heldout_mean_v": {"T": side_mean(t_per, "HELDOUT"), "A": side_mean(a_per, "HELDOUT")},
        "t_stage_choice_dist_train": stage_dist("TRAIN"),
        "t_stage_choice_dist_heldout": stage_dist("HELDOUT"),
        "t_final_stage_nodes": t_verdict.get("final_stage_nodes"),
        "canary_counts": {"T": canary_t, "A": canary_a},
        "credit_assignment_v0_note": (
            "v0 equal-share attribution across stage nodes (CAPSULE B memo R1); "
            "known ceiling, not causal credit"
        ),
        "significance_on_secondary": "FORBIDDEN",
    }


def run_readout(
    *,
    run_root: Path,
    split_path: Path,
    self_test: bool = False,
) -> dict[str, Any]:
    if self_test:
        return _self_test()

    split = load_json(split_path)
    t_path = run_root / "T" / "verdict.json"
    a_path = run_root / "A" / "verdict.json"
    if not t_path.exists() or not a_path.exists():
        raise SystemExit(f"missing arm verdict(s): T={t_path.exists()} A={a_path.exists()}")

    t_verdict = load_json(t_path)
    a_verdict = load_json(a_path)
    t_per = per_instance_v(t_verdict, split)
    a_per = per_instance_v(a_verdict, split)

    train_ids = list(split.get("train_instance_ids") or [])
    heldout_ids = list(split.get("heldout_instance_ids") or [])

    star_t = starvation_check_T(t_verdict, split)
    star_a = starvation_check_A(a_verdict, split)
    starvation = {
        "T": star_t,
        "A": star_a,
        "ok": bool(star_t["ok"] and star_a["ok"]),
    }

    q_t_train = quality_floor(t_per, planned=train_ids, side="TRAIN")
    q_t_held = quality_floor(t_per, planned=heldout_ids, side="HELDOUT")
    q_a_train = quality_floor(a_per, planned=train_ids, side="TRAIN")
    q_a_held = quality_floor(a_per, planned=heldout_ids, side="HELDOUT")
    quality = {
        "T": {"TRAIN": q_t_train, "HELDOUT": q_t_held},
        "A": {"TRAIN": q_a_train, "HELDOUT": q_a_held},
        "ok": all(x["ok"] for x in (q_t_train, q_t_held, q_a_train, q_a_held)),
    }

    # Paired HELDOUT diffs
    paired: list[dict[str, Any]] = []
    diffs: list[float] = []
    for iid in heldout_ids:
        tv = t_per.get(iid, {}).get("v")
        av = a_per.get(iid, {}).get("v")
        if tv is None or av is None:
            continue
        d = float(tv) - float(av)
        paired.append({"instance_id": iid, "v_T": tv, "v_A": av, "diff": d})
        diffs.append(d)

    wilcox = wilcoxon_signed_rank_exact_one_sided(diffs)

    if not starvation["ok"]:
        outcome = "NOT_RUN_STARVED"
        h_e1 = {
            "hypothesis": "H-E1: T > A on HELDOUT",
            "supported": None,
            "reason": "starvation_floor_failed",
        }
    elif not quality["ok"]:
        outcome = "NOT_RUN_INSUFFICIENT"
        h_e1 = {
            "hypothesis": "H-E1: T > A on HELDOUT",
            "supported": None,
            "reason": "quality_floor_failed",
        }
    else:
        p = wilcox.get("p_one_sided")
        supported = p is not None and p < ALPHA
        outcome = "STAGE_MECHANISM_TRANSFERS" if supported else "NO_STAGE_TRANSFER_ADVANTAGE"
        h_e1 = {
            "hypothesis": "H-E1: T > A on HELDOUT",
            "alpha": ALPHA,
            "test": "wilcoxon_signed_rank_exact_one_sided",
            "n_paired": len(diffs),
            "mean_diff": mean_or_none(diffs),
            "W_plus": wilcox.get("W_plus"),
            "p_one_sided": p,
            "supported": supported,
        }

    readout = {
        "schema": "econ_lab.etransfer_readout.v1",
        "prereg": {
            "judgment_domain": "HELDOUT",
            "metric": "verify_pass_fraction_v_in_0_1",
            "alpha": ALPHA,
            "hypothesis": "H-E1: T > A on HELDOUT (Wilcoxon signed-rank exact one-sided)",
            "starvation_floors": {
                "T_each_stage_node_train_N": T_STAGE_N_FLOOR,
                "A_route_train_N_median": A_ROUTE_N_MEDIAN_FLOOR,
            },
            "quality_floors": {
                "settled_frac": SETTLED_FRAC_FLOOR,
            },
            "outcomes": [
                "STAGE_MECHANISM_TRANSFERS",
                "NO_STAGE_TRANSFER_ADVANTAGE",
                "NOT_RUN_STARVED",
                "NOT_RUN_INSUFFICIENT",
            ],
            "language_ban": "no_learned_function_claims",
        },
        "split_manifest_path": str(split_path),
        "split_manifest_sha256": sha256_file(split_path),
        "split_fingerprint_sha256": split.get("fingerprint_sha256"),
        "arms": {
            "T": {"verdict_path": str(t_path), "domain_bucket": t_verdict.get("domain_bucket")},
            "A": {
                "verdict_path": str(a_path),
                "domain_buckets": (a_verdict.get("stage_b_prime_meta") or {}).get(
                    "domain_buckets_observed"
                ),
            },
        },
        "starvation_check": starvation,
        "quality_floors": quality,
        "paired_heldout": paired,
        "wilcoxon": wilcox,
        "H_E1": h_e1,
        "outcome": outcome,
        "secondary_descriptive": descriptive_secondary(t_per, a_per, t_verdict, split),
        "status_ceiling": "ADDRESSED",
        "claims": {
            "significance_outside_H_E1": False,
            "learned_function": False,
            "note": "Readout maps prereg outcomes only; interpretation authority is orchestrator.",
        },
    }
    return readout


def _self_test() -> dict[str, Any]:
    """Offline self-test covering all four outcomes + both floors. No real data."""
    results: dict[str, Any] = {"schema": "econ_lab.etransfer_readout.self_test.v1", "cases": {}}

    # Wilcoxon: T clearly better
    diffs_pos = [0.2, 0.3, 0.1, 0.4, 0.15, 0.25, 0.05, 0.35]
    w = wilcoxon_signed_rank_exact_one_sided(diffs_pos)
    assert w["p_one_sided"] is not None and w["p_one_sided"] < 0.05, w
    results["cases"]["wilcoxon_positive"] = w

    # Wilcoxon: zeros / no signal
    w0 = wilcoxon_signed_rank_exact_one_sided([0.0, 0.0])
    assert w0["p_one_sided"] is None
    results["cases"]["wilcoxon_all_zero"] = w0

    # Symmetric null-ish
    diffs_sym = [0.1, -0.1, 0.2, -0.2, 0.05, -0.05]
    w_sym = wilcoxon_signed_rank_exact_one_sided(diffs_sym)
    assert w_sym["p_one_sided"] is not None and w_sym["p_one_sided"] > 0.2
    results["cases"]["wilcoxon_symmetric"] = w_sym

    # Synthetic starvation T
    t_starved = {
        "tasks": [],
        "stage_node_train_n": {k: 10 for k in STAGE_NODES},
    }
    t_starved["stage_node_train_n"]["context:minimal"] = 2
    split = {
        "train_instance_ids": [f"x__{i}" for i in range(10)],
        "heldout_instance_ids": [f"y__{i}" for i in range(10)],
    }
    st = starvation_check_T(t_starved, split)
    assert st["ok"] is False
    results["cases"]["T_starved"] = st

    t_ok = {"tasks": [], "stage_node_train_n": {k: 8 for k in STAGE_NODES}}
    assert starvation_check_T(t_ok, split)["ok"] is True

    # A median
    a_verdict = {
        "tasks": [
            {
                "instance_id": f"x__{i}",
                "side": "TRAIN",
                "selected_route_id": f"armA::deepseek" if i < 6 else f"armB::qwen",
                "dispatches": [{"settlement_verdict_resolved": True}],
            }
            for i in range(10)
        ],
        "scaffold_ids": {
            "armA": {"deepseek": "s1", "qwen": "s2", "glm": "s3", "kimi": "s4"},
            "armB": {"deepseek": "s5", "qwen": "s6", "glm": "s7", "kimi": "s8"},
            "armC": {"deepseek": "s9", "qwen": "s10", "glm": "s11", "kimi": "s12"},
        },
    }
    sa = starvation_check_A(a_verdict, split)
    # many zeros → median 0 → starved
    assert sa["ok"] is False
    results["cases"]["A_starved_median"] = sa

    # Quality floor
    per = {
        f"y__{i}": {"v": 0.5 if i < 9 else None, "side": "HELDOUT", "task": {}}
        for i in range(10)
    }
    q = quality_floor(per, planned=[f"y__{i}" for i in range(10)], side="HELDOUT")
    assert q["ok"] is True  # 9 >= 0.8*10=8
    per2 = {
        f"y__{i}": {"v": 0.5 if i < 7 else None, "side": "HELDOUT", "task": {}}
        for i in range(10)
    }
    q2 = quality_floor(per2, planned=[f"y__{i}" for i in range(10)], side="HELDOUT")
    assert q2["ok"] is False
    results["cases"]["quality_ok"] = q
    results["cases"]["quality_fail"] = q2

    # Outcome mapping simulation
    def map_outcome(star_ok: bool, qual_ok: bool, p: Optional[float]) -> str:
        if not star_ok:
            return "NOT_RUN_STARVED"
        if not qual_ok:
            return "NOT_RUN_INSUFFICIENT"
        if p is not None and p < ALPHA:
            return "STAGE_MECHANISM_TRANSFERS"
        return "NO_STAGE_TRANSFER_ADVANTAGE"

    outcomes = {
        "starved": map_outcome(False, True, 0.01),
        "insufficient": map_outcome(True, False, 0.01),
        "transfer": map_outcome(True, True, 0.01),
        "no_adv": map_outcome(True, True, 0.5),
    }
    assert outcomes["starved"] == "NOT_RUN_STARVED"
    assert outcomes["insufficient"] == "NOT_RUN_INSUFFICIENT"
    assert outcomes["transfer"] == "STAGE_MECHANISM_TRANSFERS"
    assert outcomes["no_adv"] == "NO_STAGE_TRANSFER_ADVANTAGE"
    results["cases"]["outcome_mapping"] = outcomes
    results["status"] = "SELF_TEST_PASS"
    return results


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="CAPSULE E prereg readout")
    parser.add_argument(
        "--run-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "runs" / "etransfer_20260710",
    )
    parser.add_argument(
        "--split-manifest",
        type=Path,
        default=None,
    )
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)

    if args.self_test:
        result = run_readout(run_root=args.run_root, split_path=Path("."), self_test=True)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("status") == "SELF_TEST_PASS" else 1

    split_path = args.split_manifest or (args.run_root / "etransfer_split_manifest.json")
    out = args.out or (args.run_root / "ETRANSFER_READOUT.json")
    readout = run_readout(run_root=args.run_root, split_path=split_path, self_test=False)
    out.write_text(json.dumps(readout, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "WROTE_READOUT",
                "path": str(out),
                "outcome": readout["outcome"],
                "H_E1_supported": readout["H_E1"].get("supported"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
