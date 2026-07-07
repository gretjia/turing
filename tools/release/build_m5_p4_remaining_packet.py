#!/usr/bin/env python3
"""Build the M5.P4 GitHub-only packet for remaining M1/M2 closure jobs."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
PLAN = REPO.parent / "PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702"
PACKET_REL = Path("evidence/verification/m5_p4_m1_m2_closure_20260704")
PACKET_ROOT = REPO / PACKET_REL
PLAN_COPY_ROOT = PACKET_REL / "plan_artifacts" / PLAN.name
M2_ROOT_REL = Path("evidence/theory/turing_completeness_witness_20260703")


class PacketError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, value: str, *, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO).as_posix()


def plan_rel(path: Path) -> str:
    return path.resolve().relative_to(PLAN).as_posix()


def copy_plan_file(source: Path, source_map: list[dict[str, str]]) -> Path:
    if not source.exists():
        raise PacketError(f"missing plan artifact: {source}")
    dest_rel = PLAN_COPY_ROOT / plan_rel(source)
    dest = REPO / dest_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    source_map.append(
        {
            "github_path": dest_rel.as_posix(),
            "original_path": str(source),
            "sha256": sha256(dest),
        }
    )
    return dest


def copy_plan_tree(source: Path, source_map: list[dict[str, str]]) -> None:
    if not source.exists():
        raise PacketError(f"missing plan artifact tree: {source}")
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        if "micro.git" in path.parts:
            continue
        copy_plan_file(path, source_map)


def repo_artifact(path: Path) -> dict[str, str]:
    if not path.exists():
        raise PacketError(f"missing repo artifact: {path}")
    return {
        "github_path": repo_rel(path),
        "original_path": str(path),
        "sha256": sha256(path),
    }


def read_m2_manifest_rels() -> list[Path]:
    manifest = REPO / M2_ROOT_REL / "packet/PACKET_MANIFEST.sha256"
    if not manifest.exists():
        raise PacketError(f"missing M2 TC5 manifest: {manifest}")
    rels: list[Path] = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        _digest, rel = line.split(maxsplit=1)
        rels.append(Path(rel))
    return rels


def collect_repo_artifacts() -> list[dict[str, str]]:
    rels = set(read_m2_manifest_rels())
    rels.update(
        [
            M2_ROOT_REL / "packet/PACKET_MANIFEST.sha256",
            Path("pack/04_registries/event_registry_v5_3_1.json"),
            Path("tools/bench/audit_micro_tape_decision_dag.py"),
            Path("tools/ci/run_m1a_gates.sh"),
            Path("tests/test_m1a_gate_quartet.py"),
            Path("tools/release/build_m5_p4_remaining_packet.py"),
            Path("tests/test_m5_p4_remaining_github_audit_packet.py"),
        ]
    )
    for path in (REPO / "tools/gates").rglob("*"):
        if path.is_file():
            rels.add(path.relative_to(REPO))
    return [repo_artifact(REPO / rel) for rel in sorted(rels, key=lambda p: p.as_posix())]


def copy_plan_artifacts() -> list[dict[str, str]]:
    source_map: list[dict[str, str]] = []
    plan_files = [
        PLAN / "PROGRESS_TRACKER.md",
        PLAN / "modules/MODULE_M1_canonical_substrate.md",
        PLAN / "modules/MODULE_M2_tc_witness.md",
        PLAN / "modules/MODULE_M5_independent_verification.md",
        PLAN / "research/RES_M1_canonical_substrate_integrity.md",
        PLAN / "research/RES_M2_turing_completeness_witness.md",
        PLAN / "research/RES_M5_independent_verification.md",
    ]
    for pattern in ["ADR-M1-*.md", "ADR-M2-*.md", "ADR-M5-*.md"]:
        plan_files.extend(sorted((PLAN / "adr").glob(pattern)))
    evidence_files = [
        "M1A_ARTIFACT_MANIFEST.sha256",
        "M1A_GATE_VERDICT.json",
        "M1B_ARTIFACT_MANIFEST.sha256",
        "M1B_FRESH_CONTEXT_VERIFIER.json",
        "M1C_ARTIFACT_MANIFEST.sha256",
        "M1C_FRESH_CONTEXT_VERIFIER_AFTER_RECEIPT.json",
        "M1D_ARTIFACT_MANIFEST.sha256",
        "M1D_FRESH_CONTEXT_VERIFIER.json",
        "M1E_BLOCKER_FIX_ARTIFACT_MANIFEST.sha256",
        "M1E_FRESH_CONTEXT_VERIFIER.json",
        "M1G_ARTIFACT_ROLLUP.json",
        "M1G_DRIFT_CHECKLIST.md",
        "M1G_FRESH_CONTEXT_VERIFIER.json",
        "M1G_GATE_VERDICT.json",
        "M2_TC0_VERDICT.json",
        "M2_TC1_VERDICT.json",
        "M2_TC2_VERDICT.json",
        "M2_TC3_VERDICT.json",
        "M2_TC4_VERDICT.json",
        "M2_TC5_ARTIFACT_MANIFEST.sha256",
        "M2_TC5_FRESH_CONTEXT_VERIFIER.json",
        "M2_TC5_PACKET_DESCRIPTOR.json",
        "M2_TC5_VERDICT.json",
        "M2G_ARTIFACT_MANIFEST.sha256",
        "M2G_ARTIFACT_ROLLUP.json",
        "M2G_DRIFT_CHECKLIST.md",
        "M2G_FRESH_CONTEXT_VERIFIER.json",
        "M2G_GATE_VERDICT.json",
        "M2G_VERDICT.json",
    ]
    plan_files.extend(PLAN / "evidence/session_20260702" / name for name in evidence_files)
    for path in sorted(set(plan_files)):
        copy_plan_file(path, source_map)
    for tree_name in [
        "M1B_REAL_GROK_OS_KEYRING_SMOKE_V2",
        "M1C_REAL_GROK_PROVIDER_RECEIPT",
        "M1G_RECHECK_M1B_STRICT_AUDIT",
        "M1G_RECHECK_M1C_STRICT_AUDIT",
    ]:
        copy_plan_tree(PLAN / "evidence/session_20260702" / tree_name, source_map)
    return sorted(source_map, key=lambda item: item["github_path"])


def rewrite_coverage(source: Path, destination: Path) -> None:
    data = json.loads(source.read_text(encoding="utf-8"))
    for run in data.get("turingos_arm_runs", []):
        if not isinstance(run, dict):
            continue
        for key in ["micro_tape_bundle", "worker_log_dir", "project", "micro_git"]:
            value = run.get(key)
            if not isinstance(value, str):
                continue
            original = Path(value)
            try:
                rel = original.resolve().relative_to(PLAN)
            except ValueError:
                continue
            packet_path = PLAN_COPY_ROOT / rel
            run[key] = packet_path.as_posix()
    write_json(destination, data)


def packet_json(source_count: int, repo_count: int) -> dict[str, Any]:
    return {
        "schema_id": "turingos.m5.p4.github_module_closure_packet.v1",
        "packet_kind": "M5.P4_MODULE_CLOSURE_GITHUB_PACKET",
        "audit_surface": "github_only",
        "repository_url": "https://github.com/gretjia/turing",
        "target_branch": "goal/mini-swe-bench-grok-worker",
        "packet_root": PACKET_REL.as_posix(),
        "targets": ["M1.G", "M2.TC5", "M2.G"],
        "status_ceiling": "ADDRESSED",
        "closure_certificate_schema_id": "turingos.closure_certificate.v1",
        "exact_commit_supplied_out_of_band": True,
        "m2_tc10_external_action_required": True,
        "copied_plan_artifact_count": source_count,
        "repo_native_artifact_count": repo_count,
        "primary_files": {
            "manifest": (PACKET_REL / "PACKET_MANIFEST.sha256").as_posix(),
            "source_map": (PACKET_REL / "SOURCE_MAP.json").as_posix(),
            "repo_artifacts": (PACKET_REL / "REPO_ARTIFACTS.json").as_posix(),
            "prompt_template": (PACKET_REL / "AUDITOR_PROMPT_TEMPLATE.md").as_posix(),
        },
        "gate_verdicts": {
            "M1.G": (PLAN_COPY_ROOT / "evidence/session_20260702/M1G_GATE_VERDICT.json").as_posix(),
            "M2.G": (PLAN_COPY_ROOT / "evidence/session_20260702/M2G_GATE_VERDICT.json").as_posix(),
        },
        "m2_tc5_packet_descriptor": (
            PLAN_COPY_ROOT / "evidence/session_20260702/M2_TC5_PACKET_DESCRIPTOR.json"
        ).as_posix(),
        "repo_native_m2_tc5_packet": (M2_ROOT_REL / "packet/M2_TC5_PACKET.json").as_posix(),
        "packet_local_checks": {
            "M1.G": (PACKET_REL / "packet_checks/run_m1_g_recheck.sh").as_posix(),
            "M2.TC5/M2.G": (PACKET_REL / "packet_checks/run_m2_tc5_boundary_check.sh").as_posix(),
        },
        "auditor_must_not_use": [
            "implementation chat",
            "local plan directory",
            "agent memory summaries",
            "uncommitted local files",
        ],
        "non_claims": [
            "This packet does not itself confer external verification.",
            "This packet does not claim TC-10 PASS, M2.G success, Turing-completeness, release, SHIPPED status, M2 enablement, OG-10/genesis signature, or constitution-byte change.",
            "Auditor verdict may be PASS or FAIL; FAIL requires repair and resubmission with a new packet.",
        ],
    }


def prompt_text() -> str:
    return f"""# M5.P4 Remaining Module Closure Audit Prompt Template

