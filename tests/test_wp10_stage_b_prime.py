"""WP10 -- Stage B' driver support + independent audit fixes B2/B3/B5/B6 regression tests.

Spec source (sole authority; a missing detail is reported BLOCKED, never guessed):
  docs/handoff/INDEPENDENT_AUDIT_ECON_LAB_20260707.md section B (findings B2/B3/B5/B6);
  ADR-ECON-003-emergence-routing-spec-pins.md Decision 7 (2026-07-08, ratifying the
  orchestrator's B-section ruling and the Stage B' mechanism); PREREG Appendix A amendment #4
  (Stage B' four-arm design, warm-start priors file, S02 task stream).

Each test below pins one fixture-level assertion from that ruling. The full happy-path
suites (`test_econ_lab_wp7_harness.py`, `test_live_driver_*.py`) stay green alongside these
-- see `test_live_driver_head_parity.py`'s own note for why B5 legitimately changes
downstream event_hash-derived fields there (not touched by these tests, which construct
their own fixed `run_label`s throughout).

Offline only: no real worker or SWE-bench Docker harness call anywhere in this file (every
scenario is driven through `_wp9c_live_driver_fixtures`'s deterministic stubs or hand-built
on-disk artifacts).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ECON_LAB_DIR = REPO / "tools" / "econ_lab"
DRIVER_PATH = ECON_LAB_DIR / "live_driver.py"
CLI_BIN = REPO / "target" / "debug" / "econ_fold_cli"

sys.path.insert(0, str(ECON_LAB_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from verifier import live_split_verifier as lsv  # noqa: E402
from _wp9c_live_driver_fixtures import (  # noqa: E402
    strip_volatile,
    stub_dispatch_worker_for_lineage,
    wire_stubs,
)


def _load_driver():
    spec = importlib.util.spec_from_file_location("wp10_driver_under_test", DRIVER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def driver(monkeypatch):
    if not CLI_BIN.exists():
        pytest.skip("econ_fold_cli not built; run `cargo build --bin econ_fold_cli -p turing-economy` first")
    module = _load_driver()
    wire_stubs(module, monkeypatch, task_count=2)
    return module


def _run_args(tmp_path: Path, **overrides) -> argparse.Namespace:
    base = dict(
        smoke=False,
        max_tasks=2,
        out=tmp_path / "verdict.json",
        econ_fold_cli=CLI_BIN,
        scoring_python="python3",
        scoring_timeout_s=60,
        task_dir_root=tmp_path / "task_runs",
        report_dir=tmp_path / "scoring",
        run_label="test-wp10",
    )
    base.update(overrides)
    return argparse.Namespace(**base)


# ---------------------------------------------------------------------------
# B2 -- infra_null classification (INCOMPLETE / malformed-or-missing report):
# "harness 未实际评测 ⇒ infra_null, 不结算不回灌" (ADR-ECON-003 Decision 7.1).
# ---------------------------------------------------------------------------


def test_judge_infra_null_shape():
    result = lsv.judge_infra_null("incomplete")
    assert result["accept_verdict"] is None
    assert result["verify_verdict"] is None
    assert result["canary"] is False
    assert result["not_enough_tests"] is False
    assert result["infra_null"] is True
    assert result["infra_null_reason"] == "incomplete"


def test_read_scoring_report_incomplete_outcome_is_infra_null(tmp_path, driver):
    report_dir = tmp_path / "report"
    report_dir.mkdir()
    run_id, instance_id = "run1", "fixture__repo-0001"
    aggregated = {
        "schema_version": 2,
        "resolved_ids": [],
        "unresolved_ids": [],
        "empty_patch_ids": [],
        "incomplete_ids": [instance_id],
        "error_ids": [],
    }
    (report_dir / f"{driver.MODEL_NAME}.{run_id}.json").write_text(json.dumps(aggregated), encoding="utf-8")
    result = driver._read_scoring_report(report_dir=report_dir, run_id=run_id, instance_id=instance_id)
    assert result["outcome"] == "INCOMPLETE"
    assert result["infra_null_reason"] == "incomplete"
    assert result["harness_error_reason"] is None


def test_read_scoring_report_error_without_report_or_marker_is_infra_null(tmp_path, driver):
    """The `error_ids` catch-all bucket with no per-instance report/log at all and no pinned
    `patch_apply_failed` marker -- the harness genuinely never evaluated this instance
    (report malformed/never written)."""
    report_dir = tmp_path / "report"
    report_dir.mkdir()
    run_id, instance_id = "run1", "fixture__repo-0001"
    aggregated = {
        "schema_version": 2,
        "resolved_ids": [],
        "unresolved_ids": [],
        "empty_patch_ids": [],
        "incomplete_ids": [],
        "error_ids": [instance_id],
    }
    (report_dir / f"{driver.MODEL_NAME}.{run_id}.json").write_text(json.dumps(aggregated), encoding="utf-8")
    result = driver._read_scoring_report(report_dir=report_dir, run_id=run_id, instance_id=instance_id)
    assert result["outcome"] == "ERROR"
    assert result["infra_null_reason"] == "harness_error_no_report"
    assert result["harness_error_reason"] is None


def test_read_scoring_report_patch_apply_failed_stays_legit_double_fail(tmp_path, driver):
    """The one `error_ids` cause the orchestrator addendum pins a specific reason for stays a
    real, determinate double-fail -- never infra_null ("补丁应用失败维持合法双败")."""
    report_dir = tmp_path / "report"
    report_dir.mkdir()
    run_id, instance_id = "run1", "fixture__repo-0001"
    aggregated = {
        "schema_version": 2,
        "resolved_ids": [],
        "unresolved_ids": [],
        "empty_patch_ids": [],
        "incomplete_ids": [],
        "error_ids": [instance_id],
    }
    (report_dir / f"{driver.MODEL_NAME}.{run_id}.json").write_text(json.dumps(aggregated), encoding="utf-8")
    instance_dir = report_dir / "logs" / "run_evaluation" / run_id / driver.MODEL_NAME / instance_id
    instance_dir.mkdir(parents=True)
    (instance_dir / "run_instance.log").write_text(
        "preamble\n" + driver.APPLY_PATCH_FAIL_MARKER + "\ntrailer\n", encoding="utf-8"
    )
    result = driver._read_scoring_report(report_dir=report_dir, run_id=run_id, instance_id=instance_id)
    assert result["outcome"] == "ERROR"
    assert result["harness_error_reason"] == "patch_apply_failed"
    assert "infra_null_reason" not in result


def test_apply_live_split_verifier_infra_null_never_settles_or_feeds_back(driver):
    live_split_result, backup_update, event = driver._apply_live_split_verifier(
        cli_bin=CLI_BIN,
        instance_id="i",
        arm="armA",
        lineage="deepseek",
        route_domain="bucket",
        route_scaffold="scaffold:sha256:aaa",
        tests_status=None,
        harness_error_reason=None,
        infra_null_reason="incomplete",
        run_label="r",
        task_index=0,
    )
    assert live_split_result["accept_verdict"] is None
    assert live_split_result["infra_null"] is True
    assert backup_update == {"applied": False, "reason": "INFRA_NULL:incomplete"}
    assert event is None


# ---------------------------------------------------------------------------
# B3 -- empty patch (worker COMPLETED, 0-byte/whitespace-only patch) is a determinate
# SWE-bench task failure: "结算 FAIL、verify FAIL、无金丝雀、正常回灌 v=0、计入分母"
# (ADR-ECON-003 Decision 7.2).
# ---------------------------------------------------------------------------


def _empty_patch_dispatch(*, arm, lineage, packet, task_dir_root, run_id_prefix, deepseek_native_provider_config):
    instance_id = packet["instance_id"]
    task_dir = task_dir_root / instance_id / lineage
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "candidate.patch").write_text("   \n", encoding="utf-8")  # whitespace-only
    return {
        "status": "COMPLETED",
        "instance_id": instance_id,
        "arm": arm,
        "lineage": lineage,
        "provider_path": "siliconflow",
    }


def test_empty_patch_settles_fail_no_canary_feeds_back_and_counts_in_denominator(tmp_path, driver, monkeypatch):
    monkeypatch.setattr(driver, "dispatch_worker_for_lineage", _empty_patch_dispatch)

    def _boom_score(**kwargs):
        raise AssertionError("must never invoke the harness for an empty/whitespace-only patch")

    monkeypatch.setattr(driver, "score_with_official_harness", _boom_score)

    args = _run_args(tmp_path, max_tasks=1)
    verdict = driver.run_driver(args)

    task = verdict["tasks"][0]
    dispatch = task["dispatches"][0]
    assert dispatch["scoring_result"]["status"] == "SKIPPED_NO_PATCH"
    assert dispatch["settlement_verdict_resolved"] is False
    assert dispatch["live_split_verdict"]["accept_verdict"] is False
    assert dispatch["live_split_verdict"]["verify_verdict"] is False
    assert dispatch["live_split_verdict"]["canary"] is False
    assert dispatch["live_split_verdict"].get("infra_null") in (None, False)
    assert dispatch["backup_update"]["applied"] is True
    assert dispatch["backup_update"]["routing_prior_updated_event_hash"].startswith("sha256:")
    assert verdict["verifier_summary"]["routing_prior_updated_applied_count"] == 1
    assert verdict["verifier_summary"]["infra_null_count"] == 0

    # Frozen, untouched Stage A readout script: SWE-bench semantics -- counted in the
    # denominator (n_settled), not excluded as infra_null.
    sys.path.insert(0, str(ECON_LAB_DIR / "analysis"))
    import stage_a_readout  # noqa: E402

    stats = stage_a_readout.arm_stats(verdict)
    assert stats["n_settled"] == 1
    assert stats["k_pass"] == 0
    assert stats["infra_null"] == 0


def test_settle_one_resume_also_settles_empty_patch_as_fail(tmp_path, driver):
    """`_settle_one_resume`'s reconstructed-artifact path (candidate.patch on disk is
    itself empty) gets the identical B3 treatment as the fresh path -- never re-invokes the
    harness or the worker."""
    instance_id, arm, lineage = "fixture__repo-0001", "armA", "deepseek"
    task_dir_root = tmp_path / "task_runs"
    task_dir = task_dir_root / instance_id / lineage
    task_dir.mkdir(parents=True)
    (task_dir / "candidate.patch").write_text("\n", encoding="utf-8")
    receipt = {
        "schema_id": "turingos.wp9a.live_driver_siliconflow_worker_receipt.v1",
        "status": "COMPLETED",
        "instance_id": instance_id,
        "arm": arm,
        "lineage": lineage,
        "model_requested": "x",
        "model_reported": "x",
        "wall_time_ms": 1,
        "candidate_patch_sha256": "sha256:" + "0" * 64,
        "response_sha256": "sha256:" + "1" * 64,
        "content_length_chars": 1,
    }
    (task_dir / "worker_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")

    args = argparse.Namespace(scoring_python="python3", scoring_timeout_s=60)
    result = driver._settle_one_resume(
        args=args,
        packet={"instance_id": instance_id},
        arm=arm,
        lineage=lineage,
        task_dir_root=task_dir_root,
        report_root=tmp_path / "scoring",
        deepseek_native_provider_config=None,
        cli_bin=CLI_BIN,
        route_domain="bucket",
        route_scaffold="scaffold:sha256:test",
        run_label="test-b3-resume",
        task_index=0,
    )
    assert result["settlement_verdict_resolved"] is False
    assert result["live_split_verdict"]["verify_verdict"] is False
    assert result["backup_update"]["applied"] is True


# ---------------------------------------------------------------------------
# B5 -- attestation uniqueness via (run_label, task_index) caller contract; the pinned
# event_hash formula itself is untouched (ADR-ECON-003 Decision 7.4).
# ---------------------------------------------------------------------------


def test_verifier_attestation_hash_varies_with_run_label_and_task_index(driver):
    live_split_result = lsv.judge_harness_error("empty_patch_worker_output")
    kwargs = dict(instance_id="i", arm="armA", lineage="deepseek", live_split_result=live_split_result)
    h_a0 = driver._verifier_attestation_hash(**kwargs, run_label="run-A", task_index=0)
    h_b0 = driver._verifier_attestation_hash(**kwargs, run_label="run-B", task_index=0)
    h_a1 = driver._verifier_attestation_hash(**kwargs, run_label="run-A", task_index=1)
    h_a0_repeat = driver._verifier_attestation_hash(**kwargs, run_label="run-A", task_index=0)

    assert h_a0 == h_a0_repeat, "identical (run_label, task_index) must be deterministic"
    assert len({h_a0, h_b0, h_a1}) == 3, "run_label and task_index must each be load-bearing"


def test_repeated_identical_observation_gets_distinct_event_hash_and_folds_without_collision(driver):
    """End-to-end proof (real econ_fold_cli, not a Python re-derivation) that two
    byte-identical (instance/arm/lineage/verdict) observations at different (run_label,
    task_index) mint distinct `RoutingPriorUpdated.event_hash`es and fold together without
    `RoutingFoldDuplicateEventHash` -- the exact collision B5 fixes."""
    live_split_result = lsv.judge_harness_error("empty_patch_worker_output")
    route_domain = "bucket"
    route_scaffold = "scaffold:sha256:b5-collision-test"

    events = []
    for task_index in (0, 1):
        attestation_hash = driver._verifier_attestation_hash(
            instance_id="same-instance",
            arm="armA",
            lineage="deepseek",
            live_split_result=live_split_result,
            run_label="stageB-armW",
            task_index=task_index,
        )
        response = driver.call_cli(
            CLI_BIN,
            "build-routing-prior-updated",
            {
                "schema": "econ_fold_cli.build_routing_prior_updated.request.v1",
                "route_domain": route_domain,
                "route_scaffold": route_scaffold,
                "verdict": False,
                "verdict_source_id": driver.LIVE_SPLIT_VERIFIER_SOURCE_ID,
                "verifier_attestation_hash": attestation_hash,
            },
        )
        events.append(response["event"])

    hashes = {e["RoutingPriorUpdated"]["event_hash"] for e in events}
    assert len(hashes) == 2, "distinct task_index must mint distinct event_hash"

    fold_response = driver.call_cli(
        CLI_BIN,
        "fold-and-suggest",
        {
            "schema": "econ_fold_cli.fold_and_suggest.request.v2",
            "committed_routing_events": events,
            "initial_prices": [],
            "candidate_routes": [
                {
                    "route_id": "r1",
                    "market_id": "m1",
                    "expected_failure_domain": "swe_bench_worker_repair",
                    "requested_tokens": 100,
                    "domain_bucket": route_domain,
                    "scaffold_id": route_scaffold,
                }
            ],
            "price_signal_hash": driver.digest("price-x"),
            "pput_prior_hash": driver.digest("pput-y"),
            "trigger_event_hash": driver.digest("trigger-z"),
            "router_mode": {"kind": "SoftmaxArgmaxBypass"},
        },
    )
    node = next(n for n in fold_response["node_states"] if n["scaffold_id"] == route_scaffold)
    assert node["n"] == 2, "both distinct observations must have folded (no collision error)"
    assert node["s"] == 0  # both verdicts were False


def test_repeated_identical_observation_without_run_label_task_index_would_collide():
    """Negative control proving the bug B5 fixes is real: the *pre-B5* attestation payload
    (no run_label/task_index) is byte-identical across a repeated observation, so its digest
    collides -- exactly the `RoutingFoldDuplicateEventHash` the fix prevents."""
    payload = {
        "schema": "live_split_verifier.attestation.v1",
        "instance_id": "same-instance",
        "arm": "armA",
        "lineage": "deepseek",
        "verify_test_ids": [],
        "verify_verdict": False,
        "harness_error_reason": "empty_patch_worker_output",
    }
    digest_1 = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    digest_2 = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    assert digest_1 == digest_2, "identical payload (no uniqueness fields) always collides"


# ---------------------------------------------------------------------------
# B6 -- SCORING_OK.marker gates resume's on-disk report reuse (ADR-ECON-003 Decision 7.5).
# ---------------------------------------------------------------------------


def test_scoring_ok_marker_written_and_validated(tmp_path, driver):
    report_dir = tmp_path / "report"
    report_dir.mkdir(parents=True)
    report_path = report_dir / "r.json"
    report_path.write_text(json.dumps({"a": 1}), encoding="utf-8")

    driver._write_scoring_ok_marker(report_dir, report_path)
    marker_path = report_dir / driver.SCORING_OK_MARKER_FILENAME
    assert marker_path.exists()
    assert marker_path.read_text().strip() == hashlib.sha256(report_path.read_bytes()).hexdigest()
    assert driver._scoring_ok_marker_valid(report_dir=report_dir, report_path=report_path) is True

    # Report content changes after the marker was written -> no longer valid.
    report_path.write_text(json.dumps({"a": 2}), encoding="utf-8")
    assert driver._scoring_ok_marker_valid(report_dir=report_dir, report_path=report_path) is False


def test_scoring_ok_marker_missing_means_not_valid(tmp_path, driver):
    report_dir = tmp_path / "report"
    report_dir.mkdir(parents=True)
    report_path = report_dir / "r.json"
    report_path.write_text("{}", encoding="utf-8")
    assert driver._scoring_ok_marker_valid(report_dir=report_dir, report_path=report_path) is False


def test_resume_rescoring_when_report_exists_without_marker(tmp_path, driver, monkeypatch):
    """Closes the residual B6 resume gap: a report left behind by a run that hit
    SCORING_FAILED (rc!=0 after the harness partially wrote a report) never got a
    SCORING_OK.marker, so `--resume` must re-score rather than silently trust it."""
    instance_id, arm, lineage = "fixture__repo-0001", "armA", "deepseek"
    task_dir_root = tmp_path / "task_runs"
    report_root = tmp_path / "scoring"
    task_dir = task_dir_root / instance_id / lineage
    task_dir.mkdir(parents=True)
    patch_text = "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n"
    (task_dir / "candidate.patch").write_text(patch_text, encoding="utf-8")
    receipt = {
        "schema_id": "turingos.wp9a.live_driver_siliconflow_worker_receipt.v1",
        "status": "COMPLETED",
        "instance_id": instance_id,
        "arm": arm,
        "lineage": lineage,
        "model_requested": "x",
        "model_reported": "x",
        "wall_time_ms": 1,
        "candidate_patch_sha256": "sha256:" + hashlib.sha256(patch_text.encode("utf-8")).hexdigest(),
        "response_sha256": "sha256:" + "0" * 64,
        "content_length_chars": len(patch_text),
    }
    (task_dir / "worker_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")

    run_id = f"wp9a-live-driver-{instance_id}-{lineage}"
    report_dir = (report_root / instance_id / lineage).resolve()
    report_dir.mkdir(parents=True)
    # Leftover aggregated report from a run that hit SCORING_FAILED after partially writing it
    # -- deliberately no SCORING_OK.marker (the exact bug B6 fixes).
    aggregated = {
        "schema_version": 2,
        "resolved_ids": [instance_id],
        "unresolved_ids": [],
        "empty_patch_ids": [],
        "incomplete_ids": [],
        "error_ids": [],
    }
    report_path = report_dir / f"{driver.MODEL_NAME}.{run_id}.json"
    report_path.write_text(json.dumps(aggregated), encoding="utf-8")
    predictions_row = {"instance_id": instance_id, "model_name_or_path": driver.MODEL_NAME, "model_patch": patch_text}
    (report_dir / "predictions.jsonl").write_text(json.dumps(predictions_row) + "\n", encoding="utf-8")

    rescore_calls = []

    def _fake_score(**kwargs):
        rescore_calls.append(kwargs["instance_id"])
        return {"status": "SCORING_FAILED", "returncode": 1}

    monkeypatch.setattr(driver, "score_with_official_harness", _fake_score)

    args = argparse.Namespace(scoring_python="python3", scoring_timeout_s=60)
    result = driver._settle_one_resume(
        args=args,
        packet={"instance_id": instance_id},
        arm=arm,
        lineage=lineage,
        task_dir_root=task_dir_root,
        report_root=report_root,
        deepseek_native_provider_config=None,
        cli_bin=CLI_BIN,
        route_domain="bucket",
        route_scaffold="scaffold:sha256:test",
        run_label="test-b6",
        task_index=0,
    )
    assert rescore_calls == [instance_id], "an unmarked leftover report must force a re-score, never be trusted"
    assert result["scoring_result"]["status"] == "SCORING_FAILED"
    assert result["settlement_verdict_resolved"] is None


# ---------------------------------------------------------------------------
# Stage B' -- warm-start `--priors` injection (ADR-ECON-003 Decision 6.1/7.6)
# ---------------------------------------------------------------------------


def test_load_stage_b_prime_priors_accepts_pinned_schema_and_bare_mapping(tmp_path, driver):
    nested = tmp_path / "nested.json"
    nested.write_text(
        json.dumps({"schema": "econ_lab.stage_b_prime_priors.v1", "priors": {"armA::deepseek": 0.25}}),
        encoding="utf-8",
    )
    priors_map, file_sha256 = driver.load_stage_b_prime_priors(nested)
    assert priors_map == {"armA::deepseek": 0.25}
    assert file_sha256 == hashlib.sha256(nested.read_bytes()).hexdigest()

    bare = tmp_path / "bare.json"
    bare.write_text(json.dumps({"armB::qwen": 0.75}), encoding="utf-8")
    priors_map2, _ = driver.load_stage_b_prime_priors(bare)
    assert priors_map2 == {"armB::qwen": 0.75}


def test_stage_b_prime_initial_prices_omits_missing_routes(driver):
    scaffold_ids = {
        arm: {lineage: f"scaffold:sha256:{arm}-{lineage}" for lineage in driver.LINEAGES}
        for arm in driver.ARM_DESCRIPTORS
    }
    entries = driver.stage_b_prime_initial_prices(
        {"armA::deepseek": 0.75}, domain_bucket="bucket", scaffold_ids=scaffold_ids
    )
    assert len(entries) == 1
    assert entries[0] == {
        "domain_bucket": "bucket",
        "scaffold_id": scaffold_ids["armA"]["deepseek"],
        "p_q32": str(int(0.75 * (1 << 32))),
    }


def test_committed_stage_b_prime_priors_file_matches_adr_pinned_sha256():
    priors_path = ECON_LAB_DIR / "analysis" / "stage_b_prime_priors_s01.json"
    assert priors_path.exists()
    digest_hex = hashlib.sha256(priors_path.read_bytes()).hexdigest()
    assert digest_hex == "d7f900934d3d9c95243af717e6ee7e3fdab7df7c989c17f05a59171757fe41ac"


def test_priors_injection_biases_first_task_argmax_selection(tmp_path, driver):
    """With an empty tape (task index 0), Q_eff == P for every route (N=0 boundary
    identity) -- a strongly-favored route from `--priors` must win argmax (`--tau 0`) over
    every other route's P=0.5 default."""
    priors_path = tmp_path / "priors.json"
    priors_path.write_text(json.dumps({"armC::kimi": 0.99}), encoding="utf-8")

    args = _run_args(tmp_path, max_tasks=1, tau="0", priors=priors_path)
    verdict = driver.run_driver(args)

    task0 = verdict["tasks"][0]
    assert task0["selected_arm"] == "armC"
    assert task0["selected_lineage"] == "kimi"
    meta = verdict["stage_b_prime_meta"]
    assert meta["priors_sha256"] == hashlib.sha256(priors_path.read_bytes()).hexdigest()
    assert meta["priors_path"] == str(priors_path)


