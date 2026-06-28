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


def commit_event(repo, event, *, parent=None):
    (repo / "event").write_text(json.dumps(event, sort_keys=True) + "\n", encoding="utf-8")
    run(["git", "add", "event"], repo)
    cmd = [
        "git",
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-m",
        "turingos micro event",
    ]
    if parent == "none":
        tree = subprocess.check_output(["git", "write-tree"], cwd=repo, text=True).strip()
        oid = subprocess.check_output(
            [
                "git",
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.com",
                "commit-tree",
                tree,
                "-m",
                "turingos micro event",
            ],
            cwd=repo,
            text=True,
        ).strip()
        run(["git", "reset", "--hard", oid], repo)
        return oid
    run(cmd, repo)
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()


def registry_row(event_type):
    auditor = load_auditor()
    registry = auditor.load_event_registry()
    return registry[event_type]


def event(seq, event_type, prev, accepted, payload, *, head_effect=None, product="PASS"):
    auditor = load_auditor()
    row = registry_row(event_type)
    payload_hash = auditor.sha256_json(payload)
    return {
        "accepted_head_before": accepted,
        "authority_epoch": 0,
        "authorization_head_before": None,
        "content_digest": payload_hash,
        "event_schema_id": row["payload_schema_id"],
        "event_type": event_type,
        "head_effect": head_effect or row["head_effect"],
        "payload": payload,
        "payload_hash": payload_hash,
        "predicate_product": product,
        "prev_tape_tip": prev,
        "schema_id": "micro_event_envelope.v1",
        "sequence": seq,
        "verified": product == "PASS",
        "writer_id": "writer:test",
    }


def make_bundle(tmp_path, specs, *, break_git_parent_at=None):
    repo = tmp_path / f"repo_{len(list(tmp_path.iterdir()))}"
    bundle = tmp_path / f"{repo.name}.bundle"
    run(["git", "init", "--object-format=sha256", str(repo)], tmp_path)
    accepted = None
    authorization = None
    prev = None
    last_oid = None
    for seq, spec in enumerate(specs):
        item = event(
            seq,
            spec["event_type"],
            prev,
            accepted,
            spec.get("payload", {}),
            head_effect=spec.get("head_effect"),
            product=spec.get("product", "PASS"),
        )
        parent_mode = "none" if break_git_parent_at == seq else None
        oid = commit_event(repo, item, parent=parent_mode)
        event_id = "mu:" + oid
        row = registry_row(spec["event_type"])
        if row["event_class"] == "SOVEREIGN_ACCEPT" and item["predicate_product"] == "PASS":
            accepted = event_id
        if row["event_class"] == "AUTHORIZATION" and item["predicate_product"] == "PASS":
            authorization = event_id
        prev = event_id
        last_oid = oid
    assert last_oid is not None
    run(["git", "update-ref", "refs/turingos/tape_tip", last_oid], repo)
    if accepted:
        run(["git", "update-ref", "refs/turingos/accepted_head", accepted.removeprefix("mu:")], repo)
    if authorization:
        run(["git", "update-ref", "refs/turingos/authorization_head", authorization.removeprefix("mu:")], repo)
    run(["git", "bundle", "create", str(bundle), "--all"], repo)
    return bundle


