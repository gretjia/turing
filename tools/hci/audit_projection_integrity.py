#!/usr/bin/env python3
"""Independent integrity audit for HCI-A operator projection snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any


CHECKS = (
    "shadow_rebuild",
    "independent_heads",
    "provenance_closure",
    "render_fidelity",
    "worker_leakage",
)


def jcs_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def sha256_jcs(value: Any) -> str:
    return "sha256:" + hashlib.sha256(jcs_bytes(value)).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def read_micro_ref(repo: Path, ref: str, required: bool) -> str | None:
    result = git(repo, "rev-parse", "--verify", "--quiet", ref)
    value = result.stdout.strip()
    if result.returncode == 0 and re.fullmatch(r"[0-9a-f]{64}", value):
        return f"mu:{value}"
    if required:
        raise ValueError(
            f"required MicroTape ref {ref} is missing or invalid: {result.stderr.strip()}"
        )
    return None


def heads_from_micro_git(repo: Path) -> dict[str, str | None]:
    fmt = git(repo, "rev-parse", "--show-object-format")
    if fmt.returncode != 0:
        raise ValueError(f"cannot read Git object format: {fmt.stderr.strip()}")
    if fmt.stdout.strip() != "sha256":
        raise ValueError(f"MicroTape repo must use sha256 objects, got {fmt.stdout.strip()}")
    return {
        "tape_tip": read_micro_ref(repo, "refs/turingos/tape_tip", True),
        "authorization_head": read_micro_ref(
            repo, "refs/turingos/authorization_head", False
        ),
        "accepted_head": read_micro_ref(repo, "refs/turingos/accepted_head", True),
    }


def heads_from_micro_bundle(bundle: Path) -> dict[str, str | None]:
    with tempfile.TemporaryDirectory(prefix="turingos-hci-audit-bundle-") as tmp:
        repo = Path(tmp) / "bundle_repo"
        init = subprocess.run(
            ["git", "init", "--object-format=sha256", "-q", str(repo)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if init.returncode != 0:
            raise ValueError(f"cannot init bundle scratch repo: {init.stderr.strip()}")
        fetch = git(repo, "fetch", "-q", str(bundle), "refs/*:refs/*")
        if fetch.returncode != 0:
            raise ValueError(f"cannot fetch MicroTape bundle: {fetch.stderr.strip()}")
        return heads_from_micro_git(repo)


def json_pointer_escape(segment: str) -> str:
    return segment.replace("~", "~0").replace("/", "~1")


def leaf_pointers(value: Any, prefix: str = "") -> list[str]:
    if isinstance(value, dict):
        if not value:
            return [prefix or ""]
        leaves: list[str] = []
        for key in sorted(value):
            child = f"{prefix}/{json_pointer_escape(key)}"
            leaves.extend(leaf_pointers(value[key], child))
        return leaves
    if isinstance(value, list):
        if not value:
            return [prefix or ""]
        leaves = []
        for index, item in enumerate(value):
            leaves.extend(leaf_pointers(item, f"{prefix}/{index}"))
        return leaves
    return [prefix or ""]


def pattern_matches(pattern: str, pointer: str) -> bool:
    pattern_parts = pattern.strip("/").split("/") if pattern else []
    pointer_parts = pointer.strip("/").split("/") if pointer else []
    if len(pattern_parts) != len(pointer_parts):
        return False
    return all(expected == "*" or expected == actual for expected, actual in zip(pattern_parts, pointer_parts))


def check_shadow_rebuild(snapshot: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    expected = snapshot.get("snapshot_hash")
    if not isinstance(expected, str):
        return False, {"error": "snapshot_hash missing or non-string"}
    preimage = {key: value for key, value in snapshot.items() if key != "snapshot_hash"}
    actual = sha256_jcs(preimage)
    return actual == expected, {"expected": expected, "actual": actual}


def check_independent_heads(
    snapshot: dict[str, Any], micro_git: Path | None, micro_bundle: Path | None
) -> tuple[bool, dict[str, Any]]:
    expected = snapshot.get("heads")
    if not isinstance(expected, dict):
        return False, {"error": "snapshot.heads missing or non-object"}
    if micro_git is not None:
        actual = heads_from_micro_git(micro_git)
    elif micro_bundle is not None:
        actual = heads_from_micro_bundle(micro_bundle)
    else:
        return False, {"error": "no MicroTape source provided"}
    return actual == expected, {"expected": expected, "actual": actual}


def check_provenance_closure(
    snapshot: dict[str, Any], provenance_path: Path
) -> tuple[bool, dict[str, Any]]:
    manifest = read_json(provenance_path)
    rules = manifest.get("rules", [])
    if not isinstance(rules, list):
        return False, {"error": "provenance manifest has no rules array"}
    exact = {
        rule["pointer"]
        for rule in rules
        if isinstance(rule, dict) and isinstance(rule.get("pointer"), str)
    }
    patterns = [
        rule["pattern"]
        for rule in rules
        if isinstance(rule, dict) and isinstance(rule.get("pattern"), str)
    ]
    uncovered = []
    for pointer in leaf_pointers(snapshot):
        if pointer in exact:
            continue
        if any(pattern_matches(pattern, pointer) for pattern in patterns):
            continue
        uncovered.append(pointer)
    return not uncovered, {"uncovered": uncovered}


def get_pointer(value: Any, pointer: str) -> Any:
    current = value
    for raw in pointer.strip("/").split("/"):
        part = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            current = current[int(part)]
        else:
            current = current[part]
    return current


def text_tokens(path: Path) -> dict[str, str]:
    body = path.read_text(encoding="utf-8")
    return {
        match.group(1): match.group(2)
        for match in re.finditer(r"(?<!\S)([A-Za-z_][A-Za-z0-9_]*)=([^\s]+)", body)
    }


def check_render_fidelity(
    snapshot: dict[str, Any], text_output_path: Path
) -> tuple[bool, dict[str, Any]]:
    tokens = text_tokens(text_output_path)
    expected = {
        "source_kind": str(get_pointer(snapshot, "/source/source_kind")),
        "micro_repo": str(get_pointer(snapshot, "/source/micro_repo")),
        "operator_state": str(get_pointer(snapshot, "/operator_state")),
        "tape_tip": str(get_pointer(snapshot, "/heads/tape_tip")),
        "authorization_head": str(
            get_pointer(snapshot, "/heads/authorization_head") or "null"
        ),
        "accepted_head": str(get_pointer(snapshot, "/heads/accepted_head")),
        "can_write_truth": (
            "true" if get_pointer(snapshot, "/source/can_write_truth") else "false"
        ),
        "snapshot_hash": str(get_pointer(snapshot, "/snapshot_hash")),
    }
    mismatches = {}
    for key, expected_value in expected.items():
        actual = tokens.get(key)
        if actual != expected_value:
            mismatches[key] = {"expected": expected_value, "actual": actual}
    return not mismatches, {"mismatches": mismatches}


def worker_scan_paths(repo_root: Path) -> list[Path]:
    candidates = [
        repo_root / "src" / "turingos" / "worker",
        repo_root / "crates" / "turing-execd" / "src",
        repo_root / "crates" / "turing-daemons" / "src",
        repo_root / "tools" / "bench" / "materialize_swebench_worker_safe_tasks.py",
        repo_root / "tools" / "bench" / "prepare_stage12_run_plan.py",
        repo_root / "tools" / "bench" / "evaluate_django_swe_bench_patches.py",
        repo_root / "tools" / "bench" / "run_swebench_shard.py",
        repo_root / "tools" / "bench" / "mini_swe_bench_grok_headless.py",
    ]
    return [path for path in candidates if path.exists()]


def iter_source_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file() and path.suffix in {".py", ".rs", ".md", ".json", ".toml"}:
            files.append(path)
        elif path.is_dir():
            for child in path.rglob("*"):
                if "__pycache__" in child.parts:
                    continue
                if child.is_file() and child.suffix in {".py", ".rs", ".md", ".json", ".toml"}:
                    files.append(child)
    return sorted(files)


def check_worker_leakage(repo_root: Path) -> tuple[bool, dict[str, Any]]:
    forbidden = [
        "operator_view_snapshot.v1",
        "operator_tool_manifest.v1",
        "operator_turn_trace.v1",
    ]
    findings = []
    for path in iter_source_files(worker_scan_paths(repo_root)):
        try:
            body = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for token in forbidden:
            if token in body:
                findings.append({"path": str(path.relative_to(repo_root)), "token": token})
    return not findings, {"findings": findings}


def build_verdict(
    args: argparse.Namespace,
    snapshot: dict[str, Any],
    checks: dict[str, str],
    details: dict[str, Any],
    failures: list[str],
) -> dict[str, Any]:
    source = "micro-git" if args.micro_git else "micro-bundle"
    return {
        "schema_id": "hci_projection_integrity_verdict.v1",
        "source": source,
        "tape": str(args.micro_git or args.micro_bundle),
        "snapshot_hash": snapshot.get("snapshot_hash"),
        "checks": checks,
        "details": details,
        "failures": failures,
        "status_ceiling": "ADDRESSED",
        "not_run_is_fail": True,
        "verdict": "PASS" if not failures else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--micro-git", type=Path)
    source.add_argument("--micro-bundle", type=Path)
    parser.add_argument("--snapshot-json", type=Path, required=True)
    parser.add_argument("--text-output", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    snapshot = read_json(args.snapshot_json)
    if not isinstance(snapshot, dict):
        raise SystemExit("snapshot JSON root must be an object")

    check_fns = {
        "shadow_rebuild": lambda: check_shadow_rebuild(snapshot),
        "independent_heads": lambda: check_independent_heads(
            snapshot, args.micro_git, args.micro_bundle
        ),
        "provenance_closure": lambda: check_provenance_closure(
            snapshot, args.provenance
        ),
        "render_fidelity": lambda: check_render_fidelity(snapshot, args.text_output),
        "worker_leakage": lambda: check_worker_leakage(args.repo_root),
    }
    checks: dict[str, str] = {}
    details: dict[str, Any] = {}
    failures: list[str] = []
    for name in CHECKS:
        try:
            passed, detail = check_fns[name]()
        except Exception as error:  # noqa: BLE001 - audit output must capture all failures.
            passed = False
            detail = {"error": str(error)}
        checks[name] = "PASS" if passed else "FAIL"
        details[name] = detail
        if not passed:
            failures.append(name)

    verdict = build_verdict(args, snapshot, checks, details, failures)
    text = json.dumps(verdict, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if verdict["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
