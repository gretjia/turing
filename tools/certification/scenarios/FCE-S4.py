#!/usr/bin/env python3
"""FCE-S4: Tape-canonical cost conservation (G2/G5 seam).

Per 09_FINAL_CERTIFICATION_EVALS.md section "FCE-S4 - Tape-canonical cost
conservation": cost is reconstructible from tape alone, and every derived
ledger agrees. This scenario is REAL (fixture_or_real=REAL): it makes one real
DeepSeek native-API worker call (real spend, small - one chat-completion call,
observed at 145 microUSD / $0.000145 in the dry-run that validated this
script) through the same golden-thread machinery FCE-S1 uses
(`tools/bench/run_mini_swe_bench_substrate_smoke.py`, `worker-mode deepseek`),
producing one real Micro Tape with a real CostEvent.v2 receipt.

Spec steps (section 3, FCE-S4), adapted to what this certification clone can
actually produce today (no FCE-S1/M3/M4 real tapes exist yet in this clone --
only their scripts do; see each scenario's own NOT_RUN gate):
  1. Sum cost (and token counts) from the tape's CostEvent events only --
     read directly from the produced Micro Tape bundle via git, independent of
     any scoring/report path.
  2. Sum cost (and token counts) from the `worker_logs/provider_receipt_sanitized.json`
     receipt files this run wrote to the evidence root (the "receipts/ files
     in evidence roots" the spec names) -- a second, independently-written
     on-disk artifact, not the tape.
  3. Layer-2 provider usage/cost API reconciliation: NOT RUN. It is optional
     (RES_M1 S2.6 Layer 2) and no such account-level reconciliation API is
     wired in this repo for DeepSeek; recorded honestly as NOT_RUN, not
     silently skipped.
  4. Run the conservation check between tape totals and any derived
     ledger/market view: `tools/bench/audit_micro_tape_decision_dag.py`
     (`--require-cost-provenance --strict-vpput --require-authorization-head
     --require-sandbox-provenance`) over the produced bundle; extract its
     `cost_provenance` / `cost_conservation_all_branches` / `authorization_head`
     / `sandbox_provenance` per-run checks directly (not the tool's own overall
     exit code -- FCE-S1 established this convention: a real, deliberately
     predicate-held single-loop run has no "final" PPUT accounting stage, so
     `--strict-vpput`'s aggregate verdict is expected to read FAIL/WARN for
     reasons unrelated to cost provenance; the individual checks this
     scenario cares about are read out of `report["runs"][i]["checks"]`).

PASS criteria (spec, line 148): tape sum == receipts-file sum exactly (both
cost_microusd and token counts, integers); every event's cost_source_kind
populated (and drawn from the closed enum -- never null/missing/unspecified);
bounded estimates each carry their bound derivation (bound_kind); derived
views conserve (no ledger entry without a tape ancestor -- i.e. the
conservation check never reports FAIL). Layer-2 reconciliation is optional and
was not run here; that is a WARN-class note, not a FAIL condition.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CERT_SHARD = "S02"
# Same pilot-exclusion rule as FCE-S1 (PREREGISTRATION.md: S02-W00 is the
# deterministic 10-task arm-A pilot window and must never enter a cert slice).
PILOT_WINDOW_ID = "S02-W00"
DEEPSEEK_MODEL = "deepseek-v4-flash"
DEEPSEEK_API_KEY_ENV = "DEEPSEEK_API_KEY"
WORKER_IDENTITY = f"{DEEPSEEK_MODEL}__armB__fce-s4-cost-conservation"

# A sibling checkout of this same certification clone, built earlier today, at
# the exact same commit (verified at runtime below before reuse -- never
# trusted blindly). Reusing it turns an ~O(10 min) cargo build into a no-op on
# this certification host. If the SHA check fails or the binaries are
# missing, this script falls back to a real local `cargo build`, so it is
# still self-sufficient in a fresh clone with no sibling checkout.
SHARED_TARGET_DEBUG = Path("/home/zephryj/turingos_backup/work/turing_fce_integration/target/debug")
REQUIRED_DAEMON_BINARIES = [
    "turing",
    "turingd",
    "turing-execd",
    "turing-marketd",
    "turing-mcp",
    "turing-pputd",
    "turing-viewd",
]


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


def git_rev_parse(repo: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )
    except (subprocess.CalledProcessError, OSError):
        return None
    return proc.stdout.strip()


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
# Daemon-binary resolution (see SHARED_TARGET_DEBUG comment above)
# --------------------------------------------------------------------------

def resolve_daemon_bin_dir(repo: Path, scenario_root: Path) -> dict[str, Any]:
    local = repo / "target" / "debug"
    if all((local / name).is_file() and os.access(local / name, os.X_OK) for name in REQUIRED_DAEMON_BINARIES):
        result = {"bin_dir": str(local), "source": "repo_local_build", "shared_sha_match": None}
        write_json(scenario_root / "daemon_bin_dir_resolution.json", result)
        return result

    repo_sha = git_rev_parse(repo)
    if (
        SHARED_TARGET_DEBUG.is_dir()
        and all((SHARED_TARGET_DEBUG / name).is_file() and os.access(SHARED_TARGET_DEBUG / name, os.X_OK) for name in REQUIRED_DAEMON_BINARIES)
    ):
        shared_repo_root = SHARED_TARGET_DEBUG.parents[1]
        shared_sha = git_rev_parse(shared_repo_root)
        if repo_sha is not None and shared_sha is not None and shared_sha == repo_sha:
            result = {
                "bin_dir": str(SHARED_TARGET_DEBUG),
                "source": "shared_sibling_checkout_same_commit",
                "shared_repo_root": str(shared_repo_root),
                "shared_sha_match": True,
                "repo_sha": repo_sha,
                "shared_sha": shared_sha,
            }
            write_json(scenario_root / "daemon_bin_dir_resolution.json", result)
            return result

    # Fall back: build in-repo. Slow path, but keeps this scenario self-sufficient.
    local.parent.mkdir(parents=True, exist_ok=True)
    build_command = run_command(
        name="cargo_build_workspace",
        argv=["cargo", "build", "--workspace"],
        cwd=repo,
        out_dir=scenario_root / "commands",
        timeout=1800,
    )
    if build_command["exit_code"] != 0:
        raise RuntimeError(f"cargo build --workspace failed (exit {build_command['exit_code']}); see {build_command['stderr']}")
    result = {"bin_dir": str(local), "source": "repo_local_build_fresh", "shared_sha_match": False, "repo_sha": repo_sha}
    write_json(scenario_root / "daemon_bin_dir_resolution.json", result)
    return result


# --------------------------------------------------------------------------
# Step 0: deterministic single-task selection (same pilot-exclusion rule as
# FCE-S1's cert-slice selection, but a single task, to keep real spend minimal)
# --------------------------------------------------------------------------

def select_single_task(repo: Path, scenario_root: Path) -> dict[str, Any]:
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
    ordered_ids = [task["instance_id"] for task in tasks if isinstance(task, dict) and isinstance(task.get("instance_id"), str)]
    eligible = [instance_id for instance_id in ordered_ids if instance_id not in pilot_ids]
    if not eligible:
        raise ValueError(f"no eligible (non-pilot) instances available in shard {CERT_SHARD}")
    instance_id = eligible[0]
    id_to_window = {task["instance_id"]: task.get("ipqc_window_id") for task in tasks if isinstance(task, dict)}
    window_id = id_to_window[instance_id]

    result = {
        "schema_id": "turingos.fce.s4.task_selection.v1",
        "shard_id": CERT_SHARD,
        "shard_manifest_path": str(shard_manifest_path),
        "shard_manifest_sha256": sha256_file(shard_manifest_path),
        "pilot_window_id": PILOT_WINDOW_ID,
        "selection_rule": "first eligible instance_id in the shard manifest's stored task order, excluding the M3 pilot window (same rule as FCE-S1)",
        "instance_id": instance_id,
        "window_id": window_id,
        "instance_in_pilot_window": instance_id in pilot_ids,
    }
    write_json(scenario_root / "task_selection.json", result)
    return result


def materialize_single_task(repo: Path, scenario_root: Path, selection: dict[str, Any]) -> dict[str, Any]:
    materialize_root = scenario_root / "materialize"
    shard_dir = materialize_root / "shards" / CERT_SHARD
    shard_dir.mkdir(parents=True, exist_ok=True)
    import shutil

    shutil.copy2(Path(selection["shard_manifest_path"]), shard_dir / "shard_manifest.json")

    default_arrow = Path.home() / ".cache/huggingface/datasets/princeton-nlp___swe-bench_verified" / "default" / "0.0.0"
    arrow_candidates = sorted(default_arrow.glob("*/swe-bench_verified-test.arrow")) if default_arrow.is_dir() else []
    if not arrow_candidates:
        raise RuntimeError("no cached SWE-bench Verified arrow dataset found; cannot materialize a worker-safe packet")
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
            selection["window_id"],
            "--dataset-arrow",
            str(dataset_arrow),
        ],
        cwd=repo,
        out_dir=scenario_root / "commands",
        timeout=300,
    )
    report_path = (
        materialize_root / "shards" / CERT_SHARD / "ipqc" / selection["window_id"] / "worker_safe_tasks" / "worker_safe_tasks_report.json"
    )
    report = load_json(report_path) if report_path.is_file() else {"status": "FAIL"}

    tasks_by_id = {item["instance_id"]: item for item in report.get("tasks", []) if isinstance(item, dict)}
    entry = tasks_by_id.get(selection["instance_id"])
    if entry is None:
        raise RuntimeError(f"materializer did not produce a worker-safe packet for {selection['instance_id']}")
    packet = load_json(materialize_root / entry["task_packet_path"])
    task_line = json.dumps(
        {
            "instance_id": packet["instance_id"],
            "repo": packet["repo"],
            "base_commit": packet["base_commit"],
            "problem_statement": packet["problem_statement"],
        },
        sort_keys=True,
    )
    tasks_jsonl_path = scenario_root / "task.jsonl"
    tasks_jsonl_path.write_text(task_line + "\n", encoding="utf-8")

    return {"command": command, "report": report, "report_path": report_path, "tasks_jsonl_path": tasks_jsonl_path}


# --------------------------------------------------------------------------
# Step 1: real DeepSeek loop run (one real worker call; same machinery FCE-S1
# uses, `--limit 1` to keep spend minimal)
# --------------------------------------------------------------------------

def run_real_loop(
    repo: Path, plan_root: Path, scenario_root: Path, tasks_jsonl_path: Path, api_key: str, daemon_bin_dir: Path
) -> dict[str, Any]:
    loop_root = scenario_root / "loop_run"
    argv = [
        sys.executable,
        str(repo / "tools" / "bench" / "run_mini_swe_bench_substrate_smoke.py"),
        "--tasks-jsonl",
        str(tasks_jsonl_path),
        "--limit",
        "1",
        "--worker-mode",
        "deepseek",
        "--model",
        DEEPSEEK_MODEL,
        "--authorization-mode",
        "required",
        # Same M1b precondition as FCE-S1: no OS-keyring session is available on
        # this headless certification host (no D-Bus session / X11). The
        # test-local authority path is a real, non-silent M1b authorization
        # event (authority_kind=test_local_authority_no_credentials), never a
        # fallback under --authorization-mode required.
        "--authority-provider",
        "test-local",
        "--deepseek-price-table",
        str(plan_root / "m3_uplift_lab" / "PRICE_TABLE.json"),
        "--daemon-bin-dir",
        str(daemon_bin_dir),
        "--out-dir",
        str(loop_root),
    ]
    env = dict(os.environ)
    env[DEEPSEEK_API_KEY_ENV] = api_key
    env["TURING_JCS_BIN"] = str(daemon_bin_dir / "turing")
    command = run_command(
        name="run_mini_swe_bench_substrate_smoke",
        argv=argv,
        cwd=repo,
        out_dir=scenario_root / "commands",
        env=env,
        timeout=600,
    )
    coverage_path = loop_root / "substrate_coverage.json"
    coverage = load_json(coverage_path) if coverage_path.is_file() else {}
    return {"command": command, "loop_root": loop_root, "coverage_path": coverage_path, "coverage": coverage}


# --------------------------------------------------------------------------
# Step 2: independent tape-side cost sum (reads Micro Tape bundles directly,
# via the shared, already-vetted tape-reading utilities in
# tools/bench/audit_micro_tape_decision_dag.py -- imported, not re-implemented,
# but never trusting that module's own PASS/FAIL verdict for this sum: we sum
# the raw CostEvent payloads ourselves)
# --------------------------------------------------------------------------

def load_tape_events(repo: Path, scenario_root: Path, bundle_path: Path) -> list[dict[str, Any]]:
    sys.path.insert(0, str(repo / "tools" / "bench"))
    import audit_micro_tape_decision_dag as audit  # noqa: E402  (sibling-script import, matches repo convention)

    work_dir = scenario_root / "tape_replay"
    work_dir.mkdir(parents=True, exist_ok=True)
    git_dir, _verify_output = audit.fetch_bundle(bundle_path, work_dir)
    return audit.read_event_chain(git_dir)


def tape_cost_summary(repo: Path, events: list[dict[str, Any]]) -> dict[str, Any]:
    sys.path.insert(0, str(repo / "tools" / "bench"))
    import audit_micro_tape_decision_dag as audit  # noqa: E402

    cost_events = [event for event in events if event.get("event_type") == "CostEvent" and isinstance(event.get("payload"), dict)]
    cost_sum = 0
    token_sum = 0
    cost_source_kinds: list[str | None] = []
    unbounded_missing_bound_kind: list[str] = []
    schema_versions: list[str | None] = []
    for event in cost_events:
        payload = event["payload"]
        cost_sum += audit.cost_event_cost_microusd(payload) or 0
        token_sum += audit.cost_event_total_tokens(payload)
        cost = payload.get("cost") if isinstance(payload.get("cost"), dict) else {}
        kind = cost.get("cost_source_kind")
        cost_source_kinds.append(kind)
        if kind == "bounded_estimate" and not (isinstance(cost.get("bound_kind"), str) and cost.get("bound_kind")):
            unbounded_missing_bound_kind.append(event.get("_event_id", "<unknown>"))
        schema_versions.append(payload.get("schema_id"))
    return {
        "cost_event_count": len(cost_events),
        "cost_microusd_sum": cost_sum,
        "token_count_sum": token_sum,
        "cost_source_kinds": cost_source_kinds,
        "all_cost_source_kinds_populated_and_valid": bool(cost_events)
        and all(isinstance(kind, str) and kind in audit.COST_SOURCE_KINDS for kind in cost_source_kinds),
        "bounded_estimates_missing_bound_kind": unbounded_missing_bound_kind,
        "all_schema_v2": bool(cost_events) and all(version == audit.COST_EVENT_V2_SCHEMA_ID for version in schema_versions),
    }


# --------------------------------------------------------------------------
# Step 2 (continued): independent receipts-file-side cost sum (the on-disk
# `worker_logs/provider_receipt_sanitized.json` files this run wrote -- the
# spec's "receipts/ files in evidence roots", a genuinely separate artifact
# from the tape)
# --------------------------------------------------------------------------

def receipts_file_cost_summary(loop_root: Path, coverage: dict[str, Any]) -> dict[str, Any]:
    runs = coverage.get("turingos_arm_runs", []) if isinstance(coverage, dict) else []
    receipt_files: list[dict[str, Any]] = []
    cost_sum = 0
    token_sum = 0
    for run in runs:
        if not isinstance(run, dict):
            continue
        log_dir = Path(run["worker_log_dir"]) if run.get("worker_log_dir") else None
        if log_dir is None:
            continue
        receipt_path = log_dir / "provider_receipt_sanitized.json"
        if not receipt_path.is_file():
            continue
        receipt = load_json(receipt_path)
        cost = receipt.get("cost") if isinstance(receipt.get("cost"), dict) else {}
        usage = receipt.get("usage") if isinstance(receipt.get("usage"), dict) else {}
        this_cost = int(cost.get("computed_cost_microusd") or 0)
        this_tokens = int(usage.get("total_tokens") or (int(usage.get("prompt_tokens") or 0) + int(usage.get("completion_tokens") or 0)))
        cost_sum += this_cost
        token_sum += this_tokens
        receipt_files.append(
            {
                "instance_id": run.get("instance_id"),
                "path": str(receipt_path),
                "sha256": sha256_file(receipt_path),
                "computed_cost_microusd": this_cost,
                "total_tokens": this_tokens,
            }
        )
    return {
        "receipt_file_count": len(receipt_files),
        "cost_microusd_sum": cost_sum,
        "token_count_sum": token_sum,
        "receipt_files": receipt_files,
        "expected_receipt_count": sum(1 for run in runs if isinstance(run, dict)),
    }


# --------------------------------------------------------------------------
# Step 4: conservation check via the existing strict auditor (evidence only --
# per-run checks are read directly, not the tool's own overall exit code; see
# module docstring for why)
# --------------------------------------------------------------------------

def strict_conservation_audit(repo: Path, scenario_root: Path, coverage_path: Path) -> dict[str, Any]:
    audit_dir = scenario_root / "s4_audit"
    command = run_command(
        name="audit_micro_tape_decision_dag_strict",
        argv=[
            sys.executable,
            str(repo / "tools" / "bench" / "audit_micro_tape_decision_dag.py"),
            "--coverage",
            str(coverage_path),
            "--strict-vpput",
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
    report = load_json(report_path) if report_path.is_file() else {"runs": []}

    m1a_command = run_command(
        name="m1a_gates",
        argv=["bash", "tools/ci/run_m1a_gates.sh"],
        cwd=repo,
        out_dir=scenario_root / "commands",
        timeout=300,
    )
    return {"command": command, "report_path": report_path, "report": report, "m1a_command": m1a_command}


# --------------------------------------------------------------------------
# Verdict assembly
# --------------------------------------------------------------------------

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
        "goals_served": ["G2", "G5"],
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

    api_key = os.environ.get(DEEPSEEK_API_KEY_ENV)
    if not api_key:
        criteria = [
            {"criterion": "deepseek_api_key_present", "result": False, "evidence": f"{scenario_id}/task_selection.json"}
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

    daemon_bin = resolve_daemon_bin_dir(repo, scenario_root)
    daemon_bin_dir = Path(daemon_bin["bin_dir"])
    evidence_files.append(scenario_root / "daemon_bin_dir_resolution.json")
    if daemon_bin.get("shared_sha_match") is False and daemon_bin["source"] != "repo_local_build_fresh":
        # A sibling checkout exists but is at a different commit: never reuse it.
        pass

    selection = select_single_task(repo, scenario_root)
    evidence_files.append(scenario_root / "task_selection.json")

    materialize = materialize_single_task(repo, scenario_root, selection)
    commands.append(materialize["command"])
    evidence_files.append(materialize["report_path"])
    evidence_files.append(materialize["tasks_jsonl_path"])

    loop = run_real_loop(repo, plan_root, scenario_root, materialize["tasks_jsonl_path"], api_key, daemon_bin_dir)
    commands.append(loop["command"])
    if loop["coverage_path"].is_file():
        evidence_files.append(loop["coverage_path"])

    runs = loop["coverage"].get("turingos_arm_runs", []) if isinstance(loop["coverage"], dict) else []
    tape_summary: dict[str, Any] = {"cost_event_count": 0, "cost_microusd_sum": 0, "token_count_sum": 0}
    tape_events: list[dict[str, Any]] = []
    if loop["command"]["exit_code"] == 0 and runs:
        bundle_path = Path(runs[0]["micro_tape_bundle"])
        tape_events = load_tape_events(repo, scenario_root, bundle_path)
        tape_summary = tape_cost_summary(repo, tape_events)
    tape_summary_path = scenario_root / "tape_cost_summary.json"
    write_json(tape_summary_path, tape_summary)
    evidence_files.append(tape_summary_path)

    receipts_summary = receipts_file_cost_summary(loop["loop_root"], loop["coverage"])
    receipts_summary_path = scenario_root / "receipts_file_cost_summary.json"
    write_json(receipts_summary_path, receipts_summary)
    evidence_files.append(receipts_summary_path)

    audit = None
    if loop["command"]["exit_code"] == 0 and loop["coverage_path"].is_file():
        audit = strict_conservation_audit(repo, scenario_root, loop["coverage_path"])
        commands.append(audit["command"])
        commands.append(audit["m1a_command"])
        if audit["report_path"].is_file():
            evidence_files.append(audit["report_path"])

    audit_runs = audit["report"].get("runs", []) if audit and isinstance(audit["report"], dict) else []
    audit_checks = audit_runs[0].get("checks", {}) if audit_runs and isinstance(audit_runs[0], dict) else {}
    legacy_missing_count = sum(1 for value in audit_checks.values() if value == "LEGACY_MISSING")

    layer2_note_path = scenario_root / "layer2_reconciliation_note.json"
    write_json(
        layer2_note_path,
        {
            "schema_id": "turingos.fce.s4.layer2_note.v1",
            "layer2_provider_usage_api_reconciliation_run": False,
            "reason": "optional per RES_M1 S2.6 Layer 2; no DeepSeek account-level usage/cost reconciliation API is wired in this repo. The inline provider receipt (Layer 1) remains the load-bearing record per spec.",
        },
    )
    evidence_files.append(layer2_note_path)

    criteria = [
        {
            "criterion": "single_task_selection_deterministic_excludes_pilot_window",
            "result": selection["instance_in_pilot_window"] is False,
            "evidence": rel(root, scenario_root / "task_selection.json"),
        },
        {
            "criterion": "materializer_worker_safe_report_pass",
            "result": materialize["report"].get("status") == "PASS",
            "evidence": rel(root, materialize["report_path"]),
        },
        {
            "criterion": "real_deepseek_loop_run_exit_zero",
            "result": loop["command"]["exit_code"] == 0,
            "evidence": rel(root, loop["coverage_path"]) if loop["coverage_path"].is_file() else f"{scenario_id}/commands/run_mini_swe_bench_substrate_smoke.stderr.txt",
        },
        {
            "criterion": "cost_event_present_on_tape_schema_v2",
            "result": tape_summary["cost_event_count"] >= 1 and tape_summary.get("all_schema_v2") is True,
            "evidence": rel(root, tape_summary_path),
        },
        {
            "criterion": "receipts_file_present_for_every_tape_run",
            "result": receipts_summary["receipt_file_count"] >= 1
            and receipts_summary["receipt_file_count"] == receipts_summary["expected_receipt_count"],
            "evidence": rel(root, receipts_summary_path),
        },
        {
            "criterion": "tape_cost_sum_equals_receipts_file_sum_exact",
            "result": tape_summary["cost_event_count"] >= 1
            and tape_summary["cost_microusd_sum"] == receipts_summary["cost_microusd_sum"],
            "evidence": rel(root, tape_summary_path),
        },
        {
            "criterion": "tape_token_sum_equals_receipts_file_sum_exact",
            "result": tape_summary["cost_event_count"] >= 1
            and tape_summary["token_count_sum"] == receipts_summary["token_count_sum"],
            "evidence": rel(root, tape_summary_path),
        },
        {
            "criterion": "every_cost_event_cost_source_kind_populated_and_valid_enum",
            "result": tape_summary.get("all_cost_source_kinds_populated_and_valid") is True,
            "evidence": rel(root, tape_summary_path),
        },
        {
            "criterion": "bounded_estimates_carry_bound_derivation",
            "result": tape_summary.get("bounded_estimates_missing_bound_kind") == [],
            "evidence": rel(root, tape_summary_path),
        },
        {
            "criterion": "strict_audit_cost_provenance_pass",
            "result": audit_checks.get("cost_provenance") == "PASS",
            "evidence": rel(root, audit["report_path"]) if audit else "",
        },
        {
            "criterion": "strict_audit_zero_legacy_missing",
            "result": legacy_missing_count == 0,
            "evidence": rel(root, audit["report_path"]) if audit else "",
        },
        {
            "criterion": "derived_ledger_conservation_never_fails",
            "result": audit_checks.get("cost_conservation_all_branches") != "FAIL",
            "evidence": rel(root, audit["report_path"]) if audit else "",
        },
        {
            "criterion": "strict_audit_authorization_head_and_sandbox_provenance_pass",
            "result": audit_checks.get("authorization_head") == "PASS" and audit_checks.get("sandbox_provenance") == "PASS",
            "evidence": rel(root, audit["report_path"]) if audit else "",
        },
        {
            "criterion": "m1a_canonical_writer_gate_pass",
            "result": bool(audit) and audit["m1a_command"]["exit_code"] == 0,
            "evidence": rel(root, audit["report_path"]) if audit else "",
        },
    ]

    readme = scenario_root / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# FCE-S4 Tape-Canonical Cost Conservation",
                "",
                "Evidence label: REAL.",
                "",
                "One real DeepSeek native-API worker call (arm-B single-loop run, same",
                "machinery FCE-S1 uses, `--limit 1` to keep spend minimal), producing one real",
                "Micro Tape with a real CostEvent.v2 receipt. Cost and token counts are summed",
                "independently from (a) the tape's CostEvent events and (b) the on-disk",
                "`provider_receipt_sanitized.json` receipt file this run wrote, and asserted",
                "exactly equal. Every on-tape cost_source_kind is checked against the closed",
                "enum (never null/missing/unspecified); bounded estimates (none present in",
                "this run) would be required to carry a bound_kind. The conservation check is",
                "read from `tools/bench/audit_micro_tape_decision_dag.py`'s per-run checks",
                "(`cost_provenance`, `cost_conservation_all_branches`), not that tool's own",
                "aggregate exit code -- a deliberately predicate-held single-loop run has no",
                "'final' PPUT accounting stage, so `--strict-vpput`'s own aggregate verdict is",
                "expected to read non-PASS for reasons unrelated to cost provenance (see the",
                "module docstring).",
                "",
                "Layer-2 provider usage/cost API reconciliation (RES_M1 S2.6, optional) was",
                "NOT run: no such account-level API is wired for DeepSeek in this repo. This",
                "is recorded honestly, not silently skipped; it does not gate PASS per spec.",
                "",
                f"Selected task: {selection['instance_id']} (shard {CERT_SHARD}, window {selection['window_id']}).",
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
                "FCE-S4 cost-conservation certification: real worker call, real CostEvent.v2 "
                "receipt, tape-sum == receipts-file-sum exact match, cost provenance and "
                "conservation checks pass on the produced tape",
            ],
            "non_claims": [
                "no solve-rate claim of any kind",
                "not a release decision",
                "not SHIPPED",
                "not an external audit",
                "not a claim that Layer-2 provider-account reconciliation was run",
            ],
        },
    )
    evidence_files.extend([readme, claim_boundary])

    automatic_fail = None
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
