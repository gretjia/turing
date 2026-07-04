#!/usr/bin/env python3
"""FCE-R2: replay determinism (same tape -> same verdicts, twice).

Per 09_FINAL_CERTIFICATION_EVALS.md section "FCE-R2 - Replay determinism": run the
complete verdict-producing audit chain TWICE (this scenario runs it THREE times) from
the same tape bundle in fresh scratch directories, and assert normalized byte-equality
of the reconstructed projection/HeadSet, plus stability of the tape bundle's own digest
across reads.

This scenario proves replay determinism at two independent, real (fixture_or_real=REAL)
layers, with zero LLM spend (replay determinism is a property of the tape/replay/console
plumbing, not of worker-uplift correctness, so no DeepSeek call is needed or made):

  Layer 1 - contracts/kernel/git-tape layer (the SG-19 ship gate,
  crates/turing-replay). A tiny new CLI wrapper,
  crates/turing-replay/examples/fce_r2_replay_probe.rs, mints the SAME fixed
  deterministic 5-event Tape crates/turing-replay/tests/replay_determinism.rs builds, via
  the ratified `turing-git-tape::Append` writer - a REAL native-SHA-256 Git commit chain,
  zero fixture JSON, zero mocks. The built Tape is copied into three independent fresh
  scratch directories; each copy is replayed by a SEPARATE OS-process invocation of the
  probe through the production `turing_replay::replay_tape` fold, and the raw canonical
  `turingos.jcs.v1` reconstruction bytes (projection + HeadSet) are captured to disk and
  sha256-compared byte-for-byte across all three (no in-process assert! is trusted - this
  FCE scenario computes its own independent digest). The existing ratified
  `cargo test -p turing-replay --test replay_determinism` (SG-19) is also re-run fresh as
  corroborating evidence (it independently asserts live-git-tape parity, ref-law
  correctness, and registry-sourced-not-envelope-trusted tamper resistance the probe alone
  does not check).

  Layer 2 - M6 console / operator-projection layer (`turing status --json`, the
  `operator_view_snapshot.v1` shadow-rebuild path this repo's own
  tools/hci/audit_projection_integrity.py audits in FCE-S1). The demo construction path
  (`turing_qualification::run_new_project_agent_economy_demo`, invoked via
  `turing status --json --demo`) builds a real Tape through the same ratified Append
  writer and real projection/economy/pput modules on every invocation - one internal
  event uses a scripted `FakeWorker` receipt (a deterministic stand-in for a live LLM
  call, disclosed here and in CLAIM_BOUNDARY.json; it is not claimed as worker-uplift
  evidence). Run as three independent OS-process invocations, each snapshot's
  `snapshot_hash` is checked for shadow-rebuild self-consistency (the same formula
  tools/hci/audit_projection_integrity.py's check_shadow_rebuild uses:
  sha256(JCS(snapshot minus its own snapshot_hash field)) == snapshot_hash), and the three
  snapshots are compared byte-for-byte after NORMALIZATION_SPEC.json stripping.

PASS (spec): normalized byte-equality for every tape's verdict pair (here: triple); the
tape bundles' own digests stable across both reads.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROUNDS = 3
PROBE_EXAMPLE = "fce_r2_replay_probe"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def run_command(
    *,
    name: str,
    argv: list[str],
    cwd: Path,
    out_dir: Path,
    env: dict[str, str] | None = None,
    timeout: int = 300,
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            env=env,
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
# Shared-spec normalization (tools/certification/NORMALIZATION_SPEC.json): the only
# byte-comparison rule FCE-R2 is allowed to use (spec: "verdict JSONs may legitimately
# differ ONLY in fields enumerated in NORMALIZATION_SPEC.json ... any other difference is
# nondeterminism and FAILs").
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
        return {key: normalize_value(item, volatile_keys) for key, item in value.items() if key not in volatile_keys}
    if isinstance(value, list):
        return [normalize_value(item, volatile_keys) for item in value]
    return value


def canonical_bytes(value: Any, volatile_keys: set[str]) -> bytes:
    normalized = normalize_value(value, volatile_keys)
    return (json.dumps(normalized, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


# --------------------------------------------------------------------------
# Whole-tree digest sweep: proves a tape bundle's own bytes are unchanged by a replay
# read (spec: "the tape bundles' own digests stable across both reads").
# --------------------------------------------------------------------------


def tree_manifest_sha256(tree_root: Path) -> str:
    lines = []
    for path in sorted(item for item in tree_root.rglob("*") if item.is_file()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(tree_root).as_posix()}")
    manifest = "\n".join(lines) + "\n"
    return "sha256:" + hashlib.sha256(manifest.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Layer 2 (console): the same shadow-rebuild formula
# tools/hci/audit_projection_integrity.py's check_shadow_rebuild uses, applied inline
# because the demo snapshot has no on-disk --micro-git path to hand that standalone
# auditor (its independent_heads/provenance_closure/render_fidelity checks need a real
# repo path; the demo path is exercised end-to-end for FCE-S1 instead, against real
# per-task Micro Tapes).
# --------------------------------------------------------------------------


def sha256_jcs(value: Any) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def shadow_rebuild_consistent(snapshot: dict[str, Any]) -> tuple[bool, str | None, str]:
    expected = snapshot.get("snapshot_hash")
    preimage = {key: value for key, value in snapshot.items() if key != "snapshot_hash"}
    actual = sha256_jcs(preimage)
    return (expected == actual, expected, actual)


# --------------------------------------------------------------------------
# Layer 1: build the fixed deterministic Tape once, replay it from 3 independent fresh
# scratch copies via 3 independent OS-process invocations of the new probe binary.
# --------------------------------------------------------------------------


def layer1_replay_probe(repo: Path, scenario_root: Path) -> dict[str, Any]:
    commands: list[dict[str, Any]] = []
    cmd_dir = scenario_root / "commands"

    build_probe = run_command(
        name="cargo_build_replay_probe",
        argv=["cargo", "build", "--example", PROBE_EXAMPLE, "-p", "turing-replay"],
        cwd=repo,
        out_dir=cmd_dir,
        timeout=600,
    )
    commands.append(build_probe)

    sg19_test = run_command(
        name="cargo_test_replay_determinism_sg19",
        argv=["cargo", "test", "-p", "turing-replay", "--test", "replay_determinism"],
        cwd=repo,
        out_dir=cmd_dir,
        timeout=600,
    )
    commands.append(sg19_test)

    probe_bin = repo / "target" / "debug" / "examples" / PROBE_EXAMPLE
    layer1_root = scenario_root / "layer1_contracts_replay"
    master = layer1_root / "tape_master"
    master.mkdir(parents=True, exist_ok=True)
    master_reconstruction = layer1_root / "master_reconstruction.json"

    build_master = run_command(
        name="replay_probe_build_master_tape",
        argv=[str(probe_bin), "--repo", str(master), "--build", "--out", str(master_reconstruction)],
        cwd=repo,
        out_dir=cmd_dir,
        timeout=120,
    )
    commands.append(build_master)

    # Real native-SHA-256 Git-tape structural check (the same ref shape
    # tools/hci/audit_projection_integrity.py's heads_from_micro_git reads).
    object_format = subprocess.run(
        ["git", "-C", str(master), "rev-parse", "--show-object-format"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    ).stdout.strip()
    tape_tip_ref = subprocess.run(
        ["git", "-C", str(master), "rev-parse", "--verify", "--quiet", "refs/turingos/tape_tip"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    accepted_head_ref = subprocess.run(
        ["git", "-C", str(master), "rev-parse", "--verify", "--quiet", "refs/turingos/accepted_head"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    master_tape_structure = {
        "schema_id": "turingos.fce.r2.master_tape_structure.v1",
        "object_format": object_format,
        "tape_tip_ref_present": tape_tip_ref.returncode == 0,
        "accepted_head_ref_present": accepted_head_ref.returncode == 0,
    }
    master_tape_structure_path = layer1_root / "master_tape_structure.json"
    write_json(master_tape_structure_path, master_tape_structure)

    master_digest_before = tree_manifest_sha256(master)

    rounds: list[dict[str, Any]] = []
    for index in range(1, ROUNDS + 1):
        round_dir = layer1_root / f"tape_round_{index}"
        if round_dir.exists():
            shutil.rmtree(round_dir)
        shutil.copytree(master, round_dir)
        digest_before_replay = tree_manifest_sha256(round_dir)

        reconstruction_path = layer1_root / f"round_{index}_reconstruction.json"
        replay_command = run_command(
            name=f"replay_probe_round_{index}",
            argv=[str(probe_bin), "--repo", str(round_dir), "--out", str(reconstruction_path)],
            cwd=repo,
            out_dir=cmd_dir,
            timeout=120,
        )
        commands.append(replay_command)
        digest_after_replay = tree_manifest_sha256(round_dir)

        rounds.append(
            {
                "index": index,
                "round_dir": round_dir,
                "reconstruction_path": reconstruction_path,
                "replay_command": replay_command,
                "digest_before_replay": digest_before_replay,
                "digest_after_replay": digest_after_replay,
                "digest_stable_across_read": digest_before_replay == digest_after_replay,
            }
        )

    master_digest_after = tree_manifest_sha256(master)

    return {
        "commands": commands,
        "build_probe": build_probe,
        "sg19_test": sg19_test,
        "build_master": build_master,
        "master": master,
        "master_reconstruction": master_reconstruction,
        "master_tape_structure": master_tape_structure,
        "master_tape_structure_path": master_tape_structure_path,
        "master_digest_before": master_digest_before,
        "master_digest_after": master_digest_after,
        "rounds": rounds,
    }


# --------------------------------------------------------------------------
# Layer 2: three independent `turing status --json --demo` invocations.
# --------------------------------------------------------------------------


def layer2_console_probe(repo: Path, scenario_root: Path) -> dict[str, Any]:
    commands: list[dict[str, Any]] = []
    cmd_dir = scenario_root / "commands"

    build_cli = run_command(
        name="cargo_build_turing_cli",
        argv=["cargo", "build", "-p", "turing-cli"],
        cwd=repo,
        out_dir=cmd_dir,
        timeout=600,
    )
    commands.append(build_cli)

    turing_bin = repo / "target" / "debug" / "turing"
    layer2_root = scenario_root / "layer2_console_replay"
    layer2_root.mkdir(parents=True, exist_ok=True)

    rounds: list[dict[str, Any]] = []
    for index in range(1, ROUNDS + 1):
        snapshot_path = layer2_root / f"console_round_{index}.json"
        status_command = run_command(
            name=f"console_status_json_demo_round_{index}",
            argv=[str(turing_bin), "status", "--json", "--demo"],
            cwd=repo,
            out_dir=cmd_dir,
            timeout=60,
        )
        commands.append(status_command)
        snapshot_path.write_text(status_command["stdout_text"], encoding="utf-8")
        snapshot: dict[str, Any] | None
        try:
            snapshot = load_json(snapshot_path)
        except (json.JSONDecodeError, OSError):
            snapshot = None
        consistent, expected_hash, actual_hash = (
            shadow_rebuild_consistent(snapshot) if isinstance(snapshot, dict) else (False, None, "")
        )
        rounds.append(
            {
                "index": index,
                "snapshot_path": snapshot_path,
                "status_command": status_command,
                "snapshot": snapshot,
                "shadow_rebuild_consistent": consistent,
                "expected_snapshot_hash": expected_hash,
                "recomputed_snapshot_hash": actual_hash,
            }
        )

    return {"commands": commands, "build_cli": build_cli, "turing_bin": turing_bin, "rounds": rounds}


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
    automatic_fail: str | None,
) -> dict[str, Any]:
    evidence_paths = sorted({rel(root, path) for path in evidence_files if path.is_file()})
    passed = all(item["result"] is True for item in criteria)
    return {
        "schema_id": "turingos.fce_scenario_verdict.v1",
        "scenario_id": scenario_id,
        "verdict": "PASS" if passed else "FAIL",
        "not_run_is_fail": True,
        "goals_served": ["G2"],
        "commands_executed": [{"cmd": command["cmd"], "exit_code": command["exit_code"]} for command in commands],
        "pass_criteria_results": criteria,
        "evidence": evidence_paths,
        "evidence_sha256": {item: sha256_file(root / item) for item in evidence_paths},
        "fixture_or_real": "REAL",
        "automatic_fail_triggered": automatic_fail,
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

    _, volatile_keys = load_normalization_spec(repo)

    commands: list[dict[str, Any]] = []
    evidence_files: list[Path] = []

    layer1 = layer1_replay_probe(repo, scenario_root)
    commands.extend(layer1["commands"])
    evidence_files.append(layer1["master_reconstruction"])
    evidence_files.append(layer1["master_tape_structure_path"])
    for round_info in layer1["rounds"]:
        evidence_files.append(round_info["reconstruction_path"])

    layer2 = layer2_console_probe(repo, scenario_root)
    commands.extend(layer2["commands"])
    for round_info in layer2["rounds"]:
        evidence_files.append(round_info["snapshot_path"])

    # ---- Layer 1 comparisons ----
    reconstruction_bytes = {"master": layer1["master_reconstruction"].read_bytes()}
    for round_info in layer1["rounds"]:
        reconstruction_bytes[f"round_{round_info['index']}"] = round_info["reconstruction_path"].read_bytes()
    reconstruction_normalized_sha256 = {
        label: sha256_bytes(canonical_bytes(json.loads(raw), volatile_keys))
        for label, raw in reconstruction_bytes.items()
    }
    reconstruction_all_identical = len(set(reconstruction_normalized_sha256.values())) == 1

    master_reconstruction_value = json.loads(reconstruction_bytes["master"])
    head_set = master_reconstruction_value.get("head_set", {})
    reconstruction_nontrivial = (
        isinstance(head_set.get("tape_tip"), str)
        and head_set.get("tape_tip", "").startswith("mu:")
        and isinstance(head_set.get("accepted_head"), str)
        and head_set.get("accepted_head", "").startswith("mu:")
        and master_reconstruction_value.get("event_count") == 5
        and len(master_reconstruction_value.get("accepted_event_ids", [])) == 2
    )

    layer1_commands_all_zero = all(item["exit_code"] == 0 for item in layer1["commands"])
    digest_stability = {
        "master_digest_stable": layer1["master_digest_before"] == layer1["master_digest_after"],
        "master_digest_before": layer1["master_digest_before"],
        "master_digest_after": layer1["master_digest_after"],
        "rounds": [
            {
                "index": item["index"],
                "digest_before_replay": item["digest_before_replay"],
                "digest_after_replay": item["digest_after_replay"],
                "digest_stable_across_read": item["digest_stable_across_read"],
            }
            for item in layer1["rounds"]
        ],
    }
    all_digests_stable = digest_stability["master_digest_stable"] and all(
        item["digest_stable_across_read"] for item in layer1["rounds"]
    )
    digest_stability_path = scenario_root / "layer1_contracts_replay" / "tape_digest_stability.json"
    write_json(digest_stability_path, digest_stability)
    evidence_files.append(digest_stability_path)

    layer1_summary_path = scenario_root / "layer1_contracts_replay" / "layer1_summary.json"
    write_json(
        layer1_summary_path,
        {
            "schema_id": "turingos.fce.r2.layer1_summary.v1",
            "reconstruction_normalized_sha256": reconstruction_normalized_sha256,
            "reconstruction_all_identical": reconstruction_all_identical,
            "reconstruction_nontrivial": reconstruction_nontrivial,
            "master_tape_structure": layer1["master_tape_structure"],
        },
    )
    evidence_files.append(layer1_summary_path)

    # ---- Layer 2 comparisons ----
    layer2_commands_all_zero = all(item["exit_code"] == 0 for item in layer2["commands"])
    console_shadow_rebuild_all_consistent = bool(layer2["rounds"]) and all(
        item["shadow_rebuild_consistent"] for item in layer2["rounds"]
    )
    console_normalized_sha256 = {
        f"round_{item['index']}": sha256_bytes(canonical_bytes(item["snapshot"], volatile_keys))
        for item in layer2["rounds"]
        if isinstance(item["snapshot"], dict)
    }
    console_all_identical = len(console_normalized_sha256) == ROUNDS and len(set(console_normalized_sha256.values())) == 1

    layer2_summary_path = scenario_root / "layer2_console_replay" / "layer2_summary.json"
    write_json(
        layer2_summary_path,
        {
            "schema_id": "turingos.fce.r2.layer2_summary.v1",
            "console_normalized_sha256": console_normalized_sha256,
            "console_all_identical": console_all_identical,
            "shadow_rebuild_results": [
                {
                    "index": item["index"],
                    "consistent": item["shadow_rebuild_consistent"],
                    "expected_snapshot_hash": item["expected_snapshot_hash"],
                    "recomputed_snapshot_hash": item["recomputed_snapshot_hash"],
                }
                for item in layer2["rounds"]
            ],
        },
    )
    evidence_files.append(layer2_summary_path)

    criteria = [
        {
            "criterion": "cargo_build_replay_probe_exit_zero",
            "result": layer1["build_probe"]["exit_code"] == 0,
            "evidence": rel(root, layer1_summary_path),
        },
        {
            "criterion": "sg19_rust_crate_replay_determinism_test_pass",
            "result": layer1["sg19_test"]["exit_code"] == 0,
            "evidence": rel(root, layer1_summary_path),
        },
        {
            "criterion": "master_tape_is_real_sha256_git_tape_with_heads",
            "result": (
                layer1["master_tape_structure"]["object_format"] == "sha256"
                and layer1["master_tape_structure"]["tape_tip_ref_present"] is True
                and layer1["master_tape_structure"]["accepted_head_ref_present"] is True
            ),
            "evidence": rel(root, layer1["master_tape_structure_path"]),
        },
        {
            "criterion": "layer1_all_commands_exit_zero",
            "result": layer1_commands_all_zero,
            "evidence": rel(root, layer1_summary_path),
        },
        {
            "criterion": "layer1_reconstruction_byte_identical_across_master_and_all_rounds",
            "result": reconstruction_all_identical,
            "evidence": rel(root, layer1_summary_path),
        },
        {
            "criterion": "layer1_reconstruction_nontrivial_and_head_set_populated",
            "result": reconstruction_nontrivial,
            "evidence": rel(root, layer1_summary_path),
        },
        {
            "criterion": "tape_bundle_digest_stable_across_reads",
            "result": all_digests_stable,
            "evidence": rel(root, digest_stability_path),
        },
        {
            "criterion": "layer2_all_commands_exit_zero",
            "result": layer2_commands_all_zero,
            "evidence": rel(root, layer2_summary_path),
        },
        {
            "criterion": "console_snapshot_hash_shadow_rebuild_consistent_all_rounds",
            "result": console_shadow_rebuild_all_consistent,
            "evidence": rel(root, layer2_summary_path),
        },
        {
            "criterion": "console_projection_byte_identical_across_all_rounds",
            "result": console_all_identical,
            "evidence": rel(root, layer2_summary_path),
        },
    ]

    readme = scenario_root / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# FCE-R2 Replay Determinism",
                "",
                "Evidence label: REAL.",
                "",
                "Layer 1 (contracts/kernel/git-tape, SG-19): a fixed 5-event Tape is minted once via",
                "the ratified `turing-git-tape::Append` writer (real native-SHA-256 Git commit chain,",
                "zero fixture JSON), copied into 3 independent fresh scratch directories, and replayed",
                "by 3 separate OS-process invocations of `crates/turing-replay/examples/",
                "fce_r2_replay_probe.rs` through the production `turing_replay::replay_tape` fold. The",
                "canonical reconstruction bytes (projection + HeadSet) are sha256-compared across all",
                "3 independently, and the existing ratified SG-19 cargo test is re-run fresh as",
                "corroborating evidence.",
                "",
                "Layer 2 (M6 console / operator projection): `turing status --json --demo` is run as 3",
                "independent OS-process invocations. Each real `operator_view_snapshot.v1` snapshot's",
                "`snapshot_hash` is checked for shadow-rebuild self-consistency (the same formula",
                "tools/hci/audit_projection_integrity.py's check_shadow_rebuild uses), and the 3",
                "snapshots are compared byte-for-byte after NORMALIZATION_SPEC.json stripping. The demo",
                "construction path uses one internal scripted FakeWorker receipt (disclosed here and in",
                "CLAIM_BOUNDARY.json) - it is not claimed as worker-uplift evidence, only as a real,",
                "deterministic exercise of the real Append/projection/economy substrate code.",
                "",
                "No DeepSeek API call was made or needed: replay determinism is a property of the",
                "tape/replay/console plumbing, not of worker-uplift correctness.",
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
            "claims": [
                "FCE-R2 replay-determinism certification: a real native-SHA-256 Micro Tape, minted"
                " via the ratified Append writer, replays byte-identical (projection + HeadSet) across"
                " 3 independent fresh-scratch-directory process invocations, corroborated by the"
                " existing ratified SG-19 cargo test",
                "the M6 console operator_view_snapshot.v1 shadow-rebuild path (turing status --json)"
                " replays byte-identical (including snapshot_hash shadow-rebuild self-consistency)"
                " across 3 independent process invocations",
            ],
            "non_claims": [
                "no worker-uplift or solve-rate claim of any kind",
                "the console layer's demo construction path uses one internal scripted FakeWorker"
                " receipt, not a live LLM call - not claimed as worker evidence",
                "not a release decision",
                "not SHIPPED",
                "not an external audit",
            ],
        },
    )
    evidence_files.extend([readme, claim_boundary])

    automatic_fail = None if all_digests_stable else "evidence_tampering"

    verdict = build_verdict(
        root=root,
        scenario_id=scenario_id,
        started=started,
        commands=commands,
        criteria=criteria,
        evidence_files=evidence_files,
        automatic_fail=automatic_fail,
    )
    write_json(scenario_root / f"{scenario_id}_verdict.json", verdict)
    print(json.dumps({"scenario_id": scenario_id, "verdict": verdict["verdict"]}, sort_keys=True))
    return 0 if verdict["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
