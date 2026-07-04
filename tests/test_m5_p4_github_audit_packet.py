from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "evidence/verification/m5_p4_module_closure_20260704"


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
