from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_hci_no_write_gate_self_test_and_clean_tree_pass() -> None:
    gate = ROOT / "tools" / "hci" / "gate_hci_no_write.sh"
    assert gate.exists()

    self_test = run("bash", str(gate), "--self-test")
    assert self_test.returncode == 0, self_test.stderr + self_test.stdout
    assert "HCI_NO_WRITE_SELF_TEST_PASS" in self_test.stdout

    clean = run("bash", str(gate))
    assert clean.returncode == 0, clean.stderr + clean.stdout
    assert "HCI_NO_WRITE_GATE_PASS" in clean.stdout


def test_projection_clippy_disallows_write_primitives() -> None:
    config = ROOT / "crates" / "turing-projection" / "clippy.toml"
    assert config.exists()
    body = config.read_text(encoding="utf-8")
    for token in [
        "turing_git_tape::append::Append::append",
        "turing_git_tape::append::Append::stage",
        "turing_git_tape::append::AppendRequest",
        "turing_git_tape::append::StagedAppend::commit",
        "turing_git_tape::append::StagedAppend::re_mint_and_commit",
    ]:
        assert token in body