def test_priors_injection_is_deterministic_same_priors_same_stream_same_verdict(tmp_path, driver):
    priors_path = tmp_path / "priors.json"
    priors_path.write_text(
        json.dumps({"priors": {"armA::deepseek": 0.9, "armB::qwen": 0.1}}), encoding="utf-8"
    )

    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    verdict_a = driver.run_driver(_run_args(root_a, priors=priors_path, tau="0.5"))
    verdict_b = driver.run_driver(_run_args(root_b, priors=priors_path, tau="0.5"))

    text_a = json.dumps(strip_volatile(verdict_a), sort_keys=True).replace(str(root_a.resolve()), "<ROOT>")
    text_b = json.dumps(strip_volatile(verdict_b), sort_keys=True).replace(str(root_b.resolve()), "<ROOT>")
    assert text_a == text_b, "identical --priors file + identical task stream must fold to an identical verdict"


def test_priors_absent_is_behavior_identical_to_pre_stage_b_prime(tmp_path, driver):
    """Zero-config default: no `--priors` flag at all must be exactly the pre-Stage-B'
    `initial_prices: []` behavior (every route falls back to the CLI's own P=0.5 default)."""
    args = _run_args(tmp_path, max_tasks=1)
    verdict = driver.run_driver(args)
    meta = verdict["stage_b_prime_meta"]
    assert meta["priors_path"] is None
    assert meta["priors_sha256"] is None
    assert meta["frozen_backup"] is False
    assert meta["task_shard"] is None


