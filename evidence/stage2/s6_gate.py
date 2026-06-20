#!/usr/bin/env python3
"""S-6 GATE — one FIXED capsule dispatched to >=2 REAL adapters; isolation + adapter-agnostic receipt.

Live: invokes the real subscription Worker CLIs (claude/codex/agy) headless on the SAME capsule, each in its
OWN isolated worktree. PASS iff >=2 adapters yield a schema-valid, worktree-confined candidate. No ranking.
    PYTHONPATH=src python3 evidence/stage2/s6_gate.py
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
import tempfile

from turingos import schemas
from turingos import dispatch_router
from turingos.worker.cli import CliWorkerAdapter

CAPSULE = {
    "schema_id": "turingos.capsule.v1",
    "capsule_id": "cap:" + "5630" * 4,
    "atom_id": "s6-fixed",
    "intent": "Create greet.py exposing a function greet() that returns exactly the string 'hello, turingos'.",
    "allowed_files": ["greet.py"],
    "budget": {"wall_seconds": 240, "max_retries": 1},
    "acceptance_commands": ["python3 -c \"import greet; assert greet.greet() == 'hello, turingos'\""],
    "context": {"tape_tip": "0" * 64, "accepted_head": "0" * 64},
}

ADAPTERS = ["claude", "codex", "agy"]  # the >=2 proven in S-6 PRE; grok available with --output-format plain


def _isolated(files_touched) -> bool:
    for p in files_touched:
        if os.path.isabs(p) or ".." in p.split("/"):
            return False
    return True


def _acceptance_ok(wt) -> bool:
    for cmd in CAPSULE["acceptance_commands"]:
        r = subprocess.run(cmd, shell=True, cwd=wt, capture_output=True, text=True)
        if r.returncode != 0:
            return False
    return True


def main() -> int:
    base = tempfile.mkdtemp(prefix="tos_s6_gate_")
    results = {"capsule_id": CAPSULE["capsule_id"], "runs": []}
    try:
        for w in ADAPTERS:
            if shutil.which(w) is None:
                results["runs"].append({"worker": w, "status": "not_installed"})
                continue
            wt = os.path.join(base, w)
            os.makedirs(wt, exist_ok=True)
            tier = dispatch_router.select_tier(CAPSULE)
            print(f"[S-6] dispatch {w} (router tier={tier}: {dispatch_router.describe(w, tier)})...", flush=True)
            try:
                rcpt = CliWorkerAdapter(w).run(CAPSULE, wt)
            except Exception as e:  # noqa: BLE001
                results["runs"].append({"worker": w, "status": "error", "detail": str(e)[:200]})
                continue
            schema_ok = True
            try:
                schemas.validate_receipt(rcpt)
            except Exception as e:  # noqa: BLE001
                schema_ok = False
            ft = rcpt["candidate"]["files_touched"]
            row = {
                "worker": w,
                "router_tier": tier,
                "status": rcpt["status"],
                "schema_valid": schema_ok,
                "adapter_agnostic_schema": rcpt.get("schema_id") == "turingos.receipt.v1",
                "tree_oid_present": bool(rcpt["candidate"]["tree_oid"]),
                "files_touched": ft,
                "isolation_ok": _isolated(ft),
                "in_scope": set(ft).issubset(set(CAPSULE["allowed_files"])),
                "acceptance_ok": _acceptance_ok(wt),
                "no_orphan": rcpt.get("no_orphan", False),
            }
            results["runs"].append(row)
            print(f"  -> {w}: status={row['status']} iso={row['isolation_ok']} accept={row['acceptance_ok']} "
                  f"in_scope={row['in_scope']}", flush=True)

        good = [r for r in results["runs"]
                if r.get("schema_valid") and r.get("adapter_agnostic_schema")
                and r.get("isolation_ok") and r.get("tree_oid_present") and r.get("status") == "ok"]
        results["adapters_isolated_valid"] = [r["worker"] for r in good]
        results["adapters_candidate_works"] = [r["worker"] for r in results["runs"] if r.get("acceptance_ok")]
        results["S6_GATE_PASS"] = len(good) >= 2
        results["no_capability_ranking"] = True
        print(json.dumps(results, indent=2))
        return 0 if results["S6_GATE_PASS"] else 1
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
