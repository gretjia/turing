"""Shared evidence-hygiene helpers for FCE scenario scripts.

FCE-R3 ("ops inventory") inspects every scenario root materialized directly
under the certification run's ``--root`` and requires, per root:

  * ``README.md`` containing the literal substring ``FIXTURE`` or ``REAL``
    matching the scenario's actual evidence class.
  * ``CLAIM_BOUNDARY.json`` with ``schema_id: CLAIM_BOUNDARY.v2`` and
    ``evidence_class`` in {FIXTURE, REAL}.
  * ``command_results.json`` listing every subprocess command the scenario
    ran (``name``/``cmd``/``exit_code``/``wall_clock_ms``), used by R3 to
    classify zero-byte ``<name>.stdout.txt``/``<name>.stderr.txt`` files as
    legitimate (empty stream from a known, recorded command) rather than
    "unclassified", and to confirm harness logs are retained per instance.

These files must exist under the scenario root regardless of which code
path the scenario takes (happy path, NOT_RUN / missing-credential early
exit, etc.), and any command a scenario runs must write its stdout/stderr
directly under the scenario root (not a nested subdirectory), since R3's
harness-log-retention check looks up ``root/<scenario_id>/<name>.stdout.txt``
at that flat depth.

This module is imported by scenario scripts; it is not itself a scenario
and is intentionally excluded from FCE-R3's own sibling-root inventory
scan (it lives alongside the scenario scripts, not under a certification
``--root``, so it is never itself a sibling root).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_command_results(
    scenario_root: Path,
    scenario_id: str,
    commands: list[dict[str, Any]],
) -> Path:
    """Write ``command_results.json`` at the scenario root.

    ``commands`` is the flat list of dicts produced by each scenario's
    ``run_command`` helper (and, for any subprocess launched outside that
    helper -- e.g. a deliberately-killed worker process -- a hand-built
    dict with at least ``name``/``cmd``/``exit_code``/``wall_clock_ms``).
    """
    path = scenario_root / "command_results.json"
    write_json(
        path,
        {
            "schema_id": f"turingos.fce.hygiene.command_results.v1",
            "scenario_id": scenario_id,
            "commands": [
                {
                    "name": item["name"],
                    "cmd": item.get("cmd", ""),
                    "exit_code": item.get("exit_code"),
                    "wall_clock_ms": item.get("wall_clock_ms", 0),
                }
                for item in commands
            ],
        },
    )
    return path


def write_evidence_labels(
    scenario_root: Path,
    *,
    scenario_id: str,
    title: str,
    evidence_class: str,
    summary_lines: list[str],
    claims: list[str],
    non_claims: list[str],
) -> tuple[Path, Path]:
    """Write ``README.md`` and ``CLAIM_BOUNDARY.json`` at the scenario root.

    ``evidence_class`` must be ``"FIXTURE"`` or ``"REAL"``; it is embedded
    verbatim in the README's "Evidence label:" line (satisfying R3's literal
    substring check) and in CLAIM_BOUNDARY.json's ``evidence_class`` field.
    """
    if evidence_class not in {"FIXTURE", "REAL"}:
        raise ValueError(f"evidence_class must be FIXTURE or REAL, got {evidence_class!r}")

    readme_path = scenario_root / "README.md"
    lines = [f"# {title}", "", f"Evidence label: {evidence_class}.", ""]
    lines.extend(summary_lines)
    lines.append("")
    readme_path.write_text("\n".join(lines), encoding="utf-8")

    claim_boundary_path = scenario_root / "CLAIM_BOUNDARY.json"
    write_json(
        claim_boundary_path,
        {
            "schema_id": "CLAIM_BOUNDARY.v2",
            "evidence_class": evidence_class,
            "claims": claims,
            "non_claims": non_claims,
        },
    )
    return readme_path, claim_boundary_path
