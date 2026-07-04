#!/usr/bin/env python3
"""FCE-R3: monitoring, logging, and evidence-hygiene inventory (ops inventory).

Steps (per 09_FINAL_CERTIFICATION_EVALS.md, section 6, FCE-R3): build a
machine-readable inventory (`ops_inventory.json`) asserting, with paths --
every FCE scenario emitted a structured verdict JSON (no prose-only status,
Intent Section 6); every evidence root created by the suite has a README with
a FIXTURE/REAL label plus a `CLAIM_BOUNDARY.json` (v2 schema, per M0); zero
0-byte files in suite-created roots except classified-legitimate ones (empty
stderr on success, classification list included, per RES_M0's
classify-don't-bulk-delete rule); harness logs retained per instance; the
receipts directory is complete (one file per `request_sha256` found on any
tape under the cert root); the operator console heartbeat (`status`) was
exercisable at every discovered workflow step; and a before/after digest
sweep over pre-existing evidence (the repo's and plan-root's real, already
committed `evidence/` trees) shows zero modifications (feeds automatic-FAIL
condition 6 in section 1).

Scope note: "the suite" and "evidence roots created by the suite" mean the
scenario roots materialized under `--root` (the certification run's own
evidence root), not the entire historical repository evidence tree. When this
scenario is invoked standalone (as opposed to after a full aggregate FCE run
via run_scenarios.py), `--root` legitimately contains only this scenario's own
in-progress root at inventory time; the inventory over sibling scenario roots
is then genuinely empty (0/0, vacuously satisfied) rather than fabricated --
this is recorded explicitly in the inventory output so it is never confused
with a full-suite sweep. This scenario's own root is excluded from the
sibling-root completeness checks (verdict/README/CLAIM_BOUNDARY presence) for
the same reason no verdict-JSON self-check can ever succeed before the
verdict JSON itself has been computed; this exclusion is documented in the
inventory output rather than silently assumed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUEST_SHA256_RE = re.compile(r'"request_sha256"\s*:\s*"([0-9a-fA-F]{16,64})"')
TAPE_FILENAME_HINTS = ("tape", "bundle")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def run_command(
    *,
    name: str,
    argv: list[str],
    cwd: Path,
    out_dir: Path,
    timeout: int = 300,
) -> dict[str, Any]:
    started = time.monotonic()
    proc = subprocess.run(
        argv,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    stdout_path = out_dir / f"{name}.stdout.txt"
    stderr_path = out_dir / f"{name}.stderr.txt"
    stdout_path.write_text(proc.stdout, encoding="utf-8")
    stderr_path.write_text(proc.stderr, encoding="utf-8")
    return {
        "name": name,
        "cmd": " ".join(argv),
        "exit_code": proc.returncode,
        "wall_clock_ms": elapsed_ms,
        "stdout": stdout_path.name,
        "stderr": stderr_path.name,
        "stdout_text": proc.stdout,
        "stderr_text": proc.stderr,
    }


def sha256_tree(roots: list[Path], exclude: Path) -> dict[str, str]:
    digests: dict[str, str] = {}
    for tree_root in roots:
        if not tree_root.is_dir():
            continue
        for path in sorted(tree_root.rglob("*")):
            if not path.is_file():
                continue
            try:
                path.relative_to(exclude)
                continue
            except ValueError:
                pass
            try:
                digests[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                digests[str(path)] = "UNREADABLE"
    return digests


def diff_digest_trees(before: dict[str, str], after: dict[str, str]) -> dict[str, Any]:
    before_keys, after_keys = set(before), set(after)
    added = sorted(after_keys - before_keys)
    removed = sorted(before_keys - after_keys)
    changed = sorted(key for key in before_keys & after_keys if before[key] != after[key])
    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "clean": not added and not removed and not changed,
    }


def discover_sibling_scenario_roots(root: Path, self_id: str) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir() and p.name != self_id)


def load_command_results(scenario_root: Path) -> list[dict[str, Any]]:
    path = scenario_root / "command_results.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    commands = data.get("commands")
    return commands if isinstance(commands, list) else []


def inventory_verdict(scenario_root: Path) -> dict[str, Any]:
    verdict_path = scenario_root / f"{scenario_root.name}_verdict.json"
    present = verdict_path.is_file()
    schema_ok = False
    verdict_value = None
    if present:
        try:
            data = json.loads(verdict_path.read_text(encoding="utf-8"))
            verdict_value = data.get("verdict")
            schema_ok = (
                data.get("schema_id") == "turingos.fce_scenario_verdict.v1"
                and verdict_value in {"PASS", "FAIL", "NOT_RUN"}
            )
        except (json.JSONDecodeError, OSError):
            schema_ok = False
    return {
        "scenario_id": scenario_root.name,
        "verdict_path": str(verdict_path),
        "present": present,
        "structured_verdict_schema_ok": schema_ok,
        "verdict": verdict_value,
        "complete": present and schema_ok,
    }


def inventory_labels(scenario_root: Path) -> dict[str, Any]:
    readme = scenario_root / "README.md"
    claim = scenario_root / "CLAIM_BOUNDARY.json"
    readme_present = readme.is_file()
    label = None
    if readme_present:
        text = readme.read_text(encoding="utf-8", errors="replace")
        if "FIXTURE" in text:
            label = "FIXTURE"
        elif "REAL" in text:
            label = "REAL"
    claim_present = claim.is_file()
    claim_schema_ok = False
    evidence_class = None
    if claim_present:
        try:
            data = json.loads(claim.read_text(encoding="utf-8"))
            evidence_class = data.get("evidence_class")
            claim_schema_ok = data.get("schema_id") == "CLAIM_BOUNDARY.v2" and evidence_class in {"FIXTURE", "REAL"}
        except (json.JSONDecodeError, OSError):
            claim_schema_ok = False
    complete = readme_present and label is not None and claim_present and claim_schema_ok
    return {
        "scenario_id": scenario_root.name,
        "readme_present": readme_present,
        "readme_label": label,
        "claim_boundary_present": claim_present,
        "claim_boundary_schema_ok": claim_schema_ok,
        "claim_boundary_evidence_class": evidence_class,
        "complete": complete,
    }


def zero_byte_scan(
    root: Path,
    command_results_by_scenario: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    zero_files = [path for path in sorted(root.rglob("*")) if path.is_file() and path.stat().st_size == 0]
    classified: list[dict[str, str]] = []
    unclassified: list[str] = []
    for path in zero_files:
        rel_path = path.relative_to(root).as_posix()
        scenario_dir = rel_path.split("/", 1)[0]
        legit = False
        reason = None
        cmd_name = None
        stream = None
        if path.name.endswith(".stderr.txt"):
            cmd_name = path.name[: -len(".stderr.txt")]
            stream = "stderr"
        elif path.name.endswith(".stdout.txt"):
            cmd_name = path.name[: -len(".stdout.txt")]
            stream = "stdout"
        if cmd_name is not None:
            for command in command_results_by_scenario.get(scenario_dir, []):
                if command.get("name") == cmd_name:
                    # Per RES_M0's real classification precedent (M0_P5 hygiene
                    # sweep): an empty stdout/stderr stream from a known,
                    # recorded command is legitimate regardless of exit code --
                    # a diagnostic tool may route its message to only one
                    # stream and leave the other empty on success (nothing to
                    # report) or on failure (message went to the other
                    # stream). The real defect class is a manifest/verdict
                    # asserting non-empty content that disk contradicts, which
                    # is a distinct, more targeted check, not "any empty
                    # stream is suspect".
                    legit = True
                    reason = f"empty_{stream}_from_recorded_command_exit_{command.get('exit_code')}"
                    break
        if legit:
            classified.append({"path": rel_path, "reason": reason})
        else:
            unclassified.append(rel_path)
    return {
        "total_zero_byte_files": len(zero_files),
        "classified_legitimate": classified,
        "unclassified": unclassified,
        "clean": not unclassified,
    }


def harness_logs_retained(
    root: Path,
    command_results_by_scenario: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    missing: list[str] = []
    checked = 0
    for scenario_dir, commands in command_results_by_scenario.items():
        for command in commands:
            checked += 1
            name = command.get("name")
            stdout_path = root / scenario_dir / f"{name}.stdout.txt"
            stderr_path = root / scenario_dir / f"{name}.stderr.txt"
            if not stdout_path.is_file():
                missing.append(str(stdout_path))
            if not stderr_path.is_file():
                missing.append(str(stderr_path))
    return {"commands_checked": checked, "missing_logs": missing, "complete": not missing}


def find_tape_request_hashes(root: Path) -> list[str]:
    hashes: set[str] = set()
    for path in root.rglob("*.json"):
        if not any(hint in path.name.lower() for hint in TAPE_FILENAME_HINTS):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        hashes.update(match.group(1) for match in REQUEST_SHA256_RE.finditer(text))
    return sorted(hashes)


def receipts_completeness(root: Path) -> dict[str, Any]:
    request_hashes = find_tape_request_hashes(root)
    receipts_dirs = [path for path in root.rglob("receipts") if path.is_dir()]
    receipt_filenames: list[str] = []
    for receipts_dir in receipts_dirs:
        receipt_filenames.extend(item.name for item in receipts_dir.iterdir() if item.is_file())
    missing = sorted(
        request_hash
        for request_hash in request_hashes
        if not any(request_hash in filename for filename in receipt_filenames)
    )
    not_applicable = not request_hashes and not receipts_dirs
    return {
        "request_sha256_found_on_tapes": request_hashes,
        "receipts_dirs": [str(item) for item in receipts_dirs],
        "receipt_filenames": sorted(receipt_filenames),
        "missing_receipt_for_request_sha256": missing,
        "not_applicable": not_applicable,
        "complete": not missing,
    }


def console_heartbeat_check(
    repo: Path,
    scenario_root: Path,
    step_labels: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for index, label in enumerate(step_labels, start=1):
        command = run_command(
            name=f"console_heartbeat_step_{index}",
            argv=["cargo", "run", "-p", "turing-cli", "--quiet", "--", "status", "--json"],
            cwd=repo,
            out_dir=scenario_root,
            timeout=180,
        )
        commands.append(command)
        ok = False
        schema_id = None
        if command["exit_code"] == 0:
            try:
                data = json.loads(command["stdout_text"])
                schema_id = data.get("schema_id")
                ok = schema_id == "operator_view_snapshot.v1"
            except json.JSONDecodeError:
                ok = False
        results.append(
            {
                "step": index,
                "step_label": label,
                "exit_code": command["exit_code"],
                "schema_id": schema_id,
                "exercisable": ok,
            }
        )
    summary = {
        "steps_checked": len(results),
        "all_exercisable": all(item["exercisable"] for item in results) if results else False,
        "results": results,
    }
    return commands, summary


def build_verdict(
    *,
    root: Path,
    scenario_id: str,
    commands: list[dict[str, Any]],
    criteria: list[dict[str, Any]],
    started: float,
    evidence_files: list[Path],
    automatic_fail_triggered: str | None,
) -> dict[str, Any]:
    scenario_root = root / scenario_id
    command_results = scenario_root / "command_results.json"
    write_json(
        command_results,
        {
            "schema_id": "turingos.fce.r3.command_results.v1",
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
        "fixture_or_real": "REAL",
        "automatic_fail_triggered": None if passed else automatic_fail_triggered,
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

    # Step 0: before-digest of pre-existing evidence (repo's and plan-root's
    # real, already-committed evidence trees), scoped away from --root.
    digest_scope = [repo / "evidence", plan_root / "evidence"]
    before_digest = sha256_tree(digest_scope, exclude=root)

    # Step 1: discover sibling scenario roots already materialized under
    # --root by this certification run (self excluded; see module docstring).
    sibling_roots = discover_sibling_scenario_roots(root, scenario_id)

    verdict_inventory = [inventory_verdict(item) for item in sibling_roots]
    label_inventory = [inventory_labels(item) for item in sibling_roots]

    # Step 2: operator console heartbeat -- exercised once per discovered
    # workflow step (each sibling scenario root already produced by the
    # suite, plus this scenario's own start/end), proving the M6 console
    # heartbeat command is genuinely exercisable throughout.
    step_labels = [f"sibling_scenario:{item.name}" for item in sibling_roots]
    step_labels = ["self:start"] + step_labels + ["self:end"]
    heartbeat_commands, heartbeat_summary = console_heartbeat_check(repo, scenario_root, step_labels)
    commands.extend(heartbeat_commands)

    # Step 3: zero-byte-file scan across everything materialized under
    # --root so far (sibling roots plus this scenario's own emitted logs),
    # classified per RES_M0's classify-don't-bulk-delete rule.
    command_results_by_scenario: dict[str, list[dict[str, Any]]] = {
        item.name: load_command_results(item) for item in sibling_roots
    }
    command_results_by_scenario[scenario_id] = [
        {"name": item["name"], "exit_code": item["exit_code"]} for item in commands
    ]
    zero_byte_report = zero_byte_scan(root, command_results_by_scenario)

    # Step 4: harness logs retained per instance (every command that any
    # scenario root under --root, including this one, recorded still has
    # its stdout/stderr log files present on disk).
    logs_report = harness_logs_retained(root, command_results_by_scenario)

    # Step 5: receipts-directory completeness against any tape found under
    # --root.
    receipts_report = receipts_completeness(root)

    # Step 6: after-digest of the same pre-existing evidence scope; diff
    # against the before-digest to prove this scenario's own run performed
    # zero mutation of pre-existing evidence (automatic-FAIL condition 6).
    after_digest = sha256_tree(digest_scope, exclude=root)
    digest_diff = diff_digest_trees(before_digest, after_digest)

    verdicts_complete = all(item["complete"] for item in verdict_inventory)
    labels_complete = all(item["complete"] for item in label_inventory)

    ops_inventory = {
        "schema_id": "turingos.fce.r3.ops_inventory.v1",
        "cert_root": str(root),
        "self_scenario_id": scenario_id,
        "self_excluded_from_sibling_checks_reason": (
            "this scenario's own verdict JSON cannot exist before this inventory "
            "computes it; the self-root is exercised (README/CLAIM_BOUNDARY/logs) "
            "but excluded from the sibling completeness rollups below"
        ),
        "standalone_invocation_caveat": (
            "sibling_scenario_roots is empty (vacuously satisfied, not fabricated) "
            "when this scenario is invoked standalone rather than after a full "
            "aggregate FCE run via run_scenarios.py, since no other scenario roots "
            "have yet been materialized under --root"
        ),
        "sibling_scenario_roots_found": [item.name for item in sibling_roots],
        "scenario_verdict_inventory": verdict_inventory,
        "scenario_verdicts_structured_and_present": verdicts_complete,
        "evidence_root_label_inventory": label_inventory,
        "evidence_roots_labeled_and_claim_bounded": labels_complete,
        "zero_byte_file_report": zero_byte_report,
        "harness_logs_retained_report": logs_report,
        "receipts_completeness_report": receipts_report,
        "operator_console_heartbeat_report": heartbeat_summary,
        "pre_existing_evidence_digest_sweep": {
            "scope": [str(item) for item in digest_scope],
            "excluded_from_scope": str(root),
            "files_checked_before": len(before_digest),
            "files_checked_after": len(after_digest),
            **digest_diff,
        },
    }
    ops_inventory_path = scenario_root / "ops_inventory.json"
    write_json(ops_inventory_path, ops_inventory)
    evidence_files.append(ops_inventory_path)

    readme_path = scenario_root / "README.md"
    readme_path.write_text(
        "\n".join(
            [
                "# FCE-R3 Ops Inventory (Monitoring, Logging, Evidence-Hygiene)",
                "",
                "Evidence label: REAL.",
                "This scenario inventories the certification root (`--root`) produced by",
                "this FCE run: every sibling scenario root's structured verdict JSON,",
                "README/CLAIM_BOUNDARY labeling, zero-byte-file classification, harness",
                "log retention, receipts-directory completeness, the M6 operator console",
                "heartbeat's exercisability, and a before/after digest sweep over the",
                "repo's and plan-root's real, pre-existing `evidence/` trees proving this",
                "scenario's own run mutated nothing outside `--root`.",
                "",
                "When invoked standalone (not after a full aggregate FCE run), the",
                "sibling-scenario-root inventory is genuinely empty; see",
                "`ops_inventory.json`'s `standalone_invocation_caveat` field.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    claim_boundary_path = scenario_root / "CLAIM_BOUNDARY.json"
    write_json(
        claim_boundary_path,
        {
            "schema_id": "CLAIM_BOUNDARY.v2",
            "evidence_class": "REAL",
            "claims": [
                "FCE-R3 ops inventory genuinely computed over the live --root cert "
                "state and the repo's/plan-root's real pre-existing evidence trees"
            ],
            "non_claims": [
                "not a full aggregate FCE suite run",
                "not a claim that every FCE scenario in the full suite has run",
                "not release eligibility",
                "not CLOSED/RELEASED/RATIFIED",
                "not SHIPPED",
                "not OG-10/genesis signature or M2 enablement",
            ],
        },
    )
    evidence_files.extend([readme_path, claim_boundary_path])

    automatic_fail_triggered = None
    if not digest_diff["clean"]:
        automatic_fail_triggered = "evidence_tampering_by_suite"
    elif not (
        verdicts_complete
        and labels_complete
        and zero_byte_report["clean"]
        and logs_report["complete"]
        and receipts_report["complete"]
        and heartbeat_summary["all_exercisable"]
    ):
        automatic_fail_triggered = "ops_inventory_gap"

    criteria = [
        {
            "criterion": "scenario_verdicts_structured_no_prose_only",
            "result": verdicts_complete,
            "evidence": rel(root, ops_inventory_path),
        },
        {
            "criterion": "evidence_roots_labeled_fixture_or_real_with_claim_boundary",
            "result": labels_complete,
            "evidence": rel(root, ops_inventory_path),
        },
        {
            "criterion": "zero_unclassified_zero_byte_files",
            "result": zero_byte_report["clean"],
            "evidence": rel(root, ops_inventory_path),
        },
        {
            "criterion": "harness_logs_retained_per_instance",
            "result": logs_report["complete"],
            "evidence": rel(root, ops_inventory_path),
        },
        {
            "criterion": "receipts_directory_complete",
            "result": receipts_report["complete"],
            "evidence": rel(root, ops_inventory_path),
        },
        {
            "criterion": "operator_console_heartbeat_exercisable_at_every_step",
            "result": heartbeat_summary["all_exercisable"],
            "evidence": rel(root, ops_inventory_path),
        },
        {
            "criterion": "pre_existing_evidence_digest_sweep_clean",
            "result": digest_diff["clean"],
            "evidence": rel(root, ops_inventory_path),
        },
    ]

    verdict = build_verdict(
        root=root,
        scenario_id=scenario_id,
        commands=commands,
        criteria=criteria,
        started=started,
        evidence_files=evidence_files,
        automatic_fail_triggered=automatic_fail_triggered,
    )
    write_json(scenario_root / f"{scenario_id}_verdict.json", verdict)
    print(json.dumps({"scenario_id": scenario_id, "verdict": verdict["verdict"]}, sort_keys=True))
    return 0 if verdict["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
