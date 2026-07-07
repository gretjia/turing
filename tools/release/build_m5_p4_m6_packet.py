#!/usr/bin/env python3
"""Build the M5.P4 GitHub-only packet for M6.G closure audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
PLAN = REPO.parent / "PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702"
PACKET_REL = Path("evidence/verification/m5_p4_m6_closure_20260704")
PACKET_ROOT = REPO / PACKET_REL
PLAN_COPY_ROOT = PACKET_REL / "plan_artifacts" / PLAN.name


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


def copy_plan_file(source: Path, source_map: list[dict[str, str]]) -> None:
    if not source.exists():
        raise PacketError(f"missing plan artifact: {source}")
    if ".git" in source.parts or "__pycache__" in source.parts or source.suffix == ".pyc":
        return
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


def copy_plan_tree(source: Path, source_map: list[dict[str, str]]) -> None:
    if not source.exists():
        raise PacketError(f"missing plan artifact tree: {source}")
    for path in sorted(source.rglob("*")):
        if path.is_file():
            copy_plan_file(path, source_map)


def collect_plan_artifacts() -> list[dict[str, str]]:
    source_map: list[dict[str, str]] = []
    plan_files = [
        PLAN / "02_EXECUTION_PLAYBOOK.md",
        PLAN / "PROGRESS_TRACKER.md",
        PLAN / "memory/SESSION_STATE.md",
        PLAN / "modules/MODULE_M5_independent_verification.md",
        PLAN / "modules/MODULE_M6_hci_console.md",
        PLAN / "research/RES_M5_independent_verification.md",
        PLAN / "research/RES_M6_hci_projection_console.md",
        PLAN / "m5_verification/schemas/closure_certificate.v1.schema.json",
        PLAN / "m5_verification/tools/validate_closure_certificate.py",
        PLAN / "m6_hci/assemble_m6_gate.py",
        PLAN / "m6_hci/tests/test_m6_g_rollup.sh",
    ]
    for pattern in ["ADR-M5-*.md", "ADR-M6-*.md"]:
        plan_files.extend(sorted((PLAN / "adr").glob(pattern)))

    evidence_names = [
        "M6_P2_RESCUE_RESULT.json",
        "M6_P2_ARTIFACT_MANIFEST.sha256",
        "M6_P2_CARGO_TEST_TRANSCRIPT.txt",
        "M6_P2_PYTEST_TRANSCRIPT.txt",
        "M6_P2_OPERATOR_AUDIT_TRANSCRIPT.txt",
        "M6_P3_STATIC_NO_WRITE_RESULT.json",
        "M6_P3_ARTIFACT_MANIFEST.sha256",
        "M6_P3_NO_WRITE_SELF_TEST_TRANSCRIPT.txt",
        "M6_P3_NO_WRITE_GATE_TRANSCRIPT.txt",
        "M6_P3_PROJECTION_CLIPPY_TRANSCRIPT.txt",
        "M6_P4_DYNAMIC_GATES_RESULT.json",
        "M6_P4_ARTIFACT_MANIFEST.sha256",
        "M6_P4_HEAD_CONSERVATION_TEST_TRANSCRIPT.txt",
        "M6_P4_READONLY_FS_TEST_TRANSCRIPT.txt",
        "M6_P4_CLI_GATES_TRANSCRIPT.txt",
        "M6_P5_PROJECTION_INTEGRITY_RESULT.json",
        "M6_P5_ARTIFACT_MANIFEST.sha256",
        "M6_P5_HCI_GATES_TRANSCRIPT.txt",
        "M6_P5_PROJECTION_INTEGRITY_PYTEST_TRANSCRIPT.txt",
        "M6G_ARTIFACT_ROLLUP.json",
        "M6G_DRIFT_CHECKLIST.md",
        "M6G_GATE_VERDICT.json",
        "M6G_M5_P4_HANDOFF_PACKET.json",
        "M6G_ARTIFACT_MANIFEST.sha256",
        "M6G_ROLLUP_TEST_TRANSCRIPT.txt",
        "M6G_HCI_GATES_TRANSCRIPT.txt",
        "M6G_VERIFY_ALIGNMENT_TRANSCRIPT.txt",
        "M6G_STATUS_LINT_TRANSCRIPT.txt",
        "M6G_CLAIM_LINT_TRANSCRIPT.txt",
        "M6G_SECRET_SCAN_TRANSCRIPT.txt",
        "M6G_REPO_STATUS_TRANSCRIPT.txt",
        "M6G_REPO_DIFF_CHECK_TRANSCRIPT.txt",
    ]
    plan_files.extend(PLAN / "evidence/session_20260702" / name for name in evidence_names)

    for path in sorted(set(plan_files)):
        copy_plan_file(path, source_map)
    for tree in [
        PLAN / "m6_hci",
        PLAN / "rescue/operator_console_v1",
        PLAN / "evidence/session_20260702/m6_p5_hci_gates_20260704",
        PLAN / "evidence/session_20260702/m6_g_hci_gates_20260704",
    ]:
        copy_plan_tree(tree, source_map)
    return sorted(
        {entry["github_path"]: entry for entry in source_map}.values(),
        key=lambda entry: entry["github_path"],
    )


def repo_artifact(path: Path) -> dict[str, str]:
    if not path.exists():
        raise PacketError(f"missing repo artifact: {path}")
    return {
        "github_path": repo_rel(path),
        "original_path": str(path),
        "sha256": sha256(path),
    }


def collect_repo_artifacts() -> list[dict[str, str]]:
    rels: set[Path] = {
        Path(".github/workflows/ci.yml"),
        Path("Cargo.lock"),
        Path("Cargo.toml"),
        Path("crates/turing-cli/Cargo.toml"),
        Path("crates/turing-cli/src/main.rs"),
        Path("crates/turing-cli/tests/cli_gates.rs"),
        Path("crates/turing-projection/Cargo.toml"),
        Path("crates/turing-projection/clippy.toml"),
        Path("crates/turing-projection/src/lib.rs"),
        Path("crates/turing-projection/tests/projection_builder.rs"),
        Path("schemas/operator/operator_view_snapshot.v1.provenance.json"),
        Path("tests/test_hci_no_write_gate.py"),
        Path("tests/test_hci_projection_integrity.py"),
        Path("tests/test_m5_p4_m6_github_audit_packet.py"),
        Path("tools/hci/audit_projection_integrity.py"),
        Path("tools/hci/gate_hci_no_write.sh"),
        Path("tools/hci/make_fixture_micro_tape.py"),
        Path("tools/hci/run_hci_gates.sh"),
        Path("tools/release/build_m5_p4_m6_packet.py"),
    }
    return [repo_artifact(REPO / rel) for rel in sorted(rels, key=lambda path: path.as_posix())]


def packet_json(source_count: int, repo_count: int) -> dict[str, Any]:
    return {
        "schema_id": "turingos.m5.p4.github_module_closure_packet.v1",
        "packet_kind": "M5.P4_M6_MODULE_CLOSURE_GITHUB_PACKET",
        "audit_surface": "github_only",
        "repository_url": "https://github.com/gretjia/turing",
        "target_branch": "hci/operator-console-v1-rebased",
        "packet_root": PACKET_REL.as_posix(),
        "targets": ["M6.G"],
        "status_ceiling": "ADDRESSED",
        "closure_certificate_schema_id": "turingos.closure_certificate.v1",
        "exact_commit_supplied_out_of_band": True,
        "copied_plan_artifact_count": source_count,
        "repo_native_artifact_count": repo_count,
        "primary_files": {
            "manifest": (PACKET_REL / "PACKET_MANIFEST.sha256").as_posix(),
            "source_map": (PACKET_REL / "SOURCE_MAP.json").as_posix(),
            "repo_artifacts": (PACKET_REL / "REPO_ARTIFACTS.json").as_posix(),
            "prompt_template": (PACKET_REL / "AUDITOR_PROMPT_TEMPLATE.md").as_posix(),
        },
        "gate_verdicts": {
            "M6.G": (
                PLAN_COPY_ROOT / "evidence/session_20260702/M6G_GATE_VERDICT.json"
            ).as_posix()
        },
        "m5_p4_handoff_packet": (
            PLAN_COPY_ROOT / "evidence/session_20260702/M6G_M5_P4_HANDOFF_PACKET.json"
        ).as_posix(),
        "packet_local_checks": {
            "M6.G": (PACKET_REL / "packet_checks/run_m6_g_rollup_check.sh").as_posix()
        },
        "auditor_must_not_use": [
            "implementation chat",
            "local plan directory",
            "agent memory summaries",
            "uncommitted local files",
        ],
        "non_claims": [
            "This packet does not itself confer external verification.",
            "This packet does not authorize HCI-B or write-capable console behavior.",
            "This packet does not claim SHIPPED, RELEASED, RATIFIED, M2 enablement, release eligibility, FCE.RUN, OG-10/genesis signature, or constitution-byte change.",
            "Auditor verdict may be PASS or FAIL; FAIL requires repair and resubmission with a new packet.",
        ],
    }


def prompt_text() -> str:
    return f"""# M5.P4 M6.G Module Closure Audit Prompt Template