def make_bundle_with_context(tmp_path, specs, *, break_git_parent_at=None):
    repo = tmp_path / f"repo_{len(list(tmp_path.iterdir()))}"
    bundle = tmp_path / f"{repo.name}.bundle"
    run(["git", "init", "--object-format=sha256", str(repo)], tmp_path)
    accepted = None
    authorization = None
    prev = None
    last_oid = None
    context = {"events": [], "event_ids": {}}
    for seq, spec in enumerate(specs):
        payload = spec.get("payload", {})
        if callable(payload):
            payload = payload(context)
        item = event(
            seq,
            spec["event_type"],
            prev,
            accepted,
            payload,
            head_effect=spec.get("head_effect"),
            product=spec.get("product", "PASS"),
        )
        parent_mode = "none" if break_git_parent_at == seq else None
        oid = commit_event(repo, item, parent=parent_mode)
        event_id = "mu:" + oid
        context["events"].append({"event_type": spec["event_type"], "event_id": event_id, "payload": payload})
        if "name" in spec:
            context["event_ids"][spec["name"]] = event_id
        row = registry_row(spec["event_type"])
        if row["event_class"] == "SOVEREIGN_ACCEPT" and item["predicate_product"] == "PASS":
            accepted = event_id
        if row["event_class"] == "AUTHORIZATION" and item["predicate_product"] == "PASS":
            authorization = event_id
        prev = event_id
        last_oid = oid
    assert last_oid is not None
    run(["git", "update-ref", "refs/turingos/tape_tip", last_oid], repo)
    if accepted:
        run(["git", "update-ref", "refs/turingos/accepted_head", accepted.removeprefix("mu:")], repo)
    if authorization:
        run(["git", "update-ref", "refs/turingos/authorization_head", authorization.removeprefix("mu:")], repo)
    run(["git", "bundle", "create", str(bundle), "--all"], repo)
    return bundle, context


def accepted_specs():
    return [
        {
            "event_type": "SystemConstitutionAccepted",
            "payload": {"constitution_digest": "sha256:" + "1" * 64},
        },
        {
            "event_type": "WorkCapsuleBuilt",
            "payload": {"capsule_id": "wc_test", "private_contract_hash": "sha256:" + "2" * 64},
        },
        {
            "event_type": "WorkerReceiptImported",
            "payload": {"capsule_id": "wc_test", "receipt_id": "rcp_test", "patch_hash": "sha256:" + "3" * 64},
        },
        {
            "event_type": "MacroObservationImported",
            "payload": {"capsule_id": "wc_test", "macro_id": "macro:diff:test", "diff_hash": "sha256:" + "3" * 64},
        },
        {
            "event_type": "OfficialEvaluatorEvidenceImported",
            "payload": {
                "capsule_id": "wc_test",
                "evidence_id": "ev_official_test",
                "macro_anchor_id": "macro:diff:test",
                "result": "PASS",
                "worker_receipt_id": "rcp_test",
            },
        },
        {
            "event_type": "CandidateAccepted",
            "payload": {
                "candidate_id": "cand_test",
                "capsule_id": "wc_test",
                "macro_anchor_id": "macro:diff:test",
                "official_evaluator_evidence_id": "ev_official_test",
                "worker_receipt_id": "rcp_test",
            },
        },
    ]


def test_micro_tape_auditor_replays_bundle_and_builds_reference_dag(tmp_path):
    auditor = load_auditor()
    bundle = make_bundle(tmp_path, accepted_specs())

    report = auditor.audit_bundles([bundle], tmp_path / "work")

    assert report["verdict"] == "PARTIAL"
    assert report["status_summary"]["replay_structural_integrity"] == "PASS"
    assert report["status_summary"]["constitutional_protocol_audit"] == "PARTIAL"
    assert report["aggregate"]["bundle_count"] == 1
    assert report["aggregate"]["event_count"] == 6
    run_report = report["runs"][0]
    assert run_report["replay_valid"] is True
    assert run_report["path_class"] == "accepted_path"
    assert run_report["derived_refs"]["accepted_head"] == run_report["actual_refs"]["accepted_head"]
    assert run_report["event_counts"]["CandidateAccepted"] == 1
    assert any(edge["kind"] == "official_evidence_to_accept" for edge in run_report["dag_edges"])
    assert any(step["event_type"] == "CandidateAccepted" for step in run_report["golden_path"])