# ---------------------------------------------------------------------------
# Stage B' -- `--frozen-backup` arm (ADR-ECON-003 Decision 7.7): RoutingPriorUpdated
# generated and persisted as evidence, but never enters the fold's own event sequence.
# ---------------------------------------------------------------------------


def test_frozen_backup_never_appends_to_fold_event_sequence(tmp_path, driver, monkeypatch):
    original_fold_and_select = driver.fold_and_select
    seen_tape_lengths: list[int] = []

    def _spy_fold_and_select(cli_bin, **kwargs):
        seen_tape_lengths.append(len(kwargs["committed_routing_events"]))
        return original_fold_and_select(cli_bin, **kwargs)

    monkeypatch.setattr(driver, "fold_and_select", _spy_fold_and_select)

    args = _run_args(tmp_path, tau="0.5", frozen_backup=True)
    verdict = driver.run_driver(args)

    assert seen_tape_lengths == [0, 0], "frozen-backup: committed_routing_events must stay empty every task"
    assert verdict["verifier_summary"]["routing_prior_updated_applied_count"] >= 1, (
        "the RoutingPriorUpdated event must still be built/attested (evidence complete) even "
        "though it never enters the fold"
    )
    assert verdict["stage_b_prime_meta"]["frozen_backup"] is True

    # Evidence-complete: the event is still persisted in the on-disk checkpoint even though it
    # never reached the fold.
    for suffix in ("0001", "0002"):
        checkpoint = json.loads(
            (tmp_path / "task_runs" / f"fixture__repo-{suffix}" / "settlement.json").read_text()
        )
        applied_events = [
            d.get("routing_prior_updated_event") for d in checkpoint["dispatches"] if d.get("routing_prior_updated_event")
        ]
        assert applied_events, f"instance fixture__repo-{suffix} must still persist its event as evidence"


