from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORK_ROOT = REPO_ROOT.parent
PLAN_ROOT = WORK_ROOT / "PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702"
VALIDATOR = PLAN_ROOT / "m5_verification/tools/validate_closure_certificate.py"
BUILD_PACKET = REPO_ROOT / "tools/release/build_packet.sh"
ASSERT_ELIGIBLE = REPO_ROOT / "tools/release/assert_release_eligible.sh"
REPO_SHA = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()


def run_cmd(argv: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["M5_VALIDATOR"] = str(VALIDATOR)
    return subprocess.run(argv, cwd=cwd or REPO_ROOT, env=env, text=True, capture_output=True)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return "sha256:" + h.hexdigest()


def make_evidence_root(tmp_path: Path) -> Path:
    root = tmp_path / "evidence_root"
    write_json(root / "receipt.json", {"schema_id": "Receipt.v1", "evidence_class": "FIXTURE"})
    write_json(root / "verdict.json", {"schema_id": "GateVerdict.v1", "verdict": "PASS"})
    write_json(
        root / "CLAIM_BOUNDARY.json",
        {
            "schema_id": "CLAIM_BOUNDARY.v2",
            "evidence_class": "FIXTURE",
            "claims": ["fixture release-mechanics packet only"],
            "non_claims": ["not an external certificate"],
        },
    )
    (root / "logs").mkdir()
    (root / "logs/run.txt").write_text("fixture transcript\n", encoding="utf-8")
    return root


def build_fixture_packet(tmp_path: Path) -> Path:
    source = make_evidence_root(tmp_path)
    out = tmp_path / "packet"
    proc = run_cmd(
        [
            str(BUILD_PACKET),
            "--root",
            str(source),
            "--sha",
            REPO_SHA,
            "--gate",
            "M5.P5.FIXTURE",
            "--out",
            str(out),
        ]
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    summary = json.loads(proc.stdout)
    assert summary["schema_id"] == "turingos.release_packet.build.v1"
    assert summary["packet_dir"] == str(out)
    assert summary["packet_sha256"].startswith("sha256:")
    return out


def valid_certificate(packet: Path, tmp_path: Path, **overrides: object) -> Path:
    manifest = json.loads((packet / "PACKET_MANIFEST.json").read_text(encoding="utf-8"))
    cert = {
        "schema_id": "turingos.closure_certificate.v1",
        "certificate_id": "cc-M5P5-fixture",
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
            "anchored_digest_reference": "fixture://m5-p5-positive-control",
        },
        "created_at_utc": "2026-07-03T00:00:00Z",
    }
    for dotted_key, value in overrides.items():
        target = cert
        parts = dotted_key.split("__")
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = value
    cert_path = tmp_path / f"{overrides.get('certificate_id', 'cert')}.json"
    write_json(cert_path, cert)
    return cert_path


def test_build_packet_closes_manifest_and_rejects_tamper_and_removed_keys(tmp_path: Path) -> None:
    packet = build_fixture_packet(tmp_path)

    manifest = json.loads((packet / "PACKET_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["schema_id"] == "turingos.release_packet.v1"
    assert manifest["gate_id"] == "M5.P5.FIXTURE"
    assert manifest["repo_sha"] == REPO_SHA
    assert "release_next_stage" not in manifest
    assert "evidence/receipt.json" in manifest["required_artifacts"]
    assert "REEXECUTION.md" in manifest["required_artifacts"]

    sha_proc = run_cmd(["sha256sum", "-c", "MANIFEST.sha256"], cwd=packet)
    assert sha_proc.returncode == 0, sha_proc.stderr + sha_proc.stdout

    validate_proc = run_cmd([str(BUILD_PACKET), "--validate", str(packet)])
    assert validate_proc.returncode == 0, validate_proc.stderr + validate_proc.stdout
    assert json.loads(validate_proc.stdout)["verdict"] == "PASS"

    (packet / "evidence/receipt.json").write_text("tampered\n", encoding="utf-8")
    tamper_proc = run_cmd([str(BUILD_PACKET), "--validate", str(packet)])
    assert tamper_proc.returncode != 0
    assert "manifest_digest_mismatch" in tamper_proc.stdout

    packet = build_fixture_packet(tmp_path / "removed_key_case")
    manifest_path = packet / "PACKET_MANIFEST.json"
    removed_key_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    removed_key_manifest["release_next_stage"] = "YES"
    write_json(manifest_path, removed_key_manifest)
    removed_key_proc = run_cmd([str(BUILD_PACKET), "--validate", str(packet)])
    assert removed_key_proc.returncode != 0
    assert "removed_legacy_key:release_next_stage" in removed_key_proc.stdout


def test_build_packet_can_include_custom_reexecution_and_auditor_runbook(tmp_path: Path) -> None:
    source = make_evidence_root(tmp_path)
    reexecution = tmp_path / "custom_REEXECUTION.md"
    runbook = tmp_path / "custom_AUDITOR_RUNBOOK.md"
    reexecution.write_text(
        "# REEXECUTION - custom gate\n\n"
        "1. Compute your verdict before reading historical EXPECTED_VERDICT text.\n"
        "2. `sha256sum -c MANIFEST.sha256` must exit 0.\n",
        encoding="utf-8",
    )
    runbook.write_text(
        "# AUDITOR_RUNBOOK - custom gate\n\n"
        "Use the packet only; do not use implementer chat or local working trees.\n",
        encoding="utf-8",
    )
    out = tmp_path / "custom_packet"

    proc = run_cmd(
        [
            str(BUILD_PACKET),
            "--root",
            str(source),
            "--sha",
            REPO_SHA,
            "--gate",
            "M5.P3",
            "--out",
            str(out),
            "--reexecution-template",
            str(reexecution),
            "--auditor-runbook-template",
            str(runbook),
        ]
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout

    manifest = json.loads((out / "PACKET_MANIFEST.json").read_text(encoding="utf-8"))
    assert "REEXECUTION.md" in manifest["required_artifacts"]
    assert "AUDITOR_RUNBOOK.md" in manifest["required_artifacts"]
    assert (out / "REEXECUTION.md").read_text(encoding="utf-8") == reexecution.read_text(encoding="utf-8")
    assert (out / "AUDITOR_RUNBOOK.md").read_text(encoding="utf-8") == runbook.read_text(encoding="utf-8")

    validate_proc = run_cmd([str(BUILD_PACKET), "--validate", str(out)])
    assert validate_proc.returncode == 0, validate_proc.stderr + validate_proc.stdout


def test_assert_release_eligible_refuses_bad_inputs_and_writes_positive_control(tmp_path: Path) -> None:
    packet = build_fixture_packet(tmp_path)

    missing_cert_proc = run_cmd(
        [str(ASSERT_ELIGIBLE), "--packet", str(packet), "--cert", str(tmp_path / "missing.json")]
    )
    assert missing_cert_proc.returncode != 0
    assert "certificate_missing" in missing_cert_proc.stdout

    implementer_cert = valid_certificate(
        packet,
        tmp_path,
        verifier__operator_label="codex-orchestrator",
        verifier__model_family="gpt-5",
        certificate_id="cert-implementer-family",
    )
    implementer_proc = run_cmd([str(ASSERT_ELIGIBLE), "--packet", str(packet), "--cert", str(implementer_cert)])
    assert implementer_proc.returncode != 0
    assert "verifier_" in implementer_proc.stdout

    mismatch_cert = valid_certificate(
        packet,
        tmp_path,
        subject__packet_sha256="sha256:" + "0" * 64,
        certificate_id="cert-digest-mismatch",
    )
    mismatch_proc = run_cmd([str(ASSERT_ELIGIBLE), "--packet", str(packet), "--cert", str(mismatch_cert)])
    assert mismatch_proc.returncode != 0
    assert "subject_digest_mismatch" in mismatch_proc.stdout

    cert = valid_certificate(packet, tmp_path, certificate_id="cert-valid-fixture")
    out = tmp_path / "RELEASE_ELIGIBLE.json"
    positive_proc = run_cmd(
        [str(ASSERT_ELIGIBLE), "--packet", str(packet), "--cert", str(cert), "--out", str(out)]
    )
    assert positive_proc.returncode == 0, positive_proc.stderr + positive_proc.stdout
    summary = json.loads(positive_proc.stdout)
    eligible = json.loads(out.read_text(encoding="utf-8"))
    manifest = json.loads((packet / "PACKET_MANIFEST.json").read_text(encoding="utf-8"))
    assert summary["verdict"] == "PASS"
    assert eligible == {
        "schema_id": "turingos.release_eligible.v1",
        "eligible": True,
        "certificate_sha256": sha256_path(cert),
        "packet_sha256": manifest["packet_sha256"],
    }
