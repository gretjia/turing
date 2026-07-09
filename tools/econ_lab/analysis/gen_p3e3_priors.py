#!/usr/bin/env python3
"""Generate P3-E3 warm-start priors from pooled S01+S02 settled posteriors.

Provenance: merges every committed Stage A (S01, five tau arms) and Stage B'
(S02, four arms W/F/C/U) verdict.json; per route
P = (0.5 + S) / (1 + N) over pooled settled outcomes (ADR-ECON-003 Decision 6
pseudo-count posterior, N0=1, neutral prior 0.5). Pattern mirrors
gen_stage_b_priors.py; the output file's sha256 is recorded in HANDOFF and
carried by each arm's verdict meta.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

RUNS = Path(__file__).resolve().parents[1] / "runs"
STAGE_A = RUNS / "stageA_20260707"
STAGE_B = RUNS / "stageBprime_20260708"

SOURCE_VERDICTS = [
    STAGE_A / f"tau_{a}/verdict.json" for a in ["0", "0p5", "1", "2", "inf"]
] + [STAGE_B / f"{a}/verdict.json" for a in ["W", "F", "C", "U"]]


def collect() -> tuple[dict[str, int], dict[str, int]]:
    n: dict[str, int] = defaultdict(int)
    k: dict[str, int] = defaultdict(int)
    for path in SOURCE_VERDICTS:
        if not path.exists():
            raise FileNotFoundError(f"missing priors source verdict: {path}")
        v = json.loads(path.read_text(encoding="utf-8"))
        for t in v.get("tasks", []):
            parts = t.get("budget_suggestion", {}).get("route_id", "").split("::")
            if len(parts) != 3:
                continue
            route = f"{parts[1]}::{parts[2]}"
            sv = None
            for d in t.get("dispatches", []):
                if d.get("settlement_verdict_resolved") is not None:
                    sv = d["settlement_verdict_resolved"]
            if sv is None:
                continue
            n[route] += 1
            k[route] += int(bool(sv))
    return n, k


def main() -> int:
    n, k = collect()
    repo = Path(__file__).resolve().parents[3]
    priors = {
        "schema": "econ_lab.p3e3_priors.v1",
        "provenance": (
            "pooled S01 Stage A (5 tau arms) + S02 Stage B' (W/F/C/U) settled "
            "outcomes, P=(0.5+S)/(1+N), ADR-ECON-003 Decision 6"
        ),
        "source_runs": ["stageA_20260707", "stageBprime_20260708"],
        "source_verdicts": [
            str(p.resolve().relative_to(repo)) if p.resolve().is_relative_to(repo) else str(p)
            for p in SOURCE_VERDICTS
        ],
        "priors": {r: round((0.5 + k[r]) / (1 + n[r]), 6) for r in sorted(n)},
        "support": {r: {"k": k[r], "n": n[r]} for r in sorted(n)},
    }
    out = Path(__file__).parent / "p3e3_priors_s01s02.json"
    out.write_text(json.dumps(priors, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
