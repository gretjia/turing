#!/usr/bin/env python3
"""Evaluate Django SWE-bench patches against task test_patch target tests."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any


def read_tasks(path: Path, limit: int) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            task = json.loads(line)
            tasks.append(task)
            if len(tasks) >= limit:
                break
    return tasks


def parse_fail_to_pass(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(item) for item in raw]
    if isinstance(raw, str):
        loaded = json.loads(raw)
        if not isinstance(loaded, list):
            raise ValueError("FAIL_TO_PASS string must decode to list")
        return [str(item) for item in loaded]
    raise ValueError("FAIL_TO_PASS must be a list or JSON string list")


def django_test_labels(fail_to_pass: list[str]) -> list[str]:
    labels: list[str] = []
    for item in fail_to_pass:
        if " (" in item and item.endswith(")"):
            test_name, class_path = item[:-1].split(" (", 1)
            labels.append(f"{class_path}.{test_name}")
        else:
            labels.append(item)
    return labels


def run_cmd(argv: list[str], *, cwd: Path | None = None, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=timeout)


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


def digest_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_forbidden_test_path(path: str) -> bool:
    normalized = path.lstrip("./")
    name = Path(normalized).name
    return (
        normalized.startswith("tests/")
        or "/tests/" in normalized
        or (name.startswith("test_") and name.endswith(".py"))
        or name.endswith("_test.py")
    )


def detect_forbidden_test_edits(diff_text: str) -> list[str]:
    paths: set[str] = set()
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            for token in parts[2:4]:
                if token.startswith(("a/", "b/")):
                    candidate = token[2:]
                    if is_forbidden_test_path(candidate):
                        paths.add(candidate)
        elif line.startswith(("+++ b/", "--- a/")):
            candidate = line[6:]
            if candidate != "/dev/null" and is_forbidden_test_path(candidate):
                paths.add(candidate)
    return sorted(paths)


def _status(result: dict[str, Any]) -> str:
    return str(result.get("status") or result.get("result") or "UNKNOWN")


def official_evaluator_evidence_payload(
    *,
    task: dict[str, Any],
    arm: str,
    candidate_patch_text: str,
    apply_candidate_result: dict[str, Any],
    apply_test_patch_result: dict[str, Any],
    target_test_result: dict[str, Any],
    capsule_id: str | None = None,
    macro_anchor_id: str | None = None,
    worker_receipt_id: str | None = None,
    worker_stop_class: str | None = None,
    failure_class_override: str | None = None,
) -> dict[str, Any]:
    forbidden_paths = detect_forbidden_test_edits(candidate_patch_text)
    candidate_status = _status(apply_candidate_result)
    test_patch_status = _status(apply_test_patch_result)
    target_status = _status(target_test_result)
    if failure_class_override is not None:
        result = "FAIL"
        failure_class = failure_class_override
    elif forbidden_paths:
        result = "FAIL"
        failure_class = "SCOPE_VIOLATION_TEST_EDIT"
    elif candidate_status != "PASS":
        result = "FAIL"
        failure_class = "PATCH_APPLY_FAILED"
    elif test_patch_status != "PASS":
        result = "FAIL"
        failure_class = "TEST_PATCH_APPLY_FAILED_AFTER_CANDIDATE_PATCH"
    elif target_status == "PASS":
        result = "PASS"
        failure_class = None
    else:
        result = "FAIL"
        failure_class = "OFFICIAL_EVAL_FAIL"
    stdout = str(target_test_result.get("stdout") or "")
    stderr = str(target_test_result.get("stderr") or "")
    evidence_id = "ev_official_" + hashlib.sha256(
        f"{task['instance_id']}:{arm}:{digest_text(candidate_patch_text)}".encode("utf-8")
    ).hexdigest()[:16]
    payload: dict[str, Any] = {
        "schema_id": "official_evaluator_evidence_imported.v1",
        "event_type": "OfficialEvaluatorEvidenceImported",
        "evidence_id": evidence_id,
        "instance_id": task["instance_id"],
        "arm": arm,
        "capsule_id": capsule_id,
        "macro_anchor_id": macro_anchor_id,
        "worker_receipt_id": worker_receipt_id,
        "candidate_patch_hash": digest_text(candidate_patch_text),
        "test_patch_hash": digest_text(str(task.get("test_patch", ""))),
        "apply_candidate_result": candidate_status,
        "apply_test_patch_result": test_patch_status,
        "fail_to_pass_labels": parse_fail_to_pass(task.get("FAIL_TO_PASS", [])),
        "target_test_exit_code": target_test_result.get("exit_code"),
        "target_test_result": target_status,
        "stdout_hash": digest_text(stdout),
        "stderr_hash": digest_text(stderr),
        "result": result,
        "failure_class": failure_class,
        "forbidden_test_edit_detected": bool(forbidden_paths),
        "forbidden_test_edit_paths": forbidden_paths,
        "truth_source": "official_evaluator_macro_evidence",
    }
    if worker_stop_class is not None:
        payload["worker_stop_class"] = worker_stop_class
    return payload


def candidate_payload_from_official_evidence(
    substrate_run: dict[str, Any],
    evidence_payload: dict[str, Any],
) -> dict[str, str]:
    return {
        "candidate_id": substrate_run.get("candidate_id") or f"cand_{substrate_run['instance_id']}",
        "capsule_id": substrate_run["capsule_id"],
        "macro_anchor_id": substrate_run["macro_anchor_id"],
        "worker_receipt_id": substrate_run["worker_receipt_id"],
        "official_evaluator_evidence_id": evidence_payload["evidence_id"],
    }


def broadcast_rule_from_evidence(evidence_payload: dict[str, Any]) -> dict[str, str] | None:
    failure_class = evidence_payload.get("failure_class")
    if failure_class is None:
        return None
    guidance_by_class = {
        "SCOPE_VIOLATION_TEST_EDIT": "Do not edit benchmark/official test files unless the task contract explicitly allows test changes.",
        "OFFICIAL_EVAL_FAIL": "Prefer the smallest production-code change that targets the failing behavior; preserve public API types unless the task explicitly asks otherwise.",
        "TEST_PATCH_APPLY_FAILED_AFTER_CANDIDATE_PATCH": "Avoid changes that conflict with benchmark test patches; do not modify files under benchmark test scopes.",
    }
    guidance = guidance_by_class.get(str(failure_class))
    if guidance is None:
        return None
    evidence_id = str(evidence_payload["evidence_id"])
    return {
        "rule_id": "br_" + evidence_id,
        "source_evidence_id": evidence_id,
        "source_instance_id": str(evidence_payload["instance_id"]),
        "failure_class": str(failure_class),
        "guidance": guidance,
    }


def load_substrate_runs(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    packet = json.loads(path.read_text(encoding="utf-8"))
    return {run["instance_id"]: run for run in packet.get("turingos_arm_runs", [])}


def micro_import_socket_path(runtime_root: Path, instance_id: str) -> Path:
    digest = hashlib.sha256(f"{runtime_root}:{instance_id}".encode("utf-8")).hexdigest()[:16]
    return Path("/tmp") / f"tos_eval_{digest}" / "d.sock"


def _substrate_ref_kwargs(substrate_run: dict[str, Any] | None) -> dict[str, str] | dict[str, None]:
    if substrate_run is None:
        return {
            "capsule_id": None,
            "macro_anchor_id": None,
            "worker_receipt_id": None,
        }
    return {
        "capsule_id": substrate_run["capsule_id"],
        "macro_anchor_id": substrate_run["macro_anchor_id"],
        "worker_receipt_id": substrate_run["worker_receipt_id"],
    }


def import_turingos_evidence_and_verify(
    *,
    substrate_run: dict[str, Any],
    evidence_payload: dict[str, Any],
    daemon_bin_dir: Path,
    runtime_root: Path,
) -> dict[str, Any]:
    socket_path = micro_import_socket_path(runtime_root, substrate_run["instance_id"])
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    socket_path.parent.chmod(0o700)
    if socket_path.exists():
        socket_path.unlink()
    proc = subprocess.Popen(
        [
            str(daemon_bin_dir / "turingd"),
            "--serve",
            "--socket",
            str(socket_path),
            "--micro-git",
            substrate_run["micro_git"],
            "--project",
            substrate_run["project"],
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.time() + 10
        while time.time() < deadline:
            if socket_path.exists():
                break
            if proc.poll() is not None:
                stderr = proc.stderr.read() if proc.stderr else ""
                raise RuntimeError(f"turingd exited before socket appeared: {stderr}")
            time.sleep(0.05)
        else:
            raise RuntimeError(f"turingd socket did not appear at {socket_path}")

        imported = rpc(
            socket_path,
            "event.append_preserve",
            {
                "event_type": "OfficialEvaluatorEvidenceImported",
                "writer_id": "writer:official-evaluator",
                "payload": evidence_payload,
            },
        )
        verify_params: dict[str, Any] = {
            "writer_id": "writer:predicate",
            "candidate_payload": candidate_payload_from_official_evidence(substrate_run, evidence_payload),
        }
        if evidence_payload["result"] != "PASS":
            verify_params["failure"] = {
                "candidate_digest": evidence_payload["candidate_patch_hash"],
                "observation_digest": evidence_payload["test_patch_hash"],
                "detail": evidence_payload.get("failure_class") or "official evaluator did not pass",
            }
        verified = rpc(socket_path, "candidate.verify_write", verify_params)
        return {
            "official_evidence_event_id": imported["event_id"],
            "candidate_write_event_type": verified["write_event_type"],
            "candidate_event_id": verified["event_id"],
            "predicate_product": verified["predicate_product"],
            "accepted_head_moved": verified["accepted_head_moved"],
        }
    finally:
        try:
            if socket_path.exists():
                rpc(socket_path, "daemon.shutdown", None)
        except Exception:
            proc.kill()
        proc.wait(timeout=5)


def ensure_django_venv(venv: Path) -> Path:
    python = venv / "bin" / "python"
    if python.exists():
        return python
    create = run_cmd(["python3", "-m", "venv", str(venv)], timeout=180)
    if create.returncode != 0:
        raise RuntimeError(f"venv create failed:\n{create.stderr}")
    pip = run_cmd([str(python), "-m", "pip", "install", "-q", "--upgrade", "pip"], timeout=300)
    if pip.returncode != 0:
        raise RuntimeError(f"pip upgrade failed:\n{pip.stderr}")
    deps = run_cmd([str(python), "-m", "pip", "install", "-q", "asgiref", "pytz", "sqlparse"], timeout=300)
    if deps.returncode != 0:
        raise RuntimeError(f"django deps install failed:\n{deps.stderr}")
    return python


def patch_path_for_arm(task: dict[str, Any], arm: str, root: Path) -> Path:
    instance_id = task["instance_id"]
    if arm == "turingos":
        return root / "instances" / instance_id / "worker_logs" / "diff.patch"
    if arm == "direct":
        return root / f"direct_baseline_{instance_id}" / "diff.patch"
    raise ValueError(f"unknown arm {arm}")


def evaluate_patch(
    task: dict[str, Any],
    arm: str,
    root: Path,
    out_dir: Path,
    work_root: Path,
    python: Path,
    substrate_run: dict[str, Any] | None = None,
) -> dict[str, Any]:
    instance_id = task["instance_id"]
    result_dir = out_dir / arm / instance_id
    result_dir.mkdir(parents=True, exist_ok=True)
    patch = patch_path_for_arm(task, arm, root)
    if task.get("repo") != "django/django":
        return {
            "instance_id": instance_id,
            "arm": arm,
            "result": "NOT_RUN",
            "reason": "only django/django target-test evaluation is supported by this smoke evaluator",
        }
    if not patch.exists() or not patch.read_text(encoding="utf-8", errors="replace").strip():
        patch_text = patch.read_text(encoding="utf-8", errors="replace") if patch.exists() else ""
        evidence = official_evaluator_evidence_payload(
            task=task,
            arm=arm,
            candidate_patch_text=patch_text,
            apply_candidate_result={"status": "NOT_RUN", "exit_code": None, "stdout": "", "stderr": ""},
            apply_test_patch_result={"status": "NOT_RUN", "exit_code": None, "stdout": "", "stderr": ""},
            target_test_result={"status": "NOT_RUN", "exit_code": None, "stdout": "", "stderr": ""},
            failure_class_override="MISSING_OR_EMPTY_PATCH",
            **_substrate_ref_kwargs(substrate_run),
        )
        return {
            "instance_id": instance_id,
            "arm": arm,
            "result": "FAIL",
            "reason": "missing_or_empty_patch",
            "official_evaluator_evidence": evidence,
        }
    patch_text = patch.read_text(encoding="utf-8", errors="replace")
    forbidden_paths = detect_forbidden_test_edits(patch_text)
    if forbidden_paths:
        evidence = official_evaluator_evidence_payload(
            task=task,
            arm=arm,
            candidate_patch_text=patch_text,
            apply_candidate_result={"status": "NOT_RUN", "exit_code": None, "stdout": "", "stderr": ""},
            apply_test_patch_result={"status": "NOT_RUN", "exit_code": None, "stdout": "", "stderr": ""},
            target_test_result={"status": "NOT_RUN", "exit_code": None, "stdout": "", "stderr": ""},
            **_substrate_ref_kwargs(substrate_run),
        )
        return {
            "instance_id": instance_id,
            "arm": arm,
            "result": "FAIL",
            "reason": "forbidden_test_file_edit",
            "forbidden_test_edit_paths": forbidden_paths,
            "official_evaluator_evidence": evidence,
        }

    eval_tree = work_root / f"{arm}_{instance_id}"
    if eval_tree.exists():
        shutil.rmtree(eval_tree)
    clone = run_cmd(
        ["git", "clone", "--filter=blob:none", "--no-checkout", "https://github.com/django/django.git", str(eval_tree)],
        timeout=900,
    )
    if clone.returncode != 0:
        return {"instance_id": instance_id, "arm": arm, "result": "ERROR", "reason": "clone_failed", "stderr": clone.stderr[-2000:]}
    checkout = run_cmd(["git", "-C", str(eval_tree), "checkout", task["base_commit"]], timeout=900)
    if checkout.returncode != 0:
        return {"instance_id": instance_id, "arm": arm, "result": "ERROR", "reason": "checkout_failed", "stderr": checkout.stderr[-2000:]}
    apply_patch = run_cmd(["git", "-C", str(eval_tree), "apply", str(patch.resolve())], timeout=180)
    if apply_patch.returncode != 0:
        evidence = official_evaluator_evidence_payload(
            task=task,
            arm=arm,
            candidate_patch_text=patch_text,
            apply_candidate_result={
                "status": "FAIL",
                "exit_code": apply_patch.returncode,
                "stdout": apply_patch.stdout,
                "stderr": apply_patch.stderr,
            },
            apply_test_patch_result={"status": "NOT_RUN", "exit_code": None, "stdout": "", "stderr": ""},
            target_test_result={"status": "NOT_RUN", "exit_code": None, "stdout": "", "stderr": ""},
            **_substrate_ref_kwargs(substrate_run),
        )
        return {
            "instance_id": instance_id,
            "arm": arm,
            "result": "FAIL",
            "reason": "patch_apply_failed",
            "stderr": apply_patch.stderr[-2000:],
            "official_evaluator_evidence": evidence,
        }
    test_patch = result_dir / "test.patch"
    test_patch.write_text(str(task.get("test_patch", "")), encoding="utf-8")
    apply_tests = run_cmd(["git", "-C", str(eval_tree), "apply", str(test_patch.resolve())], timeout=180)
    if apply_tests.returncode != 0:
        evidence = official_evaluator_evidence_payload(
            task=task,
            arm=arm,
            candidate_patch_text=patch_text,
            apply_candidate_result={
                "status": "PASS",
                "exit_code": apply_patch.returncode,
                "stdout": apply_patch.stdout,
                "stderr": apply_patch.stderr,
            },
            apply_test_patch_result={
                "status": "FAIL",
                "exit_code": apply_tests.returncode,
                "stdout": apply_tests.stdout,
                "stderr": apply_tests.stderr,
            },
            target_test_result={"status": "NOT_RUN", "exit_code": None, "stdout": "", "stderr": ""},
            **_substrate_ref_kwargs(substrate_run),
        )
        return {
            "instance_id": instance_id,
            "arm": arm,
            "result": "FAIL",
            "reason": "test_patch_apply_failed_after_candidate_patch",
            "stderr": apply_tests.stderr[-2000:],
            "official_evaluator_evidence": evidence,
        }
    labels = django_test_labels(parse_fail_to_pass(task["FAIL_TO_PASS"]))
    command = [
        str(python),
        str(eval_tree / "tests" / "runtests.py"),
        *labels,
        "--verbosity",
        "2",
    ]
    env = {"PYTHONPATH": str(eval_tree)}
    proc = subprocess.run(command, text=True, capture_output=True, timeout=600, env=env)
    (result_dir / "stdout.txt").write_text(proc.stdout, encoding="utf-8")
    (result_dir / "stderr.txt").write_text(proc.stderr, encoding="utf-8")
    evidence = official_evaluator_evidence_payload(
        task=task,
        arm=arm,
        candidate_patch_text=patch_text,
        apply_candidate_result={
            "status": "PASS",
            "exit_code": apply_patch.returncode,
            "stdout": apply_patch.stdout,
            "stderr": apply_patch.stderr,
        },
        apply_test_patch_result={
            "status": "PASS",
            "exit_code": apply_tests.returncode,
            "stdout": apply_tests.stdout,
            "stderr": apply_tests.stderr,
        },
        target_test_result={
            "status": "PASS" if proc.returncode == 0 else "FAIL",
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        },
        **_substrate_ref_kwargs(substrate_run),
    )
    return {
        "instance_id": instance_id,
        "arm": arm,
        "result": "PASS" if proc.returncode == 0 else "FAIL",
        "exit_code": proc.returncode,
        "target_tests": labels,
        "stdout": str(result_dir / "stdout.txt"),
        "stderr": str(result_dir / "stderr.txt"),
        "official_evaluator_evidence": evidence,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks-jsonl", required=True)
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--turingos-dir", required=True)
    parser.add_argument("--direct-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--work-root", default="/tmp/turingos_django_patch_eval")
    parser.add_argument("--venv", default="/tmp/turingos-django-swebench-venv")
    parser.add_argument("--substrate-coverage")
    parser.add_argument("--import-turingos-evidence", action="store_true")
    parser.add_argument("--daemon-bin-dir", default=str(Path(__file__).resolve().parents[2] / "target" / "debug"))
    args = parser.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    python = ensure_django_venv(Path(args.venv))
    tasks = read_tasks(Path(args.tasks_jsonl), args.limit)
    substrate_runs = load_substrate_runs(Path(args.substrate_coverage)) if args.substrate_coverage else {}
    results = []
    broadcast_rules: list[dict[str, str]] = []
    for task in tasks:
        turingos_result = evaluate_patch(
            task,
            "turingos",
            Path(args.turingos_dir),
            out,
            Path(args.work_root),
            python,
            substrate_runs.get(task["instance_id"]),
        )
        if args.import_turingos_evidence and task["instance_id"] in substrate_runs:
            evidence_payload = turingos_result.get("official_evaluator_evidence")
            if evidence_payload is not None:
                turingos_result["micro_tape_import"] = import_turingos_evidence_and_verify(
                    substrate_run=substrate_runs[task["instance_id"]],
                    evidence_payload=evidence_payload,
                    daemon_bin_dir=Path(args.daemon_bin_dir),
                    runtime_root=out / "micro_import_runtime",
                )
        evidence_payload = turingos_result.get("official_evaluator_evidence")
        if isinstance(evidence_payload, dict):
            rule = broadcast_rule_from_evidence(evidence_payload)
            if rule is not None:
                broadcast_rules.append(rule)
        results.append(turingos_result)
        results.append(evaluate_patch(task, "direct", Path(args.direct_dir), out, Path(args.work_root), python))
    by_arm = {"turingos": {"pass": 0, "total": 0}, "direct": {"pass": 0, "total": 0}}
    for result in results:
        arm = result["arm"]
        by_arm[arm]["total"] += 1
        if result["result"] == "PASS":
            by_arm[arm]["pass"] += 1
    packet = {
        "schema_id": "DjangoSweBenchPatchEval.v1",
        "sample_size": len(tasks),
        "results": results,
        "by_arm": by_arm,
        "broadcast_rules": broadcast_rules,
        "statistical_claim": "none_smoke_only",
    }
    (out / "patch_eval_summary.json").write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "broadcast_rules.json").write_text(
        json.dumps(
            {
                "schema_id": "BenchmarkBroadcastRules.v1",
                "source": "official_evaluator_evidence",
                "rules": broadcast_rules,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0 if all(result["result"] in {"PASS", "FAIL", "NOT_RUN"} for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
