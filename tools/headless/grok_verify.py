#!/usr/bin/env python3
"""G12-A Grok independent-verifier wrapper.

The wrapper is the consumed interface, not raw Grok text. It records deterministic
preconditions first and fails closed when the selected repo cannot satisfy the
Foundation P0 closure contract.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from headless_common import (
    NO_HUMAN_STATE_CEILING,
    attach_packet_digest,
    base_env_digest,
    clean_fixture_pass,
    detect_missing_foundation_primitives,
    forbidden_claims_present,
    gate_result,
    git_commit,
    git_remote,
    git_tree_digest,
    load_json,
    maybe_sha256_path,
    packet_digest,
    platform_not_run,
    print_packet_summary,
    sha256_path,
    stream_digest,
    tampered_fixture_fail,
    utc_now,
    which_digest,
    write_json,
)


def git_candidate_available(repo: Path, candidate: str) -> bool:
    try:
        proc = subprocess.run(
            ["git", "cat-file", "-e", f"{candidate}^{{commit}}"],
            cwd=repo,
            text=True,
            capture_output=True,
        )
    except OSError:
        return False
    return proc.returncode == 0


def make_clean_clone(repo: Path, candidate: str) -> tuple[Path | None, str | None]:
    if not git_candidate_available(repo, candidate):
        return None, None
    temp = Path(tempfile.mkdtemp(prefix="turingos-grok-clean-"))
    clone = temp / "clone"
    proc = subprocess.run(
        ["git", "clone", "--quiet", "--no-local", str(repo), str(clone)],
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        shutil.rmtree(temp, ignore_errors=True)
        return None, None
    proc = subprocess.run(["git", "checkout", "--quiet", candidate], cwd=clone)
    if proc.returncode != 0:
        shutil.rmtree(temp, ignore_errors=True)
        return None, None
    return clone, str(temp)


def maybe_run_grok(clone: Path, book: Path, evidence: Path) -> tuple[int, str, str, dict]:
    grok, _digest = which_digest("grok")
    if grok is None:
        return 127, "", "grok CLI missing", {}
    schema = {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["PASS", "FAIL", "NOT_RUN"]},
            "summary": {"type": "string"},
            "blocking_reasons": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["verdict", "summary", "blocking_reasons"],
        "additionalProperties": False,
    }
    prompt = (
        "You are the independent verifier for TuringOS Foundation. "
        "Return JSON only. Treat missing Rust authority-kernel evidence, missing "
        "runsc RED/GREEN evidence, or human-only signature gaps as blocking. "
        f"Project book: {book}\nEvidence bundle: {evidence}\n"
    )
    proc = subprocess.run(
        [
            grok,
            "-p",
            prompt,
            "--cwd",
            str(clone),
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(schema, separators=(",", ":")),
            "--disable-web-search",
            "--max-turns",
            "1",
        ],
        text=True,
        capture_output=True,
        timeout=300,
    )
    parsed: dict = {}
    if proc.stdout.strip():
        try:
            parsed = json.loads(proc.stdout)
        except json.JSONDecodeError:
            parsed = {}
    return proc.returncode, proc.stdout, proc.stderr, parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--book", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    script = Path(__file__).resolve()
    repo = script.parents[2]
    book = Path(args.book)
    evidence = Path(args.evidence)
    out = Path(args.out)
    gate_dir = out.parent / "gate_results"

    grok_path, grok_digest = which_digest("grok")
    not_run: list[str] = []
    if grok_path is None:
        not_run.append("grok_cli_missing")
    if not book.exists():
        not_run.append("project_book_missing")
    if not evidence.exists():
        not_run.append("evidence_bundle_missing")
    if not git_candidate_available(repo, args.candidate):
        not_run.append("candidate_unavailable")
    not_run.extend(platform_not_run())

    evidence_bundle = load_json(evidence) if evidence.exists() else {}
    for item in evidence_bundle.get("not_run", []):
        not_run.append(f"evidence:{item}")

    clone: Path | None = None
    temp_root: str | None = None
    if "candidate_unavailable" not in not_run:
        clone, temp_root = make_clean_clone(repo, args.candidate)
        if clone is None:
            not_run.append("clean_clone_failed")
        else:
            not_run.extend(detect_missing_foundation_primitives(clone))

    stdout = ""
    stderr = ""
    grok_packet: dict = {}
    external_invocation = {
        "schema_id": "ExternalAgentInvocation.v1",
        "agent_id": "grok_build_verifier",
        "model_family": "grok",
        "role": "independent_verifier",
        "command_argv": [],
        "cwd": str(clone) if clone else None,
        "clean_clone_digest": git_tree_digest(clone) if clone else None,
        "stdin_digest": None,
        "stdout_digest": stream_digest(""),
        "stderr_digest": stream_digest(""),
        "exit_status": None,
        "env_allowlist_digest": base_env_digest(),
        "tool_binary_digest": grok_digest,
        "source_write_permission": False,
        "key_ids_visible_to_agent": [],
        "produced_packet_path": str(out),
        "produced_packet_digest": None,
    }

    # Deterministic blockers dominate. Grok cannot convert missing platform facts into PASS.
    if not not_run and clone is not None:
        try:
            rc, stdout, stderr, grok_packet = maybe_run_grok(clone, book, evidence)
        except subprocess.TimeoutExpired as e:
            rc, stdout, stderr, grok_packet = 124, e.stdout or "", e.stderr or "grok timed out", {}
        external_invocation["command_argv"] = ["grok", "-p", "<prompt>", "--cwd", str(clone), "--output-format", "json"]
        external_invocation["stdout_digest"] = stream_digest(stdout)
        external_invocation["stderr_digest"] = stream_digest(stderr)
        external_invocation["exit_status"] = rc
        if rc != 0:
            not_run.append("grok_cli_failed")
        elif grok_packet.get("verdict") != "PASS":
            not_run.append("grok_model_not_pass")

    not_run = sorted(set(not_run))
    verdict = "NOT_RUN" if not_run else "PASS"
    reasons = [
        {
            "id": "clean_read_only_clone",
            "verdict": "PASS" if clone is not None else "NOT_RUN",
            "clone_digest": git_tree_digest(clone) if clone else None,
        },
        {
            "id": "real_linux_pinned_runsc",
            "verdict": "PASS" if "runsc_missing" not in not_run and "linux_required" not in not_run else "NOT_RUN",
        },
        {
            "id": "rust_authority_kernel_evidence",
            "verdict": "PASS"
            if not any(x.endswith("rust_authority_kernel_missing") for x in not_run)
            else "NOT_RUN",
        },
    ]
    report = {
        "schema_id": "GrokVerificationReport.v1",
        "created_at": utc_now(),
        "candidate": args.candidate,
        "working_repo": {
            "path": str(repo),
            "remote": git_remote(repo),
            "current_commit": git_commit(repo),
        },
        "project_book": str(book),
        "project_book_digest": maybe_sha256_path(book),
        "evidence_bundle": str(evidence),
        "evidence_bundle_digest": maybe_sha256_path(evidence),
        "verdict": verdict,
        "reasons": reasons,
        "not_run": not_run,
        "closure_certificate": None,
        "external_invocation": external_invocation,
        "model_packet": grok_packet,
        "state_ceiling": NO_HUMAN_STATE_CEILING,
        "m2_status": "DISABLED",
        "forbidden_claims_present": forbidden_claims_present([json.dumps(grok_packet), " ".join(not_run)]),
    }
    report = attach_packet_digest(report)
    write_json(out, report)
    external_invocation["produced_packet_digest"] = packet_digest(report)

    gate = gate_result(
        gate_id="G12-A",
        phase_id="F8",
        command_argv=[
            "python3",
            str(script.relative_to(repo)),
            "--candidate",
            args.candidate,
            "--book",
            str(book),
            "--evidence",
            str(evidence),
            "--out",
            str(out),
        ],
        exit_status=0 if verdict == "PASS" else 1,
        reasons=reasons,
        not_run=not_run,
        tool_path=script,
        input_paths=[book, evidence],
        output_path=out,
        stdout=stdout,
        stderr=stderr,
        clean_fixture_results=[clean_fixture_pass()],
        tampered_fixture_results=[tampered_fixture_fail()],
    )
    write_json(gate_dir / "G12-A.json", gate)
    if temp_root:
        shutil.rmtree(temp_root, ignore_errors=True)
    print_packet_summary(report)
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
