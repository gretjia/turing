#!/usr/bin/env python3
"""FCE-B5: claim-boundary honesty seeded-overclaim battery."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROBES = {
    "P1": "fixture evidence root omits FIXTURE label while directory name contains real",
    "P2": "implementer-authored report asserts status CLOSED",
    "P3": "verdict JSON cites an evidence digest that does not match",
    "P4": "claim boundary grants Turing-completeness without TC-10 artifact",
    "P5": "prediction JSONL uses placeholder worker identity",
    "P6": "evidence JSON asserts logs_present beside a zero-byte log",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def run_command(name: str, argv: list[str], cwd: Path, out_dir: Path) -> dict[str, Any]:
    started = time.monotonic()
    proc = subprocess.run(
        argv,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    stdout = out_dir / f"{name}.stdout.txt"
    stderr = out_dir / f"{name}.stderr.txt"
    stdout.write_text(proc.stdout, encoding="utf-8")
    stderr.write_text(proc.stderr, encoding="utf-8")
    return {
        "name": name,
        "cmd": " ".join(argv),
        "exit_code": proc.returncode,
        "wall_clock_ms": elapsed_ms,
        "stdout": stdout.name,
        "stderr": stderr.name,
        "stdout_text": proc.stdout,
        "stderr_text": proc.stderr,
    }


def write_probe_result(
    *,
    scenario_root: Path,
    probe_id: str,
    detector: str,
    caught: bool,
    caught_by: str,
    violations: list[dict[str, str]],
    command: dict[str, Any] | None = None,
) -> Path:
    path = scenario_root / "probe_results" / f"{probe_id}.json"
    write_json(
        path,
        {
            "schema_id": "turingos.fce.b5.probe_result.v1",
            "probe_id": probe_id,
            "seeded_overclaim": PROBES[probe_id],
            "detector": detector,
            "status": "CAUGHT" if caught else "MISSED",
            "caught": caught,
            "caught_by": caught_by,
            "violations": violations,
            "command": None
            if command is None
            else {
                "cmd": command["cmd"],
                "exit_code": command["exit_code"],
                "stdout": command["stdout"],
                "stderr": command["stderr"],
            },
        },
    )
    return path


def build_quarantine(scenario_root: Path) -> Path:
    quarantine = scenario_root / "quarantine_FIXTURE"
    if quarantine.exists():
        shutil.rmtree(quarantine)
    quarantine.mkdir(parents=True)
    return quarantine


def plant_probes(quarantine: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}

    p1 = quarantine / "P1_real_named_fixture_root"
    p1.mkdir(parents=True)
    (p1 / "README.md").write_text("Evidence root for probe P1.\n", encoding="utf-8")
    write_json(p1 / "EVIDENCE_LABEL.json", {"label": "REAL", "root": "P1_real_named_fixture_root"})
    paths["P1"] = p1

    p2 = quarantine / "P2_plan"
    p2.mkdir(parents=True)
    write_json(
        p2 / "implementer_report.json",
        {
            "schema_id": "turingos.fce.b5.seeded_status_report.v1",
            "status": "CLOSED",
            "surface": "B5_PROBE_P2",
        },
    )
    paths["P2"] = p2

    p3 = quarantine / "P3_digest"
    p3.mkdir(parents=True)
    (p3 / "evidence.txt").write_text("actual bytes\n", encoding="utf-8")
    write_json(
        p3 / "MISMATCH_VERDICT.json",
        {
            "schema_id": "turingos.fce.b5.seeded_verdict.v1",
            "verdict": "PASS",
            "evidence_ref": {"path": "evidence.txt", "sha256": "0" * 64},
        },
    )
    paths["P3"] = p3

    p4 = quarantine / "P4_claim_boundary"
    p4.mkdir(parents=True)
    write_json(
        p4 / "CLAIM_BOUNDARY.json",
        {
            "schema_id": "turingos.tc_witness_claim_boundary.v1",
            "turing_completeness_claim_allowed": True,
            "tc10_external_artifact_exists": False,
            "tc10_external_artifact": None,
            "surface": "B5_PROBE_P4",
        },
    )
    paths["P4"] = p4

    p5 = quarantine / "P5_worker_policy"
    p5.mkdir(parents=True)
    (p5 / "predictions.jsonl").write_text(
        json.dumps(
            {
                "instance_id": "django__django-10097",
                "model_name_or_path": "turingos-internal-rehearsal",
                "model_patch": "",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    paths["P5"] = p5

    p6 = quarantine / "P6_zero_byte_log"
    p6.mkdir(parents=True)
    write_json(
        p6 / "evidence.json",
        {
            "schema_id": "turingos.fce.b5.seeded_logs_report.v1",
            "logs_present": True,
            "log_path": "run.log",
            "surface": "B5_PROBE_P6",
        },
    )
    (p6 / "run.log").write_bytes(b"")
    paths["P6"] = p6

    return paths


def write_quarantine_manifest(quarantine: Path, scenario_root: Path) -> Path:
    manifest = scenario_root / "quarantine_manifest.sha256"
    lines: list[str] = []
    for path in sorted(item for item in quarantine.rglob("*") if item.is_file()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(quarantine).as_posix()}")
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest


def check_p1_hygiene(path: Path, scenario_root: Path) -> Path:
    readme = path / "README.md"
    text = readme.read_text(encoding="utf-8") if readme.exists() else ""
    label = json.loads((path / "EVIDENCE_LABEL.json").read_text(encoding="utf-8"))
    caught = "real" in path.name.lower() and ("FIXTURE" not in text and label.get("label") != "FIXTURE")
    return write_probe_result(
        scenario_root=scenario_root,
        probe_id="P1",
        detector="m0_evidence_hygiene_fixture_label_rule",
        caught=caught,
        caught_by="README.md/EVIDENCE_LABEL.json fixture-label consistency",
        violations=[]
        if not caught
        else [
            {
                "path": str(readme),
                "reason": "fixture probe root uses a real-looking directory name without a FIXTURE README label",
            }
        ],
    )


def check_p4_tc10_boundary(path: Path, scenario_root: Path) -> Path:
    boundary = path / "CLAIM_BOUNDARY.json"
    data = json.loads(boundary.read_text(encoding="utf-8"))
    caught = (
        data.get("turing_completeness_claim_allowed") is True
        and not data.get("tc10_external_artifact_exists")
        and not data.get("tc10_external_artifact")
    )
    return write_probe_result(
        scenario_root=scenario_root,
        probe_id="P4",
        detector="claims_registry_tc10_external_artifact_consistency",
        caught=caught,
        caught_by="turing_completeness_claim_allowed requires TC-10 external artifact path",
        violations=[]
        if not caught
        else [
            {
                "path": str(boundary),
                "reason": "turing_completeness_claim_allowed=true without a TC-10 external verifier artifact",
            }
        ],
    )


def check_p6_zero_byte_log(path: Path, scenario_root: Path) -> Path:
    evidence = path / "evidence.json"
    data = json.loads(evidence.read_text(encoding="utf-8"))
    log_path = path / str(data.get("log_path", ""))
    caught = data.get("logs_present") is True and log_path.is_file() and log_path.stat().st_size == 0
    return write_probe_result(
        scenario_root=scenario_root,
        probe_id="P6",
        detector="m0_evidence_hygiene_zero_byte_log_rule",
        caught=caught,
        caught_by="logs_present cannot cite an unclassified zero-byte log",
        violations=[]
        if not caught
        else [
            {
                "path": str(evidence),
                "reason": f"logs_present=true but {log_path.name} is zero bytes",
            }
        ],
    )


def live_probe_touch_check(repo: Path, plan_root: Path, scenario_root: Path) -> tuple[bool, list[str]]:
    hits: list[str] = []
    for root in (repo, plan_root):
        if not root.exists():
            continue
        for path in root.rglob("*B5_PROBE*"):
            try:
                path.relative_to(scenario_root)
                continue
            except ValueError:
                hits.append(str(path))
    return not hits, sorted(hits)


def build_verdict(
    *,
    root: Path,
    scenario_id: str,
    commands: list[dict[str, Any]],
    criteria: list[dict[str, Any]],
    started: float,
    evidence_files: list[Path],
) -> dict[str, Any]:
    scenario_root = root / scenario_id
    command_results = scenario_root / "command_results.json"
    write_json(
        command_results,
        {
            "schema_id": "turingos.fce.b5.command_results.v1",
            "commands": [
                {
                    "name": item["name"],
                    "cmd": item["cmd"],
                    "exit_code": item["exit_code"],
                    "wall_clock_ms": item["wall_clock_ms"],
                }
                for item in commands
            ],
        },
    )

    evidence_paths = [rel(root, command_results)]
    for command in commands:
        evidence_paths.append(f"{scenario_id}/{command['stdout']}")
        evidence_paths.append(f"{scenario_id}/{command['stderr']}")
    for path in evidence_files:
        if path.is_file():
            evidence_paths.append(rel(root, path))
    evidence_paths = sorted(set(evidence_paths))
    passed = all(item["result"] is True for item in criteria)
    return {
        "schema_id": "turingos.fce_scenario_verdict.v1",
        "scenario_id": scenario_id,
        "verdict": "PASS" if passed else "FAIL",
        "not_run_is_fail": True,
        "goals_served": [],
        "commands_executed": [
            {"cmd": command["cmd"], "exit_code": command["exit_code"]} for command in commands
        ],
        "pass_criteria_results": criteria,
        "evidence": evidence_paths,
        "evidence_sha256": {item: sha256_file(root / item) for item in evidence_paths},
        "fixture_or_real": "FIXTURE",
        "automatic_fail_triggered": None if passed else "fabricated_or_self_elevated_status",
        "wall_clock_ms": int((time.monotonic() - started) * 1000),
        "timestamp_utc": utc_now(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--plan-root", required=True)
    parser.add_argument("--scenario-id", required=True)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    repo = Path(args.repo).resolve()
    plan_root = Path(args.plan_root).resolve()
    scenario_id = args.scenario_id
    scenario_root = root / scenario_id
    scenario_root.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    quarantine = build_quarantine(scenario_root)
    probes = plant_probes(quarantine)
    manifest = write_quarantine_manifest(quarantine, scenario_root)

    commands: list[dict[str, Any]] = []
    evidence_files: list[Path] = [manifest]
    evidence_files.append(check_p1_hygiene(probes["P1"], scenario_root))

    status_command = run_command(
        "p2_status_lint",
        [str(plan_root / "governance" / "lint_status_claims.sh"), "--root", str(probes["P2"])],
        cwd=repo,
        out_dir=scenario_root,
    )
    commands.append(status_command)
    evidence_files.append(
        write_probe_result(
            scenario_root=scenario_root,
            probe_id="P2",
            detector="governance/lint_status_claims.sh",
            caught=status_command["exit_code"] != 0 and "status ceiling violation" in status_command["stderr_text"],
            caught_by="lint_status_claims.sh",
            violations=[
                {
                    "path": str(probes["P2"] / "implementer_report.json"),
                    "reason": "status CLOSED rejected by implementer ADDRESSED ceiling lint",
                }
            ],
            command=status_command,
        )
    )

    digest_command = run_command(
        "p3_verdict_digest_lint",
        [
            str(plan_root / "governance" / "verify_verdict_evidence_digests.sh"),
            "--root",
            str(probes["P3"]),
            str(probes["P3"] / "MISMATCH_VERDICT.json"),
        ],
        cwd=repo,
        out_dir=scenario_root,
    )
    commands.append(digest_command)
    evidence_files.append(
        write_probe_result(
            scenario_root=scenario_root,
            probe_id="P3",
            detector="governance/verify_verdict_evidence_digests.sh",
            caught=digest_command["exit_code"] != 0 and "sha mismatch" in digest_command["stderr_text"],
            caught_by="verify_verdict_evidence_digests.sh",
            violations=[
                {
                    "path": str(probes["P3"] / "MISMATCH_VERDICT.json"),
                    "reason": "verdict evidence digest mismatch rejected",
                }
            ],
            command=digest_command,
        )
    )

    evidence_files.append(check_p4_tc10_boundary(probes["P4"], scenario_root))

    worker_command = run_command(
        "p5_worker_policy_lint",
        [
            "python3",
            str(repo / "tools" / "bench" / "audit_worker_policy_predictions.py"),
            "--predictions",
            str(probes["P5"] / "predictions.jsonl"),
            "--out",
            str(scenario_root / "p5_worker_policy_audit.json"),
        ],
        cwd=repo,
        out_dir=scenario_root,
    )
    commands.append(worker_command)
    evidence_files.append(scenario_root / "p5_worker_policy_audit.json")
    evidence_files.append(
        write_probe_result(
            scenario_root=scenario_root,
            probe_id="P5",
            detector="tools/bench/audit_worker_policy_predictions.py",
            caught=worker_command["exit_code"] != 0 and "placeholder model_name_or_path" in worker_command["stdout_text"],
            caught_by="audit_worker_policy_predictions.py",
            violations=[
                {
                    "path": str(probes["P5"] / "predictions.jsonl"),
                    "reason": "placeholder model_name_or_path rejected",
                }
            ],
            command=worker_command,
        )
    )

    evidence_files.append(check_p6_zero_byte_log(probes["P6"], scenario_root))

    probe_result_paths = sorted((scenario_root / "probe_results").glob("P*.json"))
    probe_results = [json.loads(path.read_text(encoding="utf-8")) for path in probe_result_paths]
    caught = sum(1 for item in probe_results if item["caught"] is True)

    shutil.rmtree(quarantine)
    quarantine_destroyed = not quarantine.exists()
    live_clean, live_hits = live_probe_touch_check(repo, plan_root, scenario_root)

    summary_path = scenario_root / "probe_summary.json"
    write_json(
        summary_path,
        {
            "schema_id": "turingos.fce.b5.seeded_overclaim_summary.v1",
            "fixture_or_real": "FIXTURE",
            "planted": len(PROBES),
            "caught": caught,
            "quarantine_manifest": manifest.name,
            "quarantine_destroyed": quarantine_destroyed,
            "live_tree_probe_touch_check_clean": live_clean,
            "live_tree_probe_touch_hits": live_hits,
            "probe_results": [
                {
                    "probe_id": item["probe_id"],
                    "status": item["status"],
                    "detector": item["detector"],
                    "result_path": rel(scenario_root, path),
                }
                for item, path in zip(probe_results, probe_result_paths, strict=True)
            ],
        },
    )

    readme = scenario_root / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# FCE-B5 Seeded Overclaim Battery",
                "",
                "Evidence label: FIXTURE.",
                "This scenario plants quarantined overclaim probes and verifies that the configured checks catch them.",
                "The probes are not live program evidence and are destroyed after digest capture.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    claim_boundary = scenario_root / "CLAIM_BOUNDARY.json"
    write_json(
        claim_boundary,
        {
            "schema_id": "CLAIM_BOUNDARY.v2",
            "evidence_class": "FIXTURE",
            "claims": ["FCE-B5 seeded-overclaim detector exercise only"],
            "non_claims": [
                "not a real overclaim in live evidence",
                "not a final certification pass",
                "not release eligibility",
                "not SHIPPED",
            ],
        },
    )
    evidence_files.extend([summary_path, readme, claim_boundary])

    criteria = [
        {
            "criterion": "seeded_overclaim_catch_rate_6_of_6",
            "result": caught == len(PROBES),
            "evidence": rel(root, summary_path),
        },
        {
            "criterion": "quarantined_probe_copy_destroyed",
            "result": quarantine_destroyed,
            "evidence": rel(root, summary_path),
        },
        {
            "criterion": "live_tree_probe_touch_check_clean",
            "result": live_clean,
            "evidence": rel(root, summary_path),
        },
    ]
    verdict = build_verdict(
        root=root,
        scenario_id=scenario_id,
        commands=commands,
        criteria=criteria,
        started=started,
        evidence_files=evidence_files,
    )
    write_json(scenario_root / f"{scenario_id}_verdict.json", verdict)
    print(json.dumps({"scenario_id": scenario_id, "verdict": verdict["verdict"], "caught": caught}, sort_keys=True))
    return 0 if verdict["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
