#!/usr/bin/env python3
"""Build or check the TC5 exact-SHA external-verifier packet."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
TIMESTAMP_UTC = "2026-07-03T00:00:00Z"
ROOT_REL = Path("evidence/theory/turing_completeness_witness_20260703")


class PacketError(RuntimeError):
    pass


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repo_relative(path: Path) -> str:
    return path.resolve().relative_to(REPO).as_posix()


def _run(cmd: list[str], *, cwd: Path = REPO) -> str:
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise PacketError(f"{cmd!r} failed: {proc.stderr.strip()}")
    return proc.stdout


def _git_head() -> str:
    return _run(["git", "rev-parse", "HEAD"]).strip()


def _tc_verdicts(root: Path) -> dict[str, str]:
    verdicts = {}
    for index in range(1, 10):
        path = root / "verdicts" / f"TC-{index:02}.json"
        payload = _load_json(path)
        verdicts[payload["gate_id"]] = payload["verdict"]
    return verdicts


def _tc10_slot(root: Path, subject_commit: str) -> dict[str, Any]:
    return {
        "schema_id": "turingos.tc5.tc10_slot.v1",
        "gate_id": "TC-10",
        "verdict": "NOT_RUN",
        "not_run_is_fail": True,
        "timestamp_utc": TIMESTAMP_UTC,
        "subject_commit": subject_commit,
        "status_reason": "M5_CLASS_EXTERNAL_VERIFIER_REQUIRED",
        "implementer_may_run": False,
        "external_verifier_required": True,
        "external_verifier_artifact": None,
        "clean_clone_required": True,
        "custody_separated_required": True,
        "expected_external_action": (
            "Clone the exact packet commit, verify the packet manifest, re-run TC-01..TC-09, "
            "then write the TC-10 verdict outside implementer custody."
        ),
    }


def _packet_boundary(subject_commit: str) -> dict[str, Any]:
    return {
        "schema_id": "turingos.tc5.packet_claim_boundary.v1",
        "scope": "M2.TC5 exact-SHA packet for external TC-10 verification",
        "status_ceiling": "IMPLEMENTER_ADDRESSED",
        "evidence_class": "REAL_DETERMINISTIC_EXECUTION_PLUS_PACKET",
        "subject_commit": subject_commit,
        "turing_completeness_claim_allowed": False,
        "tc10_external_artifact_exists": False,
        "m2_gate_claim_allowed": False,
        "claims_allowed": [
            "TC-01 through TC-09 local verdicts are present and PASS",
            "TC-10 slot is present and NOT_RUN pending M5-class external verification",
            "exact-SHA packet inputs and digests are recorded for external verification",
        ],
        "claims_forbidden": [
            "TuringOS is Turing-complete",
            "TC-10 passed",
            "M2.G passed",
            "EXTERNALLY_VERIFIED",
            "CLOSED",
            "RELEASED",
            "RATIFIED",
            "SHIPPED",
            "M2_ENABLED",
        ],
        "not_run_is_fail": True,
    }


def _packet_json(root: Path, subject_commit: str) -> dict[str, Any]:
    verdicts = _tc_verdicts(root)
    tc10 = _tc10_slot(root, subject_commit)
    return {
        "schema_id": "turingos.tc5.external_packet.v1",
        "module": "M2",
        "phase": "M2.TC5",
        "phase_status": "ADDRESSED",
        "status_ceiling": "ADDRESSED",
        "timestamp_utc": TIMESTAMP_UTC,
        "subject_repo": "/home/zephryj/turingos_backup/work/turing",
        "subject_commit": subject_commit,
        "packet_role": "external_verifier_input",
        "packet_manifest": _repo_relative(root / "packet" / "PACKET_MANIFEST.sha256"),
        "tc01_tc09": {
            "verdicts": verdicts,
            "all_pass": all(verdict == "PASS" for verdict in verdicts.values()),
            "summary": _repo_relative(root / "verdicts" / "TC4_AUDIT_SUMMARY.json"),
        },
        "tc10": {
            "path": _repo_relative(root / "verdicts" / "TC-10.json"),
            "verdict": tc10["verdict"],
            "not_run_is_fail": tc10["not_run_is_fail"],
            "external_verifier_required": True,
            "implementer_may_run": False,
        },
        "claims": {
            "claim_boundary": _repo_relative(root / "packet" / "CLAIM_BOUNDARY.json"),
            "turing_completeness_claim_allowed": False,
            "tc10_external_artifact_exists": False,
            "m2_gate_claim_allowed": False,
        },
        "clean_clone_instructions": [
            "git clone <repo-url> fresh",
            "cd fresh && git checkout <exact_sha_from_plan_packet_descriptor>",
            f"sha256sum -c {_repo_relative(root / 'packet' / 'PACKET_MANIFEST.sha256')}",
            f"cd {_repo_relative(root)} && sha256sum -c bundle_sha256s.txt",
            "cd <repo-root> && PYTHONPATH=src python3 -m pytest -q tests/test_theory_tc4_audit.py",
            f"cd <repo-root> && python3 tools/theory/audit_tc4_witness.py --root {_repo_relative(root)}",
            "write TC-10 verdict outside implementer custody; do not edit this packet in place",
        ],
        "explicit_non_claims": {
            "tc10_external_artifact_exists": False,
            "turing_completeness_claim_allowed": False,
            "externally_verified": False,
            "closed": False,
            "released": False,
            "ratified": False,
            "shipped": False,
            "m2_enabled": False,
            "constitution_bytes_changed": False,
            "og10_or_genesis_signature": False,
        },
    }


def _readme(subject_commit: str) -> str:
    return f"""# M2.TC5 External Verification Packet

