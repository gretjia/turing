"""WP-H6 acceptance test (ADR-ECON-007, CAPSULE H integration smoke, 2026-07-11):
event-stream determinism for `tools/econ_lab/wp_h6_integration_smoke.py`'s replay
path (this WP's own brief, point 5: "事件流确定性:全事件序可重放(离线重放测试一条)").

This is an offline, hermetic test: it reads the real, pre-existing WP-H1 fixture
(`tools/econ_lab/monitor/fixtures/real_settlement_pytest_dev_pytest_5787_tau_0p5.json`,
already used by WP-H1's own module docstring as its empirical format-fit proof) and
replays `monitor.loop_detector.events_from_real_settlement_checkpoint` ->
`monitor.loop_detector.detect` -> `monitor.interventions.build_diagnostic` ->
`monitor.interventions.execute_rollback` -- the same production call chain
`live_driver.py`'s own `--monitor` hook uses -- twice, over byte-identical input, and
asserts the two runs produce a dict-equal result (Art 0.2 determinism). No network, no
subprocess, no clock/RNG read anywhere in the call chain under test.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ECON_LAB = REPO / "tools" / "econ_lab"
sys.path.insert(0, str(ECON_LAB))

from wp_h6_integration_smoke import (  # noqa: E402
    REAL_FIXTURE_PATH,
    replay_determinism_check,
    replay_trip_diagnostic_rollback,
)


def test_real_fixture_still_trips_the_detector() -> None:
    settlement = json.loads(REAL_FIXTURE_PATH.read_text(encoding="utf-8"))
    result = replay_trip_diagnostic_rollback(settlement)
    assert result["tripped"] is True
    assert result["trip"]["rule_id"] == "TERMINATION_WITHOUT_VERIFIER_EVIDENCE"
    assert result["diagnostic"]["rule_id"] == "TERMINATION_WITHOUT_VERIFIER_EVIDENCE"
    assert result["rollback"]["event"]["event_type"] == "TrajectoryRolledBack"


def test_replay_is_byte_identical_across_two_independent_runs() -> None:
    settlement = json.loads(REAL_FIXTURE_PATH.read_text(encoding="utf-8"))
    check = replay_determinism_check(settlement)
    assert check["byte_identical_across_two_runs"] is True
    assert check["run1_sha256"] == check["run2_sha256"]


def test_diagnostic_never_carries_a_bzone_quantity() -> None:
    """Redundant, test-suite-level re-assertion of Decision 3 (the production
    functions already self-validate this internally; this test pins that the smoke
    driver's own re-assertion call, `replay_trip_diagnostic_rollback`'s
    `decision3_legal_reassert`, is actually reached and actually passes)."""
    settlement = json.loads(REAL_FIXTURE_PATH.read_text(encoding="utf-8"))
    result = replay_trip_diagnostic_rollback(settlement)
    assert result["diagnostic"]["decision3_legal_reassert"] == "PASS"
    facts_text = json.dumps(result["diagnostic"]["facts"])
    for forbidden in ("tau", "lambda", "floor", "bucket", "threshold", "q_eff", "count"):
        assert forbidden not in facts_text.lower()
