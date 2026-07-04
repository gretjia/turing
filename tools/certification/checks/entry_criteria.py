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
AT_LEAST_ADDRESSED = {"ADDRESSED", "EXTERNALLY_VERIFIED"}
EXTERNAL_REQUIRED_GATES = {"M1.G", "M2.G", "M3.G", "M4.G", "M5.G", "M6.G"}


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


def load_json_file(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def certificate_targets(certificate: dict[str, Any]) -> set[str]:
    targets: set[str] = set()
    subject = certificate.get("subject")
    if isinstance(subject, dict):
        for key in ("module_targets", "certified_for_module_targets"):
            values = subject.get(key)
            if isinstance(values, list):
                targets.update(value for value in values if isinstance(value, str))
        for key in ("gate_id", "module_target"):
            value = subject.get(key)
            if isinstance(value, str):
                targets.add(value)

    semantics = certificate.get("status_semantics")
    if isinstance(semantics, dict):
        values = semantics.get("certified_for_module_targets")
        if isinstance(values, list):
            targets.update(value for value in values if isinstance(value, str))
        value = semantics.get("certified_for_gate")
        if isinstance(value, str):
            targets.add(value)
    return targets


def collect_custody_booleans(certificate: dict[str, Any]) -> dict[str, bool]:
    values: dict[str, bool] = {}
    for source in (
        certificate.get("custody"),
        certificate.get("verifier"),
        certificate.get("verifier", {}).get("custody") if isinstance(certificate.get("verifier"), dict) else None,
    ):
        if not isinstance(source, dict):
            continue
        for key, value in source.items():
            if isinstance(value, bool):
                values[key] = value
    return values


def certificate_custody_ok(certificate: dict[str, Any]) -> bool:
    values = collect_custody_booleans(certificate)
    if not values or any(value is False for value in values.values()):
        return False
    required_groups = [
        ("fresh_clone", "fresh_clone_from_github"),
        ("no_shared_conversation_state", "no_implementation_chat_used", "no_local_plan_directory_used"),
        ("own_credentials", "own_credentials_session", "own_cli_credentials_session"),
        ("cross_family_or_human", "cross_family_or_human_verifier", "cross_family_relative_to_implementer"),
        ("own_custody_output",),
    ]
    return all(any(values.get(key) is True for key in group) for group in required_groups)


def external_certificate_index(plan_root: Path) -> dict[str, dict[str, Any]]:
    session = plan_root / "evidence" / "session_20260702"
    certificates: dict[str, dict[str, Any]] = {}
    for path in sorted(session.glob("*CERTIFICATE*.json")):
        certificate = load_json_file(path)
        if certificate is None:
            continue
        if certificate.get("schema_id") != "turingos.closure_certificate.v1":
            continue
        if certificate.get("verdict") != "PASS":
            continue
        if not certificate_custody_ok(certificate):
            continue
        for target in certificate_targets(certificate):
            if target in GATES:
                certificates.setdefault(
                    target,
                    {
                        "path": str(path),
                        "verdict": "PASS",
                        "verifier": certificate.get("verifier", {}),
                        "subject": certificate.get("subject", {}),
                    },
                )
    return certificates


def evaluate_gate_entry_status(plan_root: Path) -> tuple[bool, dict[str, Any]]:
    tracker = plan_root / "PROGRESS_TRACKER.md"
    table_statuses = tracker_gate_statuses(tracker)
    certs = external_certificate_index(plan_root)
    effective_statuses = {gate: table_statuses.get(gate, "MISSING") for gate in GATES}
    external_required: dict[str, dict[str, Any]] = {}

    all_at_least_addressed = all(effective_statuses[gate] in AT_LEAST_ADDRESSED for gate in GATES)
    for gate in EXTERNAL_REQUIRED_GATES:
        table_external = table_statuses.get(gate) == "EXTERNALLY_VERIFIED"
        certificate = certs.get(gate)
        if certificate is not None:
            effective_statuses[gate] = "EXTERNALLY_VERIFIED"
        satisfied = table_external or certificate is not None
        external_required[gate] = {
            "satisfied": satisfied,
            "source": "tracker" if table_external else ("certificate" if certificate is not None else "missing"),
            "certificate": certificate,
        }

    passed = all_at_least_addressed and all(item["satisfied"] for item in external_required.values())
    return passed, {
        "tracker": str(tracker),
        "table_gate_statuses": {gate: table_statuses.get(gate, "MISSING") for gate in GATES},
        "effective_gate_statuses": effective_statuses,
        "external_required_gates": external_required,
    }


def criterion(item_id: str, description: str, passed: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item_id,
        "description": description,
        "verdict": "PASS" if passed else "FAIL",
        "evidence": evidence,
    }


def build_manifest(repo: Path, plan_root: Path, budget_ceiling_microusd: int) -> dict[str, Any]:
    entry: list[dict[str, Any]] = []
    e1_pass, e1_evidence = evaluate_gate_entry_status(plan_root)
    entry.append(
        criterion(
            "E1",
            "All module gates M0.G-M6.G at least ADDRESSED; external-required gates are EXTERNALLY_VERIFIED",
            e1_pass,
            e1_evidence,
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
