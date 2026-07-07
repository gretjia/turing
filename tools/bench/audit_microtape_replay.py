#!/usr/bin/env python3
"""Audit task-level MicroTape replay reports for a campaign shard/root."""

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


def audit_replay(root: Path, shard: str | None = None) -> dict[str, Any]:
    shard_ids = [shard] if shard else sorted(path.name for path in (root / "shards").glob("S*") if path.is_dir())
    problems: list[str] = []
    checked = 0
    for shard_id in shard_ids:
        for replay in (root / "shards" / shard_id / "tasks").glob("*/microtape/replay_report.json"):
            checked += 1
            report = load_json(replay)
            if report.get("status") != "PASS":
                problems.append(f"{replay}: status={report.get('status')}")
    return {
        "schema_id": "turingos.swebench_microtape_replay_audit.v1",
        "status": "PASS" if not problems else "FAIL",
        "problems": problems,
        "replay_reports_checked": checked,
        "shard": shard,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--shard")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = audit_replay(args.root, args.shard)
    write_json(args.out, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
