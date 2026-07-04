import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_hci_copy_lint_rejects_forbidden_completion_claims(tmp_path):
    bad = tmp_path / "bad.md"
    bad.write_text("This flow is approved and class closed.\n", encoding="utf-8")

    result = subprocess.run(
        ["python3", str(ROOT / "scripts" / "lint_hci_copy.py"), str(bad)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode != 0
    assert "forbidden operator copy" in result.stderr


def test_ascii_schema_key_lint_rejects_non_ascii_keys(tmp_path):
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()
    (schema_dir / "bad.schema.json").write_text(
        json.dumps({"properties": {"状态": {"type": "string"}}}),
        encoding="utf-8",
    )

    result = subprocess.run(
        ["python3", str(ROOT / "scripts" / "lint_ascii_schema_keys.py"), str(schema_dir)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode != 0
    assert "non-ASCII schema key" in result.stderr


def test_operator_agent_audit_passes_repository_contracts():
    result = subprocess.run(
        ["python3", str(ROOT / "scripts" / "audit_operator_agent.py")],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "PYTHONPATH": "src"},
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "operator agent audit: PASS" in result.stdout


def test_operator_cli_runtime_copy_audit_passes():
    result = subprocess.run(
        ["python3", str(ROOT / "scripts" / "audit_operator_cli_copy.py")],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "PYTHONPATH": "src"},
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "operator CLI copy audit: PASS" in result.stdout
