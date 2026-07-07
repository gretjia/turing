#!/usr/bin/env python3
"""Gate RELEASE_ELIGIBLE.json creation on a validated external certificate."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import build_packet


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - gate emits one machine reason.
        refuse(f"json_parse:{path.name}:{exc.__class__.__name__}")
    if not isinstance(data, dict):
        refuse(f"json_not_object:{path.name}")
    return data


def emit(payload: dict[str, Any], exit_code: int = 0) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))
    raise SystemExit(exit_code)


def refuse(reason: str, **details: Any) -> None:
    payload: dict[str, Any] = {
        "schema_id": "turingos.release_eligibility_check.v1",
        "verdict": "FAIL",
        "reason": reason,
    }
    if details:
        payload["details"] = details
    emit(payload, 1)


def default_validator() -> Path:
    env_path = os.environ.get("M5_VALIDATOR")
    if env_path:
        return Path(env_path)
    repo = Path(__file__).resolve().parents[2]
    candidate = repo.parent / "PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/m5_verification/tools/validate_closure_certificate.py"
    return candidate


def run_certificate_validator(validator: Path, cert: Path, manifest: Path) -> None:
    if not validator.is_file():
        refuse("validator_missing", path=str(validator))
    proc = subprocess.run(
        [sys.executable, str(validator), str(cert), str(manifest)],
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        reason = proc.stdout.strip() or proc.stderr.strip() or "validator_reject"
        if reason.startswith("REJECT:"):
            reason = reason.removeprefix("REJECT:")
        refuse(f"certificate_invalid:{reason}", validator_stdout=proc.stdout, validator_stderr=proc.stderr)


def assert_eligible(args: argparse.Namespace) -> None:
    packet = Path(args.packet).resolve()
    cert = Path(args.cert).resolve()
    out = Path(args.out).resolve() if args.out else packet / "RELEASE_ELIGIBLE.json"
    validator = Path(args.validator).resolve() if args.validator else default_validator().resolve()

    if not packet.is_dir():
        refuse("packet_missing", path=str(packet))
    if not cert.is_file():
        refuse("certificate_missing", path=str(cert))

    packet_validation_stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(packet_validation_stdout):
            build_packet.validate_packet(packet)
    except SystemExit as exc:
        if exc.code != 0:
            reason = packet_validation_stdout.getvalue().strip() or "packet_invalid"
            refuse("packet_invalid", validator_stdout=reason)

    manifest_path = packet / "PACKET_MANIFEST.json"
    run_certificate_validator(validator, cert, manifest_path)
    manifest = load_json(manifest_path)
    certificate = load_json(cert)

    if certificate.get("verdict") != "PASS":
        refuse("certificate_not_pass")
    verification = certificate.get("verification")
    if not isinstance(verification, dict) or verification.get("digest_manifest_result") != "PASS":
        refuse("digest_manifest_not_pass")
    if certificate.get("subject", {}).get("packet_sha256") != manifest.get("packet_sha256"):
        refuse("subject_digest_mismatch")

    payload = {
        "schema_id": "turingos.release_eligible.v1",
        "eligible": True,
        "certificate_sha256": sha256_file(cert),
        "packet_sha256": manifest["packet_sha256"],
    }
    write_json(out, payload)
    emit(
        {
            "schema_id": "turingos.release_eligibility_check.v1",
            "verdict": "PASS",
            "release_eligible": str(out),
            "packet_sha256": manifest["packet_sha256"],
            "certificate_sha256": payload["certificate_sha256"],
        }
    )


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--packet", required=True)
    p.add_argument("--cert", required=True)
    p.add_argument("--out")
    p.add_argument("--validator")
    return p


def main(argv: list[str]) -> int:
    assert_eligible(parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