You are the custody-separated external auditor for TuringOS M5.P4 remaining module closure jobs.

Do not use implementation chat, local plan-directory files, agent memory summaries, or uncommitted local files. Use only the GitHub repository, branch, exact commit SHA supplied by the owner, and files committed under this packet.

## Repository

- Repository: `https://github.com/gretjia/turing`
- Branch: `goal/mini-swe-bench-grok-worker`
- Exact commit: supplied by owner in the surrounding prompt
- Packet root: `{PACKET_REL.as_posix()}/`

## Audit Scope

Audit M5.P4 module closure queue targets:

- `M1.G`
- `M2.TC5`
- `M2.G`

Do not audit M3.G, M4.G, M5.G, M6.G, FCE.RUN, release eligibility, or SHIPPED status from this packet unless the owner supplies a separate exact-SHA packet for those targets.

## Required Inputs

Start from:

- `{PACKET_REL.as_posix()}/PACKET.json`
- `{PACKET_REL.as_posix()}/SOURCE_MAP.json`
- `{PACKET_REL.as_posix()}/REPO_ARTIFACTS.json`
- `{PACKET_REL.as_posix()}/PACKET_MANIFEST.sha256`

The packet contains copied plan artifacts under:

- `{PACKET_REL.as_posix()}/plan_artifacts/`

