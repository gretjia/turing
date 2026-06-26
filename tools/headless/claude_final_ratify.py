#!/usr/bin/env python3
"""G12-B Claude final-ratifier wrapper."""

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
    executed_clean_fixture,
    executed_tampered_fixture,
    forbidden_claims_present,
    gate_result,
    git_commit,
    git_remote,
    git_tree_digest,
    load_json,
    maybe_sha256_path,
    packet_digest,
    print_packet_summary,
    sha256_path,
    stream_digest,
    structured_output,
    utc_now,
    which_digest,
    write_json,
)


def build_claude_prompt(book: Path, evidence: Path, grok_report: Path) -> str:
    evidence_text = evidence.read_text(encoding="utf-8")
    grok_report_text = grok_report.read_text(encoding="utf-8")
    return (
        "You are Claude Code FinalRatifier for TuringOS Foundation. "
        "Return JSON only. Model ratification is not human ratification. "
        "Reject or NOT_RUN if Grok evidence, gate receipts, or autonomous mechanical "
        "supply-chain/test evidence is missing. Human-only genesis signature and "
        "independent verifier-key custody gaps should remain human decision requests; "
        "they do not prevent MODEL_RATIFIED when the candidate is mechanically ready "
        "for human genesis-signature review. Do not claim any human-ratified, "
        "OG-10-signed, foundation-ready, M2-enabled, or closed state. Do not spell "
        "restricted uppercase status identifiers in your response.\n"
        f"Project book path: {book}\n"
        f"EvidenceBundle.v1 JSON:\n{evidence_text}\n"
        f"GrokVerificationReport.v1 JSON:\n{grok_report_text}\n"
    )


