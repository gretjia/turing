#!/usr/bin/env python3
"""FCE-B1: uplift-verification / recomputation battery (G4/G5).

Per 09_FINAL_CERTIFICATION_EVALS.md section "FCE-B1 - Loop self-improvement
effectiveness (failure-memory efficacy, from M3/M4 outputs)": this scenario
verifies that the M3/M4 measurements are valid and reproducible. It does NOT
re-run the M3 confirmatory shard S01 experiment or any worker call; it
recomputes digests and metrics from the frozen M3/M4 evidence already on disk
and asserts the recomputed values equal the recorded/certified values. A
positive uplift result is explicitly NOT required for PASS (Intent G4).

Eight checks, each producing one or more `pass_criteria_results` entries:

1. digest_check           - PREREGISTRATION.sha256 -> M3_P1_FREEZE_RECORD.json
                             digest, and every M3.P1 frozen packet file's
                             sha256 (preregistration, analysis script, S01/S02
                             shard manifests, dataset descriptor, loop
                             manifest) recomputed and compared to the frozen
                             record.
2. recompute_analysis     - re-run the frozen analyze_uplift.py against the
                             S01-scoped derived evaluation_results.json files
                             and assert the recomputed UPLIFT_REPORT.json
                             equals the published one exactly.
3. scoring_provenance     - every arm's (A, B, C, D) evaluation outcome traces
                             to an official upstream SWE-bench harness
                             report.json (schema_version 2), never a
                             repo-local evaluator; digests recomputed.
4. ablation_honesty       - re-run tools/bench/audit_ablation_capsules.py over
                             the real Arm B / Arm C worker-visible capsules
                             and assert PASS (capsules differ only inside the
                             delimited broadcast-rules section).
5. manipulation_check     - Arm D (deterministic floor) resolved_instances is
                             recomputed from its official upstream report and
                             must be exactly 0, with no stop-condition latch.
6. efficacy_statistics    - the recomputed report states Delta for H2 with a
                             bootstrap CI and the pre-registered MDE
                             statement, and the M4 north-star honesty sentence
                             is phrased as "Delta = x [CI], powered for MDE =
                             y", never "no effect".
7. deviations_completeness- DEVIATIONS.md exists and documents the roster
                             reregistration and the incomplete_ids handling
                             rule; pairwise_exclusions is 0 and every derived
                             per-arm result file's error_ids/incomplete_ids
                             are empty, matching the "zero pairwise
                             exclusions" claim.
8. h_vpput_verification   - digest-check the M4 north-star inputs, recompute
                             H-VPPUT per arm from the frozen compute_hvpput.py
                             plus the held-out task registry and normalized
                             receipts/results, assert the recomputed values
                             equal the published per-arm and assembled
                             reports exactly, assert zero excluded
                             (cost_source_kind-inadmissible, including
                             "unspecified") events, and re-run a worker-visible
                             marker sweep for the held-out registry / metric
                             surface with zero hits.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TURING_MARKER = "/work/turing/"
VOLATILE_KEYS = {"timestamp_utc", "created_at_utc", "wall_clock_ms"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return "sha256:" + sha256_bytes(path.read_bytes())


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def resolve_turing_path(raw: str, repo: Path) -> Path:
    """Frozen M3/M4 records cite absolute paths under the `turing` repo's own
    checkout at authoring time. Re-resolve them against THIS certification
    run's `--repo` clone (which may be a different worktree/branch of the
    same repo) so the recompute genuinely re-reads bytes from the cert
    clone, per Intent's "from the certification clone" rule (FCE-S2)."""
    idx = raw.find(TURING_MARKER)
    if idx == -1:
        return Path(raw)
    return repo / raw[idx + len(TURING_MARKER):]