Repo-native artifacts remain at their normal GitHub paths and are listed in `REPO_ARTIFACTS.json`.

## Custody Requirements

You must be able to truthfully set all six custody booleans to true:

- `fresh_clone`
- `no_shared_conversation_state`
- `no_implementer_transcript`
- `own_credentials`
- `cross_family_or_human`
- `own_custody_output`

If any custody boolean is false, return `FAIL`.

## Required Checks

1. Fresh-clone the GitHub repository and checkout the exact owner-supplied commit SHA.
2. Verify `PACKET_MANIFEST.sha256` from inside the packet root:

   ```bash
   cd {PACKET_REL.as_posix()}
   sha256sum -c PACKET_MANIFEST.sha256
   ```

3. Verify every copied plan artifact in `SOURCE_MAP.json` exists at its `github_path` and matches its `sha256`.
4. Verify every repo-native artifact in `REPO_ARTIFACTS.json` exists at its GitHub path and matches its `sha256`.
5. Run the packet-local M1.G recheck:

   ```bash
   bash {PACKET_REL.as_posix()}/packet_checks/run_m1_g_recheck.sh
   ```

6. Run the packet-local M2.TC5/M2.G boundary check:

   ```bash
   bash {PACKET_REL.as_posix()}/packet_checks/run_m2_tc5_boundary_check.sh
   ```

7. For `M2.TC5`, run TC-10 yourself from the clean clone. The implementer-side `TC-10.json` is intentionally `NOT_RUN` with `not_run_is_fail: true`; treating it as PASS is a FAIL.
8. For `M1.G`, decide whether the packet supports only this claim:

   `M1.G is ADDRESSED at the implementer ceiling as a canonical-substrate G2 roll-up, not external verification.`

9. For `M2.TC5/M2.G`, decide whether the clean-clone TC-10 action and M2 boundary support PASS or FAIL. Do not infer Turing-completeness unless TC-10 is actually executed under your custody and its result supports the claim boundary.
10. Check that no target claims release, SHIPPED status, M2 enablement, OG-10/genesis signature, constitution-byte change, or external verification before your certificate.

## Output

Return one JSON object using `ClosureCertificate.v1` shape:

