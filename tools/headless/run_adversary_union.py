#!/usr/bin/env python3
"""Run the current required adversary-union subset as real probes."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from headless_common import compute_product, sha256_path, write_json


def run_fixture_probe(repo: Path, fixture: dict) -> dict:
    with tempfile.TemporaryDirectory() as td:
        fixture_path = Path(td) / "fixture.json"
        write_json(fixture_path, fixture)
        proc = subprocess.run(
            [sys.executable, str(repo / "tools/headless/fixture_probe.py"), "--fixture", str(fixture_path)],
            cwd=repo,
            text=True,
            capture_output=True,
        )
        return {
            "argv": [sys.executable, "tools/headless/fixture_probe.py", "--fixture", str(fixture_path)],
            "exit_status": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }


def gate_unexecuted_fixture_product() -> str:
    return compute_product(
        {
            "exit_status": 0,
            "reasons": [{"id": "command_exit_zero", "verdict": "PASS"}],
            "not_run": [],
            "tool_digest": "sha256:" + "0" * 64,
            "input_digest": "sha256:" + "1" * 64,
            "output_digest": "sha256:" + "2" * 64,
            "stdout_digest": "sha256:" + "3" * 64,
            "stderr_digest": "sha256:" + "4" * 64,
            "clean_fixture_results": [{"id": "clean", "verdict": "PASS"}],
            "tampered_fixture_results": [{"id": "tampered", "verdict": "FAIL"}],
        }
    )


def run_probe(repo: Path, probe: dict) -> dict:
    probe_id = probe["id"]
    if probe_id == "ADV-FIXTURE-FORBIDDEN-CLAIM":
        result = run_fixture_probe(
            repo,
            {
                "schema_id": "FixtureProbe.v1",
                "claim": "M2_ENABLED",
                "not_run": [],
            },
        )
        passed = result["exit_status"] != 0
        result["passed"] = passed
        return result
    if probe_id == "ADV-FIXTURE-NOT-RUN-ABSORBS":
        result = run_fixture_probe(
            repo,
            {
                "schema_id": "FixtureProbe.v1",
                "claim": "IMPLEMENTER_ADDRESSED",
                "not_run": ["synthetic_missing_probe"],
            },
        )
        passed = result["exit_status"] != 0
        result["passed"] = passed
        return result
    if probe_id == "ADV-GATE-UNEXECUTED-FIXTURE-REJECTED":
        product = gate_unexecuted_fixture_product()
        return {
            "product": product,
            "passed": product == "FAIL",
        }
    return {
        "error": f"unknown probe {probe_id}",
        "passed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="evidence/g12/required_adversaries.union.v1.json")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    repo = Path(__file__).resolve().parents[2]
    manifest_path = repo / args.manifest
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    results = []
    for probe in manifest.get("probes", []):
        result = run_probe(repo, probe)
        results.append({"id": probe["id"], **result})
    packet = {
        "schema_id": "AdversaryUnionRun.v1",
        "manifest": str(manifest_path),
        "manifest_digest": sha256_path(manifest_path),
        "results": results,
        "product": "PASS" if results and all(result.get("passed") for result in results) else "FAIL",
    }
    out = Path(args.out)
    write_json(out, packet)
    print(json.dumps({"product": packet["product"], "out": str(out)}, sort_keys=True))
    return 0 if packet["product"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
