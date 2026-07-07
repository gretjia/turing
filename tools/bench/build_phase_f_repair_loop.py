#!/usr/bin/env python3
"""Build the Phase F repair-loop packet.

This packet does not repair Stage16R by rewriting history. It records the loop
decision that the current Phase F blockers require fresh Stage16R-real evaluator
bundles with worker-derived unified diffs and executable official evaluator logs.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import shutil
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
AUDITOR_PATH = REPO / "tools" / "bench" / "audit_phase_f_repair_loop.py"


def load_auditor() -> Any:
    spec = importlib.util.spec_from_file_location("audit_phase_f_repair_loop", AUDITOR_PATH)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"cannot load {AUDITOR_PATH}")
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def command_output(command: list[str]) -> str:
    result = subprocess.run(command, cwd=REPO, text=True, capture_output=True)
    return result.stdout.strip() if result.returncode == 0 else ""


def build_phase_f_repair_loop(phase_f_root: Path, out_dir: Path) -> dict[str, Any]:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    auditor = load_auditor()
    source_audit = load_json(phase_f_root / "official_eval_replay_audit.json")
    targets = auditor.phase_f_stage16r_targets(phase_f_root)
    target_ids = [str(item["instance_id"]) for item in targets]

    claim = {
        "schema_id": "PhaseFRepairClaimBoundary.v1",
        "artifact_kind": "PHASE_F_REPAIR_LOOP_BLOCKER_PACKET",
        "source_phase_f_root": str(phase_f_root),
        "source_phase_f_status": source_audit.get("status"),
        "not_full_swe_bench_dataset": True,
        "full_dataset_claim_allowed": False,
        "full_swe_bench_score_claim_allowed": False,
        "leaderboard_equivalence_claim_allowed": False,
        "phase_g_release_allowed": False,
        "purpose": "Decide whether Phase F can be repaired from existing evidence or must loop back to fresh Stage16R-real evaluator bundles.",
    }
    write_json(out_dir / "CLAIM_BOUNDARY.json", claim)
    repair_targets = [
        {
            "instance_id": instance_id,
            "source_phase_f_candidate_patch_path": str(phase_f_root / str(item["candidate_patch_path"])),
            "source_phase_f_test_patch_path": str(phase_f_root / str(item["test_patch_path"])),
            "old_microtape_immutable": True,
            "repair_strategy": "supersede_not_rewrite",
            "candidate_source": "worker_derived_patch_required",
            "required_next_action": "fresh_stage16r_real_evaluator_bundle",
        }
        for instance_id, item in zip(target_ids, targets)
    ]
    manifest = {
        "schema_id": "PhaseFRepairLoopManifest.v1",
        "created_from_commit": command_output(["git", "rev-parse", "HEAD"]),
        "source_phase_f_status": source_audit.get("status"),
        "source_phase_f_release_next_phase_g": source_audit.get("release_next_phase_g"),
        "repair_target_count": len(repair_targets),
        "repair_targets": repair_targets,
        "old_microtape_immutable": True,
        "dataset_gold_patch_use_allowed": False,
        "loop_decision": "blocked_until_fresh_stage16r_real_evaluator_bundles",
    }
    write_json(out_dir / "repair_manifest.json", manifest)
    report = auditor.audit_phase_f_repair_loop(phase_f_root, out_dir)
    write_json(out_dir / "phase_f_repair_loop_audit.json", report)
    write_json(
        out_dir / "blocker_manifest.json",
        {
            "schema_id": "PhaseFRepairBlockerManifest.v1",
            "status": report["status"],
            "blocked_by": report["blocked_by"],
            "repair_targets": report["repair_targets"],
        },
    )
    write_json(
        out_dir / "secret_scan_summary.json",
        {
            "schema_id": "PhaseFRepairSecretScan.v1",
            "status": report["secret_scan_status"],
            "problem_count": len(report.get("secret_scan_problems", [])),
            "problems": report.get("secret_scan_problems", []),
        },
    )
    write_docs(out_dir, report, target_ids)
    return report


def write_docs(out_dir: Path, report: dict[str, Any], target_ids: list[str]) -> None:
    targets = "\n".join(f"- {item}" for item in target_ids)
    blockers = "\n".join(f"- {item}" for item in report.get("blocked_by", [])) or "- none"
    readme = f"""# Phase F Repair Loop

