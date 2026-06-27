#!/usr/bin/env python3
"""Run DeepSeek MetaAI review for a benchmark smoke evidence directory.

MetaAI is advisory only. It cannot move Micro heads and its output is not truth.
The API key is read only from an environment variable and is never serialized.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-v4-pro"
DEFAULT_KEY_ENV = "DEEPSEEK_API_KEY"


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def read_optional(path: Path, limit: int = 6000) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[:limit]


def find_first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def find_substrate_dir(paths: list[Path]) -> Path | None:
    for path in paths:
        if (path / "substrate_coverage.json").exists():
            return path
    return None


def build_review_payload(evidence_dir: Path) -> tuple[str, dict[str, Any]]:
    substrate_dir = find_substrate_dir(
        [
            evidence_dir,
            evidence_dir / "turingos",
            evidence_dir / "turingos_incremental",
        ]
    )
    if substrate_dir is None:
        substrate_dir = evidence_dir
    coverage_audit = load_json(substrate_dir / "substrate_coverage_audit.json")
    coverage = load_json(substrate_dir / "substrate_coverage.json")
    smoke = load_json(substrate_dir / "substrate_smoke_result.json")
    runs = [run for run in coverage.get("turingos_arm_runs", []) if isinstance(run, dict)]
    first_run = runs[0] if runs else {}
    direct_roots = [evidence_dir / "direct", evidence_dir / "direct_incremental", evidence_dir]
    direct_results = []
    for direct_root in direct_roots:
        if not direct_root.exists():
            continue
        for result_path in sorted(direct_root.glob("direct_baseline_*/result.json")):
            direct_results.append(load_json(result_path))
    patch_eval = None
    patch_eval_path = find_first_existing(
        [
            evidence_dir / "patch_eval" / "patch_eval_summary.json",
            evidence_dir / "patch_eval_incremental" / "patch_eval_summary.json",
        ]
    )
    if patch_eval_path is not None:
        patch_eval = load_json(patch_eval_path)
    loop_eval = None
    loop_eval_path = evidence_dir / "loop_eval_summary.json"
    if loop_eval_path.exists():
        loop_eval = load_json(loop_eval_path)

    def worker_summary(run: dict[str, Any]) -> dict[str, Any]:
        worker_logs = substrate_dir / "instances" / str(run.get("instance_id", "")) / "worker_logs"
        return {
            "instance_id": run.get("instance_id"),
            "worker_mode": run.get("worker_mode"),
            "worker_id": run.get("worker_id"),
            "worker_exit_code": run.get("worker_exit_code"),
            "predicate_write_event_type": run.get("predicate_write_event_type"),
            "process_calls": run.get("process_calls"),
            "event_calls": run.get("event_calls"),
            "patch_hash": sha256_text(read_optional(worker_logs / "diff.patch", limit=100000)),
            "patch_excerpt": read_optional(worker_logs / "diff.patch"),
            "stderr_excerpt": read_optional(worker_logs / "stderr.txt", limit=2000),
        }

    first_worker_logs = substrate_dir / "instances" / str(first_run.get("instance_id", "")) / "worker_logs"
    context = {
        "schema_id": "MetaAIReviewContext.v1",
        "evidence_dir": str(evidence_dir),
        "substrate_smoke_result": smoke,
        "substrate_coverage_audit": coverage_audit,
        "turingos_workers": [worker_summary(run) for run in runs],
        "turingos_patch_hash": sha256_text(read_optional(first_worker_logs / "diff.patch", limit=100000)),
        "turingos_patch_excerpt": read_optional(first_worker_logs / "diff.patch"),
        "turingos_worker_stdout_excerpt": read_optional(first_worker_logs / "stdout.txt", limit=2000),
        "turingos_worker_stderr_excerpt": read_optional(first_worker_logs / "stderr.txt", limit=2000),
        "direct_baseline_results": direct_results,
        "patch_eval_summary": patch_eval,
        "loop_eval_summary": loop_eval,
        "truth_boundary": {
            "meta_ai_authority": "none",
            "accepted_head_policy": "predicate_only",
            "forbidden_truth_signals": [
                "worker_exit_code",
                "worker_self_report",
                "ci_green",
                "official_benchmark_label_without_tape_import",
                "meta_ai_opinion",
            ],
        },
    }
    prompt = (
        "You are the non-authority MetaAI auditor for a TuringOS real-worker Mini SWE-bench smoke.\n"
        "Audit the evidence for scientific meaning, substrate completeness, and truth-boundary violations.\n"
        "Return JSON only with keys: schema_id, verdict, findings, substrate_complete, benchmark_claim_allowed, next_required_gate.\n"
        "Allowed verdicts: PASS, WARN, FAIL. Do not include secrets.\n\n"
        + json.dumps(context, ensure_ascii=False, sort_keys=True)
    )
    return prompt, context


def write_json(path: Path, packet: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def call_deepseek(base_url: str, model: str, api_key: str, prompt: str, timeout: int) -> dict[str, Any]:
    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a concise scientific auditor. Return JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "stream": False,
        "response_format": {"type": "json_object"},
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")
    parsed = json.loads(raw)
    content = parsed["choices"][0]["message"]["content"]
    try:
        review = json.loads(content)
    except json.JSONDecodeError:
        review = {"schema_id": "DeepSeekMetaAIReview.v1", "verdict": "FAIL", "raw_content": content}
    return {
        "raw_response_hash": sha256_text(raw),
        "review_content_hash": sha256_text(content),
        "review": review,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key-env", default=DEFAULT_KEY_ENV)
    parser.add_argument("--timeout-s", type=int, default=120)
    args = parser.parse_args(argv)

    evidence_dir = Path(args.evidence_dir)
    out = Path(args.out)
    api_key = os.environ.get(args.api_key_env)
    base_packet = {
        "schema_id": "DeepSeekMetaAIReviewRun.v1",
        "provider": "deepseek",
        "model": args.model,
        "base_url": args.base_url,
        "api_key_env": args.api_key_env,
        "credential_material": "env_only_not_serialized",
        "authority": "none",
        "accepted_head_authority": False,
    }
    if not api_key:
        packet = {
            **base_packet,
            "status": "NOT_RUN",
            "missing_env": [args.api_key_env],
            "request_hash": None,
            "context_hash": None,
            "review": None,
        }
        write_json(out, packet)
        return 2

    prompt, context = build_review_payload(evidence_dir)
    base_packet = {
        **base_packet,
        "request_hash": sha256_text(prompt),
        "context_hash": sha256_text(json.dumps(context, ensure_ascii=False, sort_keys=True)),
    }

    try:
        result = call_deepseek(args.base_url, args.model, api_key, prompt, args.timeout_s)
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        packet = {
            **base_packet,
            "status": "API_ERROR",
            "http_status": error.code,
            "error_body_hash": sha256_text(body),
            "error_excerpt": body[:1000],
            "review": None,
        }
        write_json(out, packet)
        return 1
    except Exception as error:  # noqa: BLE001 - evidence runner must record external failures.
        packet = {
            **base_packet,
            "status": "ERROR",
            "error": str(error),
            "review": None,
        }
        write_json(out, packet)
        return 1

    packet = {
        **base_packet,
        "status": "PASS",
        **result,
    }
    write_json(out, packet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
