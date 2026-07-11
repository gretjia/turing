#!/usr/bin/env python3
"""WP-L3-2 -- real smoke driver for the GRILL-ME route dialectic gate (this WP's own
brief, item 4: "真实冒烟 ≤6 调用(1 个真实任务上下文跑一次完整三角色门,产出真
portfolio,SMOKE_FIXTURE)").

One full proposer×2 -> critic -> judge pass on one real task/spec context (this WP's
own brief, item 4) costs exactly 4 LLM calls (`dialectic_gate.PROPOSER_COUNT` + 1
critic + 1 judge) -- within the WP's own <= 6 call budget with headroom, and the
default `--task-context` below is the REAL spec this very WP was built against
(`adr/ADR-ECON-007-route-market-loop-remedy.md` Decision 5 +
`research/RES_ROUTE_lockIn_remedy_design_20260710.md` §2 L3.6), not a synthetic
fixture -- this smoke run points the gate at the honest question "what route should
close the L3 dialectic-gate WP itself", the same self-referential move the WP's own
brief names ("把建造 TuringOS 的元流程...下沉为产品机制").

Two modes:
  --mode real (default) -- `llm_clients.SiliconFlowLLMClient`, a genuine network call
    per role. Honest degrade (this codebase's own established `live_driver.py::
    dispatch_via_siliconflow` precedent): if `SILICONFLOW_API_KEY` is unset, this
    script writes a `status: NOT_RUN` verdict naming the missing env var --  it never
    fabricates a completion, never silently falls back to the mock client.
  --mode offline-mock -- `llm_clients.MockLLMClient` with a small canned, clearly-
    labeled fixture response set, `evidence_class=OFFLINE_MOCK` (never `SMOKE_FIXTURE`
    -- this mode exists only to exercise this SCRIPT's own file-writing/bridge
    plumbing without a network call, the same "offline dry run of a real driver's own
    plumbing" role `route_market.py --offline-mock` already plays for that driver).

Usage:
  python3 tools/econ_lab/dialectic/dialectic_smoke.py --run-dir tools/econ_lab/runs/dialectic_smoke_20260711
  python3 tools/econ_lab/dialectic/dialectic_smoke.py --run-dir /tmp/x --mode offline-mock
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

DIALECTIC_DIR = Path(__file__).resolve().parent
ECON_LAB_DIR = DIALECTIC_DIR.parent
if str(ECON_LAB_DIR) not in sys.path:
    sys.path.insert(0, str(ECON_LAB_DIR))

import dialectic.dialectic_gate as dialectic_gate  # noqa: E402
import dialectic.route_market_bridge as route_market_bridge  # noqa: E402
from dialectic.llm_clients import (  # noqa: E402
    MissingCredentialError,
    MockLLMClient,
    SiliconFlowLLMClient,
)

SMOKE_SCHEMA = "econ_lab.dialectic.dialectic_smoke.v1"
EVIDENCE_CLASS_SMOKE = "SMOKE_FIXTURE"
EVIDENCE_CLASS_OFFLINE = "OFFLINE_MOCK"

# The real task/spec context this smoke run points the gate at (module docstring):
# this WP's own real assignment, drawn from its own real source-of-truth paths.
DEFAULT_TASK_CONTEXT = {
    "task_id": "WP-L3-2-self-referential",
    "spec_sources": [
        "adr/ADR-ECON-007-route-market-loop-remedy.md Decision 5",
        "research/RES_ROUTE_lockIn_remedy_design_20260710.md section 2 L3.6",
    ],
    "problem_statement": (
        "TuringOS needs a product-level route dialectic gate: given a task or spec "
        "context, produce at least three heterogeneous candidate technical routes "
        "(never a single committed route), each with its own predicted failure "
        "modes, a cheap probe design, an exit criterion, and a provenanced prior "
        "estimate, by running two structurally distinct proposers, one adversarial "
        "critic pass, and one synthesizing judge pass. Propose a concrete "
        "implementation route for building exactly this gate as a small, testable "
        "Python package that reuses an existing verification-report leak scanner "
        "read-only, bridges its output into an existing route-market warm-start "
        "prior format, and never advances any accepted decision on its own."
    ),
    "constraints": [
        "output is proposal_only; no route is ever auto-accepted",
        "every candidate route's worker-visible text must pass an existing leakage scanner unmodified",
        "the gate must support re-entry from a prior route's falsification evidence",
    ],
}


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _offline_mock_client() -> MockLLMClient:
    """A small, clearly-labeled canned fixture -- exercises this script's own
    plumbing only (module docstring's `--mode offline-mock`), never claimed as real
    evidence."""

    def proposal(label: str, p: str, perspective_note: str) -> str:
        return json.dumps(
            {
                "route_descriptor": {
                    "label": label,
                    "summary": (
                        f"Offline-mock synthesized route for the dialectic gate itself, "
                        f"perspective: {perspective_note}."
                    ),
                    "key_choices": ["small self-contained package", "reuse existing scanner read-only"],
                },
                "predicted_failure_modes": [
                    "LLM output does not parse as strict JSON",
                    "judge fails to reach three candidates",
                ],
                "probe_design": "run one offline mock pass through the full three-role pipeline first",
                "exit_criteria": "abandon if schema validation fails on two consecutive real attempts",
                "prior_estimate": {"p": p, "provenance": "offline-mock canned estimate, not a real call"},
            }
        )

    critic_resp = json.dumps(
        {
            "critiques": [
                {
                    "route_label": "conservative-package",
                    "additional_failure_modes": ["prompt template drifts out of sync with schema"],
                    "predicted_failure_modes_adequate": "false",
                    "probe_design_critique": "fine as a first pass",
                    "exit_criteria_critique": "concrete enough",
                },
                {
                    "route_label": "structural-package",
                    "additional_failure_modes": [],
                    "predicted_failure_modes_adequate": "true",
                    "probe_design_critique": "fine",
                    "exit_criteria_critique": "fine",
                },
            ]
        }
    )
    judge_resp = json.dumps(
        [
            json.loads(proposal("conservative-package", "0.55", "conservative reuse")),
            json.loads(proposal("structural-package", "0.35", "structural redesign")),
            json.loads(proposal("hybrid-package", "0.45", "judge-synthesized hybrid")),
        ]
    )
    return MockLLMClient(
        responses={
            "proposer_1": proposal("conservative-package", "0.55", "conservative reuse"),
            "proposer_2": proposal("structural-package", "0.35", "structural redesign"),
            "critic": critic_resp,
            "judge": judge_resp,
        }
    )


_RECEIPT_REDACTION_MARKER = (
    "[REDACTED: this attempt's raw provider response failed the B-zone leak scan and "
    "was retried by dialectic_gate.py's own bounded retry -- the metadata fields "
    "above are kept, but the flagged raw text itself is dropped before this "
    "worker-visible receipts file is written]"
)


def _redact_receipt_if_bzone_leak(receipt: Dict[str, Any]) -> Dict[str, Any]:
    """`receipts.json` is written to this WP's own `tools/econ_lab/runs/` tree, a
    committed, worker-visible path -- so it is subject to the exact same "全部
    worker 可见文本过 B 区泄漏扫描" rule this WP's own brief states for every other
    worker-visible surface. A raw provider receipt can legitimately be one of the
    attempts `dialectic_gate._complete_with_role_retry` itself REJECTED and retried
    away (that is precisely what the retry mechanism exists to catch) -- `on_receipt`
    fires on every network call, successful or not, so an unscanned `response_raw`
    would otherwise leak that rejected text into this committed file even though it
    never made it into the accepted `portfolio.json`/`critiques.json`. Returns a NEW
    dict; `receipt` itself is never mutated."""
    raw = receipt.get("response_raw")
    redacted = dict(receipt)
    if not isinstance(raw, str):
        redacted["bzone_redacted"] = False
        return redacted
    try:
        dialectic_gate.scan_worker_text(label="receipt.response_raw", text=raw)
    except dialectic_gate.DialecticGateError:
        redacted["response_raw"] = _RECEIPT_REDACTION_MARKER
        redacted["bzone_redacted"] = True
        return redacted
    redacted["bzone_redacted"] = False
    return redacted


def run(run_dir: Path, mode: str) -> Dict[str, Any]:
    receipts: List[Dict[str, Any]] = []

    if mode == "offline-mock":
        client = _offline_mock_client()
        evidence_class = EVIDENCE_CLASS_OFFLINE
    else:

        def on_receipt(receipt: Dict[str, Any]) -> None:
            receipts.append(receipt)

        # `SiliconFlowLLMClient`'s own default `timeout_s=120` is tuned for a short
        # single-proposal completion; the critic/judge roles here receive a much
        # larger user prompt (both proposals, and for judge both proposals AND the
        # critiques) so the provider can legitimately take longer to first-byte --
        # widened here, in this real-network driver only (offline tests never touch
        # the network at all), to `live_driver.py::dispatch_via_siliconflow`'s own
        # established `timeout_s=600` default for exactly the same real-network-call
        # reason, not a new number invented for this WP.
        client = SiliconFlowLLMClient(on_receipt=on_receipt, timeout_s=600)
        evidence_class = EVIDENCE_CLASS_SMOKE

    try:
        result = dialectic_gate.run_dialectic_gate(
            task_context=DEFAULT_TASK_CONTEXT, llm_client=client
        )
    except MissingCredentialError as exc:
        verdict = {
            "schema": SMOKE_SCHEMA,
            "status": "NOT_RUN",
            "missing_env": ["SILICONFLOW_API_KEY"],
            "reason": str(exc),
            "worker_calls_used": 0,
            "significance_claims": "NONE -- credential missing, no call was made",
        }
        write_json(run_dir / "verdict.json", verdict)
        return verdict

    n_calls = len(client.calls) if isinstance(client, MockLLMClient) else len(receipts)

    write_json(run_dir / "portfolio.json", result.portfolio)
    write_json(
        run_dir / "critiques.json",
        {"schema": result.critiques.get("schema"), "critiques": result.critiques.get("critiques")},
    )
    if receipts:
        scanned_receipts = [_redact_receipt_if_bzone_leak(r) for r in receipts]
        write_json(run_dir / "receipts.json", {"receipts": scanned_receipts})

    bridge_dir = run_dir / "route_market_bridge"
    bridge_manifest = route_market_bridge.write_route_market_bridge(result.portfolio, bridge_dir)

    verdict = {
        "schema": SMOKE_SCHEMA,
        "status": "COMPLETED",
        "mode": mode,
        "evidence_class": evidence_class,
        "task_context_digest": result.portfolio["task_context_digest"],
        "portfolio_digest": result.portfolio["portfolio_digest"],
        "candidate_labels": [c["route_descriptor"]["label"] for c in result.portfolio["candidates"]],
        "worker_calls_used": n_calls,
        "route_market_bridge": bridge_manifest,
        "significance_claims": "NONE -- exploratory smoke fixture only",
    }
    write_json(run_dir / "verdict.json", verdict)
    return verdict


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=("real", "offline-mock"), default="real")
    args = parser.parse_args()

    verdict = run(args.run_dir, args.mode)
    print(json.dumps(verdict, indent=2))


if __name__ == "__main__":
    main()