def test_non_frozen_backup_does_append_to_fold_event_sequence(tmp_path, driver, monkeypatch):
    """Positive/negative control for the test above: without `--frozen-backup`, the second
    task's fold call must see at least the first task's applied event on its tape."""
    original_fold_and_select = driver.fold_and_select
    seen_tape_lengths: list[int] = []

    def _spy_fold_and_select(cli_bin, **kwargs):
        seen_tape_lengths.append(len(kwargs["committed_routing_events"]))
        return original_fold_and_select(cli_bin, **kwargs)

    monkeypatch.setattr(driver, "fold_and_select", _spy_fold_and_select)

    args = _run_args(tmp_path, tau="0.5", frozen_backup=False)
    verdict = driver.run_driver(args)

    assert seen_tape_lengths[0] == 0
    assert seen_tape_lengths[1] >= 1
    assert verdict["stage_b_prime_meta"]["frozen_backup"] is False


# ---------------------------------------------------------------------------
# Stage B' -- `--task-shard` task-stream root override (ADR-ECON-003 Decision 7.6
# out-of-sample discipline: evaluation stream disjoint from the priors' source stream).
# ---------------------------------------------------------------------------


def test_task_shard_override_loads_from_alternate_root(tmp_path):
    """Uses a *freshly loaded, unstubbed* module (the `driver` fixture's `wire_stubs`
    monkeypatches `load_task_packets` itself, which would defeat this unit test)."""
    if not CLI_BIN.exists():
        pytest.skip("econ_fold_cli not built; run `cargo build --bin econ_fold_cli -p turing-economy` first")
    unstubbed_driver = _load_driver()

    shard_root = tmp_path / "S02"
    packet_dir = shard_root / "ipqc" / "S02-W00" / "worker_safe_tasks" / "demo__repo-0001"
    packet_dir.mkdir(parents=True)
    packet = {"instance_id": "demo__repo-0001", "repo": "demo/repo", "ipqc_window_id": "S02-W00"}
    (packet_dir / "task_packet.json").write_text(json.dumps(packet), encoding="utf-8")

    packets = unstubbed_driver.load_task_packets(shard_root)
    assert len(packets) == 1
    assert packets[0]["instance_id"] == "demo__repo-0001"


