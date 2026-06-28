#!/usr/bin/env python3
"""Audit the Phase F repair loop.

This auditor is intentionally conservative. It does not turn Phase F's
artifact-binding packet into an evaluator replay PASS. It checks whether the
known Stage16R blockers have been repaired by real replayable unified diffs.
If they have not, the correct result is BLOCKED with Phase G release disabled.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


FORBIDDEN_SECRET = [
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"(?i)(private[_-]?key|signing[_-]?seed|auth\.json|api[_-]?key)(\s*[:=]\s*)[A-Za-z0-9_./~:-]{6,}"),
]


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def relative_path(root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return root / path


def looks_like_unified_diff(path: Path) -> bool:
    text = path.read_text(errors="ignore")
    return text.startswith("diff --git ") and "\n--- " in text and "\n+++ " in text


def scan_secrets(root: Path) -> list[dict[str, str]]:
    problems: list[dict[str, str]] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix == ".bundle":
            continue
        text = path.read_text(errors="ignore")
        for pattern in FORBIDDEN_SECRET:
            match = pattern.search(text)
            if match:
                problems.append({"path": str(path), "match": match.group(0)[:80]})
    return problems


def phase_f_stage16r_targets(phase_f_root: Path) -> list[dict[str, Any]]:
    manifest = load_json(phase_f_root / "patch_manifest.json")
    targets = [
        item
        for item in manifest.get("patches", [])
        if isinstance(item, dict) and item.get("source_stage") == "Stage16R"
    ]
    return sorted(targets, key=lambda item: str(item.get("instance_id")))


def audit_phase_f_repair_loop(phase_f_root: Path, root: Path) -> dict[str, Any]:
    problems: list[str] = []
    source_audit = load_json(phase_f_root / "official_eval_replay_audit.json")
    claim = load_json(root / "CLAIM_BOUNDARY.json") if (root / "CLAIM_BOUNDARY.json").exists() else {}
    manifest = load_json(root / "repair_manifest.json") if (root / "repair_manifest.json").exists() else {}
    source_targets = phase_f_stage16r_targets(phase_f_root)
    source_ids = [str(item["instance_id"]) for item in source_targets]

    if source_audit.get("status") != "PARTIAL":
        problems.append("source Phase F audit must be PARTIAL before repair loop")
    if source_audit.get("release_next_phase_g") is not False:
        problems.append("source Phase F audit must block Phase G release")
    for key in [
        "full_swe_bench_score_claim_allowed",
        "full_dataset_claim_allowed",
        "leaderboard_equivalence_claim_allowed",
    ]:
        if claim.get(key) is not False:
            problems.append(f"{key} must be false")
    if claim.get("phase_g_release_allowed") is not False:
        problems.append("Phase G release must remain forbidden")
    if manifest.get("dataset_gold_patch_use_allowed") is not False:
        problems.append("gold patch shortcut must be forbidden")
    if manifest.get("old_microtape_immutable") is not True:
        problems.append("old MicroTape bundles must remain immutable")
    manifest_targets = manifest.get("repair_targets")
    if not isinstance(manifest_targets, list):
        manifest_targets = []
    manifest_ids = sorted(str(item.get("instance_id")) for item in manifest_targets if isinstance(item, dict))
    if manifest_ids != source_ids:
        problems.append("repair_manifest must contain exactly the Phase F Stage16R blocker targets")

    repair_targets: list[dict[str, Any]] = []
    replayable_count = 0
    for source in source_targets:
        instance_id = str(source["instance_id"])
        candidate_path = relative_path(phase_f_root, str(source.get("candidate_patch_path", "")))
        test_patch_path = relative_path(phase_f_root, str(source.get("test_patch_path", "")))
        candidate_exists = candidate_path.exists()
        test_exists = test_patch_path.exists()
        candidate_hash_ok = candidate_exists and sha256_file(candidate_path) == source.get("candidate_patch_sha256")
        test_hash_ok = test_exists and sha256_file(test_patch_path) == source.get("official_test_patch_sha256")
        candidate_unified = candidate_exists and looks_like_unified_diff(candidate_path)
        test_unified = test_exists and looks_like_unified_diff(test_patch_path)
        replayable = bool(candidate_hash_ok and test_hash_ok and candidate_unified and test_unified)
        if replayable:
            replayable_count += 1
        repair_targets.append(
            {
                "instance_id": instance_id,
                "source_phase_f_candidate_patch_path": str(candidate_path),
                "source_phase_f_test_patch_path": str(test_patch_path),
                "candidate_patch_hash_ok": candidate_hash_ok,
                "test_patch_hash_ok": test_hash_ok,
                "candidate_patch_is_unified_diff": candidate_unified,
                "test_patch_is_unified_diff": test_unified,
                "existing_artifacts_replayable": replayable,
                "old_microtape_immutable": True,
                "repair_strategy": "supersede_not_rewrite",
                "required_next_action": "fresh_stage16r_real_evaluator_bundle",
            }
        )

    secret_problems = scan_secrets(root)
    if secret_problems:
        problems.append("secret scan found credential-shaped values")

    if problems:
        status = "FAIL"
    elif replayable_count == len(source_targets):
        status = "PASS"
    else:
        status = "BLOCKED"

    return {
        "schema_id": "PhaseFRepairLoopAudit.v1",
        "status": status,
        "source_phase_f_status": source_audit.get("status"),
        "repair_target_count": len(source_targets),
        "replayable_repair_bundle_count": replayable_count,
        "release_next_phase_g": status == "PASS",
        "full_swe_bench_score_claim_allowed": False,
        "full_dataset_claim_allowed": False,
        "leaderboard_equivalence_claim_allowed": False,
        "gold_patch_shortcut_rejected": manifest.get("dataset_gold_patch_use_allowed") is False,
        "old_microtape_immutable": manifest.get("old_microtape_immutable") is True,
        "required_next_action": "phase_g_release" if status == "PASS" else "fresh_stage16r_real_evaluator_bundles",
        "blocked_by": [] if status == "PASS" else [
            "existing_stage16r_microtape_hashes_bind_non_replayable_fixture_text",
            "old_tape_cannot_be_rewritten_without_violating_immutable_evidence_boundary",
            "fresh worker-derived unified diffs and official evaluator logs are required",
        ],
        "problems": problems,
        "secret_scan_status": "PASS" if not secret_problems else "FAIL",
        "secret_scan_problems": secret_problems,
        "repair_targets": repair_targets,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase-f-root", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    report = audit_phase_f_repair_loop(Path(args.phase_f_root), Path(args.root))
    write_json(Path(args.out), report)
    return 0 if report["status"] in {"PASS", "BLOCKED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
