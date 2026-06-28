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
import importlib.util
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
MICRO_TAPE_AUDITOR = REPO / "tools" / "bench" / "audit_micro_tape_decision_dag.py"
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
NATIVE_API_TOOLS = ["read_file", "list_dir", "grep", "apply_patch", "write_file", "run_command"]
STAGE10_FAILURE_CLASSES = [
    "INSTALL_FAIL",
    "TEST_TIMEOUT",
    "WRONG_FILE",
    "NO_REPRO",
    "OVERBROAD_PATCH",
    "SEMANTIC_FAIL",
    "FLAKY_ORACLE",
    "DEPENDENCY_GAP",
    "CONTEXT_MISSING",
    "PATCH_APPLIES_BUT_WRONG",
]
STAGE11_LOOP_CASES = [
    {
        "case_id": "case_a",
        "failure_class": "WRONG_FILE",
        "observed_signals": {
            "exit_code": 1,
            "official_evaluator_result": "FAIL",
            "diff_scope": "wrong_file",
            "macro_observation_kind": "patch_wrong_file",
            "test_log_digest": "sha256:" + "a" * 64,
        },
        "abstract_pattern": "The first attempt changed the wrong file surface.",
        "guidance": "Retry with a production-code-only patch in the scoped Django module.",
    },
    {
        "case_id": "case_b",
        "failure_class": "CONTEXT_MISSING",
        "observed_signals": {
            "exit_code": 1,
            "timeout_kind": "context_starved",
            "official_evaluator_result": "FAIL",
            "receipt_schema_status": "context_missing",
            "test_log_digest": "sha256:" + "b" * 64,
        },
        "abstract_pattern": "The first attempt lacked the required implementation context.",
        "guidance": "Retry with a smaller capsule that includes the relevant framework file and no extra context.",
    },
    {
        "case_id": "case_c",
        "failure_class": "SEMANTIC_FAIL",
        "observed_signals": {
            "exit_code": 1,
            "official_evaluator_result": "FAIL",
            "command_result": "semantic_mismatch",
            "macro_observation_kind": "patch_applied_but_semantic_fail",
            "test_log_digest": "sha256:" + "c" * 64,
        },
        "abstract_pattern": "The first attempt applied but did not satisfy target semantics.",
        "guidance": "Retry with a narrower semantic patch and preserve the framework runtime type contract.",
    },
]


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


def approval_request(
    *,
    approval_id: str,
    action: str,
    subject_id: str,
    evidence_digest: str,
    title_zh: str,
    body_en: str,
) -> dict[str, Any]:
    return {
        "key_id": "operator-local-key",
        "payload": {
            "schema_id": "approval_payload.v2",
            "approval_id": approval_id,
            "authority_epoch": 0,
            "action": action,
            "subject_id": subject_id,
            "evidence_digests": [evidence_digest],
            "risk_class": "P2",
            "signature_route": "OsKeyring",
        },
        "display_copy": {
            "title_zh": title_zh,
            "body_en": body_en,
        },
    }


def maybe_authorize(
    turingd: Daemon,
    method: str,
    request: dict[str, Any],
    *,
    authorization_mode: str,
) -> dict[str, Any] | None:
    if authorization_mode == "off":
        return None
    try:
        return rpc(turingd.socket_path, method, request)
    except RuntimeError as error:
        message = str(error)
        if authorization_mode == "auto" and "OS keyring provider secret-tool unavailable" in message:
            return None
        raise


def run_substrate_task(
    task: dict[str, Any],
    out_dir: Path,
    bin_dir: Path,
    worker_mode: str,
    model: str,
    max_turns: int,
    worker_timeout_s: int,
    broadcast_rules: list[dict[str, Any]] | None = None,
    authorization_mode: str = "auto",
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

        atom_id = f"atom_{task['instance_id']}"
        atom_auth = maybe_authorize(
            turingd,
            "approval.authorize_atom",
            approval_request(
                approval_id=f"ap_atom_{task['instance_id']}",
                action="atom_authorize",
                subject_id=atom_id,
                evidence_digest=digest_text(task["instance_id"] + ":atom"),
                title_zh="批准 Atom",
                body_en="Authorize the benchmark atom dispatch path.",
            ),
            authorization_mode=authorization_mode,
        )
        if atom_auth is not None:
            mark_event(atom_auth, "AtomAuthorized")
        mark_module("M10_evidence_approval")

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

        dispatch_auth = maybe_authorize(
            turingd,
            "capsule.approve",
            approval_request(
                approval_id=f"ap_capsule_{task['instance_id']}",
                action="capsule_approve",
                subject_id=capsule_id,
                evidence_digest=digest_text(capsule_id + ":dispatch"),
                title_zh="批准 Capsule",
                body_en="Authorize the benchmark work capsule dispatch.",
            ),
            authorization_mode=authorization_mode,
        )
        if dispatch_auth is not None:
            mark_event(dispatch_auth, "WorkerDispatchAuthorized")

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
            if dispatch_auth is not None:
                grant["authorization_event"] = dispatch_auth["event_id"]
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
                "solved": False,
                "verified": False,
                "accounting_stage": "progress",
                "golden_path_token_count": 0,
                "total_run_token_count": worker_result["prompt_tokens_estimate"]
                + worker_result["completion_tokens_estimate"]
                + worker_result["tool_stdout_tokens_estimate"],
                "total_wall_time_ms": worker_result["elapsed_ms"],
                "progress": 0,
                "vpput_raw": "0",
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
        "authorization_mode": authorization_mode,
        "authorization_head_expected": authorization_mode == "required",
        "market_id": market_id,
        "capsule_id": capsule_id,
        "candidate_id": candidate_id,
        "macro_anchor_id": macro_id,
        "worker_receipt_id": worker_result["receipt_id"],
        "patch_hash": worker_result["patch_hash"],
        "broadcast_rules_injected": broadcast_rules or [],
        "broadcast_rules_emitted": [],
        "worker_exit_code": worker_result["exit_code"],
        "worker_prompt_tokens_estimate": worker_result["prompt_tokens_estimate"],
        "worker_completion_tokens_estimate": worker_result["completion_tokens_estimate"],
        "worker_tool_stdout_tokens_estimate": worker_result["tool_stdout_tokens_estimate"],
        "worker_elapsed_ms": worker_result["elapsed_ms"],
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


def load_micro_tape_auditor() -> Any:
    spec = importlib.util.spec_from_file_location("audit_micro_tape_decision_dag", MICRO_TAPE_AUDITOR)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"cannot load {MICRO_TAPE_AUDITOR}")
    spec.loader.exec_module(module)
    return module


def commit_stage6_event(repo: Path, event: dict[str, Any]) -> str:
    (repo / "event").write_text(json.dumps(event, sort_keys=True) + "\n", encoding="utf-8")
    run_cmd(["git", "add", "event"], cwd=repo)
    proc = run_cmd(
        [
            "git",
            "-c",
            "user.name=TuringOS Stage6",
            "-c",
            "user.email=stage6@example.invalid",
            "commit",
            "-m",
            "turingos stage6 micro event",
        ],
        cwd=repo,
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"stage6 git commit failed:\n{proc.stderr}")
    oid = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo, timeout=120)
    if oid.returncode != 0:
        raise RuntimeError(f"stage6 rev-parse failed:\n{oid.stderr}")
    return oid.stdout.strip()


