"""WP-L3-2 -- portfolio -> route market bridge (this WP's own brief, item 2: "组合→
市场桥:portfolio 转 route market 候选+先验注入文件(--priors 语义,provenance 字段
记 dialectic_gate 出处)").

Converts one `route_portfolio.v1` (`dialectic_gate.run_dialectic_gate`'s own output
shape) into two landing artifacts at `depthk/route_market.py`'s own `--priors`
injection point (ADR-ECON-003 Decision 6.1/7.6 semantics, reused verbatim -- see
`route_market.py`'s own module docstring, "`--priors` (warm-start P injection)"):

  1. `route_candidates.json` -- one entry per portfolio candidate, carrying its
     `route_label`, a locally-computed (NOT the authoritative `econ_fold_cli`-derived
     one -- see `local_route_descriptor_digest`'s own docstring) descriptor digest for
     traceability/dedup, its flattened descriptor text, and a `provenance` block
     naming this WP's own brief's required field: `{"origin": "dialectic_gate.v1",
     "portfolio_digest": ..., "role_chain": [...]}`.
  2. `route_priors.json` -- the exact `{"priors": {"<route_label>": p, ...}}` shape
     `route_market.py::load_route_priors` already accepts (its OTHER accepted shape,
     a bare mapping with no `"priors"` wrapper, is never emitted here -- always the
     pinned, self-documenting shape), with a sibling top-level `"provenance"` key
     `load_route_priors` simply ignores (it only ever reads `parsed["priors"]`) -- so
     this file is a drop-in `--priors` argument for `route_market.py` AS-IS, with no
     format change required on that file's side.

File-partition discipline (mirrors `depthk/route_market.py`'s own "does not import,
read, or modify `tools/econ_lab/monitor/` or `tools/econ_lab/live_driver.py`" red
line, applied here in the opposite direction): this module never imports from, reads,
or modifies `depthk/route_market.py` -- it independently reproduces only the tiny
`--priors` JSON *shape* that module's own docstring documents (not its selection
math, not its CLI plumbing), matching that file-partition boundary from the other
side. `derive_route_keys`/`econ_fold_cli` (the authoritative, Rust-backed route_id/
route_scaffold derivation) is deliberately NOT called from here: this bridge produces
the market-facing *candidate* + *priors* artifacts at the landing point, not a second,
competing implementation of route-key derivation -- wiring `route_candidates.json`
into a real `derive-route-keys` call remains `route_market.py`'s own job (or a future
WP's), never re-derived here.

This module is `proposal_only`-adjacent bookkeeping, not a new agent-visible text
surface (`route_candidates.json`/`route_priors.json` are market-mechanism wire
artifacts, the same category as `route_market.py`'s own pre-existing `--priors` JSON
input, which already carries bare floats -- not GRILL-ME conversation text). The
worker-visible TEXT this bridge's inputs are made of (every candidate's
`route_descriptor`/`predicted_failure_modes`/`probe_design`/`exit_criteria`/
`prior_estimate.provenance` string) was already B-zone-scanned once by
`dialectic_gate.run_dialectic_gate` before this module ever sees it; this module
re-validates that invariant defensively (`assert_portfolio_is_legal`) rather than
trusting a caller-supplied portfolio blindly.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping

from .dialectic_gate import DialecticGateError, MIN_CANDIDATES, jcs_sha256, scan_worker_text

BRIDGE_ORIGIN = "dialectic_gate.v1"
ROUTE_CANDIDATES_SCHEMA = "econ_lab.dialectic.route_market_bridge.route_candidates.v1"
ROUTE_PRIORS_SCHEMA = "econ_lab.dialectic.route_market_bridge.route_priors.v1"


def assert_portfolio_is_legal(portfolio: Mapping[str, Any]) -> None:
    """Defensive re-check (this module's own input contract, not a re-derivation of
    `dialectic_gate`'s own validation): `proposal_only` must be hard `True`, and there
    must be >= `MIN_CANDIDATES` candidates. Raises `DialecticGateError` -- reused
    directly rather than a new bridge-local exception type, since this is the exact
    same "structurally illegal, BLOCKED, never silently guessed" family of condition
    `dialectic_gate.py` itself raises."""
    if portfolio.get("proposal_only") is not True:
        raise DialecticGateError("route_market_bridge: portfolio.proposal_only must be hard True")
    candidates = portfolio.get("candidates")
    if not isinstance(candidates, list) or len(candidates) < MIN_CANDIDATES:
        raise DialecticGateError(
            f"route_market_bridge: portfolio must carry >= {MIN_CANDIDATES} candidates, "
            f"got {candidates!r}"
        )
    labels = [c["route_descriptor"]["label"] for c in candidates]
    if len(set(labels)) != len(labels):
        raise DialecticGateError(f"route_market_bridge: duplicate candidate route labels: {labels!r}")


def local_route_descriptor_digest(route_descriptor: Mapping[str, Any]) -> str:
    """A locally-computed JCS-SHA256 of one candidate's `route_descriptor` (ADR-ECON-
    007 Decision 5: "route_id = 路线描述子(JCS)哈希"). Explicitly NOT the authoritative
    `route_id`/`route_scaffold` `econ_fold_cli derive-route-keys` would produce (this
    bridge never calls that CLI -- see module docstring) -- this digest exists only
    for THIS bridge's own local dedup/traceability between `route_candidates.json`
    and `route_priors.json`, and is named `route_descriptor_digest`, never `route_id`,
    to avoid ever being mistaken for the CLI's own authoritative identity."""
    return jcs_sha256(dict(route_descriptor))


