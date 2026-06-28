#!/usr/bin/env python3
"""Build Stage16 sealed campaign evidence from immutable Stage12 bundles."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
STAGE16_AUDITOR = REPO / "tools" / "bench" / "audit_stage16_sealed_campaign.py"


def load_stage16_auditor() -> Any:
    spec = importlib.util.spec_from_file_location("audit_stage16_sealed_campaign", STAGE16_AUDITOR)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"cannot load {STAGE16_AUDITOR}")
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def run_cmd(command: list[str], cwd: Path = REPO) -> None:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError("command failed: " + " ".join(command) + "\nSTDOUT:\n" + result.stdout + "\nSTDERR:\n" + result.stderr)


def scoped_secret_scan(root: Path) -> dict[str, Any]:
    patterns = [
        re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
        re.compile(r"(?i)(private[_-]?key|signing[_-]?seed|auth\\.json|api[_-]?key)(\\s*[:=]\\s*)[A-Za-z0-9_./~:-]{6,}"),
    ]
    problems: list[dict[str, str]] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix == ".bundle":
            continue
        text = path.read_text(errors="ignore")
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                problems.append({"path": str(path), "match": match.group(0)[:80]})
    return {"schema_id": "Stage16SecretScan.v1", "status": "PASS" if not problems else "FAIL", "problem_count": len(problems), "problems": problems}


def build_stage16_campaign(source_root: Path, out_dir: Path) -> dict[str, Any]:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    source_coverage = load_json(source_root / "substrate_coverage.json")
    source_task = load_json(source_root / "task_manifest.json")
    runs = source_coverage.get("turingos_arm_runs", [])
    if not isinstance(runs, list):
        raise ValueError("source coverage missing turingos_arm_runs")

    copied_runs: list[dict[str, Any]] = []
    bundle_lines: list[str] = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        instance_id = run["instance_id"]
        source_bundle = Path(run["micro_tape_bundle"])
        dest_bundle = out_dir / "instances" / instance_id / "micro_tape.bundle"
        dest_bundle.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_bundle, dest_bundle)
        bundle_hash = sha256_file(dest_bundle)
        copied = dict(run)
        copied["source_stage"] = "Stage12"
        copied["source_micro_tape_bundle"] = str(source_bundle)
        copied["micro_tape_bundle"] = str(dest_bundle)
        copied["micro_tape_bundle_sha256"] = bundle_hash
        copied_runs.append(copied)
        bundle_lines.append(f"{bundle_hash}  {dest_bundle}")

    task_manifest = {
        "schema_id": "turingos.stage16.sealed_task_manifest.v1",
        "stage": "Stage16",
        "source_stage": "Stage12",
        "source_task_manifest": str(source_root / "task_manifest.json"),
        "source_dataset": source_task.get("source_dataset"),
        "source_dataset_digest": source_task.get("source_dataset_digest"),
        "task_count": len(copied_runs),
        "instance_ids": [run["instance_id"] for run in copied_runs],
        "campaign_scope": "sealed replay campaign over frozen Stage12 20-task Verified Mini shard",
        "full_swe_bench_score_claim": "FORBIDDEN unless unsolved_count == 0",
    }
    coverage = {
        "schema_id": "Stage16SealedCampaignCoverage.v1",
        "run_id": "stage16_full_sealed_replay_campaign",
        "truth_source": "copied_micro_tape_bundles_from_stage12_no_rewrite",
        "scientific_status": "STAGE16_SEALED_REPLAY_CAMPAIGN_NOT_FULL_SCORE_CLAIM",
        "sample_size": len(copied_runs),
        "turingos_arm_runs": copied_runs,
    }
    write_json(out_dir / "task_manifest.json", task_manifest)
    write_json(out_dir / "substrate_coverage.json", coverage)
    write_json(out_dir / "bundle_manifest.json", coverage)
    (out_dir / "bundle_sha256s.txt").write_text("\n".join(bundle_lines) + "\n", encoding="utf-8")

    run_cmd(
        [
            "python3",
            str(REPO / "tools/bench/audit_micro_tape_decision_dag.py"),
            "--strict-vpput",
            "--strict-terminal-market",
            "--require-authorization-head",
            "--coverage",
            str(out_dir / "substrate_coverage.json"),
            "--out-dir",
            str(out_dir / "micro_tape_audit_strict"),
        ]
    )
    auditor = load_stage16_auditor()
    report = auditor.audit_stage16(out_dir)
    auditor.write_stage16_reports(out_dir, report)
    secret = scoped_secret_scan(out_dir)
    write_json(out_dir / "stage16_secret_scan_summary.json", secret)
    (out_dir / "stage16_secret_scan_summary.txt").write_text(
        f"Stage16 scoped evidence secret scan\n\nResult: {secret['status']}\nProblems: {secret['problem_count']}\n",
        encoding="utf-8",
    )
    write_docs(out_dir, report)
    return report


def write_docs(out_dir: Path, report: dict[str, Any]) -> None:
    bundle_manifest = "evidence/bench/swe_bench_stage16_full_sealed_20260628/bundle_manifest.json"
    strict = "evidence/bench/swe_bench_stage16_full_sealed_20260628/micro_tape_audit_strict/micro_tape_decision_dag_audit.json"
    readme = f"""# Stage16 Sealed Campaign Replay Packet

