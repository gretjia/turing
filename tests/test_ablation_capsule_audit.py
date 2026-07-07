from __future__ import annotations

import importlib.util
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
AUDIT = REPO / "tools" / "bench" / "audit_ablation_capsules.py"


def load_audit():
    spec = importlib.util.spec_from_file_location("audit_ablation_capsules", AUDIT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_capsule(root: Path, instance_id: str, body: str) -> Path:
    path = root / instance_id / "worker_visible_capsule.md"
    path.parent.mkdir(parents=True)
    path.write_text(body, encoding="utf-8")
    return path


def capsule_with_rules(rule_body: str) -> str:
    return (
        "# Capsule\n"
        "Shared text\n\n"
        "## TuringOS Failure-Memory Broadcast Rules\n"
        "<!-- BEGIN_TURINGOS_BROADCAST_RULES -->\n"
        f"{rule_body}\n"
        "<!-- END_TURINGOS_BROADCAST_RULES -->\n\n"
        "Source context\n"
    )


def test_ablation_audit_passes_when_only_broadcast_section_differs(tmp_path):
    audit = load_audit()
    arm_b = tmp_path / "B"
    arm_c = tmp_path / "C"
    write_capsule(arm_b, "repo__task-1", capsule_with_rules("- FORMAT: fix diff"))
    write_capsule(arm_c, "repo__task-1", capsule_with_rules("(none)"))

    report = audit.audit_capsules(arm_b, arm_c)

    assert report["status"] == "PASS"
    assert report["capsule_count"] == 1


def test_ablation_audit_fails_on_non_broadcast_diff(tmp_path):
    audit = load_audit()
    arm_b = tmp_path / "B"
    arm_c = tmp_path / "C"
    write_capsule(arm_b, "repo__task-1", capsule_with_rules("- FORMAT: fix diff"))
    write_capsule(arm_c, "repo__task-1", capsule_with_rules("(none)").replace("Shared text", "Changed text"))

    report = audit.audit_capsules(arm_b, arm_c)

    assert report["status"] == "FAIL"
    assert "capsule diff outside broadcast section" in report["problems"][0]