You are the custody-separated external auditor for the TuringOS M5.P4 module closure job targeting M6.G.

Do not use implementation chat, local plan-directory files, agent memory summaries, or uncommitted local files. Use only the GitHub repository, branch, exact commit SHA supplied by the owner, and files committed under this packet.

## Repository

- Repository: `https://github.com/gretjia/turing`
- Branch: `hci/operator-console-v1-rebased`
- Exact commit: supplied by owner in the surrounding prompt
- Packet root: `{PACKET_REL.as_posix()}/`

## Audit Scope

- Target gate: `M6.G`
- Closure service: `M5.P4`
- Certificate schema: `ClosureCertificate.v1`
- Status ceiling before your audit: `ADDRESSED`
- M6.G is not externally verified by this packet. Only your custody-separated PASS certificate can certify the target as `EXTERNALLY_VERIFIED`.

## Required Checks

1. Fresh clone the repository and check out the exact commit supplied by the owner.
2. Run `cd {PACKET_REL.as_posix()} && sha256sum -c PACKET_MANIFEST.sha256`.
3. Run `bash {PACKET_REL.as_posix()}/packet_checks/run_m6_g_rollup_check.sh` from the repository root.
4. Independently verify every `SOURCE_MAP.json` entry points to an existing copied packet artifact with a matching sha256.
5. Independently verify every `REPO_ARTIFACTS.json` entry points to an existing repository file at the checked-out commit with a matching sha256.
6. Confirm `M6G_GATE_VERDICT.json` is `GateVerdict.v1`, `gate_id: M6.G`, `status: ADDRESSED`, `status_ceiling: ADDRESSED`, and `not_run_is_fail: true`.
7. Confirm the G7 predicates are true: HCI-A ADR accepted, displayed values replayable, zero head-moving paths static and dynamic, and branch committed/archived.
8. Confirm no packet artifact authorizes HCI-B, any write-capable console behavior, SHIPPED, RELEASED, RATIFIED, M2 enablement, release eligibility, FCE.RUN, OG-10/genesis signature, or constitution-byte change.

