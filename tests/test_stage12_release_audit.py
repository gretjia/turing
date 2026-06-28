import importlib.util
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def stage12_tasks(count: int = 20):
    return [
        {
            "instance_id": f"stage12_case_{index + 1:02d}",
            "repo": "django/django",
            "base_commit": "58c1acb1d6054dfec29d0f30b1033bae6ef62aec",
            "problem_statement": f"Stage12 release-audit task {index + 1}",
        }
        for index in range(count)
    ]


def write_manifest(root: Path, tasks: list[dict]):
    root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_id": "turingos.stage12.task_manifest.v1",
        "stage": "Stage12",
        "task_count": len(tasks),
        "instance_ids": [task["instance_id"] for task in tasks],
        "frozen_before_run": True,
    }
    (root / "task_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def make_stage12_like_coverage(tmp_path: Path, *, count: int = 20, budget_exhausted_last: bool = False):
    runner = load_module("runner", REPO / "tools" / "bench" / "run_mini_swe_bench_substrate_smoke.py")
    tape = load_module("tape", REPO / "tools" / "bench" / "audit_micro_tape_decision_dag.py")
    out_dir = tmp_path / "stage12"
    tasks = stage12_tasks(count)
    runs = [
        build_stage12_release_bundle(out_dir, task, index, solved=not (budget_exhausted_last and index == count - 1))
        for index, task in enumerate(tasks)
    ]
    coverage = {
        "schema_id": "Stage12LoopUntilPassScaleManifest.v1",
        "run_id": "stage12_20task_loop_until_pass",
        "truth_source": "fresh_micro_tape_bundles",
        "scientific_status": "STAGE12_20TASK_SCALE_PROTOCOL_EVIDENCE_NOT_STATISTICAL_CLAIM",
        "sample_size": len(runs),
        "turingos_arm_runs": runs,
    }
    root = tmp_path / "stage12_root"
    write_manifest(root, tasks)
    coverage_path = root / "turingos" / "substrate_coverage.json"
    coverage_path.parent.mkdir(parents=True, exist_ok=True)
    coverage_path.write_text(json.dumps(coverage, indent=2, sort_keys=True) + "\n")
    bundles = [Path(run["micro_tape_bundle"]) for run in runs]
    strict_summary = tape.audit_bundles(
        bundles,
        tmp_path / "strict_stage12_release",
        strict_vpput=True,
        strict_terminal_market=True,
        require_authorization_head=True,
    )
    strict_path = root / "micro_tape_audit_strict" / "micro_tape_decision_dag_audit.json"
    strict_path.parent.mkdir(parents=True, exist_ok=True)
    strict_path.write_text(json.dumps(strict_summary, indent=2, sort_keys=True) + "\n")
    return root, coverage_path, strict_path


def build_stage12_release_bundle(out_dir: Path, task: dict, index: int, *, solved: bool) -> dict:
    runner = load_module("runner", REPO / "tools" / "bench" / "run_mini_swe_bench_substrate_smoke.py")
    tape = load_module("tape", REPO / "tools" / "bench" / "audit_micro_tape_decision_dag.py")
    registry = tape.load_event_registry()
    instance_id = task["instance_id"]
    instance_dir = out_dir / "turingos" / "instances" / instance_id
    repo = instance_dir / "micro.git"
    bundle = instance_dir / "micro_tape.bundle"
    runner.init_micro_git(repo)
    state = runner.stage6_base_state()
    short = f"{index + 1:02d}"
    worker_id = "worker:sha256:" + ("a" * 62) + f"{index % 10}{index % 10}"
    atom_id = f"atom_stage12_{short}"
    capsule1 = f"wc_stage12_{short}_attempt1"
    capsule2 = f"wc_stage12_{short}_attempt2"
    receipt1 = f"rcp_stage12_{short}_attempt1"
    receipt2 = f"rcp_stage12_{short}_attempt2"
    macro1 = f"macro:diff:stage12:{short}:attempt1"
    macro2 = f"macro:diff:stage12:{short}:attempt2"
    candidate_id = f"cand_stage12_{short}"
    run_id = f"run_stage12_{short}"
    market_id = f"mkt_stage12_{short}"
    rule_id = f"br_stage12_{short}"
    cost1 = 100 + index
    cost2 = 200 + index
    wall1 = 10 + index
    wall2 = 20 + index

    def append(event_type: str, payload: dict, writer_id: str, **kwargs):
        return runner.append_stage6_event(
            repo=repo,
            state=state,
            registry=registry,
            canonical_payload_digest=tape.canonical_payload_digest,
            event_type=event_type,
            payload=payload,
            writer_id=writer_id,
            **kwargs,
        )

    append("SystemConstitutionAccepted", {"constitution_digest": runner.digest_text("stage12 constitution")}, "writer:bootstrap")
    append(
        "GoalStateProposed",
        {
            "goal_id": f"goal_stage12_{short}",
            "objective": "Stage12 scale protocol task",
            "task_source": "verified_mini_20task",
        },
        "writer:goal",
    )
    append(
        "AtomAuthorized",
        {
            "atom_id": atom_id,
            "approval_id": f"ap_atom_stage12_{short}",
            "authority_kind": "test_local_authority_no_credentials",
            "signature_route": "test_local_authority",
        },
        "writer:test-local-authority",
    )
    append(
        "WorkerDispatchAuthorized",
        {
            "capsule_id": capsule1,
            "worker_id": worker_id,
            "approval_id": f"ap_dispatch_stage12_{short}_attempt1",
            "authority_kind": "test_local_authority_no_credentials",
            "signature_route": "test_local_authority",
        },
        "writer:test-local-authority",
    )
    append(
        "WorkCapsuleBuilt",
        {
            "capsule_id": capsule1,
            "private_contract_hash": runner.digest_text(capsule1 + ":private"),
            "acceptance_commands": ["stage12.official.eval"],
            "attempt_index": 1,
        },
        "writer:capsule",
    )
    append(
        "WorkerReceiptImported",
        {
            "receipt_id": receipt1,
            "capsule_id": capsule1,
            "worker_id": worker_id,
            "exit_code": 1,
            "stdout_hash": runner.digest_text(instance_id + ":a1:stdout"),
            "stderr_hash": runner.digest_text(instance_id + ":a1:stderr"),
            "done_json_hash": runner.digest_text(instance_id + ":a1:done"),
            "credential_material_absent": True,
            "manual_patch": False,
            "micro_refs_moved": False,
            "patch_hash": runner.digest_text(instance_id + ":a1:patch"),
        },
        "writer:receipt",
    )
    append(
        "MacroObservationImported",
        {"macro_id": macro1, "capsule_id": capsule1, "diff_hash": runner.digest_text(instance_id + ":a1:patch")},
        "writer:macro",
    )
    append(
        "CostEvent",
        {
            "schema_id": "cost_event.v1",
            "run_id": run_id,
            "problem_id": instance_id,
            "agent_id": worker_id,
            "branch_id": f"branch_stage12_{short}_attempt1",
            "capsule_id": capsule1,
            "prompt_tokens": 40,
            "completion_tokens": 40,
            "tool_tokens": 10,
            "tool_stdout_tokens": 10 + index,
            "total_tokens": cost1,
            "wall_time_ms": wall1,
            "counted_in_total": True,
        },
        "writer:pput",
    )
    official_fail = append(
        "OfficialEvaluatorEvidenceImported",
        {
            "schema_id": "official_evaluator_evidence_imported.v1",
            "evidence_id": f"ev_stage12_{short}_fail",
            "instance_id": instance_id,
            "capsule_id": capsule1,
            "macro_anchor_id": macro1,
            "worker_receipt_id": receipt1,
            "candidate_patch_hash": runner.digest_text(instance_id + ":a1:patch"),
            "test_patch_hash": runner.digest_text(instance_id + ":test"),
            "apply_candidate_result": "PASS",
            "apply_test_patch_result": "PASS",
            "fail_to_pass_labels": [],
            "target_test_exit_code": 1,
            "target_test_result": "FAIL",
            "stdout_hash": runner.digest_text(instance_id + ":a1:official-stdout"),
            "stderr_hash": runner.digest_text(instance_id + ":a1:official-stderr"),
            "result": "FAIL",
            "failure_class": "SEMANTIC_FAIL",
            "forbidden_test_edit_detected": False,
            "forbidden_test_edit_paths": [],
            "truth_source": "official_evaluator_macro_evidence",
        },
        "writer:official-evaluator",
        name="official_fail",
    )
    failure = append(
        "FailureNode",
        {
            "capsule_id": capsule1,
            "candidate_id": candidate_id,
            "failure_class": "SEMANTIC_FAIL",
            "official_evaluator_evidence_id": f"ev_stage12_{short}_fail",
            "classifier_decision": {
                "failure_class": "SEMANTIC_FAIL",
                "observer_derived_failure_class": True,
                "classifier_inputs": {
                    "official_evaluator_result": "FAIL",
                    "command_result": "semantic_mismatch",
                    "macro_observation_kind": "patch_failed",
                },
            },
        },
        "writer:predicate",
        product="NOT_RUN",
        name="failure",
    )
    append(
        "PPUTAccounted",
        {
            "schema_id": "pput_accounted.v1",
            "run_id": run_id,
            "problem_id": instance_id,
            "accounting_stage": "progress",
            "basis_event_id": official_fail["event_id"],
            "terminal_event_id": failure["event_id"],
            "total_run_token_count": cost1,
            "total_wall_time_ms": wall1,
            "progress": 0,
            "vpput_raw": "0",
            "hidden_from_worker_prompt": True,
        },
        "writer:pput",
    )
    certificate = append(
        "FailureCertificate",
        {
            "certificate_id": f"fc_stage12_{short}",
            "source_failure_node_id": failure["event_id"],
            "failure_class": "SEMANTIC_FAIL",
            "abstract_pattern": "The first patch did not satisfy target evaluator behavior.",
            "broadcast_rule_candidate": {
                "rule_id": rule_id,
                "candidate_only": True,
                "source_failure_nodes": [failure["event_id"]],
                "failure_class": "SEMANTIC_FAIL",
                "abstract_pattern": "Patch must target observed runtime behavior.",
                "new_instruction": "Use evaluator evidence to narrow the production-code change.",
                "raw_log_text_absent": True,
                "hidden_predicates_absent": True,
            },
        },
        "writer:failure-taxonomy",
    )
    broadcast = append(
        "BroadcastRuleActivated",
        {
            "rule_id": rule_id,
            "source_failure_nodes": [failure["event_id"]],
            "failure_certificate_event_id": certificate["event_id"],
            "failure_class": "SEMANTIC_FAIL",
            "abstract_pattern": "Patch must target observed runtime behavior.",
            "new_instruction": "Use evaluator evidence to narrow the production-code change.",
            "recipients": ["future_capsule"],
            "hidden_details_removed": True,
            "raw_log_text_absent": True,
            "hidden_predicates_absent": True,
            "pput_or_heldout_details_absent": True,
        },
        "writer:failure-memory",
    )
    retry = append(
        "RetryAuthorized",
        {
            "retry_id": f"retry_stage12_{short}",
            "capsule_id": capsule2,
            "source_failure_node_id": failure["event_id"],
            "broadcast_rule_event_id": broadcast["event_id"],
            "retry_decision_source": "tape_reducer_or_policy",
            "approval_id": f"ap_retry_stage12_{short}",
            "authority_kind": "test_local_authority_no_credentials",
            "signature_route": "test_local_authority",
            "human_intervention_count": 0,
        },
        "writer:test-local-authority",
    )
    append(
        "WorkerDispatchAuthorized",
        {
            "capsule_id": capsule2,
            "worker_id": worker_id,
            "approval_id": f"ap_dispatch_stage12_{short}_attempt2",
            "authority_kind": "test_local_authority_no_credentials",
            "signature_route": "test_local_authority",
            "retry_authorization_event_id": retry["event_id"],
        },
        "writer:test-local-authority",
    )
    append(
        "WorkCapsuleBuilt",
        {
            "capsule_id": capsule2,
            "private_contract_hash": runner.digest_text(capsule2 + ":private"),
            "acceptance_commands": ["stage12.official.eval"],
            "attempt_index": 2,
            "source_failure_nodes": [failure["event_id"]],
            "consumed_broadcast_rule_ids": [rule_id],
            "injected_broadcast_rule_ids": [rule_id],
            "broadcast_rule_event_id": broadcast["event_id"],
            "raw_log_text_absent": True,
            "hidden_predicates_absent": True,
        },
        "writer:capsule",
        name="second_capsule",
    )

    terminal_event = failure
    official_basis = official_fail
    total_tokens = cost1
    total_wall = wall1
    if solved:
        total_tokens += cost2
        total_wall += wall2
        append(
            "CostEvent",
            {
                "schema_id": "cost_event.v1",
                "run_id": run_id,
                "problem_id": instance_id,
                "agent_id": worker_id,
                "branch_id": f"branch_stage12_{short}_attempt2",
                "capsule_id": capsule2,
                "prompt_tokens": 90,
                "completion_tokens": 70,
                "tool_tokens": 20,
                "tool_stdout_tokens": 20 + index,
                "total_tokens": cost2,
                "wall_time_ms": wall2,
                "counted_in_total": True,
            },
            "writer:pput",
        )
        append(
            "WorkerReceiptImported",
            {
                "receipt_id": receipt2,
                "capsule_id": capsule2,
                "worker_id": worker_id,
                "exit_code": 0,
                "stdout_hash": runner.digest_text(instance_id + ":a2:stdout"),
                "stderr_hash": runner.digest_text(instance_id + ":a2:stderr"),
                "done_json_hash": runner.digest_text(instance_id + ":a2:done"),
                "credential_material_absent": True,
                "manual_patch": False,
                "micro_refs_moved": False,
                "patch_hash": runner.digest_text(instance_id + ":a2:patch"),
            },
            "writer:receipt",
        )
        append(
            "MacroObservationImported",
            {"macro_id": macro2, "capsule_id": capsule2, "diff_hash": runner.digest_text(instance_id + ":a2:patch")},
            "writer:macro",
        )
        official_basis = append(
            "OfficialEvaluatorEvidenceImported",
            {
                "schema_id": "official_evaluator_evidence_imported.v1",
                "evidence_id": f"ev_stage12_{short}_pass",
                "instance_id": instance_id,
                "capsule_id": capsule2,
                "macro_anchor_id": macro2,
                "worker_receipt_id": receipt2,
                "candidate_patch_hash": runner.digest_text(instance_id + ":a2:patch"),
                "test_patch_hash": runner.digest_text(instance_id + ":test"),
                "apply_candidate_result": "PASS",
                "apply_test_patch_result": "PASS",
                "fail_to_pass_labels": [],
                "target_test_exit_code": 0,
                "target_test_result": "PASS",
                "stdout_hash": runner.digest_text(instance_id + ":a2:official-stdout"),
                "stderr_hash": runner.digest_text(instance_id + ":a2:official-stderr"),
                "result": "PASS",
                "failure_class": None,
                "forbidden_test_edit_detected": False,
                "forbidden_test_edit_paths": [],
                "truth_source": "official_evaluator_macro_evidence",
            },
            "writer:official-evaluator",
        )
        terminal_event = append(
            "CandidateAccepted",
            {
                "candidate_id": candidate_id,
                "capsule_id": capsule2,
                "macro_anchor_id": macro2,
                "worker_receipt_id": receipt2,
                "official_evaluator_evidence_id": f"ev_stage12_{short}_pass",
                "consumed_broadcast_rule_event_id": broadcast["event_id"],
            },
            "writer:predicate",
        )
    else:
        terminal_event = append(
            "BudgetExhausted",
            {
                "budget_event_id": f"budget_exhausted_stage12_{short}",
                "capsule_id": capsule2,
                "source_failure_node_id": failure["event_id"],
                "reason": "retry budget exhausted before official pass",
            },
            "writer:budget",
            product="NOT_RUN",
        )

    settlement = append(
        "MarketSettled",
        {
            "schema_id": "market_settled.v1",
            "market_id": market_id,
            "result": "YES" if solved else "NO",
            "settlement_basis_event_id": official_basis["event_id"],
            "basis_kind": "official_eval",
            "terminal_event_id": terminal_event["event_id"],
            "is_terminal": True,
            "price_not_truth_ack": True,
        },
        "writer:market",
    )
    append(
        "RewardDistributed",
        {
            "schema_id": "reward_distributed.v1",
            "market_id": market_id,
            "agent_id": worker_id,
            "reward_coin": "1" if solved else "0",
            "slash_coin": "0" if solved else "1",
            "reason": "PREDICATE_SETTLEMENT" if solved else "BUDGET_EXHAUSTED",
            "settlement_event_id": settlement["event_id"],
        },
        "writer:market",
    )
    append(
        "PPUTAccounted",
        {
            "schema_id": "pput_accounted.v1",
            "run_id": run_id,
            "problem_id": instance_id,
            "solved": solved,
            "verified": solved,
            "accounting_stage": "final",
            "basis_event_id": official_basis["event_id"],
            "terminal_event_id": terminal_event["event_id"],
            "golden_path_token_count": total_tokens if solved else 0,
            "total_run_token_count": total_tokens,
            "total_wall_time_ms": total_wall,
            "progress": 1 if solved else 0,
            "vpput_raw": runner.stage6_vpput(1 if solved else 0, total_tokens, total_wall),
            "failed_branch_count": 1,
            "hidden_from_worker_prompt": True,
        },
        "writer:pput",
    )
    proc = runner.run_cmd(["git", "bundle", "create", str(bundle.resolve()), "--all"], cwd=repo, timeout=120)
    assert proc.returncode == 0, proc.stderr
    bundle_hash = "sha256:" + __import__("hashlib").sha256(bundle.read_bytes()).hexdigest()
    loop = {
        "human_intervention_count": 0,
        "manual_patch_count": 0,
        "manual_approval_count": 0,
        "manual_rerun_selection_count": 0,
        "fallback_to_auto_authorization": False,
        "attempts_total": 2,
        "failed_attempts_before_accept": 1,
        "first_failed_attempt_index": 1,
        "accepted_attempt_index": 2 if solved else None,
        "budget_exhausted": not solved,
        "retry_decision_source": "tape_reducer_or_policy",
        "retry_policy_event_id": retry["event_id"],
        "first_failure_event_id": failure["event_id"],
        "failure_certificate_event_id": certificate["event_id"],
        "broadcast_rule_activated_event_id": broadcast["event_id"],
        "second_attempt_capsule_event_id": state["event_ids"]["second_capsule"],
        "terminal_candidate_accepted_event_id": terminal_event["event_id"] if solved else None,
        "accepted_head": state["accepted_head"] if solved else None,
        "verified_from_micro_tape_bundle_only": True,
    }
    return {
        "instance_id": instance_id,
        "authorization_mode": "required",
        "authority_provider": "test-local",
        "authorization_head": state["authorization_head"],
        "micro_tape_bundle": str(bundle),
        "micro_tape_bundle_sha256": bundle_hash,
        "loop_until_pass": loop,
        "basis": "stage12_real_loop_attempt",
    }


def test_stage12_release_accepts_20_valid_loop_runs(tmp_path):
    audit = load_module("stage12", REPO / "tools" / "bench" / "audit_stage12_release.py")
    root, coverage, strict = make_stage12_like_coverage(tmp_path)

    report = audit.audit_stage12(root=root, coverage_path=coverage, strict_audit_path=strict)

    assert report["status"] == "PASS"
    assert report["local_release_candidate"] is True
    assert report["run_count"] == 20
    assert report["solved_count"] == 20
    assert report["unsolved_count"] == 0
    assert report["external_exact_sha_audit_required"] is True


def test_stage12_release_accepts_budget_terminal_unsolved_with_progress_zero(tmp_path):
    audit = load_module("stage12", REPO / "tools" / "bench" / "audit_stage12_release.py")
    root, coverage, strict = make_stage12_like_coverage(tmp_path, budget_exhausted_last=True)

    report = audit.audit_stage12(root=root, coverage_path=coverage, strict_audit_path=strict)

    assert report["status"] == "PASS"
    assert report["solved_count"] == 19
    assert report["unsolved_count"] == 1
    assert report["runs"][-1]["terminal_progress_zero"] is True


def test_stage12_release_rejects_less_than_20_runs(tmp_path):
    audit = load_module("stage12", REPO / "tools" / "bench" / "audit_stage12_release.py")
    root, coverage, strict = make_stage12_like_coverage(tmp_path, count=19)

    report = audit.audit_stage12(root=root, coverage_path=coverage, strict_audit_path=strict)

    assert report["status"] == "FAIL"
    assert "Stage12 requires exactly 20 runs" in report["problems"]


def test_stage12_release_rejects_fixture_scientific_status(tmp_path):
    audit = load_module("stage12", REPO / "tools" / "bench" / "audit_stage12_release.py")
    root, coverage, strict = make_stage12_like_coverage(tmp_path)
    data = json.loads(coverage.read_text())
    data["scientific_status"] = "LOOP_UNTIL_PASS_FIXTURE_NOT_SOLVE_RATE"
    coverage.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

    report = audit.audit_stage12(root=root, coverage_path=coverage, strict_audit_path=strict)

    assert report["status"] == "FAIL"
    assert "fixture coverage cannot release Stage12" in report["problems"]


def test_stage12_release_rejects_affirmative_overclaim_status(tmp_path):
    audit = load_module("stage12", REPO / "tools" / "bench" / "audit_stage12_release.py")
    root, coverage, strict = make_stage12_like_coverage(tmp_path)
    data = json.loads(coverage.read_text())
    data["scientific_status"] = "WE_MAKE_STATISTICAL_CLAIM_AND_FULL_SCORE_CLAIM"
    coverage.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

    report = audit.audit_stage12(root=root, coverage_path=coverage, strict_audit_path=strict)

    assert report["status"] == "FAIL"
    assert "scientific_status must be STAGE12_20TASK_SCALE_PROTOCOL_EVIDENCE_NOT_STATISTICAL_CLAIM" in report["problems"]


def test_stage12_release_rejects_relabelled_stage11_fixture_payloads(tmp_path):
    audit = load_module("stage12", REPO / "tools" / "bench" / "audit_stage12_release.py")
    runner = load_module("runner", REPO / "tools" / "bench" / "run_mini_swe_bench_substrate_smoke.py")
    tape = load_module("tape", REPO / "tools" / "bench" / "audit_micro_tape_decision_dag.py")
    tasks = stage12_tasks(20)
    generated = runner.generate_stage11_loop_until_pass_fixture(tmp_path / "stage11_relabelled", tasks)
    runs = generated["turingos_arm_runs"]
    for run in runs:
        run["basis"] = "stage12_real_loop_attempt"
    coverage = {
        "schema_id": "Stage12LoopUntilPassScaleManifest.v1",
        "run_id": "stage12_20task_loop_until_pass",
        "truth_source": "fresh_micro_tape_bundles",
        "scientific_status": "STAGE12_20TASK_SCALE_PROTOCOL_EVIDENCE_NOT_STATISTICAL_CLAIM",
        "sample_size": 20,
        "turingos_arm_runs": runs,
    }
    root = tmp_path / "stage12_root"
    write_manifest(root, tasks)
    coverage_path = root / "turingos" / "substrate_coverage.json"
    coverage_path.parent.mkdir(parents=True, exist_ok=True)
    coverage_path.write_text(json.dumps(coverage, indent=2, sort_keys=True) + "\n")
    strict = tape.audit_bundles(
        [Path(run["micro_tape_bundle"]) for run in runs],
        tmp_path / "strict_relabelled",
        strict_vpput=True,
        strict_terminal_market=True,
        require_authorization_head=True,
    )
    strict_path = root / "micro_tape_audit_strict" / "micro_tape_decision_dag_audit.json"
    strict_path.parent.mkdir(parents=True, exist_ok=True)
    strict_path.write_text(json.dumps(strict, indent=2, sort_keys=True) + "\n")

    report = audit.audit_stage12(root=root, coverage_path=coverage_path, strict_audit_path=strict_path)

    assert report["status"] == "FAIL"
    assert any("bundle payload contains fixture markers" in problem for problem in report["problems"])


def test_stage12_release_rejects_non_pass_strict_audit(tmp_path):
    audit = load_module("stage12", REPO / "tools" / "bench" / "audit_stage12_release.py")
    root, coverage, strict = make_stage12_like_coverage(tmp_path)
    data = json.loads(strict.read_text())
    data["status_summary"]["authorization_head"] = "LEGACY_MISSING"
    strict.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

    report = audit.audit_stage12(root=root, coverage_path=coverage, strict_audit_path=strict)

    assert report["status"] == "FAIL"
    assert "strict audit authorization_head must be PASS" in report["problems"]


def test_stage12_release_rejects_unbound_strict_audit(tmp_path):
    audit = load_module("stage12", REPO / "tools" / "bench" / "audit_stage12_release.py")
    tape = load_module("tape", REPO / "tools" / "bench" / "audit_micro_tape_decision_dag.py")
    root, coverage, strict = make_stage12_like_coverage(tmp_path)
    data = json.loads(coverage.read_text())
    unrelated = tape.audit_bundles(
        [Path(data["turingos_arm_runs"][0]["micro_tape_bundle"])],
        tmp_path / "strict_unrelated",
        strict_vpput=True,
        strict_terminal_market=True,
        require_authorization_head=True,
    )
    strict.write_text(json.dumps(unrelated, indent=2, sort_keys=True) + "\n")

    report = audit.audit_stage12(root=root, coverage_path=coverage, strict_audit_path=strict)

    assert report["status"] == "FAIL"
    assert "supplied strict audit bundle_hashes do not match coverage bundles" in report["problems"]


def test_stage12_release_rejects_manual_intervention(tmp_path):
    audit = load_module("stage12", REPO / "tools" / "bench" / "audit_stage12_release.py")
    root, coverage, strict = make_stage12_like_coverage(tmp_path)
    data = json.loads(coverage.read_text())
    data["turingos_arm_runs"][0]["loop_until_pass"]["manual_patch_count"] = 1
    coverage.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

    report = audit.audit_stage12(root=root, coverage_path=coverage, strict_audit_path=strict)

    assert report["status"] == "FAIL"
    assert any("manual_patch_count" in problem for problem in report["problems"])


def test_stage12_release_cli_writes_report(tmp_path):
    root, coverage, strict = make_stage12_like_coverage(tmp_path)
    out = root / "stage12_release_audit.json"

    import subprocess

    subprocess.run(
        [
            "python3",
            "tools/bench/audit_stage12_release.py",
            "--root",
            str(root),
            "--coverage",
            str(coverage),
            "--strict-audit",
            str(strict),
            "--out",
            str(out),
        ],
        cwd=REPO,
        check=True,
    )

    report = json.loads(out.read_text())
    assert report["status"] == "PASS"
    assert report["run_count"] == 20
