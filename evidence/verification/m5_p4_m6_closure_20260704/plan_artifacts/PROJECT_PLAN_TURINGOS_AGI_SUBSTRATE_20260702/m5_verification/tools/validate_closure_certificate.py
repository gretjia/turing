#!/usr/bin/env python3
"""Validate turingos.closure_certificate.v1 with no third-party deps."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


REQUIRED_CUSTODY = (
    "fresh_clone",
    "no_shared_conversation_state",
    "no_implementer_transcript",
    "own_credentials",
    "cross_family_or_human",
    "own_custody_output",
)

VALID_VERIFIER_KINDS = {"external_human_operator", "external_cross_family_model"}
VALID_VERDICTS = {"PASS", "FAIL"}
HATCH_RE = re.compile(r"\bexternal\b.*\bor\b.*\b(designated|internal)\b", re.I | re.S)


def reject(reason: str) -> None:
    print(f"REJECT:{reason}")
    raise SystemExit(1)


def load_json(path: str) -> dict[str, Any]:
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as exc:  # noqa: BLE001 - validator must fail closed with one reason.
        reject(f"json_parse:{Path(path).name}:{exc.__class__.__name__}")
    if not isinstance(data, dict):
        reject(f"json_object:{Path(path).name}")
    return data


def require_mapping(root: dict[str, Any], key: str) -> dict[str, Any]:
    value = root.get(key)
    if not isinstance(value, dict):
        reject(key)
    return value


def require_string(root: dict[str, Any], key: str) -> str:
    value = root.get(key)
    if not isinstance(value, str) or not value:
        reject(key)
    return value


def validate(cert: dict[str, Any], packet: dict[str, Any]) -> None:
    if cert.get("schema_id") != "turingos.closure_certificate.v1":
        reject("schema_id")
    if cert.get("verdict") not in VALID_VERDICTS:
        reject("verdict_enum")
    if cert.get("verdict_enum") != ["PASS", "FAIL"]:
        reject("verdict_enum")

    subject = require_mapping(cert, "subject")
    verifier = require_mapping(cert, "verifier")
    custody = require_mapping(verifier, "custody")
    verification = require_mapping(cert, "verification")
    status_semantics = require_mapping(cert, "status_semantics")
    anchoring = require_mapping(cert, "anchoring")

    if verifier.get("kind") not in VALID_VERIFIER_KINDS:
        reject("verifier_kind")
    missing_or_false = [key for key in REQUIRED_CUSTODY if custody.get(key) is not True]
    if missing_or_false:
        reject("custody_booleans")

    implementer_families = {
        str(item.get("model_family"))
        for item in packet.get("implementer_manifest", [])
        if isinstance(item, dict) and item.get("model_family")
    }
    implementer_labels = {
        str(item.get("operator_label"))
        for item in packet.get("implementer_manifest", [])
        if isinstance(item, dict) and item.get("operator_label")
    }
    if verifier.get("kind") == "external_cross_family_model":
        if verifier.get("model_family") in implementer_families:
            reject("verifier_family")
    if verifier.get("operator_label") in implementer_labels:
        reject("verifier_identity")

    if subject.get("packet_sha256") != packet.get("packet_sha256"):
        reject("subject_digest_mismatch")
    if packet.get("repo_sha") and subject.get("repo_sha") != packet.get("repo_sha"):
        reject("repo_sha_mismatch")
    if status_semantics.get("implementer_ceiling") != "ADDRESSED":
        reject("implementer_ceiling")
    if status_semantics.get("this_certificate_confers") != "EXTERNALLY_VERIFIED":
        reject("certificate_confers")

    commands = verification.get("commands_run")
    if not isinstance(commands, list) or not commands:
        reject("no_commands_run")
    for command in commands:
        if not isinstance(command, dict) or not isinstance(command.get("cmd"), str):
            reject("commands_run")
        if not isinstance(command.get("exit_code"), int):
            reject("commands_run")

    require_string(anchoring, "channel")
    require_string(anchoring, "anchored_digest_reference")
    require_string(cert, "certificate_id")
    require_string(cert, "created_at_utc")

    haystack = json.dumps([cert, packet], sort_keys=True)
    if HATCH_RE.search(haystack):
        reject("disjunctive_escape_hatch")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: validate_closure_certificate.py <cert.json> <packet_manifest.json>", file=sys.stderr)
        return 2
    cert = load_json(argv[1])
    packet = load_json(argv[2])
    validate(cert, packet)
    print("VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
