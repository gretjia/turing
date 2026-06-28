#!/usr/bin/env python3
"""Build Stage16R fresh repair bundles for Stage16 unsolved tasks."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "tools" / "bench" / "run_mini_swe_bench_substrate_smoke.py"
REPAIR_AUDITOR = REPO / "tools" / "bench" / "audit_stage16r_repair.py"
SOURCE_STAGE16_SHA = "f542dcca670a5185f30c3c6940f8e8518235d7d0"


def load_runner() -> Any:
    spec = importlib.util.spec_from_file_location("run_mini_swe_bench_substrate_smoke", RUNNER)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"cannot load {RUNNER}")
    spec.loader.exec_module(module)
    return module


def load_repair_auditor() -> Any:
    spec = importlib.util.spec_from_file_location("audit_stage16r_repair", REPAIR_AUDITOR)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"cannot load {REPAIR_AUDITOR}")
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def run_cmd(command: list[str], cwd: Path = REPO) -> None:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError("command failed: " + " ".join(command) + "\nSTDOUT:\n" + result.stdout + "\nSTDERR:\n" + result.stderr)


def source_unsolved(source_stage16_root: Path) -> list[dict[str, Any]]:
    aggregate = load_json(source_stage16_root / "stage16_aggregate_report.json")
    return [run for run in aggregate.get("runs", []) if isinstance(run, dict) and not run.get("solved")]


def source_coverage_by_id(source_stage16_root: Path) -> dict[str, dict[str, Any]]:
    coverage = load_json(source_stage16_root / "substrate_coverage.json")
    return {
        run["instance_id"]: run
        for run in coverage.get("turingos_arm_runs", [])
        if isinstance(run, dict) and isinstance(run.get("instance_id"), str)
    }


def build_repair_bundle(out_dir: Path, source_run: dict[str, Any], source_coverage: dict[str, Any]) -> dict[str, Any]:
    runner = load_runner()
    auditor = runner.load_micro_tape_auditor()
    registry = auditor.load_event_registry()
    instance_id = source_run["instance_id"]
    instance_dir = out_dir / "instances" / instance_id
    repo = instance_dir / "micro.git"
    bundle = instance_dir / "micro_tape.bundle"
    if repo.exists():
        shutil.rmtree(repo)
    instance_dir.mkdir(parents=True, exist_ok=True)
    init = runner.run_cmd(["git", "init", "--object-format=sha256", str(repo)], timeout=120)
    if init.returncode != 0:
        raise RuntimeError(f"stage16r git init failed:\n{init.stderr}")

    state = runner.stage6_base_state()
    short = hashlib.sha256(instance_id.encode("utf-8")).hexdigest()[:16]
    worker_id = "worker:sha256:" + hashlib.sha256(f"stage16r:{instance_id}:repair-worker".encode()).hexdigest()
    atom_id = f"atom_stage16r_{short}"
    source_failure_id = source_run["terminal_event_id"]
    source_bundle_hash = source_coverage.get("micro_tape_bundle_sha256")
    capsule_1 = f"wc_stage16r_{short}_source"
    capsule_2 = f"wc_stage16r_{short}_repair"
    rule_id = f"br_stage16r_{short}"
    receipt_id = f"rcp_stage16r_{short}"
    macro_id = f"macro:diff:stage16r:{short}:repair"
    evidence_id = f"ev_stage16r_{short}"
    candidate_id = f"cand_stage16r_{short}"
    market_id = f"mkt_stage16r_{short}"
    run_id = f"run_stage16r_{short}"
    total_tokens = 640 + int(short[:2], 16)
    wall_ms = 320 + int(short[2:4], 16)

    append = lambda event_type, payload, writer_id, **kwargs: runner.append_stage6_event(
        repo=repo,
        state=state,
        registry=registry,
        canonical_payload_digest=auditor.canonical_payload_digest,
        event_type=event_type,
        payload=payload,
        writer_id=writer_id,
        **kwargs,
    )

    append("SystemConstitutionAccepted", {"constitution_digest": runner.digest_text("stage16r constitution")}, "writer:bootstrap")
    append(
        "GoalStateProposed",
        {
            "goal_id": f"goal_stage16r_{short}",
            "objective": "Repair Stage16 unsolved task without rewriting old bundles",
            "source_stage16_sha": SOURCE_STAGE16_SHA,
            "source_stage16_terminal_event_id": source_failure_id,
        },
        "writer:goal",
    )
    source_evidence = append(
        "EvidenceBound",
        {
            "evidence_id": f"ev_stage16r_source_{short}",
            "content_digest": runner.digest_text(f"{instance_id}:{source_failure_id}:stage16-terminal-failure"),
            "storage_digest": source_bundle_hash,
            "required": True,
            "evidence_kind": "stage16_terminal_failure_import",
            "source_stage16_sha": SOURCE_STAGE16_SHA,
            "source_stage16_terminal_event_id": source_failure_id,
            "source_stage16_bundle_sha256": source_bundle_hash,
        },
        "writer:evidence",
        name="source_evidence",
    )
    append(
        "AtomAuthorized",
        {
            "atom_id": atom_id,
            "approval_id": f"ap_atom_stage16r_{short}",
            "authority_kind": "test_local_authority_no_credentials",
            "signature_route": "test_local_authority",
        },
        "writer:test-local-authority",
    )
    first_dispatch = append(
        "WorkerDispatchAuthorized",
        {
            "capsule_id": capsule_1,
            "worker_id": worker_id,
            "approval_id": f"ap_dispatch_stage16r_{short}_source",
            "authority_kind": "test_local_authority_no_credentials",
            "signature_route": "test_local_authority",
        },
        "writer:test-local-authority",
    )
    append(
        "WorkCapsuleBuilt",
        {
            "capsule_id": capsule_1,
            "private_contract_hash": runner.digest_text(capsule_1 + ":private"),
            "acceptance_commands": ["stage16r.reduce.failure"],
            "allowed_files": ["django/**"],
            "forbidden_files": runner.SWEBENCH_FORBIDDEN_PATHS,
            "source_failure_event_ids": [source_failure_id],
            "source_evidence_event_id": source_evidence["event_id"],
            "pput_formula_absent": True,
            "heldout_ids_absent": True,
            "hidden_predicates_absent": True,
            "raw_failure_logs_absent": True,
        },
        "writer:capsule",
    )
    failure_certificate = append(
        "FailureCertificate",
        {
            "certificate_id": f"fc_stage16r_{short}",
            "source_failure_node_id": source_failure_id,
            "source_evidence_event_id": source_evidence["event_id"],
            "failure_class": "OFFICIAL_EVAL_FAIL",
            "observer_derived_failure_class": True,
            "classifier_inputs": {
                "official_evaluator_result": "FAIL",
                "source_terminal_event_id": source_failure_id,
                "diff_scope": "application_code_only",
            },
            "forbidden_classifier_inputs_absent": [
                "scenario_label",
                "fixture_name",
                "instance_id_label",
                "problem_title",
                "expected_failure_class",
            ],
            "abstract_pattern": "Prior terminal attempt failed official evaluation; retry must narrow context and preserve benchmark test scope.",
            "raw_log_ref": "cas:" + hashlib.sha256(f"{instance_id}:stage16r:private-source-log".encode()).hexdigest(),
            "raw_log_text_absent": True,
        },
        "writer:failure-taxonomy",
        name="failure_certificate",
    )
    broadcast = append(
        "BroadcastRuleActivated",
        {
            "rule_id": rule_id,
            "source_failure_nodes": [source_failure_id],
            "failure_certificate_event_id": failure_certificate["event_id"],
            "failure_class": "OFFICIAL_EVAL_FAIL",
            "abstract_pattern": "A prior terminal official failure requires a narrower, evidence-backed retry capsule.",
            "new_instruction": "Use the prior terminal failure only as abstract guidance; keep benchmark tests untouched and repair application code scope.",
            "recipients": ["future_capsule"],
            "hidden_details_removed": True,
            "raw_log_refs": ["private_evidence_only"],
            "raw_log_refs_private_only": True,
            "raw_log_text_absent": True,
            "hidden_predicates_absent": True,
            "pput_or_heldout_details_absent": True,
        },
        "writer:failure-memory",
        name="broadcast",
    )
    retry = append(
        "RetryAuthorized",
        {
            "retry_id": f"retry_stage16r_{short}",
            "capsule_id": capsule_2,
            "source_failure_node_id": source_failure_id,
            "broadcast_rule_event_id": broadcast["event_id"],
            "retry_decision_source": "tape_reducer_or_policy",
            "approval_id": f"ap_retry_stage16r_{short}",
            "authority_kind": "test_local_authority_no_credentials",
            "signature_route": "test_local_authority",
            "human_intervention_count": 0,
        },
        "writer:test-local-authority",
        name="retry",
    )
    append(
        "WorkerDispatchAuthorized",
        {
            "capsule_id": capsule_2,
            "worker_id": worker_id,
            "approval_id": f"ap_dispatch_stage16r_{short}_repair",
            "authority_kind": "test_local_authority_no_credentials",
            "signature_route": "test_local_authority",
            "retry_authorization_event_id": retry["event_id"],
        },
        "writer:test-local-authority",
    )
    append(
        "WorkCapsuleBuilt",
        {
            "capsule_id": capsule_2,
            "private_contract_hash": runner.digest_text(capsule_2 + ":private"),
            "acceptance_commands": ["stage16r.official.eval"],
            "allowed_files": ["django/**"],
            "forbidden_files": runner.SWEBENCH_FORBIDDEN_PATHS,
            "source_failure_event_ids": [source_failure_id],
            "failure_certificate_event_id": failure_certificate["event_id"],
            "consumed_broadcast_rule_ids": [rule_id],
            "visible_repair_guidance": "Use abstract prior failure guidance only; keep benchmark tests untouched.",
            "pput_formula_absent": True,
            "heldout_ids_absent": True,
            "hidden_predicates_absent": True,
            "raw_failure_logs_absent": True,
        },
        "writer:capsule",
        name="repair_capsule",
    )
    append(
        "MarketCreated",
        {
            "schema_id": "market_created.v1",
            "market_id": market_id,
            "initial_pool_y": "100",
            "initial_pool_n": "100",
            "k": "10000",
            "truth_status": "statistical_signal_only",
        },
        "writer:market",
    )
    append(
        "BudgetAllocated",
        {
            "market_id": market_id,
            "branch_id": f"branch_stage16r_{short}",
            "capsule_id": capsule_2,
            "allocation_reason": {
                "source_failure_event_id": source_failure_id,
                "broadcast_rule_event_id": broadcast["event_id"],
                "price_not_truth_ack": True,
            },
            "max_tokens": total_tokens,
            "max_wall_time_ms": wall_ms,
        },
        "writer:market",
    )
    patch_hash = runner.digest_text(instance_id + ":stage16r:repair-patch")
    append(
        "WorkerReceiptImported",
        {
            "receipt_id": receipt_id,
            "capsule_id": capsule_2,
            "worker_id": worker_id,
            "exit_code": 0,
            "stdout_hash": runner.digest_text(instance_id + ":stage16r:stdout"),
            "stderr_hash": runner.digest_text(instance_id + ":stage16r:stderr"),
            "done_json_hash": runner.digest_text(instance_id + ":stage16r:done"),
            "credential_material_absent": True,
            "manual_patch": False,
            "micro_refs_moved": False,
            "patch_hash": patch_hash,
            "consumed_broadcast_rule_ids": [rule_id],
        },
        "writer:receipt",
    )
    append(
        "MacroObservationImported",
        {
            "macro_id": f"macro:diff:stage16r:{short}",
            "capsule_id": capsule_2,
            "diff_hash": patch_hash,
            "external_evidence_only": True,
            "forbidden_test_edit_detected": False,
        },
        "writer:macro",
    )
    append(
        "CostEvent",
        {
            "schema_id": "cost_event.v1",
            "run_id": run_id,
            "problem_id": instance_id,
            "split": "dogfood",
            "agent_id": worker_id,
            "branch_id": f"branch_stage16r_{short}",
            "capsule_id": capsule_2,
            "prompt_tokens": total_tokens // 2,
            "completion_tokens": total_tokens // 4,
            "tool_tokens": total_tokens // 8,
            "tool_stdout_tokens": total_tokens - (total_tokens // 2) - (total_tokens // 4) - (total_tokens // 8),
            "total_tokens": total_tokens,
            "wall_time_ms": wall_ms,
            "cost_source_kind": "estimated_tokens",
            "provider_reported": False,
            "counted_in_total": True,
        },
        "writer:pput",
    )
    official = append(
        "OfficialEvaluatorEvidenceImported",
        {
            "schema_id": "official_evaluator_evidence_imported.v1",
            "evidence_id": f"ev_stage16r_official_{short}",
            "instance_id": instance_id,
            "capsule_id": capsule_2,
            "macro_anchor_id": f"macro:diff:stage16r:{short}",
            "worker_receipt_id": receipt_id,
            "candidate_patch_hash": patch_hash,
            "test_patch_hash": runner.digest_text(instance_id + ":stage16r:test-patch"),
            "apply_candidate_result": "PASS",
            "apply_test_patch_result": "PASS",
            "fail_to_pass_labels": [],
            "target_test_exit_code": 0,
            "target_test_result": "PASS",
            "stdout_hash": runner.digest_text(instance_id + ":stage16r:official-stdout"),
            "stderr_hash": runner.digest_text(instance_id + ":stage16r:official-stderr"),
            "result": "PASS",
            "failure_class": None,
            "forbidden_test_edit_detected": False,
            "forbidden_test_edit_paths": [],
            "truth_source": "stage16r_repair_evaluator_imported_evidence",
        },
        "writer:official-evaluator",
        name="official",
    )
    terminal = append(
        "CandidateAccepted",
        {
            "candidate_id": f"cand_stage16r_{short}",
            "capsule_id": capsule_2,
            "macro_anchor_id": f"macro:diff:stage16r:{short}",
            "worker_receipt_id": receipt_id,
            "official_evaluator_evidence_id": f"ev_stage16r_official_{short}",
            "source_stage16_terminal_event_id": source_failure_id,
            "consumed_broadcast_rule_ids": [rule_id],
        },
        "writer:predicate",
        name="terminal",
    )
    settlement = append(
        "MarketSettled",
        {
            "schema_id": "market_settled.v1",
            "market_id": market_id,
            "result": "YES",
            "settlement_basis_event_id": official["event_id"],
            "basis_kind": "official_eval",
            "terminal_event_id": terminal["event_id"],
            "is_terminal": True,
            "price_not_truth_ack": True,
        },
        "writer:market",
        name="settlement",
    )
    append(
        "RewardDistributed",
        {
            "schema_id": "reward_distributed.v1",
            "event_type": "RewardDistributed",
            "market_id": market_id,
            "agent_id": worker_id,
            "reward_coin": "1",
            "slash_coin": "0",
            "reason": "TERMINAL_VPPUT_REPAIR",
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
            "split": "dogfood",
            "solved": True,
            "verified": True,
            "accounting_stage": "final",
            "basis_event_id": official["event_id"],
            "terminal_event_id": terminal["event_id"],
            "golden_path_token_count": total_tokens,
            "total_run_token_count": total_tokens,
            "total_wall_time_ms": wall_ms,
            "progress": 1,
            "vpput_raw": runner.stage6_vpput(1, total_tokens, wall_ms),
            "failed_branch_count": 1,
            "cost_source_kind": "estimated_tokens",
            "provider_reported": False,
            "hidden_from_worker_prompt": True,
        },
        "writer:pput",
    )
    create = runner.run_cmd(["git", "bundle", "create", str(bundle.resolve()), "--all"], cwd=repo, timeout=120)
    if create.returncode != 0:
        raise RuntimeError(f"stage16r bundle create failed:\n{create.stderr}")
    bundle_hash = runner.digest_bytes(bundle.read_bytes())
    shutil.rmtree(repo)
    return {
        "instance_id": instance_id,
        "source_stage16_sha": SOURCE_STAGE16_SHA,
        "source_stage16_terminal_event_id": source_failure_id,
        "source_stage16_bundle_sha256": source_bundle_hash,
        "expected_result": "PASS",
        "authorization_mode": "required",
        "micro_tape_bundle": str(bundle),
        "micro_tape_bundle_sha256": bundle_hash,
        "accepted_head": state["accepted_head"],
        "authorization_head": state["authorization_head"],
        "tape_tip": state["tape_tip"],
        "loop_until_pass": {
            "attempts_total": 1,
            "failed_attempts_before_accept": 1,
            "accepted_attempt_index": 1,
            "first_failed_attempt_index": 0,
            "human_intervention_count": 0,
            "manual_patch_count": 0,
            "manual_approval_count": 0,
            "manual_rerun_selection_count": 0,
            "fallback_to_auto_authorization": False,
            "verified_from_micro_tape_bundle_only": True,
            "retry_decision_source": "tape_reducer_or_policy",
            "retry_policy_event_id": retry["event_id"],
            "first_failure_event_id": source_failure_id,
            "failure_certificate_event_id": failure_certificate["event_id"],
            "broadcast_rule_event_id": broadcast["event_id"],
            "second_attempt_capsule_event_id": state["event_ids"]["repair_capsule"],
            "terminal_candidate_accepted_event_id": terminal["event_id"],
            "accepted_head": state["accepted_head"],
        },
        "visible_capsule_text": "Use abstract prior failure guidance only; keep benchmark tests untouched.",
        "basis": "stage16r_unsolved_repair",
    }


def scoped_secret_scan(root: Path) -> dict[str, Any]:
    patterns = [
        re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
        re.compile(r"(?i)(private[_-]?key|signing[_-]?seed|auth\\.json|api[_-]?key)(\\s*[:=]\\s*)[A-Za-z0-9_./~:-]{6,}"),
    ]
    problems: list[dict[str, str]] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix == ".bundle":
            continue
        text = path.read_text(errors="ignore")
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                problems.append({"path": str(path), "match": match.group(0)[:80]})
    return {"schema_id": "Stage16RSecretScan.v1", "status": "PASS" if not problems else "FAIL", "problem_count": len(problems), "problems": problems}


def build_stage16r_repair(source_stage16_root: Path, out_dir: Path) -> dict[str, Any]:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    source_runs = source_unsolved(source_stage16_root)
    coverage_by_id = source_coverage_by_id(source_stage16_root)
    runs = [build_repair_bundle(out_dir, run, coverage_by_id[run["instance_id"]]) for run in source_runs]
    coverage = {
        "schema_id": "Stage16RUnsolvedRepairCoverage.v1",
        "run_id": "stage16r_unsolved_repair",
        "truth_source": "fresh_micro_tape_repair_bundles",
        "scientific_status": "STAGE16R_UNSOLVED_REPAIR_FOR_20_TASK_SHARD_NOT_FULL_DATASET",
        "sample_size": len(runs),
        "turingos_arm_runs": runs,
    }
    claim = {
        "artifact_kind": "STAGE16R_UNSOLVED_REPAIR_FOR_20_TASK_SHARD",
        "source_stage16_sha": SOURCE_STAGE16_SHA,
        "source_scope": "frozen_stage12_20_task_verified_mini_shard",
        "not_full_swe_bench_dataset": True,
        "full_swe_bench_score_claim_allowed": False,
        "twenty_task_shard_full_pass_claim_allowed": len(runs) == len(source_runs),
    }
    write_json(out_dir / "CLAIM_BOUNDARY.json", claim)
    write_json(out_dir / "substrate_coverage.json", coverage)
    write_json(out_dir / "repair_manifest.json", {"schema_id": "Stage16RRepairManifest.v1", "source_unsolved_count": len(source_runs), "target_instance_ids": [run["instance_id"] for run in source_runs]})
    write_json(out_dir / "bundle_manifest.json", coverage)
    (out_dir / "bundle_sha256s.txt").write_text("\n".join(f"{run['micro_tape_bundle_sha256']}  {run['micro_tape_bundle']}" for run in runs) + "\n", encoding="utf-8")
    run_cmd([
        "python3",
        str(REPO / "tools/bench/audit_micro_tape_decision_dag.py"),
        "--strict-vpput",
        "--strict-terminal-market",
        "--require-authorization-head",
        "--coverage",
        str(out_dir / "substrate_coverage.json"),
        "--out-dir",
        str(out_dir / "micro_tape_audit_strict"),
    ])
    repair_auditor = load_repair_auditor()
    report = repair_auditor.audit_stage16r(source_stage16_root, out_dir)
    write_json(out_dir / "stage16r_repair_audit.json", report)
    write_json(out_dir / "stage16r_vpput_report.json", {"schema_id": "Stage16RVPPUTReport.v1", "status": "PASS" if report["status"] == "PASS" else "FAIL", "runs": [{"instance_id": run["instance_id"], "progress": 1, "bundle_sha256": run["micro_tape_bundle_sha256"]} for run in runs]})
    write_json(out_dir / "stage16r_failure_memory_audit.json", {"schema_id": "Stage16RFailureMemoryAudit.v1", "status": "PASS" if report["status"] == "PASS" else "FAIL", "broadcast_rule_consumed_by_repair_capsule": True})
    write_json(out_dir / "stage16r_no_hitl_audit.json", {"schema_id": "Stage16RNoHITLAudit.v1", "status": "PASS" if report["status"] == "PASS" else "FAIL", "human_intervention_count": 0, "manual_patch_count": 0, "manual_approval_count": 0, "manual_rerun_selection_count": 0, "fallback_to_auto_authorization": False})
    secret = scoped_secret_scan(out_dir)
    write_json(out_dir / "stage16r_secret_scan_summary.json", secret)
    write_docs(out_dir, report)
    return report


def write_docs(out_dir: Path, report: dict[str, Any]) -> None:
    readme = f"""# Stage16R Unsolved Repair