- `schema_id`: `turingos.closure_certificate.v1`
- `subject.gate_id`: `M5.P4`
- `subject.module_targets`: `["M1.G", "M2.TC5", "M2.G"]`
- `subject.repo_url`: `https://github.com/gretjia/turing`
- `subject.branch`: `goal/mini-swe-bench-grok-worker`
- `subject.commit_sha`: exact commit you audited
- `subject.packet_root`: `{PACKET_REL.as_posix()}`
- `verifier.kind`: `external_human_operator` or `external_cross_family_model`
- `verification.commands_run`: include commands and exit codes, including your TC-10 command/result
- `verification.digest_manifest_result`: `PASS` or `FAIL`
- `verification.gate_predicate_result`: `PASS` or `FAIL`
- `verdict`: `PASS` or `FAIL`

If the verdict is `FAIL`, include machine-readable reasons. Do not repair the packet. Do not infer from implementation chat. Do not grant release or SHIPPED status.
"""


def m1_check_script() -> str:
    return f"""#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
PACKET_ROOT="$REPO_ROOT/{PACKET_REL.as_posix()}"
PLAN_ROOT="$PACKET_ROOT/plan_artifacts/{PLAN.name}"
TMP_ROOT="$(mktemp -d "${{TMPDIR:-/tmp}}/m5p4_m1_recheck.XXXXXX")"

cleanup() {{
  rm -rf "$TMP_ROOT"
}}
trap cleanup EXIT

python3 - "$PACKET_ROOT" "$PLAN_ROOT" <<'PY'
import hashlib
import json
import pathlib
import sys

packet_root = pathlib.Path(sys.argv[1])
plan_root = pathlib.Path(sys.argv[2])
repo_root = packet_root.parents[2]

required = [
    plan_root / "evidence/session_20260702/M1G_ARTIFACT_ROLLUP.json",
    plan_root / "evidence/session_20260702/M1G_DRIFT_CHECKLIST.md",
    plan_root / "evidence/session_20260702/M1G_GATE_VERDICT.json",
    plan_root / "evidence/session_20260702/M1G_FRESH_CONTEXT_VERIFIER.json",
]
for path in required:
    assert path.exists(), f"missing {{path}}"

gate = json.loads(required[2].read_text(encoding="utf-8"))
rollup = json.loads(required[0].read_text(encoding="utf-8"))
fresh = json.loads(required[3].read_text(encoding="utf-8"))

assert gate["gate_id"] == "M1.G"
assert gate["status"] == "ADDRESSED"
assert gate["alignment_verify"] == "GREEN"
assert all(item["verdict"] == "PASS" for item in gate["checklist_results"])
assert rollup["gate"] == "M1.G"
assert rollup["status_ceiling"] == "ADDRESSED"
assert rollup["ship_gate_claim_boundary"]["external_verification_claim_allowed"] is False
assert all(status == "ADDRESSED" for status in rollup["child_phase_statuses"].values())
assert fresh["verdict"] == "PASS"

source_map = json.loads((packet_root / "SOURCE_MAP.json").read_text(encoding="utf-8"))
source_sha_by_path = {{entry["github_path"]: entry["sha256"] for entry in source_map}}
for path in required:
    github_path = path.relative_to(repo_root).as_posix()
    assert github_path in source_sha_by_path, f"missing SOURCE_MAP entry for {{github_path}}"
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    assert actual == source_sha_by_path[github_path], f"digest mismatch for {{github_path}}"

print("M5_P4_REMAINING_PACKET_M1_METADATA_CHECK_PASS")
PY

bash "$REPO_ROOT/tools/ci/run_m1a_gates.sh" --self-test
bash "$REPO_ROOT/tools/ci/run_m1a_gates.sh"

python3 "$REPO_ROOT/tools/bench/audit_micro_tape_decision_dag.py" \
  --coverage "$PACKET_ROOT/packet_checks/m1b_packet_coverage.json" \
  --strict-vpput \
  --strict-terminal-market \
  --require-authorization-head \
  --require-cost-provenance \
  --require-sandbox-provenance \
  --out-dir "$TMP_ROOT/m1b"

python3 "$REPO_ROOT/tools/bench/audit_micro_tape_decision_dag.py" \
  --coverage "$PACKET_ROOT/packet_checks/m1c_packet_coverage.json" \
  --strict-vpput \
  --strict-terminal-market \
  --require-authorization-head \
  --require-cost-provenance \
  --require-sandbox-provenance \
  --out-dir "$TMP_ROOT/m1c"

