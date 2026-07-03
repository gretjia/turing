import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "evidence" / "theory" / "turing_completeness_witness_20260703"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_tc5_packet_check_keeps_tc10_external_and_not_run():
    proc = subprocess.run(
        [
            "python3",
            "tools/theory/build_tc5_packet.py",
            "--root",
            str(ROOT),
            "--check",
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    tc10 = _load(ROOT / "verdicts" / "TC-10.json")
    assert tc10["gate_id"] == "TC-10"
    assert tc10["verdict"] == "NOT_RUN"
    assert tc10["not_run_is_fail"] is True
    assert tc10["implementer_may_run"] is False
    assert tc10["external_verifier_required"] is True

    packet = _load(ROOT / "packet" / "M2_TC5_PACKET.json")
    assert packet["phase_status"] == "ADDRESSED"
    assert packet["tc10"]["verdict"] == "NOT_RUN"
    assert packet["tc10"]["external_verifier_required"] is True
    assert packet["claims"]["turing_completeness_claim_allowed"] is False
    assert packet["claims"]["tc10_external_artifact_exists"] is False

    boundary = _load(ROOT / "packet" / "CLAIM_BOUNDARY.json")
    assert boundary["turing_completeness_claim_allowed"] is False
    assert boundary["tc10_external_artifact_exists"] is False

    manifest = ROOT / "packet" / "PACKET_MANIFEST.sha256"
    digest_proc = subprocess.run(
        ["sha256sum", "-c", str(manifest.relative_to(REPO))],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
    )
    assert digest_proc.returncode == 0, digest_proc.stdout + digest_proc.stderr
