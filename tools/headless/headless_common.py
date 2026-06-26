#!/usr/bin/env python3
"""Shared helpers for /goal headless-triad evidence.

This module is non-authority orchestration. It renders receipts and digests for
the goal runner; it does not own canonical sovereign bytes, reducer state,
launch admission, closure, signing keys, or any Micro Tape head movement.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SHA256_EMPTY = "sha256:" + hashlib.sha256(b"").hexdigest()
FORBIDDEN_CLAIMS = [
    "HUMAN_RATIFIED",
    "OG10_SIGNED",
    "FOUNDATION_READY",
    "M2_ENABLED",
]
NO_HUMAN_STATE_CEILING = "READY_FOR_HUMAN_GENESIS_SIGNATURE"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def maybe_sha256_path(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    return sha256_path(path)


def digest_paths(paths: list[Path]) -> str:
    manifest = []
    for path in sorted(paths, key=lambda p: str(p)):
        manifest.append(
            {
                "path": str(path),
                "exists": path.exists(),
                "digest": maybe_sha256_path(path),
            }
        )
    return sha256_bytes(canonical_json_bytes(manifest))


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def packet_digest(value: dict[str, Any]) -> str:
    unsigned = dict(value)
    unsigned.pop("packet_digest", None)
    return sha256_bytes(canonical_json_bytes(unsigned))


def attach_packet_digest(value: dict[str, Any]) -> dict[str, Any]:
    out = dict(value)
    out["packet_digest"] = packet_digest(out)
    return out


def stream_digest(text: str | bytes) -> str:
    if isinstance(text, str):
        text = text.encode("utf-8")
    return sha256_bytes(text)


def which_digest(name: str) -> tuple[str | None, str | None]:
    exe = shutil.which(name)
    if exe is None:
        return None, None
    path = Path(exe)
    return exe, sha256_path(path) if path.exists() else None


def command_digest(argv: list[str]) -> str:
    return sha256_bytes(canonical_json_bytes(argv))


def compute_product(result: dict[str, Any]) -> str:
    if result.get("not_run"):
        return "NOT_RUN"
    if result.get("exit_status") != 0:
        return "FAIL"
    for key in ("tool_digest", "input_digest", "output_digest", "stdout_digest", "stderr_digest"):
        if not result.get(key):
            return "FAIL"
    for reason in result.get("reasons", []):
        if reason.get("verdict") != "PASS":
            return "FAIL"
    if not result.get("clean_fixture_results"):
        return "FAIL"
    if not result.get("tampered_fixture_results"):
        return "FAIL"
    for fixture in result["clean_fixture_results"]:
        if fixture.get("verdict") != "PASS":
            return "FAIL"
    for fixture in result["tampered_fixture_results"]:
        if fixture.get("verdict") == "PASS":
            return "FAIL"
    return "PASS"


def gate_result(
    *,
    gate_id: str,
    phase_id: str,
    command_argv: list[str],
    exit_status: int,
    reasons: list[dict[str, Any]],
    not_run: list[str],
    tool_path: Path,
    input_paths: list[Path],
    output_path: Path | None,
    stdout: str = "",
    stderr: str = "",
    clean_fixture_results: list[dict[str, Any]] | None = None,
    tampered_fixture_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    result = {
        "schema_id": "GateResult.v1",
        "gate_id": gate_id,
        "phase_id": phase_id,
        "command_argv": command_argv,
        "command_digest": command_digest(command_argv),
        "exit_status": exit_status,
        "product": "FAIL",
        "reasons": reasons,
        "not_run": sorted(set(not_run)),
        "tool_digest": sha256_path(tool_path),
        "input_digest": digest_paths(input_paths),
        "output_digest": maybe_sha256_path(output_path),
        "stdout_digest": stream_digest(stdout),
        "stderr_digest": stream_digest(stderr),
        "clean_fixture_results": clean_fixture_results or [],
        "tampered_fixture_results": tampered_fixture_results or [],
        "created_at": utc_now(),
    }
    result["product"] = compute_product(result)
    return result


def repo_root_from_script(script: Path) -> Path:
    return script.resolve().parents[2]


def git_stdout(repo: Path, args: list[str]) -> str | None:
    try:
        proc = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True)
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def git_commit(repo: Path) -> str:
    return git_stdout(repo, ["rev-parse", "HEAD"]) or "UNKNOWN"


def git_remote(repo: Path) -> str | None:
    return git_stdout(repo, ["config", "--get", "remote.origin.url"])


def git_tree_digest(repo: Path) -> str:
    try:
        proc = subprocess.run(["git", "ls-files", "-z"], cwd=repo, capture_output=True)
    except OSError:
        return "sha256:UNKNOWN"
    if proc.returncode != 0:
        return "sha256:UNKNOWN"
    entries = []
    for raw in proc.stdout.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode("utf-8")
        path = repo / rel
        if path.is_file():
            entries.append({"path": rel, "digest": sha256_path(path)})
    return sha256_bytes(canonical_json_bytes(entries))


def forbidden_claims_present(values: list[str]) -> list[str]:
    haystack = "\n".join(values)
    return [claim for claim in FORBIDDEN_CLAIMS if claim in haystack]


def platform_not_run() -> list[str]:
    missing: list[str] = []
    if sys.platform != "linux":
        missing.append("linux_required")
    runsc, _digest = which_digest("runsc")
    if runsc is None:
        missing.append("runsc_missing")
    return missing


def runsc_version() -> str | None:
    exe, _digest = which_digest("runsc")
    if exe is None:
        return None
    proc = subprocess.run([exe, "--version"], text=True, capture_output=True)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or proc.stderr.strip()


def detect_missing_foundation_primitives(repo: Path) -> list[str]:
    missing: list[str] = []
    if not (repo / "Cargo.toml").exists() or not (repo / "crates").is_dir():
        missing.append("rust_authority_kernel_missing")
    if not (repo / "Cargo.lock").exists():
        missing.append("cargo_lock_missing")
    if not (repo / "contracts").is_dir():
        missing.append("schema_contracts_missing")
    missing.extend(platform_not_run())
    return sorted(set(missing))


def clean_fixture_pass() -> dict[str, Any]:
    return {"id": "clean_fixture_schema_shape", "verdict": "PASS"}


def tampered_fixture_fail() -> dict[str, Any]:
    return {"id": "tampered_fixture_forbidden_claim", "verdict": "FAIL"}


def base_env_digest() -> str:
    allow = {
        "PATH": os.environ.get("PATH", ""),
        "LANG": os.environ.get("LANG", ""),
        "LC_ALL": os.environ.get("LC_ALL", ""),
        "platform": platform.platform(),
    }
    return sha256_bytes(canonical_json_bytes(allow))


def print_packet_summary(packet: dict[str, Any]) -> None:
    print(
        json.dumps(
            {
                "schema_id": packet.get("schema_id"),
                "status": packet.get("status"),
                "verdict": packet.get("verdict"),
                "not_run": packet.get("not_run", []),
                "packet_digest": packet.get("packet_digest"),
            },
            sort_keys=True,
        )
    )


def structured_output(packet: dict[str, Any]) -> dict[str, Any]:
    """Return schema-constrained model output from a CLI wrapper packet.

    Grok/Claude CLIs may wrap schema output in an outer session object under
    `structuredOutput`; older/plain invocations may return the structured object
    directly. Treat missing/null/non-object structured output as absent.
    """
    nested = packet.get("structuredOutput")
    if not isinstance(nested, dict):
        nested = packet.get("structured_output")
    if isinstance(nested, dict):
        return nested
    if "verdict" in packet:
        return packet
    text = packet.get("text")
    if isinstance(text, str):
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                parsed = {}
            if isinstance(parsed, dict) and "verdict" in parsed:
                return parsed
    return {}
