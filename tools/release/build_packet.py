#!/usr/bin/env python3
"""Build and validate turingos.release_packet.v1 packets."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PENDING_PACKET_SHA = "sha256:PENDING"
REMOVED_LEGACY_KEYS = {
    "release_next_stage",
    "independent_recursive_audit",
    "packet_internal_audit_verdict",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - CLI reports a single machine reason.
        fail(f"json_parse:{path.name}:{exc.__class__.__name__}")
    if not isinstance(data, dict):
        fail(f"json_not_object:{path.name}")
    return data


def emit(payload: dict[str, Any], exit_code: int = 0) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))
    raise SystemExit(exit_code)


def fail(reason: str, **details: Any) -> None:
    payload: dict[str, Any] = {
        "schema_id": "turingos.release_packet.validate.v1",
        "verdict": "FAIL",
        "reason": reason,
    }
    if details:
        payload["details"] = details
    emit(payload, 1)


def safe_rel(path: str) -> Path:
    rel = Path(path)
    if rel.is_absolute() or ".." in rel.parts or str(rel) in {"", "."}:
        fail("invalid_relative_path", path=path)
    return rel


def source_files(root: Path, artifact_list: Path | None) -> list[Path]:
    if artifact_list is None:
        files = [path for path in root.rglob("*") if path.is_file()]
        return sorted(files, key=lambda path: path.relative_to(root).as_posix())

    out: list[Path] = []
    for raw in artifact_list.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        rel = safe_rel(line)
        src = root / rel
        if not src.is_file():
            fail("artifact_missing", path=line)
        out.append(src)
    return sorted(out, key=lambda path: path.relative_to(root).as_posix())


def copy_template(src_raw: str | None, dst: Path) -> bool:
    if src_raw is None:
        return False
    src = Path(src_raw).resolve()
    if not src.is_file():
        fail("template_missing", path=str(src))
    shutil.copy2(src, dst)
    return True


def packet_files(packet: Path) -> list[Path]:
    return sorted(
        [path for path in packet.rglob("*") if path.is_file() and path.name != "MANIFEST.sha256"],
        key=lambda path: path.relative_to(packet).as_posix(),
    )


def normalized_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(manifest))
    out["packet_sha256"] = PENDING_PACKET_SHA
    return out


def compute_packet_sha(packet: Path, manifest: dict[str, Any]) -> str:
    material: list[dict[str, str]] = []
    normalized_manifest_digest = sha256_bytes(canonical_json_bytes(normalized_manifest(manifest)))
    for path in packet_files(packet):
        rel = path.relative_to(packet).as_posix()
        if rel == "PACKET_MANIFEST.json":
            digest = normalized_manifest_digest
        else:
            digest = sha256_file(path)
        material.append({"path": rel, "sha256": digest})
    return "sha256:" + sha256_bytes(canonical_json_bytes(material))


def write_sha_manifest(packet: Path) -> None:
    lines = []
    for path in packet_files(packet):
        rel = path.relative_to(packet).as_posix()
        lines.append(f"{sha256_file(path)}  {rel}")
    (packet / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_packet(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    if not root.is_dir():
        fail("root_missing", path=str(root))
    out = Path(args.out).resolve() if args.out else Path.cwd() / f"packet_{args.gate}_{utc_now()[:10]}"
    if out.exists():
        if any(out.iterdir()):
            fail("output_exists", path=str(out))
    out.mkdir(parents=True, exist_ok=True)

    files = source_files(root, Path(args.artifact_list).resolve() if args.artifact_list else None)
    evidence_required: list[str] = []
    for src in files:
        rel = src.relative_to(root)
        dst = out / "evidence" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        evidence_required.append((Path("evidence") / rel).as_posix())

    claim_boundary = root / "CLAIM_BOUNDARY.json"
    if claim_boundary.is_file():
        shutil.copy2(claim_boundary, out / "CLAIM_BOUNDARY.json")
    else:
        write_json(
            out / "CLAIM_BOUNDARY.json",
            {
                "schema_id": "CLAIM_BOUNDARY.v2",
                "evidence_class": "FIXTURE",
                "claims": [f"{args.gate} packet fixture"],
                "non_claims": ["not an external certificate", "not a release decision"],
            },
        )

    (out / "repo_head.txt").write_text(args.sha + "\n", encoding="utf-8")
    if not copy_template(args.reexecution_template, out / "REEXECUTION.md"):
        (out / "REEXECUTION.md").write_text(
            "\n".join(
                [
                    f"# REEXECUTION - {args.gate}",
                    "",
                    "1. `sha256sum -c MANIFEST.sha256` must exit 0 from this packet directory.",
                    "2. `bash tools/release/build_packet.sh --validate <packet_dir>` must exit 0 before submission.",
                    "3. The verifier computes any gate verdict before reading historical EXPECTED_VERDICT text.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    has_auditor_runbook = copy_template(args.auditor_runbook_template, out / "AUDITOR_RUNBOOK.md")

    required = [
        "PACKET_MANIFEST.json",
        "CLAIM_BOUNDARY.json",
        "REEXECUTION.md",
        "repo_head.txt",
        *evidence_required,
    ]
    if has_auditor_runbook:
        required.insert(3, "AUDITOR_RUNBOOK.md")
    manifest = {
        "schema_id": "turingos.release_packet.v1",
        "gate_id": args.gate,
        "repo_sha": args.sha,
        "packet_sha256": PENDING_PACKET_SHA,
        "packet_digest_method": "sha256 of canonical packet file digest list with PACKET_MANIFEST.json packet_sha256 normalized to sha256:PENDING",
        "packet_manifest_files": len(required),
        "required_artifacts": required,
        "implementer_manifest": [
            {
                "operator_label": "codex-orchestrator",
                "model_family": "gpt-5",
                "role": "packet-builder",
            }
        ],
        "builder": {
            "schema_id": "turingos.release_packet.builder.v1",
            "tool": "tools/release/build_packet.sh",
            "built_at_utc": utc_now(),
        },
    }
    write_json(out / "PACKET_MANIFEST.json", manifest)
    manifest["packet_sha256"] = compute_packet_sha(out, manifest)
    write_json(out / "PACKET_MANIFEST.json", manifest)
    write_sha_manifest(out)

    emit(
        {
            "schema_id": "turingos.release_packet.build.v1",
            "verdict": "PASS",
            "packet_dir": str(out),
            "packet_sha256": manifest["packet_sha256"],
            "manifest": str(out / "PACKET_MANIFEST.json"),
        }
    )


def find_removed_keys(value: Any, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else key
            if key in REMOVED_LEGACY_KEYS:
                found.append(key)
            found.extend(find_removed_keys(child, path))
    elif isinstance(value, list):
        for item in value:
            found.extend(find_removed_keys(item, prefix))
    return found


def parse_sha_manifest(packet: Path) -> dict[str, str]:
    manifest_path = packet / "MANIFEST.sha256"
    if not manifest_path.is_file():
        fail("manifest_missing")
    entries: dict[str, str] = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            digest, rel = line.split(maxsplit=1)
        except ValueError:
            fail("manifest_line_invalid", line=line)
        rel = rel.strip()
        safe_rel(rel)
        if rel in entries:
            fail("manifest_duplicate", path=rel)
        entries[rel] = digest
    return entries


def validate_packet(packet: Path) -> None:
    packet = packet.resolve()
    if not packet.is_dir():
        fail("packet_missing", path=str(packet))
    manifest_path = packet / "PACKET_MANIFEST.json"
    if not manifest_path.is_file():
        fail("packet_manifest_missing")
    manifest = load_json(manifest_path)

    removed = sorted(set(find_removed_keys(manifest)))
    if removed:
        fail(f"removed_legacy_key:{removed[0]}")
    if manifest.get("schema_id") != "turingos.release_packet.v1":
        fail("schema_id")
    for key in ("gate_id", "repo_sha", "packet_sha256", "required_artifacts", "implementer_manifest"):
        if key not in manifest:
            fail(f"missing_manifest_key:{key}")

    required = manifest.get("required_artifacts")
    if not isinstance(required, list) or not required:
        fail("required_artifacts_missing")
    seen_required: set[str] = set()
    for rel_raw in required:
        if not isinstance(rel_raw, str):
            fail("invalid_declared_artifact", path=str(rel_raw))
        rel = safe_rel(rel_raw).as_posix()
        if rel in seen_required:
            fail("duplicate_declared_artifact", path=rel)
        seen_required.add(rel)
        if not (packet / rel).is_file():
            fail("missing_declared_artifact", path=rel)

    repo_head = packet / "repo_head.txt"
    if repo_head.is_file() and repo_head.read_text(encoding="utf-8").strip() != manifest.get("repo_sha"):
        fail("repo_sha_mismatch")

    entries = parse_sha_manifest(packet)
    actual_files = {path.relative_to(packet).as_posix() for path in packet_files(packet)}
    if set(entries) != actual_files:
        missing = sorted(actual_files - set(entries))
        extra = sorted(set(entries) - actual_files)
        fail("manifest_closure_mismatch", missing=missing, extra=extra)
    for rel, expected in entries.items():
        actual = sha256_file(packet / rel)
        if actual != expected:
            fail("manifest_digest_mismatch", path=rel, expected=expected, actual=actual)

    recomputed = compute_packet_sha(packet, manifest)
    if manifest.get("packet_sha256") != recomputed:
        fail("packet_sha256_mismatch", expected=manifest.get("packet_sha256"), actual=recomputed)

    emit(
        {
            "schema_id": "turingos.release_packet.validate.v1",
            "verdict": "PASS",
            "packet_dir": str(packet),
            "packet_sha256": manifest["packet_sha256"],
            "checked_files": len(actual_files),
        }
    )


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root")
    p.add_argument("--sha")
    p.add_argument("--gate", default="M5.P5.FIXTURE")
    p.add_argument("--artifact-list")
    p.add_argument("--out")
    p.add_argument("--reexecution-template")
    p.add_argument("--auditor-runbook-template")
    p.add_argument("--validate", nargs="?", const=".")
    return p


def main(argv: list[str]) -> int:
    args = parser().parse_args(argv)
    if args.validate is not None:
        validate_packet(Path(args.validate))
        return 0
    if not args.root or not args.sha:
        parser().error("--root and --sha are required unless --validate is used")
    build_packet(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
