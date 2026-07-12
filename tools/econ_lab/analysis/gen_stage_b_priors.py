#!/usr/bin/env python3
"""Generate Stage B' warm-start priors from pooled S01 (Stage A) posteriors.

Provenance: reads the five committed Stage A verdict.json files; per route
P = (0.5 + S) / (1 + N) over pooled settled outcomes (ADR-ECON-003 Decision 6
pseudo-count posterior, N0=1, neutral prior 0.5). Deterministic; the output
file's sha256 is pinned in PREREG Appendix A amendment #4. EXPLORATORY data
becomes CONFIRMATORY input here only as *priors*; all Stage B' evaluation
happens on disjoint S02 tasks (out-of-sample transfer).
"""
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "runs/stageA_20260707"
n = defaultdict(int); k = defaultdict(int)
for a in ["0", "0p5", "1", "2", "inf"]:
    v = json.loads((ROOT / f"tau_{a}/verdict.json").read_text())
    for t in v["tasks"]:
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
        n[route] += 1; k[route] += int(bool(sv))

priors = {
    "schema": "econ_lab.stage_b_prime_priors.v1",
    "provenance": "pooled S01 Stage A settled outcomes, P=(0.5+S)/(1+N), Decision 6",
    "source_run": "stageA_20260707",
    "priors": {r: round((0.5 + k[r]) / (1 + n[r]), 6) for r in sorted(n)},
    "support": {r: {"k": k[r], "n": n[r]} for r in sorted(n)},
}
out = Path(__file__).parent / "stage_b_prime_priors_s01.json"
out.write_text(json.dumps(priors, indent=2, sort_keys=True) + "\n")
print(out)
