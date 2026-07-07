#!/usr/bin/env python3
"""Build a scoped positioning report from sealed shard evidence."""

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


def build_report(root: Path, shard: str, out: Path | None = None) -> str:
    audit_path = root / "shards" / shard / "shard_audit.json"
    audit: dict[str, Any] = load_json(audit_path) if audit_path.exists() else {"status": "NOT_RUN"}
    text = f"""# SWE-bench Shard {shard} Positioning Report

## Scope

This report summarizes one internal upstream-harness shard audit atom. It is
not a leaderboard-equivalence claim and not a full SWE-bench dataset claim.

## External Compatibility

- shard_status: {audit.get("status")}
- task_count: {audit.get("task_count")}
- resolved_count: {audit.get("resolved_count")}
- unresolved_count: {audit.get("unresolved_count")}
- infra_failed_count: {audit.get("infra_failed_count")}

## TuringOS-Native Integrity

- microtape_replay: {audit.get("microtape_replay")}
- required_evidence_missing: {audit.get("required_evidence_missing")}
- official_harness_identity: {audit.get("official_harness_identity")}
- gold_patch_guard: {audit.get("gold_patch_guard")}

## Interpretation

The shard gate decides evidence integrity and replayability. It does not make
product superiority, official leaderboard, or full-score claims.
"""
    out = out or root / "shards" / shard / "positioning_report.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--shard", required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    print(build_report(args.root, args.shard, args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
