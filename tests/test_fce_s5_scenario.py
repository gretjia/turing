"""Tests for tools/certification/scenarios/FCE-S5.py (console no-write scenario).

FCE-S5 makes ONE real DeepSeek API call when actually executed (same minimal
`--limit 1` spend pattern as FCE-S4) - it is a certification scenario, not
something to spend real money on every `pytest` run. Following the
established convention in this repo (tests/test_fce_s1_scenario.py,
tests/test_fce_s4_scenario.py): load the module directly via importlib and
unit-test its pure/deterministic helper functions with synthetic data (no
network, no `turing` binary needed for most of these), and exercise the
"no credentials" gating path via monkeypatch - the gating is a runtime
behavior of the script itself (exit code 2, verdict NOT_RUN), not a pytest
marker/skip.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
SCENARIO_PATH = REPO / "tools" / "certification" / "scenarios" / "FCE-S5.py"


def load_module():
    spec = importlib.util.spec_from_file_location("fce_s5_scenario", SCENARIO_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def init_sha256_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "-C", str(path), "init", "--object-format=sha256", "-q", "--", "."],
        check=True,
    )


def write_ref(repo: Path, ref: str, value: str) -> None:
    subprocess.run(["git", "-C", str(repo), "update-ref", ref, value], check=True)


def commit_blob(repo: Path, content: bytes) -> str:
    """Create a real commit object (not just a blob) so `git rev-list`/
    `git rev-parse --verify` treat it as a valid ref target, mirroring how
    the real Append writer commits each tape event."""
    blob_oid = subprocess.run(
        ["git", "-C", str(repo), "hash-object", "-w", "--stdin"],
        input=content,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout.decode().strip()
    tree_spec = f"100644 blob {blob_oid}\tevent\n"
    tree_oid = subprocess.run(
        ["git", "-C", str(repo), "mktree"],
        input=tree_spec,
        stdout=subprocess.PIPE,
        text=True,
        check=True,
    ).stdout.strip()
    commit_oid = subprocess.run(
        ["git", "-C", str(repo), "commit-tree", tree_oid, "-m", "fixture event"],
        stdout=subprocess.PIPE,
        text=True,
        check=True,
    ).stdout.strip()
    return commit_oid


# --------------------------------------------------------------------------
# Reproducibility: DEEPSEEK_API_KEY loading (environment vs secrets.env)
# --------------------------------------------------------------------------


def test_load_deepseek_api_key_prefers_environment(monkeypatch):
    scenario = load_module()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "env-value")

    key, source = scenario.load_deepseek_api_key()

    assert key == "env-value"
    assert source == "environment"


def test_load_deepseek_api_key_falls_back_to_secrets_env_file(monkeypatch, tmp_path):
    scenario = load_module()
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    secrets_path = tmp_path / "secrets.env"
    secrets_path.write_text("SOME_OTHER_KEY=x\nDEEPSEEK_API_KEY=file-value\n", encoding="utf-8")
    monkeypatch.setattr(scenario, "SECRETS_ENV_PATH", secrets_path)

    key, source = scenario.load_deepseek_api_key()

    assert key == "file-value"
    assert source == str(secrets_path)


def test_load_deepseek_api_key_handles_quoted_values(monkeypatch, tmp_path):
    scenario = load_module()
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    secrets_path = tmp_path / "secrets.env"
    secrets_path.write_text('DEEPSEEK_API_KEY="quoted-value"\n', encoding="utf-8")
    monkeypatch.setattr(scenario, "SECRETS_ENV_PATH", secrets_path)

    key, _source = scenario.load_deepseek_api_key()

    assert key == "quoted-value"


def test_load_deepseek_api_key_returns_none_when_absent_everywhere(monkeypatch, tmp_path):
    scenario = load_module()
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(scenario, "SECRETS_ENV_PATH", tmp_path / "does_not_exist.env")

    key, source = scenario.load_deepseek_api_key()

    assert key is None
    assert "not found" in source


# --------------------------------------------------------------------------
# select_single_task (same rule as FCE-S4, pinned against the real committed
# S02 shard manifest)
# --------------------------------------------------------------------------


def test_select_single_task_is_deterministic_and_excludes_the_pilot_window(tmp_path):
    scenario = load_module()

    selection = scenario.select_single_task(REPO, tmp_path)

    assert selection["schema_id"] == "turingos.fce.s5.task_selection.v1"
    assert selection["shard_id"] == "S02"
    assert selection["pilot_window_id"] == "S02-W00"
    assert selection["instance_in_pilot_window"] is False
    assert selection["instance_id"] == "django__django-11133"
    assert selection["window_id"] == "S02-W01"

    manifest_path = tmp_path / "task_selection.json"
    assert manifest_path.is_file()
    written = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert written["instance_id"] == selection["instance_id"]

    second = scenario.select_single_task(REPO, tmp_path)
    assert second["instance_id"] == selection["instance_id"]


# --------------------------------------------------------------------------
# read_heads / tree_manifest_sha256 / sample_event_id: exercised against a
# real (tiny) sha256 git repo, mirroring
# crates/turing-cli/tests/cli_gates.rs::sample_micro_repo but built directly
# with git plumbing here (no cargo build needed for these pure-helper tests).
# --------------------------------------------------------------------------


def test_read_heads_reads_real_refs_and_reports_missing_ones_as_none(tmp_path):
    scenario = load_module()
    repo = tmp_path / "repo"
    init_sha256_repo(repo)

    oid = commit_blob(repo, b'{"hello":"world"}')
    write_ref(repo, "refs/turingos/tape_tip", oid)
    write_ref(repo, "refs/turingos/accepted_head", oid)
    # authorization_head deliberately left absent.

    heads = scenario.read_heads(repo)

    assert heads["refs/turingos/tape_tip"] == oid
    assert heads["refs/turingos/accepted_head"] == oid
    assert heads["refs/turingos/authorization_head"] is None


def test_read_heads_before_and_after_a_pure_read_command_is_byte_identical(tmp_path):
    scenario = load_module()
    repo = tmp_path / "repo"
    init_sha256_repo(repo)
    oid = commit_blob(repo, b'{"a":1}')
    write_ref(repo, "refs/turingos/tape_tip", oid)
    write_ref(repo, "refs/turingos/accepted_head", oid)

    before = scenario.read_heads(repo)
    # A pure read: must never move a ref.
    subprocess.run(["git", "-C", str(repo), "cat-file", "-p", oid], check=True, capture_output=True)
    after = scenario.read_heads(repo)

    assert before == after


def test_tree_manifest_sha256_changes_when_a_file_is_added_and_is_deterministic(tmp_path):
    scenario = load_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.txt").write_text("hello", encoding="utf-8")

    digest1 = scenario.tree_manifest_sha256(repo)
    digest2 = scenario.tree_manifest_sha256(repo)
    assert digest1 == digest2
    assert digest1.startswith("sha256:")

    (repo / "b.txt").write_text("world", encoding="utf-8")
    digest3 = scenario.tree_manifest_sha256(repo)
    assert digest3 != digest1


def test_sample_event_id_returns_mu_prefixed_tape_tip_oid(tmp_path):
    scenario = load_module()
    repo = tmp_path / "repo"
    init_sha256_repo(repo)
    oid = commit_blob(repo, b'{"event_type":"Genesis"}')
    write_ref(repo, "refs/turingos/tape_tip", oid)

    event_id = scenario.sample_event_id(repo)

    assert event_id == f"mu:{oid}"


def test_sample_event_id_returns_none_when_tape_tip_absent(tmp_path):
    scenario = load_module()
    repo = tmp_path / "repo"
    init_sha256_repo(repo)

    assert scenario.sample_event_id(repo) is None


# --------------------------------------------------------------------------
# chmod_recursive: the read-only-filesystem-matrix mechanism.
# --------------------------------------------------------------------------


def test_chmod_recursive_strips_and_restores_write_bits(tmp_path):
    scenario = load_module()
    root = tmp_path / "tree"
    (root / "sub").mkdir(parents=True)
    (root / "sub" / "file.txt").write_text("data", encoding="utf-8")

    scenario.chmod_recursive(root, writable=False)
    mode = (root / "sub" / "file.txt").stat().st_mode
    assert not (mode & 0o222), "write bits should be stripped"

    # A write attempt against the read-only tree must fail.
    with pytest.raises(PermissionError):
        (root / "sub" / "file.txt").write_text("changed", encoding="utf-8")

    scenario.chmod_recursive(root, writable=True)
    mode = (root / "sub" / "file.txt").stat().st_mode
    assert mode & 0o200, "owner write bit should be restored"
    # Now a write succeeds again.
    (root / "sub" / "file.txt").write_text("changed", encoding="utf-8")
    assert (root / "sub" / "file.txt").read_text(encoding="utf-8") == "changed"


# --------------------------------------------------------------------------
# build_console_command_matrix / run_console_matrix / parse_help_commands_write_flags
# --------------------------------------------------------------------------


def test_build_console_command_matrix_covers_the_full_spec_surface():
    scenario = load_module()

    matrix = scenario.build_console_command_matrix("/tmp/repo", "/tmp/bundle", "mu:" + "a" * 64)
    labels = {case["label"] for case in matrix}

    for expected_label in [
        "help",
        "help commands",
        "status micro-git",
        "status micro-git json",
        "panoview micro-git",
        "panoview micro-git json",
        "explain blocker micro-git",
        "status micro-bundle",
        "panoview micro-bundle",
        "approval preview",
        "operator stdin script",
        "ask view status",
        "ask approve candidate",
        "ask dispatch worker",
    ]:
        assert expected_label in labels, f"missing case: {expected_label}"

    approval_case = next(case for case in matrix if case["label"] == "approval preview")
    assert "writes_micro_truth=false" in approval_case["expect"]

    operator_case = next(case for case in matrix if case["label"] == "operator stdin script")
    assert operator_case["stdin"].startswith("status\npanoview\n")


def test_build_console_command_matrix_without_event_id_still_covers_explain_event():
    scenario = load_module()

    matrix = scenario.build_console_command_matrix("/tmp/repo", "/tmp/bundle", None)
    labels = {case["label"] for case in matrix}

    assert "explain event micro-git no-id" in labels
    assert "explain event micro-git real-id" not in labels


def test_parse_help_commands_write_flags_extracts_verb_to_writes_truth_mapping():
    scenario = load_module()

    text = (
        "Operator Console v1 topic=commands\n"
        "contract=operator_tool_manifest.v1 item_contract=typed_command.v1\n"
        "verb=VIEW_STATUS side_effect_class=none approval_required=false writes_truth=false confirmation_route=none source_heads=tape_tip expected_receipt=false\n"
        "verb=APPROVE_CANDIDATE side_effect_class=sovereign_mutation approval_required=true writes_truth=false confirmation_route=human source_heads=tape_tip expected_receipt=true\n"
        "status_ceiling=IMPLEMENTER_ADDRESSED\n"
    )

    flags = scenario.parse_help_commands_write_flags(text)

    assert flags == {"VIEW_STATUS": "false", "APPROVE_CANDIDATE": "false"}


def test_run_console_matrix_detects_write_claims_and_permission_errors(tmp_path):
    scenario = load_module()

    # A fake "turing" binary (a tiny shell script) standing in for the real
    # Rust binary, so this pure-logic test needs no cargo build. It echoes
    # back its argv so we can assert on argv plumbing, and one invocation
    # deliberately emits a write-claim / permission-error marker to prove
    # run_console_matrix's detection regexes actually fire.
    fake_bin = tmp_path / "turing"
    fake_bin.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "bad" ]; then\n'
        '  echo "writes_truth=true permission denied" \n'
        "  exit 1\n"
        "fi\n"
        'echo "ok $@"\n',
        encoding="utf-8",
    )
    fake_bin.chmod(0o755)

    matrix = [
        {"label": "good", "argv": ["status", "--json"], "expect": ["ok"]},
        {"label": "bad", "argv": ["bad"], "expect": []},
    ]
    out_dir = tmp_path / "out"

    results = scenario.run_console_matrix(fake_bin, matrix, out_dir, "test")

    good = next(r for r in results if r["label"] == "good")
    bad = next(r for r in results if r["label"] == "bad")

    assert good["command"]["exit_code"] == 0
    assert good["all_expected_present"] is True
    assert good["claims_write_authority"] is False
    assert good["permission_error_present"] is False

    assert bad["command"]["exit_code"] == 1
    assert bad["claims_write_authority"] is True
    assert bad["permission_error_present"] is True


# --------------------------------------------------------------------------
# build_verdict
# --------------------------------------------------------------------------


def test_build_verdict_pass_requires_every_criterion_true(tmp_path):
    scenario = load_module()

    scenario_root = tmp_path / "FCE-S5"
    scenario_root.mkdir()
    evidence_file = scenario_root / "evidence.json"
    evidence_file.write_text(json.dumps({"ok": True}), encoding="utf-8")

    verdict = scenario.build_verdict(
        root=tmp_path,
        scenario_id="FCE-S5",
        started=0.0,
        commands=[{"cmd": "true", "exit_code": 0}],
        criteria=[{"criterion": "fixture_criterion", "result": True, "evidence": "FCE-S5/evidence.json"}],
        evidence_files=[evidence_file],
        automatic_fail=None,
    )

    assert verdict["schema_id"] == "turingos.fce_scenario_verdict.v1"
    assert verdict["scenario_id"] == "FCE-S5"
    assert verdict["verdict"] == "PASS"
    assert verdict["goals_served"] == ["G7"]
    assert verdict["fixture_or_real"] == "REAL"
    assert verdict["not_run_is_fail"] is True
    assert "FCE-S5/evidence.json" in verdict["evidence"]
    assert verdict["evidence_sha256"]["FCE-S5/evidence.json"] == scenario.sha256_file(evidence_file)


def test_build_verdict_fail_when_any_criterion_false(tmp_path):
    scenario = load_module()

    scenario_root = tmp_path / "FCE-S5"
    scenario_root.mkdir()
    evidence_file = scenario_root / "evidence.json"
    evidence_file.write_text("{}", encoding="utf-8")

    verdict = scenario.build_verdict(
        root=tmp_path,
        scenario_id="FCE-S5",
        started=0.0,
        commands=[],
        criteria=[
            {"criterion": "one", "result": True, "evidence": "FCE-S5/evidence.json"},
            {"criterion": "two", "result": False, "evidence": "FCE-S5/evidence.json"},
        ],
        evidence_files=[evidence_file],
        automatic_fail="head_movement_by_console",
    )

    assert verdict["verdict"] == "FAIL"
    assert verdict["automatic_fail_triggered"] == "head_movement_by_console"


def test_resolve_daemon_bin_dir_prefers_repo_local_build(tmp_path):
    scenario = load_module()

    fake_repo = tmp_path / "repo"
    bin_dir = fake_repo / "target" / "debug"
    bin_dir.mkdir(parents=True)
    for name in scenario.REQUIRED_DAEMON_BINARIES:
        binary = bin_dir / name
        binary.write_text("#!/bin/sh\n", encoding="utf-8")
        binary.chmod(0o755)

    scenario_root = tmp_path / "FCE-S5"
    scenario_root.mkdir()

    result = scenario.resolve_daemon_bin_dir(fake_repo, scenario_root)

    assert result["source"] == "repo_local_build"
    assert result["bin_dir"] == str(bin_dir)
    assert (scenario_root / "daemon_bin_dir_resolution.json").is_file()


def test_main_without_deepseek_api_key_is_not_run_and_makes_no_llm_call(tmp_path, monkeypatch):
    """Mirrors FCE-S1/FCE-S4's own no-credential gating convention: the
    runtime behavior of the script itself (exit code, verdict NOT_RUN) is
    what gates real spend, not a pytest marker. No network call and no
    daemon-binary resolution/build is attempted in this path (the key check
    happens before either), and the key-provenance evidence file records that
    both the environment and ~/.turingos/secrets.env (redirected here) were
    checked.
    """
    scenario = load_module()
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(scenario, "SECRETS_ENV_PATH", tmp_path / "no_such_secrets.env")

    root = tmp_path / "root"
    plan_root = REPO.parent / "PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702"
    argv = [
        "FCE-S5.py",
        "--root",
        str(root),
        "--repo",
        str(REPO),
        "--plan-root",
        str(plan_root),
        "--scenario-id",
        "FCE-S5",
    ]
    monkeypatch.setattr(sys, "argv", argv)

    exit_code = scenario.main()

    assert exit_code == 2
    verdict_path = root / "FCE-S5" / "FCE-S5_verdict.json"
    assert verdict_path.is_file()
    verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
    assert verdict["schema_id"] == "turingos.fce_scenario_verdict.v1"
    assert verdict["scenario_id"] == "FCE-S5"
    assert verdict["verdict"] == "NOT_RUN"
    assert "DEEPSEEK_API_KEY" in verdict["not_run_reason"]
    assert not (root / "FCE-S5" / "daemon_bin_dir_resolution.json").is_file()

    provenance = load_json(root / "FCE-S5" / "deepseek_api_key_provenance.json")
    assert provenance["present"] is False
