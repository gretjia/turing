# Shipgate 1 — receipt (Stage 1: fake/manual Worker drives the FULL loop E2E + replay)

**Date:** 2026-06-20 · **Result:** PASS · **This is the BOOT MILESTONE.**
**Built by:** Workflow `w6ji4mcxw` (loop layer, 16 agents) on the Foundation kernel (Workflow `wecrsyjag`).

## Exit criteria (plan §6.2 Shipgate 1)
1. **Full loop runs end-to-end with the fake Worker, traversing BOTH predicate branches** — `loop_e2e.py`
   summary: `accepted=2, failed=1, branches_covered=true`. Every sovereignty-boundary change is a Tape event.
2. **S-3, S-4, S-7 GATE assertions green on the REAL Tape/capsule/receipt** — `loop_e2e.py` ALL_PASS (10/10):
   - c1 branches_covered · c2 ≥1 accept · c3 ≥1 failure
   - c4 replay rebuilds accepted_head · c5 two replays byte-equal · c6 handoff bundle rebuild equal **(S-7)**
   - c7 failure-on-Tape · c8 shield no raw leak · c9 shield abstract rule injected **(S-4)**
   - c10 dispatch is authorization, never "accepted" (Authorized-vs-Accepted)
3. **Conservation** — `WorkGraph == derive(q_t, tape_t, macro_obs)`; replay consults the Tape only (no sqlite).
4. **FREEZE the 18-event registry count NOW** — done: `contracts/event_registry.json` status → **FROZEN**
   (version 1.0.0), the first E2E loop having validated it (Stage-1 freeze rule, App E §E.4).

## Independent verification (orchestrator, Verifier ≠ Implementer)
- `tests/integration/loop_e2e.py` (authored by orchestrator) → ALL_PASS.
- `tests/integration/kernel_smoke.py` → ALL_PASS (10/10).
- Full suite: **373 unit tests OK**.
- Adversarial probes: S-3 predicate determinism (identical reason_digest); S-4 only-relevant rule filtering
  (same-module DeclaredTests included, unrelated-module Scope EXCLUDED, rules abstract — no raw leak).

## Forbidden-pattern release audit (all clean)
failure-on-Tape ✓ · no projection-as-hidden-truth (replay Tape-only) ✓ · no predicate bypass (accepted_head
advances only on SOVEREIGN_ACCEPT + Predicate PASS) ✓ · accepted state rebuildable from Tape ✓ · no NL
faking a gate (predicate has no taste/quality check) ✓ · append-only/FF-only, no history overwrite ✓ ·
project Spec/registry treated as subordinate to the constitution ✓.

## Loop modules shipped
boot · planner · capsule + FailureMemory (shield, S-4) · worker/adapter + FakeWorker (PG-reap timeout/kill) ·
signing (SigningBackend seam + ApprovalCard) · explore + HumanSteer · panorama (Authorized-vs-Accepted, text
renderer, no hard textual dep) · loop (the E2E driver).
