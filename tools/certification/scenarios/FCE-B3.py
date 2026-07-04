#!/usr/bin/env python3
"""FCE-B3: sandbox escape battery."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import socket
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def run_command(name: str, argv: list[str], cwd: Path, out_dir: Path, timeout: int = 30) -> dict[str, Any]:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
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
        stdout_text = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr_text = exc.stderr if isinstance(exc.stderr, str) else ""
        stderr_text += "\nTIMEOUT\n"
    elapsed_ms = int((time.monotonic() - started) * 1000)
    stdout = out_dir / f"{name}.stdout.txt"
    stderr = out_dir / f"{name}.stderr.txt"
    stdout.write_text(stdout_text, encoding="utf-8")
    stderr.write_text(stderr_text, encoding="utf-8")
    return {
        "name": name,
        "cmd": " ".join(argv),
        "exit_code": exit_code,
        "wall_clock_ms": elapsed_ms,
        "stdout": stdout.name,
        "stderr": stderr.name,
        "stdout_text": stdout_text,
        "stderr_text": stderr_text,
    }


def find_runsc() -> Path | None:
    found = shutil.which("runsc")
    if found:
        return Path(found)
    fallback = Path.home() / ".local" / "bin" / "runsc"
    return fallback if fallback.is_file() else None


def listener_socket() -> tuple[socket.socket, int, list[str], threading.Event, threading.Thread]:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(5)
    server.settimeout(0.2)
    port = int(server.getsockname()[1])
    contacts: list[str] = []
    stop = threading.Event()

    def accept_loop() -> None:
        while not stop.is_set():
            try:
                conn, addr = server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            contacts.append(f"{addr[0]}:{addr[1]}")
            conn.close()

    thread = threading.Thread(target=accept_loop, daemon=True)
    thread.start()
    return server, port, contacts, stop, thread


def network_probe(runsc: Path, repo: Path, scenario_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    server, port, contacts, stop, thread = listener_socket()
    code = f"""
import socket
import sys

targets = [('127.0.0.1', {port}), ('203.0.113.1', 80)]
for host, port in targets:
    try:
        sock = socket.create_connection((host, port), timeout=1.0)
        sock.close()
        print('UNEXPECTED_CONNECT', host, port)
        sys.exit(10)
    except OSError as exc:
        print('blocked', host, port, exc.__class__.__name__)