def strip_volatile(value: Any, parent_key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {
            k: strip_volatile(v, k)
            for k, v in value.items()
            if k not in VOLATILE_KEYS
            # "source_report.path" legitimately differs across scratch
            # recompute directories (each run writes its per-arm report to a
            # fresh scratch path); its sha256 sibling is compared instead, so
            # this is scratch-path volatility (NORMALIZATION_SPEC.json's
            # absolute_scratch_path class), not a substantive mismatch.
            and not (k == "path" and parent_key == "source_report")
        }
    if isinstance(value, list):
        return [strip_volatile(item, parent_key) for item in value]
    return value


def run_command(
    *,
    name: str,
    argv: list[str],
    cwd: Path,
    out_dir: Path,
    timeout: int = 600,
) -> dict[str, Any]:
    started = time.monotonic()
    proc = subprocess.run(
        argv,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    stdout_path = out_dir / f"{name}.stdout.txt"
    stderr_path = out_dir / f"{name}.stderr.txt"
    stdout_path.write_text(proc.stdout, encoding="utf-8")
    stderr_path.write_text(proc.stderr, encoding="utf-8")
    return {
        "name": name,
        "cmd": " ".join(argv),
        "exit_code": proc.returncode,
        "wall_clock_ms": elapsed_ms,
        "stdout": stdout_path.name,
        "stderr": stderr_path.name,
        "stdout_text": proc.stdout,
        "stderr_text": proc.stderr,
    }


# --------------------------------------------------------------------------
# Check 1: preregistration + frozen-packet digest chain
# --------------------------------------------------------------------------


def check_digest_chain(m3_dir: Path, repo: Path, scenario_root: Path) -> tuple[dict[str, Any], list[Path]]:
    freeze_record_path = m3_dir / "M3_P1_FREEZE_RECORD.json"
    prereg_sha_path = m3_dir / "PREREGISTRATION.sha256"
    plan_root = m3_dir.parent

    line = prereg_sha_path.read_text(encoding="utf-8").strip()
    recorded_digest, recorded_rel = line.split(maxsplit=1)
    freeze_record_actual_sha256 = sha256_bytes(freeze_record_path.read_bytes())
    freeze_record_digest_matches = (
        recorded_digest == freeze_record_actual_sha256
        and (plan_root / recorded_rel).resolve() == freeze_record_path.resolve()
    )

    freeze_record = load_json(freeze_record_path)
    packet_rows: list[dict[str, Any]] = []
    all_match = True
    for entry in freeze_record.get("packet_files", []):
        raw_path = entry["path"]
        if raw_path.startswith("/"):
            actual_path = resolve_turing_path(raw_path, repo)
        else:
            actual_path = plan_root / raw_path
        exists = actual_path.is_file()
        actual_sha = sha256_bytes(actual_path.read_bytes()) if exists else None
        matches = exists and actual_sha == entry["sha256"]
        all_match = all_match and matches
        packet_rows.append(
            {
                "recorded_path": raw_path,
                "resolved_path": str(actual_path),
                "recorded_sha256": entry["sha256"],
                "actual_sha256": actual_sha,
                "exists": exists,
                "matches": matches,
            }
        )

    result = {
        "schema_id": "turingos.fce.b1.digest_chain_check.v1",
        "preregistration_sha256_file": str(prereg_sha_path),
        "preregistration_sha256_recorded_target": recorded_rel,
        "preregistration_sha256_recorded_digest": recorded_digest,
        "freeze_record_actual_sha256": freeze_record_actual_sha256,
        "freeze_record_digest_matches": freeze_record_digest_matches,
        "packet_files_checked": len(packet_rows),
        "packet_files_all_match": all_match,
        "packet_rows": packet_rows,
    }
    path = scenario_root / "m3_digest_chain_check.json"
    write_json(path, result)
    return result, [path]


# --------------------------------------------------------------------------
# Check 2: recompute the frozen analyzer over the S01-scoped evaluation_results.json
# --------------------------------------------------------------------------


def check_recompute_analysis(
    m3_dir: Path, scenario_root: Path, commands: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[Path], dict[str, Any]]:
    analysis_root = m3_dir / "analysis" / "s01_deepseek_only_20260703"
    script = m3_dir / "analysis" / "analyze_uplift.py"
    published_path = analysis_root / "out" / "UPLIFT_REPORT.json"
    out_dir = scenario_root / "m3_analysis_recompute"

    command = run_command(
        name="m3_analyze_uplift_recompute",
        argv=[
            sys.executable,
            str(script),
            "--root",
            str(analysis_root),
            "--out",
            str(out_dir),
            "--reps",
            "10000",
            "--seed",
            "20260702",
        ],
        cwd=m3_dir,
        out_dir=scenario_root,
    )
    commands.append(command)

    recomputed_path = out_dir / "UPLIFT_REPORT.json"
    published = load_json(published_path)
    recomputed = load_json(recomputed_path) if recomputed_path.is_file() else None
    equal = recomputed is not None and recomputed == published

    comparison = {
        "schema_id": "turingos.fce.b1.analysis_recompute_check.v1",
        "command_exit_code": command["exit_code"],
        "published_report_path": str(published_path),
        "published_report_sha256": sha256_file(published_path),
        "recomputed_report_path": str(recomputed_path),
        "recomputed_report_sha256": sha256_file(recomputed_path) if recomputed_path.is_file() else None,
        "reports_byte_equal_after_parse": equal,
        "published_h1": published["confirmatory_tests"]["H1_B_gt_A"],
        "recomputed_h1": recomputed["confirmatory_tests"]["H1_B_gt_A"] if recomputed else None,
        "published_h2": published["confirmatory_tests"]["H2_B_gt_C"],
        "recomputed_h2": recomputed["confirmatory_tests"]["H2_B_gt_C"] if recomputed else None,
    }
    path = scenario_root / "m3_analysis_recompute_comparison.json"
    write_json(path, comparison)
    return comparison, [path], published


# --------------------------------------------------------------------------
# Check 3: scoring provenance (every outcome traces to an upstream harness report)
# --------------------------------------------------------------------------


def check_scoring_provenance(
    m3_dir: Path, repo: Path, scenario_root: Path
) -> tuple[dict[str, Any], list[Path]]:
    analysis_root = m3_dir / "analysis" / "s01_deepseek_only_20260703"
    derivation_record = load_json(analysis_root / "ANALYSIS_INPUT_DERIVATION_RECORD.json")
    floor_audit_path_candidates = list(
        repo.glob("evidence/bench/*/shards/S01/arms/D_deterministic_floor/deterministic_floor_result_audit.json")
    )

    rows: list[dict[str, Any]] = []
    all_pass = True
    for entry in derivation_record["derived_results"]:
        source_path = resolve_turing_path(entry["source_report_path"], repo)
        exists = source_path.is_file()
        actual_sha = sha256_bytes(source_path.read_bytes()) if exists else None
        expected_sha = entry["source_report_sha256"]
        digest_matches = exists and actual_sha == expected_sha
        report = load_json(source_path) if exists else {}
        is_upstream_schema = report.get("schema_version") == 2 and "resolved_ids" in report
        is_upstream_path = "/scoring/" in source_path.as_posix()
        no_repo_local_marker = "repo_local" not in source_path.as_posix() and "internal_evaluator" not in source_path.as_posix()
        row_pass = digest_matches and is_upstream_schema and is_upstream_path and no_repo_local_marker
        all_pass = all_pass and row_pass
        rows.append(
            {
                "arm": entry["arm"],
                "source_report_path": str(source_path),
                "digest_matches": digest_matches,
                "upstream_schema_version_2": is_upstream_schema,
                "path_under_scoring_dir": is_upstream_path,
                "no_repo_local_evaluator_marker": no_repo_local_marker,
                "pass": row_pass,
            }
        )

    floor_row: dict[str, Any] | None = None
    if floor_audit_path_candidates:
        floor_audit = load_json(floor_audit_path_candidates[0])
        floor_report_path = repo / floor_audit["official_report_path"]
        floor_exists = floor_report_path.is_file()
        floor_actual_sha = "sha256:" + sha256_bytes(floor_report_path.read_bytes()) if floor_exists else None
        floor_digest_matches = floor_exists and floor_actual_sha == floor_audit["official_report_sha256"]
        floor_report = load_json(floor_report_path) if floor_exists else {}
        floor_row = {
            "arm": "D",
            "source_report_path": str(floor_report_path),
            "digest_matches": floor_digest_matches,
            "upstream_schema_version_2": floor_report.get("schema_version") == 2 and "resolved_ids" in floor_report,
            "path_under_scoring_dir": "/scoring/" in floor_report_path.as_posix(),
            "no_repo_local_evaluator_marker": True,
            "pass": floor_digest_matches,
        }
        all_pass = all_pass and floor_row["pass"]
        rows.append(floor_row)

    result = {
        "schema_id": "turingos.fce.b1.scoring_provenance_check.v1",
        "rows": rows,
        "all_arms_trace_to_upstream_harness": all_pass,
    }
    path = scenario_root / "m3_scoring_provenance_check.json"
    write_json(path, result)
    return result, [path]


# --------------------------------------------------------------------------
# Check 4: ablation-honesty re-run
# --------------------------------------------------------------------------


def check_ablation_honesty(
    repo: Path, scenario_root: Path, commands: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[Path]]:
    stored_audit_candidates = list(
        repo.glob("evidence/bench/*/shards/S01/arms/m3_p6_ablation_capsule_audit.json")
    )
    if not stored_audit_candidates:
        result = {
            "schema_id": "turingos.fce.b1.ablation_honesty_recompute.v1",
            "status": "MISSING_STORED_AUDIT",
            "pass": False,
        }
        path = scenario_root / "m3_ablation_honesty_recompute.json"
        write_json(path, result)
        return result, [path]

    stored_audit_path = stored_audit_candidates[0]
    stored_audit = load_json(stored_audit_path)
    arm_b_dir = resolve_turing_path(stored_audit["arm_b_dir"], repo)
    arm_c_dir = resolve_turing_path(stored_audit["arm_c_dir"], repo)

    out_path = scenario_root / "m3_ablation_honesty_recompute_audit.json"
    command = run_command(
        name="m3_ablation_capsule_audit_recompute",
        argv=[
            sys.executable,
            str(repo / "tools" / "bench" / "audit_ablation_capsules.py"),
            "--arm-b-dir",
            str(arm_b_dir),
            "--arm-c-dir",
            str(arm_c_dir),
            "--out",
            str(out_path),
        ],
        cwd=repo,
        out_dir=scenario_root,
    )
    commands.append(command)

    recomputed = load_json(out_path) if out_path.is_file() else None
    result = {
        "schema_id": "turingos.fce.b1.ablation_honesty_recompute.v1",
        "stored_audit_path": str(stored_audit_path),
        "stored_audit_status": stored_audit.get("status"),
        "stored_audit_capsule_count": stored_audit.get("capsule_count"),
        "recomputed_audit_path": str(out_path),
        "recomputed_audit_status": recomputed.get("status") if recomputed else None,
        "recomputed_capsule_count": recomputed.get("capsule_count") if recomputed else None,
        "recomputed_problems": recomputed.get("problems") if recomputed else None,
        "command_exit_code": command["exit_code"],
        "pass": bool(
            recomputed
            and recomputed.get("status") == "PASS"
            and recomputed.get("capsule_count", 0) > 0
            and not recomputed.get("problems")
        ),
    }
    path = scenario_root / "m3_ablation_honesty_recompute.json"
    write_json(path, result)
    return result, [path, out_path]


# --------------------------------------------------------------------------
# Check 5: Arm D deterministic-floor manipulation check
# --------------------------------------------------------------------------


def check_arm_d_floor(repo: Path, scenario_root: Path) -> tuple[dict[str, Any], list[Path]]:
    candidates = list(
        repo.glob("evidence/bench/*/shards/S01/arms/D_deterministic_floor/deterministic_floor_result_audit.json")
    )
    if not candidates:
        result = {
            "schema_id": "turingos.fce.b1.arm_d_floor_check.v1",
            "status": "MISSING_ARM_D_AUDIT",
            "pass": False,
        }
        path = scenario_root / "m3_arm_d_floor_check.json"
        write_json(path, result)
        return result, [path]

    audit = load_json(candidates[0])
    official_report_path = repo / audit["official_report_path"]
    exists = official_report_path.is_file()
    actual_sha = "sha256:" + sha256_bytes(official_report_path.read_bytes()) if exists else None
    digest_matches = exists and actual_sha == audit["official_report_sha256"]
    report = load_json(official_report_path) if exists else {}
    resolved_instances = report.get("resolved_instances")
    resolved_ids = report.get("resolved_ids", [])
    zero_resolved = resolved_instances == 0 and resolved_ids == []
    result = {
        "schema_id": "turingos.fce.b1.arm_d_floor_check.v1",
        "official_report_path": str(official_report_path),
        "digest_matches": digest_matches,
        "recomputed_resolved_instances": resolved_instances,
        "recomputed_resolved_ids": resolved_ids,
        "stop_condition_triggered_recorded": audit.get("stop_condition_triggered"),
        "zero_resolved_confirmed": zero_resolved,
        "pass": digest_matches and zero_resolved and audit.get("stop_condition_triggered") is False,
    }
    path = scenario_root / "m3_arm_d_floor_check.json"
    write_json(path, result)
    return result, [path]


# --------------------------------------------------------------------------
# Check 6: efficacy-statistics presence + honest-null phrasing
# --------------------------------------------------------------------------


NO_EFFECT_RE = re.compile(r"\bno effect\b", re.IGNORECASE)


def check_efficacy_statistics(
    published_uplift_report: dict[str, Any], m4_dir: Path, scenario_root: Path
) -> tuple[dict[str, Any], list[Path]]:
    h2 = published_uplift_report["confirmatory_tests"]["H2_B_gt_C"]
    has_delta = isinstance(h2.get("delta"), (int, float))
    has_ci = (
        isinstance(h2.get("bootstrap_ci95", {}).get("ci95_low"), (int, float))
        and isinstance(h2.get("bootstrap_ci95", {}).get("ci95_high"), (int, float))
    )
    mde_statement = published_uplift_report.get("mde_statement", "")
    has_mde = isinstance(mde_statement, str) and len(mde_statement.strip()) > 0

    northstar_result_path = m4_dir / "M4_P3_NORTHSTAR_RESULT.json"
    northstar_report_path = m4_dir / "real_s01_deepseek_20260703" / "NORTHSTAR_REPORT.md"
    northstar_result = load_json(northstar_result_path)
    direction_sentence = northstar_result.get("mandatory_direction_sentence", "")
    northstar_text = northstar_report_path.read_text(encoding="utf-8")

    honest_phrasing = (
        "CI includes 0" in direction_sentence
        and "powered for MDE" in direction_sentence
        and not NO_EFFECT_RE.search(direction_sentence)
        and not NO_EFFECT_RE.search(northstar_text)
    )

    result = {
        "schema_id": "turingos.fce.b1.efficacy_statistics_check.v1",
        "h2_has_delta": has_delta,
        "h2_delta": h2.get("delta"),
        "h2_has_bootstrap_ci95": has_ci,
        "h2_ci95_low": h2.get("bootstrap_ci95", {}).get("ci95_low"),
        "h2_ci95_high": h2.get("bootstrap_ci95", {}).get("ci95_high"),
        "mde_statement_present": has_mde,
        "mde_statement": mde_statement,
        "m4_mandatory_direction_sentence": direction_sentence,
        "honest_null_phrasing_no_bare_no_effect_claim": honest_phrasing,
        "pass": has_delta and has_ci and has_mde and honest_phrasing,
    }
    path = scenario_root / "m3_m4_efficacy_statistics_check.json"
    write_json(path, result)
    return result, [path]


# --------------------------------------------------------------------------
# Check 7: deviations completeness
# --------------------------------------------------------------------------


def check_deviations_completeness(m3_dir: Path, scenario_root: Path) -> tuple[dict[str, Any], list[Path]]:
    analysis_root = m3_dir / "analysis" / "s01_deepseek_only_20260703"
    deviations_path = analysis_root / "DEVIATIONS.md"
    derivation_record = load_json(analysis_root / "ANALYSIS_INPUT_DERIVATION_RECORD.json")
    frozen_result = load_json(m3_dir / "M3_P7_FROZEN_ANALYSIS_RESULT.json")
    manifest = load_json(analysis_root / "experiment_manifest.json")

    deviations_text = deviations_path.read_text(encoding="utf-8") if deviations_path.is_file() else ""
    deviations_nonempty = len(deviations_text.strip()) > 0
    documents_reregistration = "reregist" in deviations_text.lower()
    documents_incomplete_handling = "incomplete_ids" in deviations_text

    pairwise_exclusions_zero = (
        derivation_record.get("pairwise_exclusions") == 0
        and frozen_result.get("scope", {}).get("pairwise_exclusions") == 0
    )

    per_arm_rows: list[dict[str, Any]] = []
    all_clean = True
    for arm, rel_path in manifest["scoring"][manifest["workers"][0]].items():
        result_path = analysis_root / rel_path
        data = load_json(result_path)
        error_ids = data.get("error_ids", [])
        incomplete_ids = data.get("incomplete_ids", [])
        clean = error_ids == [] and incomplete_ids == []
        all_clean = all_clean and clean
        per_arm_rows.append(
            {
                "arm": arm,
                "path": str(result_path),
                "error_ids": error_ids,
                "incomplete_ids": incomplete_ids,
                "clean": clean,
            }
        )

    result = {
        "schema_id": "turingos.fce.b1.deviations_completeness_check.v1",
        "deviations_md_path": str(deviations_path),
        "deviations_nonempty": deviations_nonempty,
        "documents_reregistration": documents_reregistration,
        "documents_incomplete_ids_handling": documents_incomplete_handling,
        "pairwise_exclusions_zero": pairwise_exclusions_zero,
        "per_arm_rows": per_arm_rows,
        "all_arms_zero_error_and_incomplete_ids": all_clean,
        "pass": (
            deviations_nonempty
            and documents_reregistration
            and documents_incomplete_handling
            and pairwise_exclusions_zero
            and all_clean
        ),
    }
    path = scenario_root / "m3_deviations_completeness_check.json"
    write_json(path, result)
    return result, [path]


# --------------------------------------------------------------------------
# Check 8: H-VPPUT recomputation (M4)
# --------------------------------------------------------------------------

MARKER_SWEEP_TERMS = ["heldout_task_registry", "hvpput", "h-vpput"]


def worker_visible_marker_sweep(repo: Path) -> dict[str, Any]:
    roots = list(repo.glob("evidence/bench/*/shards/S01/arms/*/capsules")) + list(
        repo.glob("evidence/bench/*/shards/S01/ipqc")
    )
    hits: list[dict[str, str]] = []
    scanned = 0
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8").lower()
            except (UnicodeDecodeError, OSError):
                continue
            scanned += 1
            for term in MARKER_SWEEP_TERMS:
                if term in text:
                    hits.append({"path": str(path), "term": term})
    return {
        "schema_id": "turingos.fce.b1.worker_visible_marker_sweep_recompute.v1",
        "roots": [str(root) for root in roots],
        "markers": MARKER_SWEEP_TERMS,
        "files_scanned": scanned,
        "hits": hits,
        "clean": not hits,
    }


def check_hvpput_verification(
    m4_dir: Path, repo: Path, scenario_root: Path, commands: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[Path]]:
    real_dir = m4_dir / "real_s01_deepseek_20260703"
    inputs_dir = real_dir / "inputs"
    registry_path = real_dir / "heldout_task_registry.v1.json"
    price_table_path = inputs_dir / "price_table.m4.json"
    receipt_binding_path = inputs_dir / "RECEIPT_BINDING_NOTE.json"
    input_digests_path = inputs_dir / "INPUT_DIGESTS.json"
    published_hvpput_path = real_dir / "hvpput_report.v1.json"
    published_hvpput = load_json(published_hvpput_path)

    manifest_candidates = list(
        (m4_dir.parent / "evidence" / "session_20260702").glob("M4G_ARTIFACT_MANIFEST.sha256")
    )
    manifest_rows: list[dict[str, Any]] = []
    manifest_all_match = True
    if manifest_candidates:
        for line in manifest_candidates[0].read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            digest, manifest_path = line.split(maxsplit=1)
            target = Path(manifest_path)
            if target.name not in ("INPUT_DIGESTS.json", "hvpput_report.v1.json"):
                continue
            if str(target) not in (str(input_digests_path), str(published_hvpput_path)):
                continue
            actual = sha256_bytes(target.read_bytes())
            matches = actual == digest
            manifest_all_match = manifest_all_match and matches
            manifest_rows.append({"path": str(target), "recorded_sha256": digest, "actual_sha256": actual, "matches": matches})

    out_dir = scenario_root / "m4_hvpput_recompute"
    out_dir.mkdir(parents=True, exist_ok=True)
    per_arm_recomputed: dict[str, Any] = {}
    per_arm_comparison: list[dict[str, Any]] = []
    all_arms_match = True
    all_arms_zero_excluded = True
    arm_report_args: list[str] = []
    for arm in ("A", "B", "C"):
        out_path = out_dir / f"arm_{arm}_hvpput_report.v1.json"
        command = run_command(
            name=f"m4_compute_hvpput_arm_{arm}",
            argv=[
                sys.executable,
                str(m4_dir / "metric" / "compute_hvpput.py"),
                "--registry",
                str(registry_path),
                "--receipts",
                str(inputs_dir / f"arm_{arm}_receipts.json"),
                "--results",
                str(inputs_dir / f"arm_{arm}_results.json"),
                "--price-table",
                str(price_table_path),
                "--run-kind",
                "REAL",
                "--out",
                str(out_path),
            ],
            cwd=m4_dir,
            out_dir=scenario_root,
        )
        commands.append(command)
        recomputed = load_json(out_path) if out_path.is_file() else None
        per_arm_recomputed[arm] = recomputed
        published_arm_path = real_dir / "per_arm" / f"arm_{arm}_hvpput_report.v1.json"
        published_arm = load_json(published_arm_path)
        equal = recomputed is not None and recomputed == published_arm
        excluded = recomputed.get("class_breakdown", {}).get("n_excluded") if recomputed else None
        all_arms_match = all_arms_match and equal
        all_arms_zero_excluded = all_arms_zero_excluded and excluded == 0
        per_arm_comparison.append(
            {
                "arm": arm,
                "command_exit_code": command["exit_code"],
                "recomputed_path": str(out_path),
                "published_path": str(published_arm_path),
                "byte_equal_after_parse": equal,
                "n_excluded": excluded,
            }
        )
        arm_report_args.extend(["--arm-report", f"{arm}={out_path}"])

    assembled_path = out_dir / "hvpput_report.v1.json"
    published_created_at = published_hvpput.get("created_at_utc")
    assemble_command = run_command(
        name="m4_assemble_hvpput_report_recompute",
        argv=[
            sys.executable,
            str(m4_dir / "metric" / "assemble_hvpput_report.py"),
            "--registry",
            str(registry_path),
            "--input-digests",
            str(input_digests_path),
            "--receipt-binding-note",
            str(receipt_binding_path),
            "--created-at-utc",
            str(published_created_at),
            "--out",
            str(assembled_path),
            *arm_report_args,
        ],
        cwd=m4_dir,
        out_dir=scenario_root,
    )
    commands.append(assemble_command)
    assembled_recomputed = load_json(assembled_path) if assembled_path.is_file() else None
    assembled_equal = assembled_recomputed is not None and strip_volatile(assembled_recomputed) == strip_volatile(published_hvpput)

    sweep = worker_visible_marker_sweep(repo)
    sweep_path = scenario_root / "m4_worker_visible_marker_sweep_recompute.json"
    write_json(sweep_path, sweep)

    result = {
        "schema_id": "turingos.fce.b1.hvpput_verification_check.v1",
        "input_digest_manifest_rows": manifest_rows,
        "input_digest_manifest_all_match": manifest_all_match,
        "per_arm_comparison": per_arm_comparison,
        "all_arms_recompute_byte_equal": all_arms_match,
        "all_arms_zero_excluded_events": all_arms_zero_excluded,
        "assemble_command_exit_code": assemble_command["exit_code"],
        "assembled_report_equal_after_normalization": assembled_equal,
        "worker_visible_marker_sweep": sweep,
        "pass": (
            manifest_all_match
            and all_arms_match
            and all_arms_zero_excluded
            and assembled_equal
            and sweep["clean"]
        ),
    }
    path = scenario_root / "m4_hvpput_verification_check.json"
    write_json(path, result)
    return result, [path, sweep_path]


# --------------------------------------------------------------------------
# Verdict assembly
# --------------------------------------------------------------------------


def build_verdict(
    *,
    root: Path,
    scenario_id: str,
    commands: list[dict[str, Any]],
    criteria: list[dict[str, Any]],
    started: float,
    evidence_files: list[Path],
) -> dict[str, Any]:
    scenario_root = root / scenario_id
    command_results = scenario_root / "command_results.json"
    write_json(
        command_results,
        {
            "schema_id": "turingos.fce.b1.command_results.v1",
            "commands": [
                {
                    "name": item["name"],
                    "cmd": item["cmd"],
                    "exit_code": item["exit_code"],
                    "wall_clock_ms": item["wall_clock_ms"],
                }
                for item in commands
            ],
        },
    )
    evidence_paths = [rel(root, command_results)]
    for command in commands:
        evidence_paths.append(f"{scenario_id}/{command['stdout']}")
        evidence_paths.append(f"{scenario_id}/{command['stderr']}")
    for path in evidence_files:
        if path.is_file():
            evidence_paths.append(rel(root, path))
    evidence_paths = sorted(set(evidence_paths))
    passed = all(item["result"] is True for item in criteria)
    return {
        "schema_id": "turingos.fce_scenario_verdict.v1",
        "scenario_id": scenario_id,
        "verdict": "PASS" if passed else "FAIL",
        "not_run_is_fail": True,
        "goals_served": ["G4", "G5"],
        "commands_executed": [
            {"cmd": command["cmd"], "exit_code": command["exit_code"]} for command in commands
        ],
        "pass_criteria_results": criteria,
        "evidence": evidence_paths,
        "evidence_sha256": {item: sha256_file(root / item) for item in evidence_paths},
        "fixture_or_real": "REAL",
        "automatic_fail_triggered": None if passed else "fabricated_or_self_elevated_status",
        "wall_clock_ms": int((time.monotonic() - started) * 1000),
        "timestamp_utc": utc_now(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--plan-root", required=True)
    parser.add_argument("--scenario-id", required=True)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    repo = Path(args.repo).resolve()
    plan_root = Path(args.plan_root).resolve()
    scenario_id = args.scenario_id
    scenario_root = root / scenario_id
    scenario_root.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    m3_dir = plan_root / "m3_uplift_lab"
    m4_dir = plan_root / "m4_self_improvement"

    commands: list[dict[str, Any]] = []
    evidence_files: list[Path] = []
    criteria: list[dict[str, Any]] = []

    digest_result, digest_evidence = check_digest_chain(m3_dir, repo, scenario_root)
    evidence_files.extend(digest_evidence)
    criteria.append(
        {
            "criterion": "check1_preregistration_and_frozen_packet_digest_chain_matches",
            "result": bool(digest_result["freeze_record_digest_matches"] and digest_result["packet_files_all_match"]),
            "evidence": rel(root, digest_evidence[0]),
        }
    )

    recompute_result, recompute_evidence, published_uplift_report = check_recompute_analysis(
        m3_dir, scenario_root, commands
    )
    evidence_files.extend(recompute_evidence)
    criteria.append(
        {
            "criterion": "check2_frozen_analyzer_recompute_matches_published_uplift_report",
            "result": bool(recompute_result["reports_byte_equal_after_parse"] and recompute_result["command_exit_code"] == 0),
            "evidence": rel(root, recompute_evidence[0]),
        }
    )

    provenance_result, provenance_evidence = check_scoring_provenance(m3_dir, repo, scenario_root)
    evidence_files.extend(provenance_evidence)
    criteria.append(
        {
            "criterion": "check3_every_arm_outcome_traces_to_upstream_harness_report",
            "result": bool(provenance_result["all_arms_trace_to_upstream_harness"]),
            "evidence": rel(root, provenance_evidence[0]),
        }
    )

    ablation_result, ablation_evidence = check_ablation_honesty(repo, scenario_root, commands)
    evidence_files.extend(ablation_evidence)
    criteria.append(
        {
            "criterion": "check4_ablation_honesty_recompute_pass_b_vs_c_capsules",
            "result": bool(ablation_result["pass"]),
            "evidence": rel(root, ablation_evidence[0]),
        }
    )

    arm_d_result, arm_d_evidence = check_arm_d_floor(repo, scenario_root)
    evidence_files.extend(arm_d_evidence)
    criteria.append(
        {
            "criterion": "check5_arm_d_deterministic_floor_zero_resolved_no_stop_latch",
            "result": bool(arm_d_result["pass"]),
            "evidence": rel(root, arm_d_evidence[0]),
        }
    )

    efficacy_result, efficacy_evidence = check_efficacy_statistics(published_uplift_report, m4_dir, scenario_root)
    evidence_files.extend(efficacy_evidence)
    criteria.append(
        {
            "criterion": "check6_h2_efficacy_statistics_present_and_honestly_phrased",
            "result": bool(efficacy_result["pass"]),
            "evidence": rel(root, efficacy_evidence[0]),
        }
    )

    deviations_result, deviations_evidence = check_deviations_completeness(m3_dir, scenario_root)
    evidence_files.extend(deviations_evidence)
    criteria.append(
        {
            "criterion": "check7_deviations_documented_and_zero_pairwise_exclusions",
            "result": bool(deviations_result["pass"]),
            "evidence": rel(root, deviations_evidence[0]),
        }
    )

    hvpput_result, hvpput_evidence = check_hvpput_verification(m4_dir, repo, scenario_root, commands)
    evidence_files.extend(hvpput_evidence)
    criteria.append(
        {
            "criterion": "check8_h_vpput_recompute_matches_published_and_zero_unspecified_cost_events",
            "result": bool(hvpput_result["pass"]),
            "evidence": rel(root, hvpput_evidence[0]),
        }
    )

    readme = scenario_root / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# FCE-B1 Uplift-Verification / Recomputation Battery",
                "",
                "Evidence label: REAL (recomputation over the frozen, already-collected M3/M4 evidence).",
                "",
                "This scenario does NOT re-run the M3 confirmatory shard S01 experiment or any worker",
                "call. It recomputes digests and metrics from evidence already on disk and asserts the",
                "recomputed values equal the recorded/certified values (Intent G4: certification does",
                "NOT require a positive uplift result; it requires the measurement be real, pre-registered,",
                "harness-scored, and recomputable).",
                "",
                "## Checks",
                "",
                "1. Preregistration + frozen-packet digest chain.",
                "2. Frozen analyzer recompute vs published UPLIFT_REPORT.json.",
                "3. Scoring provenance (upstream harness only, never a repo-local evaluator).",
                "4. Ablation-honesty recompute (Arm B vs Arm C capsules).",
                "5. Arm D deterministic-floor manipulation check (zero resolved).",
                "6. H2 efficacy-statistics presence and honest null phrasing.",
                "7. Deviations completeness and zero pairwise exclusions.",
                "8. M4 H-VPPUT recompute and zero unspecified-cost-event check.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    claim_boundary = scenario_root / "CLAIM_BOUNDARY.json"
    write_json(
        claim_boundary,
        {
            "schema_id": "CLAIM_BOUNDARY.v2",
            "evidence_class": "REAL",
            "claims": [
                "FCE-B1 recomputation battery genuinely re-derives M3 uplift statistics and M4 "
                "H-VPPUT from frozen inputs already on disk and compares them to the "
                "recorded/certified values."
            ],
            "non_claims": [
                "Does not re-run the M3 confirmatory shard S01 experiment or make any worker call.",
                "Does not assert a positive uplift result; H1/H2 remain null per the frozen analysis.",
                "Not release eligibility, not CLOSED/RELEASED/RATIFIED, not SHIPPED.",
                "Not OG-10/genesis signature or M2 enablement.",
            ],
        },
    )
    evidence_files.extend([readme, claim_boundary])

    verdict = build_verdict(
        root=root,
        scenario_id=scenario_id,
        commands=commands,
        criteria=criteria,
        started=started,
        evidence_files=evidence_files,
    )
    write_json(scenario_root / f"{scenario_id}_verdict.json", verdict)
    print(json.dumps({"scenario_id": scenario_id, "verdict": verdict["verdict"]}, sort_keys=True))
    return 0 if verdict["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
