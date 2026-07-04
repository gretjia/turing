#!/usr/bin/env python3
"""FCE-R4: Cost dashboard from tape projections (G5/G7 seam).

Per 09_FINAL_CERTIFICATION_EVALS.md section "FCE-R4 - Cost dashboard from tape
projections": (1) build the cost projection over all certification tapes:
totals and breakdowns per scenario, per worker, per arm, per module-seam --
derived ONLY from tape receipt events; (2) render it through the M6 console
(`--json` mode); (3) cross-check every displayed number against an
independent recomputation from the raw tape (the FCE-S4 sums); (4) check
budget compliance against the E7 ceiling.

PASS (spec, line 293): every dashboard value replayable (exact match); budget
ceiling respected; zero cost events excluded from the projection (count
reconciliation); the dashboard JSON is attached to the certification packet.

Adaptation notes (same honesty convention FCE-S4 established for this clone):

  * "all certification tapes": this scenario scans `--root` for every
    `substrate_coverage.json` any OTHER scenario already wrote under the same
    evidence root (e.g. FCE-S4, when the full orchestrator runs this scenario
    after FCE-S4 in the same session) and rolls those real tapes up alongside
    its own. When run standalone (this scenario's own `--root` is empty of
    other scenario output -- e.g. this file's own `--verify` invocation), it
    is self-sufficient: it mints exactly one new real Micro Tape via the same
    minimal single-DeepSeek-call machinery FCE-S4 uses (imported from
    `FCE-S4.py`, not duplicated), so the rollup is never empty. No DeepSeek
    key is read, and no spend is made, when at least one existing tape is
    already available to roll up.
  * "render it through the M6 console (--json mode)": `turing status --json
    --demo` (the same real `operator_view_snapshot.v1` shadow-rebuild path
    FCE-R2/FCE-S1 exercise) is invoked for real, to prove the M6
    console/projection layer is live. As of this commit,
    `schemas/operator/operator_view_snapshot.v1.schema.json` has
    `additionalProperties: false` and carries no cost fields -- a real,
    disclosed gap, not one this scenario papers over. The cost dashboard
    itself is therefore delivered as its own attached JSON artifact
    (`cost_dashboard.json`), not fabricated as a field inside that schema.
  * "the FCE-S4 sums": for every tape source, this scenario computes the same
    two independent sums FCE-S4 defines -- the raw tape CostEvent sum and the
    on-disk `provider_receipt_sanitized.json` sum -- and requires exact
    equality, per source and in aggregate.
  * "per arm": CostEvent.v2 carries no explicit arm field. Where `run_id` or
    `branch_id` encode an `arm_a`/`arm_b` marker (the M4 uplift-study
    convention), that label is used; otherwise the event is honestly labeled
    `single_run_no_explicit_arm_label` rather than fabricating an arm.
  * "per module-seam": derived from `worker.adapter_kind`, the real field
    CostEvent.v2's own docstring calls the "WorkerAdapter seam" (native_api /
    cli / fake).
  * Replayability is checked by fetching every tape bundle a SECOND time (an
    independent `git bundle` fetch/replay, not a cached copy) and asserting
    the two independently-built dashboards are byte-identical.
  * Known pre-existing gap this scenario does NOT fix (out of this scenario's
    permitted edit scope): `tools/certification/score_certification.py`'s
    aggregate `FINAL_CERTIFICATION_VERDICT.json` "cost" block is a hardcoded
    stub (`total_llm_cost_from_tape_microusd: 0`, etc.), not wired to any
    scenario's real numbers. This scenario's own verdict and
    `cost_dashboard.json` carry the real computed numbers; the aggregate
    stub is a separate, already-tracked defect in a file this scenario is not
    authorized to modify.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCENARIOS_DIR = Path(__file__).resolve().parent
S4_SCRIPT_PATH = SCENARIOS_DIR / "FCE-S4.py"

DEFAULT_BUDGET_CEILING_MICROUSD = 50_000_000  # US$50, per 09_FINAL_CERTIFICATION_EVALS.md E7 recommendation
SECRETS_ENV_PATH = Path.home() / ".turingos" / "secrets.env"

ARM_PATTERN = re.compile(r"arm[_-]?([ab])(?![a-zA-Z0-9])", re.IGNORECASE)
NO_EXPLICIT_ARM_LABEL = "single_run_no_explicit_arm_label"

REQUIRED_DAEMON_BINARIES_FOR_CONSOLE = ["turing"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def run_command(
    *,
    name: str,
    argv: list[str],
    cwd: Path,
    out_dir: Path,
    env: dict[str, str] | None = None,
    timeout: int = 600,
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            argv, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False
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
    out_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = out_dir / f"{name}.stdout.txt"
    stderr_path = out_dir / f"{name}.stderr.txt"
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
# FCE-S4 reuse: import its cost machinery/tape helpers directly rather than
# duplicating them (per the sibling-script import convention this repo
# already uses for tools/bench/audit_micro_tape_decision_dag.py).
# --------------------------------------------------------------------------

def load_s4_module():
    spec = importlib.util.spec_from_file_location("fce_s4_for_r4", S4_SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_audit_module(repo: Path):
    sys.path.insert(0, str(repo / "tools" / "bench"))
    import audit_micro_tape_decision_dag as audit  # noqa: E402  (sibling-script import, matches repo convention)

    return audit


# --------------------------------------------------------------------------
# DeepSeek key resolution: reproducible from a clean shell. A prior scenario
# assumed the caller had already `export`-ed DEEPSEEK_API_KEY; this scenario
# also falls back to reading it directly from ~/.turingos/secrets.env so a
# fresh shell with nothing pre-exported still reproduces standalone.
# --------------------------------------------------------------------------

def resolve_deepseek_api_key(env_var: str, secrets_path: Path | None = None) -> tuple[str | None, str]:
    # secrets_path defaults to the module-level SECRETS_ENV_PATH, looked up
    # dynamically (not bound at function-definition time) so tests can
    # monkeypatch the module attribute and have it actually take effect.
    resolved_secrets_path = secrets_path if secrets_path is not None else SECRETS_ENV_PATH
    value = os.environ.get(env_var)
    if value:
        return value, "process_environment"
    if resolved_secrets_path.is_file():
        for line in resolved_secrets_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("export "):
                stripped = stripped[len("export ") :]
            if "=" not in stripped:
                continue
            key, _, val = stripped.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key == env_var and val:
                return val, "secrets_env_file"
    return None, "not_found"


# --------------------------------------------------------------------------
# Discovery: find every OTHER scenario's already-produced real tape(s) under
# the shared --root before deciding whether this scenario needs to mint its
# own.
# --------------------------------------------------------------------------

def discover_existing_tape_sources(root: Path, exclude_scenario_id: str) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    if not root.is_dir():
        return sources
    for coverage_path in sorted(root.rglob("substrate_coverage.json")):
        try:
            rel_parts = coverage_path.relative_to(root).parts
        except ValueError:
            continue
        if not rel_parts or rel_parts[0] == exclude_scenario_id:
            continue
        sources.append(
            {
                "scenario_id": rel_parts[0],
                "coverage_path": coverage_path,
                "minted_by_this_scenario": False,
            }
        )
    return sources


# --------------------------------------------------------------------------
# Per-event row extraction (independent of FCE-S4's own aggregate sums --
# used for the scenario/worker/arm/module-seam breakdowns and as the second,
# separately-authored count-reconciliation implementation).
# --------------------------------------------------------------------------

def derive_arm_label(run_id: Any, branch_id: Any) -> str:
    for candidate in (branch_id, run_id):
        if isinstance(candidate, str):
            match = ARM_PATTERN.search(candidate)
            if match:
                return f"arm_{match.group(1).lower()}"
    return NO_EXPLICIT_ARM_LABEL


def cost_rows_for_events(audit_module, events: list[dict[str, Any]], source_scenario_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in events:
        if event.get("event_type") != "CostEvent" or not isinstance(event.get("payload"), dict):
            continue
        payload = event["payload"]
        worker = payload.get("worker") if isinstance(payload.get("worker"), dict) else {}
        cost = payload.get("cost") if isinstance(payload.get("cost"), dict) else {}
        rows.append(
            {
                "scenario_id": source_scenario_id,
                "event_id": event.get("_event_id"),
                "worker_model": worker.get("model_id_resolved") or "unknown_model",
                "module_seam": worker.get("adapter_kind") or "unknown_adapter_kind",
                "arm": derive_arm_label(payload.get("run_id"), payload.get("branch_id")),
                "cost_microusd": audit_module.cost_event_cost_microusd(payload) or 0,
                "tokens": audit_module.cost_event_total_tokens(payload),
                "cost_source_kind": cost.get("cost_source_kind"),
                "bound_kind": cost.get("bound_kind"),
            }
        )
    return rows


def aggregate_rows(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for row in rows:
        bucket = out.setdefault(str(row[key]), {"cost_microusd_sum": 0, "token_count_sum": 0, "cost_event_count": 0})
        bucket["cost_microusd_sum"] += int(row["cost_microusd"])
        bucket["token_count_sum"] += int(row["tokens"])
        bucket["cost_event_count"] += 1
    return out


def totals_from_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "cost_microusd_sum": sum(int(row["cost_microusd"]) for row in rows),
        "token_count_sum": sum(int(row["tokens"]) for row in rows),
        "cost_event_count": len(rows),
    }


def breakdown_partitions_totals(breakdown: dict[str, dict[str, int]], totals: dict[str, int]) -> bool:
    return (
        sum(bucket["cost_microusd_sum"] for bucket in breakdown.values()) == totals["cost_microusd_sum"]
        and sum(bucket["token_count_sum"] for bucket in breakdown.values()) == totals["token_count_sum"]
        and sum(bucket["cost_event_count"] for bucket in breakdown.values()) == totals["cost_event_count"]
    )


# --------------------------------------------------------------------------
# Per-source processing: fetch/replay every bundle in a source's coverage
# file, build rows, and cross-check the two FCE-S4-defined independent sums.
# --------------------------------------------------------------------------

def process_source(
    *,
    repo: Path,
    scenario_root: Path,
    s4_module,
    audit_module,
    source_scenario_id: str,
    coverage_path: Path,
    round_label: str,
) -> dict[str, Any]:
    coverage = load_json(coverage_path) if coverage_path.is_file() else {}
    runs = coverage.get("turingos_arm_runs", []) if isinstance(coverage, dict) else []
    all_events: list[dict[str, Any]] = []
    bundle_errors: list[str] = []
    bundle_count = 0
    for idx, run in enumerate(runs):
        if not isinstance(run, dict) or not run.get("micro_tape_bundle"):
            continue
        bundle_path = Path(run["micro_tape_bundle"])
        if not bundle_path.is_file():
            bundle_errors.append(f"{source_scenario_id}[{idx}]: bundle_missing:{bundle_path}")
            continue
        work_dir_root = scenario_root / "tape_replay" / round_label / source_scenario_id / str(idx)
        try:
            events = s4_module.load_tape_events(repo, work_dir_root, bundle_path)
        except Exception as exc:  # noqa: BLE001 - record as an honest per-bundle failure, do not crash the rollup
            bundle_errors.append(f"{source_scenario_id}[{idx}]: {exc!r}")
            continue
        bundle_count += 1
        all_events.extend(events)

    rows = cost_rows_for_events(audit_module, all_events, source_scenario_id)
    tape_summary = s4_module.tape_cost_summary(repo, all_events)
    receipts_summary = s4_module.receipts_file_cost_summary(scenario_root, coverage)
    row_totals = totals_from_rows(rows)

    return {
        "scenario_id": source_scenario_id,
        "coverage_path": coverage_path,
        "bundle_count": bundle_count,
        "bundle_errors": bundle_errors,
        "rows": rows,
        "tape_summary": tape_summary,
        "receipts_summary": receipts_summary,
        "row_totals": row_totals,
    }


def assemble_dashboard(
    *,
    source_results: list[dict[str, Any]],
    budget_ceiling_microusd: int,
    budget_ceiling_source: str,
    generated_utc: str,
) -> dict[str, Any]:
    all_rows: list[dict[str, Any]] = []
    for source in source_results:
        all_rows.extend(source["rows"])
    totals = totals_from_rows(all_rows)
    return {
        "schema_id": "turingos.fce.r4.cost_dashboard.v1",
        "generated_utc": generated_utc,
        "sources": [
            {
                "scenario_id": source["scenario_id"],
                "bundle_count": source["bundle_count"],
                "cost_event_count": source["row_totals"]["cost_event_count"],
                "cost_microusd_sum": source["row_totals"]["cost_microusd_sum"],
                "token_count_sum": source["row_totals"]["token_count_sum"],
            }
            for source in source_results
        ],
        "totals": totals,
        "by_scenario": aggregate_rows(all_rows, "scenario_id"),
        "by_worker": aggregate_rows(all_rows, "worker_model"),
        "by_arm": aggregate_rows(all_rows, "arm"),
        "by_module_seam": aggregate_rows(all_rows, "module_seam"),
        "budget": {
            "ceiling_microusd": budget_ceiling_microusd,
            "ceiling_source": budget_ceiling_source,
            "spend_microusd": totals["cost_microusd_sum"],
            "ceiling_respected": totals["cost_microusd_sum"] <= budget_ceiling_microusd,
        },
    }


def read_budget_ceiling(root: Path, override: int | None) -> tuple[int, str]:
    if override is not None:
        return override, "cli_override"
    manifest_path = root / "FCE_RUN_MANIFEST.json"
    if manifest_path.is_file():
        try:
            manifest = load_json(manifest_path)
        except (OSError, ValueError, json.JSONDecodeError):
            manifest = {}
        for item in manifest.get("entry_criteria", []) if isinstance(manifest, dict) else []:
            if isinstance(item, dict) and item.get("id") == "E7":
                evidence = item.get("evidence", {})
                value = evidence.get("budget_ceiling_microusd") if isinstance(evidence, dict) else None
                if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                    return value, "fce_run_manifest_e7"
    return DEFAULT_BUDGET_CEILING_MICROUSD, "default_recommended_ceiling"


# --------------------------------------------------------------------------
# M6 console (--json mode) real invocation
# --------------------------------------------------------------------------

def run_m6_console(repo: Path, scenario_root: Path, daemon_bin_dir: Path) -> dict[str, Any]:
    turing_bin = daemon_bin_dir / "turing"
    command = run_command(
        name="turing_status_json_demo",
        argv=[str(turing_bin), "status", "--json", "--demo"],
        cwd=repo,
        out_dir=scenario_root / "commands",
    )
    snapshot: dict[str, Any] | None = None
    schema_valid = False
    if command["exit_code"] == 0:
        try:
            snapshot = json.loads(command["stdout_text"])
            schema_valid = isinstance(snapshot, dict) and snapshot.get("schema_id") == "operator_view_snapshot.v1"
        except json.JSONDecodeError:
            schema_valid = False
    snapshot_path = scenario_root / "m6_console_operator_view_snapshot.json"
    write_json(snapshot_path, snapshot if isinstance(snapshot, dict) else {"parse_error": True})
    return {"command": command, "snapshot_path": snapshot_path, "schema_valid": schema_valid}


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
) -> dict[str, Any]:
    evidence_paths = sorted({rel(root, path) for path in evidence_files if path.is_file()})
    passed = all(item["result"] is True for item in criteria)
    return {
        "schema_id": "turingos.fce_scenario_verdict.v1",
        "scenario_id": scenario_id,
        "verdict": "PASS" if passed else "FAIL",
        "not_run_is_fail": True,
        "goals_served": ["G5", "G7"],
        "commands_executed": [{"cmd": command["cmd"], "exit_code": command["exit_code"]} for command in commands],
        "pass_criteria_results": criteria,
        "evidence": evidence_paths,
        "evidence_sha256": {item: sha256_file(root / item) for item in evidence_paths},
        "fixture_or_real": "REAL",
        "automatic_fail_triggered": None,
        "wall_clock_ms": int((time.monotonic() - started) * 1000),
        "timestamp_utc": utc_now(),
    }


def write_not_run(root: Path, scenario_id: str, started: float, reason: str) -> dict[str, Any]:
    verdict = {
        "schema_id": "turingos.fce_scenario_verdict.v1",
        "scenario_id": scenario_id,
        "verdict": "NOT_RUN",
        "not_run_is_fail": True,
        "goals_served": ["G5", "G7"],
        "commands_executed": [],
        "pass_criteria_results": [],
        "evidence": [],
        "evidence_sha256": {},
        "fixture_or_real": "REAL",
        "automatic_fail_triggered": None,
        "not_run_reason": reason,
        "wall_clock_ms": int((time.monotonic() - started) * 1000),
        "timestamp_utc": utc_now(),
    }
    write_json(root / scenario_id / f"{scenario_id}_verdict.json", verdict)
    return verdict


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--plan-root", required=True)
    parser.add_argument("--scenario-id", required=True)
    parser.add_argument("--budget-ceiling-microusd", type=int, default=None)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    repo = Path(args.repo).resolve()
    plan_root = Path(args.plan_root).resolve()
    scenario_id = args.scenario_id
    scenario_root = root / scenario_id
    scenario_root.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    s4_module = load_s4_module()
    audit_module = load_audit_module(repo)

    commands: list[dict[str, Any]] = []
    evidence_files: list[Path] = []

    daemon_bin = s4_module.resolve_daemon_bin_dir(repo, scenario_root)
    daemon_bin_dir = Path(daemon_bin["bin_dir"])
    evidence_files.append(scenario_root / "daemon_bin_dir_resolution.json")

    existing_sources = discover_existing_tape_sources(root, scenario_id)

    minted_own = False
    api_key_source = "not_needed_existing_tapes_reused"
    if not existing_sources:
        api_key, api_key_source = resolve_deepseek_api_key(s4_module.DEEPSEEK_API_KEY_ENV)
        if not api_key:
            write_not_run(
                root,
                scenario_id,
                started,
                f"no existing certification tapes found under {root} and missing DeepSeek credentials "
                f"(checked process environment and {SECRETS_ENV_PATH}) to mint one",
            )
            print(json.dumps({"scenario_id": scenario_id, "verdict": "NOT_RUN"}, sort_keys=True))
            return 2

        os.environ[s4_module.DEEPSEEK_API_KEY_ENV] = api_key
        selection = s4_module.select_single_task(repo, scenario_root)
        evidence_files.append(scenario_root / "task_selection.json")
        materialize = s4_module.materialize_single_task(repo, scenario_root, selection)
        commands.append(materialize["command"])
        evidence_files.append(materialize["report_path"])
        loop = s4_module.run_real_loop(repo, plan_root, scenario_root, materialize["tasks_jsonl_path"], api_key, daemon_bin_dir)
        commands.append(loop["command"])
        if loop["coverage_path"].is_file():
            evidence_files.append(loop["coverage_path"])
        existing_sources = [
            {
                "scenario_id": scenario_id,
                "coverage_path": loop["coverage_path"],
                "minted_by_this_scenario": True,
            }
        ]
        minted_own = True

    key_resolution_note_path = scenario_root / "api_key_resolution_note.json"
    write_json(
        key_resolution_note_path,
        {
            "schema_id": "turingos.fce.r4.api_key_resolution.v1",
            "deepseek_api_key_source": api_key_source,
            "secrets_env_path_checked": str(SECRETS_ENV_PATH),
            "own_tape_minted": minted_own,
        },
    )
    evidence_files.append(key_resolution_note_path)

    budget_ceiling_microusd, budget_ceiling_source = read_budget_ceiling(root, args.budget_ceiling_microusd)

    # Two independent rounds: every tape bundle is fetched/replayed twice
    # (fresh git-bundle fetch each time) to prove the dashboard is replayable,
    # not just internally self-consistent.
    round_results: dict[str, list[dict[str, Any]]] = {}
    for round_label in ("round1", "round2"):
        results = []
        for source in existing_sources:
            result = process_source(
                repo=repo,
                scenario_root=scenario_root,
                s4_module=s4_module,
                audit_module=audit_module,
                source_scenario_id=source["scenario_id"],
                coverage_path=source["coverage_path"],
                round_label=round_label,
            )
            result["minted_by_this_scenario"] = source["minted_by_this_scenario"]
            results.append(result)
        round_results[round_label] = results

    generated_utc = utc_now()
    dashboard_round1 = assemble_dashboard(
        source_results=round_results["round1"],
        budget_ceiling_microusd=budget_ceiling_microusd,
        budget_ceiling_source=budget_ceiling_source,
        generated_utc=generated_utc,
    )
    dashboard_round2 = assemble_dashboard(
        source_results=round_results["round2"],
        budget_ceiling_microusd=budget_ceiling_microusd,
        budget_ceiling_source=budget_ceiling_source,
        generated_utc=generated_utc,
    )
    dashboard_replay_byte_identical = json.dumps(dashboard_round1, sort_keys=True) == json.dumps(dashboard_round2, sort_keys=True)

    dashboard_path = scenario_root / "cost_dashboard.json"
    write_json(dashboard_path, dashboard_round1)
    evidence_files.append(dashboard_path)

    replay_path = scenario_root / "cost_dashboard_replay_round2.json"
    write_json(replay_path, dashboard_round2)
    evidence_files.append(replay_path)

    # Console (M6, --json mode) real invocation.
    console = run_m6_console(repo, scenario_root, daemon_bin_dir)
    commands.append(console["command"])
    evidence_files.append(console["snapshot_path"])

    console_gap_note_path = scenario_root / "m6_console_cost_field_gap_note.json"
    write_json(
        console_gap_note_path,
        {
            "schema_id": "turingos.fce.r4.console_cost_field_gap_note.v1",
            "note": (
                "schemas/operator/operator_view_snapshot.v1.schema.json has additionalProperties:false "
                "and carries no cost fields as of this commit; a real, disclosed gap. The cost dashboard "
                "is delivered as its own attached artifact (cost_dashboard.json), not fabricated inside "
                "that schema."
            ),
            "console_invocation_exit_code": console["command"]["exit_code"],
            "console_snapshot_schema_valid": console["schema_valid"],
        },
    )
    evidence_files.append(console_gap_note_path)

    per_source_reconciliation = []
    all_bundle_errors: list[str] = []
    per_source_cost_exact = True
    per_source_tokens_exact = True
    per_source_count_reconciled = True
    for source in round_results["round1"]:
        cost_exact = (
            source["row_totals"]["cost_event_count"] >= 1
            and source["tape_summary"]["cost_microusd_sum"] == source["receipts_summary"]["cost_microusd_sum"]
        )
        tokens_exact = (
            source["row_totals"]["cost_event_count"] >= 1
            and source["tape_summary"]["token_count_sum"] == source["receipts_summary"]["token_count_sum"]
        )
        count_reconciled = source["tape_summary"]["cost_event_count"] == source["row_totals"]["cost_event_count"]
        per_source_cost_exact = per_source_cost_exact and cost_exact
        per_source_tokens_exact = per_source_tokens_exact and tokens_exact
        per_source_count_reconciled = per_source_count_reconciled and count_reconciled
        all_bundle_errors.extend(source["bundle_errors"])
        per_source_reconciliation.append(
            {
                "scenario_id": source["scenario_id"],
                "tape_cost_microusd_sum": source["tape_summary"]["cost_microusd_sum"],
                "receipts_cost_microusd_sum": source["receipts_summary"]["cost_microusd_sum"],
                "tape_token_count_sum": source["tape_summary"]["token_count_sum"],
                "receipts_token_count_sum": source["receipts_summary"]["token_count_sum"],
                "tape_cost_event_count": source["tape_summary"]["cost_event_count"],
                "row_cost_event_count": source["row_totals"]["cost_event_count"],
                "cost_exact_match": cost_exact,
                "tokens_exact_match": tokens_exact,
                "count_reconciled": count_reconciled,
            }
        )
    reconciliation_path = scenario_root / "per_source_reconciliation.json"
    write_json(reconciliation_path, {"schema_id": "turingos.fce.r4.reconciliation.v1", "sources": per_source_reconciliation})
    evidence_files.append(reconciliation_path)

    all_rows_round1 = [row for source in round_results["round1"] for row in source["rows"]]
    valid_cost_source_kinds = all(
        isinstance(row["cost_source_kind"], str) and row["cost_source_kind"] in audit_module.COST_SOURCE_KINDS
        for row in all_rows_round1
    )
    bounded_estimates_carry_bound_kind = all(
        isinstance(row["bound_kind"], str) and bool(row["bound_kind"])
        for row in all_rows_round1
        if row["cost_source_kind"] == "bounded_estimate"
    )

    criteria = [
        {
            "criterion": "at_least_one_certification_tape_in_rollup",
            "result": dashboard_round1["totals"]["cost_event_count"] >= 1,
            "evidence": rel(root, dashboard_path),
        },
        {
            "criterion": "zero_bundle_processing_errors",
            "result": all_bundle_errors == [],
            "evidence": rel(root, reconciliation_path),
        },
        {
            "criterion": "every_cost_event_cost_source_kind_populated_and_valid_enum",
            "result": bool(all_rows_round1) and valid_cost_source_kinds,
            "evidence": rel(root, dashboard_path),
        },
        {
            "criterion": "bounded_estimates_carry_bound_derivation",
            "result": bounded_estimates_carry_bound_kind,
            "evidence": rel(root, dashboard_path),
        },
        {
            "criterion": "tape_sum_equals_receipts_file_sum_exact_cost_per_source",
            "result": per_source_cost_exact,
            "evidence": rel(root, reconciliation_path),
        },
        {
            "criterion": "tape_sum_equals_receipts_file_sum_exact_tokens_per_source",
            "result": per_source_tokens_exact,
            "evidence": rel(root, reconciliation_path),
        },
        {
            "criterion": "zero_cost_events_excluded_count_reconciliation",
            "result": per_source_count_reconciled,
            "evidence": rel(root, reconciliation_path),
        },
        {
            "criterion": "dashboard_breakdown_partitions_match_totals_exact",
            "result": (
                breakdown_partitions_totals(dashboard_round1["by_scenario"], dashboard_round1["totals"])
                and breakdown_partitions_totals(dashboard_round1["by_worker"], dashboard_round1["totals"])
                and breakdown_partitions_totals(dashboard_round1["by_arm"], dashboard_round1["totals"])
                and breakdown_partitions_totals(dashboard_round1["by_module_seam"], dashboard_round1["totals"])
            ),
            "evidence": rel(root, dashboard_path),
        },
        {
            "criterion": "dashboard_replay_byte_identical_independent_refetch",
            "result": dashboard_replay_byte_identical,
            "evidence": rel(root, replay_path),
        },
        {
            "criterion": "budget_ceiling_respected",
            "result": dashboard_round1["budget"]["ceiling_respected"],
            "evidence": rel(root, dashboard_path),
        },
        {
            "criterion": "m6_console_real_invocation_exit_zero",
            "result": console["command"]["exit_code"] == 0,
            "evidence": rel(root, console["snapshot_path"]),
        },
        {
            "criterion": "m6_console_snapshot_schema_valid",
            "result": console["schema_valid"],
            "evidence": rel(root, console["snapshot_path"]),
        },
        {
            "criterion": "cost_dashboard_json_attached_to_evidence_root",
            "result": dashboard_path.is_file(),
            "evidence": rel(root, dashboard_path),
        },
    ]

    readme = scenario_root / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# FCE-R4 Cost Dashboard From Tape Projections",
                "",
                "Evidence label: REAL.",
                "",
                f"Own tape minted by this scenario: {minted_own}. DeepSeek API key source: {api_key_source}.",
                f"Rolled-up sources: {[s['scenario_id'] for s in round_results['round1']]}.",
                "",
                "Cost totals/breakdowns (per scenario, per worker, per arm, per module-seam) are built",
                "ONLY from real tape CostEvent.v2 events, fetched via an independent git-bundle read (no",
                "fixture JSON). Every source's tape sum is cross-checked exactly against the on-disk",
                "`provider_receipt_sanitized.json` receipts-file sum (the FCE-S4 pair). Every bundle is",
                "fetched/replayed twice (independent git-bundle fetches) and the two resulting dashboards",
                "are asserted byte-identical (dashboard_replay_byte_identical_independent_refetch).",
                "",
                "`turing status --json --demo` (M6 console) is invoked for real to exercise the live",
                "operator_view_snapshot.v1 projection layer. That schema has no cost fields as of this",
                "commit (additionalProperties:false) -- a real, disclosed gap, not papered over; the cost",
                "dashboard is delivered as its own attached artifact, cost_dashboard.json, per the spec's",
                "operational-readiness deliverable.",
                "",
                "Known pre-existing gap NOT fixed by this scenario (outside its permitted edit scope):",
                "tools/certification/score_certification.py's aggregate FINAL_CERTIFICATION_VERDICT.json",
                "'cost' block is a hardcoded stub, not wired to any scenario's real numbers.",
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
                "FCE-R4 cost-dashboard certification: real tape CostEvent.v2 rollup (totals + "
                "scenario/worker/arm/module-seam breakdowns), exact cross-check against the FCE-S4 "
                "receipts-file sums, byte-identical replay across two independent git-bundle fetches, "
                "budget-ceiling compliance, and a real M6 console (--json --demo) invocation",
            ],
            "non_claims": [
                "no solve-rate claim of any kind",
                "not a claim that operator_view_snapshot.v1 itself carries cost fields (it does not, as "
                "of this commit)",
                "not a release decision",
                "not SHIPPED",
                "not an external audit",
            ],
        },
    )
    evidence_files.extend([readme, claim_boundary])

    verdict = build_verdict(
        root=root,
        scenario_id=scenario_id,
        started=started,
        commands=commands,
        criteria=criteria,
        evidence_files=evidence_files,
    )
    write_json(scenario_root / f"{scenario_id}_verdict.json", verdict)
    print(json.dumps({"scenario_id": scenario_id, "verdict": verdict["verdict"]}, sort_keys=True))
    return 0 if verdict["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
