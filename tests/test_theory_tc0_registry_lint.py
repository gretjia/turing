import hashlib
import json
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "tools" / "theory" / "lint_event_registry_consistency.py"
REGISTRY = REPO / "pack" / "04_registries" / "event_registry_v5_3_1.json"


def _name_set_digest(names):
    payload = "\n".join(sorted(names)) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _registry_with_counts(counts_override=None, digest_override=None):
    events = [
        {
            "canonical_name": "AlphaObserved",
            "event_class": "OBSERVATION",
            "head_effect": "PRESERVE",
            "target_ref": "tape_tip",
            "predicate_required": True,
            "human_required": False,
            "payload_schema_id": "alpha_observed.v1",
            "ordinal": 1,
            "status": "TEST",
        },
        {
            "canonical_name": "BetaAuthorized",
            "event_class": "AUTHORIZATION",
            "head_effect": "ADVANCE",
            "target_ref": "authorization_head",
            "predicate_required": True,
            "human_required": False,
            "payload_schema_id": "beta_authorized.v1",
            "ordinal": 2,
            "status": "TEST",
        },
    ]
    counts = {
        "total": 2,
        "advance": 1,
        "preserve": 1,
        "sovereign_accept": 0,
        "authorization": 1,
        "proposal": 0,
        "observation": 1,
        "receipt": 0,
        "failure": 0,
        "economy": 0,
    }
    if counts_override:
        counts.update(counts_override)
    names = [event["canonical_name"] for event in events]
    return {
        "schema_id": "test.event_registry",
        "registry_name_set_sha256": digest_override or _name_set_digest(names),
        "registry_name_set_sha256_profile": "sorted_canonical_names_lf_trailing_lf",
        "counts": counts,
        "unknown_event_policy": "REJECT",
        "append_only_by_name": True,
        "never_renumber": True,
        "events": events,
    }


def test_valid_registry_passes_and_writes_machine_report(tmp_path):
    registry = tmp_path / "registry.json"
    report = tmp_path / "report.json"
    registry.write_text(json.dumps(_registry_with_counts()), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--registry", str(registry), "--out", str(report)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["verdict"] == "PASS"
    assert all(check["status"] == "PASS" for check in data["checks"])


def test_count_mismatch_fails_with_actionable_report(tmp_path):
    registry = tmp_path / "registry.json"
    report = tmp_path / "report.json"
    registry.write_text(
        json.dumps(_registry_with_counts({"total": 1, "preserve": 0})),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--registry", str(registry), "--out", str(report)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 1
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["verdict"] == "FAIL"
    failing = {check["name"]: check["message"] for check in data["checks"] if check["status"] == "FAIL"}
    assert "counts.total" in failing
    assert "counts.preserve" in failing


def test_current_repo_registry_passes_self_consistency(tmp_path):
    report = tmp_path / "report.json"

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--registry", str(REGISTRY), "--out", str(report)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["verdict"] == "PASS"
    assert data["observed"]["counts"]["total"] == 63
