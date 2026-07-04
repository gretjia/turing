#!/usr/bin/env python3
"""Repository-local audit for Operator Agent v1 boundaries."""

from __future__ import annotations

import sys

from turingos.operator_agent import (
    CLOSED_VERBS,
    command_spec,
    production_approval_route_allowed,
    tool_manifest,
)


def main() -> int:
    manifest = tool_manifest()
    if manifest["schema_id"] != "operator_tool_manifest.v1":
        print("bad manifest schema", file=sys.stderr)
        return 1
    if [command["verb"] for command in manifest["commands"]] != list(CLOSED_VERBS):
        print("closed verb order mismatch", file=sys.stderr)
        return 1
    for verb in CLOSED_VERBS:
        spec = command_spec(verb)
        if spec["writes_truth"]:
            print(f"{verb} writes truth from agent boundary", file=sys.stderr)
            return 1
    if (
        manifest["can_run_shell"]
        or manifest["can_move_heads"]
        or manifest["can_evaluate_predicates"]
        or manifest["can_autonomous_dispatch"]
    ):
        print("operator agent has forbidden capability", file=sys.stderr)
        return 1
    if production_approval_route_allowed("in-memory-test"):
        print("in-memory-test route allowed in production", file=sys.stderr)
        return 1
    if production_approval_route_allowed("local-file-dev"):
        print("local-file-dev route allowed in production", file=sys.stderr)
        return 1
    print("operator agent audit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
