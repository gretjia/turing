import importlib.util
import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
AUDITOR = REPO / "tools" / "bench" / "audit_micro_tape_decision_dag.py"


def load_auditor():
    spec = importlib.util.spec_from_file_location("audit_micro_tape_decision_dag", AUDITOR)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def run(cmd, cwd):
    subprocess.run(cmd, cwd=cwd, check=True, text=True, capture_output=True)


def commit_event(repo, event):
    (repo / "event").write_text(json.dumps(event, sort_keys=True) + "\n", encoding="utf-8")
    run(["git", "add", "event"], repo)
    run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-m",
            "turingos micro event",
        ],
        repo,
    )
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()


def event(seq, event_type, prev, accepted, payload, *, head_effect="PRESERVE", product="PASS"):
    auditor = load_auditor()
    payload_hash = auditor.sha256_json(payload)
    return {
        "accepted_head_before": accepted,
        "authority_epoch": 0,
        "authorization_head_before": None,
        "content_digest": payload_hash,
        "event_schema_id": event_type.lower() + ".v1",
        "event_type": event_type,
        "head_effect": head_effect,
        "payload": payload,
        "payload_hash": payload_hash,
        "predicate_product": product,
        "prev_tape_tip": prev,
        "schema_id": "micro_event_envelope.v1",
        "sequence": seq,
        "verified": product == "PASS",
        "writer_id": "writer:test",
    }


def make_bundle(tmp_path):
    repo = tmp_path / "repo"
    bundle = tmp_path / "micro_tape.bundle"
    run(["git", "init", "--object-format=sha256", str(repo)], tmp_path)
    accepted = None
    prev = None

    genesis = event(
        0,
        "SystemConstitutionAccepted",
        prev,
        accepted,
        {"constitution_digest": "sha256:" + "1" * 64},
        head_effect="ADVANCE",
    )
    oid0 = commit_event(repo, genesis)
    accepted = "mu:" + oid0
    prev = "mu:" + oid0

    capsule = event(
        1,
        "WorkCapsuleBuilt",
        prev,
        accepted,
        {"capsule_id": "wc_test", "private_contract_hash": "sha256:" + "2" * 64},
    )
    oid1 = commit_event(repo, capsule)
    prev = "mu:" + oid1

    receipt = event(
        2,
        "WorkerReceiptImported",
        prev,
        accepted,
        {"capsule_id": "wc_test", "receipt_id": "rcp_test", "patch_hash": "sha256:" + "3" * 64},
    )
    oid2 = commit_event(repo, receipt)
    prev = "mu:" + oid2

    macro = event(
        3,
        "MacroObservationImported",
        prev,
        accepted,
        {"capsule_id": "wc_test", "macro_id": "macro:diff:test", "diff_hash": "sha256:" + "3" * 64},
    )
    oid3 = commit_event(repo, macro)
    prev = "mu:" + oid3

    evidence = event(
        4,
        "OfficialEvaluatorEvidenceImported",
        prev,
        accepted,
        {
            "capsule_id": "wc_test",
            "evidence_id": "ev_official_test",
            "macro_anchor_id": "macro:diff:test",
            "result": "PASS",
            "worker_receipt_id": "rcp_test",
        },
    )
    oid4 = commit_event(repo, evidence)
    prev = "mu:" + oid4

    accept = event(
        5,
        "CandidateAccepted",
        prev,
        accepted,
        {
            "candidate_id": "cand_test",
            "capsule_id": "wc_test",
            "macro_anchor_id": "macro:diff:test",
            "official_evaluator_evidence_id": "ev_official_test",
            "worker_receipt_id": "rcp_test",
        },
        head_effect="ADVANCE",
    )
    oid5 = commit_event(repo, accept)
    run(["git", "update-ref", "refs/turingos/tape_tip", oid5], repo)
    run(["git", "update-ref", "refs/turingos/accepted_head", oid5], repo)
    run(["git", "bundle", "create", str(bundle), "--all"], repo)
    return bundle


def test_micro_tape_auditor_replays_bundle_and_builds_reference_dag(tmp_path):
    auditor = load_auditor()
    bundle = make_bundle(tmp_path)

    report = auditor.audit_bundles([bundle], tmp_path / "work")

    assert report["verdict"] == "PASS"
    assert report["aggregate"]["bundle_count"] == 1
    assert report["aggregate"]["event_count"] == 6
    run_report = report["runs"][0]
    assert run_report["replay_valid"] is True
    assert run_report["derived_refs"]["accepted_head"] == run_report["actual_refs"]["accepted_head"]
    assert run_report["event_counts"]["CandidateAccepted"] == 1
    assert any(edge["kind"] == "official_evidence_to_accept" for edge in run_report["dag_edges"])
    assert any(step["event_type"] == "CandidateAccepted" for step in run_report["golden_path"])
