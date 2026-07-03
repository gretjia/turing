import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "evidence" / "theory" / "turing_completeness_witness_20260703"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_tc4_audit_runner_writes_verdicts_mutations_and_noninterference():
    proc = subprocess.run(
        [
            "python3",
            "tools/theory/audit_tc4_witness.py",
            "--root",
            str(ROOT),
            "--write",
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    verdicts = [_load(ROOT / "verdicts" / f"TC-{index:02}.json") for index in range(1, 10)]
    assert [verdict["verdict"] for verdict in verdicts] == ["PASS"] * 9
    assert all(verdict["not_run_is_fail"] is True for verdict in verdicts)

    matrix = _load(ROOT / "mutations" / "matrix.json")
    assert matrix["verdict"] == "PASS"
    assert [row["mutant"] for row in matrix["rows"]] == [f"m{index}" for index in range(1, 8)]
    assert all(row["status"] == "KILLED" for row in matrix["rows"])

    noninterference = _load(ROOT / "noninterference" / "report.json")
    assert noninterference["verdict"] == "PASS"
    assert noninterference["interleave_invariant"] is True
    assert noninterference["sabotage_meta_test"] == "FAILS_AS_EXPECTED"

    replay = _load(ROOT / "verdicts" / "TC-09.json")
    assert replay["observed"]["replay_twice_identical"] is True