Scope: repair-loop decision packet for Phase F evaluator proof.

This packet does not rewrite Stage16R or claim full SWE-bench status. It records that Phase F cannot release Phase G until the Stage16R repair artifacts are superseded by worker-derived unified diffs and executable official evaluator logs.

Result:
- status: {report['status']}
- repair_target_count: {report['repair_target_count']}
- replayable_repair_bundle_count: {report['replayable_repair_bundle_count']}
- release_next_phase_g: {report['release_next_phase_g']}
- full_swe_bench_score_claim_allowed: false
- full_dataset_claim_allowed: false
- leaderboard_equivalence_claim_allowed: false

Repair targets:
{targets}

Blockers:
{blockers}

Acceptance commands:

```bash
python3 -m py_compile \\
  tools/bench/audit_phase_f_repair_loop.py \\
  tools/bench/build_phase_f_repair_loop.py \\
  tools/bench/audit_phase_f_evaluator_proof.py

pytest \\
  tests/test_phase_f_repair_loop.py \\
  tests/test_phase_f_evaluator_proof.py \\
  -q

python3 tools/bench/audit_phase_f_repair_loop.py \\
  --phase-f-root evidence/bench/swe_bench_phase_f_evaluator_proof_20260628 \\
  --root evidence/bench/swe_bench_phase_f_repair_loop_20260628 \\
  --out /tmp/turingos_phase_f_repair_loop_audit.json
```
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")

    contract = """# Next Contract: Stage16R Real Evaluator Bundles

Required next loop:

1. Do not rewrite existing Stage16R bundles.
2. For each Phase F repair target, run a fresh retry attempt that produces a worker-derived unified diff.
3. Run the batch evaluator with the recorded task manifest and real patch artifact.
4. Import official evaluator evidence into a fresh MicroTape bundle.
5. CandidateAccepted may occur only after official PASS.
6. MarketSettled, RewardDistributed, and final PPUTAccounted remain terminal-basis and preserve-only.
7. Public evidence must include candidate patch, test patch, apply logs, target test logs, command, environment digest, stdout/stderr digests, and bundle SHA.
8. Dataset `patch` / gold patch fields are forbidden as candidate patch sources.

Release rule:

```text
Phase G release remains blocked until audit_phase_f_evaluator_proof reports:
  status: PASS
  official_evaluator_executable_replay: true
  release_next_phase_g: true
```
"""
    (out_dir / "next_stage16r_real_evaluator_contract.md").write_text(contract, encoding="utf-8")

    prompt = """# External Auditor Prompt: Phase F Repair Loop

Audit the exact pushed SHA and this evidence root.

Expected scoped verdict for the current packet:

```text
phase_f_repair_loop_status: BLOCKED
release_next_phase_g: NO
gold_patch_shortcut: FORBIDDEN
old_stage16r_tape_rewrite: FORBIDDEN
required_next_action: fresh Stage16R-real evaluator bundles
```

Check that this packet does not claim full dataset, full SWE-bench score, leaderboard equivalence, or Phase G release.
"""
    (out_dir / "phase_f_repair_external_auditor_prompt.md").write_text(prompt, encoding="utf-8")

    independent = """# Phase F Repair Loop Recursive Audit

Status: pending external audit on exact pushed SHA.

Expected scope: this packet should block Phase G and require fresh Stage16R-real evaluator bundles.
"""
    (out_dir / "independent_recursive_audit.md").write_text(independent, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase-f-root", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)
    report = build_phase_f_repair_loop(Path(args.phase_f_root), Path(args.out_dir))
    return 0 if report["status"] in {"PASS", "BLOCKED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