def test_registry_authorization_moves_authorization_head_not_accepted_head(tmp_path):
    auditor = load_auditor()
    bundle = make_bundle(
        tmp_path,
        [
            {
                "event_type": "SystemConstitutionAccepted",
                "payload": {"constitution_digest": "sha256:" + "1" * 64},
            },
            {
                "event_type": "AtomAuthorized",
                "payload": {"atom_id": "atom:test", "approval_id": "approval:test"},
            },
        ],
    )

    run_report = auditor.audit_bundles([bundle], tmp_path / "work")["runs"][0]

    assert run_report["checks"]["registry_head_effect"] == "PASS"
    assert run_report["checks"]["authorization_head"] == "PASS"
    assert run_report["derived_refs"]["authorization_head"] == run_report["actual_refs"]["authorization_head"]
    assert run_report["derived_refs"]["accepted_head"] == run_report["events"][0]["event_id"]


def test_head_effect_disagreement_fails_closed_registry(tmp_path):
    auditor = load_auditor()
    specs = accepted_specs()
    specs[-1] = {**specs[-1], "head_effect": "PRESERVE"}
    bundle = make_bundle(tmp_path, specs)

    report = auditor.audit_bundles([bundle], tmp_path / "work")

    assert report["verdict"] == "FAIL"
    assert report["runs"][0]["checks"]["registry_head_effect"] == "FAIL"
    assert any("head_effect PRESERVE != registry ADVANCE" in p for p in report["runs"][0]["replay_problems"])


def test_official_fail_is_failed_path_not_golden_path_and_pput_zero_is_valid(tmp_path):
    auditor = load_auditor()
    bundle = make_bundle(
        tmp_path,
        [
            {
                "event_type": "SystemConstitutionAccepted",
                "payload": {"constitution_digest": "sha256:" + "1" * 64},
            },
            {"event_type": "WorkCapsuleBuilt", "payload": {"capsule_id": "wc_fail"}},
            {
                "event_type": "PPUTAccounted",
                "payload": {"capsule_id": "wc_fail", "progress": 0, "vpput_raw": "0"},
            },
            {
                "event_type": "OfficialEvaluatorEvidenceImported",
                "payload": {"capsule_id": "wc_fail", "evidence_id": "ev_fail", "result": "FAIL"},
            },
            {
                "event_type": "FailureNode",
                "payload": {"capsule_id": "wc_fail", "failure_class": "OFFICIAL_EVAL_FAIL"},
            },
        ],
    )

    run_report = auditor.audit_bundles([bundle], tmp_path / "work")["runs"][0]

    assert run_report["path_class"] == "failed_path"
    assert run_report["golden_path"] == []
    assert run_report["checks"]["economic_timing"] == "PASS"
    assert not any(f["finding"] == "failed_run_has_nonzero_pput_progress" for f in run_report["execution_findings"])


def test_market_and_pput_timing_downgrade_overall_to_partial(tmp_path):
    auditor = load_auditor()
    specs = [
        {
            "event_type": "SystemConstitutionAccepted",
            "payload": {"constitution_digest": "sha256:" + "1" * 64},
        },
        {"event_type": "WorkCapsuleBuilt", "payload": {"capsule_id": "wc_timing"}},
        {"event_type": "MarketCreated", "payload": {"market_id": "mkt_timing", "capsule_id": "wc_timing"}},
        {"event_type": "MarketSettled", "payload": {"market_id": "mkt_timing", "result": "NO"}},
        {"event_type": "RewardDistributed", "payload": {"market_id": "mkt_timing", "agent_id": "agent:test"}},
        {"event_type": "CostEvent", "payload": {"capsule_id": "wc_timing", "total_tokens": 1, "wall_time_ms": 1}},
        {"event_type": "PPUTAccounted", "payload": {"capsule_id": "wc_timing", "progress": 0, "vpput_raw": "0"}},
        {
            "event_type": "OfficialEvaluatorEvidenceImported",
            "payload": {"capsule_id": "wc_timing", "evidence_id": "ev_timing", "result": "PASS"},
        },
        {
            "event_type": "CandidateAccepted",
            "payload": {
                "candidate_id": "cand_timing",
                "capsule_id": "wc_timing",
                "official_evaluator_evidence_id": "ev_timing",
            },
        },
    ]
    bundle = make_bundle(tmp_path, specs)

    report = auditor.audit_bundles([bundle], tmp_path / "work")

    assert report["verdict"] == "PARTIAL"
    assert report["status_summary"]["market_accounting_correctness"] == "WARN"
    assert report["status_summary"]["economic_timing"] == "WARN"
    findings = {item["finding"] for item in report["runs"][0]["execution_findings"]}
    assert "market_settled_before_terminal_evidence" in findings
    assert "pput_final_accounting_missing_after_accept" in findings

    strict_report = auditor.audit_bundles(
        [bundle],
        tmp_path / "work_strict",
        strict_vpput=True,
        strict_terminal_market=True,
        require_authorization_head=True,
    )
    assert strict_report["verdict"] == "FAIL"
    assert "strict_vpput" in {item["id"] for item in strict_report["strict_findings"]}
    assert "strict_terminal_market" in {item["id"] for item in strict_report["strict_findings"]}
    assert "require_authorization_head" in {item["id"] for item in strict_report["strict_findings"]}


