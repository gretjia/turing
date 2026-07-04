#!/usr/bin/env python3
"""FCE-W1: A certification day in the life (Block B end-to-end workflow scenario).

Per 09_FINAL_CERTIFICATION_EVALS.md section "FCE-W1 - A certification day in the
life" and the workflow script `tools/certification/workflow_scripts/w1.json`, this
scenario is REAL (fixture_or_real=REAL): it makes real DeepSeek native-API worker
calls (real spend, small) over the same 5-task cert slice FCE-S1 uses, and asserts
w1.json's three step `expected_observable`s hold against the produced Micro Tape(s):

  1. operator  - "Ask console for current heads and open lanes."
                 expected_observable: console_status_has_tape_heads
  2. orchestrator - "Dispatch five certification-slice tasks to the worker fleet."
                 expected_observable: five_task_dispatch_events
  3. worker    - "Record one preserved failed attempt and later rule consumption."
                 expected_observable: failure_preserved_and_consumed_rule_ids_nonempty

Real code defect found and fixed while implementing this scenario (documented in
full at the top of `tools/bench/run_mini_swe_bench_substrate_smoke.py`, search
"Real fix (found by FCE-W1)"): `run_substrate_task`'s `broadcast_rules` parameter
was already threaded into the worker-visible PROMPT text
(`deepseek_visible_prompt`/`visible_grok_prompt`) and `main()`'s per-task loop
already accumulated `broadcast_rules_emitted` across tasks (`active_broadcast_rules
.extend(...)`) - but the capsule itself never recorded that it had consumed the
rules it was given. `consumed_broadcast_rule_ids` was therefore silently absent
from EVERY real (non-fixture) run, even when `--broadcast-rules-file` was
supplied. Fixed: `WorkCapsuleBuilt` now carries `consumed_broadcast_rule_ids` /
`injected_broadcast_rule_ids` whenever `broadcast_rules` is non-empty.

Documented (not fixed) gap found in the same investigation: `BroadcastRuleActivated`
is registered as a `SOVEREIGN_ACCEPT` / `ADVANCE`-class event
(`pack/04_registries/event_registry_v5_3_1.json:103-108`), but `turingd`'s RPC
surface (`crates/turing-daemons/src/lib.rs`) exposes no admission endpoint for it
- only offline fixture generators ever write it, by bypassing the daemon entirely
via the raw git-level `append_stage6_event` helper. Implementing a real,
predicate-gated SOVEREIGN_ACCEPT admission RPC for this event type is out of
scope for this scenario (it is a new production capability, not a bug fix), so
this scenario does NOT claim a live BroadcastRuleActivated event was written to
any task's tape. Instead it demonstrates the two REAL halves the spec's flat
`failure_preserved_and_consumed_rule_ids_nonempty` observable actually requires:

  (a) task 1's real run preserves its rejected candidate branch on tape
      (FailureNode + PPUTAccounted progress=0 - unconditional in the real loop,
      confirmed present via a genuine Micro Tape bundle read, not trusted from
      the JSON summary alone).
  (b) a broadcast rule is derived (by this scenario script, not the daemon) from
      that real, on-tape failure event id, then fed via the already-real
      `--broadcast-rules-file` mechanism into a SECOND real dispatch batch
      (tasks 2-5); each of those tasks' real `WorkCapsuleBuilt` events records
      `consumed_broadcast_rule_ids` non-empty (verified the same way: read the
      real tape bundle, do not trust the summary).

CLAIM_BOUNDARY.json states plainly that no live BroadcastRuleActivated admission
event is claimed.
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
# Same pilot-exclusion rule as FCE-S1/FCE-S4 (PREREGISTRATION.md: S02-W00 is the
# deterministic 10-task arm-A pilot window and must never enter a cert slice).
PILOT_WINDOW_ID = "S02-W00"
CERT_SLICE_SIZE = 5
DEEPSEEK_MODEL = "deepseek-v4-flash"
DEEPSEEK_API_KEY_ENV = "DEEPSEEK_API_KEY"
SECRETS_ENV_PATH = Path.home() / ".turingos" / "secrets.env"
WORKER_IDENTITY = f"{DEEPSEEK_MODEL}__armB__fce-w1-day-in-life"
# Kept deliberately small: this scenario needs 5 real dispatch events, not solved
# tasks, so a short single-shot completion is enough (cheap real spend).
DEEPSEEK_MAX_TOKENS = 4000
WORKER_TIMEOUT_S = 240

# A sibling checkout of this same certification clone, built earlier, at the exact
# same commit (verified at runtime before reuse - never trusted blindly). Same
# convention as FCE-S4/FCE-S5.
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
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
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
    stdin_text: str | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            input=stdin_text,
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
# Reproducibility: load DEEPSEEK_API_KEY from the environment, falling back to
# ~/.turingos/secrets.env itself. A prior scenario broke reproducibility by
# assuming the caller had already `export`-ed it; this scenario never does.
# --------------------------------------------------------------------------


def load_deepseek_api_key() -> tuple[str | None, str]:
    env_value = os.environ.get(DEEPSEEK_API_KEY_ENV)
    if env_value:
        return env_value, "environment"
    if not SECRETS_ENV_PATH.is_file():
        return None, f"not found in environment or {SECRETS_ENV_PATH}"
    for raw_line in SECRETS_ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        if name.strip() != DEEPSEEK_API_KEY_ENV:
            continue
        value = value.strip().strip('"').strip("'")
        if value:
            return value, str(SECRETS_ENV_PATH)
    return None, f"key not present inside {SECRETS_ENV_PATH}"


# --------------------------------------------------------------------------
# Daemon-binary resolution (same convention as FCE-S4/FCE-S5)
# --------------------------------------------------------------------------


def resolve_daemon_bin_dir(repo: Path, scenario_root: Path) -> dict[str, Any]:
    local = repo / "target" / "debug"
    if all((local / name).is_file() and os.access(local / name, os.X_OK) for name in REQUIRED_DAEMON_BINARIES):
        result = {"bin_dir": str(local), "source": "repo_local_build", "shared_sha_match": None}
        write_json(scenario_root / "daemon_bin_dir_resolution.json", result)
        return result

    repo_sha = git_rev_parse(repo)
    if SHARED_TARGET_DEBUG.is_dir() and all(
        (SHARED_TARGET_DEBUG / name).is_file() and os.access(SHARED_TARGET_DEBUG / name, os.X_OK)
        for name in REQUIRED_DAEMON_BINARIES
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
# Cert-slice selection (identical rule/result to FCE-S1's select_cert_slice -
# the spec names "the 5 cert-slice tasks" for both S1 and W1)
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
        "schema_id": "turingos.fce.w1.cert_slice_manifest.v1",
        "shard_id": CERT_SHARD,
        "shard_manifest_path": str(shard_manifest_path),
        "shard_manifest_sha256": sha256_file(shard_manifest_path),
        "pilot_window_id": PILOT_WINDOW_ID,
        "pilot_instance_ids": sorted(pilot_ids),
        "selection_rule": "first N eligible instance_id in the shard manifest's stored task order, excluding the M3 pilot window (same rule as FCE-S1)",
        "cert_slice_size": CERT_SLICE_SIZE,
        "cert_slice_window_id": window_id,
        "cert_slice_instance_ids": slice_ids,
    }
    write_json(scenario_root / "cert_slice_manifest.json", result)
    return result


def materialize_cert_slice(repo: Path, scenario_root: Path, cert_slice: dict[str, Any]) -> dict[str, Any]:
    materialize_root = scenario_root / "materialize"
    shard_dir = materialize_root / "shards" / CERT_SHARD
    shard_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(cert_slice["shard_manifest_path"]), shard_dir / "shard_manifest.json")

    default_arrow = Path.home() / ".cache/huggingface/datasets/princeton-nlp___swe-bench_verified" / "default" / "0.0.0"
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
    task_lines: list[str] = []
    for instance_id in cert_slice["cert_slice_instance_ids"]:
        entry = tasks_by_id.get(instance_id)
        if entry is None:
            raise RuntimeError(f"materializer did not produce a worker-safe packet for {instance_id}")
        packet = load_json(materialize_root / entry["task_packet_path"])
        task_lines.append(
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

    task1_path = scenario_root / "task1.jsonl"
    task1_path.write_text(task_lines[0] + "\n", encoding="utf-8")
    tasks_rest_path = scenario_root / "tasks_2to5.jsonl"
    tasks_rest_path.write_text("\n".join(task_lines[1:]) + "\n", encoding="utf-8")

    return {
        "command": command,
        "report": report,
        "report_path": report_path,
        "task1_path": task1_path,
        "tasks_rest_path": tasks_rest_path,
    }


# --------------------------------------------------------------------------
# Real substrate-loop dispatch (same machinery FCE-S1/FCE-S4 use)
# --------------------------------------------------------------------------


def run_real_loop(
    *,
    repo: Path,
    plan_root: Path,
    scenario_root: Path,
    tasks_jsonl_path: Path,
    limit: int,
    api_key: str,
    daemon_bin_dir: Path,
    out_dir: Path,
    name: str,
    broadcast_rules_file: Path | None,
    timeout: int,
) -> dict[str, Any]:
    argv = [
        sys.executable,
        str(repo / "tools" / "bench" / "run_mini_swe_bench_substrate_smoke.py"),
        "--tasks-jsonl",
        str(tasks_jsonl_path),
        "--limit",
        str(limit),
        "--worker-mode",
        "deepseek",
        "--model",
        DEEPSEEK_MODEL,
        "--authorization-mode",
        "required",
        # Same M1b precondition as FCE-S1/FCE-S4: no OS-keyring session is available
        # on this headless certification host. The test-local authority path is a
        # real, non-silent M1b authorization event, never a silent fallback under
        # --authorization-mode required.
        "--authority-provider",
        "test-local",
        "--deepseek-price-table",
        str(plan_root / "m3_uplift_lab" / "PRICE_TABLE.json"),
        "--deepseek-max-tokens",
        str(DEEPSEEK_MAX_TOKENS),
        "--worker-timeout-s",
        str(WORKER_TIMEOUT_S),
        "--daemon-bin-dir",
        str(daemon_bin_dir),
        "--out-dir",
        str(out_dir),
    ]
    if broadcast_rules_file is not None:
        argv += ["--broadcast-rules-file", str(broadcast_rules_file)]
    env = dict(os.environ)
    env[DEEPSEEK_API_KEY_ENV] = api_key
    env["TURING_JCS_BIN"] = str(daemon_bin_dir / "turing")
    command = run_command(
        name=name,
        argv=argv,
        cwd=repo,
        out_dir=scenario_root / "commands",
        env=env,
        timeout=timeout,
    )
    coverage_path = out_dir / "substrate_coverage.json"
    coverage = load_json(coverage_path) if coverage_path.is_file() else {}
    return {"command": command, "out_dir": out_dir, "coverage_path": coverage_path, "coverage": coverage}


# --------------------------------------------------------------------------
# Independent tape reads (never trust the JSON summary alone - same convention
# as FCE-S4's load_tape_events / tape_cost_summary)
# --------------------------------------------------------------------------


def load_tape_events(repo: Path, scenario_root: Path, bundle_path: Path, label: str) -> list[dict[str, Any]]:
    sys.path.insert(0, str(repo / "tools" / "bench"))
    import audit_micro_tape_decision_dag as audit  # noqa: E402  (sibling-script import, matches repo convention)

    work_dir = scenario_root / "tape_replay" / label
    work_dir.mkdir(parents=True, exist_ok=True)
    git_dir, _verify_output = audit.fetch_bundle(bundle_path, work_dir)
    return audit.read_event_chain(git_dir)


def find_events(events: list[dict[str, Any]], event_type: str) -> list[dict[str, Any]]:
    return [event for event in events if event.get("event_type") == event_type]


# --------------------------------------------------------------------------
# Step 1: operator console check (turing status --json over task 1's real tape)
# --------------------------------------------------------------------------


def console_status_check(turing_bin: Path, micro_git: Path, scenario_root: Path) -> dict[str, Any]:
    json_command = run_command(
        name="console_status_json",
        argv=[str(turing_bin), "status", "--micro-git", str(micro_git), "--json"],
        cwd=turing_bin.parent,
        out_dir=scenario_root / "commands",
        timeout=60,
    )
    text_command = run_command(
        name="console_status_text",
        argv=[str(turing_bin), "status", "--micro-git", str(micro_git)],
        cwd=turing_bin.parent,
        out_dir=scenario_root / "commands",
        timeout=60,
    )
    panoview_command = run_command(
        name="console_panoview",
        argv=[str(turing_bin), "panoview", "--micro-git", str(micro_git)],
        cwd=turing_bin.parent,
        out_dir=scenario_root / "commands",
        timeout=60,
    )
    ask_command = run_command(
        name="console_ask_what_changed",
        argv=[str(turing_bin), "ask", "what changed since this morning", "--micro-git", str(micro_git)],
        cwd=turing_bin.parent,
        out_dir=scenario_root / "commands",
        timeout=60,
    )
    snapshot: dict[str, Any] = {}
    try:
        snapshot = json.loads(json_command["stdout_text"])
    except json.JSONDecodeError:
        snapshot = {}
    snapshot_path = scenario_root / "operator_status_snapshot.json"
    write_json(snapshot_path, snapshot if isinstance(snapshot, dict) else {"raw": snapshot})
    return {
        "json_command": json_command,
        "text_command": text_command,
        "panoview_command": panoview_command,
        "ask_command": ask_command,
        "snapshot": snapshot,
        "snapshot_path": snapshot_path,
    }


# --------------------------------------------------------------------------
# Broadcast-rule derivation (this SCRIPT computes it from task 1's real, on-tape
# failure - it is not claimed to be a live daemon-written BroadcastRuleActivated
# event; see module docstring / CLAIM_BOUNDARY.json)
# --------------------------------------------------------------------------


def derive_broadcast_rule(*, run: dict[str, Any], scenario_root: Path) -> dict[str, Any]:
    failure_event_id = run.get("failure_event_id")
    if not isinstance(failure_event_id, str) or not failure_event_id:
        raise RuntimeError("task 1's run did not expose a failure_event_id to derive a broadcast rule from")
    instance_id = run["instance_id"]
    rule_id = "br_real_" + hashlib.sha256(f"{instance_id}:{failure_event_id}".encode("utf-8")).hexdigest()[:16]
    rule = {
        "rule_id": rule_id,
        "failure_class": "SEMANTIC_FAIL",
        "guidance": (
            "Before retrying a similar SWE-bench-shaped task, keep the candidate patch "
            "minimal and scoped strictly to the files implicated by the problem "
            "statement, and re-verify test discovery before resubmitting."
        ),
        "source_failure_event_id": failure_event_id,
        "source_instance_id": instance_id,
        "derivation": (
            "Derived by tools/certification/scenarios/FCE-W1.py from task 1's real, "
            "on-tape FailureNode/PPUTAccounted(progress=0) event id above. This is a "
            "scenario-script-level derivation, not a live turingd-admitted "
            "BroadcastRuleActivated event - turingd currently exposes no SOVEREIGN_ACCEPT "
            "admission RPC for that event type (documented gap, see module docstring)."
        ),
    }
    packet = {
        "schema_id": "turingos.fce.w1.broadcast_rules.v1",
        "fixture_or_real": "REAL",
        "rules": [rule],
    }
    path = scenario_root / "broadcast_rules_from_task1_failure.json"
    write_json(path, packet)
    return {"path": path, "rule": rule, "rule_id": rule_id}


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
        "goals_served": ["G1", "G2", "G7"],
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

    api_key, api_key_source = load_deepseek_api_key()
    api_key_source_path = scenario_root / "deepseek_api_key_source.json"
    write_json(
        api_key_source_path,
        {
            "schema_id": "turingos.fce.w1.api_key_source.v1",
            "source": api_key_source,
            "secrets_env_path": str(SECRETS_ENV_PATH),
            "resolved": api_key is not None,
        },
    )
    evidence_files.append(api_key_source_path)
    if not api_key:
        criteria = [
            {"criterion": "deepseek_api_key_present", "result": False, "evidence": rel(root, api_key_source_path)},
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
        verdict["not_run_reason"] = f"missing {DEEPSEEK_API_KEY_ENV}: {api_key_source}"
        write_json(scenario_root / f"{scenario_id}_verdict.json", verdict)
        print(json.dumps({"scenario_id": scenario_id, "verdict": "NOT_RUN"}, sort_keys=True))
        return 2

    daemon_bin = resolve_daemon_bin_dir(repo, scenario_root)
    daemon_bin_dir = Path(daemon_bin["bin_dir"])
    turing_bin = daemon_bin_dir / "turing"
    evidence_files.append(scenario_root / "daemon_bin_dir_resolution.json")

    cert_slice = select_cert_slice(repo, scenario_root)
    evidence_files.append(scenario_root / "cert_slice_manifest.json")

    materialize = materialize_cert_slice(repo, scenario_root, cert_slice)
    commands.append(materialize["command"])
    evidence_files.append(materialize["report_path"])
    evidence_files.append(materialize["task1_path"])
    evidence_files.append(materialize["tasks_rest_path"])

    # ---- Batch 1: task 1 alone (real dispatch #1; its structurally-unconditional
    # rejected branch is what "the failure is preserved on tape with progress=0"
    # refers to - see run_substrate_task's capsule.reject call). ----
    loop1 = run_real_loop(
        repo=repo,
        plan_root=plan_root,
        scenario_root=scenario_root,
        tasks_jsonl_path=materialize["task1_path"],
        limit=1,
        api_key=api_key,
        daemon_bin_dir=daemon_bin_dir,
        out_dir=scenario_root / "loop_run_1",
        name="run_mini_swe_bench_substrate_smoke_task1",
        broadcast_rules_file=None,
        timeout=1200,
    )
    commands.append(loop1["command"])
    if loop1["coverage_path"].is_file():
        evidence_files.append(loop1["coverage_path"])
    runs1 = loop1["coverage"].get("turingos_arm_runs", []) if isinstance(loop1["coverage"], dict) else []

    # ---- Step 1 (operator): console status check against task 1's real tape,
    # between the first and remaining dispatches (preserves w1.json's step
    # order: operator checks in, THEN the orchestrator keeps dispatching). ----
    console = None
    if loop1["command"]["exit_code"] == 0 and runs1:
        micro_git_1 = Path(runs1[0]["micro_git"])
        console = console_status_check(turing_bin, micro_git_1, scenario_root)
        commands.append(console["json_command"])
        commands.append(console["text_command"])
        commands.append(console["panoview_command"])
        commands.append(console["ask_command"])
        evidence_files.append(console["snapshot_path"])

    # ---- Derive a broadcast rule from task 1's real, on-tape failure ----
    broadcast_rule = None
    task1_events: list[dict[str, Any]] = []
    task1_failure_present = False
    task1_pput_progress_zero_present = False
    if loop1["command"]["exit_code"] == 0 and runs1:
        task1_events = load_tape_events(repo, scenario_root, Path(runs1[0]["micro_tape_bundle"]), "task1")
        task1_failure_present = len(find_events(task1_events, "FailureNode")) >= 1
        task1_pput_progress_zero_present = any(
            event.get("payload", {}).get("progress") == 0
            for event in find_events(task1_events, "PPUTAccounted")
            if isinstance(event.get("payload"), dict)
        )
        broadcast_rule = derive_broadcast_rule(run=runs1[0], scenario_root=scenario_root)
        evidence_files.append(broadcast_rule["path"])

    # ---- Batch 2: tasks 2-5, fed the derived broadcast rule (real dispatches
    # #2-#5; each real WorkCapsuleBuilt should now record consumed_broadcast_rule_ids
    # thanks to the fix documented at the top of this file). ----
    loop2 = None
    runs2: list[dict[str, Any]] = []
    if broadcast_rule is not None:
        loop2 = run_real_loop(
            repo=repo,
            plan_root=plan_root,
            scenario_root=scenario_root,
            tasks_jsonl_path=materialize["tasks_rest_path"],
            limit=4,
            api_key=api_key,
            daemon_bin_dir=daemon_bin_dir,
            out_dir=scenario_root / "loop_run_2",
            name="run_mini_swe_bench_substrate_smoke_tasks_2to5",
            broadcast_rules_file=broadcast_rule["path"],
            timeout=1800,
        )
        commands.append(loop2["command"])
        if loop2["coverage_path"].is_file():
            evidence_files.append(loop2["coverage_path"])
        runs2 = loop2["coverage"].get("turingos_arm_runs", []) if isinstance(loop2["coverage"], dict) else []

    # ---- Verify rule consumption for real: read each batch-2 task's tape
    # directly (never trust the JSON summary alone) ----
    consuming_instance_ids: list[str] = []
    if broadcast_rule is not None and loop2 is not None and loop2["command"]["exit_code"] == 0:
        for run in runs2:
            if not isinstance(run, dict) or "micro_tape_bundle" not in run:
                continue
            events = load_tape_events(repo, scenario_root, Path(run["micro_tape_bundle"]), run["instance_id"])
            for event in find_events(events, "WorkCapsuleBuilt"):
                payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
                if broadcast_rule["rule_id"] in (payload.get("consumed_broadcast_rule_ids") or []):
                    consuming_instance_ids.append(run["instance_id"])
                    break

    # ---- Re-read task 1's tape once more: the preserved failure must still be
    # present, never deleted/overwritten (append-only Micro Tape; asserted, not
    # merely assumed). ----
    task1_failure_still_present = False
    if task1_events and runs1:
        events_again = load_tape_events(repo, scenario_root, Path(runs1[0]["micro_tape_bundle"]), "task1_recheck")
        first_ids = {event["_event_id"] for event in find_events(task1_events, "FailureNode")}
        second_ids = {event["_event_id"] for event in find_events(events_again, "FailureNode")}
        task1_failure_still_present = bool(first_ids) and first_ids == second_ids

    # ---- Dispatch count across both batches ----
    all_runs = runs1 + runs2
    dispatch_event_count = sum(
        int(run.get("event_calls", {}).get("WorkerDispatchAuthorized", 0)) for run in all_runs if isinstance(run, dict)
    )
    distinct_instance_ids = {run.get("instance_id") for run in all_runs if isinstance(run, dict)}

    # ---- Bonus: prompt-leakage spot audit over the combined 5-task coverage
    # (spec prose: "zero worker packet contains operator- or verifier-side
    # fields (spot-audit with audit_prompt_leakage.py)") ----
    combined_coverage_path = scenario_root / "combined_coverage.json"
    write_json(
        combined_coverage_path,
        {
            "schema_id": "MiniSweBenchSubstrateCoverage.v1",
            "run_id": "fce_w1_day_in_life",
            "sample_size": len(all_runs),
            "turingos_arm_runs": all_runs,
        },
    )
    leakage_report: dict[str, Any] = {"status": "NOT_RUN"}
    leakage_command = None
    if all_runs:
        leakage_out = scenario_root / "prompt_leakage.json"
        leakage_command = run_command(
            name="audit_prompt_leakage",
            argv=[
                sys.executable,
                str(repo / "tools" / "bench" / "audit_prompt_leakage.py"),
                "--coverage",
                str(combined_coverage_path),
                "--out",
                str(leakage_out),
            ],
            cwd=repo,
            out_dir=scenario_root / "commands",
            timeout=120,
        )
        commands.append(leakage_command)
        leakage_report = load_json(leakage_out) if leakage_out.is_file() else {"status": "FAIL"}
        evidence_files.append(leakage_out)
    evidence_files.append(combined_coverage_path)

    # ---- Criteria: the three w1.json step observables, plus a small number of
    # tightly-scoped bonus checks drawn from the spec prose's PASS criteria. ----
    console_snapshot = console["snapshot"] if console else {}
    heads = console_snapshot.get("heads") if isinstance(console_snapshot, dict) else None
    console_status_has_tape_heads = (
        console is not None
        and console["json_command"]["exit_code"] == 0
        and isinstance(heads, dict)
        and isinstance(heads.get("tape_tip"), str)
        and bool(heads.get("tape_tip"))
        and isinstance(heads.get("accepted_head"), str)
        and bool(heads.get("accepted_head"))
    )
    five_task_dispatch_events = (
        len(all_runs) == CERT_SLICE_SIZE
        and len(distinct_instance_ids) == CERT_SLICE_SIZE
        and dispatch_event_count == CERT_SLICE_SIZE
        and set(distinct_instance_ids) == set(cert_slice["cert_slice_instance_ids"])
    )
    failure_preserved_and_consumed_rule_ids_nonempty = (
        task1_failure_present
        and task1_pput_progress_zero_present
        and broadcast_rule is not None
        and len(consuming_instance_ids) >= 1
    )

    criteria = [
        {
            "criterion": "console_status_has_tape_heads",
            "result": console_status_has_tape_heads,
            "evidence": rel(root, console["snapshot_path"]) if console else "",
        },
        {
            "criterion": "five_task_dispatch_events",
            "result": five_task_dispatch_events,
            "evidence": rel(root, combined_coverage_path),
        },
        {
            "criterion": "failure_preserved_and_consumed_rule_ids_nonempty",
            "result": failure_preserved_and_consumed_rule_ids_nonempty,
            "evidence": rel(root, broadcast_rule["path"]) if broadcast_rule else "",
        },
        {
            "criterion": "preserved_failure_never_deleted_or_overwritten",
            "result": task1_failure_still_present,
            "evidence": rel(root, loop1["coverage_path"]) if loop1["coverage_path"].is_file() else "",
        },
        {
            "criterion": "all_five_dispatches_carry_test_local_authorization",
            "result": bool(all_runs)
            and all(
                run.get("authorization_mode") == "required" and run.get("authority_provider") == "test-local"
                for run in all_runs
                if isinstance(run, dict)
            ),
            "evidence": rel(root, combined_coverage_path),
        },
        {
            "criterion": "worker_packet_prompt_leakage_zero_hits",
            "result": leakage_report.get("status") == "PASS",
            "evidence": rel(root, scenario_root / "prompt_leakage.json") if (scenario_root / "prompt_leakage.json").is_file() else "",
        },
    ]

    readme = scenario_root / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# FCE-W1 A Certification Day in the Life",
                "",
                "Evidence label: REAL.",
                "",
                "Real DeepSeek native-API worker calls (arm-B, same golden-thread machinery as",
                "FCE-S1/FCE-S4) over the same 5-task S02 cert slice, split into two real batches:",
                "task 1 alone, then tasks 2-5 fed a broadcast rule derived from task 1's real,",
                "preserved, on-tape failure. Asserts the three step `expected_observable`s from",
                "`tools/certification/workflow_scripts/w1.json`.",
                "",
                "Real code defect found and fixed (see the module docstring and",
                "`tools/bench/run_mini_swe_bench_substrate_smoke.py`, search",
                "'Real fix (found by FCE-W1)'): consumed_broadcast_rule_ids was silently never",
                "recorded on any real WorkCapsuleBuilt event, even when --broadcast-rules-file",
                "was supplied.",
                "",
                "Documented gap (not fixed, out of scope - a new capability, not a bug): turingd",
                "exposes no live SOVEREIGN_ACCEPT admission RPC for BroadcastRuleActivated; this",
                "scenario derives the rule at the scenario-script level from a real, on-tape",
                "failure event id rather than claiming a live BroadcastRuleActivated event was",
                "written. See CLAIM_BOUNDARY.json.",
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
            "live_broadcast_rule_activated_event_claim_allowed": False,
            "claims": [
                "FCE-W1 day-in-life plumbing certification: real 5-task worker-fleet dispatch, "
                "real console status check with real tape heads, one real preserved failed "
                "attempt (progress=0, never deleted), and real cross-task consumed_broadcast_rule_ids "
                "recorded on real WorkCapsuleBuilt events for a rule derived from that real failure",
            ],
            "non_claims": [
                "no solve-rate claim of any kind",
                "not a claim that a live BroadcastRuleActivated (SOVEREIGN_ACCEPT) event was "
                "admitted by turingd - no such RPC exists yet (documented gap)",
                "not a release decision",
                "not SHIPPED",
                "not an external audit",
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