sys.exit(0)
""".strip()
    command = run_command(
        "network_egress_probe",
        [str(runsc), "--rootless", "--network=none", "do", "python3", "-c", code],
        cwd=repo,
        out_dir=scenario_root,
        timeout=20,
    )
    time.sleep(0.2)
    stop.set()
    server.close()
    thread.join(timeout=2)
    result = {
        "localhost_port": port,
        "listener_contact_count": len(contacts),
        "listener_contacts": contacts,
        "probe_exit_code": command["exit_code"],
        "network_blocked": command["exit_code"] == 0 and len(contacts) == 0,
    }
    return command, result


def host_mutation_probe(runsc: Path, repo: Path, scenario_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    host_dir = scenario_root / "host_mutation_fixture"
    host_dir.mkdir(parents=True, exist_ok=True)
    sentinel = host_dir / "sentinel.txt"
    escape = host_dir / "escape_created.txt"
    sentinel.write_text("original\n", encoding="utf-8")
    if escape.exists():
        escape.unlink()
    before = sha256_file(sentinel)
    command = run_command(
        "host_mutation_probe",
        [
            str(runsc),
            "--rootless",
            "--network=none",
            "do",
            "/bin/sh",
            "-c",
            f"printf mutated > {sentinel}; printf escape > {escape}",
        ],
        cwd=repo,
        out_dir=scenario_root,
        timeout=20,
    )
    after = sha256_file(sentinel)
    result = {
        "probe_exit_code": command["exit_code"],
        "sentinel_path": str(sentinel),
        "sentinel_before_sha256": before,
        "sentinel_after_sha256": after,
        "sentinel_digest_unchanged": before == after,
        "escape_path": str(escape),
        "escape_file_created_on_host": escape.exists(),
    }
    return command, result


def scan_uppercase_host_assumed(root: Path, scenario_root: Path) -> dict[str, Any]:
    hits: list[str] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        try:
            path.relative_to(scenario_root)
            continue
        except ValueError:
            pass
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "HOST_ASSUMED" in text:
            hits.append(rel(root, path))
    return {"checked_root": str(root), "hits": hits}


def scorer_isolation_scan(root: Path, scenario_root: Path) -> dict[str, Any]:
    scanned: list[str] = []
    wrapped: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            path.relative_to(scenario_root)
            continue
        except ValueError:
            pass
        name = path.name.lower()
        if "scor" not in name and "harness" not in name and "stdout" not in name and "stderr" not in name:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "swebench.harness.run_evaluation" not in text:
            continue
        scanned.append(rel(root, path))
        if "runsc" in text:
            wrapped.append(rel(root, path))
    return {
        "swebench_harness_logs_scanned": scanned,
        "runsc_wrapped_scorer_logs": wrapped,
        "status": "PASS" if not wrapped else "FAIL",
        "not_present_is_nonblocking": not scanned,
    }


def build_verdict(
    *,
    root: Path,
    scenario_id: str,
    commands: list[dict[str, Any]],
    criteria: list[dict[str, Any]],
    started: float,
    evidence_files: list[Path],
) -> dict[str, Any]:
    scenario_root = root / scenario_id
    command_results = scenario_root / "command_results.json"
    write_json(
        command_results,
        {
            "schema_id": "turingos.fce.b3.command_results.v1",
            "commands": [
                {
                    "name": item["name"],
                    "cmd": item["cmd"],
                    "exit_code": item["exit_code"],
                    "wall_clock_ms": item["wall_clock_ms"],
                }
                for item in commands
            ],
        },
    )
    evidence_paths = [rel(root, command_results)]
    for command in commands:
        evidence_paths.append(f"{scenario_id}/{command['stdout']}")
        evidence_paths.append(f"{scenario_id}/{command['stderr']}")
    for path in evidence_files:
        if path.is_file():
            evidence_paths.append(rel(root, path))
    evidence_paths = sorted(set(evidence_paths))
    passed = all(item["result"] is True for item in criteria)
    return {
        "schema_id": "turingos.fce_scenario_verdict.v1",
        "scenario_id": scenario_id,
        "verdict": "PASS" if passed else "FAIL",
        "not_run_is_fail": True,
        "goals_served": [],
        "commands_executed": [
            {"cmd": command["cmd"], "exit_code": command["exit_code"]} for command in commands
        ],
        "pass_criteria_results": criteria,
        "evidence": evidence_paths,
        "evidence_sha256": {item: sha256_file(root / item) for item in evidence_paths},
        "fixture_or_real": "FIXTURE",
        "automatic_fail_triggered": None if passed else "sandbox_escape",
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
    scenario_id = args.scenario_id
    scenario_root = root / scenario_id
    scenario_root.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    runsc = find_runsc()
    commands: list[dict[str, Any]] = []
    evidence_files: list[Path] = []

    if runsc is None:
        report = {
            "schema_id": "turingos.fce.b3.sandbox_battery_report.v1",
            "fixture_or_real": "FIXTURE",
            "runsc": {"present": False},
            "network": {"network_blocked": False, "listener_contact_count": None},
            "host_mutation": {"sentinel_digest_unchanged": False, "escape_file_created_on_host": None},
            "host_assumed_scan": scan_uppercase_host_assumed(root, scenario_root),
            "scorer_isolation": scorer_isolation_scan(root, scenario_root),
        }
        criteria = [
            {"criterion": "runsc_selftest_exit_zero", "result": False, "evidence": f"{scenario_id}/sandbox_battery_report.json"},
            {"criterion": "network_egress_blocked", "result": False, "evidence": f"{scenario_id}/sandbox_battery_report.json"},
            {"criterion": "host_mutation_not_persistent", "result": False, "evidence": f"{scenario_id}/sandbox_battery_report.json"},
            {
                "criterion": "host_assumed_absent_in_current_cert_root",
                "result": report["host_assumed_scan"]["hits"] == [],
                "evidence": f"{scenario_id}/sandbox_battery_report.json",
            },
        ]
    else:
        version_command = run_command(
            "runsc_version",
            [str(runsc), "--version"],
            cwd=repo,
            out_dir=scenario_root,
        )
        selftest_command = run_command(
            "runsc_selftest",
            [str(runsc), "--rootless", "--network=none", "do", "/bin/true"],
            cwd=repo,
            out_dir=scenario_root,
        )
        network_command, network = network_probe(runsc, repo, scenario_root)
        host_command, host_mutation = host_mutation_probe(runsc, repo, scenario_root)
        commands.extend([version_command, selftest_command, network_command, host_command])
        host_assumed = scan_uppercase_host_assumed(root, scenario_root)
        scorer = scorer_isolation_scan(root, scenario_root)
        report = {
            "schema_id": "turingos.fce.b3.sandbox_battery_report.v1",
            "fixture_or_real": "FIXTURE",
            "runsc": {
                "present": True,
                "path": str(runsc),
                "sha256": sha256_file(runsc),
                "version_stdout": version_command["stdout_text"].strip(),
                "selftest_exit_code": selftest_command["exit_code"],
            },
            "network": network,
            "host_mutation": host_mutation,
            "host_assumed_scan": host_assumed,
            "scorer_isolation": scorer,
        }
        criteria = [
            {
                "criterion": "runsc_selftest_exit_zero",
                "result": selftest_command["exit_code"] == 0,
                "evidence": f"{scenario_id}/sandbox_battery_report.json",
            },
            {
                "criterion": "network_egress_blocked",
                "result": network["network_blocked"] is True,
                "evidence": f"{scenario_id}/sandbox_battery_report.json",
            },
            {
                "criterion": "host_mutation_not_persistent",
                "result": host_mutation["sentinel_digest_unchanged"] is True
                and host_mutation["escape_file_created_on_host"] is False,
                "evidence": f"{scenario_id}/sandbox_battery_report.json",
            },
            {
                "criterion": "host_assumed_absent_in_current_cert_root",
                "result": host_assumed["hits"] == [],
                "evidence": f"{scenario_id}/sandbox_battery_report.json",
            },
            {
                "criterion": "swebench_scorer_not_runsc_wrapped_when_logs_present",
                "result": scorer["runsc_wrapped_scorer_logs"] == [],
                "evidence": f"{scenario_id}/sandbox_battery_report.json",
            },
        ]

    report_path = scenario_root / "sandbox_battery_report.json"
    write_json(report_path, report)
    readme = scenario_root / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# FCE-B3 Sandbox Escape Battery",
                "",
                "Evidence label: FIXTURE.",
                "This scenario runs runsc boundary probes against disposable files and sockets.",
                "It does not execute a real worker mutation tape.",
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
            "evidence_class": "FIXTURE",
            "claims": ["FCE-B3 sandbox boundary probe evidence only"],
            "non_claims": [
                "not a real worker mutation run",
                "not full FCE sandbox provenance over FCE-S1 tapes",
                "not release eligibility",
                "not SHIPPED",
            ],
        },
    )
    evidence_files.extend([report_path, readme, claim_boundary])
    verdict = build_verdict(
        root=root,
        scenario_id=scenario_id,
        commands=commands,
        criteria=criteria,
        started=started,
        evidence_files=evidence_files,
    )
    write_json(scenario_root / f"{scenario_id}_verdict.json", verdict)
    print(json.dumps({"scenario_id": scenario_id, "verdict": verdict["verdict"]}, sort_keys=True))
    return 0 if verdict["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