## Certificate Output

Return a single JSON object conforming to `turingos.closure_certificate.v1`.

Use:
- `subject.gate_id`: `M5.P4`
- `subject.module_targets`: [`M6.G`]
- `subject.repo_url`: `https://github.com/gretjia/turing`
- `subject.branch`: `hci/operator-console-v1-rebased`
- `subject.commit_sha`: the exact commit you checked out
- `subject.packet_root`: `{PACKET_REL.as_posix()}`
- `verifier.kind`: `external_human_operator` or `external_cross_family_model`
- all six custody booleans set according to what you actually did

If any required check fails, return `verdict: FAIL` with machine-readable reasons and missing or mismatched paths. Do not repair the packet in place.
"""


def check_script() -> str:
    return f"""#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
PACKET="$ROOT/{PACKET_REL.as_posix()}"

cd "$PACKET"
sha256sum -c PACKET_MANIFEST.sha256

cd "$ROOT"
python3 - <<'PY'
import hashlib
import json
from pathlib import Path

root = Path.cwd()
packet = root / "{PACKET_REL.as_posix()}"

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

for map_name in ["SOURCE_MAP.json", "REPO_ARTIFACTS.json"]:
    entries = json.loads((packet / map_name).read_text(encoding="utf-8"))
    if not entries:
        raise SystemExit(f"empty {{map_name}}")
    for entry in entries:
        path = root / entry["github_path"]
        if not path.exists():
            raise SystemExit(f"missing {{map_name}} entry: {{entry['github_path']}}")
        actual = sha256(path)
        if actual != entry["sha256"]:
            raise SystemExit(
                f"digest mismatch {{map_name}} {{entry['github_path']}}: {{actual}} != {{entry['sha256']}}"
            )

gate = json.loads(
    (packet / "plan_artifacts/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/evidence/session_20260702/M6G_GATE_VERDICT.json").read_text(
        encoding="utf-8"
    )
)
if gate.get("schema_id") != "GateVerdict.v1":
    raise SystemExit("bad gate verdict schema")
