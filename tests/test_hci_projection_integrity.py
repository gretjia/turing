from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(*args: str, stdout_path: Path | None = None) -> subprocess.CompletedProcess[str]:
    stdout = stdout_path.open("w", encoding="utf-8") if stdout_path else subprocess.PIPE
    try:
        return subprocess.run(
            args,
            cwd=ROOT,
            text=True,
            stdout=stdout,
            stderr=subprocess.PIPE,
            check=False,
        )
    finally:
        if stdout_path:
            stdout.close()


def build_fixture(tmp_path: Path) -> Path:
    fixture = tmp_path / "micro_tape"
    maker = ROOT / "tools" / "hci" / "make_fixture_micro_tape.py"
    assert maker.exists()
    result = run("python3", str(maker), "--out", str(fixture))
    assert result.returncode == 0, result.stderr + result.stdout
    return fixture


def write_snapshot_and_text(fixture: Path, tmp_path: Path) -> tuple[Path, Path]:
    snapshot = tmp_path / "snapshot.json"
    status_text = tmp_path / "status.txt"
    json_result = run(
        "cargo",
        "run",
        "-p",
        "turing-cli",
        "--quiet",
        "--",
        "status",
        "--micro-git",
        str(fixture),
        "--json",
        stdout_path=snapshot,
    )
    assert json_result.returncode == 0, json_result.stderr
    text_result = run(
        "cargo",
        "run",
        "-p",
        "turing-cli",
        "--quiet",
        "--",
        "status",
        "--micro-git",
        str(fixture),
        stdout_path=status_text,
    )
    assert text_result.returncode == 0, text_result.stderr
    return snapshot, status_text


def test_hci_projection_integrity_auditor_passes_fixture_snapshot(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    snapshot, status_text = write_snapshot_and_text(fixture, tmp_path)
    auditor = ROOT / "tools" / "hci" / "audit_projection_integrity.py"
    provenance = ROOT / "schemas" / "operator" / "operator_view_snapshot.v1.provenance.json"
    assert auditor.exists()
    assert provenance.exists()

    verdict_path = tmp_path / "verdict.json"
    result = run(
        "python3",
        str(auditor),
        "--micro-git",
        str(fixture),
        "--snapshot-json",
        str(snapshot),
        "--text-output",
        str(status_text),
        "--provenance",
        str(provenance),
        "--repo-root",
        str(ROOT),
        "--out",
        str(verdict_path),
    )
    assert result.returncode == 0, result.stderr + result.stdout
    verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
    assert verdict["schema_id"] == "hci_projection_integrity_verdict.v1"
    assert verdict["verdict"] == "PASS"
    assert verdict["checks"] == {
        "shadow_rebuild": "PASS",
        "independent_heads": "PASS",
        "provenance_closure": "PASS",
        "render_fidelity": "PASS",
        "worker_leakage": "PASS",
    }


def test_hci_projection_integrity_auditor_fails_tampered_head(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    snapshot, status_text = write_snapshot_and_text(fixture, tmp_path)
    data = json.loads(snapshot.read_text(encoding="utf-8"))
    data["heads"]["tape_tip"] = "mu:" + "b" * 64
    snapshot.write_text(json.dumps(data, sort_keys=True) + "\n", encoding="utf-8")

    result = run(
        "python3",
        str(ROOT / "tools" / "hci" / "audit_projection_integrity.py"),
        "--micro-git",
        str(fixture),
        "--snapshot-json",
        str(snapshot),
        "--text-output",
        str(status_text),
        "--provenance",
        str(ROOT / "schemas" / "operator" / "operator_view_snapshot.v1.provenance.json"),
        "--repo-root",
        str(ROOT),
    )
    assert result.returncode != 0
    assert "independent_heads" in result.stdout + result.stderr


def test_hci_gates_runner_and_workflow_are_wired(tmp_path: Path) -> None:
    runner = ROOT / "tools" / "hci" / "run_hci_gates.sh"
    workflow = ROOT / ".github" / "workflows" / "ci.yml"
    assert runner.exists()
    result = run("bash", str(runner), "--self-test", "--out-dir", str(tmp_path / "self_test"))
    assert result.returncode == 0, result.stderr + result.stdout
    assert "HCI_GATES_SELF_TEST_PASS" in result.stdout
    body = workflow.read_text(encoding="utf-8")
    assert "hci-gates:" in body
    assert "tools/hci/run_hci_gates.sh" in body