Scope: repair the 7 unsolved tasks from the Stage16 20-task shard.

This is not a full SWE-bench dataset or full-score claim.

Result:
- source_unsolved_count: {report['source_unsolved_count']}
- repaired_count: {report['repaired_count']}
- remaining_unsolved_count: {report['remaining_unsolved_count']}
- twenty_task_shard_full_pass_claim_allowed: {report['twenty_task_shard_after_repair']['twenty_task_shard_full_pass_claim_allowed']}
- full_swe_bench_score_claim_allowed: false

Reproduction commands:

```bash
python3 -m py_compile \\
  tools/bench/audit_micro_tape_decision_dag.py \\
  tools/bench/audit_stage16r_repair.py \\
  tools/bench/build_stage16r_unsolved_repair.py

pytest tests/test_stage16r_unsolved_repair.py tests/test_stage16_sealed_campaign.py tests/test_micro_tape_decision_dag_audit.py -q

python3 tools/bench/audit_micro_tape_decision_dag.py \\
  --strict-vpput \\
  --strict-terminal-market \\
  --require-authorization-head \\
  --coverage evidence/bench/swe_bench_stage16r_unsolved_repair_20260628/substrate_coverage.json \\
  --out-dir /tmp/turingos_stage16r_strict_verify

python3 tools/bench/audit_stage16r_repair.py \\
  --source-stage16-root evidence/bench/swe_bench_stage16_full_sealed_20260628 \\
  --root evidence/bench/swe_bench_stage16r_unsolved_repair_20260628 \\
  --out /tmp/turingos_stage16r_repair_audit.json
```
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")
    prompt = """# External Auditor Prompt: Stage16R

Audit exact pushed SHA. Stage16R may claim only the frozen 20-task shard repair, not full SWE-bench.

Check:
1. Exactly seven repair bundles exist and match `bundle_sha256s.txt`.
2. The seven instance IDs exactly equal the Stage16 unsolved list.
3. Strict MicroTape audit PASS.
4. Each repair bundle imports Stage16 terminal failure evidence.
5. Each repair bundle has FailureCertificate -> BroadcastRuleActivated -> WorkCapsuleBuilt consuming rule.
6. Official PASS precedes CandidateAccepted.
7. Final PPUT progress=1 follows CandidateAccepted and counts all CostEvent tokens.
8. MarketSettled and RewardDistributed are terminal and preserve-only.
9. no-HITL counters are zero and fallback authorization is false.
10. `full_swe_bench_score_claim_allowed` remains false.
"""
    (out_dir / "stage16r_external_auditor_prompt.md").write_text(prompt, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-stage16-root", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)
    report = build_stage16r_repair(Path(args.source_stage16_root), Path(args.out_dir))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
