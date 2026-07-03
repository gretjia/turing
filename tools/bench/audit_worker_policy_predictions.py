#!/usr/bin/env python3
"""Audit benchmark prediction JSONL worker identity policy."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*__arm[A-D]__[A-Za-z0-9][A-Za-z0-9._+-]*$")

PLACEHOLDER_MODEL_NAMES = {
    "direct_grok_baseline",
    "model",
    "placeholder",
    "test",
    "tbd",
    "turingos-internal-rehearsal",
    "turingos-test",
    "unknown",
}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def iter_prediction_rows(path: Path):
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        yield line_number, row


def audit_prediction_files(paths: list[Path]) -> dict[str, Any]:
    problems: list[str] = []
    rows: list[dict[str, Any]] = []
    for path in paths:
        for line_number, row in iter_prediction_rows(path):
            model_name = row.get("model_name_or_path")
            instance_id = row.get("instance_id")
            if not isinstance(model_name, str) or not model_name:
                problems.append(f"{path.name}:{line_number} model_name_or_path missing")
                continue
            if model_name.lower() in PLACEHOLDER_MODEL_NAMES or "placeholder" in model_name.lower():
                problems.append(f"{path.name}:{line_number} placeholder model_name_or_path: {model_name}")
                continue
            if MODEL_NAME_RE.fullmatch(model_name) is None:
                problems.append(f"{path.name}:{line_number} model_name_or_path must match worker__arm__experiment: {model_name}")
                continue
            rows.append(
                {
                    "file": str(path),
                    "line": line_number,
                    "instance_id": instance_id,
                    "model_name_or_path": model_name,
                }
            )

    return {
        "schema_id": "turingos.worker_policy_predictions_audit.v1",
        "status": "PASS" if not problems else "FAIL",
        "model_name_policy": "worker__arm__experiment",
        "placeholder_model_names_forbidden": sorted(PLACEHOLDER_MODEL_NAMES),
        "file_count": len(paths),
        "row_count": len(rows),
        "problems": problems,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = audit_prediction_files(args.predictions)
    if args.out:
        write_json(args.out, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
