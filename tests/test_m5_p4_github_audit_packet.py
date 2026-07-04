from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "evidence/verification/m5_p4_module_closure_20260704"
REPAIR_PACKET = ROOT / "evidence/verification/m5_p4_module_closure_20260704_r2"
PASS_CERT = ROOT / "evidence/verification/m5_p4_module_closure_20260704_r2_external_pass/M5_P4_GROK_PASS_CERTIFICATE.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_m5_p4_github_packet_is_self_contained_and_digest_bound() -> None:
    packet_json = PACKET / "PACKET.json"
    prompt = PACKET / "AUDITOR_PROMPT_TEMPLATE.md"
    manifest = PACKET / "PACKET_MANIFEST.sha256"
    source_map = PACKET / "SOURCE_MAP.json"

    assert packet_json.exists()
    assert prompt.exists()
    assert manifest.exists()
    assert source_map.exists()

    packet = json.loads(packet_json.read_text(encoding="utf-8"))
    assert packet["schema_id"] == "turingos.m5.p4.github_module_closure_packet.v1"
    assert packet["packet_kind"] == "M5.P4_MODULE_CLOSURE_GITHUB_PACKET"
    assert packet["audit_surface"] == "github_only"
    assert packet["target_branch"] == "goal/mini-swe-bench-grok-worker"
    assert packet["targets"] == ["M3.G", "M4.G"]
    assert packet["status_ceiling"] == "ADDRESSED"
    assert packet["auditor_must_not_use"] == [
        "implementation chat",
        "local plan directory",
        "agent memory summaries",
        "uncommitted local files",
    ]
    assert packet["closure_certificate_schema_id"] == "turingos.closure_certificate.v1"

    source_entries = json.loads(source_map.read_text(encoding="utf-8"))
    assert len(source_entries) >= 70
    for entry in source_entries:
        copied = ROOT / entry["github_path"]
        assert copied.exists(), copied
        assert sha256(copied) == entry["sha256"], copied

    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, rel = line.split(maxsplit=1)
        path = PACKET / rel
        assert path.exists(), path
        assert sha256(path) == digest, path

    text = prompt.read_text(encoding="utf-8")
    assert "Do not use implementation chat" in text
    assert "M3.G" in text and "M4.G" in text
    assert "ClosureCertificate.v1" in text


def test_m5_p4_repair_packet_includes_external_fail_and_missing_rerun_inputs() -> None:
    packet_json = REPAIR_PACKET / "PACKET.json"
    manifest = REPAIR_PACKET / "PACKET_MANIFEST.sha256"
    source_map = REPAIR_PACKET / "SOURCE_MAP.json"
    fail_cert = REPAIR_PACKET / "prior_audit/M5_P4_GROK_FAIL_CERTIFICATE.json"
    m3_rerun = REPAIR_PACKET / "packet_checks/run_m3_analysis_recheck.sh"
    m4_rerun = REPAIR_PACKET / "packet_checks/run_m4_p3_northstar_check.sh"

    assert packet_json.exists()
    assert manifest.exists()
    assert source_map.exists()
    assert fail_cert.exists()
    assert m3_rerun.exists()
    assert m4_rerun.exists()

    packet = json.loads(packet_json.read_text(encoding="utf-8"))
    assert packet["schema_id"] == "turingos.m5.p4.github_module_closure_packet.v1"
    assert packet["packet_kind"] == "M5.P4_MODULE_CLOSURE_GITHUB_PACKET"
    assert packet["repair_of_packet_root"] == "evidence/verification/m5_p4_module_closure_20260704"
    assert packet["prior_audit_verdict"] == "FAIL"
    assert packet["targets"] == ["M3.G", "M4.G"]

    cert = json.loads(fail_cert.read_text(encoding="utf-8"))
    assert cert["schema_id"] == "turingos.closure_certificate.v1"
    assert cert["verdict"] == "FAIL"
    reason_codes = {reason["code"] for reason in cert["reasons"]}
    assert reason_codes == {
        "M3_MISSING_ANALYSIS_REEXECUTION_INPUTS",
        "M4_MISSING_P3_ARTIFACT_MANIFEST",
    }

    source_entries = json.loads(source_map.read_text(encoding="utf-8"))
    github_paths = {entry["github_path"] for entry in source_entries}
    required_paths = {
        "evidence/verification/m5_p4_module_closure_20260704_r2/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/m3_uplift_lab/analysis/s01_deepseek_only_20260703/ANALYSIS_INPUT_DERIVATION_RECORD.json",
        "evidence/verification/m5_p4_module_closure_20260704_r2/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/m3_uplift_lab/analysis/s01_deepseek_only_20260703/scoring/deepseek-v4-pro__same-provider-source-context-worker_armA/evaluation_results.json",
        "evidence/verification/m5_p4_module_closure_20260704_r2/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/m3_uplift_lab/analysis/s01_deepseek_only_20260703/scoring/deepseek-v4-pro__same-provider-source-context-worker_armB/evaluation_results.json",
        "evidence/verification/m5_p4_module_closure_20260704_r2/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/m3_uplift_lab/analysis/s01_deepseek_only_20260703/scoring/deepseek-v4-pro__same-provider-source-context-worker_armC/evaluation_results.json",
        "evidence/verification/m5_p4_module_closure_20260704_r2/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/m4_self_improvement/M4_P3_NORTHSTAR_ARTIFACTS.sha256",
    }
    assert required_paths.issubset(github_paths)

    for entry in source_entries:
        copied = ROOT / entry["github_path"]
        assert copied.exists(), copied
        assert sha256(copied) == entry["sha256"], copied

    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, rel = line.split(maxsplit=1)
        path = REPAIR_PACKET / rel
        assert path.exists(), path
        assert sha256(path) == digest, path

    subprocess.run([str(m3_rerun)], cwd=ROOT, check=True)
    subprocess.run([str(m4_rerun)], cwd=ROOT, check=True)

    prompt = (REPAIR_PACKET / "AUDITOR_PROMPT_TEMPLATE.md").read_text(encoding="utf-8")
    assert "packet_checks/run_m3_analysis_recheck.sh" in prompt
    assert "packet_checks/run_m4_p3_northstar_check.sh" in prompt


