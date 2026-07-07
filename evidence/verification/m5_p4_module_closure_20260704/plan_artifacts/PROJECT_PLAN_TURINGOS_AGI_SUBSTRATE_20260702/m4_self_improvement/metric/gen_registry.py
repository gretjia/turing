#!/usr/bin/env python3
"""Generate heldout_task_registry.v1.json from a frozen shard manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def digest_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def extract_instance_ids(manifest: dict[str, Any], shard: str) -> list[str]:
    if isinstance(manifest.get("shards"), dict) and shard in manifest["shards"]:
        rows = manifest["shards"][shard]
    elif manifest.get("shard") == shard:
        rows = manifest.get("tasks", manifest.get("instances", manifest.get("instance_ids", [])))
    else:
        rows = manifest.get("tasks", manifest.get("instances", []))
    if not isinstance(rows, list):
        raise ValueError("manifest rows must be a list")
    ids: list[str] = []
    for row in rows:
        if isinstance(row, str):
            instance_id = row
        elif isinstance(row, dict):
            instance_id = row.get("instance_id") or row.get("id")
        else:
            instance_id = None
        if not isinstance(instance_id, str) or not instance_id:
            raise ValueError(f"manifest row missing instance_id: {row!r}")
        ids.append(instance_id)
    if not ids:
        raise ValueError(f"no instance ids for shard {shard}")
    return ids


def build_registry(manifest_path: Path, shard: str, created_at_utc: str | None) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    timestamp = created_at_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    registry = {
        "created_at_utc": timestamp,
        "instance_ids": extract_instance_ids(manifest, shard),
        "registry_sha256_self_excluded": "sha256:PENDING",
        "schema_id": "heldout_task_registry.v1",
        "shard": shard,
        "shard_manifest_sha256": digest_file(manifest_path),
    }
    self_digest = "sha256:" + hashlib.sha256(canonical(registry)).hexdigest()
    registry["registry_sha256_self_excluded"] = self_digest
    return registry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shard-manifest", required=True)
    parser.add_argument("--shard", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--created-at-utc")
    args = parser.parse_args()
    registry = build_registry(Path(args.shard_manifest), args.shard, args.created_at_utc)
    Path(args.out).write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