python3 - "$TMP_ROOT" <<'PY'
import json
import pathlib
import sys

tmp = pathlib.Path(sys.argv[1])
required_checks = [
    "authorization_head",
    "cost_provenance",
    "sandbox_provenance",
    "terminal_golden_path_anchors_to_accepted_head",
    "vpput_accounting",
]
for label in ["m1b", "m1c"]:
    audit = json.loads((tmp / label / "micro_tape_decision_dag_audit.json").read_text(encoding="utf-8"))
    assert audit["verdict"] == "PASS", label
    assert audit["strict_findings"] == [], label
    assert audit["aggregate"]["sandbox_host_assumed_count"] == 0, label
    run = audit["runs"][0]
    for check in required_checks:
        assert run["checks"][check] == "PASS", (label, check, run["checks"].get(check))

print("M5_P4_REMAINING_PACKET_M1_G_RECHECK_PASS")
PY
"""


def m2_check_script() -> str:
    return f"""#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
PACKET_ROOT="$REPO_ROOT/{PACKET_REL.as_posix()}"
PLAN_ROOT="$PACKET_ROOT/plan_artifacts/{PLAN.name}"
M2_ROOT="$REPO_ROOT/{M2_ROOT_REL.as_posix()}"

cd "$REPO_ROOT"
sha256sum -c "{M2_ROOT_REL.as_posix()}/packet/PACKET_MANIFEST.sha256"

cd "$M2_ROOT"
sha256sum -c bundle_sha256s.txt

cd "$REPO_ROOT"
PYTHONPATH=src python3 -m pytest -q tests/test_theory_tc4_audit.py tests/test_theory_tc5_packet.py
python3 tools/theory/audit_tc4_witness.py --root "{M2_ROOT_REL.as_posix()}" >/tmp/m5p4_m2_tc4_audit.json
python3 tools/theory/build_tc5_packet.py --root "{M2_ROOT_REL.as_posix()}" --check >/tmp/m5p4_m2_tc5_check.json

python3 - "$PACKET_ROOT" "$PLAN_ROOT" "$M2_ROOT" <<'PY'
import hashlib
import json
import pathlib
import sys

packet_root = pathlib.Path(sys.argv[1])
plan_root = pathlib.Path(sys.argv[2])
m2_root = pathlib.Path(sys.argv[3])
repo_root = packet_root.parents[2]

tc10 = json.loads((m2_root / "verdicts/TC-10.json").read_text(encoding="utf-8"))
descriptor = json.loads((plan_root / "evidence/session_20260702/M2_TC5_PACKET_DESCRIPTOR.json").read_text(encoding="utf-8"))
tc5_verdict = json.loads((plan_root / "evidence/session_20260702/M2_TC5_VERDICT.json").read_text(encoding="utf-8"))
m2g_gate = json.loads((plan_root / "evidence/session_20260702/M2G_GATE_VERDICT.json").read_text(encoding="utf-8"))
m2g_rollup = json.loads((plan_root / "evidence/session_20260702/M2G_ARTIFACT_ROLLUP.json").read_text(encoding="utf-8"))
tc5_packet = json.loads((m2_root / "packet/M2_TC5_PACKET.json").read_text(encoding="utf-8"))
boundary = json.loads((m2_root / "packet/CLAIM_BOUNDARY.json").read_text(encoding="utf-8"))

assert tc10["gate_id"] == "TC-10"
assert tc10["verdict"] == "NOT_RUN"
assert tc10["not_run_is_fail"] is True
assert tc10["implementer_may_run"] is False
assert tc10["external_verifier_required"] is True

assert descriptor["phase"] == "M2.TC5"
assert descriptor["phase_status"] == "ADDRESSED"
assert descriptor["external_verifier"]["status"] == "NOT_RUN"
assert descriptor["claims"]["tc10_external_artifact_exists"] is False
assert descriptor["claims"]["turing_completeness_claim_allowed"] is False
assert tc5_verdict["phase"] == "M2.TC5"
assert tc5_verdict["phase_status"] == "ADDRESSED"
assert tc5_verdict["not_run_is_fail"] is True
assert tc5_verdict["explicit_non_claims"]["tc10_passed"] is False