Scope: sealed replay campaign over the frozen Stage12 20-task Verified Mini shard.

This is not a full SWE-bench score claim. `stage16_full_pass_claim_allowed` is `{str(report['stage16_full_pass_claim_allowed']).lower()}` because `unsolved_count` is `{report['unsolved_count']}`.

Results:
- run_count: {report['run_count']}
- solved_count: {report['solved_count']}
- unsolved_count: {report['unsolved_count']}
- stage16_replay_campaign_pass: {report['stage16_replay_campaign_pass']}
- stage16_full_pass_claim_allowed: {report['stage16_full_pass_claim_allowed']}

Reproduction commands:

```bash
python3 -m py_compile \\
  tools/bench/audit_micro_tape_decision_dag.py \\
  tools/bench/audit_stage16_sealed_campaign.py \\
  tools/bench/build_stage16_sealed_campaign.py

pytest tests/test_stage16_sealed_campaign.py tests/test_micro_tape_decision_dag_audit.py -q

python3 tools/bench/audit_micro_tape_decision_dag.py \\
  --strict-vpput \\
  --strict-terminal-market \\
  --require-authorization-head \\
  --coverage evidence/bench/swe_bench_stage16_full_sealed_20260628/substrate_coverage.json \\
  --out-dir /tmp/turingos_stage16_strict_verify

python3 tools/bench/audit_stage16_sealed_campaign.py \\
  --root evidence/bench/swe_bench_stage16_full_sealed_20260628 \\
  --out-dir /tmp/turingos_stage16_verify
```

Claim boundary:
- PASS means sealed replay campaign honesty and VPPUT/ref/market/no-HITL discipline.
- PASS does not mean full SWE-bench all-pass.
- Full-score claim is forbidden until `unsolved_count == 0`.
- Stage16R remains open for unsolved repair.
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")
    prompt = f"""# External Auditor Prompt: Stage16

Audit the exact pushed GitHub SHA. Do not trust local summaries.

Evidence root: `evidence/bench/swe_bench_stage16_full_sealed_20260628/`

Required files:
- `{bundle_manifest}`
- `{strict}`
- `stage16_aggregate_report.json`
- `stage16_vpput_report.json`
- `stage16_replay_audit.json`
- `stage16_market_audit.json`
- `stage16_failure_memory_audit.json`
- `stage16_no_hitl_audit.json`
- `stage16_secret_scan_summary.txt`

Questions:
1. Can every listed `micro_tape.bundle` be fetched from GitHub and does its SHA-256 match `bundle_sha256s.txt`?
2. Does strict MicroTape audit PASS?
3. Does `stage16_aggregate_report.json` reconstruct solved/unsolved only from bundles?
4. Are solved instances exactly official PASS -> CandidateAccepted -> final PPUT progress=1?
5. Are unsolved instances exactly no CandidateAccepted -> terminal failure/budget -> final PPUT progress=0?
6. Does all cost come from CostEvent totals and final PPUT totals?
7. Are market settlement/reward terminal and non-sovereign?
8. Are no-HITL counters zero?
9. Is `stage16_full_pass_claim_allowed` false when unsolved_count > 0?
10. Does README avoid any full-score/all-pass claim?

Required verdict:
```text
stage16_replay_campaign: PASS|PARTIAL|FAIL
stage16_full_score_claim: ALLOWED|FORBIDDEN|OVERCLAIM
release_status: PASS|PARTIAL|FAIL|OVERCLAIM
```
"""
    (out_dir / "stage16_external_auditor_prompt.md").write_text(prompt, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)
    report = build_stage16_campaign(Path(args.source_root), Path(args.out_dir))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
