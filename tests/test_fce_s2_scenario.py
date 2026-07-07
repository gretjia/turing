from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
WORK_ROOT = REPO.parent
PLAN_ROOT = WORK_ROOT / "PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702"
TOOLS = REPO / "tools" / "certification"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_scenario(out: Path, *, plan_root: Path = PLAN_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "python3",
            str(TOOLS / "scenarios" / "FCE-S2.py"),
            "--root",
            str(out),
            "--repo",
            str(REPO),
            "--plan-root",
            str(plan_root),
            "--scenario-id",
            "FCE-S2",
        ],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def test_fce_s2_universality_scenario_pass(tmp_path: Path) -> None:
    out = tmp_path / "fce_run"
    proc = run_scenario(out)

    assert proc.returncode == 0, proc.stdout
    verdict = load_json(out / "FCE-S2" / "FCE-S2_verdict.json")
    assert verdict["schema_id"] == "turingos.fce_scenario_verdict.v1"
    assert verdict["scenario_id"] == "FCE-S2"
    assert verdict["verdict"] == "PASS"
    assert verdict["fixture_or_real"] == "REAL"
    assert verdict["goals_served"] == ["G3"]
    assert verdict["automatic_fail_triggered"] is None
    assert verdict["not_run_is_fail"] is True

    expected_criteria = {
        "witness_bundle_digests_ok",
        "tc03_fuzz_differential_reverified_pass",
        "tc04_tc09_local_audit_reverified_pass",
        "reverified_verdicts_byte_consistent_with_stored",
        "tc5_packet_check_pass_and_not_overclaiming",
        "tc10_packet_local_slot_correctly_guarded_not_run",
        "tc10_external_artifact_present_with_distinct_verifier_identity",
        "halting_and_nonhalting_example_classes_present",
        "noninterference_gate_pass_economy_signals_ignored",
    }
    seen_criteria = {item["criterion"] for item in verdict["pass_criteria_results"]}
    assert seen_criteria == expected_criteria
    assert all(item["result"] is True for item in verdict["pass_criteria_results"])

    # Every evidence path listed in the verdict must exist and carry a real
    # sha256 digest of its actual bytes -- no fabricated digests.
    for evidence_path in verdict["evidence"]:
        full_path = out / evidence_path
        assert full_path.is_file(), f"missing evidence file: {evidence_path}"
        recorded = verdict["evidence_sha256"][evidence_path]
        assert recorded.startswith("sha256:")
        import hashlib

        assert recorded == "sha256:" + hashlib.sha256(full_path.read_bytes()).hexdigest()

    # The real TC audit tools must actually have been invoked (not merely a
    # cached-artifact read): both TC-03 and TC-04..09 re-audits ran, plus the
    # bundle digest check and the TC5 packet check.
    joined_cmds = " ".join(item["cmd"] for item in verdict["commands_executed"])
    assert "sha256sum -c bundle_sha256s.txt" in joined_cmds
    assert "audit_tc3_evidence.py" in joined_cmds
    assert "audit_tc4_witness.py" in joined_cmds
    assert "build_tc5_packet.py" in joined_cmds
    assert all(item["exit_code"] == 0 for item in verdict["commands_executed"])

    # Byte-consistency report must cover all nine TC gates plus the mutation
    # matrix, non-interference report, and TC-03 differential artifact, and
    # every comparison must be genuinely consistent (not asserted blind).
    consistency = load_json(out / "FCE-S2" / "byte_consistency_report.json")
    labels = {item["label"] for item in consistency["results"]}
    assert labels == {f"TC-{index:02d}" for index in range(1, 10)} | {
        "mutation_matrix",
        "noninterference_report",
        "tc03_differential_results",
    }
    assert all(item["byte_consistent"] is True for item in consistency["results"])

    # Halting AND non-halting classes must both be present, independently
    # recomputed from bundle_manifest.json.
    classes = load_json(out / "FCE-S2" / "halting_nonhalting_classes.json")
    assert classes["halting_count_recomputed"] > 0
    assert classes["nonhalting_count_recomputed"] > 0
    assert classes["counts_self_consistent"] is True

    # TC-10 external artifact must show custody-separated, distinct verifier
    # identity -- never the implementer.
    tc10_external = load_json(out / "FCE-S2" / "tc10_external_verification.json")
    assert tc10_external["present_with_distinct_custody_verified_identity"] is True
    assert tc10_external["custody_ok"] is True
    assert tc10_external["identity_distinct_from_implementer_markers"] is True
    assert tc10_external["verifier_identity"] not in ("", "implementer", "self")

    # The packet-local TC-10 slot must remain the correctly-guarded NOT_RUN
    # sentinel -- an implementer-written PASS there would itself be the
    # self-closure overclaim the module charter forbids.
    tc10_slot = load_json(out / "FCE-S2" / "tc10_packet_local_slot.json")
    assert tc10_slot["observed"]["verdict"] == "NOT_RUN"
    assert tc10_slot["observed"]["implementer_may_run"] is False
    assert tc10_slot["correctly_guarded"] is True

    claim_boundary = load_json(out / "FCE-S2" / "CLAIM_BOUNDARY.json")
    assert claim_boundary["evidence_class"] == "REAL"
    assert "FCE-S2/CLAIM_BOUNDARY.json" in verdict["evidence"]


def test_fce_s2_fails_honestly_when_tc10_external_artifact_absent(tmp_path: Path) -> None:
    """If the TC-10 external verifier artifact cannot be found, the scenario
    must FAIL (not fabricate a PASS) -- this is the exact automatic-fail
    behavior the spec requires ("If TC-10 is absent: this scenario FAILs").
    """
    empty_plan_root = tmp_path / "empty_plan_root"
    (empty_plan_root / "evidence" / "session_20260702").mkdir(parents=True)

    out = tmp_path / "fce_run_neg"
    proc = run_scenario(out, plan_root=empty_plan_root)

    assert proc.returncode == 1
    verdict = load_json(out / "FCE-S2" / "FCE-S2_verdict.json")
    assert verdict["verdict"] == "FAIL"
    assert verdict["automatic_fail_triggered"] == "tc10_external_artifact_absent"
    tc10_criterion = next(
        item
        for item in verdict["pass_criteria_results"]
        if item["criterion"] == "tc10_external_artifact_present_with_distinct_verifier_identity"
    )
    assert tc10_criterion["result"] is False
