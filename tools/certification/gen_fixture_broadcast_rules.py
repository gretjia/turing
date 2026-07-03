#!/usr/bin/env python3
"""Generate FIXTURE broadcast-rule inventory for FCE-B4 scale checks."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path


FAILURE_CLASSES = [
    "INSTALL_FAIL",
    "TEST_TIMEOUT",
    "WRONG_FILE",
    "NO_REPRO",
    "OVERBROAD_PATCH",
    "SEMANTIC_FAIL",
    "FLAKY_ORACLE",
    "DEPENDENCY_GAP",
    "CONTEXT_MISSING",
    "PATCH_APPLIES_BUT_WRONG",
]


def build_rules(count: int, max_active: int) -> dict:
    if count < 1:
        raise ValueError("count must be positive")
    if max_active < 0:
        raise ValueError("max-active must be non-negative")
    rules = []
    for index in range(count):
        rule_id = f"fixture_rule_{index:04d}"
        rules.append(
            {
                "rule_id": rule_id,
                "failure_class": FAILURE_CLASSES[index % len(FAILURE_CLASSES)],
                "abstract_pattern": f"fixture abstract pattern {index}",
                "guidance": f"fixture guidance {index}",
                "raw_log_text_absent": True,
                "hidden_predicates_absent": True,
                "fixture_or_real": "FIXTURE",
            }
        )
    return {
        "schema_id": "turingos.fce.fixture_broadcast_rules.v1",
        "fixture_or_real": "FIXTURE",
        "count": count,
        "injection_budget": {"max_active_rules": max_active},
        "active_rule_ids": [rule["rule_id"] for rule in rules[:max_active]],
        "rules": rules,
    }


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def self_test() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "rules.json"
        write_json(out, build_rules(50, 8))
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["fixture_or_real"] == "FIXTURE"
        assert len(data["rules"]) == 50
        assert len(data["active_rule_ids"]) == 8
        assert all(rule["raw_log_text_absent"] for rule in data["rules"])
    print("FCE_BROADCAST_RULE_FIXTURE_SELF_TEST_PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--max-active", type=int, default=8)
    parser.add_argument("--out")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if not args.out:
        parser.error("--out is required unless --self-test is used")
    write_json(Path(args.out), build_rules(args.count, args.max_active))
    print(json.dumps({"schema_id": "turingos.fce.fixture_broadcast_rules.summary.v1", "out": args.out}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