def test_m5_p4_external_pass_certificate_is_narrow_and_custody_separated() -> None:
    assert PASS_CERT.exists()
    cert = json.loads(PASS_CERT.read_text(encoding="utf-8"))

    assert cert["schema_id"] == "turingos.closure_certificate.v1"
    assert cert["verdict"] == "PASS"
    assert cert["subject"]["gate_id"] == "M5.P4"
    assert cert["subject"]["module_targets"] == ["M3.G", "M4.G"]
    assert cert["subject"]["repo_url"] == "https://github.com/gretjia/turing"
    assert cert["subject"]["branch"] == "goal/mini-swe-bench-grok-worker"
    assert cert["subject"]["commit_sha"] == "1b54ca40820294e56fb4218946531633cf180745"
    assert cert["subject"]["packet_root"] == "evidence/verification/m5_p4_module_closure_20260704_r2"

    assert cert["verifier"]["kind"] == "external_cross_family_model"
    assert cert["verifier"]["identity"] == "grok-cursor-external-auditor"
    assert all(cert["verifier"]["custody"].values())

    semantics = cert["status_semantics"]
    assert semantics["certified_closure_level"] == "EXTERNALLY_VERIFIED"
    assert semantics["certified_for_module_targets"] == ["M3.G", "M4.G"]
    assert semantics["implementer_ceiling_was"] == "ADDRESSED"
    assert {
        "SHIPPED",
        "RELEASED",
        "RATIFIED",
        "M2 enablement",
        "release eligibility",
        "OG-10/genesis signature",
        "constitution-byte change",
    }.issubset(set(semantics["does_not_grant"]))

    verification = cert["verification"]
    assert verification["digest_manifest_result"] == "PASS"
    assert verification["gate_predicate_result"] == "PASS"
    commands = verification["commands_run"]
    assert commands
    assert all(command["exit_code"] == 0 for command in commands)
    command_text = "\n".join(command["command"] for command in commands)
    assert "sha256sum -c PACKET_MANIFEST.sha256" in command_text
    assert "packet_checks/run_m3_analysis_recheck.sh" in command_text
    assert "packet_checks/run_m4_p3_northstar_check.sh" in command_text

    assert "M5.P3" not in cert["subject"]["module_targets"]
    assert "FCE.RUN" not in cert["subject"]["module_targets"]
