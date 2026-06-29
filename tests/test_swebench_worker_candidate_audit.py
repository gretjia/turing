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


def write_candidate(root: Path, *, patch: str | None = None, integrity: str | None = None):
    task_dir = root / "shards/S00/tasks/django__django-10097"
    safe_dir = root / "shards/S00/ipqc/S00-W00/worker_safe_tasks/django__django-10097"
    task_dir.mkdir(parents=True, exist_ok=True)
    safe_dir.mkdir(parents=True, exist_ok=True)
    (safe_dir / "task_packet.json").write_text(json.dumps({"instance_id": "django__django-10097"}) + "\n")
    (safe_dir / "worker_capsule.md").write_text("# safe capsule\n")
    patch_text = patch or (
        "diff --git a/django/core/validators.py b/django/core/validators.py\n"
        "--- a/django/core/validators.py\n"
        "+++ b/django/core/validators.py\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
    )
    (task_dir / "candidate.patch").write_text(patch_text)
    receipt = {
        "status": "COMPLETED",
        "instance_id": "django__django-10097",
        "source_capsule_path": str((safe_dir / "worker_capsule.md").relative_to(root)),
        "candidate_patch_path": str((task_dir / "candidate.patch").relative_to(root)),
        "candidate_source": "worker_derived",
        "submitted_patch_scope": "source_only",
        "integrity_statement": integrity
        or "I read only the worker-safe task_packet.json and worker_capsule.md. I did not read raw SWE-bench dataset rows, dataset patches, test patches, FAIL_TO_PASS, PASS_TO_PASS, official solution hints, gold patches, or hidden evaluator labels.",
    }
    (task_dir / "worker_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")


def test_worker_candidate_audit_passes_source_only_worker_patch(tmp_path):
    auditor = load_module("candidate_auditor", REPO / "tools/bench/audit_worker_candidate_patch.py")
    root = tmp_path / "campaign"
    write_candidate(root)

    report = auditor.audit_candidate(root, "S00", "django__django-10097")

    assert report["status"] == "PASS"
    assert report["candidate_source"] == "worker_derived"
    assert report["submitted_patch_scope"] == "source_only"
    assert report["candidate_patch_sha256"].startswith("sha256:")
    assert (root / "shards/S00/tasks/django__django-10097/candidate.patch.sha256").exists()


def test_worker_candidate_audit_rejects_test_file_patch(tmp_path):
    auditor = load_module("candidate_auditor", REPO / "tools/bench/audit_worker_candidate_patch.py")
    root = tmp_path / "campaign"
    write_candidate(
        root,
        patch=(
            "diff --git a/tests/validators/tests.py b/tests/validators/tests.py\n"
            "--- a/tests/validators/tests.py\n"
            "+++ b/tests/validators/tests.py\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
        ),
    )

    report = auditor.audit_candidate(root, "S00", "django__django-10097")

    assert report["status"] == "FAIL"
    assert "candidate patch touches test path: tests/validators/tests.py" in report["problems"]


def test_worker_candidate_audit_rejects_missing_integrity_statement(tmp_path):
    auditor = load_module("candidate_auditor", REPO / "tools/bench/audit_worker_candidate_patch.py")
    root = tmp_path / "campaign"
    write_candidate(root, integrity="I made a patch.")

    report = auditor.audit_candidate(root, "S00", "django__django-10097")

    assert report["status"] == "FAIL"
    assert "integrity statement does not deny hidden/gold fields" in report["problems"]


def test_worker_candidate_audit_cli(tmp_path):
    root = tmp_path / "campaign"
    write_candidate(root)

    subprocess.run(
        [
            "python3",
            "tools/bench/audit_worker_candidate_patch.py",
            "--root",
            str(root),
            "--shard",
            "S00",
            "--instance-id",
            "django__django-10097",
        ],
        cwd=REPO,
        check=True,
    )

    assert (root / "shards/S00/tasks/django__django-10097/worker_candidate_audit.json").exists()
