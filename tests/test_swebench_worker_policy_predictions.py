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


def write_jsonl(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_worker_policy_lint_accepts_worker_arm_experiment_model_names(tmp_path):
    auditor = load_module("worker_policy", REPO / "tools/bench/audit_worker_policy_predictions.py")
    predictions = tmp_path / "predictions.jsonl"
    write_jsonl(
        predictions,
        [
            {
                "instance_id": "django__django-10097",
                "model_name_or_path": "deepseek-v4-flash__armA__uplift-s01",
                "model_patch": "diff --git a/a.py b/a.py\n",
            },
            {
                "instance_id": "astropy__astropy-12907",
                "model_name_or_path": "gpt-5.4-nano__armB__uplift-s01",
                "model_patch": "",
            },
        ],
    )

    report = auditor.audit_prediction_files([predictions])

    assert report["status"] == "PASS"
    assert report["row_count"] == 2
    assert report["problems"] == []


def test_worker_policy_lint_rejects_placeholders_and_malformed_names(tmp_path):
    auditor = load_module("worker_policy", REPO / "tools/bench/audit_worker_policy_predictions.py")
    predictions = tmp_path / "predictions.jsonl"
    write_jsonl(
        predictions,
        [
            {
                "instance_id": "django__django-10097",
                "model_name_or_path": "turingos-internal-rehearsal",
                "model_patch": "",
            },
            {
                "instance_id": "astropy__astropy-12907",
                "model_name_or_path": "deepseek-v4-flash",
                "model_patch": "",
            },
        ],
    )

    report = auditor.audit_prediction_files([predictions])

    assert report["status"] == "FAIL"
    assert "predictions.jsonl:1 placeholder model_name_or_path: turingos-internal-rehearsal" in report["problems"]
    assert "predictions.jsonl:2 model_name_or_path must match worker__arm__experiment: deepseek-v4-flash" in report[
        "problems"
    ]


def test_worker_policy_lint_cli_writes_report(tmp_path):
    predictions = tmp_path / "predictions.jsonl"
    report_path = tmp_path / "worker_policy_audit.json"
    write_jsonl(
        predictions,
        [
            {
                "instance_id": "django__django-10097",
                "model_name_or_path": "haiku-4-5__armC__uplift-s01",
                "model_patch": "",
            }
        ],
    )

    subprocess.run(
        [
            "python3",
            "tools/bench/audit_worker_policy_predictions.py",
            "--predictions",
            str(predictions),
            "--out",
            str(report_path),
        ],
        cwd=REPO,
        check=True,
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "PASS"