assert m2g_gate["gate_id"] == "M2.G"
assert m2g_gate["status"] == "ADDRESSED"
assert m2g_gate["tc10_verdict"] == "NOT_RUN"
assert m2g_gate["tc10_external_artifact_exists"] is False
assert m2g_gate["turing_completeness_claim_allowed"] is False
assert m2g_rollup["tc10_blocker"]["tc10_verdict"] == "NOT_RUN"
assert m2g_rollup["ship_gate_claim_boundary"]["external_verification_claim_allowed"] is False

assert tc5_packet["phase"] == "M2.TC5"
assert tc5_packet["tc10"]["verdict"] == "NOT_RUN"
assert tc5_packet["claims"]["tc10_external_artifact_exists"] is False
assert boundary["tc10_external_artifact_exists"] is False
assert boundary["turing_completeness_claim_allowed"] is False

repo_artifacts = json.loads((packet_root / "REPO_ARTIFACTS.json").read_text(encoding="utf-8"))
repo_sha_by_path = {{entry["github_path"]: entry["sha256"] for entry in repo_artifacts}}
for path in [
    m2_root / "packet/M2_TC5_PACKET.json",
    m2_root / "packet/PACKET_MANIFEST.sha256",
    m2_root / "verdicts/TC-10.json",
    repo_root / "tools/theory/audit_tc4_witness.py",
    repo_root / "tools/theory/build_tc5_packet.py",
]:
    github_path = path.relative_to(repo_root).as_posix()
    assert github_path in repo_sha_by_path, f"missing REPO_ARTIFACTS entry for {{github_path}}"
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    assert actual == repo_sha_by_path[github_path], f"digest mismatch for {{github_path}}"

print("M5_P4_REMAINING_PACKET_M2_TC5_BOUNDARY_CHECK_PASS")
PY
"""


def write_packet_files(source_count: int, repo_count: int) -> None:
    write_json(PACKET_ROOT / "PACKET.json", packet_json(source_count, repo_count))
    write_text(PACKET_ROOT / "AUDITOR_PROMPT_TEMPLATE.md", prompt_text())
    write_text(PACKET_ROOT / "packet_checks/run_m1_g_recheck.sh", m1_check_script(), executable=True)
    write_text(PACKET_ROOT / "packet_checks/run_m2_tc5_boundary_check.sh", m2_check_script(), executable=True)

    rewrite_coverage(
        PLAN / "evidence/session_20260702/M1B_REAL_GROK_OS_KEYRING_SMOKE_V2/substrate_coverage.json",
        PACKET_ROOT / "packet_checks/m1b_packet_coverage.json",
    )
    rewrite_coverage(
        PLAN / "evidence/session_20260702/M1C_REAL_GROK_PROVIDER_RECEIPT/substrate_coverage.json",
        PACKET_ROOT / "packet_checks/m1c_packet_coverage.json",
    )


def write_manifest() -> None:
    manifest = PACKET_ROOT / "PACKET_MANIFEST.sha256"
    lines = []
    for path in sorted(PACKET_ROOT.rglob("*")):
        if not path.is_file() or path == manifest:
            continue
        lines.append(f"{sha256(path)}  {path.relative_to(PACKET_ROOT).as_posix()}")
    write_text(manifest, "\n".join(lines) + "\n")


def build() -> dict[str, Any]:
    if PACKET_ROOT.exists():
        shutil.rmtree(PACKET_ROOT)
    source_map = copy_plan_artifacts()
    repo_artifacts = collect_repo_artifacts()
    write_json(PACKET_ROOT / "SOURCE_MAP.json", source_map)
    write_json(PACKET_ROOT / "REPO_ARTIFACTS.json", repo_artifacts)
    write_packet_files(len(source_map), len(repo_artifacts))
    write_manifest()
    return {
        "packet_root": PACKET_REL.as_posix(),
        "source_map_entries": len(source_map),
        "repo_artifact_entries": len(repo_artifacts),
        "packet_sha256": sha256(PACKET_ROOT / "PACKET.json"),
        "manifest_sha256": sha256(PACKET_ROOT / "PACKET_MANIFEST.sha256"),
    }


def run_check() -> None:
    subprocess.run(["sha256sum", "-c", "PACKET_MANIFEST.sha256"], cwd=PACKET_ROOT, check=True)
    subprocess.run([str(PACKET_ROOT / "packet_checks/run_m1_g_recheck.sh")], cwd=REPO, check=True)
    subprocess.run([str(PACKET_ROOT / "packet_checks/run_m2_tc5_boundary_check.sh")], cwd=REPO, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        run_check()
        return 0
    report = build()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
