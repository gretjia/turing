"""WP-L3-2 acceptance tests: `tools/econ_lab/dialectic/route_market_bridge.py`
(this WP's own brief, item 2: "组合→市场桥:portfolio 转 route market 候选+先验注入
文件(--priors 语义,provenance 字段记 dialectic_gate 出处)").

Fully offline, no `econ_fold_cli` subprocess dependency (module docstring's own file-
partition note: this bridge never calls `depthk/route_market.py`'s CLI plumbing).

Claims required by this WP's own brief:
  1. `route_priors.json` is byte-for-byte consumable by `depthk/route_market.py`'s
     OWN, unmodified `load_route_priors` function (real cross-module compatibility
     check, not just "the shape looks right").
  2. Both landing artifacts carry a `provenance` field recording `dialectic_gate`
     origin (this WP's own brief's exact phrase: "provenance 字段记 dialectic_gate
     出处").
  3. An illegal portfolio (not `proposal_only`, fewer than 3 candidates, or duplicate
     labels) is rejected -- BLOCKED, never silently coerced into a market artifact.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ECON_LAB = REPO / "tools" / "econ_lab"

sys.path.insert(0, str(ECON_LAB))
sys.path.insert(0, str(ECON_LAB / "depthk"))

import dialectic.dialectic_gate as dg  # noqa: E402
import dialectic.route_market_bridge as bridge  # noqa: E402
import route_market  # noqa: E402
from dialectic.llm_clients import MockLLMClient  # noqa: E402


def _proposal_json(label: str, p: str) -> dict:
    return {
        "route_descriptor": {"label": label, "summary": f"summary for {label}", "key_choices": ["a", "b"]},
        "predicted_failure_modes": ["mode one"],
        "probe_design": f"spike on {label}",
        "exit_criteria": "abandon if the spike fails",
        "prior_estimate": {"p": p, "provenance": "estimate provenance text"},
    }


def _real_portfolio() -> dict:
    client = MockLLMClient(
        responses={
            "proposer_1": json.dumps(_proposal_json("route-a", "0.4")),
            "proposer_2": json.dumps(_proposal_json("route-b", "0.5")),
            "critic": json.dumps(
                {
                    "critiques": [
                        {
                            "route_label": "route-a",
                            "additional_failure_modes": [],
                            "predicted_failure_modes_adequate": "true",
                            "probe_design_critique": "fine",
                            "exit_criteria_critique": "fine",
                        }
                    ]
                }
            ),
            "judge": json.dumps(
                [_proposal_json("route-a", "0.4"), _proposal_json("route-b", "0.5"), _proposal_json("route-c", "0.3")]
            ),
        }
    )
    return dg.run_dialectic_gate(task_context="Fix a bug.", llm_client=client).portfolio


# ---------------------------------------------------------------------------
# 1. Cross-module compatibility with route_market.py's own --priors loader.
# ---------------------------------------------------------------------------


def test_route_priors_is_consumable_by_route_market_load_route_priors(tmp_path):
    portfolio = _real_portfolio()
    manifest = bridge.write_route_market_bridge(portfolio, tmp_path)

    priors_map, file_sha256 = route_market.load_route_priors(Path(manifest["route_priors_path"]))

    assert priors_map == {"route-a": 0.4, "route-b": 0.5, "route-c": 0.3}
    assert isinstance(file_sha256, str) and len(file_sha256) == 64


def test_route_priors_payload_shape_matches_pinned_shape():
    portfolio = _real_portfolio()
    payload = bridge.portfolio_to_route_priors(portfolio)
    assert set(payload["priors"].keys()) == {"route-a", "route-b", "route-c"}
    assert all(isinstance(v, float) for v in payload["priors"].values())


# ---------------------------------------------------------------------------
# 2. Provenance recording dialectic_gate origin.
# ---------------------------------------------------------------------------


def test_route_priors_provenance_names_dialectic_gate_origin():
    portfolio = _real_portfolio()
    payload = bridge.portfolio_to_route_priors(portfolio)
    assert payload["provenance"]["origin"] == "dialectic_gate.v1"
    assert payload["provenance"]["portfolio_digest"] == portfolio["portfolio_digest"]
    assert payload["provenance"]["role_chain"] == portfolio["provenance"]["role_chain"]


def test_route_candidates_provenance_names_dialectic_gate_origin():
    portfolio = _real_portfolio()
    payload = bridge.portfolio_to_route_candidates(portfolio)
    for entry in payload["candidates"]:
        assert entry["provenance"]["origin"] == "dialectic_gate.v1"
        assert entry["provenance"]["portfolio_digest"] == portfolio["portfolio_digest"]


def test_write_route_market_bridge_writes_both_files(tmp_path):
    portfolio = _real_portfolio()
    manifest = bridge.write_route_market_bridge(portfolio, tmp_path)

    candidates_path = Path(manifest["route_candidates_path"])
    priors_path = Path(manifest["route_priors_path"])
    assert candidates_path.exists()
    assert priors_path.exists()

    candidates_payload = json.loads(candidates_path.read_text())
    assert candidates_payload["proposal_only"] is True
    assert len(candidates_payload["candidates"]) == 3


# ---------------------------------------------------------------------------
# 3. Illegal portfolios are rejected, never silently coerced.
# ---------------------------------------------------------------------------


def test_non_proposal_only_portfolio_is_rejected():
    portfolio = _real_portfolio()
    portfolio = dict(portfolio)
    portfolio["proposal_only"] = False
    with pytest.raises(dg.DialecticGateError, match="proposal_only must be hard True"):
        bridge.portfolio_to_route_priors(portfolio)


def test_too_few_candidates_is_rejected():
    portfolio = _real_portfolio()
    portfolio = dict(portfolio)
    portfolio["candidates"] = portfolio["candidates"][:2]
    with pytest.raises(dg.DialecticGateError, match=">= 3"):
        bridge.portfolio_to_route_priors(portfolio)


def test_duplicate_labels_is_rejected():
    portfolio = _real_portfolio()
    portfolio = dict(portfolio)
    dup = json.loads(json.dumps(portfolio["candidates"][0]))
    portfolio["candidates"] = list(portfolio["candidates"]) + [dup]
    with pytest.raises(dg.DialecticGateError, match="duplicate candidate route labels"):
        bridge.portfolio_to_route_priors(portfolio)
