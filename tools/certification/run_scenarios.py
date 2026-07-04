#!/usr/bin/env python3
"""Run or materialize FCE scenario verdicts, then invoke the FCE scorer.

The first implemented behavior is deliberately conservative: absent scenario
scripts become explicit NOT_RUN verdicts, and NOT_RUN remains a failing state.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from score_certification import REQUIRED_SCENARIOS, score


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


def materialize_missing_not_run(root: Path) -> int:
    created = 0
    for scenario_id in REQUIRED_SCENARIOS:
        verdict_path = root / scenario_id / f"{scenario_id}_verdict.json"
        if verdict_path.exists():
            continue
        write_json(verdict_path, not_run_verdict(scenario_id, "scenario_script_missing"))
        created += 1
    return created


def run_scenarios(root: Path, cert_repo_sha: str, out_final: Path) -> int:
    root.mkdir(parents=True, exist_ok=True)
    created = materialize_missing_not_run(root)
    code = score(root, cert_repo_sha, out_final)
    print(
        json.dumps(
            {
                "schema_id": "turingos.fce.scenario_layer.summary.v1",
                "scenario_count": len(REQUIRED_SCENARIOS),
                "not_run_created": created,
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
        code = run_scenarios(root, "a" * 40, root / "FINAL_CERTIFICATION_VERDICT.json")
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
    parser.add_argument("--cert-repo-sha")
    parser.add_argument("--out-final")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if not args.root or not args.cert_repo_sha or not args.out_final:
        parser.error("--root, --cert-repo-sha, and --out-final are required unless --self-test is used")
    return run_scenarios(Path(args.root), args.cert_repo_sha, Path(args.out_final))


if __name__ == "__main__":
    raise SystemExit(main())
