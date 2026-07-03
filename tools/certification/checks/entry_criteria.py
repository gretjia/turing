#!/usr/bin/env python3
"""Check FCE entry criteria E1-E7 and write FCE_RUN_MANIFEST.json."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONSTITUTION_SHA256 = "a0174ef8a2be6914f86ea8e594e022c7ca6a4221ed63535d65a997e096ca3ad0"
GATES = ["M0.G", "M1.G", "M2.G", "M3.G", "M4.G", "M5.G", "M6.G"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(argv: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)


def git_output(repo: Path, *args: str) -> tuple[int, str]:
    proc = run(["git", *args], cwd=repo)
    return proc.returncode, proc.stdout.strip()


def tracker_gate_statuses(tracker: Path) -> dict[str, str]:
    statuses: dict[str, str] = {}
    if not tracker.is_file():
        return statuses
    for raw in tracker.read_text(encoding="utf-8").splitlines():
        if not raw.startswith("| M"):
            continue
        cells = [cell.strip() for cell in raw.split("|")]
        if len(cells) < 7:
            continue
        phase = cells[1]
        if phase in GATES:
            statuses[phase] = cells[6]
    return statuses


def criterion(item_id: str, description: str, passed: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item_id,
        "description": description,
        "verdict": "PASS" if passed else "FAIL",
        "evidence": evidence,
    }


def build_manifest(repo: Path, plan_root: Path, budget_ceiling_microusd: int) -> dict[str, Any]:
    entry: list[dict[str, Any]] = []
    tracker = plan_root / "PROGRESS_TRACKER.md"
    statuses = tracker_gate_statuses(tracker)
    e1_pass = all(statuses.get(gate) == "ADDRESSED" for gate in GATES)
    entry.append(
        criterion(
            "E1",
            "All module gates M0.G-M6.G addressed with required verifier artifacts",
            e1_pass,
            {"gate_statuses": {gate: statuses.get(gate, "MISSING") for gate in GATES}, "tracker": str(tracker)},
        )
    )

    rev_code, rev = git_output(repo, "rev-parse", "HEAD")
    status_code, status = git_output(repo, "status", "--porcelain")
    e2_pass = rev_code == 0 and status_code == 0 and status == ""
    entry.append(
        criterion(
            "E2",
            "Pinned repo SHA and clean working tree",
            e2_pass,
            {"repo": str(repo), "rev_parse_exit": rev_code, "cert_repo_sha": rev, "status_porcelain": status},
        )
    )

    constitution = plan_root.parent / "turing_v5/pack_v5_3_1/00_authority/constitution_root_law.md"
    constitution_digest = sha256_file(constitution) if constitution.is_file() else None
    entry.append(
        criterion(
            "E3",
            "Constitution byte identity",
            constitution_digest == CONSTITUTION_SHA256,
            {"path": str(constitution), "sha256": constitution_digest},
        )
    )

    verifier = plan_root / "governance/verify_alignment.sh"
    verify_proc = run(["bash", str(verifier)]) if verifier.is_file() else subprocess.CompletedProcess([], 127, "missing")
    entry.append(
        criterion(
            "E4",
            "M0 alignment verifier GREEN",
            verify_proc.returncode == 0,
            {"command": f"bash {verifier}", "exit_code": verify_proc.returncode},
        )
    )

    prereg = plan_root / "m3_uplift_lab/PREREGISTRATION.sha256"
    entry.append(
        criterion(
            "E5",
            "M3 pre-registration packet frozen",
            prereg.is_file(),
            {"path": str(prereg), "exists": prereg.is_file()},
        )
    )

    separated = os.environ.get("FCE_CONTEXT_SEPARATED") == "yes"
    entry.append(
        criterion(
            "E6",
            "Certification agent context separation",
            separated,
            {"role": "certification_eval_agent", "FCE_CONTEXT_SEPARATED": os.environ.get("FCE_CONTEXT_SEPARATED", "")},
        )
    )

    entry.append(
        criterion(
            "E7",
            "Budget authorization",
            budget_ceiling_microusd > 0,
            {"budget_ceiling_microusd": budget_ceiling_microusd},
        )
    )
    met = all(item["verdict"] == "PASS" for item in entry)
    return {
        "schema_id": "turingos.fce_run_manifest.v1",
        "created_at_utc": utc_now(),
        "cert_repo_sha": rev,
        "entry_criteria": entry,
        "entry_criteria_met": met,
        "scenarios_default_verdict": "READY" if met else "NOT_RUN",
        "not_run_is_fail": True,
        "status_ceiling": "ADDRESSED",
    }


def run_check(repo: Path, plan_root: Path, out: Path, budget_ceiling_microusd: int) -> int:
    manifest = build_manifest(repo, plan_root, budget_ceiling_microusd)
    write_json(out, manifest)
    print(json.dumps({"schema_id": "turingos.fce.entry_criteria.summary.v1", "entry_criteria_met": manifest["entry_criteria_met"]}, sort_keys=True))
    return 0 if manifest["entry_criteria_met"] else 1


def self_test() -> int:
    repo = Path(__file__).resolve().parents[3]
    plan = repo.parent / "PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702"
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "manifest.json"
        code = run_check(repo, plan, out, 50_000_000)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert code == 1
        assert data["entry_criteria_met"] is False
        assert data["scenarios_default_verdict"] == "NOT_RUN"
        assert any(item["id"] == "E1" for item in data["entry_criteria"])
    print("FCE_ENTRY_CRITERIA_SELF_TEST_PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo")
    parser.add_argument("--plan-root")
    parser.add_argument("--out")
    parser.add_argument("--budget-ceiling-microusd", type=int, default=0)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if not args.repo or not args.plan_root or not args.out:
        parser.error("--repo, --plan-root, and --out are required unless --self-test is used")
    return run_check(Path(args.repo), Path(args.plan_root), Path(args.out), args.budget_ceiling_microusd)


if __name__ == "__main__":
    raise SystemExit(main())