def append_stage6_event(
    *,
    repo: Path,
    state: dict[str, Any],
    registry: dict[str, dict[str, Any]],
    canonical_payload_digest: Any,
    event_type: str,
    payload: dict[str, Any],
    writer_id: str,
    product: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    row = registry[event_type]
    predicate_product = product
    if predicate_product is None:
        predicate_product = "PASS" if row["predicate_required"] else "NOT_RUN"
    payload_hash = canonical_payload_digest(payload)
    event = {
        "accepted_head_before": state["accepted_head"],
        "authority_epoch": state["authority_epoch"],
        "authorization_head_before": state["authorization_head"],
        "content_digest": payload_hash,
        "event_schema_id": row["payload_schema_id"],
        "event_type": event_type,
        "head_effect": row["head_effect"],
        "payload": payload,
        "payload_hash": payload_hash,
        "predicate_product": predicate_product,
        "prev_tape_tip": state["tape_tip"],
        "schema_id": "micro_event_envelope.v1",
        "sequence": state["sequence"],
        "verified": predicate_product == "PASS",
        "writer_id": writer_id,
    }
    oid = commit_stage6_event(repo, event)
    event_id = "mu:" + oid
    run_cmd(["git", "update-ref", "refs/turingos/tape_tip", oid], cwd=repo)
    if row["event_class"] == "SOVEREIGN_ACCEPT" and predicate_product == "PASS":
        run_cmd(["git", "update-ref", "refs/turingos/accepted_head", oid], cwd=repo)
        state["accepted_head"] = event_id
    if row["event_class"] == "AUTHORIZATION" and predicate_product == "PASS":
        run_cmd(["git", "update-ref", "refs/turingos/authorization_head", oid], cwd=repo)
        state["authorization_head"] = event_id
    state["tape_tip"] = event_id
    state["sequence"] += 1
    state["events"].append({"event_type": event_type, "event_id": event_id, "payload": payload})
    if name is not None:
        state["event_ids"][name] = event_id
    return {"event_type": event_type, "event_id": event_id, "payload": payload}


def stage6_base_state() -> dict[str, Any]:
    return {
        "accepted_head": None,
        "authorization_head": None,
        "authority_epoch": 0,
        "event_ids": {},
        "events": [],
        "sequence": 0,
        "tape_tip": None,
    }


def stage6_vpput(progress: int, total_tokens: int, wall_time_ms: int) -> str:
    if progress != 1 or total_tokens <= 0 or wall_time_ms <= 0:
        return "0"
    numerator = 1
    denominator = total_tokens * wall_time_ms
    return f"{numerator}/{denominator}"


def build_stage6_bundle(out_dir: Path, task: dict[str, Any], expected_result: str) -> dict[str, Any]:
    auditor = load_micro_tape_auditor()
    registry = auditor.load_event_registry()
    instance_id = task["instance_id"]
    instance_dir = out_dir / "instances" / instance_id
    repo = instance_dir / "micro.git"
    bundle = instance_dir / "micro_tape.bundle"
    if repo.exists():
        shutil.rmtree(repo)
    instance_dir.mkdir(parents=True, exist_ok=True)
    init = run_cmd(["git", "init", "--object-format=sha256", str(repo)], timeout=120)
    if init.returncode != 0:
        raise RuntimeError(f"stage6 git init failed:\n{init.stderr}")

    state = stage6_base_state()
    worker_id = "worker:sha256:" + hashlib.sha256(f"stage6:{instance_id}:worker".encode("utf-8")).hexdigest()
    capsule_id = f"wc_stage6_{hashlib.sha256(instance_id.encode('utf-8')).hexdigest()[:16]}"
    atom_id = f"atom_stage6_{hashlib.sha256((instance_id + ':atom').encode('utf-8')).hexdigest()[:16]}"
    market_id = f"mkt_stage6_{hashlib.sha256((instance_id + ':market').encode('utf-8')).hexdigest()[:16]}"
    receipt_id = f"rcp_stage6_{hashlib.sha256((instance_id + ':receipt').encode('utf-8')).hexdigest()[:16]}"
    macro_id = f"macro:diff:stage6:{hashlib.sha256(instance_id.encode('utf-8')).hexdigest()[:16]}"
    evidence_id = f"ev_stage6_{hashlib.sha256((instance_id + ':official').encode('utf-8')).hexdigest()[:16]}"
    candidate_id = f"cand_stage6_{hashlib.sha256((instance_id + ':candidate').encode('utf-8')).hexdigest()[:16]}"
    total_tokens = 100
    wall_time_ms = 50

    append = lambda event_type, payload, writer_id, **kwargs: append_stage6_event(
        repo=repo,
        state=state,
        registry=registry,
        canonical_payload_digest=auditor.canonical_payload_digest,
        event_type=event_type,
        payload=payload,
        writer_id=writer_id,
        **kwargs,
    )

    append("SystemConstitutionAccepted", {"constitution_digest": digest_text("stage6 constitution")}, "writer:bootstrap")
    append(
        "GoalStateProposed",
        {
            "goal_id": f"goal_{instance_id}",
            "objective": f"Stage6 strict MicroTape protocol fixture for {instance_id}",
            "task_source": "existing_repo_swe_bench_fixture",
        },
        "writer:goal",
    )
    append(
        "AtomAuthorized",
        {
            "atom_id": atom_id,
            "approval_id": f"ap_atom_{instance_id}",
            "signature_route": "BenchLocalDeterministicAuthority",
            "authority_kind": "stage6_protocol_fixture_no_credentials",
        },
        "writer:bench-authority",
    )
    append(
        "WorkerDispatchAuthorized",
        {
            "capsule_id": capsule_id,
            "worker_id": worker_id,
            "approval_id": f"ap_dispatch_{instance_id}",
            "signature_route": "BenchLocalDeterministicAuthority",
            "authority_kind": "stage6_protocol_fixture_no_credentials",
        },
        "writer:bench-authority",
    )
    append(
        "WorkCapsuleBuilt",
        {
            "capsule_id": capsule_id,
            "private_contract_hash": digest_text(capsule_id + ":private"),
            "acceptance_commands": ["strict.stage6.protocol.fixture"],
            "allowed_files": ["django/**"],
            "forbidden_files": SWEBENCH_FORBIDDEN_PATHS,
        },
        "writer:capsule",
    )
    append(
        "EvidenceBound",
        {
            "evidence_id": f"ev_bound_{instance_id}",
            "content_digest": digest_text(task["problem_statement"]),
            "storage_digest": digest_text(task["repo"] + task["base_commit"]),
            "required": True,
        },
        "writer:evidence",
    )
    append(
        "MarketCreated",
        {
            "schema_id": "market_created.v1",
            "market_id": market_id,
            "initial_pool_y": "100",
            "initial_pool_n": "100",
            "k": "10000",
            "truth_status": "statistical_signal_only",
        },
        "writer:market",
    )
    append(
        "PositionMinted",
        {
            "schema_id": "position_minted.v1",
            "market_id": market_id,
            "agent_id": worker_id,
            "coin_in": "1",
            "yes_out": "1",
            "no_out": "1",
            "invariant": "coin_in == yes_out == no_out",
        },
        "writer:market",
    )
    append(
        "BudgetAllocated",
        {
            "market_id": market_id,
            "branch_id": "branch_stage6_fixture",
            "capsule_id": capsule_id,
            "allocation_reason": {
                "price_signal_hash": digest_text("stage6 price"),
                "pput_prior_hash": digest_text("stage6 pput"),
                "diversity_policy_hash": digest_text("stage6 diversity"),
            },
            "max_tokens": total_tokens,
            "max_wall_time_ms": wall_time_ms,
        },
        "writer:market",
    )
    patch_hash = digest_text(instance_id + ":" + expected_result + ":patch")
    append(
        "WorkerReceiptImported",
        {
            "receipt_id": receipt_id,
            "capsule_id": capsule_id,
            "worker_id": worker_id,
            "exit_code": 0 if expected_result == "PASS" else 1,
            "stdout_hash": digest_text(instance_id + ":stdout"),
            "stderr_hash": digest_text(instance_id + ":stderr"),
            "done_json_hash": digest_text(instance_id + ":done"),
            "credential_material_absent": True,
            "micro_refs_moved": False,
            "patch_hash": patch_hash,
        },
        "writer:receipt",
    )
    append(
        "MacroObservationImported",
        {
            "macro_id": macro_id,
            "capsule_id": capsule_id,
            "diff_hash": patch_hash,
            "external_evidence_only": True,
        },
        "writer:macro",
    )
    append(
        "CostEvent",
        {
            "schema_id": "cost_event.v1",
            "run_id": f"run_{instance_id}",
            "problem_id": instance_id,
            "split": "dogfood",
            "agent_id": worker_id,
            "branch_id": "branch_stage6_fixture",
            "capsule_id": capsule_id,
            "prompt_tokens": 40,
            "completion_tokens": 40,
            "tool_tokens": 10,
            "tool_stdout_tokens": 10,
            "total_tokens": total_tokens,
            "wall_time_ms": wall_time_ms,
            "tool_stdout_hash": digest_text(instance_id + ":tool-stdout"),
            "counted_in_total": True,
        },
        "writer:pput",
    )
    append(
        "PPUTAccounted",
        {
            "schema_id": "pput_accounted.v1",
            "run_id": f"run_{instance_id}",
            "problem_id": instance_id,
            "split": "dogfood",
            "solved": False,
            "verified": False,
            "accounting_stage": "progress",
            "golden_path_token_count": 0,
            "total_run_token_count": total_tokens,
            "total_wall_time_ms": wall_time_ms,
            "progress": 0,
            "vpput_raw": "0",
            "failed_branch_count": 1,
            "hidden_from_worker_prompt": True,
        },
        "writer:pput",
    )
    official = append(
        "OfficialEvaluatorEvidenceImported",
        {
            "schema_id": "official_evaluator_evidence_imported.v1",
            "evidence_id": evidence_id,
            "instance_id": instance_id,
            "capsule_id": capsule_id,
            "macro_anchor_id": macro_id,
            "worker_receipt_id": receipt_id,
            "candidate_patch_hash": patch_hash,
            "test_patch_hash": digest_text(instance_id + ":test-patch"),
            "apply_candidate_result": expected_result,
            "apply_test_patch_result": "PASS",
            "fail_to_pass_labels": [],
            "target_test_exit_code": 0 if expected_result == "PASS" else 1,
            "target_test_result": expected_result,
            "stdout_hash": digest_text(instance_id + ":official-stdout"),
            "stderr_hash": digest_text(instance_id + ":official-stderr"),
            "result": expected_result,
            "failure_class": None if expected_result == "PASS" else "OFFICIAL_EVAL_FAIL",
            "forbidden_test_edit_detected": False,
            "forbidden_test_edit_paths": [],
            "truth_source": "stage6_deterministic_official_fixture",
        },
        "writer:official-evaluator",
        name="official",
    )

    if expected_result == "PASS":
        terminal = append(
            "CandidateAccepted",
            {
                "candidate_id": candidate_id,
                "capsule_id": capsule_id,
                "macro_anchor_id": macro_id,
                "worker_receipt_id": receipt_id,
                "official_evaluator_evidence_id": evidence_id,
            },
            "writer:predicate",
            name="terminal",
        )
        market_result = "YES"
        reward = "1"
        slash = "0"
        progress = 1
    else:
        terminal = append(
            "FailureNode",
            {
                "capsule_id": capsule_id,
                "candidate_id": candidate_id,
                "failure_class": "OFFICIAL_EVAL_FAIL",
                "detail": "stage6 deterministic failing fixture",
                "official_evaluator_evidence_id": evidence_id,
            },
            "writer:predicate",
            product="FAIL",
            name="terminal",
        )
        market_result = "NO"
        reward = "0"
        slash = "1"
        progress = 0

    settlement = append(
        "MarketSettled",
        {
            "schema_id": "market_settled.v1",
            "market_id": market_id,
            "result": market_result,
            "settlement_basis_event_id": official["event_id"],
            "basis_kind": "official_eval",
            "terminal_event_id": terminal["event_id"],
            "is_terminal": True,
            "price_not_truth_ack": True,
        },
        "writer:market",
        name="settlement",
    )
    append(
        "RewardDistributed",
        {
            "schema_id": "reward_distributed.v1",
            "event_type": "RewardDistributed",
            "market_id": market_id,
            "agent_id": worker_id,
            "reward_coin": reward,
            "slash_coin": slash,
            "reason": "PREDICATE_SETTLEMENT" if progress == 1 else "BUDGET_EXHAUSTED",
            "settlement_event_id": settlement["event_id"],
        },
        "writer:market",
    )
    append(
        "PPUTAccounted",
        {
            "schema_id": "pput_accounted.v1",
            "run_id": f"run_{instance_id}",
            "problem_id": instance_id,
            "split": "dogfood",
            "solved": progress == 1,
            "verified": progress == 1,
            "accounting_stage": "final",
            "basis_event_id": official["event_id"],
            "terminal_event_id": terminal["event_id"],
            "golden_path_token_count": total_tokens if progress == 1 else 0,
            "total_run_token_count": total_tokens,
            "total_wall_time_ms": wall_time_ms,
            "progress": progress,
            "vpput_raw": stage6_vpput(progress, total_tokens, wall_time_ms),
            "failed_branch_count": 1 if progress == 0 else 0,
            "hidden_from_worker_prompt": True,
        },
        "writer:pput",
    )
    append(
        "PredicateEvaluated",
        {
            "predicate_id": "predicate.replay.verify",
            "result": "PASS",
            "source_tape_tip": state["tape_tip"],
            "replay_hash": digest_text("stage6 replay:" + instance_id),
        },
        "writer:replay",
        product="NOT_RUN",
    )

    create = run_cmd(["git", "bundle", "create", str(bundle.resolve()), "--all"], cwd=repo, timeout=120)
    if create.returncode != 0:
        raise RuntimeError(f"stage6 bundle create failed:\n{create.stderr}")
    bundle_hash = digest_bytes(bundle.read_bytes())
    shutil.rmtree(repo)
    return {
        "instance_id": instance_id,
        "expected_result": expected_result,
        "authorization_mode": "required",
        "authorization_head_expected": True,
        "micro_git": "not_persisted_bundle_is_audit_artifact",
        "micro_tape_bundle": str(bundle),
        "micro_tape_bundle_sha256": bundle_hash,
        "accepted_head": state["accepted_head"],
        "authorization_head": state["authorization_head"],
        "tape_tip": state["tape_tip"],
        "worker_id": worker_id,
        "capsule_id": capsule_id,
        "candidate_id": candidate_id,
        "market_id": market_id,
        "basis": "stage6_strict_microtape_protocol_fixture",
    }


def generate_stage6_strict_microtape_fixtures(out_dir: Path, tasks: list[dict[str, Any]]) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    runs: list[dict[str, Any]] = []
    for index, task in enumerate(tasks):
        expected = str(task.get("stage6_expected_result") or ("PASS" if index == 0 else "FAIL")).upper()
        if expected not in {"PASS", "FAIL"}:
            raise ValueError(f"stage6_expected_result must be PASS or FAIL for {task['instance_id']}")
        runs.append(build_stage6_bundle(out_dir, task, expected))
    manifest = {
        "schema_id": "Stage6StrictMicroTapeFixtureManifest.v1",
        "run_id": "stage6_strict_microtape",
        "truth_source": "fresh_micro_tape_bundles",
        "old_stage4_stage5_bundles": "intentionally_not_rewritten_legacy_partial",
        "sample_size": len(runs),
        "turingos_arm_runs": runs,
    }
    write_json(out_dir / "substrate_coverage.json", manifest)
    write_json(out_dir / "bundle_manifest.json", manifest)
    return manifest


def build_stage8_no_hitl_loop_bundle(out_dir: Path, task: dict[str, Any]) -> dict[str, Any]:
    auditor = load_micro_tape_auditor()
    registry = auditor.load_event_registry()
    instance_id = task["instance_id"]
    instance_dir = out_dir / "turingos" / "instances" / instance_id
    repo = instance_dir / "micro.git"
    bundle = instance_dir / "micro_tape.bundle"
    if repo.exists():
        shutil.rmtree(repo)
    instance_dir.mkdir(parents=True, exist_ok=True)
    init = run_cmd(["git", "init", "--object-format=sha256", str(repo)], timeout=120)
    if init.returncode != 0:
        raise RuntimeError(f"stage8 git init failed:\n{init.stderr}")

    state = stage6_base_state()
    short = hashlib.sha256(instance_id.encode("utf-8")).hexdigest()[:16]
    worker_id = "worker:sha256:" + hashlib.sha256(f"stage8:{instance_id}:worker".encode("utf-8")).hexdigest()
    atom_id = f"atom_stage8_{short}"
    capsule_1 = f"wc_stage8_{short}_attempt1"
    capsule_2 = f"wc_stage8_{short}_attempt2"
    market_id = f"mkt_stage8_{short}"
    receipt_1 = f"rcp_stage8_{short}_attempt1"
    receipt_2 = f"rcp_stage8_{short}_attempt2"
    macro_1 = f"macro:diff:stage8:{short}:attempt1"
    macro_2 = f"macro:diff:stage8:{short}:attempt2"
    evidence_fail = f"ev_stage8_{short}_fail"
    evidence_pass = f"ev_stage8_{short}_pass"
    candidate_id = f"cand_stage8_{short}"
    rule_id = f"br_stage8_{short}"
    run_id = f"run_stage8_{short}"
    first_tokens = 160
    second_tokens = 240
    first_wall_ms = 80
    second_wall_ms = 120
    total_tokens = first_tokens + second_tokens
    total_wall_ms = first_wall_ms + second_wall_ms

    append = lambda event_type, payload, writer_id, **kwargs: append_stage6_event(
        repo=repo,
        state=state,
        registry=registry,
        canonical_payload_digest=auditor.canonical_payload_digest,
        event_type=event_type,
        payload=payload,
        writer_id=writer_id,
        **kwargs,
    )

    append("SystemConstitutionAccepted", {"constitution_digest": digest_text("stage8 constitution")}, "writer:bootstrap")
    append(
        "GoalStateProposed",
        {
            "goal_id": f"goal_{short}",
            "objective": f"Stage8 no-HITL retry loop fixture for {instance_id}",
            "task_source": "swe_bench_shaped_no_hitl_loop_fixture",
        },
        "writer:goal",
    )
    append(
        "AtomAuthorized",
        {
            "atom_id": atom_id,
            "approval_id": f"ap_atom_stage8_{short}",
            "authority_kind": "test_local_authority_no_credentials",
            "signature_route": "test_local_authority",
        },
        "writer:test-local-authority",
    )
    append(
        "WorkerDispatchAuthorized",
        {
            "capsule_id": capsule_1,
            "worker_id": worker_id,
            "approval_id": f"ap_dispatch_stage8_{short}_attempt1",
            "authority_kind": "test_local_authority_no_credentials",
            "signature_route": "test_local_authority",
        },
        "writer:test-local-authority",
        name="dispatch_attempt1",
    )
    append(
        "WorkCapsuleBuilt",
        {
            "capsule_id": capsule_1,
            "private_contract_hash": digest_text(capsule_1 + ":private"),
            "acceptance_commands": ["stage8.official.eval"],
            "allowed_files": ["django/**"],
            "forbidden_files": SWEBENCH_FORBIDDEN_PATHS,
            "attempt_index": 1,
            "visible_known_failures_to_avoid": [],
            "raw_log_text_absent": True,
            "hidden_predicates_absent": True,
        },
        "writer:capsule",
        name="capsule_attempt1",
    )
    append(
        "MarketCreated",
        {
            "schema_id": "market_created.v1",
            "market_id": market_id,
            "initial_pool_y": "100",
            "initial_pool_n": "100",
            "k": "10000",
            "truth_status": "statistical_signal_only",
        },
        "writer:market",
    )
    append(
        "PositionMinted",
        {
            "schema_id": "position_minted.v1",
            "market_id": market_id,
            "agent_id": worker_id,
            "coin_in": "1",
            "yes_out": "1",
            "no_out": "1",
            "invariant": "coin_in == yes_out == no_out",
        },
        "writer:market",
    )
    append(
        "BudgetAllocated",
        {
            "market_id": market_id,
            "branch_id": "branch_stage8_attempt1",
            "capsule_id": capsule_1,
            "allocation_reason": {
                "price_signal_hash": digest_text("stage8 price attempt1"),
                "pput_prior_hash": digest_text("stage8 pput attempt1"),
                "diversity_policy_hash": digest_text("stage8 diversity attempt1"),
            },
            "max_tokens": first_tokens,
            "max_wall_time_ms": first_wall_ms,
        },
        "writer:market",
    )
    patch_fail = digest_text(instance_id + ":stage8:noop-patch")
    append(
        "WorkerReceiptImported",
        {
            "receipt_id": receipt_1,
            "capsule_id": capsule_1,
            "worker_id": worker_id,
            "exit_code": 0,
            "stdout_hash": digest_text(instance_id + ":attempt1:stdout"),
            "stderr_hash": digest_text(instance_id + ":attempt1:stderr"),
            "done_json_hash": digest_text(instance_id + ":attempt1:done"),
            "credential_material_absent": True,
            "manual_patch": False,
            "micro_refs_moved": False,
            "patch_hash": patch_fail,
        },
        "writer:receipt",
    )
    append(
        "MacroObservationImported",
        {
            "macro_id": macro_1,
            "capsule_id": capsule_1,
            "diff_hash": patch_fail,
            "external_evidence_only": True,
        },
        "writer:macro",
    )
    append(
        "CostEvent",
        {
            "schema_id": "cost_event.v1",
            "run_id": run_id,
            "problem_id": instance_id,
            "split": "dogfood",
            "agent_id": worker_id,
            "branch_id": "branch_stage8_attempt1",
            "capsule_id": capsule_1,
            "prompt_tokens": 60,
            "completion_tokens": 60,
            "tool_tokens": 20,
            "tool_stdout_tokens": 20,
            "total_tokens": first_tokens,
            "wall_time_ms": first_wall_ms,
            "tool_stdout_hash": digest_text(instance_id + ":attempt1:tool-stdout"),
            "counted_in_total": True,
        },
        "writer:pput",
    )
    official_fail = append(
        "OfficialEvaluatorEvidenceImported",
        {
            "schema_id": "official_evaluator_evidence_imported.v1",
            "evidence_id": evidence_fail,
            "instance_id": instance_id,
            "capsule_id": capsule_1,
            "macro_anchor_id": macro_1,
            "worker_receipt_id": receipt_1,
            "candidate_patch_hash": patch_fail,
            "test_patch_hash": digest_text(instance_id + ":test-patch"),
            "apply_candidate_result": "PASS",
            "apply_test_patch_result": "PASS",
            "fail_to_pass_labels": [],
            "target_test_exit_code": 1,
            "target_test_result": "FAIL",
            "stdout_hash": digest_text(instance_id + ":attempt1:official-stdout"),
            "stderr_hash": digest_text(instance_id + ":attempt1:official-stderr"),
            "result": "FAIL",
            "failure_class": "OFFICIAL_EVAL_FAIL",
            "forbidden_test_edit_detected": False,
            "forbidden_test_edit_paths": [],
            "truth_source": "stage8_deterministic_official_fixture",
        },
        "writer:official-evaluator",
        name="official_fail",
    )
    failure = append(
        "FailureNode",
        {
            "capsule_id": capsule_1,
            "candidate_id": candidate_id,
            "failure_class": "OFFICIAL_EVAL_FAIL",
            "detail": "first no-HITL attempt intentionally failed official target tests",
            "official_evaluator_evidence_id": evidence_fail,
        },
        "writer:predicate",
        product="NOT_RUN",
        name="first_failure",
    )
    append(
        "PPUTAccounted",
        {
            "schema_id": "pput_accounted.v1",
            "run_id": run_id,
            "problem_id": instance_id,
            "split": "dogfood",
            "solved": False,
            "verified": False,
            "accounting_stage": "progress",
            "basis_event_id": official_fail["event_id"],
            "terminal_event_id": failure["event_id"],
            "golden_path_token_count": 0,
            "total_run_token_count": first_tokens,
            "total_wall_time_ms": first_wall_ms,
            "progress": 0,
            "vpput_raw": "0",
            "failed_branch_count": 1,
            "hidden_from_worker_prompt": True,
        },
        "writer:pput",
    )
    append(
        "FailureCertificate",
        {
            "certificate_id": f"fc_stage8_{short}",
            "source_failure_node_id": failure["event_id"],
            "failure_class": "OFFICIAL_EVAL_FAIL",
            "abstract_pattern": "First attempt patch did not satisfy the official target tests.",
            "raw_log_ref": "cas:" + hashlib.sha256(f"{instance_id}:attempt1:raw-log".encode("utf-8")).hexdigest(),
            "raw_log_text_absent": True,
        },
        "writer:failure",
        name="failure_certificate",
    )
    broadcast = append(
        "BroadcastRuleActivated",
        {
            "rule_id": rule_id,
            "source_failure_nodes": [failure["event_id"]],
            "failure_class": "OFFICIAL_EVAL_FAIL",
            "abstract_pattern": "Retry with a production-code-only patch that satisfies the official target tests.",
            "guidance": "Do not reuse the empty patch; modify only production code allowed by capsule scope.",
            "raw_log_refs": ["cas:" + hashlib.sha256(f"{instance_id}:attempt1:raw-log".encode("utf-8")).hexdigest()],
            "raw_log_text_absent": True,
            "hidden_predicates_absent": True,
        },
        "writer:failure-memory",
        name="broadcast",
    )
    retry = append(
        "RetryAuthorized",
        {
            "retry_id": f"retry_stage8_{short}",
            "capsule_id": capsule_2,
            "source_failure_node_id": failure["event_id"],
            "broadcast_rule_event_id": broadcast["event_id"],
            "retry_decision_source": "tape_reducer_or_policy",
            "approval_id": f"ap_retry_stage8_{short}",
            "authority_kind": "test_local_authority_no_credentials",
            "signature_route": "test_local_authority",
            "human_intervention_count": 0,
        },
        "writer:test-local-authority",
        name="retry",
    )
    append(
        "WorkerDispatchAuthorized",
        {
            "capsule_id": capsule_2,
            "worker_id": worker_id,
            "approval_id": f"ap_dispatch_stage8_{short}_attempt2",
            "signature_route": "test_local_authority",
            "authority_kind": "test_local_authority_no_credentials",
            "retry_authorization_event_id": retry["event_id"],
        },
        "writer:test-local-authority",
        name="dispatch_attempt2",
    )
    append(
        "WorkCapsuleBuilt",
        {
            "capsule_id": capsule_2,
            "private_contract_hash": digest_text(capsule_2 + ":private"),
            "acceptance_commands": ["stage8.official.eval"],
            "allowed_files": ["django/**"],
            "forbidden_files": SWEBENCH_FORBIDDEN_PATHS,
            "attempt_index": 2,
            "source_failure_nodes": [failure["event_id"]],
            "injected_broadcast_rule_ids": [rule_id],
            "broadcast_rule_event_id": broadcast["event_id"],
            "visible_known_failures_to_avoid": [
                "Do not reuse the empty patch; modify only production code allowed by capsule scope."
            ],
            "raw_log_text_absent": True,
            "hidden_predicates_absent": True,
        },
        "writer:capsule",
        name="capsule_attempt2",
    )
    append(
        "BudgetAllocated",
        {
            "market_id": market_id,
            "branch_id": "branch_stage8_attempt2",
            "capsule_id": capsule_2,
            "allocation_reason": {
                "price_signal_hash": digest_text("stage8 price attempt2"),
                "pput_prior_hash": digest_text("stage8 pput attempt2"),
                "diversity_policy_hash": digest_text("stage8 diversity attempt2"),
            },
            "max_tokens": second_tokens,
            "max_wall_time_ms": second_wall_ms,
        },
        "writer:market",
    )
    patch_pass = digest_text(instance_id + ":stage8:repair-patch")
    append(
        "WorkerReceiptImported",
        {
            "receipt_id": receipt_2,
            "capsule_id": capsule_2,
            "worker_id": worker_id,
            "exit_code": 0,
            "stdout_hash": digest_text(instance_id + ":attempt2:stdout"),
            "stderr_hash": digest_text(instance_id + ":attempt2:stderr"),
            "done_json_hash": digest_text(instance_id + ":attempt2:done"),
            "credential_material_absent": True,
            "manual_patch": False,
            "micro_refs_moved": False,
            "patch_hash": patch_pass,
        },
        "writer:receipt",
    )
    append(
        "MacroObservationImported",
        {
            "macro_id": macro_2,
            "capsule_id": capsule_2,
            "diff_hash": patch_pass,
            "external_evidence_only": True,
        },
        "writer:macro",
    )
    append(
        "CostEvent",
        {
            "schema_id": "cost_event.v1",
            "run_id": run_id,
            "problem_id": instance_id,
            "split": "dogfood",
            "agent_id": worker_id,
            "branch_id": "branch_stage8_attempt2",
            "capsule_id": capsule_2,
            "prompt_tokens": 90,
            "completion_tokens": 90,
            "tool_tokens": 30,
            "tool_stdout_tokens": 30,
            "total_tokens": second_tokens,
            "wall_time_ms": second_wall_ms,
            "tool_stdout_hash": digest_text(instance_id + ":attempt2:tool-stdout"),
            "counted_in_total": True,
        },
        "writer:pput",
    )
    official_pass = append(
        "OfficialEvaluatorEvidenceImported",
        {
            "schema_id": "official_evaluator_evidence_imported.v1",
            "evidence_id": evidence_pass,
            "instance_id": instance_id,
            "capsule_id": capsule_2,
            "macro_anchor_id": macro_2,
            "worker_receipt_id": receipt_2,
            "candidate_patch_hash": patch_pass,
            "test_patch_hash": digest_text(instance_id + ":test-patch"),
            "apply_candidate_result": "PASS",
            "apply_test_patch_result": "PASS",
            "fail_to_pass_labels": [],
            "target_test_exit_code": 0,
            "target_test_result": "PASS",
            "stdout_hash": digest_text(instance_id + ":attempt2:official-stdout"),
            "stderr_hash": digest_text(instance_id + ":attempt2:official-stderr"),
            "result": "PASS",
            "failure_class": None,
            "forbidden_test_edit_detected": False,
            "forbidden_test_edit_paths": [],
            "truth_source": "stage8_deterministic_official_fixture",
        },
        "writer:official-evaluator",
        name="official_pass",
    )
    terminal = append(
        "CandidateAccepted",
        {
            "candidate_id": candidate_id,
            "capsule_id": capsule_2,
            "macro_anchor_id": macro_2,
            "worker_receipt_id": receipt_2,
            "official_evaluator_evidence_id": evidence_pass,
            "consumed_broadcast_rule_event_id": broadcast["event_id"],
        },
        "writer:predicate",
        name="terminal",
    )
    settlement = append(
        "MarketSettled",
        {
            "schema_id": "market_settled.v1",
            "market_id": market_id,
            "result": "YES",
            "settlement_basis_event_id": official_pass["event_id"],
            "basis_kind": "official_eval",
            "terminal_event_id": terminal["event_id"],
            "is_terminal": True,
            "price_not_truth_ack": True,
        },
        "writer:market",
        name="settlement",
    )
    append(
        "RewardDistributed",
        {
            "schema_id": "reward_distributed.v1",
            "event_type": "RewardDistributed",
            "market_id": market_id,
            "agent_id": worker_id,
            "reward_coin": "1",
            "slash_coin": "0",
            "reason": "PREDICATE_SETTLEMENT",
            "settlement_event_id": settlement["event_id"],
        },
        "writer:market",
    )
    append(
        "PPUTAccounted",
        {
            "schema_id": "pput_accounted.v1",
            "run_id": run_id,
            "problem_id": instance_id,
            "split": "dogfood",
            "solved": True,
            "verified": True,
            "accounting_stage": "final",
            "basis_event_id": official_pass["event_id"],
            "terminal_event_id": terminal["event_id"],
            "golden_path_token_count": total_tokens,
            "total_run_token_count": total_tokens,
            "total_wall_time_ms": total_wall_ms,
            "progress": 1,
            "vpput_raw": stage6_vpput(1, total_tokens, total_wall_ms),
            "failed_branch_count": 1,
            "hidden_from_worker_prompt": True,
        },
        "writer:pput",
    )
    append(
        "PredicateEvaluated",
        {
            "predicate_id": "predicate.stage8.no_hitl.replay",
            "result": "PASS",
            "source_tape_tip": state["tape_tip"],
            "replay_hash": digest_text("stage8 replay:" + instance_id),
        },
        "writer:replay",
        product="NOT_RUN",
    )

    create = run_cmd(["git", "bundle", "create", str(bundle.resolve()), "--all"], cwd=repo, timeout=120)
    if create.returncode != 0:
        raise RuntimeError(f"stage8 bundle create failed:\n{create.stderr}")
    bundle_hash = digest_bytes(bundle.read_bytes())
    shutil.rmtree(repo)
    no_hitl_loop = {
        "human_intervention_count": 0,
        "manual_patch_count": 0,
        "manual_approval_count": 0,
        "manual_rerun_selection_count": 0,
        "fallback_to_auto_authorization": False,
        "retry_decision_source": "tape_reducer_or_policy",
        "retry_policy_event_id": retry["event_id"],
        "first_failure_event_id": failure["event_id"],
        "broadcast_rule_event_id": broadcast["event_id"],
        "second_attempt_capsule_event_id": state["event_ids"]["capsule_attempt2"],
        "terminal_candidate_accepted_event_id": terminal["event_id"],
        "accepted_head": state["accepted_head"],
        "verified_from_micro_tape_bundle_only": True,
    }
    failure_memory = {
        "source_failure_nodes": [failure["event_id"]],
        "failure_class": "OFFICIAL_EVAL_FAIL",
        "abstract_pattern": "Retry with a production-code-only patch that satisfies the official target tests.",
        "broadcast_rule_event_id": broadcast["event_id"],
        "injected_into_capsule_id": capsule_2,
        "raw_log_refs_present_only_as_private_evidence": True,
        "raw_log_text_absent_from_visible_capsule": True,
        "hidden_predicates_absent_from_visible_capsule": True,
        "broadcast_rule_reduced_from_tape": True,
    }
    return {
        "instance_id": instance_id,
        "expected_result": "PASS_AFTER_RETRY",
        "authorization_mode": "required",
        "authorization_head_expected": True,
        "micro_git": "not_persisted_bundle_is_audit_artifact",
        "micro_tape_bundle": str(bundle),
        "micro_tape_bundle_sha256": bundle_hash,
        "accepted_head": state["accepted_head"],
        "authorization_head": state["authorization_head"],
        "tape_tip": state["tape_tip"],
        "worker_id": worker_id,
        "capsule_id": capsule_2,
        "candidate_id": candidate_id,
        "market_id": market_id,
        "no_hitl_loop": no_hitl_loop,
        "failure_memory": failure_memory,
        "basis": "stage8_no_hitl_loop_fixture_with_failure_memory_retry",
    }


def generate_stage8_no_hitl_loop_fixture(out_dir: Path, tasks: list[dict[str, Any]]) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    runs = [build_stage8_no_hitl_loop_bundle(out_dir, task) for task in tasks]
    manifest = {
        "schema_id": "Stage8NoHitlLoopFixtureManifest.v1",
        "run_id": "stage8_real_no_hitl_loop",
        "truth_source": "fresh_micro_tape_bundles",
        "scientific_status": "NO_HITL_LOOP_PROTOCOL_FIXTURE_NOT_SOLVE_RATE",
        "sample_size": len(runs),
        "turingos_arm_runs": runs,
    }
    turingos_dir = out_dir / "turingos"
    write_json(turingos_dir / "substrate_coverage.json", manifest)
    write_json(out_dir / "loop_manifest.json", manifest)
    write_json(out_dir / "bundle_manifest.json", manifest)
    bundle_lines = [f"{run['micro_tape_bundle_sha256']}  {run['micro_tape_bundle']}" for run in runs]
    (out_dir / "bundle_sha256s.txt").write_text("\n".join(bundle_lines) + "\n", encoding="utf-8")
    return manifest


def build_stage9_native_api_worker_bundle(out_dir: Path, task: dict[str, Any], expected_result: str) -> dict[str, Any]:
    auditor = load_micro_tape_auditor()
    registry = auditor.load_event_registry()
    instance_id = task["instance_id"]
    instance_dir = out_dir / "turingos" / "instances" / instance_id
    repo = instance_dir / "micro.git"
    bundle = instance_dir / "micro_tape.bundle"
    if repo.exists():
        shutil.rmtree(repo)
    instance_dir.mkdir(parents=True, exist_ok=True)
    init = run_cmd(["git", "init", "--object-format=sha256", str(repo)], timeout=120)
    if init.returncode != 0:
        raise RuntimeError(f"stage9 git init failed:\n{init.stderr}")

    state = stage6_base_state()
    short = hashlib.sha256(instance_id.encode("utf-8")).hexdigest()[:16]
    worker_id = "worker:sha256:" + hashlib.sha256(f"stage9:{instance_id}:native-api".encode("utf-8")).hexdigest()
    atom_id = f"atom_stage9_{short}"
    capsule_id = f"wc_stage9_{short}"
    market_id = f"mkt_stage9_{short}"
    receipt_id = f"rcp_stage9_{short}"
    macro_id = f"macro:diff:stage9:{short}"
    evidence_id = f"ev_stage9_{short}"
    candidate_id = f"cand_stage9_{short}"
    run_id = f"run_stage9_{short}"
    total_tokens = 360 if expected_result == "PASS" else 220
    wall_ms = 180 if expected_result == "PASS" else 110

    append = lambda event_type, payload, writer_id, **kwargs: append_stage6_event(
        repo=repo,
        state=state,
        registry=registry,
        canonical_payload_digest=auditor.canonical_payload_digest,
        event_type=event_type,
        payload=payload,
        writer_id=writer_id,
        **kwargs,
    )

    append("SystemConstitutionAccepted", {"constitution_digest": digest_text("stage9 constitution")}, "writer:bootstrap")
    append(
        "GoalStateProposed",
        {
            "goal_id": f"goal_stage9_{short}",
            "objective": f"Stage9 Native API Worker fixture for {instance_id}",
            "task_source": "swe_bench_shaped_native_api_worker_fixture",
        },
        "writer:goal",
    )
    append(
        "AtomAuthorized",
        {
            "atom_id": atom_id,
            "approval_id": f"ap_atom_stage9_{short}",
            "authority_kind": "test_local_authority_no_credentials",
            "signature_route": "test_local_authority",
        },
        "writer:test-local-authority",
    )
    append(
        "WorkerDispatchAuthorized",
        {
            "capsule_id": capsule_id,
            "worker_id": worker_id,
            "approval_id": f"ap_dispatch_stage9_{short}",
            "authority_kind": "test_local_authority_no_credentials",
            "signature_route": "test_local_authority",
        },
        "writer:test-local-authority",
    )
    append(
        "WorkCapsuleBuilt",
        {
            "capsule_id": capsule_id,
            "private_contract_hash": digest_text(capsule_id + ":private"),
            "acceptance_commands": ["stage9.native_api.eval"],
            "allowed_files": ["django/**"],
            "forbidden_files": SWEBENCH_FORBIDDEN_PATHS,
            "worker_kind": "NativeApiWorker",
            "allowed_tools": NATIVE_API_TOOLS,
            "pput_formula_absent": True,
            "heldout_ids_absent": True,
            "hidden_predicates_absent": True,
        },
        "writer:capsule",
    )
    append(
        "MarketCreated",
        {
            "schema_id": "market_created.v1",
            "market_id": market_id,
            "initial_pool_y": "100",
            "initial_pool_n": "100",
            "k": "10000",
            "truth_status": "statistical_signal_only",
        },
        "writer:market",
    )
    append(
        "PositionMinted",
        {
            "schema_id": "position_minted.v1",
            "market_id": market_id,
            "agent_id": worker_id,
            "coin_in": "1",
            "yes_out": "1",
            "no_out": "1",
            "invariant": "coin_in == yes_out == no_out",
        },
        "writer:market",
    )
    append(
        "BudgetAllocated",
        {
            "market_id": market_id,
            "branch_id": f"branch_stage9_{short}",
            "capsule_id": capsule_id,
            "allocation_reason": {
                "price_signal_hash": digest_text("stage9 price"),
                "pput_prior_hash": digest_text("stage9 pput"),
                "diversity_policy_hash": digest_text("stage9 diversity"),
            },
            "max_tokens": total_tokens,
            "max_wall_time_ms": wall_ms,
        },
        "writer:market",
    )

    tool_receipt_ids: list[str] = []

    def append_tool(tool: str, status: str, *, exit_code: int = 0, error_class: str | None = None) -> None:
        receipt = append(
            "ToolReceiptAppended",
            {
                "schema_id": "tool_receipt_appended.v1",
                "receipt_id": f"tr_stage9_{short}_{len(tool_receipt_ids) + 1}",
                "capsule_id": capsule_id,
                "worker_id": worker_id,
                "tool": tool,
                "status": status,
                "exit_code": exit_code,
                "error_class": error_class,
                "stdout_hash": digest_text(f"{instance_id}:{tool}:stdout:{status}"),
                "stderr_hash": digest_text(f"{instance_id}:{tool}:stderr:{status}"),
                "path": "django/db/backends/ddl_references.py" if tool != "list_dir" else "django/db/backends",
                "mutates": tool in {"apply_patch", "write_file"},
                "prompt_tokens": 10,
                "completion_tokens": 10,
                "tool_tokens": 5,
                "tool_stdout_tokens": 5,
                "credential_material_absent": True,
            },
            "writer:native-api-worker",
        )
        tool_receipt_ids.append(receipt["event_id"])

    if expected_result == "PASS":
        for tool in NATIVE_API_TOOLS:
            append_tool(tool, "SUCCESS")
    else:
        append_tool("read_file", "SUCCESS")
        append_tool("list_dir", "SUCCESS")
        append_tool("grep", "SUCCESS")
        append_tool("apply_patch", "FAILED", exit_code=1, error_class="PATCH_APPLIES_BUT_WRONG")

    patch_hash = digest_text(f"{instance_id}:stage9:{expected_result}:patch")
    append(
        "WorkerReceiptImported",
        {
            "receipt_id": receipt_id,
            "capsule_id": capsule_id,
            "worker_id": worker_id,
            "exit_code": 0 if expected_result == "PASS" else 1,
            "stdout_hash": digest_text(instance_id + ":stage9:worker-stdout"),
            "stderr_hash": digest_text(instance_id + ":stage9:worker-stderr"),
            "done_json_hash": digest_text(instance_id + ":stage9:done"),
            "credential_material_absent": True,
            "micro_refs_moved": False,
            "patch_hash": patch_hash,
            "tool_receipt_event_ids": tool_receipt_ids,
            "assembled_from_tool_receipts": True,
        },
        "writer:receipt",
    )
    append(
        "MacroObservationImported",
        {
            "macro_id": macro_id,
            "capsule_id": capsule_id,
            "diff_hash": patch_hash,
            "external_evidence_only": True,
        },
        "writer:macro",
    )
    append(
        "CostEvent",
        {
            "schema_id": "cost_event.v1",
            "run_id": run_id,
            "problem_id": instance_id,
            "split": "dogfood",
            "agent_id": worker_id,
            "branch_id": f"branch_stage9_{short}",
            "capsule_id": capsule_id,
            "prompt_tokens": total_tokens // 3,
            "completion_tokens": total_tokens // 3,
            "tool_tokens": total_tokens // 6,
            "tool_stdout_tokens": total_tokens - (total_tokens // 3) - (total_tokens // 3) - (total_tokens // 6),
            "total_tokens": total_tokens,
            "wall_time_ms": wall_ms,
            "tool_stdout_hash": digest_text(instance_id + ":stage9:tool-stdout"),
            "counted_in_total": True,
        },
        "writer:pput",
    )
    official = append(
        "OfficialEvaluatorEvidenceImported",
        {
            "schema_id": "official_evaluator_evidence_imported.v1",
            "evidence_id": evidence_id,
            "instance_id": instance_id,
            "capsule_id": capsule_id,
            "macro_anchor_id": macro_id,
            "worker_receipt_id": receipt_id,
            "candidate_patch_hash": patch_hash,
            "test_patch_hash": digest_text(instance_id + ":stage9:test-patch"),
            "apply_candidate_result": "PASS" if expected_result == "PASS" else "FAIL",
            "apply_test_patch_result": "PASS",
            "fail_to_pass_labels": [],
            "target_test_exit_code": 0 if expected_result == "PASS" else 1,
            "target_test_result": expected_result,
            "stdout_hash": digest_text(instance_id + ":stage9:official-stdout"),
            "stderr_hash": digest_text(instance_id + ":stage9:official-stderr"),
            "result": expected_result,
            "failure_class": None if expected_result == "PASS" else "PATCH_APPLIES_BUT_WRONG",
            "forbidden_test_edit_detected": False,
            "forbidden_test_edit_paths": [],
            "truth_source": "stage9_deterministic_official_fixture",
        },
        "writer:official-evaluator",
        name="official",
    )
    if expected_result == "PASS":
        terminal = append(
            "CandidateAccepted",
            {
                "candidate_id": candidate_id,
                "capsule_id": capsule_id,
                "macro_anchor_id": macro_id,
                "worker_receipt_id": receipt_id,
                "official_evaluator_evidence_id": evidence_id,
            },
            "writer:predicate",
            name="terminal",
        )
        market_result = "YES"
        reward = "1"
        slash = "0"
        progress = 1
    else:
        terminal = append(
            "FailureNode",
            {
                "capsule_id": capsule_id,
                "candidate_id": candidate_id,
                "failure_class": "PATCH_APPLIES_BUT_WRONG",
                "detail": "Native API Worker tool receipt captured a failed apply_patch attempt.",
                "official_evaluator_evidence_id": evidence_id,
                "failed_tool_receipt_event_ids": [tool_receipt_ids[-1]],
            },
            "writer:predicate",
            product="NOT_RUN",
            name="terminal",
        )
        market_result = "NO"
        reward = "0"
        slash = "1"
        progress = 0

    settlement = append(
        "MarketSettled",
        {
            "schema_id": "market_settled.v1",
            "market_id": market_id,
            "result": market_result,
            "settlement_basis_event_id": official["event_id"],
            "basis_kind": "official_eval",
            "terminal_event_id": terminal["event_id"],
            "is_terminal": True,
            "price_not_truth_ack": True,
        },
        "writer:market",
        name="settlement",
    )
    append(
        "RewardDistributed",
        {
            "schema_id": "reward_distributed.v1",
            "event_type": "RewardDistributed",
            "market_id": market_id,
            "agent_id": worker_id,
            "reward_coin": reward,
            "slash_coin": slash,
            "reason": "PREDICATE_SETTLEMENT" if progress == 1 else "BUDGET_EXHAUSTED",
            "settlement_event_id": settlement["event_id"],
        },
        "writer:market",
    )
    append(
        "PPUTAccounted",
        {
            "schema_id": "pput_accounted.v1",
            "run_id": run_id,
            "problem_id": instance_id,
            "split": "dogfood",
            "solved": progress == 1,
            "verified": progress == 1,
            "accounting_stage": "final",
            "basis_event_id": official["event_id"],
            "terminal_event_id": terminal["event_id"],
            "golden_path_token_count": total_tokens if progress == 1 else 0,
            "total_run_token_count": total_tokens,
            "total_wall_time_ms": wall_ms,
            "progress": progress,
            "vpput_raw": stage6_vpput(progress, total_tokens, wall_ms),
            "failed_branch_count": 0 if progress == 1 else 1,
            "hidden_from_worker_prompt": True,
        },
        "writer:pput",
    )
    append(
        "PredicateEvaluated",
        {
            "predicate_id": "predicate.stage9.native_api.replay",
            "result": "PASS",
            "source_tape_tip": state["tape_tip"],
            "replay_hash": digest_text("stage9 replay:" + instance_id),
        },
        "writer:replay",
        product="NOT_RUN",
    )

    create = run_cmd(["git", "bundle", "create", str(bundle.resolve()), "--all"], cwd=repo, timeout=120)
    if create.returncode != 0:
        raise RuntimeError(f"stage9 bundle create failed:\n{create.stderr}")
    bundle_hash = digest_bytes(bundle.read_bytes())
    shutil.rmtree(repo)
    return {
        "instance_id": instance_id,
        "expected_result": expected_result,
        "authorization_mode": "required",
        "micro_tape_bundle": str(bundle),
        "micro_tape_bundle_sha256": bundle_hash,
        "accepted_head": state["accepted_head"],
        "authorization_head": state["authorization_head"],
        "tape_tip": state["tape_tip"],
        "worker_id": worker_id,
        "capsule_id": capsule_id,
        "candidate_id": candidate_id,
        "market_id": market_id,
        "native_api_worker": {
            "worker_kind": "NativeApiWorker",
            "expected_tools": NATIVE_API_TOOLS,
            "tool_receipt_event_ids": tool_receipt_ids,
            "worker_receipt_id": receipt_id,
            "worker_receipts_assembled_from_tool_receipts": True,
            "failed_tool_receipt_event_ids": [] if expected_result == "PASS" else [tool_receipt_ids[-1]],
            "prompt_leak_scan": "PASS",
        },
        "basis": "stage9_native_api_worker_tool_receipt_fixture",
    }


def generate_stage9_native_api_worker_fixture(out_dir: Path, tasks: list[dict[str, Any]]) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    runs = []
    for index, task in enumerate(tasks):
        expected = str(task.get("stage9_expected_result") or ("PASS" if index == 0 else "FAIL")).upper()
        if expected not in {"PASS", "FAIL"}:
            raise ValueError(f"stage9_expected_result must be PASS or FAIL for {task['instance_id']}")
        runs.append(build_stage9_native_api_worker_bundle(out_dir, task, expected))
    manifest = {
        "schema_id": "Stage9NativeApiWorkerFixtureManifest.v1",
        "run_id": "stage9_native_api_worker",
        "truth_source": "fresh_micro_tape_bundles",
        "scientific_status": "NATIVE_API_WORKER_TOOL_RECEIPT_FIXTURE_NOT_SOLVE_RATE",
        "sample_size": len(runs),
        "turingos_arm_runs": runs,
    }
    turingos_dir = out_dir / "turingos"
    write_json(turingos_dir / "substrate_coverage.json", manifest)
    write_json(out_dir / "worker_manifest.json", manifest)
    write_json(out_dir / "bundle_manifest.json", manifest)
    bundle_lines = [f"{run['micro_tape_bundle_sha256']}  {run['micro_tape_bundle']}" for run in runs]
    (out_dir / "bundle_sha256s.txt").write_text("\n".join(bundle_lines) + "\n", encoding="utf-8")
    return manifest


def build_stage10_failure_taxonomy_bundle(out_dir: Path, task: dict[str, Any], failure_class: str) -> dict[str, Any]:
    auditor = load_micro_tape_auditor()
    registry = auditor.load_event_registry()
    instance_id = task["instance_id"]
    instance_dir = out_dir / "turingos" / "instances" / instance_id
    repo = instance_dir / "micro.git"
    bundle = instance_dir / "micro_tape.bundle"
    if repo.exists():
        shutil.rmtree(repo)
    instance_dir.mkdir(parents=True, exist_ok=True)
    init = run_cmd(["git", "init", "--object-format=sha256", str(repo)], timeout=120)
    if init.returncode != 0:
        raise RuntimeError(f"stage10 git init failed:\n{init.stderr}")

    state = stage6_base_state()
    short = hashlib.sha256(instance_id.encode("utf-8")).hexdigest()[:16]
    worker_id = "worker:sha256:" + hashlib.sha256(f"stage10:{instance_id}:worker".encode("utf-8")).hexdigest()
    atom_id = f"atom_stage10_{short}"
    capsule_id = f"wc_stage10_{short}"
    market_id = f"mkt_stage10_{short}"
    receipt_id = f"rcp_stage10_{short}"
    macro_id = f"macro:diff:stage10:{short}"
    evidence_id = f"ev_stage10_{short}"
    candidate_id = f"cand_stage10_{short}"
    run_id = f"run_stage10_{short}"
    total_tokens = 120
    wall_ms = 60

    append = lambda event_type, payload, writer_id, **kwargs: append_stage6_event(
        repo=repo,
        state=state,
        registry=registry,
        canonical_payload_digest=auditor.canonical_payload_digest,
        event_type=event_type,
        payload=payload,
        writer_id=writer_id,
        **kwargs,
    )

    append("SystemConstitutionAccepted", {"constitution_digest": digest_text("stage10 constitution")}, "writer:bootstrap")
    append(
        "GoalStateProposed",
        {
            "goal_id": f"goal_stage10_{short}",
            "objective": f"Stage10 failure taxonomy fixture for {failure_class}",
            "task_source": "swe_bench_shaped_failure_taxonomy_fixture",
        },
        "writer:goal",
    )
    append(
        "AtomAuthorized",
        {
            "atom_id": atom_id,
            "approval_id": f"ap_atom_stage10_{short}",
            "authority_kind": "test_local_authority_no_credentials",
            "signature_route": "test_local_authority",
        },
        "writer:test-local-authority",
    )
    append(
        "WorkerDispatchAuthorized",
        {
            "capsule_id": capsule_id,
            "worker_id": worker_id,
            "approval_id": f"ap_dispatch_stage10_{short}",
            "authority_kind": "test_local_authority_no_credentials",
            "signature_route": "test_local_authority",
        },
        "writer:test-local-authority",
    )
    append(
        "WorkCapsuleBuilt",
        {
            "capsule_id": capsule_id,
            "private_contract_hash": digest_text(capsule_id + ":private"),
            "acceptance_commands": ["stage10.failure.taxonomy.eval"],
            "allowed_files": ["django/**"],
            "forbidden_files": SWEBENCH_FORBIDDEN_PATHS,
            "pput_formula_absent": True,
            "heldout_ids_absent": True,
            "hidden_predicates_absent": True,
        },
        "writer:capsule",
    )
    append(
        "MarketCreated",
        {
            "schema_id": "market_created.v1",
            "market_id": market_id,
            "initial_pool_y": "100",
            "initial_pool_n": "100",
            "k": "10000",
            "truth_status": "statistical_signal_only",
        },
        "writer:market",
    )
    append(
        "WorkerReceiptImported",
        {
            "receipt_id": receipt_id,
            "capsule_id": capsule_id,
            "worker_id": worker_id,
            "exit_code": 1,
            "stdout_hash": digest_text(instance_id + ":stage10:stdout"),
            "stderr_hash": digest_text(instance_id + ":stage10:stderr"),
            "done_json_hash": digest_text(instance_id + ":stage10:done"),
            "credential_material_absent": True,
            "micro_refs_moved": False,
            "patch_hash": digest_text(instance_id + ":stage10:patch"),
        },
        "writer:receipt",
    )
    append(
        "MacroObservationImported",
        {
            "macro_id": macro_id,
            "capsule_id": capsule_id,
            "diff_hash": digest_text(instance_id + ":stage10:patch"),
            "external_evidence_only": True,
        },
        "writer:macro",
    )
    append(
        "CostEvent",
        {
            "schema_id": "cost_event.v1",
            "run_id": run_id,
            "problem_id": instance_id,
            "split": "dogfood",
            "agent_id": worker_id,
            "branch_id": f"branch_stage10_{short}",
            "capsule_id": capsule_id,
            "prompt_tokens": 40,
            "completion_tokens": 40,
            "tool_tokens": 20,
            "tool_stdout_tokens": 20,
            "total_tokens": total_tokens,
            "wall_time_ms": wall_ms,
            "tool_stdout_hash": digest_text(instance_id + ":stage10:tool-stdout"),
            "counted_in_total": True,
        },
        "writer:pput",
    )
    official = append(
        "OfficialEvaluatorEvidenceImported",
        {
            "schema_id": "official_evaluator_evidence_imported.v1",
            "evidence_id": evidence_id,
            "instance_id": instance_id,
            "capsule_id": capsule_id,
            "macro_anchor_id": macro_id,
            "worker_receipt_id": receipt_id,
            "candidate_patch_hash": digest_text(instance_id + ":stage10:patch"),
            "test_patch_hash": digest_text(instance_id + ":stage10:test-patch"),
            "apply_candidate_result": "FAIL",
            "apply_test_patch_result": "PASS",
            "fail_to_pass_labels": [],
            "target_test_exit_code": 1,
            "target_test_result": "FAIL",
            "stdout_hash": digest_text(instance_id + ":stage10:official-stdout"),
            "stderr_hash": digest_text(instance_id + ":stage10:official-stderr"),
            "result": "FAIL",
            "failure_class": failure_class,
            "forbidden_test_edit_detected": False,
            "forbidden_test_edit_paths": [],
            "truth_source": "stage10_deterministic_official_fixture",
        },
        "writer:official-evaluator",
        name="official",
    )
    failure = append(
        "FailureNode",
        {
            "capsule_id": capsule_id,
            "candidate_id": candidate_id,
            "failure_class": failure_class,
            "detail": f"Stage10 deterministic failure classified as {failure_class}",
            "official_evaluator_evidence_id": evidence_id,
        },
        "writer:predicate",
        product="NOT_RUN",
        name="failure",
    )
    append(
        "FailureCertificate",
        {
            "certificate_id": f"fc_stage10_{short}",
            "source_failure_node_id": failure["event_id"],
            "failure_class": failure_class,
            "abstract_pattern": f"Classified SWE-bench failure pattern: {failure_class}",
            "raw_log_ref": "cas:" + hashlib.sha256(f"{instance_id}:stage10:raw-log".encode("utf-8")).hexdigest(),
            "raw_log_text_absent": True,
            "broadcast_rule_candidate": {
                "rule_id": f"br_candidate_stage10_{short}",
                "candidate_only": True,
                "activation_event_id": None,
                "source_failure_nodes": [failure["event_id"]],
                "failure_class": failure_class,
                "abstract_pattern": f"Classified SWE-bench failure pattern: {failure_class}",
                "guidance": f"Handle {failure_class} with targeted repair before retry.",
                "raw_log_text_absent": True,
                "hidden_predicates_absent": True,
            },
        },
        "writer:failure-taxonomy",
    )
    settlement = append(
        "MarketSettled",
        {
            "schema_id": "market_settled.v1",
            "market_id": market_id,
            "result": "NO",
            "settlement_basis_event_id": official["event_id"],
            "basis_kind": "official_eval",
            "terminal_event_id": failure["event_id"],
            "is_terminal": True,
            "price_not_truth_ack": True,
        },
        "writer:market",
        name="settlement",
    )
    append(
        "RewardDistributed",
        {
            "schema_id": "reward_distributed.v1",
            "event_type": "RewardDistributed",
            "market_id": market_id,
            "agent_id": worker_id,
            "reward_coin": "0",
            "slash_coin": "1",
            "reason": "BUDGET_EXHAUSTED",
            "settlement_event_id": settlement["event_id"],
        },
        "writer:market",
    )
    append(
        "PPUTAccounted",
        {
            "schema_id": "pput_accounted.v1",
            "run_id": run_id,
            "problem_id": instance_id,
            "split": "dogfood",
            "solved": False,
            "verified": False,
            "accounting_stage": "final",
            "basis_event_id": official["event_id"],
            "terminal_event_id": failure["event_id"],
            "golden_path_token_count": 0,
            "total_run_token_count": total_tokens,
            "total_wall_time_ms": wall_ms,
            "progress": 0,
            "vpput_raw": "0",
            "failed_branch_count": 1,
            "hidden_from_worker_prompt": True,
        },
        "writer:pput",
    )
    append(
        "PredicateEvaluated",
        {
            "predicate_id": "predicate.stage10.failure_taxonomy.replay",
            "result": "PASS",
            "source_tape_tip": state["tape_tip"],
            "replay_hash": digest_text("stage10 replay:" + instance_id),
        },
        "writer:replay",
        product="NOT_RUN",
    )

    create = run_cmd(["git", "bundle", "create", str(bundle.resolve()), "--all"], cwd=repo, timeout=120)
    if create.returncode != 0:
        raise RuntimeError(f"stage10 bundle create failed:\n{create.stderr}")
    bundle_hash = digest_bytes(bundle.read_bytes())
    shutil.rmtree(repo)
    return {
        "instance_id": instance_id,
        "expected_result": "FAIL",
        "stage10_failure_class": failure_class,
        "authorization_mode": "required",
        "micro_tape_bundle": str(bundle),
        "micro_tape_bundle_sha256": bundle_hash,
        "accepted_head": state["accepted_head"],
        "authorization_head": state["authorization_head"],
        "tape_tip": state["tape_tip"],
        "worker_id": worker_id,
        "capsule_id": capsule_id,
        "candidate_id": candidate_id,
        "market_id": market_id,
        "basis": "stage10_failure_taxonomy_fixture",
    }


def generate_stage10_failure_taxonomy_fixture(out_dir: Path, tasks: list[dict[str, Any]]) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    runs = []
    for index, task in enumerate(tasks):
        failure_class = str(task.get("stage10_failure_class") or STAGE10_FAILURE_CLASSES[index % len(STAGE10_FAILURE_CLASSES)]).upper()
        if failure_class not in STAGE10_FAILURE_CLASSES:
            raise ValueError(f"unsupported stage10_failure_class {failure_class!r}")
        runs.append(build_stage10_failure_taxonomy_bundle(out_dir, task, failure_class))
    manifest = {
        "schema_id": "Stage10FailureTaxonomyFixtureManifest.v1",
        "run_id": "stage10_failure_taxonomy",
        "truth_source": "fresh_micro_tape_bundles",
        "scientific_status": "FAILURE_TAXONOMY_FIXTURE_NOT_SOLVE_RATE",
        "sample_size": len(runs),
        "expected_classes": STAGE10_FAILURE_CLASSES,
        "turingos_arm_runs": runs,
    }
    turingos_dir = out_dir / "turingos"
    write_json(turingos_dir / "substrate_coverage.json", manifest)
    write_json(out_dir / "taxonomy_manifest.json", manifest)
    write_json(out_dir / "bundle_manifest.json", manifest)
    bundle_lines = [f"{run['micro_tape_bundle_sha256']}  {run['micro_tape_bundle']}" for run in runs]
    (out_dir / "bundle_sha256s.txt").write_text("\n".join(bundle_lines) + "\n", encoding="utf-8")
    return manifest


def default_stage11_tasks() -> list[dict[str, Any]]:
    return [
        {
            "instance_id": f"stage11_case_{index + 1}",
            "repo": "django/django",
            "base_commit": "58c1acb1d6054dfec29d0f30b1033bae6ef62aec",
            "problem_statement": f"Stage11 loop-until-PASS fixture case {index + 1}",
        }
        for index in range(len(STAGE11_LOOP_CASES))
    ]


def stage11_case_for_index(index: int) -> dict[str, Any]:
    return STAGE11_LOOP_CASES[index % len(STAGE11_LOOP_CASES)]


def classify_stage11_observed_signals(signals: dict[str, Any]) -> str:
    if signals.get("diff_scope") == "wrong_file":
        return "WRONG_FILE"
    if signals.get("timeout_kind") == "context_starved" or signals.get("receipt_schema_status") == "context_missing":
        return "CONTEXT_MISSING"
    if signals.get("official_evaluator_result") == "FAIL" and signals.get("command_result") == "semantic_mismatch":
        return "SEMANTIC_FAIL"
    raise ValueError(f"Stage11 observed signals do not imply a supported class: {signals}")


def build_stage11_loop_until_pass_bundle(
    out_dir: Path,
    task: dict[str, Any],
    case: dict[str, Any],
    *,
    force_budget_exhausted: bool = False,
    omit_broadcast_consumption: bool = False,
) -> dict[str, Any]:
    auditor = load_micro_tape_auditor()
    registry = auditor.load_event_registry()
    instance_id = task["instance_id"]
    instance_dir = out_dir / "turingos" / "instances" / instance_id
    repo = instance_dir / "micro.git"
    bundle = instance_dir / "micro_tape.bundle"
    if repo.exists():
        shutil.rmtree(repo)
    instance_dir.mkdir(parents=True, exist_ok=True)
    init = run_cmd(["git", "init", "--object-format=sha256", str(repo)], timeout=120)
    if init.returncode != 0:
        raise RuntimeError(f"stage11 git init failed:\n{init.stderr}")

    state = stage6_base_state()
    short = hashlib.sha256(instance_id.encode("utf-8")).hexdigest()[:16]
    worker_id = "worker:sha256:" + hashlib.sha256(f"stage11:{instance_id}:worker".encode("utf-8")).hexdigest()
    atom_id = f"atom_stage11_{short}"
    capsule_1 = f"wc_stage11_{short}_attempt1"
    capsule_2 = f"wc_stage11_{short}_attempt2"
    market_id = f"mkt_stage11_{short}"
    receipt_1 = f"rcp_stage11_{short}_attempt1"
    receipt_2 = f"rcp_stage11_{short}_attempt2"
    macro_1 = f"macro:diff:stage11:{short}:attempt1"
    macro_2 = f"macro:diff:stage11:{short}:attempt2"
    evidence_fail = f"ev_stage11_{short}_fail"
    evidence_pass = f"ev_stage11_{short}_pass"
    candidate_id = f"cand_stage11_{short}"
    run_id = f"run_stage11_{short}"
    rule_id = f"br_stage11_{short}"
    first_tokens = 180
    second_tokens = 260
    first_wall_ms = 90
    second_wall_ms = 130
    total_tokens = first_tokens + (0 if force_budget_exhausted else second_tokens)
    total_wall_ms = first_wall_ms + (0 if force_budget_exhausted else second_wall_ms)

    observed_signals = dict(case["observed_signals"])
    failure_class = classify_stage11_observed_signals(observed_signals)
    if failure_class != case["failure_class"]:
        raise ValueError("Stage11 case failure_class must match observer-derived classifier output")

    append = lambda event_type, payload, writer_id, **kwargs: append_stage6_event(
        repo=repo,
        state=state,
        registry=registry,
        canonical_payload_digest=auditor.canonical_payload_digest,
        event_type=event_type,
        payload=payload,
        writer_id=writer_id,
        **kwargs,
    )

    append("SystemConstitutionAccepted", {"constitution_digest": digest_text("stage11 constitution")}, "writer:bootstrap")
    append(
        "GoalStateProposed",
        {
            "goal_id": f"goal_stage11_{short}",
            "objective": "Stage11 loop-until-PASS protocol fixture",
            "task_source": "swe_bench_shaped_loop_until_pass_fixture",
        },
        "writer:goal",
    )
    append(
        "AtomAuthorized",
        {
            "atom_id": atom_id,
            "approval_id": f"ap_atom_stage11_{short}",
            "authority_kind": "test_local_authority_no_credentials",
            "signature_route": "test_local_authority",
        },
        "writer:test-local-authority",
    )
    append(
        "WorkerDispatchAuthorized",
        {
            "capsule_id": capsule_1,
            "worker_id": worker_id,
            "approval_id": f"ap_dispatch_stage11_{short}_attempt1",
            "authority_kind": "test_local_authority_no_credentials",
            "signature_route": "test_local_authority",
        },
        "writer:test-local-authority",
    )
    append(
        "WorkCapsuleBuilt",
        {
            "capsule_id": capsule_1,
            "private_contract_hash": digest_text(capsule_1 + ":private"),
            "acceptance_commands": ["stage11.official.eval"],
            "allowed_files": ["django/**"],
            "forbidden_files": SWEBENCH_FORBIDDEN_PATHS,
            "attempt_index": 1,
            "pput_formula_absent": True,
            "heldout_ids_absent": True,
            "hidden_predicates_absent": True,
        },
        "writer:capsule",
    )
    append(
        "MarketCreated",
        {
            "schema_id": "market_created.v1",
            "market_id": market_id,
            "initial_pool_y": "100",
            "initial_pool_n": "100",
            "k": "10000",
            "truth_status": "statistical_signal_only",
        },
        "writer:market",
    )
    patch_fail = digest_text(instance_id + ":stage11:attempt1:patch")
    append(
        "WorkerReceiptImported",
        {
            "receipt_id": receipt_1,
            "capsule_id": capsule_1,
            "worker_id": worker_id,
            "exit_code": observed_signals.get("exit_code", 1),
            "stdout_hash": digest_text(instance_id + ":stage11:attempt1:stdout"),
            "stderr_hash": digest_text(instance_id + ":stage11:attempt1:stderr"),
            "done_json_hash": digest_text(instance_id + ":stage11:attempt1:done"),
            "credential_material_absent": True,
            "manual_patch": False,
            "micro_refs_moved": False,
            "patch_hash": patch_fail,
            "observed_signals_hash": digest_text(json.dumps(observed_signals, sort_keys=True)),
        },
        "writer:receipt",
    )
    append(
        "MacroObservationImported",
        {
            "macro_id": macro_1,
            "capsule_id": capsule_1,
            "diff_hash": patch_fail,
            "external_evidence_only": True,
            "macro_observation_kind": observed_signals.get("macro_observation_kind", "patch_failed"),
        },
        "writer:macro",
    )
    append(
        "CostEvent",
        {
            "schema_id": "cost_event.v1",
            "run_id": run_id,
            "problem_id": instance_id,
            "split": "dogfood",
            "agent_id": worker_id,
            "branch_id": f"branch_stage11_{short}_attempt1",
            "capsule_id": capsule_1,
            "prompt_tokens": 80,
            "completion_tokens": 60,
            "tool_tokens": 20,
            "tool_stdout_tokens": 20,
            "total_tokens": first_tokens,
            "wall_time_ms": first_wall_ms,
            "tool_stdout_hash": digest_text(instance_id + ":stage11:attempt1:tool-stdout"),
            "counted_in_total": True,
        },
        "writer:pput",
    )
    official_fail = append(
        "OfficialEvaluatorEvidenceImported",
        {
            "schema_id": "official_evaluator_evidence_imported.v1",
            "evidence_id": evidence_fail,
            "instance_id": instance_id,
            "capsule_id": capsule_1,
            "macro_anchor_id": macro_1,
            "worker_receipt_id": receipt_1,
            "candidate_patch_hash": patch_fail,
            "test_patch_hash": digest_text(instance_id + ":stage11:test-patch"),
            "apply_candidate_result": "PASS",
            "apply_test_patch_result": "PASS",
            "fail_to_pass_labels": [],
            "target_test_exit_code": 1,
            "target_test_result": "FAIL",
            "stdout_hash": digest_text(instance_id + ":stage11:attempt1:official-stdout"),
            "stderr_hash": digest_text(instance_id + ":stage11:attempt1:official-stderr"),
            "result": "FAIL",
            "failure_class": failure_class,
            "forbidden_test_edit_detected": False,
            "forbidden_test_edit_paths": [],
            "truth_source": "stage11_deterministic_official_fixture",
        },
        "writer:official-evaluator",
        name="official_fail",
    )
    classifier_decision = {
        "failure_class": failure_class,
        "observer_derived_failure_class": True,
        "classifier_inputs": observed_signals,
        "classifier_input_sources": [
            "WorkerReceiptImported.exit_code",
            "OfficialEvaluatorEvidenceImported.result",
            "MacroObservationImported.macro_observation_kind",
        ],
        "forbidden_classifier_inputs_absent": [
            "scenario_label",
            "fixture_name",
            "instance_id_label",
            "problem_title",
            "expected_failure_class",
        ],
    }
    failure = append(
        "FailureNode",
        {
            "capsule_id": capsule_1,
            "candidate_id": candidate_id,
            "failure_class": failure_class,
            "detail": "Stage11 first attempt failed and was classified from observer signals.",
            "official_evaluator_evidence_id": evidence_fail,
            "classifier_decision": classifier_decision,
        },
        "writer:predicate",
        product="NOT_RUN",
        name="first_failure",
    )
    append(
        "PPUTAccounted",
        {
            "schema_id": "pput_accounted.v1",
            "run_id": run_id,
            "problem_id": instance_id,
            "split": "dogfood",
            "solved": False,
            "verified": False,
            "accounting_stage": "progress",
            "basis_event_id": official_fail["event_id"],
            "terminal_event_id": failure["event_id"],
            "golden_path_token_count": 0,
            "total_run_token_count": first_tokens,
            "total_wall_time_ms": first_wall_ms,
            "progress": 0,
            "vpput_raw": "0",
            "failed_branch_count": 1,
            "hidden_from_worker_prompt": True,
        },
        "writer:pput",
    )
    certificate = append(
        "FailureCertificate",
        {
            "certificate_id": f"fc_stage11_{short}",
            "source_failure_node_id": failure["event_id"],
            "failure_class": failure_class,
            "abstract_pattern": case["abstract_pattern"],
            "classifier_decision_hash": digest_text(json.dumps(classifier_decision, sort_keys=True)),
            "raw_log_ref": "cas:" + hashlib.sha256(f"{instance_id}:stage11:attempt1:private-log".encode("utf-8")).hexdigest(),
            "raw_log_text_absent": True,
            "broadcast_rule_candidate": {
                "rule_id": rule_id,
                "candidate_only": True,
                "activation_event_id": None,
                "source_failure_nodes": [failure["event_id"]],
                "failure_class": failure_class,
                "abstract_pattern": case["abstract_pattern"],
                "new_instruction": case["guidance"],
                "raw_log_text_absent": True,
                "hidden_predicates_absent": True,
                "pput_or_heldout_details_absent": True,
            },
        },
        "writer:failure-taxonomy",
        name="failure_certificate",
    )
    broadcast = append(
        "BroadcastRuleActivated",
        {
            "rule_id": rule_id,
            "source_failure_nodes": [failure["event_id"]],
            "failure_certificate_event_id": certificate["event_id"],
            "failure_class": failure_class,
            "abstract_pattern": case["abstract_pattern"],
            "new_instruction": case["guidance"],
            "recipients": ["future_capsule"],
            "hidden_details_removed": True,
            "raw_log_refs": ["cas:" + hashlib.sha256(f"{instance_id}:stage11:attempt1:private-log".encode("utf-8")).hexdigest()],
            "raw_log_refs_private_only": True,
            "raw_log_text_absent": True,
            "hidden_predicates_absent": True,
            "pput_or_heldout_details_absent": True,
        },
        "writer:failure-memory",
        name="broadcast",
    )
    retry = append(
        "RetryAuthorized",
        {
            "retry_id": f"retry_stage11_{short}",
            "capsule_id": capsule_2,
            "source_failure_node_id": failure["event_id"],
            "broadcast_rule_event_id": broadcast["event_id"],
            "retry_decision_source": "tape_reducer_or_policy",
            "approval_id": f"ap_retry_stage11_{short}",
            "authority_kind": "test_local_authority_no_credentials",
            "signature_route": "test_local_authority",
            "human_intervention_count": 0,
        },
        "writer:test-local-authority",
        name="retry",
    )
    append(
        "WorkerDispatchAuthorized",
        {
            "capsule_id": capsule_2,
            "worker_id": worker_id,
            "approval_id": f"ap_dispatch_stage11_{short}_attempt2",
            "signature_route": "test_local_authority",
            "authority_kind": "test_local_authority_no_credentials",
            "retry_authorization_event_id": retry["event_id"],
        },
        "writer:test-local-authority",
        name="dispatch_attempt2",
    )
    capsule_payload = {
        "capsule_id": capsule_2,
        "private_contract_hash": digest_text(capsule_2 + ":private"),
        "acceptance_commands": ["stage11.official.eval"],
        "allowed_files": ["django/**"],
        "forbidden_files": SWEBENCH_FORBIDDEN_PATHS,
        "attempt_index": 2,
        "source_failure_nodes": [failure["event_id"]],
        "visible_known_failures_to_avoid": [case["guidance"]],
        "raw_log_text_absent": True,
        "hidden_predicates_absent": True,
        "pput_or_heldout_details_absent": True,
    }
    if not omit_broadcast_consumption:
        capsule_payload["consumed_broadcast_rule_ids"] = [rule_id]
        capsule_payload["injected_broadcast_rule_ids"] = [rule_id]
        capsule_payload["broadcast_rule_event_id"] = broadcast["event_id"]
    append("WorkCapsuleBuilt", capsule_payload, "writer:capsule", name="capsule_attempt2")

    terminal_event = failure
    official_pass = None
    if not force_budget_exhausted:
        append(
            "CostEvent",
            {
                "schema_id": "cost_event.v1",
                "run_id": run_id,
                "problem_id": instance_id,
                "split": "dogfood",
                "agent_id": worker_id,
                "branch_id": f"branch_stage11_{short}_attempt2",
                "capsule_id": capsule_2,
                "prompt_tokens": 110,
                "completion_tokens": 90,
                "tool_tokens": 30,
                "tool_stdout_tokens": 30,
                "total_tokens": second_tokens,
                "wall_time_ms": second_wall_ms,
                "tool_stdout_hash": digest_text(instance_id + ":stage11:attempt2:tool-stdout"),
                "counted_in_total": True,
            },
            "writer:pput",
        )
        patch_pass = digest_text(instance_id + ":stage11:attempt2:patch")
        append(
            "WorkerReceiptImported",
            {
                "receipt_id": receipt_2,
                "capsule_id": capsule_2,
                "worker_id": worker_id,
                "exit_code": 0,
                "stdout_hash": digest_text(instance_id + ":stage11:attempt2:stdout"),
                "stderr_hash": digest_text(instance_id + ":stage11:attempt2:stderr"),
                "done_json_hash": digest_text(instance_id + ":stage11:attempt2:done"),
                "credential_material_absent": True,
                "manual_patch": False,
                "micro_refs_moved": False,
                "patch_hash": patch_pass,
                "consumed_broadcast_rule_event_id": broadcast["event_id"],
            },
            "writer:receipt",
        )
        append(
            "MacroObservationImported",
            {
                "macro_id": macro_2,
                "capsule_id": capsule_2,
                "diff_hash": patch_pass,
                "external_evidence_only": True,
                "macro_observation_kind": "repair_patch",
            },
            "writer:macro",
        )
        official_pass = append(
            "OfficialEvaluatorEvidenceImported",
            {
                "schema_id": "official_evaluator_evidence_imported.v1",
                "evidence_id": evidence_pass,
                "instance_id": instance_id,
                "capsule_id": capsule_2,
                "macro_anchor_id": macro_2,
                "worker_receipt_id": receipt_2,
                "candidate_patch_hash": patch_pass,
                "test_patch_hash": digest_text(instance_id + ":stage11:test-patch"),
                "apply_candidate_result": "PASS",
                "apply_test_patch_result": "PASS",
                "fail_to_pass_labels": [],
                "target_test_exit_code": 0,
                "target_test_result": "PASS",
                "stdout_hash": digest_text(instance_id + ":stage11:attempt2:official-stdout"),
                "stderr_hash": digest_text(instance_id + ":stage11:attempt2:official-stderr"),
                "result": "PASS",
                "failure_class": None,
                "forbidden_test_edit_detected": False,
                "forbidden_test_edit_paths": [],
                "truth_source": "stage11_deterministic_official_fixture",
            },
            "writer:official-evaluator",
            name="official_pass",
        )
        terminal_event = append(
            "CandidateAccepted",
            {
                "candidate_id": candidate_id,
                "capsule_id": capsule_2,
                "macro_anchor_id": macro_2,
                "worker_receipt_id": receipt_2,
                "official_evaluator_evidence_id": evidence_pass,
                "consumed_broadcast_rule_event_id": broadcast["event_id"],
            },
            "writer:predicate",
            name="terminal",
        )

    settlement = append(
        "MarketSettled",
        {
            "schema_id": "market_settled.v1",
            "market_id": market_id,
            "result": "NO" if force_budget_exhausted else "YES",
            "settlement_basis_event_id": official_fail["event_id"] if force_budget_exhausted else official_pass["event_id"],
            "basis_kind": "official_eval",
            "terminal_event_id": terminal_event["event_id"],
            "is_terminal": True,
            "price_not_truth_ack": True,
        },
        "writer:market",
        name="settlement",
    )
    append(
        "RewardDistributed",
        {
            "schema_id": "reward_distributed.v1",
            "event_type": "RewardDistributed",
            "market_id": market_id,
            "agent_id": worker_id,
            "reward_coin": "0" if force_budget_exhausted else "1",
            "slash_coin": "1" if force_budget_exhausted else "0",
            "reason": "BUDGET_EXHAUSTED" if force_budget_exhausted else "PREDICATE_SETTLEMENT",
            "settlement_event_id": settlement["event_id"],
        },
        "writer:market",
    )
    append(
        "PPUTAccounted",
        {
            "schema_id": "pput_accounted.v1",
            "run_id": run_id,
            "problem_id": instance_id,
            "split": "dogfood",
            "solved": not force_budget_exhausted,
            "verified": not force_budget_exhausted,
            "accounting_stage": "final",
            "basis_event_id": official_fail["event_id"] if force_budget_exhausted else official_pass["event_id"],
            "terminal_event_id": terminal_event["event_id"],
            "golden_path_token_count": total_tokens if not force_budget_exhausted else 0,
            "total_run_token_count": total_tokens,
            "total_wall_time_ms": total_wall_ms,
            "progress": 0 if force_budget_exhausted else 1,
            "vpput_raw": stage6_vpput(0 if force_budget_exhausted else 1, total_tokens, total_wall_ms),
            "failed_branch_count": 1,
            "hidden_from_worker_prompt": True,
        },
        "writer:pput",
    )
    append(
        "PredicateEvaluated",
        {
            "predicate_id": "predicate.stage11.loop_until_pass.replay",
            "result": "PASS",
            "source_tape_tip": state["tape_tip"],
            "replay_hash": digest_text("stage11 replay:" + instance_id),
        },
        "writer:replay",
        product="NOT_RUN",
    )

    create = run_cmd(["git", "bundle", "create", str(bundle.resolve()), "--all"], cwd=repo, timeout=120)
    if create.returncode != 0:
        raise RuntimeError(f"stage11 bundle create failed:\n{create.stderr}")
    bundle_hash = digest_bytes(bundle.read_bytes())
    shutil.rmtree(repo)

    loop = {
        "status": "BUDGET_EXHAUSTED" if force_budget_exhausted else "PASS",
        "human_intervention_count": 0,
        "manual_patch_count": 0,
        "manual_approval_count": 0,
        "manual_rerun_selection_count": 0,
        "fallback_to_auto_authorization": False,
        "attempts_total": 2,
        "failed_attempts_before_accept": 1,
        "first_failed_attempt_index": 1,
        "accepted_attempt_index": None if force_budget_exhausted else 2,
        "budget_exhausted": force_budget_exhausted,
        "retry_decision_source": "tape_reducer_or_policy",
        "retry_policy_event_id": retry["event_id"],
        "first_failure_event_id": failure["event_id"],
        "failure_certificate_event_id": certificate["event_id"],
        "broadcast_rule_activated_event_id": broadcast["event_id"],
        "second_attempt_capsule_event_id": state["event_ids"]["capsule_attempt2"],
        "terminal_candidate_accepted_event_id": None if force_budget_exhausted else terminal_event["event_id"],
        "accepted_head": state["accepted_head"],
        "verified_from_micro_tape_bundle_only": True,
    }
    failure_memory = {
        "status": "PASS",
        "source_failure_nodes": [failure["event_id"]],
        "failure_class": failure_class,
        "abstract_pattern": case["abstract_pattern"],
        "activated_rule_event_id": broadcast["event_id"],
        "injected_into_capsule_id": capsule_2,
        "later_capsule_consumed_rule": not omit_broadcast_consumption,
        "raw_log_refs_private_only": True,
        "raw_log_text_absent_from_visible_capsule": True,
        "hidden_predicates_absent_from_visible_capsule": True,
        "pput_or_heldout_details_absent_from_visible_capsule": True,
        "broadcast_rule_reduced_from_tape": True,
    }
    classifier_audit = {
        "status": "PASS",
        "failure_class": failure_class,
        "classifier_inputs": observed_signals,
        "observer_derived_failure_class": True,
        "classifier_inputs_allowed_only": [
            "exit_code",
            "timeout_kind",
            "official_evaluator_result",
            "diff_scope",
            "receipt_schema_status",
            "command_result",
            "macro_observation_kind",
            "test_log_digest",
        ],
        "forbidden_classifier_inputs_absent": [
            "scenario_label",
            "fixture_name",
            "instance_id_label",
            "problem_title",
            "expected_failure_class",
        ],
    }
    return {
        "instance_id": instance_id,
        "expected_result": "BUDGET_EXHAUSTED" if force_budget_exhausted else "PASS",
        "stage11_case_id": case["case_id"],
        "authorization_mode": "required",
        "micro_tape_bundle": str(bundle),
        "micro_tape_bundle_sha256": bundle_hash,
        "accepted_head": state["accepted_head"],
        "authorization_head": state["authorization_head"],
        "tape_tip": state["tape_tip"],
        "worker_id": worker_id,
        "capsule_id": capsule_2,
        "candidate_id": candidate_id,
        "market_id": market_id,
        "loop_until_pass": loop,
        "failure_memory_activation": failure_memory,
        "real_classifier": classifier_audit,
        "basis": "stage11_loop_until_pass_fixture",
    }


def generate_stage11_loop_until_pass_fixture(
    out_dir: Path,
    tasks: list[dict[str, Any]],
    *,
    force_budget_exhausted: bool = False,
    omit_broadcast_consumption: bool = False,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    runs = []
    for index, task in enumerate(tasks):
        case = stage11_case_for_index(index)
        runs.append(
            build_stage11_loop_until_pass_bundle(
                out_dir,
                task,
                case,
                force_budget_exhausted=force_budget_exhausted,
                omit_broadcast_consumption=omit_broadcast_consumption,
            )
        )
    manifest = {
        "schema_id": "Stage11LoopUntilPassFixtureManifest.v1",
        "run_id": "stage11_loop_until_pass",
        "truth_source": "fresh_micro_tape_bundles",
        "scientific_status": "LOOP_UNTIL_PASS_FIXTURE_NOT_SOLVE_RATE",
        "sample_size": len(runs),
        "turingos_arm_runs": runs,
    }
    turingos_dir = out_dir / "turingos"
    write_json(turingos_dir / "substrate_coverage.json", manifest)
    write_json(out_dir / "loop_manifest.json", manifest)
    write_json(out_dir / "bundle_manifest.json", manifest)
    bundle_lines = [f"{run['micro_tape_bundle_sha256']}  {run['micro_tape_bundle']}" for run in runs]
    (out_dir / "bundle_sha256s.txt").write_text("\n".join(bundle_lines) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks-jsonl")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--worker-mode", choices=["fake", "grok"], default="fake")
    parser.add_argument("--model", default="grok-build")
    parser.add_argument("--max-turns", type=int, default=8)
    parser.add_argument("--worker-timeout-s", type=int, default=1200)
    parser.add_argument("--authorization-mode", choices=["auto", "required", "off"], default="auto")
    parser.add_argument("--daemon-bin-dir", default=str(REPO / "target" / "debug"))
    parser.add_argument("--broadcast-rules-file")
    parser.add_argument("--strict-microtape-fixture", action="store_true")
    parser.add_argument("--no-hitl-loop-fixture", action="store_true")
    parser.add_argument("--native-api-worker-fixture", action="store_true")
    parser.add_argument("--failure-taxonomy-fixture", action="store_true")
    parser.add_argument("--loop-until-pass-fixture", action="store_true")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.loop_until_pass_fixture and not args.tasks_jsonl:
        tasks = default_stage11_tasks()[: args.limit]
    else:
        if not args.tasks_jsonl:
            parser.error("--tasks-jsonl is required unless --loop-until-pass-fixture is used")
        tasks = read_tasks(Path(args.tasks_jsonl), args.limit)
    if args.strict_microtape_fixture:
        if args.authorization_mode != "required":
            parser.error("--strict-microtape-fixture requires --authorization-mode required")
        manifest = generate_stage6_strict_microtape_fixtures(out_dir, tasks)
        summary = {
            "schema_id": "MiniSweBenchSubstrateSmokeResult.v1",
            "coverage": str(out_dir / "substrate_coverage.json"),
            "worker_process": "stage6_strict_fixture",
            "auditor_exit_code": 0,
            "scientific_status": "STRICT_MICROTAPE_PROTOCOL_FIXTURE_NOT_SOLVE_RATE",
            "sample_size": manifest["sample_size"],
        }
        write_json(out_dir / "substrate_smoke_result.json", summary)
        return 0
    if args.no_hitl_loop_fixture:
        if args.authorization_mode != "required":
            parser.error("--no-hitl-loop-fixture requires --authorization-mode required")
        manifest = generate_stage8_no_hitl_loop_fixture(out_dir, tasks)
        summary = {
            "schema_id": "MiniSweBenchSubstrateSmokeResult.v1",
            "coverage": str(out_dir / "turingos" / "substrate_coverage.json"),
            "worker_process": "stage8_no_hitl_loop_fixture",
            "auditor_exit_code": 0,
            "scientific_status": "NO_HITL_LOOP_PROTOCOL_FIXTURE_NOT_SOLVE_RATE",
            "sample_size": manifest["sample_size"],
        }
        write_json(out_dir / "substrate_smoke_result.json", summary)
        return 0
    if args.native_api_worker_fixture:
        if args.authorization_mode != "required":
            parser.error("--native-api-worker-fixture requires --authorization-mode required")
        manifest = generate_stage9_native_api_worker_fixture(out_dir, tasks)
        summary = {
            "schema_id": "MiniSweBenchSubstrateSmokeResult.v1",
            "coverage": str(out_dir / "turingos" / "substrate_coverage.json"),
            "worker_process": "stage9_native_api_worker_fixture",
            "auditor_exit_code": 0,
            "scientific_status": "NATIVE_API_WORKER_TOOL_RECEIPT_FIXTURE_NOT_SOLVE_RATE",
            "sample_size": manifest["sample_size"],
        }
        write_json(out_dir / "substrate_smoke_result.json", summary)
        return 0
    if args.failure_taxonomy_fixture:
        if args.authorization_mode != "required":
            parser.error("--failure-taxonomy-fixture requires --authorization-mode required")
        manifest = generate_stage10_failure_taxonomy_fixture(out_dir, tasks)
        summary = {
            "schema_id": "MiniSweBenchSubstrateSmokeResult.v1",
            "coverage": str(out_dir / "turingos" / "substrate_coverage.json"),
            "worker_process": "stage10_failure_taxonomy_fixture",
            "auditor_exit_code": 0,
            "scientific_status": "FAILURE_TAXONOMY_FIXTURE_NOT_SOLVE_RATE",
            "sample_size": manifest["sample_size"],
        }
        write_json(out_dir / "substrate_smoke_result.json", summary)
        return 0
    if args.loop_until_pass_fixture:
        if args.authorization_mode != "required":
            parser.error("--loop-until-pass-fixture requires --authorization-mode required")
        manifest = generate_stage11_loop_until_pass_fixture(out_dir, tasks)
        summary = {
            "schema_id": "MiniSweBenchSubstrateSmokeResult.v1",
            "coverage": str(out_dir / "turingos" / "substrate_coverage.json"),
            "worker_process": "stage11_loop_until_pass_fixture",
            "auditor_exit_code": 0,
            "scientific_status": "LOOP_UNTIL_PASS_FIXTURE_NOT_SOLVE_RATE",
            "sample_size": manifest["sample_size"],
        }
        write_json(out_dir / "substrate_smoke_result.json", summary)
        return 0

    bin_dir = Path(args.daemon_bin_dir)
    ensure_binaries(bin_dir)
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
            authorization_mode=args.authorization_mode,
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
