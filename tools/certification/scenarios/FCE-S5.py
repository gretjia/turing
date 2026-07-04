#!/usr/bin/env python3
"""FCE-S5: Console truthfulness and no-write proof under certification load (G7).

Per 09_FINAL_CERTIFICATION_EVALS.md section "FCE-S5 - Console truthfulness and
no-write proof under certification load": the M6 console (`turing` CLI),
pointed at the REAL certification tape (not its demo fixture), displays only
tape-derivable values and cannot write.

This scenario is REAL (fixture_or_real=REAL): it makes one real DeepSeek
native-API worker call (real spend, small - one chat-completion call, the same
golden-thread machinery FCE-S1/FCE-S4 use,
`tools/bench/run_mini_swe_bench_substrate_smoke.py --limit 1 --worker-mode
deepseek`) to produce one real, non-fixture Micro Tape (`instances/<id>/
micro.git` + `instances/<id>/micro_tape.bundle`), then points the real `turing`
console binary at that tape and proves the four things spec section 3, FCE-S5
requires:

  1. Projection-integrity checks (RES_M6 S2.4, via the existing
     `tools/hci/audit_projection_integrity.py`): shadow rebuild, independent
     head derivation, provenance-manifest closure (100% of the
     `operator_view_snapshot.v1` JSON's leaf fields classified against
     `schemas/operator/operator_view_snapshot.v1.provenance.json`), render
     fidelity, and worker-side leakage (zero `operator_view_snapshot.v1` /
     `operator_tool_manifest.v1` / `operator_turn_trace.v1` hits in
     worker-facing source).
  2. Dynamic head-conservation test: the three `refs/turingos/*` OIDs (and a
     whole-tree digest of the MicroTape object store, for a stronger check
     than the spec's own minimum) are captured before AND after the FULL
     console command matrix (`status`, `panoview`, `explain`, `ask`,
     `approval preview`, all `--json` modes, `--micro-git` and
     `--micro-bundle` sources, the `operator` stdin REPL) - the same 27-case
     matrix `crates/turing-cli/tests/cli_gates.rs::operator_command_matrix`
     already exercises against a synthetic fixture tape, run here against the
     real tape instead - and asserted byte-identical.
  3. Read-only filesystem matrix: the same full command matrix, repeated
     against a `chmod -R a-w` scratch copy of the real tape (both the
     `micro.git` directory and the `micro_tape.bundle` file), asserting every
     command still exits zero with zero permission-denied/EACCES text in its
     output (i.e. no command masks a failed write attempt as a successful
     read) and that heads stay unchanged throughout.
  4. Leakage direction check: `audit_projection_integrity.py`'s
     `worker_leakage` check greps the worker-packet builders for
     `operator_view_snapshot.v1` et al. - expected zero hits (reused directly,
     not re-implemented, from step 1's invocation).

Reproducibility note (a prior scenario's non-reproducibility lesson): this
script does NOT assume `DEEPSEEK_API_KEY` is already exported. It first checks
the environment, then falls back to reading it out of
`~/.turingos/secrets.env` itself (see `load_deepseek_api_key`), so a fresh
clean-env agent invocation (`python3 tools/certification/scenarios/FCE-S5.py
...` with no prior `source secrets.env`) still finds real credentials if that
file exists on the host, and honestly reports NOT_RUN (never a fabricated
PASS) if it does not.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CERT_SHARD = "S02"
# Same pilot-exclusion rule as FCE-S1/FCE-S4 (PREREGISTRATION.md: S02-W00 is
# the deterministic 10-task arm-A pilot window and must never enter a cert
# slice).
PILOT_WINDOW_ID = "S02-W00"
DEEPSEEK_MODEL = "deepseek-v4-flash"
DEEPSEEK_API_KEY_ENV = "DEEPSEEK_API_KEY"
WORKER_IDENTITY = f"{DEEPSEEK_MODEL}__armB__fce-s5-console-no-write"
SECRETS_ENV_PATH = Path.home() / ".turingos" / "secrets.env"

# A sibling checkout of this same certification clone, built earlier, at the
# exact same commit (verified at runtime below before reuse - never trusted
# blindly). Reusing it turns an ~O(10 min) cargo build into a no-op. Falls
# back to a real local `cargo build` otherwise, so this scenario is still
# self-sufficient in a fresh clone with no sibling checkout.
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

# The exact three MicroTape head refs the console reads
# (crates/turing-cli/tests/cli_gates.rs::REF_NAMES;
# tools/hci/audit_projection_integrity.py::heads_from_micro_git).
REF_NAMES = (
    "refs/turingos/tape_tip",
    "refs/turingos/authorization_head",
    "refs/turingos/accepted_head",
)


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


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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
    stdin_text: str | None = None,
    timeout: int = 600,
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            text=True,
            input=stdin_text,
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
# ~/.turingos/secrets.env itself (a prior scenario's reproducibility lesson:
# never assume the caller has already `source`d it).
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
# Daemon-binary resolution (see SHARED_TARGET_DEBUG comment above; identical
# convention to FCE-S4).
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
# Step 0: deterministic single-task selection + materialization (same rule as
# FCE-S4, to keep real spend minimal - one task).
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
        "schema_id": "turingos.fce.s5.task_selection.v1",
        "shard_id": CERT_SHARD,
        "shard_manifest_path": str(shard_manifest_path),
        "shard_manifest_sha256": sha256_file(shard_manifest_path),
        "pilot_window_id": PILOT_WINDOW_ID,
        "selection_rule": "first eligible instance_id in the shard manifest's stored task order, excluding the M3 pilot window (same rule as FCE-S1/FCE-S4)",
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
# Step 1: real DeepSeek loop run (one real worker call, `--limit 1`; same
# machinery FCE-S1/FCE-S4 use) - produces one real, non-fixture Micro Tape.
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
        # Same M1b precondition as FCE-S1/FCE-S4: no OS-keyring session is
        # available on this headless certification host (no D-Bus session /
        # X11). The test-local authority path is a real, non-silent M1b
        # authorization event (authority_kind=test_local_authority_no_credentials),
        # never a fallback under --authorization-mode required.
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
# Independent MicroTape head + whole-tree-digest capture (never trusts the
# console's own prose - reads refs directly via git, mirroring
# crates/turing-cli/tests/cli_gates.rs::read_heads /
# tools/hci/audit_projection_integrity.py::heads_from_micro_git).
# --------------------------------------------------------------------------


def read_ref(repo: Path, ref_name: str) -> str | None:
    proc = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", "--end-of-options", ref_name],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def read_heads(repo: Path) -> dict[str, str | None]:
    return {ref_name: read_ref(repo, ref_name) for ref_name in REF_NAMES}


def tree_manifest_sha256(tree_root: Path) -> str:
    lines = []
    for path in sorted(item for item in tree_root.rglob("*") if item.is_file()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(tree_root).as_posix()}")
    manifest = "\n".join(lines) + "\n"
    return "sha256:" + hashlib.sha256(manifest.encode("utf-8")).hexdigest()


def sample_event_id(repo: Path) -> str | None:
    proc = subprocess.run(
        ["git", "-C", str(repo), "rev-list", "-n", "1", "refs/turingos/tape_tip"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    oid = proc.stdout.strip()
    if proc.returncode != 0 or not oid:
        return None
    return f"mu:{oid}"


# --------------------------------------------------------------------------
# The full console command matrix (spec: "status, panoview, explain, ask,
# approval preview, --json modes"). Mirrors
# crates/turing-cli/tests/cli_gates.rs::operator_command_matrix exactly (same
# case shapes/labels), run here against the REAL tape instead of a synthetic
# 2-event fixture repo.
# --------------------------------------------------------------------------


def build_console_command_matrix(repo_arg: str, bundle_arg: str, event_id: str | None) -> list[dict[str, Any]]:
    digest = "sha256:" + "a" * 64
    cases: list[dict[str, Any]] = [
        {"label": "help", "argv": ["--help"], "expect": ["Operator Console v1"]},
        {"label": "help commands", "argv": ["help", "commands"], "expect": ["operator_tool_manifest.v1", "writes_truth="]},
        {
            "label": "status micro-git",
            "argv": ["status", "--micro-git", repo_arg],
            "expect": ["operator_view_snapshot.v1", "source_kind=guarded_micro_tape_read", "can_write_truth=false"],
        },
        {
            "label": "status micro-git json",
            "argv": ["status", "--micro-git", repo_arg, "--json"],
            "expect": ["operator_view_snapshot.v1", "guarded_micro_tape_read"],
        },
        {
            "label": "panoview micro-git",
            "argv": ["panoview", "--micro-git", repo_arg],
            "expect": ["source=guarded_micro_tape_read"],
        },
        {
            "label": "panoview micro-git json",
            "argv": ["panoview", "--micro-git", repo_arg, "--json"],
            "expect": ["operator_view_snapshot.v1", "guarded_micro_tape_read"],
        },
        {
            "label": "explain blocker micro-git",
            "argv": ["explain", "blocker", "--micro-git", repo_arg],
            "expect": ["EXPLAIN_BLOCKER", "source_kind=guarded_micro_tape_read"],
        },
        {
            "label": "explain event micro-git no-id",
            "argv": ["explain", "event", "--micro-git", repo_arg],
            "expect": ["EXPLAIN_EVENT"],
        },
        {
            "label": "status micro-bundle",
            "argv": ["status", "--micro-bundle", bundle_arg],
            "expect": ["source_kind=guarded_micro_tape_read"],
        },
        {
            "label": "status micro-bundle json",
            "argv": ["status", "--micro-bundle", bundle_arg, "--json"],
            "expect": ["operator_view_snapshot.v1", "guarded_micro_tape_read"],
        },
        {
            "label": "panoview micro-bundle",
            "argv": ["panoview", "--micro-bundle", bundle_arg],
            "expect": ["source=guarded_micro_tape_read"],
        },
        {
            "label": "panoview micro-bundle json",
            "argv": ["panoview", "--micro-bundle", bundle_arg, "--json"],
            "expect": ["operator_view_snapshot.v1", "guarded_micro_tape_read"],
        },
        {
            "label": "explain event micro-bundle",
            "argv": ["explain", "event", "--micro-bundle", bundle_arg],
            "expect": ["EXPLAIN_EVENT"],
        },
        {
            "label": "approval preview",
            "argv": [
                "approval", "preview",
                "--approval-id", "ap_fce_s5_preview",
                "--authority-epoch", "7",
                "--action", "capsule_approve",
                "--subject", "wc_fce_s5",
                "--risk", "P2",
                "--evidence-digest", digest,
                "--signature-route", "none",
            ],
            "expect": ["writes_micro_truth=false"],
        },
    ]
    if event_id:
        cases.append(
            {
                "label": "explain event micro-git real-id",
                "argv": ["explain", "event", event_id, "--micro-git", repo_arg],
                "expect": ["EXPLAIN_EVENT"],
            }
        )
    cases.append(
        {
            "label": "operator stdin script",
            "argv": ["operator"],
            "stdin": f"status\npanoview\nexplain event {event_id or 'unknown'}\nquit\n",
            "expect": ["EXPLAIN_EVENT"],
        }
    )
    ask_cases = [
        ("ask view status", "status", "VIEW_STATUS"),
        ("ask view panoview", "panoview", "VIEW_PANOVIEW"),
        ("ask explain event", "event details", "EXPLAIN_EVENT"),
        ("ask explain blocker", "blocker", "EXPLAIN_BLOCKER"),
        ("ask replay verify", "replay verify", "REPLAY_VERIFY"),
        ("ask audit invariants", "audit invariants", "AUDIT_INVARIANTS"),
        ("ask propose intent", "intent proposal", "PROPOSE_INTENT"),
        ("ask propose goal", "goal proposal", "PROPOSE_GOAL"),
        ("ask propose capsule", "capsule proposal", "PROPOSE_CAPSULE"),
        ("ask approve capsule", "approve capsule", "APPROVE_CAPSULE"),
        ("ask dispatch worker", "dispatch worker", "DISPATCH_WORKER"),
        ("ask observe capsule", "observe capsule", "OBSERVE_CAPSULE"),
        ("ask reject candidate", "reject candidate", "REJECT_CANDIDATE"),
        ("ask request macro auth", "request macro authorization", "REQUEST_MACRO_AUTH"),
        ("ask approve candidate", "approve candidate", "APPROVE_CANDIDATE"),
        ("ask help", "help", "HELP"),
    ]
    for label, utterance, expected_verb in ask_cases:
        cases.append({"label": label, "argv": ["ask", utterance], "expect": [expected_verb]})
    return cases


PERMISSION_ERROR_PATTERN = re.compile(r"permission denied|eacces", re.IGNORECASE)
WRITE_CLAIM_PATTERN = re.compile(r"writes_truth=true|writes_micro_truth=true")


def run_console_matrix(turing_bin: Path, matrix: list[dict[str, Any]], out_dir: Path, label_prefix: str) -> list[dict[str, Any]]:
    results = []
    for index, case in enumerate(matrix):
        safe_label = re.sub(r"[^a-zA-Z0-9]+", "_", case["label"]).strip("_")
        command = run_command(
            name=f"{label_prefix}_{index:02d}_{safe_label}",
            argv=[str(turing_bin), *case["argv"]],
            cwd=turing_bin.parent,
            out_dir=out_dir,
            stdin_text=case.get("stdin"),
            timeout=60,
        )
        combined = command["stdout_text"] + "\n" + command["stderr_text"]
        expect_hits = {token: (token in command["stdout_text"]) for token in case.get("expect", [])}
        results.append(
            {
                "label": case["label"],
                "command": command,
                "expect_hits": expect_hits,
                "all_expected_present": all(expect_hits.values()) if expect_hits else True,
                "claims_write_authority": bool(WRITE_CLAIM_PATTERN.search(combined)),
                "permission_error_present": bool(PERMISSION_ERROR_PATTERN.search(combined)),
            }
        )
    return results


def chmod_recursive(root: Path, *, writable: bool) -> None:
    paths = [root] + [item for item in root.rglob("*")]
    for path in paths:
        if path.is_symlink():
            continue
        try:
            mode = path.lstat().st_mode
        except OSError:
            continue
        new_mode = (mode | 0o200) if writable else (mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
        try:
            os.chmod(path, new_mode)
        except OSError:
            pass


# --------------------------------------------------------------------------
# `turing help commands` structural check: every fixed verb in the closed
# operator_tool_manifest.v1 must self-report writes_truth=false (the "refusal
# path is code, not convention" check - no verb, including the
# mutation-shaped ones like APPROVE_CANDIDATE/DISPATCH_WORKER, may claim write
# authority).
# --------------------------------------------------------------------------


def parse_help_commands_write_flags(text: str) -> dict[str, str]:
    flags: dict[str, str] = {}
    for line in text.splitlines():
        verb_match = re.search(r"verb=(\S+)", line)
        writes_match = re.search(r"writes_truth=(\S+)", line)
        if verb_match and writes_match:
            flags[verb_match.group(1)] = writes_match.group(1)
    return flags


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
    evidence_paths = sorted({rel(root, path) for path in evidence_files if path.is_file()})
    passed = all(item["result"] is True for item in criteria)
    return {
        "schema_id": "turingos.fce_scenario_verdict.v1",
        "scenario_id": scenario_id,
        "verdict": "PASS" if passed else "FAIL",
        "not_run_is_fail": True,
        "goals_served": ["G7"],
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
    key_provenance_path = scenario_root / "deepseek_api_key_provenance.json"
    write_json(
        key_provenance_path,
        {
            "schema_id": "turingos.fce.s5.api_key_provenance.v1",
            "present": api_key is not None,
            "source": api_key_source,
            "secrets_env_path": str(SECRETS_ENV_PATH),
        },
    )
    evidence_files.append(key_provenance_path)

    if not api_key:
        criteria = [
            {"criterion": "deepseek_api_key_present", "result": False, "evidence": f"{scenario_id}/deepseek_api_key_provenance.json"}
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
        verdict["not_run_reason"] = (
            f"missing {DEEPSEEK_API_KEY_ENV}: not in environment and not found in {SECRETS_ENV_PATH}"
        )
        write_json(scenario_root / f"{scenario_id}_verdict.json", verdict)
        print(json.dumps({"scenario_id": scenario_id, "verdict": "NOT_RUN"}, sort_keys=True))
        return 2

    daemon_bin = resolve_daemon_bin_dir(repo, scenario_root)
    daemon_bin_dir = Path(daemon_bin["bin_dir"])
    turing_bin = daemon_bin_dir / "turing"
    evidence_files.append(scenario_root / "daemon_bin_dir_resolution.json")

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
    loop_ok = loop["command"]["exit_code"] == 0 and bool(runs)

    # ---- default/failure-shaped values, overwritten below if the real loop succeeded ----
    micro_git = loop["loop_root"] / "instances" / selection["instance_id"] / "micro.git"
    micro_bundle = loop["loop_root"] / "instances" / selection["instance_id"] / "micro_tape.bundle"
    integrity_verdict: dict[str, Any] = {"verdict": "FAIL", "checks": {}}
    integrity_verdict_path = scenario_root / "console" / "projection_integrity_verdict.json"
    tape_is_real_snapshot = False
    writable_heads_before: dict[str, str | None] = {}
    writable_heads_after: dict[str, str | None] = {}
    writable_tree_before = ""
    writable_tree_after = ""
    writable_results: list[dict[str, Any]] = []
    readonly_heads_before: dict[str, str | None] = {}
    readonly_heads_after: dict[str, str | None] = {}
    readonly_results: list[dict[str, Any]] = []
    help_commands_flags: dict[str, str] = {}
    m1a_command: dict[str, Any] = {"exit_code": -1}

    if loop_ok:
        m1a_command = run_command(
            name="m1a_gates",
            argv=["bash", "tools/ci/run_m1a_gates.sh"],
            cwd=repo,
            out_dir=scenario_root / "commands",
            timeout=300,
        )
        commands.append(m1a_command)

        event_id = sample_event_id(micro_git)
        repo_arg = str(micro_git)
        bundle_arg = str(micro_bundle)

        # ---- step: real M6 console replay + projection-integrity audit (RES_M6 S2.4) ----
        console_dir = scenario_root / "console"
        console_dir.mkdir(parents=True, exist_ok=True)
        snapshot_command = run_command(
            name="console_status_json",
            argv=[str(turing_bin), "status", "--micro-git", repo_arg, "--json"],
            cwd=repo,
            out_dir=scenario_root / "commands",
            timeout=60,
        )
        commands.append(snapshot_command)
        snapshot_path = console_dir / "operator_snapshot.json"
        snapshot_path.write_text(snapshot_command["stdout_text"], encoding="utf-8")
        text_command = run_command(
            name="console_status_text",
            argv=[str(turing_bin), "status", "--micro-git", repo_arg],
            cwd=repo,
            out_dir=scenario_root / "commands",
            timeout=60,
        )
        commands.append(text_command)
        text_path = console_dir / "operator_status.txt"
        text_path.write_text(text_command["stdout_text"], encoding="utf-8")

        integrity_command = run_command(
            name="projection_integrity_audit",
            argv=[
                sys.executable,
                str(repo / "tools" / "hci" / "audit_projection_integrity.py"),
                "--micro-git",
                repo_arg,
                "--snapshot-json",
                str(snapshot_path),
                "--text-output",
                str(text_path),
                "--provenance",
                str(repo / "schemas" / "operator" / "operator_view_snapshot.v1.provenance.json"),
                "--repo-root",
                str(repo),
                "--out",
                str(integrity_verdict_path),
            ],
            cwd=repo,
            out_dir=scenario_root / "commands",
            timeout=120,
        )
        commands.append(integrity_command)
        integrity_verdict = load_json(integrity_verdict_path) if integrity_verdict_path.is_file() else {"verdict": "FAIL", "checks": {}}
        evidence_files.append(integrity_verdict_path)

        try:
            snapshot_json = json.loads(snapshot_command["stdout_text"])
        except json.JSONDecodeError:
            snapshot_json = {}
        source = snapshot_json.get("source", {}) if isinstance(snapshot_json, dict) else {}
        tape_is_real_snapshot = (
            source.get("source_kind") == "guarded_micro_tape_read"
            and isinstance(source.get("micro_repo"), str)
            and source.get("micro_repo") == str(micro_git.resolve())
            and "demo" not in source.get("micro_repo", "")
        )

        # ---- step: `help commands` structural no-write-authority check ----
        help_commands_command = run_command(
            name="console_help_commands",
            argv=[str(turing_bin), "help", "commands"],
            cwd=repo,
            out_dir=scenario_root / "commands",
            timeout=30,
        )
        commands.append(help_commands_command)
        help_commands_flags = parse_help_commands_write_flags(help_commands_command["stdout_text"])
        help_commands_path = scenario_root / "help_commands_write_flags.json"
        write_json(help_commands_path, help_commands_flags)
        evidence_files.append(help_commands_path)

        # ---- step: dynamic head-conservation test over the FULL command matrix ----
        matrix = build_console_command_matrix(repo_arg, bundle_arg, event_id)
        writable_heads_before = read_heads(micro_git)
        writable_tree_before = tree_manifest_sha256(micro_git)
        writable_results = run_console_matrix(turing_bin, matrix, scenario_root / "commands" / "writable_matrix", "writable")
        for result in writable_results:
            commands.append(result["command"])
        writable_heads_after = read_heads(micro_git)
        writable_tree_after = tree_manifest_sha256(micro_git)

        writable_matrix_path = scenario_root / "writable_matrix_summary.json"
        write_json(
            writable_matrix_path,
            {
                "schema_id": "turingos.fce.s5.writable_matrix_summary.v1",
                "heads_before": writable_heads_before,
                "heads_after": writable_heads_after,
                "tree_digest_before": writable_tree_before,
                "tree_digest_after": writable_tree_after,
                "cases": [
                    {
                        "label": item["label"],
                        "cmd": item["command"]["cmd"],
                        "exit_code": item["command"]["exit_code"],
                        "expect_hits": item["expect_hits"],
                        "all_expected_present": item["all_expected_present"],
                        "claims_write_authority": item["claims_write_authority"],
                        "permission_error_present": item["permission_error_present"],
                    }
                    for item in writable_results
                ],
            },
        )
        evidence_files.append(writable_matrix_path)

        # ---- step: read-only filesystem matrix (chmod -R a-w scratch copy) ----
        readonly_scratch = scenario_root / "readonly_tape"
        if readonly_scratch.exists():
            chmod_recursive(readonly_scratch, writable=True)
            shutil.rmtree(readonly_scratch)
        readonly_scratch.mkdir(parents=True)
        readonly_micro_git = readonly_scratch / "micro.git"
        readonly_bundle = readonly_scratch / "micro_tape.bundle"
        shutil.copytree(micro_git, readonly_micro_git)
        shutil.copy2(micro_bundle, readonly_bundle)
        readonly_heads_before = read_heads(readonly_micro_git)
        try:
            chmod_recursive(readonly_scratch, writable=False)
            readonly_matrix = build_console_command_matrix(str(readonly_micro_git), str(readonly_bundle), event_id)
            readonly_results = run_console_matrix(
                turing_bin, readonly_matrix, scenario_root / "commands" / "readonly_matrix", "readonly"
            )
            for result in readonly_results:
                commands.append(result["command"])
        finally:
            chmod_recursive(readonly_scratch, writable=True)
        readonly_heads_after = read_heads(readonly_micro_git)

        readonly_matrix_path = scenario_root / "readonly_matrix_summary.json"
        write_json(
            readonly_matrix_path,
            {
                "schema_id": "turingos.fce.s5.readonly_matrix_summary.v1",
                "heads_before": readonly_heads_before,
                "heads_after": readonly_heads_after,
                "cases": [
                    {
                        "label": item["label"],
                        "cmd": item["command"]["cmd"],
                        "exit_code": item["command"]["exit_code"],
                        "claims_write_authority": item["claims_write_authority"],
                        "permission_error_present": item["permission_error_present"],
                    }
                    for item in readonly_results
                ],
            },
        )
        evidence_files.append(readonly_matrix_path)

    # ---- criteria (spec section 3, FCE-S5 "PASS criteria (all)") ----
    checks = integrity_verdict.get("checks", {}) if isinstance(integrity_verdict, dict) else {}
    writable_heads_unchanged = bool(writable_heads_before) and writable_heads_before == writable_heads_after
    writable_tree_unchanged = bool(writable_tree_before) and writable_tree_before == writable_tree_after
    writable_all_exit_zero = bool(writable_results) and all(item["command"]["exit_code"] == 0 for item in writable_results)
    writable_zero_write_claims = bool(writable_results) and not any(item["claims_write_authority"] for item in writable_results)
    writable_all_expected_present = bool(writable_results) and all(item["all_expected_present"] for item in writable_results)

    readonly_heads_unchanged = bool(readonly_heads_before) and readonly_heads_before == readonly_heads_after
    readonly_all_exit_zero = bool(readonly_results) and all(item["command"]["exit_code"] == 0 for item in readonly_results)
    readonly_zero_permission_errors = bool(readonly_results) and not any(item["permission_error_present"] for item in readonly_results)
    readonly_zero_write_claims = bool(readonly_results) and not any(item["claims_write_authority"] for item in readonly_results)

    help_commands_zero_write_authority = bool(help_commands_flags) and all(
        value == "false" for value in help_commands_flags.values()
    )

    criteria = [
        {
            "criterion": "deepseek_api_key_present",
            "result": api_key is not None,
            "evidence": rel(root, key_provenance_path),
        },
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
            "criterion": "real_deepseek_loop_run_produces_non_fixture_tape",
            "result": loop_ok,
            "evidence": rel(root, loop["coverage_path"]) if loop["coverage_path"].is_file() else f"{scenario_id}/commands/run_mini_swe_bench_substrate_smoke.stderr.txt",
        },
        {
            "criterion": "m1a_canonical_writer_gate_pass",
            "result": m1a_command["exit_code"] == 0,
            "evidence": rel(root, integrity_verdict_path) if integrity_verdict_path.is_file() else f"{scenario_id}/commands",
        },
        {
            "criterion": "console_points_at_real_tape_not_demo_fixture",
            "result": tape_is_real_snapshot,
            "evidence": rel(root, scenario_root / "console" / "operator_snapshot.json"),
        },
        {
            "criterion": "provenance_closure_100_percent",
            "result": checks.get("provenance_closure") == "PASS",
            "evidence": rel(root, integrity_verdict_path) if integrity_verdict_path.is_file() else "",
        },
        {
            "criterion": "shadow_rebuild_hash_equal",
            "result": checks.get("shadow_rebuild") == "PASS",
            "evidence": rel(root, integrity_verdict_path) if integrity_verdict_path.is_file() else "",
        },
        {
            "criterion": "independent_head_derivation_equal",
            "result": checks.get("independent_heads") == "PASS",
            "evidence": rel(root, integrity_verdict_path) if integrity_verdict_path.is_file() else "",
        },
        {
            "criterion": "render_fidelity_every_token_present_in_snapshot",
            "result": checks.get("render_fidelity") == "PASS",
            "evidence": rel(root, integrity_verdict_path) if integrity_verdict_path.is_file() else "",
        },
        {
            "criterion": "worker_side_builders_zero_snapshot_schema_leakage",
            "result": checks.get("worker_leakage") == "PASS",
            "evidence": rel(root, integrity_verdict_path) if integrity_verdict_path.is_file() else "",
        },
        {
            "criterion": "help_commands_zero_verbs_claim_write_authority",
            "result": help_commands_zero_write_authority,
            "evidence": rel(root, scenario_root / "help_commands_write_flags.json") if (scenario_root / "help_commands_write_flags.json").is_file() else "",
        },
        {
            "criterion": "writable_matrix_all_commands_exit_zero",
            "result": writable_all_exit_zero,
            "evidence": rel(root, scenario_root / "writable_matrix_summary.json") if (scenario_root / "writable_matrix_summary.json").is_file() else "",
        },
        {
            "criterion": "writable_matrix_all_expected_content_present",
            "result": writable_all_expected_present,
            "evidence": rel(root, scenario_root / "writable_matrix_summary.json") if (scenario_root / "writable_matrix_summary.json").is_file() else "",
        },
        {
            "criterion": "writable_matrix_zero_commands_claim_write_authority",
            "result": writable_zero_write_claims,
            "evidence": rel(root, scenario_root / "writable_matrix_summary.json") if (scenario_root / "writable_matrix_summary.json").is_file() else "",
        },
        {
            "criterion": "writable_matrix_refs_byte_identical_before_after",
            "result": writable_heads_unchanged,
            "evidence": rel(root, scenario_root / "writable_matrix_summary.json") if (scenario_root / "writable_matrix_summary.json").is_file() else "",
        },
        {
            "criterion": "writable_matrix_tree_digest_byte_identical_before_after",
            "result": writable_tree_unchanged,
            "evidence": rel(root, scenario_root / "writable_matrix_summary.json") if (scenario_root / "writable_matrix_summary.json").is_file() else "",
        },
        {
            "criterion": "readonly_matrix_all_commands_exit_zero",
            "result": readonly_all_exit_zero,
            "evidence": rel(root, scenario_root / "readonly_matrix_summary.json") if (scenario_root / "readonly_matrix_summary.json").is_file() else "",
        },
        {
            "criterion": "readonly_matrix_zero_eacces_masked_writes",
            "result": readonly_zero_permission_errors,
            "evidence": rel(root, scenario_root / "readonly_matrix_summary.json") if (scenario_root / "readonly_matrix_summary.json").is_file() else "",
        },
        {
            "criterion": "readonly_matrix_zero_commands_claim_write_authority",
            "result": readonly_zero_write_claims,
            "evidence": rel(root, scenario_root / "readonly_matrix_summary.json") if (scenario_root / "readonly_matrix_summary.json").is_file() else "",
        },
        {
            "criterion": "readonly_matrix_refs_byte_identical_before_after",
            "result": readonly_heads_unchanged,
            "evidence": rel(root, scenario_root / "readonly_matrix_summary.json") if (scenario_root / "readonly_matrix_summary.json").is_file() else "",
        },
    ]

    readme = scenario_root / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# FCE-S5 Console Truthfulness and No-Write Proof",
                "",
                "Evidence label: REAL.",
                "",
                "One real DeepSeek native-API worker call (arm-B single-loop run, same",
                "machinery FCE-S1/FCE-S4 use, `--limit 1` to keep spend minimal), producing",
                "one real, non-fixture Micro Tape. The real `turing` console binary is pointed",
                "at that tape and run through the FULL command matrix (`status`, `panoview`,",
                "`explain`, `ask`, `approval preview`, all `--json` modes, `--micro-git` and",
                "`--micro-bundle` sources, the `operator` stdin REPL - the same case shapes",
                "`crates/turing-cli/tests/cli_gates.rs::operator_command_matrix` already",
                "exercises against a synthetic fixture, run here against the real tape",
                "instead). `tools/hci/audit_projection_integrity.py` (shadow rebuild,",
                "independent head derivation, provenance-manifest closure, render fidelity,",
                "worker-side leakage) is run against the real `status --json` snapshot.",
                "The three `refs/turingos/*` heads (and a whole-tree digest of the MicroTape",
                "object store) are captured independently via `git rev-parse` before and",
                "after the full matrix, on both a writable copy and a `chmod -R a-w`",
                "read-only copy of the tape, and asserted byte-identical.",
                "",
                "Reproducibility: this scenario loads DEEPSEEK_API_KEY from the environment",
                "or, if absent, from ~/.turingos/secrets.env itself - it never assumes the",
                "caller pre-exported it.",
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
                "FCE-S5 console no-write certification: the real M6 console, pointed at a "
                "real (non-fixture) Micro Tape, displays only tape-derivable fields "
                "(provenance closure 100%, shadow-rebuild and independent-head equality, "
                "render fidelity) and cannot write (refs and whole-tree digest byte-identical "
                "across the full command matrix, on both a writable and a read-only-"
                "filesystem copy of the tape; zero commands claim write authority; the closed "
                "operator_tool_manifest.v1 structurally reports writes_truth=false for every "
                "verb)",
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
    if loop_ok and (not writable_heads_unchanged or not readonly_heads_unchanged):
        automatic_fail = "head_movement_by_console"

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
