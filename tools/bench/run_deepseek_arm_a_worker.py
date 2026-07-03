#!/usr/bin/env python3
"""Run DeepSeek V4 Flash as the M3.P4 Arm A capsule-only worker."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
PLAN_ROOT = REPO.parent / "PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702"
DEFAULT_PRICE_TABLE = PLAN_ROOT / "m3_uplift_lab" / "PRICE_TABLE_M3_P4_DEEPSEEK_ONLY.json"
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_KEY_ENV = "DEEPSEEK_API_KEY"

sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import audit_worker_candidate_patch as candidate_audit  # noqa: E402
import run_deepseek_provider_canary as provider  # noqa: E402
from turingos import codec  # noqa: E402
from turingos.worker import cost as worker_cost  # noqa: E402


INTEGRITY_STATEMENT = (
    "I read only the worker-safe task_packet.json and worker_capsule.md. "
    "I did not read raw SWE-bench dataset rows, dataset patches, test patches, "
    "FAIL_TO_PASS, PASS_TO_PASS, official solution hints, gold patches, or hidden evaluator labels."
)


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def build_worker_request(
    *,
    model: str,
    capsule_text: str,
    max_tokens: int,
    thinking_type: str = "disabled",
    reasoning_effort: str | None = None,
) -> dict[str, Any]:
    if thinking_type not in {"enabled", "disabled"}:
        raise ValueError("thinking_type must be enabled or disabled")
    request = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a weak Arm A SWE-bench worker. Use only the worker-safe capsule. "
                    "Return only a source-code unified diff. Do not edit tests. "
                    "Do not mention hidden tests, gold patches, or evaluator labels."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Your first characters must be: diff --git \n"
                    "Produce one best-effort source-only unified diff for this SWE-bench task. "
                    "Do not wrap the diff in markdown fences and do not add explanation before or after it. "
                    "If uncertain, still return the best source-only patch you can infer.\n\n"
                    + capsule_text
                ),
            },
        ],
        "thinking": {"type": thinking_type},
        "stream": False,
        "max_tokens": max_tokens,
    }
    if reasoning_effort is not None:
        request["reasoning_effort"] = reasoning_effort
    return request


def load_worker_visible_context(
    capsule_path: Path,
    *,
    source_context_name: str | None = None,
    extra_context_file: Path | None = None,
) -> tuple[str, dict[str, Any]]:
    capsule_text = capsule_path.read_text(encoding="utf-8")
    metadata: dict[str, Any] = {}
    parts = [capsule_text.rstrip()]
    if source_context_name:
        source_context_path = capsule_path.parent / source_context_name
        if source_context_path.exists():
            source_context_text = source_context_path.read_text(encoding="utf-8")
            metadata.update(
                {
                    "source_context_path": str(source_context_path),
                    "source_context_sha256": provider.sha256_text(source_context_text),
                    "source_context_length_chars": len(source_context_text),
                }
            )
            parts.extend(["## Worker-Visible Repository Source Context", source_context_text.strip()])
    if extra_context_file is not None and extra_context_file.exists():
        extra_context_text = extra_context_file.read_text(encoding="utf-8")
        metadata.update(
            {
                "extra_context_path": str(extra_context_file),
                "extra_context_sha256": provider.sha256_text(extra_context_text),
                "extra_context_length_chars": len(extra_context_text),
            }
        )
        parts.extend(["## Worker-Visible Extra Context", extra_context_text.strip()])
    return "\n\n".join(part for part in parts if part) + "\n", metadata


def integrity_statement(source_context_metadata: dict[str, Any]) -> str:
    visible_inputs = ["worker-safe task_packet.json", "worker_capsule.md"]
    if source_context_metadata.get("source_context_path"):
        visible_inputs.append("audited source_context.md selected from worker-derived candidate diff paths")
    if source_context_metadata.get("extra_context_path"):
        visible_inputs.append("recorded extra context file")
    return (
        "I read only the "
        + ", ".join(visible_inputs)
        + ". I did not read raw SWE-bench dataset rows, dataset patches, test patches, "
        "FAIL_TO_PASS, PASS_TO_PASS, official solution hints, gold patches, or hidden evaluator labels."
    )


def extract_unified_diff(text: str) -> str:
    start = text.find("diff --git ")
    if start < 0:
        return ""
    patch = text[start:]
    fence = patch.find("\n```")
    if fence >= 0:
        patch = patch[:fence]
    return normalize_unified_diff(patch)


def normalize_unified_diff(patch: str) -> str:
    if not patch:
        return ""
    normalized: list[str] = []
    in_hunk = False
    for line in patch.splitlines():
        if line.strip().startswith("```"):
            continue
        if line.startswith("diff --git "):
            in_hunk = False
        elif line.startswith("@@ "):
            in_hunk = True
        if in_hunk and line == "":
            normalized.append(" ")
        else:
            normalized.append(line)
    return "\n".join(normalized) + "\n"


def _apply_patch_to_temp_source(patch_text: str, apply_root: Path, *, recount: bool) -> tuple[bool, str, str]:
    with tempfile.TemporaryDirectory(prefix="turingos-worker-patch-") as tmp:
        tmp_path = Path(tmp)
        worktree = tmp_path / "worktree"
        shutil.copytree(apply_root, worktree)
        patch_path = tmp_path / "candidate.patch"
        patch_path.write_text(patch_text, encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=worktree, check=True)
        subprocess.run(["git", "add", "."], cwd=worktree, check=True)
        command = ["git", "apply", "--verbose"]
        if recount:
            command.append("--recount")
        command.append(str(patch_path))
        result = subprocess.run(
            command,
            cwd=worktree,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if result.returncode != 0:
            return False, result.stdout.strip(), ""
        diff = subprocess.run(
            ["git", "diff", "--no-ext-diff", "--no-color"],
            cwd=worktree,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
        ).stdout
    return True, result.stdout.strip(), normalize_unified_diff(diff)


def normalize_patch_against_source(patch_text: str, apply_root: Path) -> tuple[str, dict[str, Any]]:
    if not patch_text:
        return patch_text, {"status": "EMPTY"}
    missing_paths = [path for path in candidate_audit.diff_paths(patch_text) if not (apply_root / path).exists()]
    if missing_paths:
        return patch_text, {"status": "MISSING_PATHS", "missing_paths": missing_paths}

    direct_ok, direct_output, direct_diff = _apply_patch_to_temp_source(patch_text, apply_root, recount=False)
    if direct_ok:
        return direct_diff, {"status": "DIRECT", "output": direct_output}

    recount_ok, recount_output, recount_diff = _apply_patch_to_temp_source(patch_text, apply_root, recount=True)
    if recount_ok:
        return recount_diff, {
            "status": "RECOUNTED",
            "direct_output": direct_output,
            "output": recount_output,
        }

    return patch_text, {
        "status": "FAILED",
        "direct_output": direct_output,
        "recount_output": recount_output,
    }


def response_message(response: dict[str, Any]) -> dict[str, Any]:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("response.choices must be a non-empty list")
    first = choices[0]
    if not isinstance(first, dict) or not isinstance(first.get("message"), dict):
        raise ValueError("response.choices[0].message must be an object")
    return first["message"]


def cost_receipt(
    *,
    run_id: str,
    capsule_id: str,
    instance_id: str,
    model_requested: str,
    response_sha256: str,
) -> dict[str, Any]:
    receipt_hex = provider.hex_digest(
        {
            "run_id": run_id,
            "capsule_id": capsule_id,
            "instance_id": instance_id,
            "model_requested": model_requested,
            "response_sha256": response_sha256,
        }
    )
    return {
        "schema_id": "turingos.receipt.v1",
        "receipt_id": "rcpt:" + receipt_hex,
        "capsule_id": capsule_id,
        "worker_id": f"deepseek-arm-a:{model_requested}",
        "worktree_path": "/tmp/turingos-arm-a-worker",
        "candidate": {
            "tree_oid": response_sha256.removeprefix("sha256:"),
            "files_touched": [],
        },
        "declared_test_results": [],
        "status": "ok",
        "no_orphan": True,
    }


def build_worker_result_packet(
    *,
    root: Path,
    shard: str,
    window: str,
    instance_id: str,
    model_requested: str,
    request_payload: dict[str, Any],
    response: dict[str, Any],
    response_raw: str,
    wall_time_ms: int,
    price_table: dict[str, Any],
    source_capsule_path: Path,
    patch_text: str,
    source_context_metadata: dict[str, Any] | None = None,
    thinking_type: str = "disabled",
    reasoning_effort: str | None = None,
    patch_normalization: dict[str, Any] | None = None,
    experiment_phase: str = "m3-p4",
    run_id_prefix: str = "m3-p4-arm-a",
    split_label: str = "s02-pilot",
    agent_id: str = "m3-p4-deepseek-arm-a-worker",
    branch_id: str = "branch:m3-p4",
) -> dict[str, Any]:
    source_context_metadata = source_context_metadata or {}
    patch_normalization = patch_normalization or {"status": "NOT_REQUESTED"}
    message = response_message(response)
    content = message.get("content") or ""
    if not isinstance(content, str):
        raise ValueError("response content must be a string or null")
    reasoning_content = message.get("reasoning_content")
    if reasoning_content is not None and not isinstance(reasoning_content, str):
        raise ValueError("reasoning_content must be a string or null")
    raw_usage = response.get("usage")
    if not isinstance(raw_usage, dict):
        raise ValueError("response.usage must be an object")
    usage = provider.normalize_deepseek_usage(raw_usage)
    model_reported = str(response.get("model") or "")
    response_sha256 = provider.sha256_text(response_raw)
    request_sha256 = codec.content_digest(request_payload)
    capsule_id = "cap:" + provider.hex_digest(
        {
            "schema_id": "DeepSeekArmAWorkerCapsule.v1",
            "instance_id": instance_id,
            "source_capsule_sha256": provider.sha256_text(source_capsule_path.read_text(encoding="utf-8")),
            "request_sha256": request_sha256,
        }
    )
    cost_microusd = provider.deepseek_cost_microusd(
        model=model_requested,
        usage=usage,
        price_table=price_table,
    )
    run_id = f"{run_id_prefix}-{window}-{model_requested}"
    cost_event = worker_cost.cost_event_from_receipt(
        cost_receipt(
            run_id=run_id,
            capsule_id=capsule_id,
            instance_id=instance_id,
            model_requested=model_requested,
            response_sha256=response_sha256,
        ),
        run_id=run_id,
        problem_id=instance_id,
        split=split_label,
        agent_id=agent_id,
        branch_id=branch_id,
        adapter_kind="native_api",
        provider="deepseek",
        model_id_requested=model_requested,
        model_id_resolved=model_reported or "unknown",
        endpoint="https://api.deepseek.com/chat/completions",
        request_id=str(response.get("id") or response_sha256),
        response_sha256=response_sha256,
        usage=usage,
        cost_source_kind="provider_receipt_inline",
        cost_microusd=cost_microusd,
        wall_time_ms=wall_time_ms,
        provider_usage_raw=raw_usage,
        price_table_digest_value=codec.content_digest(price_table),
    )
    packet = {
        "schema_id": "turingos.m3.arm_a_worker_receipt.v1",
        "status": "COMPLETED",
        "experiment_phase": experiment_phase,
        "shard_id": shard,
        "ipqc_window_id": window,
        "instance_id": instance_id,
        "provider": "deepseek",
        "model_requested": model_requested,
        "model_reported": model_reported,
        "thinking": {"type": "disabled"},
        "candidate_source": "worker_derived",
        "submitted_patch_scope": "source_only",
        "source_capsule_path": str(source_capsule_path.relative_to(root)),
        "source_context_path": None,
        "source_context_sha256": None,
        "source_context_length_chars": 0,
        "patch_normalization": patch_normalization,
        "candidate_patch_sha256": provider.sha256_text(patch_text),
        "request_sha256": request_sha256,
        "response_sha256": response_sha256,
        "content_sha256": sha256_text(content),
        "content_length_chars": len(content),
        "reasoning_content_sha256": sha256_text(reasoning_content) if reasoning_content is not None else None,
        "reasoning_content_length_chars": len(reasoning_content) if reasoning_content is not None else 0,
        "usage": usage,
        "usage_raw_sha256": codec.content_digest(raw_usage),
        "cost_event": cost_event,
        "extra_context_path": None,
        "extra_context_sha256": None,
        "extra_context_length_chars": 0,
        "integrity_statement": integrity_statement(source_context_metadata),
        "wall_time_ms": wall_time_ms,
    }
    packet["thinking"] = {"type": thinking_type}
    if reasoning_effort is not None:
        packet["reasoning_effort"] = reasoning_effort
    context_path = source_context_metadata.get("source_context_path")
    if isinstance(context_path, str):
        path_obj = Path(context_path)
        try:
            packet["source_context_path"] = str(path_obj.relative_to(root))
        except ValueError:
            packet["source_context_path"] = context_path
        packet["source_context_sha256"] = source_context_metadata.get("source_context_sha256")
        packet["source_context_length_chars"] = source_context_metadata.get("source_context_length_chars", 0)
    extra_context_path = source_context_metadata.get("extra_context_path")
    if isinstance(extra_context_path, str):
        path_obj = Path(extra_context_path)
        try:
            packet["extra_context_path"] = str(path_obj.relative_to(root))
        except ValueError:
            packet["extra_context_path"] = extra_context_path
        packet["extra_context_sha256"] = source_context_metadata.get("extra_context_sha256")
        packet["extra_context_length_chars"] = source_context_metadata.get("extra_context_length_chars", 0)
    return packet


def worker_task_dirs(root: Path, shard: str, window: str) -> list[Path]:
    report_path = root / "shards" / shard / "ipqc" / window / "worker_safe_tasks" / "worker_safe_tasks_report.json"
    report = read_json(report_path)
    tasks = report.get("tasks")
    if report.get("status") != "PASS" or not isinstance(tasks, list):
        raise ValueError(f"worker-safe task report is not PASS: {report_path}")
    return [root / task["worker_capsule_path"] for task in tasks if isinstance(task, dict)]


def run_one_task(
    *,
    root: Path,
    shard: str,
    window: str,
    instance_id: str,
    capsule_path: Path,
    model: str,
    api_key: str,
    price_table: dict[str, Any],
    max_tokens: int,
    timeout_s: int,
    thinking_type: str,
    reasoning_effort: str | None,
    source_context_name: str | None,
    extra_context_file: Path | None,
    apply_root_dir: Path | None,
    experiment_phase: str,
    run_id_prefix: str,
    split_label: str,
    agent_id: str,
    branch_id: str,
) -> dict[str, Any]:
    capsule_text, source_context_metadata = load_worker_visible_context(
        capsule_path,
        source_context_name=source_context_name,
        extra_context_file=extra_context_file,
    )
    request_payload = build_worker_request(
        model=model,
        capsule_text=capsule_text,
        max_tokens=max_tokens,
        thinking_type=thinking_type,
        reasoning_effort=reasoning_effort,
    )
    response, response_raw, wall_time_ms = provider.call_deepseek(
        base_url=provider.DEFAULT_BASE_URL,
        endpoint=provider.DEFAULT_ENDPOINT,
        api_key=api_key,
        request_payload=request_payload,
        timeout_s=timeout_s,
    )
    content = response_message(response).get("content") or ""
    if not isinstance(content, str):
        raise ValueError("response content must be a string or null")
    patch_text = extract_unified_diff(content)
    apply_root = None
    if apply_root_dir is not None:
        per_task_apply_root = apply_root_dir / instance_id
        apply_root = per_task_apply_root if per_task_apply_root.exists() else apply_root_dir
    patch_normalization = {"status": "NOT_REQUESTED"}
    if apply_root is not None:
        patch_text, patch_normalization = normalize_patch_against_source(patch_text, apply_root)
    task_dir = root / "shards" / shard / "tasks" / instance_id
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "candidate.patch").write_text(patch_text, encoding="utf-8")
    receipt = build_worker_result_packet(
        root=root,
        shard=shard,
        window=window,
        instance_id=instance_id,
        model_requested=model,
        request_payload=request_payload,
        response=response,
        response_raw=response_raw,
        wall_time_ms=wall_time_ms,
        price_table=price_table,
        source_capsule_path=capsule_path,
        source_context_metadata=source_context_metadata,
        thinking_type=thinking_type,
        reasoning_effort=reasoning_effort,
        patch_normalization=patch_normalization,
        experiment_phase=experiment_phase,
        run_id_prefix=run_id_prefix,
        split_label=split_label,
        agent_id=agent_id,
        branch_id=branch_id,
        patch_text=patch_text,
    )
    write_json(task_dir / "worker_receipt.json", receipt)
    audit = candidate_audit.audit_candidate(root, shard, instance_id, apply_root=apply_root)
    return {
        "instance_id": instance_id,
        "status": receipt["status"],
        "model_reported": receipt["model_reported"],
        "candidate_patch_sha256": receipt["candidate_patch_sha256"],
        "candidate_patch_bytes": len(patch_text.encode("utf-8")),
        "candidate_audit_status": audit["status"],
        "candidate_audit_problems": audit["problems"],
        "cost_microusd": receipt["cost_event"]["cost"]["cost_microusd"],
        "usage": receipt["usage"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--shard", required=True)
    parser.add_argument("--window", required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--api-key-env", default=DEFAULT_KEY_ENV)
    parser.add_argument("--price-table", type=Path, default=DEFAULT_PRICE_TABLE)
    parser.add_argument("--max-tokens", type=int, default=12000)
    parser.add_argument("--timeout-s", type=int, default=240)
    parser.add_argument("--thinking", choices=["enabled", "disabled"], default="disabled")
    parser.add_argument("--reasoning-effort", choices=["high", "max"])
    parser.add_argument("--source-context-name")
    parser.add_argument("--extra-context-file", type=Path)
    parser.add_argument("--apply-root-dir", type=Path)
    parser.add_argument("--experiment-phase", default="m3-p4")
    parser.add_argument("--run-id-prefix", default="m3-p4-arm-a")
    parser.add_argument("--split-label", default="s02-pilot")
    parser.add_argument("--agent-id", default="m3-p4-deepseek-arm-a-worker")
    parser.add_argument("--branch-id", default="branch:m3-p4")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--instance-id")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    out = args.out or args.root / "shards" / args.shard / "arms" / "A_deepseek_flash_pilot" / "worker_run_summary.json"
    api_key = os.environ.get(args.api_key_env)
    base_summary = {
        "schema_id": "turingos.m3.arm_a_worker_run_summary.v1",
        "shard_id": args.shard,
        "ipqc_window_id": args.window,
        "provider": "deepseek",
        "model_requested": args.model,
        "experiment_phase": args.experiment_phase,
        "run_id_prefix": args.run_id_prefix,
        "split_label": args.split_label,
        "agent_id": args.agent_id,
        "branch_id": args.branch_id,
        "thinking": {"type": args.thinking},
        "reasoning_effort": args.reasoning_effort,
        "source_context_name": args.source_context_name,
        "extra_context_file": str(args.extra_context_file) if args.extra_context_file is not None else None,
        "apply_root_dir": str(args.apply_root_dir) if args.apply_root_dir is not None else None,
        "api_key_env": args.api_key_env,
        "credential_material": "env_only_not_serialized",
    }
    if not api_key:
        summary = {**base_summary, "status": "NOT_RUN", "missing_env": [args.api_key_env], "tasks": []}
        write_json(out, summary)
        return 2

    started = time.monotonic()
    price_table = provider.load_json(args.price_table)
    tasks = worker_task_dirs(args.root, args.shard, args.window)
    if args.instance_id:
        tasks = [path for path in tasks if path.parent.name == args.instance_id]
    if args.limit is not None:
        tasks = tasks[: args.limit]

    results: list[dict[str, Any]] = []
    problems: list[str] = []
    for capsule_path in tasks:
        instance_id = capsule_path.parent.name
        try:
            results.append(
                run_one_task(
                    root=args.root,
                    shard=args.shard,
                    window=args.window,
                    instance_id=instance_id,
                    capsule_path=capsule_path,
                    model=args.model,
                    api_key=api_key,
                    price_table=price_table,
                    max_tokens=args.max_tokens,
                    timeout_s=args.timeout_s,
                    thinking_type=args.thinking,
                    reasoning_effort=args.reasoning_effort,
                    source_context_name=args.source_context_name,
                    extra_context_file=args.extra_context_file,
                    apply_root_dir=args.apply_root_dir,
                    experiment_phase=args.experiment_phase,
                    run_id_prefix=args.run_id_prefix,
                    split_label=args.split_label,
                    agent_id=args.agent_id,
                    branch_id=args.branch_id,
                )
            )
        except urllib.error.HTTPError as error:
            body = error.read()
            problem = {
                "instance_id": instance_id,
                "status": "API_ERROR",
                "http_status": error.code,
                "error_body_sha256": provider.sha256_bytes(body),
            }
            results.append(problem)
            problems.append(f"{instance_id}: API_ERROR {error.code}")
        except Exception as error:  # noqa: BLE001 - live evidence runner records task failures.
            problem = {
                "instance_id": instance_id,
                "status": "ERROR",
                "error_type": type(error).__name__,
                "error_message": str(error),
            }
            results.append(problem)
            problems.append(f"{instance_id}: {type(error).__name__}: {error}")

    audit_failures = [
        f"{row['instance_id']}: candidate audit {row.get('candidate_audit_status')}"
        for row in results
        if row.get("candidate_audit_status") not in (None, "PASS")
    ]
    problems.extend(audit_failures)
    summary = {
        **base_summary,
        "status": "PASS" if not problems and len(results) == len(tasks) else "FAIL",
        "task_count_requested": len(tasks),
        "task_count_completed": sum(1 for row in results if row.get("status") == "COMPLETED"),
        "problems": problems,
        "tasks": results,
        "wall_time_ms": int((time.monotonic() - started) * 1000),
        "claim_boundary": {
            "arm": "A",
            "pilot_only": args.experiment_phase == "m3-p4",
            "confirmatory_s01": args.experiment_phase == "m3-p5" and args.shard == "S01",
            "no_turingos_loop": True,
            "no_failure_memory": True,
            "no_uplift_result": True,
        },
    }
    write_json(out, summary)
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
