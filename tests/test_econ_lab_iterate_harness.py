"""WP-L3-1 acceptance tests: `tools/econ_lab/iterate/iterate_harness.py`.

Every worker in this file is a fully offline, scripted mock (no network/API call) --
per the WP brief's "测试:mock worker 全离线". The one exception -- an audit_loop_until_
pass.py PASS check against a bundle this harness actually produces -- runs the real,
unmodified `tools/bench/audit_loop_until_pass.py` (via its own `audit_coverage`
function, the same way `tests/test_stage11_loop_until_pass.py` already does), per the
WP brief's "跑真 audit_loop_until_pass.py 于产出 bundle 并 PASS".
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import pytest

REPO = Path(__file__).resolve().parents[1]
ECON_LAB = REPO / "tools" / "econ_lab"
BENCH = REPO / "tools" / "bench"

sys.path.insert(0, str(ECON_LAB))
sys.path.insert(0, str(ECON_LAB / "iterate"))

import iterate.iterate_harness as ih  # noqa: E402
import monitor.loop_detector as loop_detector  # noqa: E402
import monitor.termination as termination  # noqa: E402


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def make_scripted_worker(outcomes: Sequence[ih.AttemptOutcome]) -> ih.WorkerCallable:
    """A fully offline, deterministic worker: attempt N gets `outcomes[N-1]`, ignoring
    the materialized capsule text/broadcast rules it is handed (the *harness*'s
    rematerialization is what these tests assert on, not the worker's own behavior)."""

    def _worker(attempt_index: int, capsule_text: str, active_broadcast_rules: Sequence[Mapping[str, Any]]) -> ih.AttemptOutcome:
        assert capsule_text  # the harness must hand the worker non-empty materialized context every round
        return outcomes[attempt_index - 1]

    return _worker


def make_task(instance_id: str) -> dict[str, Any]:
    return {
        "instance_id": instance_id,
        "repo": "example/example",
        "base_commit": "0" * 40,
        "problem_statement": f"WP-L3-1 fixture task {instance_id}",
    }


def make_capsule(tmp_path: Path, instance_id: str) -> Path:
    capsule_dir = tmp_path / "capsules" / instance_id
    capsule_dir.mkdir(parents=True, exist_ok=True)
    capsule_path = capsule_dir / "worker_capsule.md"
    capsule_path.write_text(f"# Worker capsule for {instance_id}\n\nFix the failing test.\n", encoding="utf-8")
    return capsule_path


def default_detector_config() -> loop_detector.LoopDetectorConfig:
    # Harness-invented placeholder thresholds (not an ADR-pinned B-zone number), same
    # posture as `tests/test_econ_lab_loop_detector.py`'s own fixtures.
    return loop_detector.LoopDetectorConfig(
        same_fragment_failure_threshold=3,
        action_window_size=5,
        action_window_repeat_threshold=3,
        phase_timeout_steps=50,
    )


def wrong_file_signals() -> dict[str, Any]:
    return {"diff_scope": "wrong_file", "exit_code": 1, "macro_observation_kind": "patch_failed"}


def context_missing_signals() -> dict[str, Any]:
    return {"timeout_kind": "context_starved", "exit_code": 1, "macro_observation_kind": "patch_failed"}


def pass_outcome(**tokens: int) -> ih.AttemptOutcome:
    return ih.AttemptOutcome(
        result="PASS",
        observed_signals={"official_evaluator_result": "PASS"},
        prompt_tokens=tokens.get("prompt_tokens", 50),
        completion_tokens=tokens.get("completion_tokens", 40),
        wall_time_ms=100,
        patch_note="attempt produced a passing candidate patch",
    )


# ---------------------------------------------------------------------------
# 1. Convergence case: attempt 1 (bad route) fails, attempt 2 (broadcast-corrected) passes.
# ---------------------------------------------------------------------------


def test_converged_case_second_attempt_real(tmp_path: Path) -> None:
    instance_id = "iterate_case_converge"
    task = make_task(instance_id)
    capsule_path = make_capsule(tmp_path, instance_id)
    config = ih.IterateConfig(
        route_id=f"{instance_id}::armA::bad_route",
        remaining_candidates=[f"{instance_id}::armA::alt_route", f"{instance_id}::armB::alt_route"],
        loop_detector_config=default_detector_config(),
        same_signature_retry_limit=ih.SAME_SIGNATURE_RETRY_LIMIT_FIXTURE_ADR007_DECISION_6A,
    )
    worker = make_scripted_worker(
        [
            ih.AttemptOutcome(result="FAIL", observed_signals=wrong_file_signals(), prompt_tokens=80, completion_tokens=60, wall_time_ms=90),
            pass_outcome(),
        ]
    )

    run_record = ih.run_iterate_harness(
        out_dir=tmp_path / "out",
        task=task,
        worker_fn=worker,
        config=config,
        capsule_path=capsule_path,
    )

    assert run_record["outcome_status"] == "CONVERGED"
    assert run_record["attempts_total"] == 2
    loop = run_record["loop_until_pass"]
    assert loop["status"] == "PASS"
    assert loop["attempts_total"] == 2
    assert loop["failed_attempts_before_accept"] == 1
    assert loop["accepted_attempt_index"] == 2
    assert loop["first_failed_attempt_index"] == 1
    assert loop["fallback_to_auto_authorization"] is False
    assert loop["retry_decision_source"] in {"tape_reducer_or_policy", "tape_policy"}
    for key in ("human_intervention_count", "manual_patch_count", "manual_approval_count", "manual_rerun_selection_count"):
        assert loop[key] == 0
    assert Path(run_record["micro_tape_bundle"]).exists()


def test_real_audit_loop_until_pass_passes_on_produced_bundle(tmp_path: Path) -> None:
    """The WP's ship-gate requirement: run the real, unmodified auditor against a
    bundle this harness actually produced, and it must PASS."""
    instance_id = "iterate_case_audit_pass"
    task = make_task(instance_id)
    capsule_path = make_capsule(tmp_path, instance_id)
    config = ih.IterateConfig(
        route_id=f"{instance_id}::armA::bad_route",
        remaining_candidates=[f"{instance_id}::armA::alt_route"],
        loop_detector_config=default_detector_config(),
        same_signature_retry_limit=2,
    )
    worker = make_scripted_worker(
        [
            ih.AttemptOutcome(result="FAIL", observed_signals=context_missing_signals(), wall_time_ms=90),
            pass_outcome(),
        ]
    )

    run_record = ih.run_iterate_harness(
        out_dir=tmp_path / "out",
        task=task,
        worker_fn=worker,
        config=config,
        capsule_path=capsule_path,
    )
    coverage = ih.build_coverage([run_record])
    coverage_path = tmp_path / "out" / "turingos" / "substrate_coverage.json"
    ih.write_json(coverage_path, coverage)

    loop_auditor = load_module("iterate_harness_real_loop_auditor", BENCH / "audit_loop_until_pass.py")
    report = loop_auditor.audit_coverage(coverage_path)

    assert report["status"] == "PASS", report["problems"]
    assert report["attempts_total"] == 2
    assert report["failed_attempts_before_accept"] == 1


def test_real_audit_loop_until_pass_cli_exit_zero(tmp_path: Path) -> None:
    """Same check, but through the real auditor's actual CLI entry point (not just its
    Python function), matching how the ship gate invokes it."""
    import subprocess

    instance_id = "iterate_case_audit_cli"
    task = make_task(instance_id)
    capsule_path = make_capsule(tmp_path, instance_id)
    config = ih.IterateConfig(
        route_id=f"{instance_id}::armA::bad_route",
        remaining_candidates=[f"{instance_id}::armA::alt_route"],
        loop_detector_config=default_detector_config(),
        same_signature_retry_limit=2,
    )
    worker = make_scripted_worker(
        [
            ih.AttemptOutcome(result="FAIL", observed_signals=wrong_file_signals(), wall_time_ms=90),
            pass_outcome(),
        ]
    )
    run_record = ih.run_iterate_harness(
        out_dir=tmp_path / "out",
        task=task,
        worker_fn=worker,
        config=config,
        capsule_path=capsule_path,
    )
    coverage_path = tmp_path / "out" / "turingos" / "substrate_coverage.json"
    ih.write_json(coverage_path, ih.build_coverage([run_record]))
    audit_out = tmp_path / "out" / "loop_until_pass_audit.json"

    proc = subprocess.run(
        [
            "python3",
            str(BENCH / "audit_loop_until_pass.py"),
            "--coverage",
            str(coverage_path),
            "--out",
            str(audit_out),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    import json

    audit_report = json.loads(audit_out.read_text(encoding="utf-8"))
    assert audit_report["status"] == "PASS"


# ---------------------------------------------------------------------------
# 2. Escalation case: same signature repeats up to the threshold -> RouteFalsified with
#    non-empty remaining_candidates (the recon-identified always-empty gap this WP closes).
# ---------------------------------------------------------------------------


def test_escalation_case_same_signature_threshold(tmp_path: Path) -> None:
    instance_id = "iterate_case_escalate"
    task = make_task(instance_id)
    capsule_path = make_capsule(tmp_path, instance_id)
    remaining = [f"{instance_id}::armB::route_two", f"{instance_id}::armC::route_three"]
    config = ih.IterateConfig(
        route_id=f"{instance_id}::armA::stuck_route",
        remaining_candidates=remaining,
        loop_detector_config=default_detector_config(),
        same_signature_retry_limit=2,
    )
    worker = make_scripted_worker(
        [
            ih.AttemptOutcome(result="FAIL", observed_signals=context_missing_signals(), wall_time_ms=90),
            ih.AttemptOutcome(result="FAIL", observed_signals=context_missing_signals(), wall_time_ms=90),
        ]
    )

    run_record = ih.run_iterate_harness(
        out_dir=tmp_path / "out",
        task=task,
        worker_fn=worker,
        config=config,
        capsule_path=capsule_path,
    )

    assert run_record["outcome_status"] == "ESCALATED"
    assert run_record["attempts_total"] == 2
    assert "loop_until_pass" not in run_record
    report = run_record["route_falsification_report"]
    assert report["route_id"] == config.route_id
    assert report["remaining_candidates"] == remaining
    assert report["remaining_candidates"] != []
    assert report["proposal_only"] is True
    # Re-verified with the real termination.py scan (WP brief: "过 termination.py 的
    # assert_report_has_no_bzone_leak 同款扫描") -- must not raise.
    termination.assert_report_has_no_bzone_leak(report)
    event = run_record["route_falsified_event"]
    assert event["event_type"] == "RouteFalsified"
    assert event["head_effect"] == "PRESERVE"


def test_escalation_resets_on_different_signature(tmp_path: Path) -> None:
    """Decision 6a is *same-signature* consecutive failures: a signature change resets
    the streak, so a run that fails twice with two *different* signatures then passes
    must still converge (not escalate) under a threshold-2 config."""
    instance_id = "iterate_case_reset_streak"
    task = make_task(instance_id)
    capsule_path = make_capsule(tmp_path, instance_id)
    config = ih.IterateConfig(
        route_id=f"{instance_id}::armA::route",
        remaining_candidates=[f"{instance_id}::armB::route"],
        loop_detector_config=default_detector_config(),
        same_signature_retry_limit=2,
    )
    worker = make_scripted_worker(
        [
            ih.AttemptOutcome(result="FAIL", observed_signals=wrong_file_signals(), wall_time_ms=90),
            ih.AttemptOutcome(result="FAIL", observed_signals=context_missing_signals(), wall_time_ms=90),
            pass_outcome(),
        ]
    )

    run_record = ih.run_iterate_harness(
        out_dir=tmp_path / "out",
        task=task,
        worker_fn=worker,
        config=config,
        capsule_path=capsule_path,
    )

    assert run_record["outcome_status"] == "CONVERGED"
    assert run_record["attempts_total"] == 3


def test_budget_exhausted_hard_cap_safety_net(tmp_path: Path) -> None:
    """A worker that never repeats a signature and never passes must still terminate
    (BUDGET_EXHAUSTED), never loop forever -- the hard-cap safety net."""
    instance_id = "iterate_case_budget_exhausted"
    task = make_task(instance_id)
    capsule_path = make_capsule(tmp_path, instance_id)
    signatures = [wrong_file_signals(), context_missing_signals()]
    config = ih.IterateConfig(
        route_id=f"{instance_id}::armA::route",
        remaining_candidates=[f"{instance_id}::armB::route"],
        loop_detector_config=default_detector_config(),
        same_signature_retry_limit=2,
        max_attempts_hard_cap=4,
    )
    worker = make_scripted_worker(
        [ih.AttemptOutcome(result="FAIL", observed_signals=signatures[i % 2], wall_time_ms=10) for i in range(4)]
    )

    run_record = ih.run_iterate_harness(
        out_dir=tmp_path / "out",
        task=task,
        worker_fn=worker,
        config=config,
        capsule_path=capsule_path,
    )

    assert run_record["outcome_status"] == "BUDGET_EXHAUSTED"
    assert run_record["attempts_total"] == 4


# ---------------------------------------------------------------------------
# 3. Detector organically triggered case: a repeated same-fragment failed edit stream
#    inside one attempt must trip `monitor.loop_detector` for real (fed each round).
# ---------------------------------------------------------------------------


def test_detector_organically_triggers_on_repeated_edit_stream(tmp_path: Path) -> None:
    instance_id = "iterate_case_detector_trip"
    task = make_task(instance_id)
    capsule_path = make_capsule(tmp_path, instance_id)
    config = ih.IterateConfig(
        route_id=f"{instance_id}::armA::route",
        remaining_candidates=[f"{instance_id}::armB::route"],
        loop_detector_config=loop_detector.LoopDetectorConfig(
            same_fragment_failure_threshold=3,
            action_window_size=6,
            action_window_repeat_threshold=6,  # effectively unreachable here -- isolates rule 1
            phase_timeout_steps=1000,
        ),
        same_signature_retry_limit=2,
    )
    repeated_fragment_edits = [
        {
            "event_type": "edit",
            "file_path": "pkg/module.py",
            "fragment_id": "frag_1",
            "action_signature": f"str_replace_attempt_{i}",
            "outcome": "failed",
        }
        for i in range(3)
    ]
    worker = make_scripted_worker(
        [
            ih.AttemptOutcome(
                result="FAIL",
                observed_signals=wrong_file_signals(),
                edit_trace=repeated_fragment_edits,
                wall_time_ms=90,
            ),
            pass_outcome(),
        ]
    )

    run_record = ih.run_iterate_harness(
        out_dir=tmp_path / "out",
        task=task,
        worker_fn=worker,
        config=config,
        capsule_path=capsule_path,
    )

    assert run_record["detector_trips"], "detector must have organically tripped on the repeated same-fragment edit stream"
    trip = run_record["detector_trips"][0]
    assert trip["rule_id"] == loop_detector.RULE_SAME_FRAGMENT_REPEATED_FAILURE
    assert trip["evidence"]["file_path"] == "pkg/module.py"
    # Decision 3 fact-only discipline: no raw count/threshold leaks into the evidence.
    for value in trip["evidence"].values():
        assert not isinstance(value, (int, float, bool))


# ---------------------------------------------------------------------------
# 4. Replay determinism (Art 0.2): the same scripted sequence, run twice, produces
#    byte-identical bundles.
# ---------------------------------------------------------------------------


def _normalize_event_refs(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("mu:"):
        return "<EVENT_REF>"
    if isinstance(value, dict):
        return {k: _normalize_event_refs(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_event_refs(v) for v in value]
    return value


def test_replay_is_deterministic(tmp_path: Path) -> None:
    """Determinism (Art 0.2) at the level this harness actually controls: the same
    scripted worker sequence + config always produces the same event_type/payload
    sequence and the same business-level `loop_until_pass` shape (attempts_total,
    failure classes, retry_decision_source, ...). Raw git commit object ids are
    intentionally *not* asserted equal here -- `commit_stage6_event` (an existing,
    unmodified `tools/bench` primitive this harness reuses read-only) embeds a
    wall-clock commit timestamp, so two independently-run constructions never share
    byte-identical oids; this is a pre-existing property of the reused primitive, not
    something this WP's own code introduces or could paper over without touching a file
    outside `tools/econ_lab/iterate/`."""
    instance_id = "iterate_case_replay"
    task = make_task(instance_id)
    tape_auditor = load_module("iterate_harness_replay_tape_auditor", BENCH / "audit_micro_tape_decision_dag.py")

    def build_once(root: Path) -> tuple[dict[str, Any], list[tuple[str, dict[str, Any]]]]:
        capsule_path = make_capsule(root, instance_id)
        config = ih.IterateConfig(
            route_id=f"{instance_id}::armA::route",
            remaining_candidates=[f"{instance_id}::armB::route"],
            loop_detector_config=default_detector_config(),
            same_signature_retry_limit=2,
        )
        worker = make_scripted_worker(
            [
                ih.AttemptOutcome(result="FAIL", observed_signals=wrong_file_signals(), wall_time_ms=90),
                pass_outcome(),
            ]
        )
        run_record = ih.run_iterate_harness(
            out_dir=root / "out",
            task=task,
            worker_fn=worker,
            config=config,
            capsule_path=capsule_path,
        )
        git_dir, _ = tape_auditor.fetch_bundle(Path(run_record["micro_tape_bundle"]), root / "replay_work")
        events = tape_auditor.read_event_chain(git_dir)
        # `mu:<git-oid>` event references embed the reused `commit_stage6_event`
        # primitive's wall-clock commit timestamp transitively (via the oid), so they
        # are normalized away here -- everything else in a payload (facts, classes,
        # token counts, schema ids, ordering) is asserted equal verbatim.
        shape = [(event["event_type"], _normalize_event_refs(event["payload"])) for event in events]
        return run_record, shape

    run_a, shape_a = build_once(tmp_path / "a")
    run_b, shape_b = build_once(tmp_path / "b")

    assert shape_a == shape_b
    assert run_a["outcome_status"] == run_b["outcome_status"] == "CONVERGED"
    assert run_a["attempts_total"] == run_b["attempts_total"]

    def strip_ids(loop: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in loop.items() if not k.endswith("_event_id") and k not in ("accepted_head",)}

    assert strip_ids(run_a["loop_until_pass"]) == strip_ids(run_b["loop_until_pass"])


# ---------------------------------------------------------------------------
# 5. Retry-policy pure-function unit tests.
# ---------------------------------------------------------------------------


def test_consecutive_same_signature_count_pure_function() -> None:
    assert ih.consecutive_same_signature_count([]) == 0
    assert ih.consecutive_same_signature_count([("A", "p1")]) == 1
    assert ih.consecutive_same_signature_count([("A", "p1"), ("A", "p1")]) == 2
    assert ih.consecutive_same_signature_count([("A", "p1"), ("B", "p2")]) == 1
    assert ih.consecutive_same_signature_count([("A", "p1"), ("A", "p1"), ("B", "p2")]) == 1


def test_compose_failure_broadcast_content_is_decision3_legal() -> None:
    abstract_pattern, guidance = ih.compose_failure_broadcast_content("WRONG_FILE", "route::x")
    assert isinstance(abstract_pattern, str) and abstract_pattern
    assert isinstance(guidance, str) and guidance
    for forbidden in ("tau", "lambda", "threshold", "bucket", "τ", "λ"):
        assert forbidden not in guidance.lower()

    with pytest.raises(ih.HarnessError):
        ih.compose_failure_broadcast_content("NOT_A_REGISTERED_CLASS", "route::x")