def test_repeated_event_types_are_rendered_as_distinct_dag_nodes(tmp_path):
    auditor = load_auditor()
    specs = accepted_specs()
    specs.insert(
        4,
        {
            "event_type": "OfficialEvaluatorEvidenceImported",
            "payload": {"capsule_id": "wc_test", "evidence_id": "ev_failed_first", "result": "FAIL"},
        },
    )
    bundle = make_bundle(tmp_path, specs)

    report = auditor.audit_bundles([bundle], tmp_path / "work")
    run_report = report["runs"][0]

    official_nodes = [event for event in run_report["events"] if event["event_type"] == "OfficialEvaluatorEvidenceImported"]
    assert len(official_nodes) == 2
    assert len({event["node_id"] for event in official_nodes}) == 2
    markdown_lines = auditor.render_tree_for_run(run_report)
    assert sum("OfficialEvaluatorEvidenceImported" in line for line in markdown_lines) == 2


def test_git_parent_mismatch_fails_even_if_payload_prev_claims_ok(tmp_path):
    auditor = load_auditor()
    bundle = make_bundle(tmp_path, accepted_specs(), break_git_parent_at=2)

    report = auditor.audit_bundles([bundle], tmp_path / "work")

    assert report["verdict"] == "FAIL"
    assert report["runs"][0]["checks"]["git_topology"] == "FAIL"
    assert any("commit parent count" in p or "commit parent" in p for p in report["runs"][0]["replay_problems"])


def test_terminal_golden_path_uses_accepted_head_not_first_candidate_accept(tmp_path):
    auditor = load_auditor()
    specs = accepted_specs()
    specs[4]["name"] = "official_first"
    specs[5]["name"] = "accept_first"
    specs.extend(
        [
            {
                "event_type": "OfficialEvaluatorEvidenceImported",
                "name": "official_terminal",
                "payload": {
                    "capsule_id": "wc_test",
                    "evidence_id": "ev_official_terminal",
                    "macro_anchor_id": "macro:diff:test",
                    "result": "PASS",
                    "worker_receipt_id": "rcp_test",
                },
            },
            {
                "event_type": "CandidateAccepted",
                "name": "accept_terminal",
                "payload": {
                    "candidate_id": "cand_test_terminal",
                    "capsule_id": "wc_test",
                    "macro_anchor_id": "macro:diff:test",
                    "official_evaluator_evidence_id": "ev_official_terminal",
                    "worker_receipt_id": "rcp_test",
                },
            },
        ]
    )
    bundle, context = make_bundle_with_context(tmp_path, specs)

    run_report = auditor.audit_bundles([bundle], tmp_path / "work")["runs"][0]

    assert context["event_ids"]["accept_first"] != context["event_ids"]["accept_terminal"]
    assert run_report["actual_refs"]["accepted_head"] == context["event_ids"]["accept_terminal"]
    assert run_report["first_candidate_accepted"] == context["event_ids"]["accept_first"]
    assert run_report["terminal_candidate_accepted"] == context["event_ids"]["accept_terminal"]
    assert run_report["golden_path_basis"] == "terminal_accepted_head"
    assert run_report["golden_path"][-1]["event_id"] == context["event_ids"]["accept_terminal"]
    assert run_report["checks"]["terminal_golden_path_anchors_to_accepted_head"] == "PASS"