def portfolio_to_route_candidates(portfolio: Mapping[str, Any]) -> Dict[str, Any]:
    """Builds the `route_candidates.json` payload (this WP's own brief item 2's first
    half: "portfolio 转 route market 候选")."""
    assert_portfolio_is_legal(portfolio)
    portfolio_digest = portfolio.get("portfolio_digest")
    role_chain = list((portfolio.get("provenance") or {}).get("role_chain") or [])

    entries: List[Dict[str, Any]] = []
    for candidate in portfolio["candidates"]:
        rd = candidate["route_descriptor"]
        descriptor_text = {"summary": rd["summary"], "key_choices": "|".join(rd["key_choices"])}
        # Defensive re-scan (module docstring: "re-validates that invariant
        # defensively rather than trusting a caller-supplied portfolio blindly") --
        # this text was already scanned once inside `dialectic_gate.run_dialectic_
        # gate`, but this bridge accepts any caller-supplied portfolio mapping, not
        # only ones that just came out of that function in-process.
        scan_worker_text(label=f"bridge.{rd['label']}.summary", text=descriptor_text["summary"])
        scan_worker_text(label=f"bridge.{rd['label']}.probe_design", text=candidate["probe_design"])
        scan_worker_text(label=f"bridge.{rd['label']}.exit_criteria", text=candidate["exit_criteria"])
        for i, mode in enumerate(candidate["predicted_failure_modes"]):
            scan_worker_text(label=f"bridge.{rd['label']}.predicted_failure_modes[{i}]", text=mode)
        entries.append(
            {
                "route_label": rd["label"],
                "route_descriptor_digest": local_route_descriptor_digest(rd),
                "descriptor_text": descriptor_text,
                "predicted_failure_modes": list(candidate["predicted_failure_modes"]),
                "probe_design": candidate["probe_design"],
                "exit_criteria": candidate["exit_criteria"],
                "provenance": {
                    "origin": BRIDGE_ORIGIN,
                    "portfolio_digest": portfolio_digest,
                    "role_chain": role_chain,
                },
            }
        )
    return {
        "schema": ROUTE_CANDIDATES_SCHEMA,
        "proposal_only": True,
        "portfolio_digest": portfolio_digest,
        "candidates": entries,
    }


def portfolio_to_route_priors(portfolio: Mapping[str, Any]) -> Dict[str, Any]:
    """Builds the `route_priors.json` payload: the exact `{"priors": {"<route_label>":
    p, ...}}` shape `route_market.py::load_route_priors` accepts (this WP's own
    brief item 2's second half: "先验注入文件(--priors 语义)"), `p` parsed from each
    candidate's own `prior_estimate.p` decimal string, plus a sibling `provenance`
    key `load_route_priors` ignores harmlessly (see module docstring)."""
    assert_portfolio_is_legal(portfolio)
    priors: Dict[str, float] = {}
    for candidate in portfolio["candidates"]:
        label = candidate["route_descriptor"]["label"]
        p = float(candidate["prior_estimate"]["p"])
        priors[label] = p
    return {
        "schema": ROUTE_PRIORS_SCHEMA,
        "priors": priors,
        "provenance": {
            "origin": BRIDGE_ORIGIN,
            "portfolio_digest": portfolio.get("portfolio_digest"),
            "role_chain": list((portfolio.get("provenance") or {}).get("role_chain") or []),
        },
    }


def write_route_market_bridge(portfolio: Mapping[str, Any], out_dir: Path) -> Dict[str, Any]:
    """Writes both landing artifacts under `out_dir` and returns a small manifest
    (paths + both payloads' own digests) -- never mutates `portfolio` itself."""
    out_dir.mkdir(parents=True, exist_ok=True)
    candidates_payload = portfolio_to_route_candidates(portfolio)
    priors_payload = portfolio_to_route_priors(portfolio)

    candidates_path = out_dir / "route_candidates.json"
    priors_path = out_dir / "route_priors.json"
    candidates_path.write_text(
        json.dumps(candidates_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    priors_path.write_text(json.dumps(priors_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "route_candidates_path": str(candidates_path),
        "route_priors_path": str(priors_path),
        "route_candidates_digest": jcs_sha256(candidates_payload),
        "route_priors_digest": jcs_sha256(priors_payload),
    }


__all__ = [
    "BRIDGE_ORIGIN",
    "ROUTE_CANDIDATES_SCHEMA",
    "ROUTE_PRIORS_SCHEMA",
    "assert_portfolio_is_legal",
    "local_route_descriptor_digest",
    "portfolio_to_route_candidates",
    "portfolio_to_route_priors",
    "write_route_market_bridge",
]
