# TuringOS — turing_fce_integration

Constitutional execution substrate for LLM-agent work: predicates are the only
acceptance authority, all economic/routing signals are PRESERVE-class (they can
never advance accepted state), every decision is deterministically replayable,
and honest failure is a first-class, evidence-carrying outcome.

**Authority chain**: this repository is subordinate to the constitution at
`turing_v5/pack_v5_3_1/00_authority/constitution_root_law.md` (read-only,
sha-pinned) via ADR-GOV-001. Program governance, ADRs, preregistrations and the
progress tracker live in the plan directory
(`PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/`), not here.

**Claim discipline**: statuses in this repo cap at ADDRESSED (implementer
ceiling). Externally verified results are recorded in the tracker with
custody-separated certificates. Nothing here self-claims CLOSED/RELEASED.

## Layout (major areas)

| Area | What it is |
|---|---|
| `crates/turing-economy` | Deterministic market kernel: softmax routing (Q32.32 fixed point, seeded selection), tape-fold reputation (Q,N,P), independent-verifier reward channel, route pause masks. Authority fields are test-locked. |
| `crates/turing-projection`, `src/turingos/operator_agent.py` | HCI-A projection-only console (ADR-M6-001/005): renders truth, cannot write it. |
| `tools/econ_lab/` | The 2026-07 experiment & delivery program: `monitor/` (loop detector, diagnostic injection + ledger-compliant rollback, verified termination), `iterate/` (multi-attempt repair harness emitting the canonical loop_until_pass receipt chain), `dialectic/` (route dialectic gate: heterogeneous proposers + critic + judge → proposal-only route portfolios), `closed_loop/` (full organic cycle driver), `depthk/` (hierarchical stage market), `analysis/` (frozen readouts, calibration). |
| `tools/gates/`, `tools/hci/` | Self-testing constitutional gates: economic-parameter leakage (F4), no-write enforcement, projection integrity, ref lint. |
| `tools/bench/` | SWE-bench materialization, worker dispatch, and tape auditors (incl. `audit_loop_until_pass.py`, the canonical repair-loop receipt auditor). |
| `docs/handoff/` | Program reports, independent audit, evidence manifest (`ECON_PROGRAM_EVIDENCE_MANIFEST_20260712.json`: sha256 of every verdict-class artifact). |
| `evidence/bench/` | Frozen worker-safe task shards (S01-S03 materialized, leakage-audited). |

## The 2026-07 program in one paragraph

Five preregistered experiments (frozen readouts, mid-run peeking bans, ~2000
real executions) tested whether market prices can carry intelligence at small
scale. Confirmed: exploration/diversity has hard value (pure argmax is
catastrophic, paired p≤0.031); prices learn to avoid bad routes. Honest nulls:
price-guided selection never significantly beat uniform (4 attempts); price
levels do not transfer across task distributions (frozen transferred prices are
directionally harmful; live updating recovers). Mechanism findings: factored
(stage-level) action spaces yield ~6x settlement density in vivo; naive
partial-credit rewards show proxy-drift signatures. The product outcome: the
field's dominant agent failure mode (premature route lock-in, blind retries,
bare error-out) is made mechanically impossible by the monitor + dialectic +
route-market stack — first organic closed-loop cycle recorded 2026-07-11.
Full navigation for successor agents:
`PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/HANDOVER_ECON_PROGRAM_20260712.md`.

## Working here

Run the governance verifier before any work; scoring requires the pinned venv
(`~/.turingos/swebench-venv`); real-call launchers should probe provider health
first. See the handover document for environment gotchas and the reusable
capsule/workflow dispatch patterns.
