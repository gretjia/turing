# Shipgate — Foundation kernel — receipt

**Date:** 2026-06-20 · **Result:** PASS · **Built by:** Workflow `wecrsyjag` (run `wf_3ad7868e-465`),
21 agents, dependency-layered implement + adversarial audit (Verifier ≠ Implementer) + 1 rework round.

## Modules shipped (10 + base)
`errors`, `__init__` (orchestrator-authored base) · `codec` (turingos.jcs.v1) · `registry` · `schemas` ·
`envelope` · `tape` · `reduce` · `evidence` · `replay` · `predicate` · `cli`. (~2224 LOC src.)

## Gate (acceptance_commands, re-run every build)
1. `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'` → **235 tests OK**.
2. `PYTHONPATH=src python3 tests/integration/kernel_smoke.py` → **ALL_PASS** (10/10), exit 0.

## Independent verification (orchestrator, Verifier ≠ Implementer)
- kernel_smoke: object_format=sha256 · accept advances · proposal preserves · **failure-is-state** ·
  candidate-accept advances accepted_head==tape_tip · **exactly 2 refs** · replay rebuilds accepted_head ·
  q_t has goal · two replays byte-equal · handoff rebuild equal.
- Adversarial spot-checks: wrong-writer → GuardReject · ADVANCE-without-predicate-PASS → RejectedAppend ·
  non-FF `_expect_parent` hook present · predicate has **no taste/quality tokens** · replay recomputes
  content_digest & uses **no sqlite** (no sqlite3 import anywhere — Tape-canonical).

## Audit summary
9/10 modules passed audit first pass; **tape** failed (3 findings) → reworked → green. "Pass-with-findings"
were minor (auditor-accepted). All gates green post-rework.

## Forbidden-pattern audit (clean)
failure-on-Tape ✓ · no projection-as-truth (replay Tape-only) ✓ · predicate not bypassable (advance needs
SOVEREIGN_ACCEPT + PASS) ✓ · accepted state rebuildable ✓ · no NL gate ✓ · append-only/FF-only ✓ · contracts
subordinate to constitution ✓.