if gate.get("gate_id") != "M6.G":
    raise SystemExit("bad gate id")
if gate.get("status") != "ADDRESSED" or gate.get("status_ceiling") != "ADDRESSED":
    raise SystemExit("bad M6.G status ceiling")
if gate.get("not_run_is_fail") is not True:
    raise SystemExit("M6.G not_run_is_fail must be true")

kpi = gate.get("g7_kpi") or {{}}
required = [
    "hci_a_adr_accepted",
    "displayed_values_replayable",
    "zero_head_moving_paths_static_and_dynamic",
    "branch_committed_or_archived",
]
missing = [key for key in required if kpi.get(key) is not True]
if missing:
    raise SystemExit(f"G7 KPI not satisfied: {{missing}}")

checklist = gate.get("checklist_results") or []
if len(checklist) != 7 or any(item.get("verdict") != "PASS" for item in checklist):
    raise SystemExit("M6.G drift checklist is not 7/7 PASS")

packet_json = json.loads((packet / "PACKET.json").read_text(encoding="utf-8"))
if packet_json.get("targets") != ["M6.G"]:
    raise SystemExit("packet targets must be ['M6.G']")
if packet_json.get("status_ceiling") != "ADDRESSED":
    raise SystemExit("packet status ceiling must be ADDRESSED")

non_claim_text = " ".join(packet_json.get("non_claims", []) + gate.get("non_claims", []))
for required_non_claim in [
    "HCI-B",
    "write-capable console behavior",
    "SHIPPED",
    "RELEASED",
    "RATIFIED",
    "M2 enablement",
    "release eligibility",
    "FCE.RUN",
    "OG-10/genesis signature",
    "constitution-byte change",
]:
    if required_non_claim not in non_claim_text:
        raise SystemExit(f"missing required non-claim: {{required_non_claim}}")

print("M6_G_PACKET_LOCAL_CHECK_PASS")
PY

bash tools/hci/run_hci_gates.sh --out-dir /tmp/turing-m6g-packet-hci-gates
"""


def write_manifest() -> None:
    rows: list[str] = []
    for path in sorted(PACKET_ROOT.rglob("*")):
        if not path.is_file() or path.name == "PACKET_MANIFEST.sha256":
            continue
        rel = path.relative_to(PACKET_ROOT).as_posix()
        rows.append(f"{sha256(path)}  {rel}")
    write_text(PACKET_ROOT / "PACKET_MANIFEST.sha256", "\n".join(rows) + "\n")


def build_packet() -> None:
    if PACKET_ROOT.exists():
        shutil.rmtree(PACKET_ROOT)
    source_map = collect_plan_artifacts()
    repo_artifacts = collect_repo_artifacts()
    write_json(PACKET_ROOT / "SOURCE_MAP.json", source_map)
    write_json(PACKET_ROOT / "REPO_ARTIFACTS.json", repo_artifacts)
    write_json(PACKET_ROOT / "PACKET.json", packet_json(len(source_map), len(repo_artifacts)))
    write_text(PACKET_ROOT / "AUDITOR_PROMPT_TEMPLATE.md", prompt_text())
    write_text(
        PACKET_ROOT / "packet_checks/run_m6_g_rollup_check.sh",
        check_script(),
        executable=True,
    )
    write_manifest()


def validate_packet() -> None:
    required = [
        PACKET_ROOT / "PACKET.json",
        PACKET_ROOT / "SOURCE_MAP.json",
        PACKET_ROOT / "REPO_ARTIFACTS.json",
        PACKET_ROOT / "AUDITOR_PROMPT_TEMPLATE.md",
        PACKET_ROOT / "PACKET_MANIFEST.sha256",
        PACKET_ROOT / "packet_checks/run_m6_g_rollup_check.sh",
    ]
    for path in required:
        if not path.exists():
            raise PacketError(f"missing packet file: {path}")
    for line in (PACKET_ROOT / "PACKET_MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
        digest, rel = line.split(maxsplit=1)
        path = PACKET_ROOT / rel
        if sha256(path) != digest:
            raise PacketError(f"manifest mismatch: {rel}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="validate existing packet without rebuilding")
    args = parser.parse_args()
    if args.check:
        validate_packet()
    else:
        build_packet()
        validate_packet()


if __name__ == "__main__":
    main()
