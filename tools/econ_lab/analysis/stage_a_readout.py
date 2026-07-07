#!/usr/bin/env python3
"""Stage A (E-price-tau) frozen statistical readout.

FROZEN before any Stage A verdict existed (PREREG Appendix A amendment #2).
Judgment logic, test family, and alpha are pinned by
PREREG_ECON_emergence_experiments_20260707.md §2 + amendment #1 and may not be
edited after data exists; a defect discovered at readout time must be recorded
as a dated PREREG addendum, never silently patched here.

Primary metric per task: dispatch settlement_verdict_resolved (the accept-side
verdict that settles the market, ADR-ECON-003 Decision 2.4). Diagnostic only:
the harness whole-suite `resolved`. Tests: one-sided two-proportion pooled-SE
z-tests, interior arm > each extreme, Bonferroni alpha' = 0.05/3 over the three
interior arms. Ceiling: ADDRESSED; this script never claims beyond the frozen
criteria and a null/falsified outcome is a valid, reportable result.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ARMS = {"0": "tau_0", "0.5": "tau_0p5", "1": "tau_1", "2": "tau_2", "inf": "tau_inf"}
INTERIOR = ["0.5", "1", "2"]
EXTREMES = ["0", "inf"]
ALPHA = 0.05
ALPHA_PRIME = ALPHA / len(INTERIOR)  # Bonferroni, PREREG §2
MIN_SETTLED_PER_ARM = 40  # 80% of the 50 frozen tasks; below = data-quality NOT_RUN
PLANNED_N = 50


def arm_stats(verdict: dict) -> dict:
    settled = 0
    passed = 0
    infra_null = 0
    diagnostic_resolved = 0
    for task in verdict.get("tasks", []):
        dispatches = task.get("dispatches", [])
        # Non-smoke arms have exactly one dispatch (the selected route).
        sv = None
        resolved = False
        for d in dispatches:
            if "settlement_verdict_resolved" in d:
                sv = d["settlement_verdict_resolved"]
            sr = d.get("scoring_result") or {}
            resolved = resolved or bool(sr.get("resolved"))
        if sv is None:
            infra_null += 1
            continue
        settled += 1
        passed += int(bool(sv))
        diagnostic_resolved += int(resolved)
    vs = verdict.get("verifier_summary", {})
    return {
        "n_settled": settled,
        "k_pass": passed,
        "rate": (passed / settled) if settled else None,
        "infra_null": infra_null,
        "diagnostic_resolved": diagnostic_resolved,
        "canary_count": vs.get("canary_count"),
        "not_enough_tests_count": vs.get("not_enough_tests_count"),
    }


def one_sided_two_prop_z(k1: int, n1: int, k2: int, n2: int) -> dict:
    """H1: p1 > p2. Pooled-SE z; p-value via normal tail (0.5*erfc(z/sqrt(2)))."""
    if n1 == 0 or n2 == 0:
        return {"z": None, "p": None}
    p1, p2 = k1 / n1, k2 / n2
    pooled = (k1 + k2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    if se == 0:
        return {"z": None, "p": 1.0 if p1 <= p2 else 0.0}
    z = (p1 - p2) / se
    return {"z": z, "p": 0.5 * math.erfc(z / math.sqrt(2))}


def judge(stats: dict[str, dict]) -> dict:
    # Data-quality gate first (NOT_RUN == FAIL discipline, no partial reading).
    quality = {a: s["n_settled"] for a, s in stats.items()}
    if any(s["n_settled"] < MIN_SETTLED_PER_ARM for s in stats.values()):
        return {
            "stage_a_outcome": "NOT_RUN_INSUFFICIENT_SETTLEMENTS",
            "detail": f"arm settled counts {quality} below the frozen floor {MIN_SETTLED_PER_ARM}/{PLANNED_N}",
            "tests": {},
        }
    tests = {}
    significant = []
    directional = []
    for arm in INTERIOR:
        s = stats[arm]
        vs = {}
        beats_both_sig = True
        beats_both_dir = True
        for ext in EXTREMES:
            e = stats[ext]
            t = one_sided_two_prop_z(s["k_pass"], s["n_settled"], e["k_pass"], e["n_settled"])
            vs[f"vs_tau_{ext}"] = t
            beats_both_sig = beats_both_sig and (t["p"] is not None and t["p"] < ALPHA_PRIME)
            beats_both_dir = beats_both_dir and (s["rate"] > e["rate"])
        tests[arm] = vs
        if beats_both_sig:
            significant.append(arm)
        if beats_both_dir:
            directional.append(arm)
    if significant:
        outcome = "PASS_INTERIOR_PEAK"
        detail = f"interior arm(s) {significant} beat both extremes at alpha'={ALPHA_PRIME:.4f}; price carries information; proceed per design §3 ladder"
    elif directional:
        outcome = "PROCEED_STAGE_B"
        detail = f"interior arm(s) {directional} directionally above both extremes but not significant at n~{PLANNED_N}; PREREG §2 Stage B applies (n=171/arm; task-stream plan in amendment #2)"
    else:
        outcome = "FALSIFIED_HONEST_STOP"
        detail = "no interior arm directionally above both extremes; per design §3.1 the single-scalar price carries no routing information at this scale — honest stop"
    return {"stage_a_outcome": outcome, "detail": detail, "tests": tests}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-root", type=Path, default=Path(__file__).resolve().parents[1] / "runs/stageA_20260707")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    stats = {}
    for arm, d in ARMS.items():
        p = args.run_root / d / "verdict.json"
        if not p.exists():
            print(json.dumps({"stage_a_outcome": "NOT_RUN_MISSING_VERDICT", "missing": str(p)}, indent=2))
            return 1
        stats[arm] = arm_stats(json.loads(p.read_text()))

    result = {
        "schema": "econ_lab.stage_a_readout.v1",
        "frozen_by": "PREREG Appendix A amendment #2",
        "alpha_prime_bonferroni": ALPHA_PRIME,
        "primary_metric": "settlement_verdict_resolved (accept-side, Decision 2.4)",
        "arm_stats": stats,
        **judge(stats),
        "status_ceiling": "ADDRESSED",
    }
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.out:
        args.out.write_text(text + "\n")
    return 0


def _fake(k: int, n: int, nulls: int = 0) -> dict:
    tasks = [{"dispatches": [{"settlement_verdict_resolved": i < k, "scoring_result": {"resolved": i < k}}]} for i in range(n)]
    tasks += [{"dispatches": [{"settlement_verdict_resolved": None, "scoring_result": {}}]} for _ in range(nulls)]
    return {"tasks": tasks, "verifier_summary": {"canary_count": 0, "not_enough_tests_count": 0}}


def self_test() -> int:
    # 1. clear interior peak: tau=1 at 40/50 vs extremes 20/50 -> PASS
    s = {a: arm_stats(_fake(20, 50)) for a in ARMS}
    s["1"] = arm_stats(_fake(40, 50))
    r = judge(s)
    assert r["stage_a_outcome"] == "PASS_INTERIOR_PEAK", r
    # 2. directional only: 26/50 vs 22/50 -> STAGE_B
    s = {a: arm_stats(_fake(22, 50)) for a in ARMS}
    for i in INTERIOR:
        s[i] = arm_stats(_fake(26, 50))
    r = judge(s)
    assert r["stage_a_outcome"] == "PROCEED_STAGE_B", r
    # 3. extremes win -> FALSIFIED
    s = {a: arm_stats(_fake(30, 50)) for a in ARMS}
    for i in INTERIOR:
        s[i] = arm_stats(_fake(20, 50))
    r = judge(s)
    assert r["stage_a_outcome"] == "FALSIFIED_HONEST_STOP", r
    # 4. quality gate: one arm settled below floor -> NOT_RUN
    s = {a: arm_stats(_fake(20, 50)) for a in ARMS}
    s["2"] = arm_stats(_fake(10, 30, nulls=20))
    r = judge(s)
    assert r["stage_a_outcome"] == "NOT_RUN_INSUFFICIENT_SETTLEMENTS", r
    # 5. z sanity: 40/50 vs 20/50 one-sided p << 0.0167
    t = one_sided_two_prop_z(40, 50, 20, 50)
    assert t["p"] < 0.0001, t
    print("STAGE_A_READOUT_SELF_TEST_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