def test_terminal_market_reward_and_final_pput_clear_economic_warnings(tmp_path):
    auditor = load_auditor()
    specs = [
        {
            "event_type": "SystemConstitutionAccepted",
            "payload": {"constitution_digest": "sha256:" + "1" * 64},
        },
        {"event_type": "WorkCapsuleBuilt", "payload": {"capsule_id": "wc_terminal"}},
        {"event_type": "WorkerReceiptImported", "payload": {"capsule_id": "wc_terminal", "receipt_id": "rcp_terminal"}},
        {"event_type": "MacroObservationImported", "payload": {"capsule_id": "wc_terminal", "macro_id": "macro:terminal"}},
        {"event_type": "CostEvent", "payload": {"capsule_id": "wc_terminal", "total_tokens": 10, "wall_time_ms": 5}},
        {"event_type": "PPUTAccounted", "payload": {"capsule_id": "wc_terminal", "accounting_stage": "progress", "progress": 0, "vpput_raw": "0"}},
        {"event_type": "MarketCreated", "payload": {"market_id": "mkt_terminal", "capsule_id": "wc_terminal"}},
        {
            "event_type": "OfficialEvaluatorEvidenceImported",
            "name": "official_terminal",
            "payload": {"capsule_id": "wc_terminal", "evidence_id": "ev_terminal", "result": "PASS"},
        },
        {
            "event_type": "CandidateAccepted",
            "name": "accept_terminal",
            "payload": {
                "candidate_id": "cand_terminal",
                "capsule_id": "wc_terminal",
                "official_evaluator_evidence_id": "ev_terminal",
            },
        },
        {
            "event_type": "MarketSettled",
            "name": "market_terminal",
            "payload": lambda ctx: {
                "market_id": "mkt_terminal",
                "result": "YES",
                "settlement_basis_event_id": ctx["event_ids"]["official_terminal"],
                "terminal_event_id": ctx["event_ids"]["accept_terminal"],
                "is_terminal": True,
                "price_not_truth_ack": True,
            },
        },
        {
            "event_type": "RewardDistributed",
            "payload": lambda ctx: {
                "market_id": "mkt_terminal",
                "agent_id": "worker:sha256:" + "1" * 64,
                "reward_coin": "1",
                "slash_coin": "0",
                "reason": "PREDICATE_SETTLEMENT",
                "settlement_event_id": ctx["event_ids"]["market_terminal"],
            },
        },
        {
            "event_type": "PPUTAccounted",
            "payload": lambda ctx: {
                "capsule_id": "wc_terminal",
                "accounting_stage": "final",
                "progress": 1,
                "vpput_raw": "0.02",
                "basis_event_id": ctx["event_ids"]["official_terminal"],
                "terminal_event_id": ctx["event_ids"]["accept_terminal"],
            },
        },
    ]
    bundle, _ = make_bundle_with_context(tmp_path, specs)

    report = auditor.audit_bundles([bundle], tmp_path / "work")
    run_report = report["runs"][0]

    assert run_report["checks"]["economic_timing"] == "PASS"
    assert run_report["checks"]["market_accounting_correctness"] == "PASS"
    assert run_report["checks"]["vpput_accounting"] == "PASS"
    assert run_report["checks"]["accepted_final_progress_one"] == "PASS"
    assert report["status_summary"]["economic_timing"] == "PASS"
