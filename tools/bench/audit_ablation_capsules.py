#!/usr/bin/env python3
"""Audit M3.P6 Arm B/C visible capsules for ablation honesty."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from pathlib import Path
from typing import Any


BROADCAST_SECTION_BEGIN = "<!-- BEGIN_TURINGOS_BROADCAST_RULES -->"
BROADCAST_SECTION_END = "<!-- END_TURINGOS_BROADCAST_RULES -->"


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def strip_broadcast_section(text: str) -> tuple[str, bool]:
    begin = text.find(BROADCAST_SECTION_BEGIN)
    end = text.find(BROADCAST_SECTION_END)
    if begin < 0 and end < 0:
        return text, False
    if begin < 0 or end < begin:
        return text, False
    end += len(BROADCAST_SECTION_END)
    line_start = text.rfind("\n", 0, begin)
    if line_start < 0:
        line_start = begin
    else:
        line_start += 1
    line_end = text.find("\n", end)
    if line_end < 0:
        line_end = end
    else:
        line_end += 1
    return text[:line_start] + "## TuringOS Failure-Memory Broadcast Rules\n<BROADCAST_RULES_STRIPPED>\n" + text[line_end:], True


def capsule_files(root: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for path in sorted(root.glob("*/worker_visible_capsule.md")):
        files[path.parent.name] = path
    return files


def audit_capsules(arm_b_dir: Path, arm_c_dir: Path) -> dict[str, Any]:
    b_files = capsule_files(arm_b_dir)
    c_files = capsule_files(arm_c_dir)
    problems: list[str] = []
    rows: list[dict[str, Any]] = []
    for instance_id in sorted(set(b_files) | set(c_files)):
        b_path = b_files.get(instance_id)
        c_path = c_files.get(instance_id)
        if b_path is None or c_path is None:
            problems.append(f"{instance_id}: missing B or C capsule")
            rows.append(
                {
                    "instance_id": instance_id,
                    "status": "FAIL",
                    "problem": "missing B or C capsule",
                    "arm_b_path": str(b_path) if b_path else None,
                    "arm_c_path": str(c_path) if c_path else None,
                }
            )
            continue
        b_text = b_path.read_text(encoding="utf-8")
        c_text = c_path.read_text(encoding="utf-8")
        b_stripped, b_had_section = strip_broadcast_section(b_text)
        c_stripped, c_had_section = strip_broadcast_section(c_text)
        status = "PASS" if b_stripped == c_stripped else "FAIL"
        row: dict[str, Any] = {
            "instance_id": instance_id,
            "status": status,
            "arm_b_path": str(b_path),
            "arm_c_path": str(c_path),
            "arm_b_sha256": sha256_text(b_text),
            "arm_c_sha256": sha256_text(c_text),
            "arm_b_broadcast_section_present": b_had_section,
            "arm_c_broadcast_section_present": c_had_section,
        }
        if status != "PASS":
            problems.append(f"{instance_id}: capsule diff outside broadcast section")
            diff = difflib.unified_diff(
                b_stripped.splitlines(),
                c_stripped.splitlines(),
                fromfile="arm_b_stripped",
                tofile="arm_c_stripped",
                lineterm="",
            )
            row["stripped_diff_preview"] = "\n".join(list(diff)[:80])
        rows.append(row)
    return {
        "schema_id": "turingos.m3.ablation_capsule_audit.v1",
        "status": "PASS" if not problems else "FAIL",
        "arm_b_dir": str(arm_b_dir),
        "arm_c_dir": str(arm_c_dir),
        "capsule_count": len(rows),
        "problems": problems,
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm-b-dir", type=Path, required=True)
    parser.add_argument("--arm-c-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    report = audit_capsules(args.arm_b_dir, args.arm_c_dir)
    write_json(args.out, report)
    print(json.dumps({"status": report["status"], "capsule_count": report["capsule_count"]}, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
