"""WP-L3-2 acceptance tests (ADR-ECON-007 Decision 5; design doc
`research/RES_ROUTE_lockIn_remedy_design_20260710.md` §2 L3.6):
`tools/econ_lab/dialectic/dialectic_gate.py`'s GRILL-ME route dialectic gate.

Fully offline (this WP's own red line: "mock LLM 全离线") -- every LLM call in this
file goes through `dialectic.llm_clients.MockLLMClient`, never real network I/O.

Claims required by this WP's own brief:
  1. Prompt templates render with every `<<TOKEN>>` filled, and an unfilled token is a
     structural error (never silently left in the text sent to a model).
  2. A `route_portfolio.v1` produced by a full proposer x2 -> critic -> judge pass
     carries >= 3 candidates, each matching the exact `{route_descriptor,
     predicted_failure_modes[], probe_design, exit_criteria, prior_estimate+
     provenance}` shape, and `proposal_only` is hard `True`.
  3. The B-zone leak scan (reusing `monitor.termination.assert_report_has_no_bzone_
     leak`, read-only import) actually catches both a literal blacklisted vocabulary
     word and a forbidden field name, and lets legal text/structure through -- tested
     directly, not just indirectly through a passing pipeline run.
  4. The static prompt template FILES on disk (this WP's own brief: "角色提示模板存
     dialectic/prompts/...同过 B 区扫描") pass the same scan.
  5. A judge that synthesizes fewer than 3 candidates is a structural error (BLOCKED),
     never silently padded to 3.
  6. Re-entry: consuming a real `RouteFalsificationReport` (built via
     `monitor.termination.build_route_falsification_report`, not a hand-rolled
     fixture) folds its evidence into every role's prompt and the resulting
     portfolio's own `reentry.upstream_remaining_candidates` -- closing the honest
     gap a prior WP named ("remaining_candidates always [] in falsification
     reports").
  7. The two forced-heterogeneous proposers actually receive DIFFERENT perspective
     text in their own system prompts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ECON_LAB = REPO / "tools" / "econ_lab"
DIALECTIC = ECON_LAB / "dialectic"

sys.path.insert(0, str(ECON_LAB))

import dialectic.dialectic_gate as dg  # noqa: E402
import monitor.termination as termination  # noqa: E402
from dialectic.llm_clients import MockLLMClient  # noqa: E402


# ---------------------------------------------------------------------------
# Shared fixture helpers.
# ---------------------------------------------------------------------------


def _proposal_json(label: str, p: str, summary: str = "a summary") -> str:
    return json.dumps(
        {
            "route_descriptor": {"label": label, "summary": summary, "key_choices": ["choice a", "choice b"]},
            "predicted_failure_modes": ["mode one", "mode two"],
            "probe_design": f"run a small spike on {label}",
            "exit_criteria": "abandon if the spike fails twice",
            "prior_estimate": {"p": p, "provenance": "based on prior experience"},
        }
    )


def _critique_json(labels: list[str]) -> str:
    return json.dumps(
        {
            "critiques": [
                {
                    "route_label": label,
                    "additional_failure_modes": ["an additional mode"],
                    "predicted_failure_modes_adequate": "true",
                    "probe_design_critique": "reasonable",
                    "exit_criteria_critique": "reasonable",
                }
                for label in labels
            ]
        }
    )


def _happy_client(*, extra_judge_candidate: bool = True) -> MockLLMClient:
    judge_candidates = [
        json.loads(_proposal_json("route-a", "0.4")),
        json.loads(_proposal_json("route-b", "0.5")),
    ]
    if extra_judge_candidate:
        judge_candidates.append(json.loads(_proposal_json("route-c-hybrid", "0.3")))
    return MockLLMClient(
        responses={
            "proposer_1": _proposal_json("route-a", "0.4"),
            "proposer_2": _proposal_json("route-b", "0.5"),
            "critic": _critique_json(["route-a", "route-b"]),
            "judge": json.dumps(judge_candidates),
        }
    )


def _falsification_report() -> dict:
    return termination.build_route_falsification_report(
        route_id="fixture-instance::A::sonnet",
        attempts=[{"fact_class": "REMEDIATION_EXHAUSTED"}],
        verifier_evidence=[{"phase": "dispatch", "result": "fail"}],
        detector_events=[{"rule_id": "TERMINATION_WITHOUT_VERIFIER_EVIDENCE"}],
        remaining_candidates=["fixture-instance::B::sonnet", "fixture-instance::C::sonnet"],
        recommendation="Route repeatedly failed verification; recommend GRILL-ME review.",
    ).to_dict()


# ---------------------------------------------------------------------------
# 1. Prompt template rendering.
# ---------------------------------------------------------------------------


def test_render_prompt_fills_every_token():
    text = dg.render_prompt(
        "proposer_system.txt",
        PROPOSER_INDEX="1",
        PERSPECTIVE_SELF="perspective A",
        PERSPECTIVE_OTHER="perspective B",
    )
    assert "perspective A" in text
    assert "perspective B" in text
    assert "<<" not in text


def test_render_prompt_raises_on_unfilled_token():
    with pytest.raises(dg.DialecticGateError, match="unfilled template token"):
        dg.render_prompt("proposer_system.txt", PROPOSER_INDEX="1")  # missing two tokens


# ---------------------------------------------------------------------------
# 2. Full offline pipeline -> route_portfolio.v1 shape.
# ---------------------------------------------------------------------------


def test_full_pipeline_produces_legal_portfolio():
    client = _happy_client()
    result = dg.run_dialectic_gate(task_context="Fix a bug in the widget parser.", llm_client=client)

    portfolio = result.portfolio
    assert portfolio["schema"] == dg.ROUTE_PORTFOLIO_SCHEMA
    assert portfolio["proposal_only"] is True
    assert len(portfolio["candidates"]) >= dg.MIN_CANDIDATES
    for candidate in portfolio["candidates"]:
        assert set(candidate.keys()) == {
            "route_descriptor",
            "predicted_failure_modes",
            "probe_design",
            "exit_criteria",
            "prior_estimate",
        }
        assert isinstance(candidate["prior_estimate"]["p"], str)
        float(candidate["prior_estimate"]["p"])  # parseable
    # exactly the 4-call budget this WP's own brief names (2 proposers + critic + judge)
    assert len(client.calls) == 4


def test_full_pipeline_accepts_dict_task_context():
    client = _happy_client()
    result = dg.run_dialectic_gate(
        task_context={"task_id": "t1", "problem_statement": "fix the thing"}, llm_client=client
    )
    assert result.portfolio["proposal_only"] is True


# ---------------------------------------------------------------------------
# 3. B-zone leak scan, direct exercise (legal and illegal fixtures).
# ---------------------------------------------------------------------------


def test_scan_worker_text_catches_forbidden_vocabulary():
    with pytest.raises(dg.DialecticGateError, match="B-zone leak"):
        dg.scan_worker_text(label="t", text="we should raise the tau value more aggressively")


def test_scan_worker_text_catches_forbidden_vocabulary_threshold():
    with pytest.raises(dg.DialecticGateError, match="B-zone leak"):
        dg.scan_worker_text(label="t", text="past that threshold the route should be abandoned")


def test_scan_worker_text_allows_legal_prose_with_ordinary_numbers():
    # must not raise -- ordinary structural counts are legal, only the named
    # B-zone vocabulary family is banned.
    dg.scan_worker_text(label="t", text="we should try three probe spikes before committing")


def test_scan_structure_catches_forbidden_field_name():
    with pytest.raises(dg.DialecticGateError, match="B-zone leak"):
        dg.scan_structure_for_bzone_leak(label="s", value={"domain_bucket": "x"})


def test_scan_structure_catches_bare_numeric_leaf():
    with pytest.raises(dg.DialecticGateError, match="B-zone leak"):
        dg.scan_structure_for_bzone_leak(label="s", value={"count": 3})


def test_scan_structure_allows_legal_structure():
    dg.scan_structure_for_bzone_leak(label="s", value={"note": "fine", "items": ["a", "b"]})


# ---------------------------------------------------------------------------
# 4. Static prompt template files themselves pass the same scan.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "filename",
    [
        "proposer_system.txt",
        "proposer_user.txt",
        "critic_system.txt",
        "critic_user.txt",
        "judge_system.txt",
        "judge_user.txt",
        "reentry_evidence_block.txt",
    ],
)
def test_prompt_template_files_pass_bzone_scan(filename):
    path = DIALECTIC / "prompts" / filename
    assert path.exists(), f"missing prompt template: {path}"
    text = path.read_text(encoding="utf-8")
    # Strip the `<<TOKEN>>` placeholders themselves before scanning (they are not
    # yet worker-visible content -- the RENDERED prompt, scanned in
    # `render_prompt` above and in the full-pipeline test, is the actual
    # worker-visible surface; this test additionally covers the template's own
    # static prose, which is what this WP's own brief names directly: "角色提示
    # 模板存 dialectic/prompts/...同过 B 区扫描").
    dg.scan_worker_text(label=f"template:{filename}", text=text)


# ---------------------------------------------------------------------------
# 5. Judge under-delivering candidates is a structural error, never padded.
# ---------------------------------------------------------------------------


def test_judge_fewer_than_three_candidates_is_blocked():
    client = _happy_client(extra_judge_candidate=False)  # judge only returns 2
    with pytest.raises(dg.DialecticGateError, match="requires >="):
        dg.run_dialectic_gate(task_context="Fix a bug.", llm_client=client)


def test_malformed_json_from_a_role_is_blocked():
    # Persistently malformed on every attempt -- exhausts the shared retry budget
    # (see `test_proposer_malformed_json_is_retried_once_and_recovers` below for the
    # transient-glitch-that-recovers case) and still fails loud in the end.
    client = MockLLMClient(
        responses={
            "proposer_1": "not json at all",
            "proposer_2": _proposal_json("route-b", "0.5"),
            "critic": _critique_json(["route-a", "route-b"]),
            "judge": json.dumps([json.loads(_proposal_json(l, "0.4")) for l in ("a", "b", "c")]),
        }
    )
    with pytest.raises(dg.DialecticGateError, match="not valid JSON"):
        dg.run_dialectic_gate(task_context="Fix a bug.", llm_client=client)


def test_proposer_malformed_json_is_retried_once_and_recovers():
    # A real model can emit a one-off malformed-JSON glitch (e.g. a stray missing
    # comma) -- the SAME shared retry budget that recovers a B-zone-vocabulary
    # collision also recovers this failure class, since both are just "this
    # completion cannot be used as-is" from `_complete_with_role_retry`'s own point
    # of view.
    call_counts = {"proposer_1": 0}

    def flaky_proposer_1() -> str:
        call_counts["proposer_1"] += 1
        if call_counts["proposer_1"] == 1:
            return "{not valid json"
        return _proposal_json("route-a", "0.4")

    client = MockLLMClient(
        responses={
            "proposer_1": flaky_proposer_1,
            "proposer_2": _proposal_json("route-b", "0.5"),
            "critic": _critique_json(["route-a", "route-b"]),
            "judge": json.dumps([json.loads(_proposal_json(l, "0.4")) for l in ("route-a", "route-b", "route-c-hybrid")]),
        }
    )

    result = dg.run_dialectic_gate(task_context="Fix a bug.", llm_client=client)

    assert call_counts["proposer_1"] == 2
    assert len(result.portfolio["candidates"]) >= dg.MIN_CANDIDATES


# ---------------------------------------------------------------------------
# 6. Re-entry: consuming a real falsification report.
# ---------------------------------------------------------------------------


def test_reentry_folds_falsification_evidence_into_every_prompt():
    client = _happy_client()
    report = _falsification_report()

    result = dg.run_dialectic_gate(
        task_context="Fix a bug.", llm_client=client, falsification_report=report
    )

    assert result.portfolio["reentry"]["upstream_route_id"] == report["route_id"]
    assert result.portfolio["reentry"]["upstream_remaining_candidates"] == report["remaining_candidates"]
    assert result.portfolio["reentry"]["upstream_report_digest"] == report["digest"]

    # every role's own user prompt actually carried the re-entry evidence block
    for call in client.calls:
        assert "Upstream route-falsification evidence" in call["user"]
        assert report["route_id"] in call["user"]


def test_reentry_with_bzone_leaking_upstream_report_is_blocked():
    # a caller-supplied report that did NOT go through termination.py's own
    # construction-time check (defense in depth -- module docstring's own claim).
    illegal_report = {
        "route_id": "r1",
        "attempts": [],
        "verifier_evidence": [],
        "detector_events": [],
        "remaining_candidates": [],
        "recommendation": "abandon once past the tau threshold",
    }
    with pytest.raises(dg.DialecticGateError, match="B-zone leak"):
        dg.run_dialectic_gate(
            task_context="Fix a bug.", llm_client=_happy_client(), falsification_report=illegal_report
        )


# ---------------------------------------------------------------------------
# 7. Forced heterogeneity: the two proposers see different perspective text.
# ---------------------------------------------------------------------------


def test_proposers_receive_distinct_perspectives():
    assert dg.PERSPECTIVES[0] != dg.PERSPECTIVES[1]
    client = _happy_client()
    dg.run_dialectic_gate(task_context="Fix a bug.", llm_client=client)

    p1_system = next(c["system"] for c in client.calls if c["role"] == "proposer_1")
    p2_system = next(c["system"] for c in client.calls if c["role"] == "proposer_2")
    assert p1_system != p2_system
    assert dg.PERSPECTIVES[0] in p1_system
    assert dg.PERSPECTIVES[1] in p2_system


# ---------------------------------------------------------------------------
# 8. A real model's own ordinary-English word choice colliding with the B-zone
# blacklist (e.g. "threshold" used in its plain-English sense) is retried once,
# bounded, in-budget -- never crashes the whole run outright, and never a second
# silent retry.
# ---------------------------------------------------------------------------


def test_bzone_retry_notice_itself_passes_bzone_scan_and_names_no_token():
    # The corrective notice is itself worker-visible text (appended to a real
    # system prompt sent back to the model) -- it must clear the same scanner it is
    # trying to steer the model away from tripping, and it must name no specific
    # blacklisted token verbatim (that would itself be the leak this module exists
    # to stop -- same reasoning `test_prompt_template_files_pass_bzone_scan` applies
    # to the static prompt files).
    dg.scan_worker_text(label="bzone_retry_notice", text=dg._BZONE_RETRY_NOTICE)


def test_proposer_bzone_leak_is_retried_once_and_recovers():
    call_counts = {"proposer_1": 0}

    def flaky_proposer_1() -> str:
        call_counts["proposer_1"] += 1
        if call_counts["proposer_1"] == 1:
            # a real model's ordinary-English word choice, not a fabricated attack
            return _proposal_json("route-a", "0.4", summary="needs a clear failure threshold")
        return _proposal_json("route-a", "0.4", summary="needs a clear failure cutoff point")

    client = MockLLMClient(
        responses={
            "proposer_1": flaky_proposer_1,
            "proposer_2": _proposal_json("route-b", "0.5"),
            "critic": _critique_json(["route-a", "route-b"]),
            "judge": json.dumps(
                [
                    json.loads(_proposal_json(l, "0.4"))
                    for l in ("route-a", "route-b", "route-c-hybrid")
                ]
            ),
        }
    )

    result = dg.run_dialectic_gate(task_context="Fix a bug.", llm_client=client)

    assert call_counts["proposer_1"] == 2
    proposer_1_calls = [c for c in client.calls if c["role"] == "proposer_1"]
    assert len(proposer_1_calls) == 2
    assert dg._BZONE_RETRY_NOTICE in proposer_1_calls[1]["system"]
    assert dg._BZONE_RETRY_NOTICE not in proposer_1_calls[0]["system"]
    assert len(result.portfolio["candidates"]) >= dg.MIN_CANDIDATES
    # total real calls stayed within the WP's own <= 6 smoke-call budget: 2 proposers
    # (one retried once = 3 calls) + 1 critic + 1 judge = 5.
    assert len(client.calls) == 5


def test_bzone_leak_persisting_through_the_retry_still_fails_loud():
    # EVERY attempt uses the blacklisted word -- the whole run-wide retry budget is
    # spent on this one call site (1 initial + MAX_BZONE_RETRIES_PER_RUN retries),
    # and the LAST failure propagates uncaught: never a further silent retry once
    # the budget is exhausted.
    client = MockLLMClient(
        responses={
            "proposer_1": _proposal_json("route-a", "0.4", summary="needs a clear failure threshold"),
            "proposer_2": _proposal_json("route-b", "0.5"),
            "critic": _critique_json(["route-a", "route-b"]),
            "judge": json.dumps([json.loads(_proposal_json(l, "0.4")) for l in ("a", "b", "c")]),
        }
    )
    with pytest.raises(dg.DialecticGateError, match="B-zone leak"):
        dg.run_dialectic_gate(task_context="Fix a bug.", llm_client=client)

    proposer_1_calls = [c for c in client.calls if c["role"] == "proposer_1"]
    assert len(proposer_1_calls) == 1 + dg.MAX_BZONE_RETRIES_PER_RUN  # budget fully spent, then gives up


def test_bzone_retry_budget_is_shared_and_bounded_across_the_whole_run():
    # Two DIFFERENT roles each trip the scan once -- both are within the run-wide
    # MAX_BZONE_RETRIES_PER_RUN budget of 2, so both recover.
    call_counts = {"proposer_1": 0, "critic": 0}

    def flaky_proposer_1() -> str:
        call_counts["proposer_1"] += 1
        summary = "needs a clear failure threshold" if call_counts["proposer_1"] == 1 else "needs a clear cutoff"
        return _proposal_json("route-a", "0.4", summary=summary)

    def flaky_critic() -> str:
        call_counts["critic"] += 1
        if call_counts["critic"] == 1:
            return json.dumps(
                {
                    "critiques": [
                        {
                            "route_label": "route-a",
                            "additional_failure_modes": ["missing a lambda check"],
                            "predicted_failure_modes_adequate": "true",
                            "probe_design_critique": "fine",
                            "exit_criteria_critique": "fine",
                        },
                        {
                            "route_label": "route-b",
                            "additional_failure_modes": [],
                            "predicted_failure_modes_adequate": "true",
                            "probe_design_critique": "fine",
                            "exit_criteria_critique": "fine",
                        },
                    ]
                }
            )
        return _critique_json(["route-a", "route-b"])

    client = MockLLMClient(
        responses={
            "proposer_1": flaky_proposer_1,
            "proposer_2": _proposal_json("route-b", "0.5"),
            "critic": flaky_critic,
            "judge": json.dumps([json.loads(_proposal_json(l, "0.4")) for l in ("a", "b", "c")]),
        }
    )

    result = dg.run_dialectic_gate(task_context="Fix a bug.", llm_client=client)

    assert call_counts["proposer_1"] == 2
    assert call_counts["critic"] == 2
    assert len(result.portfolio["candidates"]) >= dg.MIN_CANDIDATES
