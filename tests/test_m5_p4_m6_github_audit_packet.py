from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "evidence/verification/m5_p4_m6_closure_20260704"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_m5_p4_m6_packet_is_self_contained_and_digest_bound() -> None:
    packet_json = PACKET / "PACKET.json"
    prompt = PACKET / "AUDITOR_PROMPT_TEMPLATE.md"
    manifest = PACKET / "PACKET_MANIFEST.sha256"
    source_map = PACKET / "SOURCE_MAP.json"
    repo_artifacts = PACKET / "REPO_ARTIFACTS.json"
    check = PACKET / "packet_checks/run_m6_g_rollup_check.sh"

    for path in [packet_json, prompt, manifest, source_map, repo_artifacts, check]:
        assert path.exists(), path

    packet = json.loads(packet_json.read_text(encoding="utf-8"))
    assert packet["schema_id"] == "turingos.m5.p4.github_module_closure_packet.v1"
    assert packet["packet_kind"] == "M5.P4_M6_MODULE_CLOSURE_GITHUB_PACKET"
    assert packet["audit_surface"] == "github_only"
    assert packet["target_branch"] == "hci/operator-console-v1-rebased"
    assert packet["targets"] == ["M6.G"]
    assert packet["status_ceiling"] == "ADDRESSED"
    assert packet["closure_certificate_schema_id"] == "turingos.closure_certificate.v1"
    assert packet["auditor_must_not_use"] == [
        "implementation chat",
        "local plan directory",
        "agent memory summaries",
        "uncommitted local files",
    ]
    assert packet["packet_local_checks"] == {
        "M6.G": "evidence/verification/m5_p4_m6_closure_20260704/packet_checks/run_m6_g_rollup_check.sh"
    }
    assert packet["gate_verdicts"]["M6.G"].endswith(
        "evidence/session_20260702/M6G_GATE_VERDICT.json"
    )

    source_entries = json.loads(source_map.read_text(encoding="utf-8"))
    source_paths = {entry["github_path"] for entry in source_entries}
    required_source_paths = {
        "evidence/verification/m5_p4_m6_closure_20260704/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/PROGRESS_TRACKER.md",
        "evidence/verification/m5_p4_m6_closure_20260704/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/memory/SESSION_STATE.md",
        "evidence/verification/m5_p4_m6_closure_20260704/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/modules/MODULE_M6_hci_console.md",
        "evidence/verification/m5_p4_m6_closure_20260704/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/modules/MODULE_M5_independent_verification.md",
        "evidence/verification/m5_p4_m6_closure_20260704/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/adr/ADR-M6-001-adopt-hci-a-projection-route.md",
        "evidence/verification/m5_p4_m6_closure_20260704/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/m5_verification/schemas/closure_certificate.v1.schema.json",
        "evidence/verification/m5_p4_m6_closure_20260704/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M6_P4_DYNAMIC_GATES_RESULT.json",
        "evidence/verification/m5_p4_m6_closure_20260704/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M6_P5_PROJECTION_INTEGRITY_RESULT.json",
        "evidence/verification/m5_p4_m6_closure_20260704/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M6G_ARTIFACT_ROLLUP.json",
        "evidence/verification/m5_p4_m6_closure_20260704/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M6G_GATE_VERDICT.json",
        "evidence/verification/m5_p4_m6_closure_20260704/plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M6G_M5_P4_HANDOFF_PACKET.json",
    }
    assert required_source_paths.issubset(source_paths)
    assert len(source_entries) >= 40
    for entry in source_entries:
        copied = ROOT / entry["github_path"]
        assert copied.exists(), copied
        assert sha256(copied) == entry["sha256"], copied

    repo_entries = json.loads(repo_artifacts.read_text(encoding="utf-8"))
    repo_paths = {entry["github_path"] for entry in repo_entries}
    required_repo_paths = {
        ".github/workflows/ci.yml",
        "crates/turing-cli/src/main.rs",
        "crates/turing-cli/tests/cli_gates.rs",
        "crates/turing-projection/src/lib.rs",
        "schemas/operator/operator_view_snapshot.v1.provenance.json",
        "tests/test_hci_no_write_gate.py",
        "tests/test_hci_projection_integrity.py",
        "tests/test_m5_p4_m6_github_audit_packet.py",
        "tools/hci/audit_projection_integrity.py",
        "tools/hci/gate_hci_no_write.sh",
        "tools/hci/make_fixture_micro_tape.py",
        "tools/hci/run_hci_gates.sh",
        "tools/release/build_m5_p4_m6_packet.py",
    }
    assert required_repo_paths.issubset(repo_paths)
    for entry in repo_entries:
        copied = ROOT / entry["github_path"]
        assert copied.exists(), copied
        assert sha256(copied) == entry["sha256"], copied

    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, rel = line.split(maxsplit=1)
        path = PACKET / rel
        assert path.exists(), path
        assert sha256(path) == digest, path

    subprocess.run([str(check)], cwd=ROOT, check=True)

    prompt_text = prompt.read_text(encoding="utf-8")
    assert "Do not use implementation chat" in prompt_text
    assert "M6.G" in prompt_text
    assert "ClosureCertificate.v1" in prompt_text
    assert "HCI-B" in prompt_text
    assert "M6.G is not externally verified by this packet" in prompt_text
