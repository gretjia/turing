import hashlib
import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "evidence" / "theory" / "turing_completeness_witness_20260703"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_tc3_evidence_root_has_bundles_certificates_and_fuzz_results():
    manifest = _load(ROOT / "bundle_manifest.json")
    assert manifest["schema_id"] == "turingos.tc3.bundle_manifest.v1"
    assert manifest["evidence_class"] == "REAL_DETERMINISTIC_EXECUTION"
    assert manifest["program_count"] == 8
    assert manifest["halting_program_count"] == 5
    assert manifest["nonhalting_program_count"] == 3

    certificate_classes = [
        run.get("certificate_class")
        for run in manifest["runs"]
        if run["expected_terminal_event"] == "BudgetExhausted"
    ]
    assert certificate_classes == [
        "C1_STATIC_HALT_UNREACHABILITY",
        "C2_STATE_RECURRENCE",
        "C3_BUDGET_BOUNDED",
    ]

    sha_lines = (ROOT / "bundle_sha256s.txt").read_text(encoding="utf-8").splitlines()
    assert len(sha_lines) == 8
    for line in sha_lines:
        expected, rel = line.split("  ", 1)
        bundle = ROOT / rel
        assert hashlib.sha256(bundle.read_bytes()).hexdigest() == expected
        verify = subprocess.run(
            ["git", "bundle", "verify", str(bundle)],
            cwd=REPO,
            text=True,
            capture_output=True,
            check=False,
        )
        assert verify.returncode == 0, verify.stderr

    fuzz_manifest = _load(ROOT / "fuzz" / "fuzz_manifest.json")
    assert fuzz_manifest["seed"] == 20260702
    assert fuzz_manifest["program_count"] == 500
    assert fuzz_manifest["max_program_len"] == 32
    assert fuzz_manifest["max_steps"] == 4096

    differential = _load(ROOT / "fuzz" / "differential_results.json")
    assert differential["verdict"] == "PASS"
    assert differential["cases_checked"] == 500