This packet is implementer-side input for an M5-class external TC-10 verifier.
It is not a TC-10 PASS artifact and does not claim M2.G.

- Subject commit recorded at packet build time: `{subject_commit}`
- TC-01..TC-09 are local deterministic audit verdicts.
- `verdicts/TC-10.json` is intentionally `NOT_RUN` with `not_run_is_fail: true`.
- The external verifier must use a clean clone, verify `packet/PACKET_MANIFEST.sha256`,
  re-run the TC audit battery, and write its TC-10 verdict outside implementer custody.

No unqualified Turing-completeness, external-verification, release, ratification,
shipping, or M2-enablement claim is allowed from this packet.
"""


def _manifest_paths(root: Path) -> list[Path]:
    packet_manifest = root / "packet" / "PACKET_MANIFEST.sha256"
    paths = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path == packet_manifest:
            continue
        paths.append(path)
    extra = [
        REPO / "tools/theory/reference_interpreter.py",
        REPO / "tools/theory/audit_tc3_evidence.py",
        REPO / "tools/theory/audit_tc4_witness.py",
        REPO / "tools/theory/build_tc5_packet.py",
        REPO / "tests/test_theory_reference_interpreter.py",
        REPO / "tests/test_theory_tc3_evidence.py",
        REPO / "tests/test_theory_tc4_audit.py",
        REPO / "tests/test_theory_tc5_packet.py",
        REPO / "crates/turing-witness/src/lib.rs",
        REPO / "crates/turing-witness/src/bin/tc3-export.rs",
        REPO / "crates/turing-witness/tests/witness.rs",
        REPO / "crates/turing-witness/tests/tc3_export.rs",
    ]
    paths.extend(path for path in extra if path.exists())
    return sorted({path.resolve() for path in paths}, key=lambda p: _repo_relative(p))


def _write_manifest(root: Path) -> None:
    lines = [f"{_sha256(path)}  {_repo_relative(path)}" for path in _manifest_paths(root)]
    _write_text(root / "packet" / "PACKET_MANIFEST.sha256", "\n".join(lines) + "\n")


def build(root: Path, subject_commit: str) -> dict[str, Any]:
    if not (root / "verdicts" / "TC4_AUDIT_SUMMARY.json").exists():
        raise PacketError("TC4 summary missing; build TC4 before TC5")
    if not all(verdict == "PASS" for verdict in _tc_verdicts(root).values()):
        raise PacketError("TC-01..TC-09 are not all PASS")

    _write_json(root / "verdicts" / "TC-10.json", _tc10_slot(root, subject_commit))
    _write_json(root / "packet" / "CLAIM_BOUNDARY.json", _packet_boundary(subject_commit))
    _write_json(root / "packet" / "M2_TC5_PACKET.json", _packet_json(root, subject_commit))
    _write_text(root / "packet" / "README.md", _readme(subject_commit))
    _write_manifest(root)
    return check(root)


def _verify_manifest(root: Path) -> None:
    manifest = root / "packet" / "PACKET_MANIFEST.sha256"
    if not manifest.exists():
        raise PacketError("packet manifest missing")
    for line_no, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), start=1):
        if not line:
            continue
        try:
            expected, rel = line.split("  ", 1)
        except ValueError as exc:
            raise PacketError(f"malformed manifest line {line_no}") from exc
        path = REPO / rel
        if not path.exists():
            raise PacketError(f"manifest path missing: {rel}")
        observed = _sha256(path)
        if observed != expected:
            raise PacketError(f"manifest digest mismatch: {rel}")


def check(root: Path) -> dict[str, Any]:
    packet = _load_json(root / "packet" / "M2_TC5_PACKET.json")
    boundary = _load_json(root / "packet" / "CLAIM_BOUNDARY.json")
    tc10 = _load_json(root / "verdicts" / "TC-10.json")
    tc09 = _tc_verdicts(root)
    failures = []
    if packet["phase_status"] != "ADDRESSED":
        failures.append("packet phase_status is not ADDRESSED")
    if not all(verdict == "PASS" for verdict in tc09.values()):
        failures.append("TC-01..TC-09 are not all PASS")
    if tc10["verdict"] != "NOT_RUN" or not tc10["not_run_is_fail"]:
        failures.append("TC-10 slot is not NOT_RUN/not_run_is_fail")
    if tc10["implementer_may_run"] or not tc10["external_verifier_required"]:
        failures.append("TC-10 external verifier boundary is invalid")
    if boundary["turing_completeness_claim_allowed"] or boundary["tc10_external_artifact_exists"]:
        failures.append("packet claim boundary is too strong")
    if packet["claims"]["turing_completeness_claim_allowed"] or packet["claims"]["tc10_external_artifact_exists"]:
        failures.append("packet claims are too strong")
    _verify_manifest(root)
    if failures:
        raise PacketError("; ".join(failures))
    return {
        "schema_id": "turingos.tc5.packet_check.v1",
        "verdict": "PASS",
        "phase_status": "ADDRESSED",
        "subject_commit": packet["subject_commit"],
        "tc01_tc09_all_pass": True,
        "tc10_verdict": "NOT_RUN",
        "packet_manifest": _repo_relative(root / "packet" / "PACKET_MANIFEST.sha256"),
        "packet_manifest_sha256": _sha256(root / "packet" / "PACKET_MANIFEST.sha256"),
        "not_run_is_fail": True,
        "turing_completeness_claim_allowed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO / ROOT_REL)
    parser.add_argument("--subject-commit", default=None)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    try:
        if args.write:
            report = build(root, args.subject_commit or _git_head())
        else:
            report = check(root)
    except Exception as error:  # noqa: BLE001 - CLI emits concise gate failure.
        print(f"TC5_PACKET_FAIL {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
