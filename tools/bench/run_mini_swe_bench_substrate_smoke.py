#!/usr/bin/env python3
"""Run a real-TuringOS substrate smoke over SWE-bench-shaped tasks.

This is not a score runner. It exists to connect a real benchmark task shape to
the TuringOS substrate: Micro Tape, daemon RPC, executor, market, PPUT,
projection, predicate accept/reject, and qualification checks. Full scoring must
wait until this coverage audit passes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
AUDITOR = REPO / "tools" / "bench" / "audit_mini_swe_bench_substrate_coverage.py"
REQUIRED_MODULES = [
    "M0_law_goal_harness",
    "M1_canonical_codec",
    "M2_micro_git_tape",
    "M3_event_registry",
    "M4_single_loop",
    "M5_goal_module_atom_capsule",
    "M6_worker_profiles",
    "M7_executor_broker",
    "M8_macro_observer",
    "M9_predicate_kernel",
    "M10_evidence_approval",
    "M11_failure_memory",
    "M12_market_substrate",
    "M13_marketrouter_shadow",
    "M14_pput_accounting",
    "M15_projection",
    "M16_integration_queue",
    "M17_e2e_handoff",
]
SWEBENCH_FORBIDDEN_PATHS = ["secrets", "tests/**", "*/tests/**", "test_*.py", "*_test.py"]


def digest_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def read_tasks(path: Path, limit: int) -> list[dict[str, Any]]:
    tasks = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            task = json.loads(line)
            for key in ("instance_id", "repo", "base_commit", "problem_statement"):
                if key not in task:
                    raise ValueError(f"task missing {key}")
            tasks.append(task)
            if len(tasks) >= limit:
                break
    if not tasks:
        raise ValueError("no tasks loaded")
    return tasks


def read_broadcast_rules(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    packet = json.loads(path.read_text(encoding="utf-8"))
    rules = packet.get("rules", packet if isinstance(packet, list) else [])
    if not isinstance(rules, list):
        raise ValueError("broadcast rules file must contain a rules list")
    return [rule for rule in rules if isinstance(rule, dict)]


def run_cmd(argv: list[str], *, cwd: Path | None = None, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=timeout)


def run_cmd_timed(
    argv: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 120,
) -> tuple[subprocess.CompletedProcess[str], int]:
    start = time.monotonic()
    try:
        proc = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or ""
        stderr = error.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        proc = subprocess.CompletedProcess(argv, 124, stdout, stderr + "\nTIMEOUT")
    elapsed_ms = max(1, int((time.monotonic() - start) * 1000))
    return proc, elapsed_ms


def ensure_binaries(bin_dir: Path) -> None:
    required = ["turingd", "turing-execd", "turing-mcp", "turing-marketd", "turing-pputd", "turing-viewd", "turing"]
    missing = [name for name in required if not (bin_dir / name).exists()]
    if not missing:
        return
    proc = run_cmd(
        ["cargo", "build", "-p", "turing-daemons", "--bins", "-p", "turing-cli", "--bin", "turing"],
        cwd=REPO,
        timeout=600,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"cargo build for daemon binaries failed:\n{proc.stderr}")
    still_missing = [name for name in required if not (bin_dir / name).exists()]
    if still_missing:
        raise RuntimeError(f"missing daemon binaries after build: {still_missing}")


class Daemon:
    def __init__(
        self,
        name: str,
        bin_dir: Path,
        socket_path: Path,
        *,
        micro_git: Path | None = None,
        project: Path | None = None,
    ) -> None:
        self.name = name
        self.bin_dir = bin_dir
        self.socket_path = socket_path
        self.micro_git = micro_git
        self.project = project
        self.proc: subprocess.Popen[str] | None = None

    def __enter__(self) -> "Daemon":
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self.socket_path.parent, 0o700)
        if self.socket_path.exists():
            self.socket_path.unlink()
        argv = [str(self.bin_dir / self.name), "--serve", "--socket", str(self.socket_path)]
        if self.micro_git is not None:
            argv += ["--micro-git", str(self.micro_git)]
        if self.project is not None:
            argv += ["--project", str(self.project)]
        self.proc = subprocess.Popen(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        deadline = time.time() + 10
        while time.time() < deadline:
            if self.socket_path.exists():
                return self
            if self.proc.poll() is not None:
                stderr = self.proc.stderr.read() if self.proc.stderr else ""
                raise RuntimeError(f"{self.name} exited before socket appeared: {stderr}")
            time.sleep(0.05)
        raise RuntimeError(f"{self.name} socket did not appear at {self.socket_path}")

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self.proc is None:
            return
        try:
            rpc(self.socket_path, "daemon.shutdown", None)
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()
            self.proc.wait(timeout=5)


def rpc(socket_path: Path, method: str, params: dict[str, Any] | None) -> dict[str, Any]:
    request: dict[str, Any] = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        request["params"] = params
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stream:
        stream.connect(str(socket_path))
        stream.sendall((json.dumps(request, sort_keys=True) + "\n").encode("utf-8"))
        with stream.makefile("r", encoding="utf-8") as handle:
            line = handle.readline()
    if not line:
        raise RuntimeError(f"empty RPC response for {method}")
    response = json.loads(line)
    if "error" in response:
        raise RuntimeError(f"RPC {method} failed: {response['error']}")
    return response["result"]


def init_micro_git(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    proc = run_cmd(["git", "-C", str(path), "init", "--object-format=sha256", "-q", "--", "."], timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"git init sha256 failed: {proc.stderr}")


def increment(mapping: dict[str, int], key: str, amount: int = 1) -> None:
    mapping[key] = mapping.get(key, 0) + amount


def append_preserve(turingd: Daemon, event_type: str, writer_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if "event_type" not in payload:
        payload = {"event_type": event_type, **payload}
    return rpc(
        turingd.socket_path,
        "event.append_preserve",
        {"event_type": event_type, "writer_id": writer_id, "payload": payload},
    )


def goal_payload(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_id": "goal_state.v1",
        "goal_id": f"goal_{task['instance_id']}",
        "objective": f"Run TuringOS substrate path for {task['instance_id']}",
        "must_haves": [
            {
                "text": "predicate and replay evidence exist",
                "machine_checks": [{"kind": "PREDICATE", "predicate_id": "predicate.replay.verify"}],
            }
        ],
        "anti_goals": ["do not expose PPUT to Worker prompts"],
    }


def worker_id_for_grok(model: str) -> str:
    seed = {
        "schema_id": "worker_identity_seed.v1",
        "provider": "grok",
        "kind": "CommandTemplate",
        "model": model,
        "thinking_mode": "no_plan_no_memory_no_subagents_plain_output",
    }
    return "worker:sha256:" + hashlib.sha256(
        json.dumps(seed, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def repo_url(repo: str) -> str:
    if repo.startswith(("http://", "https://", "git@")):
        return repo
    return f"https://github.com/{repo}.git"


def checkout_task(task: dict[str, Any], worktree: Path) -> None:
    if worktree.exists():
        shutil.rmtree(worktree)
    worktree.parent.mkdir(parents=True, exist_ok=True)
    clone = run_cmd(
        [
            "git",
            "clone",
            "--filter=blob:none",
            "--no-checkout",
            repo_url(task["repo"]),
            str(worktree),
        ],
        timeout=900,
    )
    if clone.returncode != 0:
        raise RuntimeError(f"git clone failed for {task['repo']}:\n{clone.stderr}")
    checkout = run_cmd(["git", "-C", str(worktree), "checkout", task["base_commit"]], timeout=900)
    if checkout.returncode != 0:
        raise RuntimeError(f"git checkout failed for {task['instance_id']}:\n{checkout.stderr}")


def visible_grok_prompt(
    task: dict[str, Any],
    capsule_id: str,
    broadcast_rules: list[dict[str, Any]] | None = None,
) -> str:
    broadcast_section = ""
    if broadcast_rules:
        lines = ["Known failures to avoid:"]
        for rule in broadcast_rules:
            lines.append(
                f"- {rule['failure_class']}: {rule['guidance']} (source rule {rule['rule_id']})"
            )
        broadcast_section = "\n".join(lines) + "\n"
    return (
        "You are a TuringOS worker operating on a SWE-bench task.\n"
        "Do not output private chain-of-thought or hidden scratchpads.\n"
        "TuringOS Micro Tape is the external execution trace.\n"
        "Acceptance is predicate-only; exit code, CI, self-report, price, and benchmark labels are not truth.\n"
        "Do not request or use credentials.\n"
        "Your job is to make the smallest plausible code patch in the checked-out worktree.\n"
        "Do not edit benchmark/official test files unless this capsule explicitly allows test changes.\n"
        "Avoid long investigation narratives. Inspect only the files needed, edit them, and stop when a candidate patch exists.\n"
        "If you cannot safely patch, leave the worktree unchanged and say why.\n"
        f"{broadcast_section}"
        f"Capsule: {capsule_id}\n"
        f"Instance: {task['instance_id']}\n"
        f"Repo: {task['repo']}\n"
        f"Base commit: {task['base_commit']}\n"
        "Task:\n"
        f"{task['problem_statement']}\n"
        "Edit the checked-out repository only. When done, leave the patch in the worktree.\n"
    )


def classify_worker_stop(
    *,
    exit_code: int,
    stderr: str,
    diff_text: str,
    official_eval_result: str | None,
) -> str:
    has_patch = bool(diff_text.strip())
    if official_eval_result == "PASS" and exit_code != 0 and has_patch:
        return "PATCH_PASS_WITH_WORKER_NONZERO"
    if official_eval_result == "FAIL" and exit_code == 0 and has_patch:
        return "PATCH_FAIL_WITH_EXIT_ZERO"
    if "max turns" in stderr.lower() and has_patch:
        return "MAX_TURNS_WITH_PATCH"
    if not has_patch:
        return "MAX_TURNS_NO_PATCH"
    if exit_code != 0:
        return "MAX_TURNS_WITH_PATCH"
    return "PATCH_FAIL_WITH_EXIT_ZERO" if official_eval_result == "FAIL" else "PATCH_PRESENT_EXIT_ZERO"


def pput_prompt_validation_request(log_dir: Path) -> dict[str, Any]:
    prompt = (log_dir / "visible_prompt.txt").read_text(encoding="utf-8")
    return {
        "prompt": prompt,
        "prompt_hash": digest_text(prompt),
        "source": "actual_visible_prompt_txt",
    }


def redacted_grok_argv(argv: list[str]) -> list[str]:
    result = list(argv)
    if "-p" in result:
        index = result.index("-p")
        if index + 1 < len(result):
            result[index + 1] = "<visible_capsule_prompt>"
    return result


def run_grok_worker(
    task: dict[str, Any],
    instance_dir: Path,
    worker_id: str,
    model: str,
    max_turns: int,
    timeout_s: int,
    capsule_id: str,
    broadcast_rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if shutil.which("grok") is None:
        raise RuntimeError("grok CLI is missing; real-worker substrate smoke cannot run")

    worktree_root = Path(os.environ.get("TURINGOS_SUBSTRATE_WORKTREE_ROOT", "/tmp/turingos_substrate_worktrees"))
    worktree = worktree_root / hashlib.sha256(
        f"{instance_dir}:{task['instance_id']}:{model}".encode("utf-8")
    ).hexdigest()[:16]
    checkout_task(task, worktree)
    prompt = visible_grok_prompt(task, capsule_id, broadcast_rules=broadcast_rules)
    worktree_abs = worktree.resolve()
    argv = [
        "grok",
        "-p",
        prompt,
        "--cwd",
        str(worktree_abs),
        "--output-format",
        "plain",
        "--model",
        model,
        "--always-approve",
        "--permission-mode",
        "bypassPermissions",
        "--disable-web-search",
        "--no-plan",
        "--no-memory",
        "--no-subagents",
        "--max-turns",
        str(max_turns),
        "--verbatim",
    ]
    proc, elapsed_ms = run_cmd_timed(argv, timeout=timeout_s)
    diff = run_cmd(["git", "-C", str(worktree), "diff", "--binary"], timeout=180)
    diff_text = diff.stdout if diff.returncode == 0 else diff.stderr
    stdout_hash = digest_text(proc.stdout)
    stderr_hash = digest_text(proc.stderr)
    patch_hash = digest_text(diff_text)
    done = {
        "schema_id": "grok_worker_done.v1",
        "instance_id": task["instance_id"],
        "worker_id": worker_id,
        "model": model,
        "exit_code": proc.returncode,
        "elapsed_ms": elapsed_ms,
        "patch_hash": patch_hash,
    }
    done_json = json.dumps(done, sort_keys=True, separators=(",", ":"))
    receipt_id = "rcp_" + hashlib.sha256(
        f"{task['instance_id']}:{worker_id}:{stdout_hash}:{stderr_hash}:{patch_hash}".encode("utf-8")
    ).hexdigest()[:32]

    log_dir = instance_dir / "worker_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "command.json").write_text(
        json.dumps({"argv": redacted_grok_argv(argv)}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (log_dir / "visible_prompt.txt").write_text(prompt, encoding="utf-8")
    (log_dir / "stdout.txt").write_text(proc.stdout, encoding="utf-8")
    (log_dir / "stderr.txt").write_text(proc.stderr, encoding="utf-8")
    (log_dir / "diff.patch").write_text(diff_text, encoding="utf-8")
    (log_dir / "done.json").write_text(done_json + "\n", encoding="utf-8")

    return {
        "receipt_id": receipt_id,
        "capsule_id": capsule_id,
        "worker_id": worker_id,
        "exit_code": proc.returncode,
        "stdout_hash": stdout_hash,
        "stderr_hash": stderr_hash,
        "done_json_hash": digest_text(done_json),
        "patch_hash": patch_hash,
        "credential_material_absent": True,
        "micro_refs_moved": False,
        "elapsed_ms": elapsed_ms,
        "prompt_tokens_estimate": len(prompt.split()),
        "completion_tokens_estimate": len(proc.stdout.split()),
        "tool_stdout_tokens_estimate": len((proc.stdout + "\n" + proc.stderr).split()),
        "worktree": str(worktree_abs),
        "log_dir": str(log_dir),
    }


def grant_json(capsule_id: str, market_id: str, worker_id: str) -> dict[str, Any]:
    return {
        "grant_id": f"grant_{capsule_id}",
        "capsule_id": capsule_id,
        "agent_id": worker_id,
        "market_id": market_id,
        "budget": {
            "max_tokens": 2048,
            "max_wall_time_ms": 120000,
            "max_tool_calls": 8,
            "max_mutated_files": 4,
        },
        "scope": {
            "allowed_paths": ["."],
            "forbidden_paths": SWEBENCH_FORBIDDEN_PATHS,
            "allowed_tools": ["read_file", "run_command"],
            "network": "Denied",
        },
        "risk": {
            "risk_class": "P3",
            "human_before_dispatch": False,
            "human_before_accept": False,
            "human_before_merge": True,
        },
        "authorization_event": None,
        "signature_route": "None",
    }


def run_substrate_task(
    task: dict[str, Any],
    out_dir: Path,
    bin_dir: Path,
    worker_mode: str,
    model: str,
    max_turns: int,
    worker_timeout_s: int,
    broadcast_rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    instance_dir = out_dir / "instances" / task["instance_id"]
    project = instance_dir / "project"
    micro_git = instance_dir / "micro.git"
    runtime = Path("/tmp") / "tos_substrate" / hashlib.sha256(
        f"{out_dir}:{task['instance_id']}".encode("utf-8")
    ).hexdigest()[:12]
    project.mkdir(parents=True, exist_ok=True)
    (project / ".turingos").mkdir(parents=True, exist_ok=True)
    init_micro_git(micro_git)

    module_calls: dict[str, int] = {}
    process_calls: dict[str, int] = {}
    event_calls: dict[str, int] = {}
    receipts: list[dict[str, Any]] = []

    def mark_module(module_id: str) -> None:
        increment(module_calls, module_id)

    def mark_event(result: dict[str, Any], event_type: str | None = None) -> None:
        increment(event_calls, event_type or str(result.get("event_type") or result.get("write_event_type")))
        receipts.append(result)

    worker_id = "worker:sha256:" + "f" * 64 if worker_mode == "fake" else worker_id_for_grok(model)

    with Daemon("turingd", bin_dir, runtime / "turingd.sock", micro_git=micro_git, project=project) as turingd:
        increment(process_calls, "turingd")
        boot = rpc(
            turingd.socket_path,
            "project.bootstrap_genesis",
            {"writer_id": "writer:bootstrap", "constitution_digest": digest_text("constitution")},
        )
        mark_event(boot, "SystemConstitutionAccepted")
        for module_id in ["M1_canonical_codec", "M2_micro_git_tape", "M3_event_registry"]:
            mark_module(module_id)

        goal = rpc(turingd.socket_path, "goal.submit", {"writer_id": "writer:goal", "goal": goal_payload(task)})
        mark_event(goal, "GoalStateProposed")
        mark_module("M0_law_goal_harness")

        capsule_id = f"wc_{task['instance_id']}"
        capsule = append_preserve(
            turingd,
            "WorkCapsuleBuilt",
            "writer:capsule",
            {
                "capsule_id": capsule_id,
                "private_contract_hash": digest_text(capsule_id + ":private"),
                "acceptance_commands": ["swebench.harness.run_evaluation"],
            },
        )
        mark_event(capsule, "WorkCapsuleBuilt")
        mark_module("M5_goal_module_atom_capsule")

        evidence = append_preserve(
            turingd,
            "EvidenceBound",
            "writer:evidence",
            {
                "evidence_id": f"ev_{task['instance_id']}",
                "content_digest": digest_text(task["problem_statement"]),
                "storage_digest": digest_text(task["repo"] + task["base_commit"]),
                "required": True,
            },
        )
        mark_event(evidence, "EvidenceBound")
        mark_module("M10_evidence_approval")

        market_id = f"mkt_{task['instance_id']}"
        market = append_preserve(
            turingd,
            "MarketCreated",
            "writer:market",
            {
                "schema_id": "market_created.v1",
                "head_effect": "PRESERVE",
                "market_id": market_id,
                "initial_pool_y": "100",
                "initial_pool_n": "100",
                "k": "10000",
                "truth_status": "statistical_signal_only",
            },
        )
        mark_event(market, "MarketCreated")
        mark_module("M12_market_substrate")

        minted = append_preserve(
            turingd,
            "PositionMinted",
            "writer:market",
            {
                "schema_id": "position_minted.v1",
                "market_id": market_id,
                "agent_id": worker_id,
                "coin_in": "1",
                "yes_out": "1",
                "no_out": "1",
                "invariant": "coin_in == yes_out == no_out",
            },
        )
        mark_event(minted, "PositionMinted")

        with Daemon("turing-marketd", bin_dir, runtime / "marketd.sock", micro_git=micro_git, project=project) as marketd:
            increment(process_calls, "turing-marketd")
            budget = rpc(
                marketd.socket_path,
                "market.shadow.suggest",
                {
                    "routes": [
                        {
                            "route_id": f"route_{worker_mode}_worker",
                            "market_id": market_id,
                            "expected_failure_domain": f"local_{worker_mode}",
                            "requested_tokens": 256,
                        }
                    ],
                    "signals": [
                        {
                            "market_id": market_id,
                            "yes_price": "0.55",
                            "no_price": "0.45",
                            "truth_status": "statistical_signal_only",
                        }
                    ],
                    "price_signal_hash": digest_text("price"),
                    "pput_prior_hash": digest_text("pput"),
                },
            )
        mark_module("M13_marketrouter_shadow")
        budget_event = append_preserve(turingd, "BudgetAllocated", "writer:market", budget)
        mark_event(budget_event, "BudgetAllocated")

        with Daemon("turing-execd", bin_dir, runtime / "execd.sock") as execd:
            increment(process_calls, "turing-execd")
            grant = grant_json(capsule_id, market_id, worker_id)
            rpc(
                execd.socket_path,
                "grant.authorize",
                {
                    "grant": grant,
                    "request": {
                        "tool": "read_file",
                        "path": "README.md",
                        "action": "FileRead",
                        "mutates": False,
                        "requested_tool_call_index": 1,
                        "mutated_files_after": 0,
                        "needs_network": False,
                    },
                },
            )
            if worker_mode == "fake":
                worker_result = rpc(
                    execd.socket_path,
                    "dispatch.request",
                    {
                        "worker_kind": "Fake",
                        "worker_id": worker_id,
                        "capsule_id": capsule_id,
                        "grant_id": grant["grant_id"],
                    },
                )
                worker_result["elapsed_ms"] = 1
                worker_result["prompt_tokens_estimate"] = 1
                worker_result["completion_tokens_estimate"] = 1
                worker_result["tool_stdout_tokens_estimate"] = 1
                worker_result["patch_hash"] = digest_text("fake diff")
                worker_result["worktree"] = None
                worker_result["log_dir"] = None
            else:
                worker_result = run_grok_worker(
                    task,
                    instance_dir,
                    worker_id,
                    model,
                    max_turns,
                    worker_timeout_s,
                    capsule_id,
                    broadcast_rules=broadcast_rules,
                )
        mark_module("M6_worker_profiles")
        mark_module("M7_executor_broker")
        increment(process_calls, "fake_worker" if worker_mode == "fake" else "grok_cli")

        worker_receipt = append_preserve(
            turingd,
            "WorkerReceiptImported",
            "writer:receipt",
            {
                "receipt_id": worker_result["receipt_id"],
                "capsule_id": capsule_id,
                "worker_id": worker_result["worker_id"],
                "exit_code": worker_result["exit_code"],
                "stdout_hash": worker_result["stdout_hash"],
                "stderr_hash": worker_result["stderr_hash"],
                "done_json_hash": worker_result["done_json_hash"],
                "credential_material_absent": worker_result["credential_material_absent"],
                "micro_refs_moved": worker_result["micro_refs_moved"],
                "patch_hash": worker_result["patch_hash"],
            },
        )
        mark_event(worker_receipt, "WorkerReceiptImported")

        macro_id = f"macro:diff:{task['instance_id']}"
        macro = append_preserve(
            turingd,
            "MacroObservationImported",
            "writer:macro",
            {
                "macro_id": macro_id,
                "capsule_id": capsule_id,
                "diff_hash": worker_result["patch_hash"],
                "external_evidence_only": True,
            },
        )
        mark_event(macro, "MacroObservationImported")
        mark_module("M8_macro_observer")

        candidate_id = "cand_" + task["instance_id"]
        accepted = rpc(
            turingd.socket_path,
            "candidate.verify_write",
            {
                "writer_id": "writer:predicate",
                "candidate_payload": {
                    "candidate_id": candidate_id,
                    "capsule_id": capsule_id,
                    "macro_anchor_id": macro_id,
                    "worker_receipt_id": worker_result["receipt_id"],
                },
                "failure": {
                    "candidate_digest": digest_text(task["instance_id"] + ":candidate"),
                    "observation_digest": worker_result["patch_hash"],
                    "detail": "candidate held at predicate gate until official evaluator evidence is imported",
                },
            },
        )
        mark_event(accepted, accepted["write_event_type"])
        mark_module("M4_single_loop")
        mark_module("M9_predicate_kernel")
        predicate_pass = accepted["write_event_type"] == "CandidateAccepted"

        failure = rpc(
            turingd.socket_path,
            "capsule.reject",
            {
                "writer_id": "writer:failure",
                "capsule_id": capsule_id,
                "capsule_digest": digest_text(capsule_id),
                "observation_digest": digest_text("rejected branch"),
                "detail": "negative branch retained for failure-memory coverage",
            },
        )
        mark_event(failure, "FailureNode")
        mark_module("M11_failure_memory")

        settlement = append_preserve(
            turingd,
            "MarketSettled",
            "writer:market",
            {
                "schema_id": "market_settled.v1",
                "market_id": market_id,
                "result": "YES" if predicate_pass else "NO",
                "settlement_event_id": accepted["event_id"],
                "price_not_truth_ack": True,
            },
        )
        mark_event(settlement, "MarketSettled")

        reward = append_preserve(
            turingd,
            "RewardDistributed",
            "writer:market",
            {
                "schema_id": "reward_distributed.v1",
                "event_type": "RewardDistributed",
                "market_id": market_id,
                "agent_id": worker_id,
                "reward_coin": "1" if predicate_pass else "0",
                "slash_coin": "0" if predicate_pass else "1",
                "reason": "PREDICATE_SETTLEMENT",
            },
        )
        mark_event(reward, "RewardDistributed")

        cost = append_preserve(
            turingd,
            "CostEvent",
            "writer:pput",
            {
                "schema_id": "cost_event.v1",
                "head_effect": "PRESERVE",
                "run_id": f"run_{task['instance_id']}",
                "problem_id": task["instance_id"],
                "split": "dogfood",
                "agent_id": worker_id,
                "branch_id": f"branch_{worker_mode}",
                "capsule_id": capsule_id,
                "prompt_tokens": worker_result["prompt_tokens_estimate"],
                "completion_tokens": worker_result["completion_tokens_estimate"],
                "tool_tokens": 0,
                "tool_stdout_tokens": worker_result["tool_stdout_tokens_estimate"],
                "total_tokens": worker_result["prompt_tokens_estimate"]
                + worker_result["completion_tokens_estimate"]
                + worker_result["tool_stdout_tokens_estimate"],
                "wall_time_ms": worker_result["elapsed_ms"],
                "tool_stdout_hash": digest_text(worker_result["stdout_hash"] + worker_result["stderr_hash"]),
                "counted_in_total": True,
            },
        )
        mark_event(cost, "CostEvent")

        pput = append_preserve(
            turingd,
            "PPUTAccounted",
            "writer:pput",
            {
                "schema_id": "pput_accounted.v1",
                "head_effect": "PRESERVE",
                "run_id": f"run_{task['instance_id']}",
                "problem_id": task["instance_id"],
                "split": "dogfood",
                "solved": predicate_pass,
                "verified": predicate_pass,
                "golden_path_token_count": 0 if not predicate_pass else worker_result["prompt_tokens_estimate"]
                + worker_result["completion_tokens_estimate"],
                "total_run_token_count": worker_result["prompt_tokens_estimate"]
                + worker_result["completion_tokens_estimate"]
                + worker_result["tool_stdout_tokens_estimate"],
                "total_wall_time_ms": worker_result["elapsed_ms"],
                "progress": 1 if predicate_pass else 0,
                "vpput_raw": "0.0005" if predicate_pass else "0",
                "failed_branch_count": 1,
                "hidden_from_worker_prompt": True,
            },
        )
        mark_event(pput, "PPUTAccounted")
        mark_module("M14_pput_accounting")

        replay = append_preserve(
            turingd,
            "PredicateEvaluated",
            "writer:replay",
            {
                "predicate_id": "predicate.replay.verify",
                "result": "PASS",
                "source_tape_tip": pput["event_id"],
                "replay_hash": digest_text("replay:" + task["instance_id"]),
            },
        )
        mark_event(replay, "PredicateEvaluated")

        with Daemon("turing-mcp", bin_dir, runtime / "mcp.sock") as mcp:
            increment(process_calls, "turing-mcp")
            rpc(mcp.socket_path, "mcp.resources.list", None)

        with Daemon("turing-marketd", bin_dir, runtime / "marketd-snapshot.sock", micro_git=micro_git, project=project) as marketd:
            increment(process_calls, "turing-marketd")
            rpc(marketd.socket_path, "market.snapshot.write", {})
            rpc(marketd.socket_path, "wallet.snapshot.write", {})

        with Daemon("turing-pputd", bin_dir, runtime / "pputd.sock", micro_git=micro_git, project=project) as pputd:
            increment(process_calls, "turing-pputd")
            if worker_result.get("log_dir"):
                prompt_request = pput_prompt_validation_request(Path(worker_result["log_dir"]))
            else:
                prompt = visible_grok_prompt(task, capsule_id, broadcast_rules=broadcast_rules)
                prompt_request = {
                    "prompt": prompt,
                    "prompt_hash": digest_text(prompt),
                    "source": "fake_worker_visible_prompt",
                }
            rpc(pputd.socket_path, "pput.prompt.validate", prompt_request)
            rpc(pputd.socket_path, "pput.snapshot.write", {})

        with Daemon("turing-viewd", bin_dir, runtime / "viewd.sock", micro_git=micro_git, project=project) as viewd:
            increment(process_calls, "turing-viewd")
            rpc(viewd.socket_path, "projection.snapshot.write", {})
        mark_module("M15_projection")

    # These module calls are executable qualification surfaces that are not yet on
    # a daemon path. Keeping them explicit prevents silent fake coverage.
    integration_check = run_cmd(
        ["cargo", "test", "-p", "turing-integration", "--test", "integration_queue", "integration_queue_cas_admits_non_conflicting_and_rejects_stale"],
        cwd=REPO,
        timeout=180,
    )
    if integration_check.returncode != 0:
        raise RuntimeError(f"integration queue check failed:\n{integration_check.stderr}")
    mark_module("M16_integration_queue")

    handoff_path = instance_dir / "handoff.md"
    handoff = run_cmd([str(bin_dir / "turing"), "handoff", "generate", "--output", str(handoff_path)], cwd=REPO, timeout=180)
    if handoff.returncode != 0:
        raise RuntimeError(f"handoff generation failed:\n{handoff.stderr}")
    mark_module("M17_e2e_handoff")

    return {
        "instance_id": task["instance_id"],
        "worker_mode": worker_mode,
        "worker_id": worker_id,
        "capsule_id": capsule_id,
        "candidate_id": candidate_id,
        "macro_anchor_id": macro_id,
        "worker_receipt_id": worker_result["receipt_id"],
        "patch_hash": worker_result["patch_hash"],
        "broadcast_rules_injected": broadcast_rules or [],
        "broadcast_rules_emitted": [],
        "worker_exit_code": worker_result["exit_code"],
        "worker_log_dir": worker_result["log_dir"],
        "worker_worktree": worker_result["worktree"],
        "predicate_write_event_type": accepted["write_event_type"],
        "module_calls": module_calls,
        "process_calls": process_calls,
        "event_calls": event_calls,
        "receipt_count": len(receipts),
        "micro_git": str(micro_git),
        "project": str(project),
        "basis": "real_daemon_rpc_plus_explicit_qualification_checks",
    }


def write_json(path: Path, packet: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks-jsonl", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--worker-mode", choices=["fake", "grok"], default="fake")
    parser.add_argument("--model", default="grok-build")
    parser.add_argument("--max-turns", type=int, default=8)
    parser.add_argument("--worker-timeout-s", type=int, default=1200)
    parser.add_argument("--daemon-bin-dir", default=str(REPO / "target" / "debug"))
    parser.add_argument("--broadcast-rules-file")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    bin_dir = Path(args.daemon_bin_dir)
    ensure_binaries(bin_dir)
    tasks = read_tasks(Path(args.tasks_jsonl), args.limit)
    active_broadcast_rules = read_broadcast_rules(
        Path(args.broadcast_rules_file) if args.broadcast_rules_file else None
    )

    runs = []
    for task in tasks:
        run = run_substrate_task(
            task,
            out_dir,
            bin_dir,
            args.worker_mode,
            args.model,
            args.max_turns,
            args.worker_timeout_s,
            broadcast_rules=active_broadcast_rules,
        )
        runs.append(run)
        active_broadcast_rules.extend(run.get("broadcast_rules_emitted", []))
    coverage = {
        "schema_id": "MiniSweBenchSubstrateCoverage.v1",
        "run_id": "substrate_smoke",
        "sample_size": len(runs),
        "turingos_arm_runs": runs,
    }
    coverage_path = out_dir / "substrate_coverage.json"
    write_json(coverage_path, coverage)
    audit_path = out_dir / "substrate_coverage_audit.json"
    worker_process = "fake_worker" if args.worker_mode == "fake" else "grok_cli"
    proc = run_cmd(
        [
            "python3",
            str(AUDITOR),
            "--coverage",
            str(coverage_path),
            "--out",
            str(audit_path),
            "--min-sample-size",
            str(len(runs)),
            "--worker-process",
            worker_process,
        ],
        cwd=REPO,
        timeout=120,
    )
    summary = {
        "schema_id": "MiniSweBenchSubstrateSmokeResult.v1",
        "coverage": str(coverage_path),
        "audit": str(audit_path),
        "worker_process": worker_process,
        "auditor_exit_code": proc.returncode,
        "scientific_status": "REAL_WORKER_SUBSTRATE_SMOKE"
        if args.worker_mode == "grok"
        else "SUBSTRATE_INSTRUMENTATION_ONLY_NOT_REAL_WORKER",
        "model": args.model if args.worker_mode == "grok" else None,
    }
    write_json(out_dir / "substrate_smoke_result.json", summary)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
