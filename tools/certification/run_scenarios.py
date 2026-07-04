#!/usr/bin/env python3
"""Run or materialize FCE scenario verdicts, then invoke the FCE scorer.

The first implemented behavior is deliberately conservative: absent scenario
scripts become explicit NOT_RUN verdicts, and NOT_RUN remains a failing state.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from score_certification import REQUIRED_SCENARIOS, score


SCRIPT_DIR = Path(__file__).resolve().parent


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def not_run_verdict(scenario_id: str, reason: str) -> dict[str, Any]:
    return {
        "schema_id": "turingos.fce_scenario_verdict.v1",
        "scenario_id": scenario_id,
        "verdict": "NOT_RUN",
        "not_run_is_fail": True,
        "goals_served": [],
        "commands_executed": [],
        "pass_criteria_results": [],
        "evidence": [],
        "evidence_sha256": {},
        "fixture_or_real": "FIXTURE",
        "automatic_fail_triggered": None,
        "wall_clock_ms": 0,
        "timestamp_utc": utc_now(),
        "not_run_reason": reason,
    }


def scenario_script(scenarios_dir: Path, scenario_id: str) -> Path | None:
    for suffix in (".py", ".sh"):
        path = scenarios_dir / f"{scenario_id}{suffix}"
        if path.is_file():
            return path
    return None


def run_available_scripts(root: Path, repo: Path, plan_root: Path, scenarios_dir: Path) -> dict[str, int]:
    results: dict[str, int] = {}
    for scenario_id in REQUIRED_SCENARIOS:
        script = scenario_script(scenarios_dir, scenario_id)
        if script is None:
            continue
        verdict_path = root / scenario_id / f"{scenario_id}_verdict.json"
        if verdict_path.exists():
            continue
        if script.suffix == ".py":
            argv = [sys.executable, str(script)]
        else:
            argv = ["bash", str(script)]
        argv.extend(
            [
                "--root",
                str(root),
                "--repo",
                str(repo),
                "--plan-root",
                str(plan_root),
                "--scenario-id",
                scenario_id,
            ]
        )
        proc = subprocess.run(argv, cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        results[scenario_id] = proc.returncode
        log_path = root / scenario_id / "scenario_script.stdout.txt"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(proc.stdout, encoding="utf-8")
        if proc.returncode != 0 and not verdict_path.exists():
            write_json(verdict_path, not_run_verdict(scenario_id, "scenario_script_failed"))
    return results


def materialize_missing_not_run(root: Path) -> int:
    created = 0
    for scenario_id in REQUIRED_SCENARIOS:
        verdict_path = root / scenario_id / f"{scenario_id}_verdict.json"
        if verdict_path.exists():
            continue
        write_json(verdict_path, not_run_verdict(scenario_id, "scenario_script_missing"))
        created += 1
    return created


def run_scenarios(root: Path, repo: Path, plan_root: Path, scenarios_dir: Path, cert_repo_sha: str, out_final: Path) -> int:
    root.mkdir(parents=True, exist_ok=True)
    script_results = run_available_scripts(root, repo, plan_root, scenarios_dir)
    created = materialize_missing_not_run(root)
    code = score(root, cert_repo_sha, out_final)
    print(
        json.dumps(
            {
                "schema_id": "turingos.fce.scenario_layer.summary.v1",
                "scenario_count": len(REQUIRED_SCENARIOS),
                "not_run_created": created,
                "scripts_executed": len(script_results),
                "score_exit_code": code,
            },
            sort_keys=True,
        )
    )
    print("FCE_SCENARIO_LAYER_EXECUTED")
    return code


def self_test() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        scenarios = root / "empty_scenarios"
        scenarios.mkdir()
        code = run_scenarios(
            root,
            Path.cwd(),
            Path.cwd(),
            scenarios,
            "a" * 40,
            root / "FINAL_CERTIFICATION_VERDICT.json",
        )
        assert code == 1
        verdict = json.loads((root / "FCE-S1" / "FCE-S1_verdict.json").read_text(encoding="utf-8"))
        assert verdict["verdict"] == "NOT_RUN"
        assert verdict["not_run_reason"] == "scenario_script_missing"
        final = json.loads((root / "FINAL_CERTIFICATION_VERDICT.json").read_text(encoding="utf-8"))
        assert final["overall"] == "CERTIFICATION_FAILED"
    print("FCE_SCENARIO_RUNNER_SELF_TEST_PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root")
    parser.add_argument("--repo")
    parser.add_argument("--plan-root")
    parser.add_argument("--scenarios-dir")
    parser.add_argument("--cert-repo-sha")
    parser.add_argument("--out-final")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if not args.root or not args.cert_repo_sha or not args.out_final:
        parser.error("--root, --cert-repo-sha, and --out-final are required unless --self-test is used")
    repo = Path(args.repo).resolve() if args.repo else Path.cwd()
    plan_root = Path(args.plan_root).resolve() if args.plan_root else repo.parent / "PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702"
    scenarios_dir = Path(args.scenarios_dir).resolve() if args.scenarios_dir else SCRIPT_DIR / "scenarios"
    return run_scenarios(Path(args.root), repo, plan_root, scenarios_dir, args.cert_repo_sha, Path(args.out_final))


if __name__ == "__main__":
    raise SystemExit(main())
