#!/usr/bin/env python3
"""FCE-S6: release-blocker mechanics negative test."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def run_command(
    *,
    name: str,
    argv: list[str],
    cwd: Path,
    out_dir: Path,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    proc = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    stdout = out_dir / f"{name}.stdout.txt"
    stderr = out_dir / f"{name}.stderr.txt"
    stdout.write_text(proc.stdout, encoding="utf-8")
    stderr.write_text(proc.stderr, encoding="utf-8")
    return {
        "name": name,
        "cmd": " ".join(argv),
        "exit_code": proc.returncode,
        "wall_clock_ms": elapsed_ms,
        "stdout": stdout.name,
        "stderr": stderr.name,
        "stdout_text": proc.stdout,
        "stderr_text": proc.stderr,
    }


def make_source_root(scenario_root: Path) -> Path:
    source = scenario_root / "source_root_FIXTURE"
    write_json(source / "receipt.json", {"schema_id": "Receipt.v1", "evidence_class": "FIXTURE"})
    write_json(source / "verdict.json", {"schema_id": "GateVerdict.v1", "verdict": "PASS"})
    write_json(
        source / "CLAIM_BOUNDARY.json",
        {
            "schema_id": "CLAIM_BOUNDARY.v2",
            "evidence_class": "FIXTURE",
            "claims": ["fixture release-mechanics packet only"],
            "non_claims": [
                "not an external certificate",
                "not a release decision",
                "not a real release-eligibility artifact",
            ],
        },
    )
    (source / "logs").mkdir(parents=True, exist_ok=True)
    (source / "logs" / "run.txt").write_text("fixture transcript\n", encoding="utf-8")
    return source


def certificate_payload(packet: Path, *, certificate_id: str) -> dict[str, Any]:
    manifest = json.loads((packet / "PACKET_MANIFEST.json").read_text(encoding="utf-8"))
    return {
        "schema_id": "turingos.closure_certificate.v1",
        "certificate_id": certificate_id,
        "subject": {
            "gate_id": manifest["gate_id"],
            "packet_sha256": manifest["packet_sha256"],
            "repo_sha": manifest["repo_sha"],
            "packet_manifest_files": manifest["packet_manifest_files"],
        },
        "verifier": {
            "kind": "external_cross_family_model",
            "operator_label": "external-fixture-verifier",
            "model_family": "grok",
            "credentials_class": "own_account",
            "custody": {
                "fresh_clone": True,
                "no_shared_conversation_state": True,
                "no_implementer_transcript": True,
                "own_credentials": True,
                "cross_family_or_human": True,
                "own_custody_output": True,
            },
        },
        "verification": {
            "inputs_checked": ["MANIFEST.sha256", "PACKET_MANIFEST.json"],
            "commands_run": [{"cmd": "sha256sum -c MANIFEST.sha256", "exit_code": 0}],
            "digest_manifest_result": "PASS",
            "gate_predicate_result": "PASS",
        },
        "verdict": "PASS",
        "verdict_enum": ["PASS", "FAIL"],
        "status_semantics": {
            "implementer_ceiling": "ADDRESSED",
            "this_certificate_confers": "EXTERNALLY_VERIFIED",
        },
        "anchoring": {
            "channel": "auditor_custody",
            "anchored_digest_reference": "fixture://fce-s6-positive-control",
        },
        "created_at_utc": "2026-07-04T00:00:00Z",
    }


def write_certificates(packet: Path, cert_dir: Path) -> dict[str, Path]:
    cert_dir.mkdir(parents=True, exist_ok=True)
    valid = certificate_payload(packet, certificate_id="cc-FCE-S6-valid-fixture")
    implementer = json.loads(json.dumps(valid))
    implementer["certificate_id"] = "cc-FCE-S6-implementer-family"
    implementer["verifier"]["operator_label"] = "codex-orchestrator"
    implementer["verifier"]["model_family"] = "gpt-5"
    mismatch = json.loads(json.dumps(valid))
    mismatch["certificate_id"] = "cc-FCE-S6-digest-mismatch"
    mismatch["subject"]["packet_sha256"] = "sha256:" + "0" * 64

    paths = {
        "valid": cert_dir / "cert_valid_FIXTURE.json",
        "implementer": cert_dir / "cert_implementer_family_FIXTURE.json",
        "mismatch": cert_dir / "cert_digest_mismatch_FIXTURE.json",
    }
    write_json(paths["valid"], valid)
    write_json(paths["implementer"], implementer)
    write_json(paths["mismatch"], mismatch)
    return paths


def build_verdict(
    *,
    root: Path,
    scenario_id: str,
    commands: list[dict[str, Any]],
    criteria: list[dict[str, Any]],
    started: float,
    extra_evidence: list[Path],
) -> dict[str, Any]:
    scenario_root = root / scenario_id
    sanitized_commands = [
        {
            "name": item["name"],
            "cmd": item["cmd"],
            "exit_code": item["exit_code"],
            "wall_clock_ms": item["wall_clock_ms"],
        }
        for item in commands
    ]
    command_results = scenario_root / "command_results.json"
    write_json(
        command_results,
        {"schema_id": "turingos.fce.s6.command_results.v1", "commands": sanitized_commands},
    )

    evidence_paths = [rel(root, command_results)]
    for command in commands:
        evidence_paths.append(f"{scenario_id}/{command['stdout']}")
        evidence_paths.append(f"{scenario_id}/{command['stderr']}")
    for path in extra_evidence:
        if path.is_file():
            evidence_paths.append(rel(root, path))
    evidence_paths = sorted(set(evidence_paths))
    evidence_sha = {item: sha256_file(root / item) for item in evidence_paths}
    passed = all(item["result"] is True for item in criteria)
    return {
        "schema_id": "turingos.fce_scenario_verdict.v1",
        "scenario_id": scenario_id,
        "verdict": "PASS" if passed else "FAIL",
        "not_run_is_fail": True,
        "goals_served": ["G6"],
        "commands_executed": [
            {"cmd": command["cmd"], "exit_code": command["exit_code"]} for command in commands
        ],
        "pass_criteria_results": criteria,
        "evidence": evidence_paths,
        "evidence_sha256": evidence_sha,
        "fixture_or_real": "FIXTURE",
        "automatic_fail_triggered": None,
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

    build_packet = repo / "tools" / "release" / "build_packet.sh"
    release_gate = repo / "tools" / "release" / "assert_release_eligible.sh"
    validator = plan_root / "m5_verification" / "tools" / "validate_closure_certificate.py"
    env = dict(os.environ)
    env["M5_VALIDATOR"] = str(validator)

    repo_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    (scenario_root / "repo_head.txt").write_text(repo_sha + "\n", encoding="utf-8")
    source_root = make_source_root(scenario_root)
    packet = scenario_root / "packet_valid_FIXTURE"

    commands: list[dict[str, Any]] = []
    commands.append(
        run_command(
            name="build_fixture_packet",
            argv=[
                str(build_packet),
                "--root",
                str(source_root),
                "--sha",
                repo_sha,
                "--gate",
                "M5.P5.FIXTURE",
                "--out",
                str(packet),
            ],
            cwd=repo,
            out_dir=scenario_root,
            env=env,
        )
    )
    commands.append(
        run_command(
            name="packet_manifest_check",
            argv=["sha256sum", "-c", "MANIFEST.sha256"],
            cwd=packet,
            out_dir=scenario_root,
            env=env,
        )
    )
    commands.append(
        run_command(
            name="packet_validate",
            argv=[str(build_packet), "--validate", str(packet)],
            cwd=repo,
            out_dir=scenario_root,
            env=env,
        )
    )

    tampered = scenario_root / "packet_tampered_FIXTURE"
    shutil.copytree(packet, tampered)
    (tampered / "evidence" / "receipt.json").write_text("tampered\n", encoding="utf-8")
    commands.append(
        run_command(
            name="packet_tamper_rejected",
            argv=[str(build_packet), "--validate", str(tampered)],
            cwd=repo,
            out_dir=scenario_root,
            env=env,
        )
    )

    removed_key = scenario_root / "packet_removed_key_FIXTURE"
    shutil.copytree(packet, removed_key)
    removed_manifest = json.loads((removed_key / "PACKET_MANIFEST.json").read_text(encoding="utf-8"))
    removed_manifest["release_next_stage"] = "YES"
    write_json(removed_key / "PACKET_MANIFEST.json", removed_manifest)
    commands.append(
        run_command(
            name="packet_removed_key_rejected",
            argv=[str(build_packet), "--validate", str(removed_key)],
            cwd=repo,
            out_dir=scenario_root,
            env=env,
        )
    )

    certs = write_certificates(packet, scenario_root / "certs")
    eligible = scenario_root / "RELEASE_ELIGIBLE_FIXTURE.json"
    commands.append(
        run_command(
            name="release_missing_cert_refused",
            argv=[str(release_gate), "--packet", str(packet), "--cert", str(scenario_root / "missing_cert.json")],
            cwd=repo,
            out_dir=scenario_root,
            env=env,
        )
    )
    commands.append(
        run_command(
            name="release_implementer_family_refused",
            argv=[str(release_gate), "--packet", str(packet), "--cert", str(certs["implementer"])],
            cwd=repo,
            out_dir=scenario_root,
            env=env,
        )
    )
    commands.append(
        run_command(
            name="release_digest_mismatch_refused",
            argv=[str(release_gate), "--packet", str(packet), "--cert", str(certs["mismatch"])],
            cwd=repo,
            out_dir=scenario_root,
            env=env,
        )
    )
    commands.append(
        run_command(
            name="release_positive_fixture_control",
            argv=[
                str(release_gate),
                "--packet",
                str(packet),
                "--cert",
                str(certs["valid"]),
                "--out",
                str(eligible),
            ],
            cwd=repo,
            out_dir=scenario_root,
            env=env,
        )
    )

    by_name = {command["name"]: command for command in commands}
    criteria = [
        {
            "criterion": "fixture_packet_built",
            "result": by_name["build_fixture_packet"]["exit_code"] == 0,
            "evidence": f"{scenario_id}/build_fixture_packet.stdout.txt",
        },
        {
            "criterion": "packet_manifest_verified",
            "result": by_name["packet_manifest_check"]["exit_code"] == 0,
            "evidence": f"{scenario_id}/packet_manifest_check.stdout.txt",
        },
        {
            "criterion": "packet_validate_pass",
            "result": by_name["packet_validate"]["exit_code"] == 0,
            "evidence": f"{scenario_id}/packet_validate.stdout.txt",
        },
        {
            "criterion": "tampered_packet_rejected",
            "result": by_name["packet_tamper_rejected"]["exit_code"] != 0
            and "manifest_digest_mismatch" in by_name["packet_tamper_rejected"]["stdout_text"],
            "evidence": f"{scenario_id}/packet_tamper_rejected.stdout.txt",
        },
        {
            "criterion": "removed_legacy_key_rejected",
            "result": by_name["packet_removed_key_rejected"]["exit_code"] != 0
            and "removed_legacy_key:release_next_stage" in by_name["packet_removed_key_rejected"]["stdout_text"],
            "evidence": f"{scenario_id}/packet_removed_key_rejected.stdout.txt",
        },
        {
            "criterion": "missing_certificate_refused",
            "result": by_name["release_missing_cert_refused"]["exit_code"] != 0
            and "certificate_missing" in by_name["release_missing_cert_refused"]["stdout_text"],
            "evidence": f"{scenario_id}/release_missing_cert_refused.stdout.txt",
        },
        {
            "criterion": "implementer_family_refused",
            "result": by_name["release_implementer_family_refused"]["exit_code"] != 0
            and "verifier_" in by_name["release_implementer_family_refused"]["stdout_text"],
            "evidence": f"{scenario_id}/release_implementer_family_refused.stdout.txt",
        },
        {
            "criterion": "digest_mismatch_refused",
            "result": by_name["release_digest_mismatch_refused"]["exit_code"] != 0
            and "subject_digest_mismatch" in by_name["release_digest_mismatch_refused"]["stdout_text"],
            "evidence": f"{scenario_id}/release_digest_mismatch_refused.stdout.txt",
        },
        {
            "criterion": "positive_fixture_control_accepted",
            "result": by_name["release_positive_fixture_control"]["exit_code"] == 0 and eligible.is_file(),
            "evidence": f"{scenario_id}/release_positive_fixture_control.stdout.txt",
        },
    ]
    extra_evidence = [
        scenario_root / "repo_head.txt",
        source_root / "CLAIM_BOUNDARY.json",
        packet / "PACKET_MANIFEST.json",
        packet / "MANIFEST.sha256",
        packet / "CLAIM_BOUNDARY.json",
        certs["valid"],
        certs["implementer"],
        certs["mismatch"],
        eligible,
    ]
    write_json(
        scenario_root / "CLAIM_BOUNDARY.json",
        {
            "schema_id": "CLAIM_BOUNDARY.v2",
            "evidence_class": "FIXTURE",
            "claims": [
                "FCE-S6 exercises release-blocker mechanics with fixture packets and fixture certificates"
            ],
            "non_claims": [
                "not a real release decision",
                "not SHIPPED",
                "not RELEASED",
                "not release eligible for the program",
                "not an external audit of the FCE packet",
            ],
        },
    )
    extra_evidence.append(scenario_root / "CLAIM_BOUNDARY.json")
    readme_path = scenario_root / "README.md"
    readme_path.write_text(
        "\n".join(
            [
                "# FCE-S6 Release-Blocker Mechanics Negative Test",
                "",
                "Evidence label: FIXTURE.",
                "This scenario exercises release-gate refusal paths (missing certificate,",
                "implementer-family verifier, digest mismatch, tampered packet, removed",
                "legacy manifest key) plus one positive fixture control, all against",
                "fixture packets and fixture certificates built under this scenario root.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    extra_evidence.append(readme_path)
    verdict = build_verdict(
        root=root,
        scenario_id=scenario_id,
        commands=commands,
        criteria=criteria,
        started=started,
        extra_evidence=extra_evidence,
    )
    write_json(scenario_root / f"{scenario_id}_verdict.json", verdict)
    return 0 if verdict["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
