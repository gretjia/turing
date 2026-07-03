from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
WORK_ROOT = REPO.parent
PLAN_ROOT = WORK_ROOT / "PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702"
TOOLS = REPO / "tools" / "certification"
REQUIRED_SCENARIOS = [
    "FCE-R1",
    "FCE-S1",
    "FCE-S2",
    "FCE-S3",
    "FCE-S4",
    "FCE-S5",
    "FCE-S6",
    "FCE-W1",
    "FCE-W2",
    "FCE-W3",
    "FCE-B1",
    "FCE-B2",
    "FCE-B3",
    "FCE-B4",
    "FCE-B5",
    "FCE-R2",
    "FCE-R3",
    "FCE-R4",
    "FCE-R5",
]


def run_cmd(*argv: str, cwd: Path = REPO) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_fce_harness_files_exist_and_self_test() -> None:
    expected = [
        TOOLS / "run_final_certification.sh",
        TOOLS / "score_certification.py",
        TOOLS / "NORMALIZATION_SPEC.json",
        TOOLS / "checks" / "entry_criteria.py",
        TOOLS / "gen_fixture_tape.py",
        TOOLS / "gen_fixture_broadcast_rules.py",
        TOOLS / "workflow_scripts" / "w1.json",
        TOOLS / "workflow_scripts" / "w2.json",
        TOOLS / "workflow_scripts" / "w3.json",
    ]
    for path in expected:
        assert path.exists(), path

    proc = run_cmd("bash", str(TOOLS / "run_final_certification.sh"), "--self-test")
    assert proc.returncode == 0, proc.stdout
    assert "FCE_HARNESS_SELF_TEST_PASS" in proc.stdout

    score_proc = run_cmd("python3", str(TOOLS / "score_certification.py"), "--self-test")
    assert score_proc.returncode == 0, score_proc.stdout
    assert "FCE_SCORE_SELF_TEST_PASS" in score_proc.stdout


def test_fixture_generators_are_labeled_and_deterministic(tmp_path: Path) -> None:
    tape_a = tmp_path / "tape_a.jsonl"
    tape_b = tmp_path / "tape_b.jsonl"
    for out in (tape_a, tape_b):
        proc = run_cmd(
            "python3",
            str(TOOLS / "gen_fixture_tape.py"),
            "--count",
            "10000",
            "--out",
            str(out),
            "--seed",
            "fce-p0-test",
        )
        assert proc.returncode == 0, proc.stdout
    assert tape_a.read_bytes() == tape_b.read_bytes()
    rows = [json.loads(line) for line in tape_a.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 10000
    assert rows[0]["schema_id"] == "turingos.fce.fixture_event.v1"
    assert rows[0]["fixture_or_real"] == "FIXTURE"
    assert rows[-1]["event_index"] == 9999

    rules = tmp_path / "rules.json"
    rules_proc = run_cmd(
        "python3",
        str(TOOLS / "gen_fixture_broadcast_rules.py"),
        "--count",
        "50",
        "--max-active",
        "8",
        "--out",
        str(rules),
    )
    assert rules_proc.returncode == 0, rules_proc.stdout
    data = load_json(rules)
    assert data["schema_id"] == "turingos.fce.fixture_broadcast_rules.v1"
    assert data["fixture_or_real"] == "FIXTURE"
    assert len(data["rules"]) == 50
    assert len(data["active_rule_ids"]) == 8


def test_score_certification_accepts_clean_fixture_and_rejects_tamper(tmp_path: Path) -> None:
    root = tmp_path / "cert_root"
    first_evidence = None
    for scenario_id in REQUIRED_SCENARIOS:
        evidence = root / scenario_id / "evidence.json"
        write_json(evidence, {"schema_id": "fixture.evidence.v1", "ok": True, "scenario_id": scenario_id})
        first_evidence = first_evidence or evidence
        digest = subprocess.check_output(["sha256sum", str(evidence)], text=True).split()[0]
        rel = f"{scenario_id}/evidence.json"
        write_json(
            root / scenario_id / f"{scenario_id}_verdict.json",
            {
                "schema_id": "turingos.fce_scenario_verdict.v1",
                "scenario_id": scenario_id,
                "verdict": "PASS",
                "not_run_is_fail": True,
                "goals_served": ["G1"],
                "commands_executed": [{"cmd": "fixture", "exit_code": 0}],
                "pass_criteria_results": [
                    {"criterion": "fixture_gate", "result": True, "evidence": rel}
                ],
                "evidence": [rel],
                "evidence_sha256": {rel: "sha256:" + digest},
                "fixture_or_real": "FIXTURE",
                "automatic_fail_triggered": None,
                "wall_clock_ms": 0,
                "timestamp_utc": "2026-07-03T00:00:00Z",
            },
        )
    proc = run_cmd(
        "python3",
        str(TOOLS / "score_certification.py"),
        "--root",
        str(root),
        "--cert-repo-sha",
        "a" * 40,
        "--out",
        str(root / "FINAL_CERTIFICATION_VERDICT.json"),
    )
    assert proc.returncode == 0, proc.stdout
    verdict = load_json(root / "FINAL_CERTIFICATION_VERDICT.json")
    assert verdict["schema_id"] == "turingos.final_certification_verdict.v1"
    assert verdict["overall"] == "CERTIFICATION_ADDRESSED"
    assert verdict["shipped_eligible"] is False
    assert "external_audit_pass_on_certification_packet_missing" in verdict["shipped_blockers"]
    assert "SHIPPED" not in json.dumps(verdict)
    assert "RELEASED" not in json.dumps(verdict)

    assert first_evidence is not None
    first_evidence.write_text("tampered\n", encoding="utf-8")
    tamper_proc = run_cmd(
        "python3",
        str(TOOLS / "score_certification.py"),
        "--root",
        str(root),
        "--cert-repo-sha",
        "a" * 40,
        "--out",
        str(root / "tampered.json"),
    )
    assert tamper_proc.returncode != 0
    assert "evidence_digest_mismatch" in tamper_proc.stdout


def test_entry_criteria_blocks_current_incomplete_program(tmp_path: Path) -> None:
    out = tmp_path / "FCE_RUN_MANIFEST.json"
    proc = run_cmd(
        "python3",
        str(TOOLS / "checks" / "entry_criteria.py"),
        "--repo",
        str(REPO),
        "--plan-root",
        str(PLAN_ROOT),
        "--out",
        str(out),
        "--budget-ceiling-microusd",
        "50000000",
    )
    assert proc.returncode != 0
    manifest = load_json(out)
    assert manifest["schema_id"] == "turingos.fce_run_manifest.v1"
    assert manifest["entry_criteria_met"] is False
    assert manifest["scenarios_default_verdict"] == "NOT_RUN"
    assert any(item["id"] == "E1" and item["verdict"] == "FAIL" for item in manifest["entry_criteria"])
