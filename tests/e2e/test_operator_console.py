import json
import subprocess


def run_turing(*args):
    return subprocess.run(
        ["cargo", "run", "-p", "turing-cli", "--quiet", "--", *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_operator_panoview_and_replay_journey():
    panoview = run_turing("panoview")
    assert panoview.returncode == 0, panoview.stderr
    assert "operator_view_snapshot.v1" in panoview.stdout
    assert "safe commands:" in panoview.stdout
    assert "APPROVE_CANDIDATE approval_required" in panoview.stdout
    assert "production ready" not in panoview.stdout

    replay = run_turing("replay", "--verify")
    assert replay.returncode == 0, replay.stderr
    assert "replay:" in replay.stdout


def test_operator_approval_boundary_journey():
    trace = run_turing("ask", "approve candidate")
    assert trace.returncode == 0, trace.stderr
    assert "operator_turn_trace.v1" in trace.stdout
    assert "approval_required=true" in trace.stdout
    assert "human_signature_required" in trace.stdout
    assert "dispatch_executed" not in trace.stdout


def test_operator_trace_json_shape_from_python_agent():
    output = subprocess.run(
        [
            "python3",
            "-c",
            (
                "import json; "
                "from turingos.operator_agent import OperatorAgent; "
                "print(json.dumps(OperatorAgent().route_turn('explain blocker'), sort_keys=True))"
            ),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={"PYTHONPATH": "src"},
        check=False,
    )
    assert output.returncode == 0, output.stderr
    trace = json.loads(output.stdout)
    assert trace["schema_id"] == "operator_turn_trace.v1"
    assert trace["selected_verb"] == "EXPLAIN_BLOCKER"
    assert trace["typed_command"]["writes_truth"] is False
