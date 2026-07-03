import importlib.util
import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_safe_task(root: Path, *, capsule_text: str = "Use only this packet.\n", extra_packet: dict | None = None):
    task_dir = root / "shards/S00/ipqc/S00-W00/worker_safe_tasks/django__django-10097"
    task_dir.mkdir(parents=True, exist_ok=True)
    packet = {
        "schema_id": "turingos.swebench_worker_safe_task_packet.v1",
        "instance_id": "django__django-10097",
        "visible_to_worker": True,
        "restricted_source_fields_removed": True,
        "candidate_source_policy": "worker_derived_patch_only",
        "problem_statement": "Fix URL validation.",
    }
    if extra_packet:
        packet.update(extra_packet)
    (task_dir / "task_packet.json").write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n")
    (task_dir / "worker_capsule.md").write_text(capsule_text, encoding="utf-8")


def test_worker_safe_task_packet_audit_passes_clean_packet_tree(tmp_path):
    auditor = load_module("safe_task_audit", REPO / "tools/bench/audit_worker_safe_task_packets.py")
    root = tmp_path / "campaign"
    write_safe_task(root)

    report = auditor.audit_worker_safe_tasks(root, "S00", "S00-W00")

    assert report["status"] == "PASS"
    assert report["packet_count"] == 1
    assert report["problems"] == []


def test_worker_safe_task_packet_audit_rejects_forbidden_keys_and_visible_markers(tmp_path):
    auditor = load_module("safe_task_audit", REPO / "tools/bench/audit_worker_safe_task_packets.py")
    root = tmp_path / "campaign"
    write_safe_task(root, capsule_text="Do not use the official solution.\n", extra_packet={"test_patch": "hidden"})

    report = auditor.audit_worker_safe_tasks(root, "S00", "S00-W00")

    assert report["status"] == "FAIL"
    assert "django__django-10097 forbidden packet key: test_patch" in report["problems"]
    assert "django__django-10097 visible capsule marker: official solution" in report["problems"]


def test_worker_safe_task_packet_audit_cli_writes_report(tmp_path):
    root = tmp_path / "campaign"
    out = tmp_path / "audit.json"
    write_safe_task(root)

    subprocess.run(
        [
            "python3",
            "tools/bench/audit_worker_safe_task_packets.py",
            "--root",
            str(root),
            "--shard",
            "S00",
            "--window",
            "S00-W00",
            "--out",
            str(out),
        ],
        cwd=REPO,
        check=True,
    )

    assert json.loads(out.read_text(encoding="utf-8"))["status"] == "PASS"
