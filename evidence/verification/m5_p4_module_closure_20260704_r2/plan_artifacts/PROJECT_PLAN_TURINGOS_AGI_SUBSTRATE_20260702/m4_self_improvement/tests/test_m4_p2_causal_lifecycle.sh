#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

python3 - "$ROOT" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
run_root = root / "m4_self_improvement/real_s01_deepseek_20260703"

result = json.loads((root / "m4_self_improvement/M4_P2_CAUSAL_LIFECYCLE_RESULT.json").read_text())
uplift = json.loads((root / "m3_uplift_lab/analysis/s01_deepseek_only_20260703/out/UPLIFT_REPORT.json").read_text())
h2 = json.loads((run_root / "causal/h2_consumption_note.json").read_text())

assert result["status"] == "ADDRESSED"
assert result["confirmatory"]["failure_memory_causal_claim_allowed"] is False
assert result["confirmatory"]["h2_blocked_by_h1"] is True
assert h2["label"] == "CONFIRMATORY_VERBATIM_M3_H2"
assert h2["h2"] == uplift["confirmatory_tests"]["H2_B_gt_C"]
assert h2["mde_statement"] == uplift["mde_statement"]

exploratory = [
    "dose_response.json",
    "memory_cost.json",
    "lineage_table.json",
    "rule_lifecycle_table.json",
]
for rel in exploratory:
    path = run_root / "causal/exploratory" / rel
    obj = json.loads(path.read_text())
    assert obj.get("label") == "EXPLORATORY", path
    assert obj.get("causal_claim_allowed") is False, path

stamp = json.loads((run_root / "causal/exploratory/stamp_assertion.json").read_text())
assert stamp["status"] == "PASS"
assert sorted(pathlib.Path(row["path"]).name for row in stamp["rows"]) == sorted(exploratory)
assert all(row["status"] == "PASS" and row["sha256"].startswith("sha256:") for row in stamp["rows"])

legacy = json.loads((run_root / "audits/legacy_lifecycle_auditors_not_applicable.json").read_text())
assert legacy["status"] == "NOT_APPLICABLE_FOR_M3_DEEPSEEK_CONTINUATION"

proposal = json.loads((run_root / "proposals/BroadcastRuleRetired_PROPOSAL.json").read_text())
assert proposal["owner"] == "M1_SCHEMA_OWNER_PROPOSED_ONLY"
assert proposal["status_ceiling"] == "ADDRESSED"
assert proposal["proposed_event"]["event_type"] == "BroadcastRuleRetired"
assert "M4 does not land this event schema." in proposal["non_claims"]

print("M4_P2_CAUSAL_LIFECYCLE_CHECK_PASS")
PY