def make_ratifier_clone(repo: Path, candidate: str) -> tuple[Path, str]:
    temp = Path(tempfile.mkdtemp(prefix="turingos-claude-ratifier-"))
    clone = temp / "clone"
    proc = subprocess.run(
        ["git", "clone", "--quiet", "--no-local", str(repo), str(clone)],
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        shutil.rmtree(temp, ignore_errors=True)
        raise RuntimeError(proc.stderr or "failed to clone ratifier repo")
    proc = subprocess.run(["git", "checkout", "--quiet", candidate], cwd=clone, text=True, capture_output=True)
    if proc.returncode != 0:
        shutil.rmtree(temp, ignore_errors=True)
        raise RuntimeError(proc.stderr or "failed to checkout ratifier candidate")
    return clone, str(temp)


def maybe_run_claude(
    book: Path, evidence: Path, grok_report: Path, ratifier_clone: Path
) -> tuple[int, str, str, dict]:
    claude, _digest = which_digest("claude")
    if claude is None:
        return 127, "", "claude CLI missing", {}
    schema = {
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["MODEL_RATIFIED", "MODEL_REJECTED", "NOT_RUN", "RETURN_TO_ARCHITECTURE"],
            },
            "summary": {"type": "string"},
            "blocking_reasons": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["verdict", "summary", "blocking_reasons"],
        "additionalProperties": False,
    }
    prompt = build_claude_prompt(book, evidence, grok_report)
    proc = subprocess.run(
        [
            claude,
            "-p",
            prompt,
            "--no-session-persistence",
            "--permission-mode",
            "plan",
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(schema, separators=(",", ":")),
        ],
        cwd=ratifier_clone,
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
    parser.add_argument("--grok-report", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    script = Path(__file__).resolve()
    repo = script.parents[2]
    book = Path(args.book).resolve()
    grok_report_path = Path(args.grok_report)
    evidence = Path(args.evidence).resolve()
    out = Path(args.out)
    gate_dir = out.parent / "gate_results"

    not_run: list[str] = []
    reason = None
    if not grok_report_path.exists():
        not_run.append("grok_report_missing")
        reason = "GROK_NOT_PASS"
        grok_report = {}
    else:
        grok_report = load_json(grok_report_path)
        if grok_report.get("verdict") != "PASS":
            not_run.append("grok_not_pass")
            reason = "GROK_NOT_PASS"
    if not book.exists():
        not_run.append("project_book_missing")
    if not evidence.exists():
        not_run.append("evidence_bundle_missing")

    claude_path, claude_digest = which_digest("claude")
    if claude_path is None and not not_run:
        not_run.append("claude_cli_missing")
        reason = "CLAUDE_CLI_MISSING"

    stdout = ""
    stderr = ""
    model_packet: dict = {}
    ratifier_clone: Path | None = None
    ratifier_temp_root: str | None = None
    external_invocation = {
        "schema_id": "ExternalAgentInvocation.v1",
        "agent_id": "claude_code_final_ratifier",
        "model_family": "claude",
        "role": "final_model_ratifier",
        "command_argv": [],
        "cwd": None,
        "clean_clone_digest": None,
        "stdin_digest": None,
        "stdout_digest": stream_digest(""),
        "stderr_digest": stream_digest(""),
        "exit_status": None,
        "env_allowlist_digest": base_env_digest(),
        "tool_binary_digest": claude_digest,
        "source_write_permission": False,
        "key_ids_visible_to_agent": [],
        "produced_packet_path": str(out),
        "produced_packet_digest": None,
    }

    if not not_run:
        try:
            ratifier_clone, ratifier_temp_root = make_ratifier_clone(repo, args.candidate)
            rc, stdout, stderr, model_packet = maybe_run_claude(book, evidence, grok_report_path, ratifier_clone)
        except subprocess.TimeoutExpired as e:
            rc, stdout, stderr, model_packet = 124, e.stdout or "", e.stderr or "claude timed out", {}
        except RuntimeError as e:
            rc, stdout, stderr, model_packet = 125, "", str(e), {}
        external_invocation["command_argv"] = ["claude", "-p", "<prompt>", "--permission-mode", "plan", "--output-format", "json"]
        external_invocation["cwd"] = str(ratifier_clone) if ratifier_clone else None
        external_invocation["clean_clone_digest"] = git_tree_digest(ratifier_clone) if ratifier_clone else None
        external_invocation["stdout_digest"] = stream_digest(stdout)
        external_invocation["stderr_digest"] = stream_digest(stderr)
        external_invocation["exit_status"] = rc
        if rc != 0:
            not_run.append("claude_cli_failed")
            reason = "CLAUDE_CLI_FAILED"
        elif structured_output(model_packet).get("verdict") != "MODEL_RATIFIED":
            reason = structured_output(model_packet).get("verdict", "MODEL_REJECTED")

    not_run = sorted(set(not_run))
    verdict = "NOT_RUN" if not_run else structured_output(model_packet).get("verdict", "MODEL_REJECTED")
    packet = {
        "schema_id": "FinalRatificationPacket.v1",
        "created_at": utc_now(),
        "candidate": args.candidate,
        "verdict": verdict,
        "reason": reason,
        "project_book": str(book),
        "project_book_digest": maybe_sha256_path(book),
        "grok_report": str(grok_report_path),
        "grok_report_digest": maybe_sha256_path(grok_report_path),
        "evidence_bundle": str(evidence),
        "evidence_bundle_digest": maybe_sha256_path(evidence),
        "external_invocation": external_invocation,
        "model_packet": model_packet,
        "model_structured_output": structured_output(model_packet),
        "not_run": not_run,
        "state_ceiling": NO_HUMAN_STATE_CEILING,
        "m2_status": "DISABLED",
        "forbidden_claims_present": forbidden_claims_present([json.dumps(model_packet), " ".join(not_run)]),
        "working_repo": {
            "path": str(repo),
            "remote": git_remote(repo),
            "current_commit": git_commit(repo),
        },
    }
    packet = attach_packet_digest(packet)
    write_json(out, packet)
    external_invocation["produced_packet_digest"] = packet_digest(packet)

    reasons = [
        {
            "id": "grok_pass_prerequisite",
            "verdict": "PASS" if grok_report.get("verdict") == "PASS" else "NOT_RUN",
        },
        {
            "id": "model_final_ratification",
            "verdict": "PASS" if verdict == "MODEL_RATIFIED" else "NOT_RUN",
        },
    ]
    gate = gate_result(
        gate_id="G12-B",
        phase_id="F8",
        command_argv=[
            "python3",
            str(script.relative_to(repo)),
            "--candidate",
            args.candidate,
            "--book",
            str(book),
            "--grok-report",
            str(grok_report_path),
            "--evidence",
            str(evidence),
            "--out",
            str(out),
        ],
        exit_status=0 if verdict == "MODEL_RATIFIED" else 1,
        reasons=reasons,
        not_run=not_run or ([] if verdict == "MODEL_RATIFIED" else ["model_not_ratified"]),
        tool_path=script,
        input_paths=[book, grok_report_path, evidence],
        output_path=out,
        stdout=stdout,
        stderr=stderr,
        clean_fixture_results=[executed_clean_fixture(repo, out.parent, "G12-B")],
        tampered_fixture_results=[executed_tampered_fixture(repo, out.parent, "G12-B")],
    )
    write_json(gate_dir / "G12-B.json", gate)
    if ratifier_temp_root:
        shutil.rmtree(ratifier_temp_root, ignore_errors=True)
    print_packet_summary(packet)
    return 0 if verdict == "MODEL_RATIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
