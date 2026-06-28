#!/usr/bin/env python3
"""Audit worker-visible prompt and capsule bytes for Stage13 leakage."""

from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
MICRO_TAPE_AUDITOR = REPO / "tools" / "bench" / "audit_micro_tape_decision_dag.py"
FORBIDDEN_MARKERS = [
    "pput",
    "vpput",
    "hidden predicate",
    "hidden predicates",
    "private contract",
    "heldout",
    "gold patch",
    "official solution",
    "raw failure log",
    "traceback",
    "stack trace",
    "auth.json",
    "private key",
    "signing key",
    "sk-",
]


def load_micro_tape_auditor() -> Any:
    spec = importlib.util.spec_from_file_location("audit_micro_tape_decision_dag", MICRO_TAPE_AUDITOR)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"cannot load {MICRO_TAPE_AUDITOR}")
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(strings(item))
        return out
    if isinstance(value, dict):
        out: list[str] = []
        for item in value.values():
            out.extend(strings(item))
        return out
    return []


def marker_hits(text: str) -> list[str]:
    lowered = text.lower()
    return sorted({marker for marker in FORBIDDEN_MARKERS if marker in lowered})


def payload(event: dict[str, Any]) -> dict[str, Any]:
    value = event.get("payload")
    return value if isinstance(value, dict) else {}


def audit_run(run: dict[str, Any], auditor: Any, work_root: Path, index: int) -> dict[str, Any]:
    problems: list[str] = []
    native = run.get("native_api_worker")
    if not isinstance(native, dict):
        native = {}
        problems.append("native_api_worker metadata missing")

    prompt_path_value = native.get("visible_prompt_path")
    prompt_scanned = False
    if not isinstance(prompt_path_value, str):
        problems.append("visible_prompt_path missing")
    else:
        prompt_path = Path(prompt_path_value)
        if not prompt_path.exists():
            problems.append(f"visible_prompt_path missing on disk: {prompt_path}")
        else:
            prompt_scanned = True
            hits = marker_hits(prompt_path.read_text(encoding="utf-8"))
            if hits:
                problems.append("visible prompt leak: " + ", ".join(hits))

    bundle_value = run.get("micro_tape_bundle")
    if not isinstance(bundle_value, str):
        return {
            "status": "FAIL",
            "instance_id": run.get("instance_id"),
            "problems": problems + ["micro_tape_bundle missing"],
            "visible_prompt_scanned": prompt_scanned,
        }

    git_dir, _ = auditor.fetch_bundle(Path(bundle_value), work_root / f"stage13_prompt_{index}")
    events = auditor.read_event_chain(git_dir)
    capsules = [payload(event) for event in events if event.get("event_type") == "WorkCapsuleBuilt"]
    if not capsules:
        problems.append("WorkCapsuleBuilt missing")
    for capsule in capsules:
        text = "\n".join(strings(capsule))
        hits = marker_hits(text)
        if hits:
            problems.append("visible capsule leak: " + ", ".join(hits))
        for key in ["pput_formula_absent", "heldout_ids_absent", "hidden_predicates_absent", "raw_failure_logs_absent"]:
            if capsule.get(key) is not True:
                problems.append(f"WorkCapsuleBuilt missing {key}=true")

    return {
        "status": "FAIL" if problems else "PASS",
        "instance_id": run.get("instance_id"),
        "problems": problems,
        "visible_prompt_scanned": prompt_scanned,
        "capsule_count": len(capsules),
    }


def audit_coverage(coverage_path: Path) -> dict[str, Any]:
    coverage = load_json(coverage_path)
    runs = coverage.get("turingos_arm_runs", [])
    if not isinstance(runs, list):
        runs = []
    auditor = load_micro_tape_auditor()
    with tempfile.TemporaryDirectory(prefix="turingos-prompt-leakage-") as temp:
        run_reports = [audit_run(run, auditor, Path(temp), idx) for idx, run in enumerate(runs) if isinstance(run, dict)]
    problems = [problem for report in run_reports for problem in report.get("problems", [])]
    return {
        "schema_id": "PromptLeakageAudit.v1",
        "status": "PASS" if run_reports and all(report["status"] == "PASS" for report in run_reports) else "FAIL",
        "truth_source": "actual_visible_prompt_files_plus_micro_tape_capsules",
        "forbidden_marker_policy": "internal denylist; marker literals omitted from evidence to avoid credential-marker artifacts",
        "run_count": len(run_reports),
        "problems": problems,
        "actual_visible_prompt_bytes_scanned": bool(run_reports)
        and all(report.get("visible_prompt_scanned") is True for report in run_reports),
        "runs": run_reports,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coverage", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    report = audit_coverage(Path(args.coverage))
    write_json(Path(args.out), report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
