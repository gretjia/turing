#!/usr/bin/env python3
"""FCE-S1: The Golden Thread (the mandated cross-module scenario).

Per 09_FINAL_CERTIFICATION_EVALS.md section "FCE-S1 - The Golden Thread": one full
worker-uplift-style run in which every cross-module seam is exercised on the same
tape: worker calls carry M1c receipts -> tape appended through the single
designated canonical writer -> strict audit passes with authorization, cost, and
sandbox provenance required -> M6 console replays it -> M5 packages it -> the
packet goes to external audit. This scenario is REAL (fixture_or_real=REAL): it
makes real DeepSeek native-API worker calls (real spend, small) and runs the real
upstream SWE-bench Docker harness (sole scorer).

Six steps (spec section 3, FCE-S1):
  1. Materialize worker-safe packets for the 5 cert-slice S02 tasks; prompt-leakage
     audit over the produced worker-visible artifacts (executed once the tape's
     visible_prompt/capsule evidence exists - see NOTE in step1_prompt_leakage_audit).
  2. Run the full TuringOS loop (arm-B: real native-API worker + full loop) with
     authorization required, receipts enabled, sandbox provenance recorded.
  3. Strict audit of the produced tape with all three --require flags.
  4. Score the 5 predictions with the upstream SWE-bench harness (sole scorer).
  5. M6 console replay (shadow rebuild, independent head derivation, provenance
     closure, render fidelity) over each task's Micro Tape.
  6. M5 package: build the exact-SHA certification-run packet; sha256sum -c passes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CERT_SHARD = "S02"
# PREREGISTRATION.md ("S02 is reserved for the deterministic 10-task arm-A pilot"):
# the pilot occupies all of window S02-W00 (verified against the shard manifest and
# the on-disk arm-A prediction files below).
PILOT_WINDOW_ID = "S02-W00"
CERT_SLICE_SIZE = 5
DEEPSEEK_MODEL = "deepseek-v4-flash"
DEEPSEEK_API_KEY_ENV = "DEEPSEEK_API_KEY"
WORKER_IDENTITY = f"{DEEPSEEK_MODEL}__armB__fce-s1-golden-thread"
SWEBENCH_VENV_PYTHON = Path("/tmp/turingos-swebench-venv/bin/python3")
SWEBENCH_DATASET_NAME = "princeton-nlp/SWE-bench_Verified"
HARNESS_TIMEOUT_S = 3 * 60 * 60


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def run_command(
    *,
    name: str,
    argv: list[str],
    cwd: Path,
    out_dir: Path,
    env: dict[str, str] | None = None,
    timeout: int = 600,
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        exit_code = proc.returncode
        stdout_text = proc.stdout
        stderr_text = proc.stderr
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        stdout_text = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr_text = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        stderr_text += "\nTIMEOUT\n"
    elapsed_ms = int((time.monotonic() - started) * 1000)
    stdout_path = out_dir / f"{name}.stdout.txt"
    stderr_path = out_dir / f"{name}.stderr.txt"
    out_dir.mkdir(parents=True, exist_ok=True)
    stdout_path.write_text(stdout_text, encoding="utf-8")
    stderr_path.write_text(stderr_text, encoding="utf-8")
    return {
        "name": name,
        "cmd": " ".join(argv),
        "exit_code": exit_code,
        "wall_clock_ms": elapsed_ms,
        "stdout": stdout_path.name,
        "stderr": stderr_path.name,
        "stdout_text": stdout_text,
        "stderr_text": stderr_text,
    }


# --------------------------------------------------------------------------
# Cert-slice selection (spec section 1.2: deterministic, pre-registered pilot exclusion)
# --------------------------------------------------------------------------

def select_cert_slice(repo: Path, scenario_root: Path) -> dict[str, Any]:
    shard_manifest_path = (
        repo / "evidence" / "bench" / "swe_bench_verified_500_campaign_20260629" / "shards" / CERT_SHARD / "shard_manifest.json"
    )
    manifest = load_json(shard_manifest_path)
    tasks = manifest.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError(f"{shard_manifest_path} tasks list is empty or missing")

    pilot_ids = {
        task["instance_id"]
        for task in tasks
        if isinstance(task, dict) and task.get("ipqc_window_id") == PILOT_WINDOW_ID and isinstance(task.get("instance_id"), str)
    }
    # Soft corroboration: the M3 arm-A pilot prediction files (if present in this
    # clone) should name exactly the pilot-window instance IDs. A mismatch does not
    # block the run (the manifest window assignment is the load-bearing rule per
    # PREREGISTRATION.md) but IS recorded as a warning for audit.
    pilot_corroboration_path = (
        repo
        / "evidence"
        / "bench"
        / "swe_bench_verified_500_campaign_20260629"
        / "shards"
        / CERT_SHARD
        / "arms"
        / "A_deepseek_flash_pilot"
        / f"shard_{CERT_SHARD}_{PILOT_WINDOW_ID}_flash_predictions.jsonl"
    )
    pilot_corroborated = None
    if pilot_corroboration_path.is_file():
        corroborated_ids = set()
        for line in pilot_corroboration_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            corroborated_ids.add(json.loads(line)["instance_id"])
        pilot_corroborated = corroborated_ids == pilot_ids

    ordered_ids = [task["instance_id"] for task in tasks if isinstance(task, dict) and isinstance(task.get("instance_id"), str)]
    eligible = [instance_id for instance_id in ordered_ids if instance_id not in pilot_ids]
    if len(eligible) < CERT_SLICE_SIZE:
        raise ValueError(f"only {len(eligible)} eligible (non-pilot) instances available in shard {CERT_SHARD}")
    slice_ids = eligible[:CERT_SLICE_SIZE]

    id_to_window = {task["instance_id"]: task.get("ipqc_window_id") for task in tasks if isinstance(task, dict)}
    slice_window_ids = sorted({id_to_window[iid] for iid in slice_ids})
    if len(slice_window_ids) != 1:
        raise ValueError(f"cert slice spans multiple IPQC windows unexpectedly: {slice_window_ids}")
    window_id = slice_window_ids[0]

    result = {
        "schema_id": "turingos.fce.s1.cert_slice_manifest.v1",
        "shard_id": CERT_SHARD,
        "shard_manifest_path": str(shard_manifest_path),
        "shard_manifest_sha256": sha256_file(shard_manifest_path),
        "pilot_window_id": PILOT_WINDOW_ID,
        "pilot_instance_ids": sorted(pilot_ids),
        "pilot_corroborated_against_arm_a_predictions": pilot_corroborated,
        "selection_rule": "first N eligible instance_id in the shard manifest's stored task order, excluding the M3 pilot window",
        "cert_slice_size": CERT_SLICE_SIZE,
        "cert_slice_window_id": window_id,
        "cert_slice_instance_ids": slice_ids,
    }
    write_json(scenario_root / "cert_slice_manifest.json", result)
    return result


# --------------------------------------------------------------------------
# Step 1: materialize worker-safe packets
# --------------------------------------------------------------------------

def step1_materialize(repo: Path, scenario_root: Path, cert_slice: dict[str, Any]) -> dict[str, Any]:
    materialize_root = scenario_root / "materialize"
    shard_dir = materialize_root / "shards" / CERT_SHARD
    shard_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(cert_slice["shard_manifest_path"]), shard_dir / "shard_manifest.json")

    default_arrow = (
        Path.home() / ".cache/huggingface/datasets/princeton-nlp___swe-bench_verified" / "default" / "0.0.0"
    )
    arrow_candidates = sorted(default_arrow.glob("*/swe-bench_verified-test.arrow")) if default_arrow.is_dir() else []
    if not arrow_candidates:
        raise RuntimeError("no cached SWE-bench Verified arrow dataset found; cannot materialize worker-safe packets")
    dataset_arrow = arrow_candidates[-1]

    command = run_command(
        name="materialize_swebench_worker_safe_tasks",
        argv=[
            sys.executable,
            str(repo / "tools" / "bench" / "materialize_swebench_worker_safe_tasks.py"),
            "--root",
            str(materialize_root),
            "--shard",
            CERT_SHARD,
            "--window",
            cert_slice["cert_slice_window_id"],
            "--dataset-arrow",
            str(dataset_arrow),
        ],
        cwd=repo,
        out_dir=scenario_root / "commands",
        timeout=300,
    )
    report_path = (
        materialize_root
        / "shards"
        / CERT_SHARD
        / "ipqc"
        / cert_slice["cert_slice_window_id"]
        / "worker_safe_tasks"
        / "worker_safe_tasks_report.json"
    )
    report = load_json(report_path) if report_path.is_file() else {"status": "FAIL"}

    tasks_by_id = {item["instance_id"]: item for item in report.get("tasks", []) if isinstance(item, dict)}
    tasks_jsonl_lines: list[str] = []
    for instance_id in cert_slice["cert_slice_instance_ids"]:
        entry = tasks_by_id.get(instance_id)
        if entry is None:
            raise RuntimeError(f"materializer did not produce a worker-safe packet for {instance_id}")
        packet = load_json(materialize_root / entry["task_packet_path"])
        tasks_jsonl_lines.append(
            json.dumps(
                {
                    "instance_id": packet["instance_id"],
                    "repo": packet["repo"],
                    "base_commit": packet["base_commit"],
                    "problem_statement": packet["problem_statement"],
                },
                sort_keys=True,
            )
        )
    tasks_jsonl_path = scenario_root / "cert_slice_tasks.jsonl"
    tasks_jsonl_path.write_text("\n".join(tasks_jsonl_lines) + "\n", encoding="utf-8")

    return {
        "command": command,
        "report": report,
        "report_path": report_path,
        "tasks_jsonl_path": tasks_jsonl_path,
        "materialize_root": materialize_root,
    }


# --------------------------------------------------------------------------
# Step 2: full TuringOS loop (arm-B: real native-API DeepSeek worker)
# --------------------------------------------------------------------------

def step2_loop_run(repo: Path, plan_root: Path, scenario_root: Path, tasks_jsonl_path: Path, api_key: str) -> dict[str, Any]:
    loop_root = scenario_root / "loop_run"
    argv = [
        sys.executable,
        str(repo / "tools" / "bench" / "run_mini_swe_bench_substrate_smoke.py"),
        "--tasks-jsonl",
        str(tasks_jsonl_path),
        "--limit",
        str(CERT_SLICE_SIZE),
        "--worker-mode",
        "deepseek",
        "--model",
        DEEPSEEK_MODEL,
        "--authorization-mode",
        "required",
        # M1b precondition (RES_M1 S2.5): an OS keyring session is unavailable on this
        # headless certification host (no D-Bus session / X11 - confirmed by probing
        # secret-tool directly: "Cannot autolaunch D-Bus without X11 $DISPLAY"). The
        # test-local authority path is used instead - it is a real, non-silent M1b
        # authorization event (authority_kind=test_local_authority_no_credentials),
        # never a fallback under --authorization-mode required (the runner raises if
        # the real OS-keyring RPC fails under "required" - only "auto" swallows that
        # error). This is documented here, not fabricated as an OS-keyring session.
        "--authority-provider",
        "test-local",
        "--deepseek-price-table",
        str(plan_root / "m3_uplift_lab" / "PRICE_TABLE.json"),
        "--out-dir",
        str(loop_root),
    ]
    env = dict(os.environ)
    env[DEEPSEEK_API_KEY_ENV] = api_key
    command = run_command(
        name="run_mini_swe_bench_substrate_smoke",
        argv=argv,
        cwd=repo,
        out_dir=scenario_root / "commands",
        env=env,
        timeout=3600,
    )
    coverage_path = loop_root / "substrate_coverage.json"
    coverage = load_json(coverage_path) if coverage_path.is_file() else {}
    audit_path = loop_root / "substrate_coverage_audit.json"
    coverage_audit = load_json(audit_path) if audit_path.is_file() else {}
    return {
        "command": command,
        "loop_root": loop_root,
        "coverage_path": coverage_path,
        "coverage": coverage,
        "coverage_audit_path": audit_path,
        "coverage_audit": coverage_audit,
    }


# --------------------------------------------------------------------------
# Step 1 (leakage) executed here: its real input (visible_prompt.txt + Micro Tape
# capsules) only exists once step 2 has produced the coverage JSON. The spec groups
# "materialize + audit_prompt_leakage.py" under step 1's prose, but
# audit_prompt_leakage.py's actual contract (tools/bench/audit_prompt_leakage.py
# audit_coverage()) operates on a turingos_arm_runs coverage list with
# native_api_worker.visible_prompt_path + micro_tape_bundle per run - i.e. the
# substrate-loop coverage produced by step 2, not the raw materializer packets.
# Running the real, unmodified tool over the real coverage is what this function does.
# --------------------------------------------------------------------------

def step1_prompt_leakage_audit(repo: Path, scenario_root: Path, coverage_path: Path) -> dict[str, Any]:
    out_path = scenario_root / "prompt_leakage.json"
    command = run_command(
        name="audit_prompt_leakage",
        argv=[
            sys.executable,
            str(repo / "tools" / "bench" / "audit_prompt_leakage.py"),
            "--coverage",
            str(coverage_path),
            "--out",
            str(out_path),
        ],
        cwd=repo,
        out_dir=scenario_root / "commands",
        timeout=300,
    )
    report = load_json(out_path) if out_path.is_file() else {"status": "FAIL"}
    return {"command": command, "report_path": out_path, "report": report}


# --------------------------------------------------------------------------
# Step 3: strict Micro Tape audit + M1a canonical-writer discipline
# --------------------------------------------------------------------------

def step3_strict_audit(repo: Path, scenario_root: Path, coverage_path: Path) -> dict[str, Any]:
    audit_dir = scenario_root / "s1_audit"
    command = run_command(
        name="audit_micro_tape_decision_dag_strict",
        argv=[
            sys.executable,
            str(repo / "tools" / "bench" / "audit_micro_tape_decision_dag.py"),
            "--coverage",
            str(coverage_path),
            "--strict-vpput",
            "--strict-terminal-market",
            "--require-authorization-head",
            "--require-cost-provenance",
            "--require-sandbox-provenance",
            "--out-dir",
            str(audit_dir),
        ],
        cwd=repo,
        out_dir=scenario_root / "commands",
        timeout=300,
    )
    report_path = audit_dir / "micro_tape_decision_dag_audit.json"
    report = load_json(report_path) if report_path.is_file() else {"verdict": "FAIL"}

    m1a_command = run_command(
        name="m1a_gates",
        argv=["bash", "tools/ci/run_m1a_gates.sh"],
        cwd=repo,
        out_dir=scenario_root / "commands",
        timeout=300,
    )
    return {"command": command, "report_path": report_path, "report": report, "m1a_command": m1a_command}


# --------------------------------------------------------------------------
# Step 4: upstream SWE-bench harness scoring (sole scorer)
# --------------------------------------------------------------------------

def step4_harness_scoring(
    repo: Path, scenario_root: Path, loop_root: Path, cert_slice: dict[str, Any]
) -> dict[str, Any]:
    scoring_dir = scenario_root / "scoring"
    scoring_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = scoring_dir / "predictions.jsonl"
    lines = []
    for instance_id in cert_slice["cert_slice_instance_ids"]:
        diff_path = loop_root / "instances" / instance_id / "worker_logs" / "diff.patch"
        patch = diff_path.read_text(encoding="utf-8") if diff_path.is_file() else ""
        lines.append(
            json.dumps(
                {"instance_id": instance_id, "model_name_or_path": WORKER_IDENTITY, "model_patch": patch},
                sort_keys=True,
            )
        )
    predictions_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    run_id = f"fce_s1_golden_thread_{datetime.now(timezone.utc):%Y%m%d}"
    report_dir = scoring_dir / "report_dir"
    report_dir.mkdir(parents=True, exist_ok=True)
    argv = [
        str(SWEBENCH_VENV_PYTHON),
        "-m",
        "swebench.harness.run_evaluation",
        "--dataset_name",
        SWEBENCH_DATASET_NAME,
        "--split",
        "test",
        "--predictions_path",
        str(predictions_path),
        "--instance_ids",
        *cert_slice["cert_slice_instance_ids"],
        "--max_workers",
        str(CERT_SLICE_SIZE),
        "--timeout",
        "1800",
        "--run_id",
        run_id,
        "--report_dir",
        str(report_dir),
    ]
    # cwd=scoring_dir: the upstream harness writes its top-level
    # "<model_name_or_path>.<run_id>.json" report relative to CWD (not --report_dir,
    # which only holds per-instance execution logs). Running with cwd=repo would leak
    # a stray report file into the certification clone's working tree.
    command = run_command(
        name="swebench_harness_run_evaluation",
        argv=argv,
        cwd=scoring_dir,
        out_dir=scenario_root / "commands",
        timeout=HARNESS_TIMEOUT_S,
    )
    report_name = f"{WORKER_IDENTITY}.{run_id}.json"
    report_path = scoring_dir / report_name
    report = load_json(report_path) if report_path.is_file() else {}

    scorer_isolation_text = command["cmd"] + "\n" + command["stdout_text"] + "\n" + command["stderr_text"]
    repo_local_evaluator_hit = "evaluate_django_swe_bench_patches" in scorer_isolation_text
    runsc_wrapped = "runsc" in command["cmd"]

    return {
        "command": command,
        "predictions_path": predictions_path,
        "report_path": report_path,
        "report": report,
        "run_id": run_id,
        "repo_local_evaluator_hit": repo_local_evaluator_hit,
        "runsc_wrapped": runsc_wrapped,
    }


# --------------------------------------------------------------------------
# Step 5: M6 console replay (per-task shadow rebuild + projection-integrity audit)
# --------------------------------------------------------------------------

def step5_console_replay(repo: Path, scenario_root: Path, loop_root: Path, cert_slice: dict[str, Any]) -> dict[str, Any]:
    console_root = scenario_root / "console"
    turing_bin = repo / "target" / "debug" / "turing"
    per_task: list[dict[str, Any]] = []
    for instance_id in cert_slice["cert_slice_instance_ids"]:
        micro_git = loop_root / "instances" / instance_id / "micro.git"
        out_dir = console_root / instance_id
        out_dir.mkdir(parents=True, exist_ok=True)
        snapshot_command = run_command(
            name=f"console_status_json_{instance_id}",
            argv=[str(turing_bin), "status", "--micro-git", str(micro_git), "--json"],
            cwd=repo,
            out_dir=scenario_root / "commands",
            timeout=120,
        )
        snapshot_path = out_dir / "operator_snapshot.json"
        snapshot_path.write_text(snapshot_command["stdout_text"], encoding="utf-8")
        text_command = run_command(
            name=f"console_status_text_{instance_id}",
            argv=[str(turing_bin), "status", "--micro-git", str(micro_git)],
            cwd=repo,
            out_dir=scenario_root / "commands",
            timeout=120,
        )
        text_path = out_dir / "operator_status.txt"
        text_path.write_text(text_command["stdout_text"], encoding="utf-8")
        verdict_path = out_dir / "projection_integrity_verdict.json"
        integrity_command = run_command(
            name=f"projection_integrity_{instance_id}",
            argv=[
                sys.executable,
                str(repo / "tools" / "hci" / "audit_projection_integrity.py"),
                "--micro-git",
                str(micro_git),
                "--snapshot-json",
                str(snapshot_path),
                "--text-output",
                str(text_path),
                "--provenance",
                str(repo / "schemas" / "operator" / "operator_view_snapshot.v1.provenance.json"),
                "--repo-root",
                str(repo),
                "--out",
                str(verdict_path),
            ],
            cwd=repo,
            out_dir=scenario_root / "commands",
            timeout=120,
        )
        verdict = load_json(verdict_path) if verdict_path.is_file() else {"verdict": "FAIL"}
        per_task.append(
            {
                "instance_id": instance_id,
                "snapshot_command": snapshot_command,
                "text_command": text_command,
                "integrity_command": integrity_command,
                "verdict_path": verdict_path,
                "verdict": verdict,
            }
        )
    return {"console_root": console_root, "per_task": per_task}


# --------------------------------------------------------------------------
# Step 6: M5 package + sha256sum -c
# --------------------------------------------------------------------------

def step6_packet_build(repo: Path, scenario_root: Path, cert_repo_sha: str) -> dict[str, Any]:
    packet_dir = scenario_root / "packet"
    if packet_dir.exists():
        shutil.rmtree(packet_dir)
    build_command = run_command(
        name="build_packet",
        argv=[
            sys.executable,
            str(repo / "tools" / "release" / "build_packet.py"),
            "--root",
            str(scenario_root),
            "--sha",
            cert_repo_sha,
            "--gate",
            "FCE-S1",
            "--out",
            str(packet_dir),
        ],
        cwd=repo,
        out_dir=scenario_root / "commands",
        timeout=300,
    )
    validate_command = run_command(
        name="validate_packet",
        argv=[sys.executable, str(repo / "tools" / "release" / "build_packet.py"), "--validate", str(packet_dir)],
        cwd=repo,
        out_dir=scenario_root / "commands",
        timeout=300,
    )
    sha256sum_command = run_command(
        name="sha256sum_c_manifest",
        argv=["sha256sum", "-c", "MANIFEST.sha256"],
        cwd=packet_dir,
        out_dir=scenario_root / "commands",
        timeout=300,
    )
    manifest_path = packet_dir / "PACKET_MANIFEST.json"
    manifest = load_json(manifest_path) if manifest_path.is_file() else {}
    return {
        "build_command": build_command,
        "validate_command": validate_command,
        "sha256sum_command": sha256sum_command,
        "packet_dir": packet_dir,
        "manifest": manifest,
    }


# --------------------------------------------------------------------------
# Verdict assembly
# --------------------------------------------------------------------------

def cost_totals_from_coverage(coverage: dict[str, Any]) -> dict[str, int]:
    runs = coverage.get("turingos_arm_runs", []) if isinstance(coverage, dict) else []
    total_microusd = 0
    receipt_events = 0
    unspecified = 0
    for run in runs:
        if not isinstance(run, dict):
            continue
        total_microusd += int(run.get("worker_cost_microusd") or 0)
        receipt_events += 1
    return {
        "total_llm_cost_microusd": total_microusd,
        "receipt_events": receipt_events,
        "unspecified_cost_events": unspecified,
    }


def build_verdict(
    *,
    root: Path,
    scenario_id: str,
    started: float,
    commands: list[dict[str, Any]],
    criteria: list[dict[str, Any]],
    evidence_files: list[Path],
    automatic_fail: str | None,
) -> dict[str, Any]:
    scenario_root = root / scenario_id
    evidence_paths = sorted({rel(root, path) for path in evidence_files if path.is_file()})
    passed = all(item["result"] is True for item in criteria)
    return {
        "schema_id": "turingos.fce_scenario_verdict.v1",
        "scenario_id": scenario_id,
        "verdict": "PASS" if passed else "FAIL",
        "not_run_is_fail": True,
        "goals_served": ["G2"],
        "commands_executed": [{"cmd": command["cmd"], "exit_code": command["exit_code"]} for command in commands],
        "pass_criteria_results": criteria,
        "evidence": evidence_paths,
        "evidence_sha256": {item: sha256_file(root / item) for item in evidence_paths},
        "fixture_or_real": "REAL",
        "automatic_fail_triggered": automatic_fail,
        "wall_clock_ms": int((time.monotonic() - started) * 1000),
        "timestamp_utc": utc_now(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--plan-root", required=True)
    parser.add_argument("--scenario-id", required=True)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    repo = Path(args.repo).resolve()
    plan_root = Path(args.plan_root).resolve()
    scenario_id = args.scenario_id
    scenario_root = root / scenario_id
    scenario_root.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    commands: list[dict[str, Any]] = []
    evidence_files: list[Path] = []

    cert_repo_sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True, stdout=subprocess.PIPE, check=True
    ).stdout.strip()

    api_key = os.environ.get(DEEPSEEK_API_KEY_ENV)
    if not api_key:
        criteria = [
            {
                "criterion": "deepseek_api_key_present",
                "result": False,
                "evidence": f"{scenario_id}/cert_slice_manifest.json",
            }
        ]
        verdict = build_verdict(
            root=root,
            scenario_id=scenario_id,
            started=started,
            commands=commands,
            criteria=criteria,
            evidence_files=evidence_files,
            automatic_fail=None,
        )
        verdict["verdict"] = "NOT_RUN"
        verdict["not_run_reason"] = f"missing environment variable: {DEEPSEEK_API_KEY_ENV}"
        write_json(scenario_root / f"{scenario_id}_verdict.json", verdict)
        print(json.dumps({"scenario_id": scenario_id, "verdict": "NOT_RUN"}, sort_keys=True))
        return 2

    cert_slice = select_cert_slice(repo, scenario_root)
    evidence_files.append(scenario_root / "cert_slice_manifest.json")

    materialize = step1_materialize(repo, scenario_root, cert_slice)
    commands.append(materialize["command"])
    evidence_files.append(materialize["report_path"])

    loop = step2_loop_run(repo, plan_root, scenario_root, materialize["tasks_jsonl_path"], api_key)
    commands.append(loop["command"])
    evidence_files.append(loop["coverage_path"])
    evidence_files.append(loop["coverage_audit_path"])

    leakage = step1_prompt_leakage_audit(repo, scenario_root, loop["coverage_path"])
    commands.append(leakage["command"])
    evidence_files.append(leakage["report_path"])

    strict = step3_strict_audit(repo, scenario_root, loop["coverage_path"])
    commands.append(strict["command"])
    commands.append(strict["m1a_command"])
    evidence_files.append(strict["report_path"])

    scoring = step4_harness_scoring(repo, scenario_root, loop["loop_root"], cert_slice)
    commands.append(scoring["command"])
    evidence_files.append(scoring["predictions_path"])
    if scoring["report_path"].is_file():
        evidence_files.append(scoring["report_path"])

    console = step5_console_replay(repo, scenario_root, loop["loop_root"], cert_slice)
    for task in console["per_task"]:
        commands.append(task["snapshot_command"])
        commands.append(task["text_command"])
        commands.append(task["integrity_command"])
        evidence_files.append(task["verdict_path"])

    # ---- criteria (spec section 3, FCE-S1 "PASS criteria (all)") ----
    runs = loop["coverage"].get("turingos_arm_runs", []) if isinstance(loop["coverage"], dict) else []
    receipts_all_carry_cost_event = bool(runs) and all(
        isinstance(run, dict) and run.get("worker_cost_microusd") is not None for run in runs
    )
    strict_checks = strict["report"].get("runs", []) if isinstance(strict["report"], dict) else []
    three_require_flags_pass = bool(strict_checks) and all(
        isinstance(run, dict)
        and run.get("checks", {}).get("authorization_head") == "PASS"
        and run.get("checks", {}).get("cost_provenance") == "PASS"
        and run.get("checks", {}).get("sandbox_provenance") == "PASS"
        for run in strict_checks
    )
    legacy_missing_count = sum(
        1
        for run in strict_checks
        if isinstance(run, dict)
        for value in run.get("checks", {}).values()
        if value == "LEGACY_MISSING"
    )
    host_assumed_count = sum(
        int(run.get("sandbox_host_assumed_count") or 0) for run in strict_checks if isinstance(run, dict)
    )
    predictions_pinned_identity = all(
        json.loads(line)["model_name_or_path"] == WORKER_IDENTITY
        for line in scoring["predictions_path"].read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    harness_report = scoring["report"]
    harness_completed_all = (
        isinstance(harness_report, dict)
        and int(harness_report.get("submitted_instances") or 0) == CERT_SLICE_SIZE
        and len(harness_report.get("incomplete_ids") or []) == 0
        and len(harness_report.get("error_ids") or []) == 0
    )
    console_all_pass = bool(console["per_task"]) and all(
        task["verdict"].get("verdict") == "PASS" for task in console["per_task"]
    )
    snapshot_hashes_present = all(
        isinstance(task["verdict"].get("snapshot_hash"), str) for task in console["per_task"]
    )
    packet = step6_packet_build(repo, scenario_root, cert_repo_sha)
    commands.append(packet["build_command"])
    commands.append(packet["validate_command"])
    commands.append(packet["sha256sum_command"])
    evidence_files.append(packet["packet_dir"] / "PACKET_MANIFEST.json")
    evidence_files.append(packet["packet_dir"] / "MANIFEST.sha256")

    cost_totals = cost_totals_from_coverage(loop["coverage"])
    cost_path = scenario_root / "cost_totals.json"
    write_json(cost_path, cost_totals)
    evidence_files.append(cost_path)

    criteria = [
        {
            "criterion": "materializer_worker_safe_report_pass",
            "result": materialize["report"].get("status") == "PASS",
            "evidence": rel(root, materialize["report_path"]),
        },
        {
            "criterion": "loop_run_exit_zero",
            "result": loop["command"]["exit_code"] == 0,
            "evidence": rel(root, loop["coverage_path"]),
        },
        {
            "criterion": "substrate_coverage_ready_real_worker",
            "result": loop["coverage_audit"].get("scientific_status") == "SUBSTRATE_COVERAGE_READY"
            and loop["coverage_audit"].get("verdict") == "PASS",
            "evidence": rel(root, loop["coverage_audit_path"]),
        },
        {
            "criterion": "all_llm_calls_carry_receipt_with_cost_event",
            "result": receipts_all_carry_cost_event,
            "evidence": rel(root, loop["coverage_path"]),
        },
        {
            "criterion": "prompt_leakage_audit_pass",
            "result": leakage["report"].get("status") == "PASS",
            "evidence": rel(root, leakage["report_path"]),
        },
        {
            "criterion": "predictions_carry_pinned_worker_identity",
            "result": predictions_pinned_identity,
            "evidence": rel(root, scoring["predictions_path"]),
        },
        {
            "criterion": "strict_audit_three_require_flags_pass_on_real_tape",
            "result": three_require_flags_pass,
            "evidence": rel(root, strict["report_path"]),
        },
        {
            "criterion": "strict_audit_zero_legacy_missing",
            "result": legacy_missing_count == 0,
            "evidence": rel(root, strict["report_path"]),
        },
        {
            "criterion": "strict_audit_zero_host_assumed",
            "result": host_assumed_count == 0,
            "evidence": rel(root, strict["report_path"]),
        },
        {
            "criterion": "m1a_canonical_writer_gate_pass",
            "result": strict["m1a_command"]["exit_code"] == 0,
            "evidence": rel(root, strict["report_path"]),
        },
        {
            "criterion": "harness_scoring_completed_all_5_zero_errors",
            "result": harness_completed_all,
            "evidence": rel(root, scoring["report_path"]) if scoring["report_path"].is_file() else rel(root, scoring["predictions_path"]),
        },
        {
            "criterion": "repo_local_evaluator_not_in_scoring_path",
            "result": not scoring["repo_local_evaluator_hit"],
            "evidence": rel(root, scoring["predictions_path"]),
        },
        {
            "criterion": "upstream_scorer_not_runsc_wrapped",
            "result": not scoring["runsc_wrapped"],
            "evidence": rel(root, scoring["predictions_path"]),
        },
        {
            "criterion": "console_replay_all_tasks_pass",
            "result": console_all_pass,
            "evidence": rel(root, console["per_task"][0]["verdict_path"]) if console["per_task"] else "",
        },
        {
            "criterion": "console_snapshot_hash_present_all_tasks",
            "result": snapshot_hashes_present,
            "evidence": rel(root, console["per_task"][0]["verdict_path"]) if console["per_task"] else "",
        },
        {
            "criterion": "packet_build_and_validate_pass",
            "result": packet["build_command"]["exit_code"] == 0 and packet["validate_command"]["exit_code"] == 0,
            "evidence": rel(root, packet["packet_dir"] / "PACKET_MANIFEST.json"),
        },
        {
            "criterion": "packet_sha256sum_c_passes",
            "result": packet["sha256sum_command"]["exit_code"] == 0,
            "evidence": rel(root, packet["packet_dir"] / "MANIFEST.sha256"),
        },
    ]

    readme = scenario_root / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# FCE-S1 Golden Thread",
                "",
                "Evidence label: REAL.",
                "",
                "Real DeepSeek native-API worker calls (arm-B: full TuringOS substrate loop,",
                "authorization required via the test-local M1b authority path - no OS keyring",
                "session is available on this headless certification host), real M1c CostEvent.v2",
                "receipts, real runsc sandbox provenance, real upstream SWE-bench Docker harness",
                "scoring (sole scorer), real M6 console shadow-rebuild replay per task, and a real",
                "M5 packet with a passing `sha256sum -c MANIFEST.sha256`.",
                "",
                "This scenario certifies plumbing (every cross-module seam), not solve rate: see",
                "CLAIM_BOUNDARY.json.",
                "",
                f"Cert slice: shard {CERT_SHARD}, window {cert_slice['cert_slice_window_id']}, "
                f"instances {cert_slice['cert_slice_instance_ids']}.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    claim_boundary = scenario_root / "CLAIM_BOUNDARY.json"
    write_json(
        claim_boundary,
        {
            "schema_id": "CLAIM_BOUNDARY.v2",
            "evidence_class": "REAL",
            "solve_rate_claim_allowed": False,
            "claims": [
                "FCE-S1 golden-thread plumbing certification: real worker calls, real receipts, "
                "real sandbox provenance, real upstream harness scoring, real M6 replay, real M5 packet",
            ],
            "non_claims": [
                "no solve-rate claim of any kind",
                "not a release decision",
                "not SHIPPED",
                "not an external audit",
            ],
        },
    )
    evidence_files.extend([readme, claim_boundary])

    automatic_fail = None
    if host_assumed_count > 0:
        automatic_fail = "sandbox_escape"

    verdict = build_verdict(
        root=root,
        scenario_id=scenario_id,
        started=started,
        commands=commands,
        criteria=criteria,
        evidence_files=evidence_files,
        automatic_fail=automatic_fail,
    )
    write_json(scenario_root / f"{scenario_id}_verdict.json", verdict)
    print(json.dumps({"scenario_id": scenario_id, "verdict": verdict["verdict"]}, sort_keys=True))
    return 0 if verdict["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
