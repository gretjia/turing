#!/usr/bin/env python3
"""FCE-S2: universality under integration (G3 scenario eval, integrated).

Per 09_FINAL_CERTIFICATION_EVALS.md §FCE-S2: the M2 Turing-completeness (TC)
witness holds from the certification clone, not just the implementer's tree.

Steps (spec, line 130): from the fresh clone (i.e. this worktree's checked-out
`turing` repo) --
  1. `sha256sum -c evidence/theory/turing_completeness_witness_<date>/bundle_sha256s.txt`
  2. re-run the TC gate battery TC-01..TC-09 (RES_M2 §5.8): the strict
     auditor's differential re-check (`tools/theory/audit_tc3_evidence.py`,
     which recomputes every fuzz case against the TC1 reference interpreter
     AND re-verifies every tape bundle digest) and the full TC4 local audit
     (`tools/theory/audit_tc4_witness.py`, which re-simulates every witness
     program from its exported tape, recomputes the m1-m7 mutation matrix,
     and re-runs the interleave/sabotage non-interference test) -- both
     invoked WITHOUT `--write`, so they are genuine re-computations printed
     to stdout, never a read of the cached verdict files;
  3. confirm the TC-10 verdict artifact exists and was produced by the
     independent cross-family verifier (custody metadata in the artifact),
     NOT by any implementer context. Per the handover, M2.TC5's own
     packet-local `verdicts/TC-10.json` slot is (correctly) NOT_RUN --
     the implementer must never write it -- and the actual external action
     lives in the M5.P4 closure certificate
     (`PROJECT_PLAN_.../evidence/session_20260702/
     M5_P4_REMAINING_M1_M2_CLAUDE_PASS_CERTIFICATE.json`), a
     `turingos.closure_certificate.v1` whose `verifier.custody` block is
     independently verified via the shared, already-vetted
     `tools/certification/checks/entry_criteria.py` custody-boolean
     machinery (imported, not re-implemented) and whose `tc10_execution`
     object records that the external cross-family verifier itself executed
     the TC-10 clone/re-verify/write action outside implementer custody.

PASS criteria (spec, line 132): all digests OK; TC-01..TC-09 re-verified PASS
with verdict JSONs byte-consistent (after `tools/certification/
NORMALIZATION_SPEC.json` normalization) with the stored ones; TC-10 artifact
present with verifier identity distinct from all implementer identities;
halting AND non-halting example classes both present; the non-interference
gate shows market/PPUT/HCI signals cannot affect transitions. If TC-10 is
absent: this scenario FAILs (G3's KPI explicitly requires the independent
audit) -- certification cannot substitute for it.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any


IMPLEMENTER_IDENTITY_MARKERS = {"", "implementer", "self", "certification-agent", "cert-agent-self"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_command(
    *,
    name: str,
    argv: list[str],
    cwd: Path,
    out_dir: Path,
    timeout: int = 180,
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
        "stdout_path": stdout_path,
        "stderr_path": stderr_path,
        "stdout_text": proc.stdout,
        "stderr_text": proc.stderr,
    }


# --------------------------------------------------------------------------
# Shared-spec normalization (tools/certification/NORMALIZATION_SPEC.json),
# reused rather than re-invented: strip the volatile leaf keys before any
# byte-consistency comparison of a freshly recomputed gate verdict against
# the stored one.
# --------------------------------------------------------------------------


def load_normalization_spec(repo: Path) -> tuple[dict[str, Any], set[str]]:
    spec_path = repo / "tools" / "certification" / "NORMALIZATION_SPEC.json"
    spec = load_json(spec_path)
    volatile_keys = set(spec.get("volatile_key_names", []))
    for pointer_suffix in spec.get("volatile_json_pointer_suffixes", []):
        volatile_keys.add(pointer_suffix.rsplit("/", 1)[-1])
    return spec, volatile_keys


def normalize_value(value: Any, volatile_keys: set[str]) -> Any:
    if isinstance(value, dict):
        return {
            key: normalize_value(item, volatile_keys)
            for key, item in value.items()
            if key not in volatile_keys
        }
    if isinstance(value, list):
        return [normalize_value(item, volatile_keys) for item in value]
    return value


def canonical_bytes(value: Any, volatile_keys: set[str]) -> bytes:
    normalized = normalize_value(value, volatile_keys)
    return (json.dumps(normalized, indent=2, sort_keys=True) + "\n").encode("utf-8")


def compare_normalized(
    *,
    label: str,
    fresh_value: Any,
    stored_path: Path,
    volatile_keys: set[str],
) -> dict[str, Any]:
    stored_value = load_json(stored_path)
    fresh_bytes = canonical_bytes(fresh_value, volatile_keys)
    stored_bytes = canonical_bytes(stored_value, volatile_keys)
    return {
        "label": label,
        "stored_path": str(stored_path),
        "fresh_normalized_sha256": sha256_bytes(fresh_bytes),
        "stored_normalized_sha256": sha256_bytes(stored_bytes),
        "byte_consistent": fresh_bytes == stored_bytes,
    }


# --------------------------------------------------------------------------
# Witness bundle discovery + classification
# --------------------------------------------------------------------------


def find_witness_root(repo: Path) -> Path | None:
    candidates = sorted((repo / "evidence" / "theory").glob("turing_completeness_witness_*"))
    return candidates[-1] if candidates else None


def classify_halting_nonhalting(bundle_manifest: dict[str, Any]) -> dict[str, Any]:
    halting: list[str] = []
    nonhalting: list[str] = []
    for run in bundle_manifest.get("runs", []):
        program_id = run.get("program_id")
        if run.get("expected_terminal_event") == "ComputationHalted":
            halting.append(program_id)
        elif run.get("certificate_class"):
            nonhalting.append(program_id)
    return {
        "halting_programs": halting,
        "nonhalting_programs": nonhalting,
        "halting_count_recomputed": len(halting),
        "nonhalting_count_recomputed": len(nonhalting),
        "halting_count_declared": bundle_manifest.get("halting_program_count"),
        "nonhalting_count_declared": bundle_manifest.get("nonhalting_program_count"),
        "counts_self_consistent": (
            len(halting) == bundle_manifest.get("halting_program_count")
            and len(nonhalting) == bundle_manifest.get("nonhalting_program_count")
        ),
    }


# --------------------------------------------------------------------------
# Verdict assembly (mirrors FCE-S3/FCE-B5 shape)
# --------------------------------------------------------------------------


def build_verdict(
    *,
    root: Path,
    scenario_id: str,
    commands: list[dict[str, Any]],
    criteria: list[dict[str, Any]],
    started: float,
    evidence_files: list[Path],
    automatic_fail_reason: str | None,
) -> dict[str, Any]:
    scenario_root = root / scenario_id
    command_results = scenario_root / "command_results.json"
    write_json(
        command_results,
        {
            "schema_id": "turingos.fce.s2.command_results.v1",
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
        evidence_paths.append(rel(root, command["stdout_path"]))
        evidence_paths.append(rel(root, command["stderr_path"]))
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
        "goals_served": ["G3"],
        "commands_executed": [
            {"cmd": command["cmd"], "exit_code": command["exit_code"]} for command in commands
        ],
        "pass_criteria_results": criteria,
        "evidence": evidence_paths,
        "evidence_sha256": {item: sha256_file(root / item) for item in evidence_paths},
        "fixture_or_real": "REAL",
        "automatic_fail_triggered": None if passed else automatic_fail_reason,
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
    criteria: list[dict[str, Any]] = []

    _, volatile_keys = load_normalization_spec(repo)

    witness_root = find_witness_root(repo)
    if witness_root is None:
        criteria.append(
            {
                "criterion": "tc_witness_evidence_root_present",
                "result": False,
                "evidence": "none: no evidence/theory/turing_completeness_witness_* directory in this clone",
            }
        )
        verdict = build_verdict(
            root=root,
            scenario_id=scenario_id,
            commands=commands,
            criteria=criteria,
            started=started,
            evidence_files=evidence_files,
            automatic_fail_reason="tc_witness_evidence_root_missing",
        )
        write_json(scenario_root / f"{scenario_id}_verdict.json", verdict)
        print(json.dumps({"scenario_id": scenario_id, "verdict": verdict["verdict"]}, sort_keys=True))
        return 1

    # ------------------------------------------------------------------
    # 1. Digest check: every tape bundle in the witness matches its pinned
    #    sha256 in THIS clone (spec step 1, run from the witness root so the
    #    manifest's repo-relative paths resolve).
    # ------------------------------------------------------------------
    digest_command = run_command(
        name="witness_bundle_digest_check",
        argv=["sha256sum", "-c", "bundle_sha256s.txt"],
        cwd=witness_root,
        out_dir=scenario_root,
    )
    commands.append(digest_command)
    digests_ok = digest_command["exit_code"] == 0
    criteria.append(
        {
            "criterion": "witness_bundle_digests_ok",
            "result": digests_ok,
            "evidence": rel(root, digest_command["stdout_path"]),
        }
    )

    # ------------------------------------------------------------------
    # 2a. Real re-run of the TC-03 fuzz/differential audit (recomputes every
    #     fuzz case against the independent reference interpreter and
    #     re-verifies bundle digests again, standalone) -- no --write, so
    #     this is a genuine recomputation, not a cached-file read.
    # ------------------------------------------------------------------
    tc3_command = run_command(
        name="tc03_fuzz_differential_reaudit",
        argv=["python3", str(repo / "tools" / "theory" / "audit_tc3_evidence.py"), "--root", str(witness_root)],
        cwd=repo,
        out_dir=scenario_root,
        timeout=300,
    )
    commands.append(tc3_command)
    try:
        tc3_fresh = json.loads(tc3_command["stdout_text"])
    except json.JSONDecodeError:
        tc3_fresh = {"verdict": "FAIL", "parse_error": True}
    tc3_pass = tc3_command["exit_code"] == 0 and tc3_fresh.get("verdict") == "PASS"
    criteria.append(
        {
            "criterion": "tc03_fuzz_differential_reverified_pass",
            "result": tc3_pass,
            "evidence": rel(root, tc3_command["stdout_path"]),
        }
    )

    # ------------------------------------------------------------------
    # 2b. Real re-run of the full TC4 local audit battery: re-simulates
    #     every witness program from its exported tape, recomputes the
    #     m1-m7 mutation matrix, and re-executes the interleave/sabotage
    #     non-interference test -- emits fresh TC-01..TC-09 verdicts.
    # ------------------------------------------------------------------
    tc4_command = run_command(
        name="tc04_tc09_local_audit_reaudit",
        argv=["python3", str(repo / "tools" / "theory" / "audit_tc4_witness.py"), "--root", str(witness_root)],
        cwd=repo,
        out_dir=scenario_root,
        timeout=300,
    )
    commands.append(tc4_command)
    try:
        tc4_fresh = json.loads(tc4_command["stdout_text"])
    except json.JSONDecodeError:
        tc4_fresh = {"verdict": "FAIL", "verdicts": {}, "mutation_matrix": {}, "noninterference": {}, "parse_error": True}
    tc4_pass = tc4_command["exit_code"] == 0 and tc4_fresh.get("verdict") == "PASS"
    per_gate_pass = all(
        gate.get("verdict") == "PASS" for gate in tc4_fresh.get("verdicts", {}).values()
    ) and len(tc4_fresh.get("verdicts", {})) == 9
    criteria.append(
        {
            "criterion": "tc04_tc09_local_audit_reverified_pass",
            "result": tc4_pass and per_gate_pass,
            "evidence": rel(root, tc4_command["stdout_path"]),
        }
    )

    # ------------------------------------------------------------------
    # 3. Byte-consistency (after shared NORMALIZATION_SPEC.json
    #    normalization) between every freshly recomputed verdict and the
    #    stored one it corresponds to: TC-01..TC-09 gate verdicts, the
    #    mutation matrix, the non-interference report, and the standalone
    #    TC-03 fuzz/differential artifact.
    # ------------------------------------------------------------------
    consistency_results: list[dict[str, Any]] = []
    for gate_id, fresh_gate_verdict in sorted(tc4_fresh.get("verdicts", {}).items()):
        stored_path = witness_root / "verdicts" / f"{gate_id}.json"
        if stored_path.is_file():
            consistency_results.append(
                compare_normalized(
                    label=gate_id,
                    fresh_value=fresh_gate_verdict,
                    stored_path=stored_path,
                    volatile_keys=volatile_keys,
                )
            )
        else:
            consistency_results.append({"label": gate_id, "stored_path": str(stored_path), "byte_consistent": False})

    mutation_stored = witness_root / "mutations" / "matrix.json"
    if mutation_stored.is_file():
        consistency_results.append(
            compare_normalized(
                label="mutation_matrix",
                fresh_value=tc4_fresh.get("mutation_matrix", {}),
                stored_path=mutation_stored,
                volatile_keys=volatile_keys,
            )
        )

    noninterference_stored = witness_root / "noninterference" / "report.json"
    if noninterference_stored.is_file():
        consistency_results.append(
            compare_normalized(
                label="noninterference_report",
                fresh_value=tc4_fresh.get("noninterference", {}),
                stored_path=noninterference_stored,
                volatile_keys=volatile_keys,
            )
        )

    tc3_stored = witness_root / "fuzz" / "differential_results.json"
    if tc3_stored.is_file():
        consistency_results.append(
            compare_normalized(
                label="tc03_differential_results",
                fresh_value=tc3_fresh,
                stored_path=tc3_stored,
                volatile_keys=volatile_keys,
            )
        )

    consistency_path = scenario_root / "byte_consistency_report.json"
    write_json(
        consistency_path,
        {
            "schema_id": "turingos.fce.s2.byte_consistency_report.v1",
            "normalization_spec": rel(repo, repo / "tools" / "certification" / "NORMALIZATION_SPEC.json"),
            "normalization_spec_sha256": sha256_file(repo / "tools" / "certification" / "NORMALIZATION_SPEC.json"),
            "results": consistency_results,
        },
    )
    evidence_files.append(consistency_path)
    all_byte_consistent = bool(consistency_results) and all(
        item["byte_consistent"] for item in consistency_results
    )
    criteria.append(
        {
            "criterion": "reverified_verdicts_byte_consistent_with_stored",
            "result": all_byte_consistent,
            "evidence": rel(root, consistency_path),
        }
    )

    # ------------------------------------------------------------------
    # 4. TC5 packet self-check: confirms the packet-local TC-01..TC-09
    #    rollup is PASS, the packet manifest digests verify, and the packet
    #    does NOT overclaim (TC-10 must remain NOT_RUN, claim boundary must
    #    remain false) -- this is itself a real subprocess audit, not a
    #    cached-field read.
    # ------------------------------------------------------------------
    tc5_command = run_command(
        name="tc5_packet_check",
        argv=[
            "python3",
            str(repo / "tools" / "theory" / "build_tc5_packet.py"),
            "--root",
            str(witness_root),
            "--check",
        ],
        cwd=repo,
        out_dir=scenario_root,
    )
    commands.append(tc5_command)
    try:
        tc5_report = json.loads(tc5_command["stdout_text"])
    except json.JSONDecodeError:
        tc5_report = {}
    tc5_pass = (
        tc5_command["exit_code"] == 0
        and tc5_report.get("verdict") == "PASS"
        and tc5_report.get("tc01_tc09_all_pass") is True
        and tc5_report.get("tc10_verdict") == "NOT_RUN"
        and tc5_report.get("turing_completeness_claim_allowed") is False
    )
    criteria.append(
        {
            "criterion": "tc5_packet_check_pass_and_not_overclaiming",
            "result": tc5_pass,
            "evidence": rel(root, tc5_command["stdout_path"]),
        }
    )

    # ------------------------------------------------------------------
    # 5. TC-10 handling. The packet-local slot must correctly remain
    #    NOT_RUN/implementer-forbidden (an implementer-written PASS there
    #    would itself be the self-closure overclaim RES_M2 §4 forbids). The
    #    actual external verifier artifact is the M5.P4 closure certificate
    #    over M1.G/M2.TC5/M2.G: verified via the already-vetted custody
    #    machinery in tools/certification/checks/entry_criteria.py
    #    (imported, not re-implemented), plus its own tc10_execution record.
    # ------------------------------------------------------------------
    tc10_slot_path = witness_root / "verdicts" / "TC-10.json"
    tc10_slot = load_json(tc10_slot_path) if tc10_slot_path.is_file() else {}
    tc10_slot_guarded = (
        tc10_slot.get("verdict") == "NOT_RUN"
        and tc10_slot.get("not_run_is_fail") is True
        and tc10_slot.get("implementer_may_run") is False
        and tc10_slot.get("external_verifier_required") is True
        and tc10_slot.get("external_verifier_artifact") is None
    )
    tc10_slot_summary_path = scenario_root / "tc10_packet_local_slot.json"
    write_json(
        tc10_slot_summary_path,
        {
            "schema_id": "turingos.fce.s2.tc10_packet_local_slot.v1",
            "source": str(tc10_slot_path),
            "observed": tc10_slot,
            "correctly_guarded": tc10_slot_guarded,
        },
    )
    evidence_files.append(tc10_slot_summary_path)
    criteria.append(
        {
            "criterion": "tc10_packet_local_slot_correctly_guarded_not_run",
            "result": tc10_slot_guarded,
            "evidence": rel(root, tc10_slot_summary_path),
        }
    )

    entry_criteria = load_module(
        repo / "tools" / "certification" / "checks" / "entry_criteria.py", "fce_s2_entry_criteria"
    )
    external_certs = entry_criteria.external_certificate_index(plan_root)
    m2_cert_entry = external_certs.get("M2.G")
    m2_cert_raw: dict[str, Any] = {}
    if m2_cert_entry is not None:
        cert_path = Path(m2_cert_entry["path"])
        if not cert_path.is_absolute():
            cert_path = (plan_root / m2_cert_entry["path"]).resolve()
        if cert_path.is_file():
            m2_cert_raw = load_json(cert_path)

    cert_targets = entry_criteria.certificate_targets(m2_cert_raw) if m2_cert_raw else set()
    cert_custody_ok = entry_criteria.certificate_custody_ok(m2_cert_raw) if m2_cert_raw else False
    verifier_identity = str(m2_cert_raw.get("verifier", {}).get("identity", "")) if m2_cert_raw else ""
    identity_distinct = bool(verifier_identity) and verifier_identity.lower() not in IMPLEMENTER_IDENTITY_MARKERS
    tc10_execution = m2_cert_raw.get("verification", {}).get("tc10_execution", {}) if m2_cert_raw else {}
    tc10_action_executed = (
        tc10_execution.get("executed_by_this_audit") is True
        and tc10_execution.get("all_subchecks_result") == "PASS"
    )
    targets_cover_tc_witness = bool({"M2.G", "M2.TC5", "M1.G"} & cert_targets)

    tc10_external_present = (
        m2_cert_entry is not None
        and m2_cert_raw.get("verdict") == "PASS"
        and cert_custody_ok
        and identity_distinct
        and targets_cover_tc_witness
        and tc10_action_executed
    )

    external_verification_path = scenario_root / "tc10_external_verification.json"
    write_json(
        external_verification_path,
        {
            "schema_id": "turingos.fce.s2.tc10_external_verification.v1",
            "certificate_path": m2_cert_entry.get("path") if m2_cert_entry else None,
            "certificate_sha256": sha256_file(Path(m2_cert_entry["path"]).resolve())
            if m2_cert_entry and (plan_root / m2_cert_entry["path"]).resolve().is_file()
            else None,
            "certificate_schema_id": m2_cert_raw.get("schema_id"),
            "certificate_verdict": m2_cert_raw.get("verdict"),
            "certificate_targets": sorted(cert_targets),
            "verifier_identity": verifier_identity,
            "verifier_kind": m2_cert_raw.get("verifier", {}).get("kind"),
            "custody": entry_criteria.collect_custody_booleans(m2_cert_raw) if m2_cert_raw else {},
            "custody_ok": cert_custody_ok,
            "identity_distinct_from_implementer_markers": identity_distinct,
            "tc10_execution": tc10_execution,
            "tc10_action_executed_by_external_verifier": tc10_action_executed,
            "present_with_distinct_custody_verified_identity": tc10_external_present,
        },
    )
    evidence_files.append(external_verification_path)
    criteria.append(
        {
            "criterion": "tc10_external_artifact_present_with_distinct_verifier_identity",
            "result": tc10_external_present,
            "evidence": rel(root, external_verification_path),
        }
    )

    # ------------------------------------------------------------------
    # 6. Halting AND non-halting example classes both present, recomputed
    #    independently from the real bundle_manifest.json (not merely
    #    trusting its own declared summary counts).
    # ------------------------------------------------------------------
    bundle_manifest_path = witness_root / "bundle_manifest.json"
    bundle_manifest = load_json(bundle_manifest_path) if bundle_manifest_path.is_file() else {}
    classification = classify_halting_nonhalting(bundle_manifest)
    classification_path = scenario_root / "halting_nonhalting_classes.json"
    write_json(
        classification_path,
        {
            "schema_id": "turingos.fce.s2.halting_nonhalting_classes.v1",
            "source": str(bundle_manifest_path),
            **classification,
        },
    )
    evidence_files.append(classification_path)
    classes_present = (
        classification["halting_count_recomputed"] > 0
        and classification["nonhalting_count_recomputed"] > 0
        and classification["counts_self_consistent"]
    )
    criteria.append(
        {
            "criterion": "halting_and_nonhalting_example_classes_present",
            "result": classes_present,
            "evidence": rel(root, classification_path),
        }
    )

    # ------------------------------------------------------------------
    # 7. Non-interference gate: freshly re-simulated (this run's
    #    tc4_fresh["noninterference"]), not a cached-file read -- confirms
    #    an ignored economy-surface event (MarketCreated, representative of
    #    the market/PPUT/HCI event classes ADR-M2-007 requires the reducer
    #    to never consult) cannot change the reduced machine state, and that
    #    the sabotage meta-test proves the check is non-vacuous.
    # ------------------------------------------------------------------
    noninterference_fresh = tc4_fresh.get("noninterference", {})
    noninterference_pass = (
        noninterference_fresh.get("verdict") == "PASS"
        and noninterference_fresh.get("interleave_invariant") is True
        and noninterference_fresh.get("sabotage_meta_test") == "FAILS_AS_EXPECTED"
    )
    criteria.append(
        {
            "criterion": "noninterference_gate_pass_economy_signals_ignored",
            "result": noninterference_pass,
            "evidence": rel(root, tc4_command["stdout_path"]),
        }
    )

    # ------------------------------------------------------------------
    # Assemble README + CLAIM_BOUNDARY (mirrors the other REAL scenarios).
    # ------------------------------------------------------------------
    readme_path = scenario_root / "README.md"
    readme_path.write_text(
        "\n".join(
            [
                "# FCE-S2 Universality Under Integration (G3)",
                "",
                "Evidence label: REAL (live `turing` clone witness bundle at "
                f"`{rel(repo, witness_root)}`, live TC audit tools re-run without "
                "`--write`, live M5.P4 closure certificate -- not fixtures).",
                "",
                "This scenario verifies the M2 Turing-completeness witness holds from",
                "this certification clone: bundle digests, a real re-run of the TC-03",
                "fuzz/differential audit and the full TC4 local audit battery",
                "(TC-01..TC-09, mutation matrix, non-interference), byte-consistency of",
                "the freshly recomputed verdicts against the stored ones, presence of an",
                "external, custody-separated TC-10 verifier artifact, and that halting",
                "and non-halting witness program classes are both present.",
                "",
                f"witness_bundle_digests_ok: {digests_ok}",
                f"tc01_tc09_reverified_pass: {tc3_pass and tc4_pass and per_gate_pass}",
                f"byte_consistent_with_stored: {all_byte_consistent}",
                f"tc10_external_artifact_present: {tc10_external_present}",
                f"halting_and_nonhalting_classes_present: {classes_present}",
                f"noninterference_gate_pass: {noninterference_pass}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    evidence_files.append(readme_path)

    claim_boundary_path = scenario_root / "CLAIM_BOUNDARY.json"
    write_json(
        claim_boundary_path,
        {
            "schema_id": "CLAIM_BOUNDARY.v2",
            "evidence_class": "REAL",
            "claims": [
                "FCE-S2 re-verified the M2 TC witness (bundle digests, TC-01..TC-09 "
                "local audits, TC-10 external-verifier artifact custody) from this "
                "certification clone"
            ],
            "non_claims": [
                "not an unqualified Turing-completeness claim",
                "not TC-10 executed by this scenario or by any implementer context",
                "not M2 enablement",
                "not a full aggregate FCE suite run",
                "not release eligibility",
                "not CLOSED/RELEASED/RATIFIED",
                "not SHIPPED",
                "not OG-10/genesis signature",
            ],
        },
    )
    evidence_files.append(claim_boundary_path)

    if not tc10_external_present:
        automatic_fail_reason = "tc10_external_artifact_absent"
    elif not digests_ok:
        automatic_fail_reason = "witness_bundle_digest_mismatch"
    elif not (tc3_pass and tc4_pass and per_gate_pass and all_byte_consistent):
        automatic_fail_reason = "universality_witness_reverification_failed"
    elif not classes_present:
        automatic_fail_reason = "halting_nonhalting_classes_missing"
    elif not noninterference_pass:
        automatic_fail_reason = "noninterference_gate_failed"
    else:
        automatic_fail_reason = None

    verdict = build_verdict(
        root=root,
        scenario_id=scenario_id,
        commands=commands,
        criteria=criteria,
        started=started,
        evidence_files=evidence_files,
        automatic_fail_reason=automatic_fail_reason,
    )
    write_json(scenario_root / f"{scenario_id}_verdict.json", verdict)
    print(
        json.dumps(
            {
                "scenario_id": scenario_id,
                "verdict": verdict["verdict"],
                "witness_root": str(witness_root),
                "tc10_external_present": tc10_external_present,
            },
            sort_keys=True,
        )
    )
    return 0 if verdict["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
