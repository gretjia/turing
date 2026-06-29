#!/usr/bin/env python3
"""Reduce 10 sealed SWE-bench Verified 500 shard audits into a campaign audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def audit_campaign(root: Path) -> dict[str, Any]:
    problems: list[str] = []
    task_manifest = load_json(root / "task_manifest.json")
    claim = load_json(root / "CLAIM_BOUNDARY.json")
    instance_ids = task_manifest.get("instance_ids", [])
    if task_manifest.get("task_count") != 500:
        problems.append("task_count must be 500")
    if not isinstance(instance_ids, list) or len(instance_ids) != 500:
        problems.append("instance_ids must contain 500 entries")
    elif len(set(instance_ids)) != 500:
        problems.append("instance_ids must be unique")
    if claim.get("leaderboard_equivalence_claim_allowed") is not False:
        problems.append("leaderboard equivalence claim must remain false")
    if claim.get("official_leaderboard_submission_claim_allowed") is not False:
        problems.append("official leaderboard submission claim must remain false")

    shard_reports: list[dict[str, Any]] = []
    for shard_index in range(10):
        shard_id = f"S{shard_index:02d}"
        path = root / "shards" / shard_id / "shard_audit.json"
        if not path.exists():
            problems.append(f"shard {shard_id} audit missing")
            continue
        report = load_json(path)
        shard_reports.append(report)
        if report.get("status") != "PASS":
            problems.append(f"shard {shard_id} status is {report.get('status')}")
        if report.get("task_count") != 50:
            problems.append(f"shard {shard_id} task_count must be 50")

    resolved = sum(int(report.get("resolved_count", 0)) for report in shard_reports)
    unresolved = sum(int(report.get("unresolved_count", 0)) for report in shard_reports)
    infra_failed = sum(int(report.get("infra_failed_count", 0)) for report in shard_reports)
    status = "PASS" if not problems else "BLOCKED"
    report = {
        "schema_id": "turingos.swebench_campaign_audit.v1",
        "status": status,
        "problems": problems,
        "shard_count": len(shard_reports),
        "task_count": task_manifest.get("task_count"),
        "resolved_count": resolved,
        "unresolved_count": unresolved,
        "infra_failed_count": infra_failed,
        "leaderboard_equivalence_claim_allowed": claim.get("leaderboard_equivalence_claim_allowed"),
        "next_action": "final_positioning_report" if status == "PASS" else "repair_blocked_shards",
    }
    write_json(root / "final" / "campaign_audit.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    report = audit_campaign(args.root)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
