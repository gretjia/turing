"""WP9c -- shared offline fixtures for `live_driver.py`'s resume tests.

Not a test file itself (no `test_` prefix; pytest does not collect it). Split out only to
avoid re-deriving the same offline stub contract `tests/test_live_driver_replay.py` already
established (WP9a deliverable 4) independently in each of this task's new test files
(`test_live_driver_head_parity.py`, `test_live_driver_resume.py`): the synthetic
`instance_id`/`tests_status`/split-side shape below is copied, not reinvented, from that
file's own `_tests_status_for_instance`/`ACCEPT_TEST_IDS`/`VERIFY_TEST_IDS` (already checked
there against the real `verifier.split.split_side` function at import time; re-checked here
too so a drift in either file's held-out-split fixture picks is caught immediately, not just
in whichever file happens to run first).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
ECON_LAB_DIR = REPO / "tools" / "econ_lab"
if str(ECON_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(ECON_LAB_DIR))

from verifier.split import ACCEPT_SIDE, VERIFY_SIDE, split_side  # noqa: E402

# Identical to test_live_driver_replay.py's own hand-picked test_ids (WP9a deliverable 4) --
# copied, not re-derived, and re-verified against the real split function below.
ACCEPT_TEST_IDS = [
    "tests/test_module.py::test_case_0004",
    "tests/test_module.py::test_case_0005",
    "tests/test_module.py::test_case_0009",
]
VERIFY_TEST_IDS = [
    "tests/test_module.py::test_case_0000",
    "tests/test_module.py::test_case_0001",
    "tests/test_module.py::test_case_0002",
]
for _tid in ACCEPT_TEST_IDS:
    assert split_side(_tid) == ACCEPT_SIDE, f"fixture drift: {_tid!r} no longer splits ACCEPT"
for _tid in VERIFY_TEST_IDS:
    assert split_side(_tid) == VERIFY_SIDE, f"fixture drift: {_tid!r} no longer splits VERIFY"

STUB_PATCH_TEXT = "diff --git a/stub.py b/stub.py\n--- a/stub.py\n+++ b/stub.py\n@@ -1 +1 @@\n-old\n+new\n"


def tests_status_for_instance(instance_id: str) -> dict[str, Any]:
    """Same contract as test_live_driver_replay.py's `_tests_status_for_instance`, extended
    with a third synthetic outcome (`...-0003`, both sides FAIL -- UNRESOLVED with a non-empty
    verify side that still fails) so a 3-task determinism run (WP9c's own kill-at-k test) has
    one instance of each of the three market-relevant shapes this fixture set can produce:
    accept+verify both PASS (`...-0001`), accept FAIL / verify PASS (`...-0002`), and
    accept+verify both FAIL (`...-0003`)."""
    if instance_id.endswith("0001"):
        return {
            "FAIL_TO_PASS": {"success": [ACCEPT_TEST_IDS[0], VERIFY_TEST_IDS[0]], "failure": []},
            "PASS_TO_PASS": {"success": [ACCEPT_TEST_IDS[1], VERIFY_TEST_IDS[1]], "failure": []},
            "FAIL_TO_FAIL": {"success": [], "failure": []},
            "PASS_TO_FAIL": {"success": [], "failure": []},
        }
    if instance_id.endswith("0003"):
        return {
            "FAIL_TO_PASS": {"success": [], "failure": [ACCEPT_TEST_IDS[2], VERIFY_TEST_IDS[2]]},
            "PASS_TO_PASS": {"success": [], "failure": []},
            "FAIL_TO_FAIL": {"success": [], "failure": []},
            "PASS_TO_FAIL": {"success": [], "failure": []},
        }
    return {
        "FAIL_TO_PASS": {"success": [VERIFY_TEST_IDS[2]], "failure": [ACCEPT_TEST_IDS[2]]},
        "PASS_TO_PASS": {"success": [], "failure": []},
        "FAIL_TO_FAIL": {"success": [], "failure": []},
        "PASS_TO_FAIL": {"success": [], "failure": []},
    }


def synthetic_packets(count: int = 2) -> list[dict[str, Any]]:
    """`count` hand-built packets shaped like the real worker-safe schema's load-bearing
    fields only (`instance_id`, `repo`, `ipqc_window_id`) -- never reads the real 50-task
    shard, so tests using this fixture are hermetic and fast regardless of shard state."""
    return [
        {
            "instance_id": f"fixture__repo-000{i}",
            "repo": "Fixture/Repo",
            "ipqc_window_id": "FIX-W00",
            "_task_dir": Path(f"/nonexistent/fixture-repo-000{i}"),
            "_task_packet_path": Path(f"/nonexistent/fixture-repo-000{i}/task_packet.json"),
        }
        for i in range(1, count + 1)
    ]


def stub_dispatch_worker_for_lineage(
    *,
    arm: str,
    lineage: str,
    packet: dict,
    task_dir_root: Path,
    run_id_prefix: str,
    deepseek_native_provider_config: dict,
):
    """Offline stand-in for `dispatch_worker_for_lineage`: no network call, deterministic
    content, and -- unlike `test_live_driver_replay.py`'s own stub -- also writes a
    `worker_receipt.json` sibling to `candidate.patch` (mirroring the real
    `dispatch_via_siliconflow` artifact pair exactly), so this module's resume tests can
    exercise `_reconstruct_worker_result_from_artifacts`'s real (candidate.patch +
    worker_receipt.json)-pair contract, not a weakened one."""
    instance_id = packet["instance_id"]
    task_dir = task_dir_root / instance_id / lineage
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "candidate.patch").write_text(STUB_PATCH_TEXT, encoding="utf-8")
    patch_sha256 = "sha256:" + ("0" * 63) + "1"
    receipt = {
        "schema_id": "turingos.wp9a.live_driver_siliconflow_worker_receipt.v1",
        "status": "COMPLETED",
        "instance_id": instance_id,
        "arm": arm,
        "lineage": lineage,
        "model_requested": "stub/stub-model",
        "model_reported": "stub/stub-model",
        "wall_time_ms": 1234,
        "candidate_patch_sha256": patch_sha256,
        "response_sha256": "sha256:" + ("1" * 63) + "0",
        "content_length_chars": len(STUB_PATCH_TEXT),
    }
    import json

    (task_dir / "worker_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "status": "COMPLETED",
        "instance_id": instance_id,
        "arm": arm,
        "lineage": lineage,
        "provider_path": "siliconflow",
        "candidate_patch_sha256": patch_sha256,
        "candidate_patch_bytes": len(STUB_PATCH_TEXT.encode("utf-8")),
        "wall_time_ms": 1234,
    }


def stub_score_with_official_harness(
    *, python_bin: str, instance_id: str, model_patch: str, run_id: str, report_dir: Path, timeout_s: int = 1800
):
    """Offline stand-in for the real SWE-bench Docker harness, a pure function of
    `instance_id` only -- shaped identically to `test_live_driver_replay.py`'s own stub, but
    also *writes* the aggregated-report + per-instance-report.json artifact pair to
    `report_dir` (mirroring `score_with_official_harness`'s real on-disk contract exactly), so
    this module's resume tests can exercise `_read_scoring_report`'s real read-back path, not
    a weakened one."""
    import json

    resolved = instance_id.endswith("0001")
    tests_status = tests_status_for_instance(instance_id)
    outcome = "RESOLVED" if resolved else "UNRESOLVED"

    report_dir = report_dir.resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    model_name = "wp9a-live-driver"
    aggregated_report = {
        "schema_version": 2,
        "resolved_ids": [instance_id] if resolved else [],
        "unresolved_ids": [] if resolved else [instance_id],
        "empty_patch_ids": [],
        "incomplete_ids": [],
        "error_ids": [],
    }
    (report_dir / f"{model_name}.{run_id}.json").write_text(
        json.dumps(aggregated_report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    instance_dir = report_dir / "logs" / "run_evaluation" / run_id / model_name / instance_id
    instance_dir.mkdir(parents=True, exist_ok=True)
    (instance_dir / "report.json").write_text(
        json.dumps({instance_id: {"tests_status": tests_status}}, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    return {
        "status": "COMPLETED",
        "outcome": outcome,
        "resolved": resolved,
        "tests_status": tests_status,
        "harness_error_reason": None,
        "report_path": str(report_dir / f"{model_name}.{run_id}.json"),
        "log_path": str(report_dir / "run_evaluation.log"),
        "raw_report": aggregated_report,
    }


def wire_stubs(module, monkeypatch, *, task_count: int = 2) -> None:
    """Wires the fixtures above onto a loaded `live_driver` module object (fresh module or
    HEAD-snapshot module alike -- both expose the same monkeypatchable names)."""
    monkeypatch.setattr(module, "load_task_packets", lambda shard_root=module.SHARD_ROOT: synthetic_packets(task_count))
    monkeypatch.setattr(
        module,
        "load_provider_config",
        lambda: {"api_key_env": "DEEPSEEK_API_KEY", "base_url": "stub://offline", "model": "stub-model"},
    )
    monkeypatch.setattr(module, "dispatch_worker_for_lineage", stub_dispatch_worker_for_lineage)
    monkeypatch.setattr(module, "score_with_official_harness", stub_score_with_official_harness)


def strip_volatile(verdict: dict) -> dict:
    verdict = dict(verdict)
    verdict.pop("generated_at_unix", None)
    return verdict
