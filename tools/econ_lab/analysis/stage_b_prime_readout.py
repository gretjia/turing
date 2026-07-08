#!/usr/bin/env python3
"""Stage B' frozen statistical readout (PREREG Appendix A amendment #4).

FROZEN before any S02 verdict exists. Judgment logic may not be edited after
data exists; defects found at readout time are recorded as dated PREREG
addenda, never silently patched.

Arms (all on fresh S02, tau*=0.5 except U):
  W  warm-start P from pooled S01 posteriors, live backup
  F  same P, frozen backup (static informed sorting)
  C  cold P=0.5, live backup
  U  uniform (tau=inf)

Pre-registered hypotheses, paired exact one-sided binomial (McNemar) on
instance-matched verdicts, Bonferroni alpha' = 0.05/3:
  H-B1: W > U   (transferred prices beat blind exploration)
  H-B2: W > F   (live learning on S02 beats static informed sorting)
  H-B3: W > C   (net value of cross-task price transfer)

Primary per-task metric: settlement_verdict_resolved under ADR-ECON-003
Decision 7 rules (driver-side: infra_null only for never-evaluated; empty
patch counts as a failed task). Rank-inversion in W is reported
DESCRIPTIVELY (event list, no significance claim) — the S02 stream is too
short for the E-emerge confirmation-window test; H-B2 carries the
confirmatory weight. Ceiling: ADDRESSED; null is a valid result.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ARMS = ["W", "F", "C", "U"]
ALPHA = 0.05
ALPHA_PRIME = ALPHA / 3
MIN_SETTLED_PER_ARM = 40
PLANNED_N = 50
PRIORS_SHA_PIN = "d7f900934d3d9c95243af717e6ee7e3fdab7df7c989c17f05a59171757fe41ac"


def load_arm(path: Path) -> dict:
    v = json.loads(path.read_text())
    per_instance = {}
    for task in v.get("tasks", []):
        iid = task.get("instance_id")
        sv = None
        for d in task.get("dispatches", []):
            if d.get("settlement_verdict_resolved") is not None:
                sv = d["settlement_verdict_resolved"]
        route = task.get("budget_suggestion", {}).get("route_id", "")
        verify = None
        for d in task.get("dispatches", []):
            if "verify_verdict" in d:
                verify = d["verify_verdict"]
        per_instance[iid] = {"pass": (bool(sv) if sv is not None else None), "route": route, "verify": verify}
    vs = v.get("verifier_summary", {})
    meta = v.get("stage_b_prime_meta", {})
    return {
        "per_instance": per_instance,
        "meta": meta,
        "canary_count": vs.get("canary_count"),
        "not_enough_tests_count": vs.get("not_enough_tests_count"),
    }


def integrity(arms: dict) -> list[str]:
    problems = []
    for a in ("W", "F"):
        if arms[a]["meta"].get("priors_sha256") != PRIORS_SHA_PIN:
            problems.append(f"arm {a} priors_sha256 != pinned value")
    if arms["F"]["meta"].get("frozen_backup") is not True:
        problems.append("arm F frozen_backup is not true")
    for a in ("W", "C", "U"):
        if arms[a]["meta"].get("frozen_backup") is True:
            problems.append(f"arm {a} unexpectedly frozen")
    sets = {a: set(i for i, r in arms[a]["per_instance"].items()) for a in ARMS}
    if len(set(map(frozenset, sets.values()))) != 1:
        problems.append("arms do not share an identical instance set")
    return problems


def paired_test(w: dict, other: dict) -> dict:
    b = c = 0
    for iid, wr in w.items():
        orr = other.get(iid)
        if orr is None or wr["pass"] is None or orr["pass"] is None:
            continue
        if wr["pass"] and not orr["pass"]:
            b += 1
        elif not wr["pass"] and orr["pass"]:
            c += 1
    n = b + c
    # one-sided exact binomial: P(X >= b | n, 0.5)
    p = sum(math.comb(n, i) for i in range(b, n + 1)) / (2 ** n) if n else None
    return {"b_w_pass_other_fail": b, "c_w_fail_other_pass": c, "n_discordant": n, "p_one_sided": p}


def arm_rate(per_instance: dict) -> dict:
    settled = [r["pass"] for r in per_instance.values() if r["pass"] is not None]
    return {
        "n_settled": len(settled),
        "k_pass": sum(settled),
        "rate": (sum(settled) / len(settled)) if settled else None,
        "infra_null": sum(1 for r in per_instance.values() if r["pass"] is None),
    }


def rank_inversions_descriptive(w_arm: dict, priors: dict) -> list[dict]:
    """Descriptive only: routes whose warm P-rank is bottom-half attaining top-1
    Q_eff at any point of W's sequential fold (analysis-side Decision 6 recompute)."""
    p0 = dict(priors)
    order = sorted(p0, key=lambda r: -p0[r])
    bottom_half = set(order[len(order) // 2:])
    S = {r: 0.0 for r in p0}
    N = {r: 0 for r in p0}
    events = []
    seq = sorted(w_arm["per_instance"].items())  # instance order proxy; W verdict tasks[] order preferred upstream
    for idx, (iid, rec) in enumerate(seq):
        parts = rec["route"].split("::")
        route = f"{parts[1]}::{parts[2]}" if len(parts) == 3 else None
        if route is None or rec["verify"] is None:
            continue
        N[route] += 1
        S[route] += int(bool(rec["verify"]))
        q = {r: (p0[r] * 1 + S[r]) / (1 + N[r]) for r in p0}
        top = max(q, key=lambda r: q[r])
        if top in bottom_half and N[top] > 0:
            events.append({"task_ordinal": idx, "instance_id": iid, "route": top, "q_eff": round(q[top], 4)})
            bottom_half.discard(top)  # report first attainment only
    return events


def judge(arms: dict, priors: dict) -> dict:
    problems = integrity(arms)
    if problems:
        return {"stage_b_outcome": "NOT_RUN_INTEGRITY", "problems": problems}
    stats = {a: arm_rate(arms[a]["per_instance"]) for a in ARMS}
    if any(s["n_settled"] < MIN_SETTLED_PER_ARM for s in stats.values()):
        return {"stage_b_outcome": "NOT_RUN_INSUFFICIENT_SETTLEMENTS",
                "arm_stats": stats}
    tests = {
        "H_B1_W_gt_U": paired_test(arms["W"]["per_instance"], arms["U"]["per_instance"]),
        "H_B2_W_gt_F": paired_test(arms["W"]["per_instance"], arms["F"]["per_instance"]),
        "H_B3_W_gt_C": paired_test(arms["W"]["per_instance"], arms["C"]["per_instance"]),
    }
    supported = {h: (t["p_one_sided"] is not None and t["p_one_sided"] < ALPHA_PRIME) for h, t in tests.items()}
    if supported["H_B1_W_gt_U"] and supported["H_B2_W_gt_F"]:
        outcome = "PRICE_LEARNING_TRANSFERS_AND_LIVE_LEARNING_ADDS"
    elif supported["H_B1_W_gt_U"]:
        outcome = "PRICE_TRANSFER_PROVEN_LIVE_INCREMENT_UNPROVEN"
    elif supported["H_B2_W_gt_F"] or supported["H_B3_W_gt_C"]:
        outcome = "PARTIAL_SUPPORT_SEE_TESTS"
    else:
        outcome = "NO_TRANSFER_DEMONSTRATED_HONEST_RECORD"
    return {
        "stage_b_outcome": outcome,
        "arm_stats": stats,
        "tests": tests,
        "supported": supported,
        "alpha_prime": ALPHA_PRIME,
        "rank_inversions_descriptive_W": rank_inversions_descriptive(arms["W"], priors),
        "canaries": {a: arms[a]["canary_count"] for a in ARMS},
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-root", type=Path, required=False,
                    default=Path(__file__).resolve().parents[1] / "runs/stageBprime_20260708")
    ap.add_argument("--priors", type=Path,
                    default=Path(__file__).parent / "stage_b_prime_priors_s01.json")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    arms = {}
    for a in ARMS:
        p = args.run_root / f"arm_{a}/verdict.json"
        if not p.exists():
            print(json.dumps({"stage_b_outcome": "NOT_RUN_MISSING_VERDICT", "missing": str(p)}))
            return 1
        arms[a] = load_arm(p)
    priors = json.loads(args.priors.read_text())["priors"]
    result = {"schema": "econ_lab.stage_b_prime_readout.v1",
              "frozen_by": "PREREG Appendix A amendment #4",
              **judge(arms, priors),
              "status_ceiling": "ADDRESSED"}
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.out:
        args.out.write_text(text + "\n")
    return 0


def _mk(passes: dict, frozen=False, sha=PRIORS_SHA_PIN) -> dict:
    return {"per_instance": {i: {"pass": p, "route": "x::armB::kimi", "verify": p} for i, p in passes.items()},
            "meta": {"priors_sha256": sha, "frozen_backup": frozen},
            "canary_count": 0, "not_enough_tests_count": 0}


def self_test() -> int:
    ids = [f"t{i:02d}" for i in range(50)]
    pri = {"armB::kimi": 0.475, "armA::qwen": 0.02}
    # 1. strong W: 30 pass; U/F/C: 10 pass, subsets of W's passes -> discordant one-way
    w = _mk({i: (k < 30) for k, i in enumerate(ids)})
    u = _mk({i: (k < 10) for k, i in enumerate(ids)})
    f = _mk({i: (k < 10) for k, i in enumerate(ids)}, frozen=True)
    c = _mk({i: (k < 10) for k, i in enumerate(ids)})
    r = judge({"W": w, "F": f, "C": c, "U": u}, pri)
    assert r["stage_b_outcome"] == "PRICE_LEARNING_TRANSFERS_AND_LIVE_LEARNING_ADDS", r["stage_b_outcome"]
    # 2. W==F strong vs U -> transfer proven, increment unproven
    f2 = _mk({i: (k < 30) for k, i in enumerate(ids)}, frozen=True)
    r = judge({"W": w, "F": f2, "C": c, "U": u}, pri)
    assert r["stage_b_outcome"] == "PRICE_TRANSFER_PROVEN_LIVE_INCREMENT_UNPROVEN", r["stage_b_outcome"]
    # 3. all equal -> no transfer
    w3 = _mk({i: (k < 10) for k, i in enumerate(ids)})
    r = judge({"W": w3, "F": f, "C": c, "U": u}, pri)
    assert r["stage_b_outcome"] == "NO_TRANSFER_DEMONSTRATED_HONEST_RECORD", r["stage_b_outcome"]
    # 4. integrity: F not frozen -> NOT_RUN
    f4 = _mk({i: (k < 10) for k, i in enumerate(ids)}, frozen=False)
    r = judge({"W": w, "F": f4, "C": c, "U": u}, pri)
    assert r["stage_b_outcome"] == "NOT_RUN_INTEGRITY", r["stage_b_outcome"]
    # 5. quality floor: W with 30 nulls -> NOT_RUN
    w5 = _mk({i: ((k < 10) if k < 20 else None) for k, i in enumerate(ids)})
    r = judge({"W": w5, "F": f, "C": c, "U": u}, pri)
    assert r["stage_b_outcome"] == "NOT_RUN_INSUFFICIENT_SETTLEMENTS", r["stage_b_outcome"]
    # 6. exact binomial sanity: b=8, c=1 -> p = P(X>=8|9) = (9+1)/512
    t = paired_test({f"i{k}": {"pass": True, "route": "", "verify": None} for k in range(8)} |
                    {f"j{k}": {"pass": False, "route": "", "verify": None} for k in range(1)},
                    {f"i{k}": {"pass": False, "route": "", "verify": None} for k in range(8)} |
                    {f"j{k}": {"pass": True, "route": "", "verify": None} for k in range(1)})
    assert abs(t["p_one_sided"] - 10 / 512) < 1e-12, t
    # 7. inversion detector: bottom-half route wins repeatedly -> event fires
    wi = _mk({i: True for i in ids[:6]})
    for k, (iid, rec) in enumerate(sorted(wi["per_instance"].items())):
        rec["route"] = "x::armA::qwen"
    ev = rank_inversions_descriptive(wi, pri)
    assert ev and ev[0]["route"] == "armA::qwen", ev
    print("STAGE_B_PRIME_READOUT_SELF_TEST_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