def test_task_shard_arg_recorded_in_verdict_meta(tmp_path, driver):
    shard_root = tmp_path / "S02"
    args = _run_args(tmp_path, max_tasks=1, task_shard=shard_root)
    verdict = driver.run_driver(args)
    assert verdict["stage_b_prime_meta"]["task_shard"] == str(shard_root)


# ---------------------------------------------------------------------------
# run_stage_b_prime.sh CLI-wiring smoke test: mirrors the shell launcher's four arms'
# flag shapes verbatim, so a flag-name typo drift between the shell script and this
# module's argparse fails here instead of only at real-launch time.
# ---------------------------------------------------------------------------


def test_main_cli_accepts_run_stage_b_prime_sh_flag_shapes(tmp_path, monkeypatch):
    if not CLI_BIN.exists():
        pytest.skip("econ_fold_cli not built; run `cargo build --bin econ_fold_cli -p turing-economy` first")
    module = _load_driver()
    captured: list = []
    monkeypatch.setattr(module, "run_driver", lambda args: captured.append(args) or {"tasks": []})

    priors_path = tmp_path / "priors.json"
    priors_path.write_text(json.dumps({"priors": {}}), encoding="utf-8")
    shard = tmp_path / "S02"

    def _common(label: str) -> list[str]:
        return [
            "--task-shard",
            str(shard),
            "--out",
            str(tmp_path / f"{label}.json"),
            "--task-dir-root",
            str(tmp_path / f"{label}_tasks"),
            "--report-dir",
            str(tmp_path / f"{label}_scoring"),
            "--scoring-python",
            "python3",
            "--scoring-timeout-s",
            "2700",
            "--run-label",
            f"stageBprime-{label}",
        ]

    arms = {
        "W": _common("W") + ["--tau", "0.5", "--priors", str(priors_path)],
        "F": _common("F") + ["--tau", "0.5", "--priors", str(priors_path), "--frozen-backup"],
        "C": _common("C") + ["--tau", "0.5"],
        "U": _common("U") + ["--tau", "inf"],
    }
    for label, argv in arms.items():
        rc = module.main(argv)
        assert rc == 0, f"arm {label} argv failed to parse/run: {argv}"
    assert len(captured) == 4

    w_args, f_args, c_args, u_args = captured
    assert w_args.priors == priors_path and w_args.frozen_backup is False and w_args.tau == "0.5"
    assert f_args.priors == priors_path and f_args.frozen_backup is True and f_args.tau == "0.5"
    assert c_args.priors is None and c_args.tau == "0.5"
    assert u_args.priors is None and u_args.tau == "inf"
    for args in captured:
        assert args.task_shard == shard
