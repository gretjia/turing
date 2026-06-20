# Shipgate 2 — receipt (Stage 2: ≥2 real Worker adapters + GitHub)

**Date:** 2026-06-20 · **Result:** PASS · Operator native login (no credential bundling), GitHub ops pre-authorized.

## What changed (loop shape unchanged; Worker + Macro became REAL)
- **`WorkerAdapter` real implementations** — `src/turingos/worker/cli.py` `CliWorkerAdapter` drives any headless
  one-shot agent CLI (claude/codex/agy/grok) in an isolated worktree, builds an adapter-agnostic
  `turingos.receipt.v1` (tree_oid anchor + files_touched), PG-reap timeout (ADR-0008).
- **Smart dispatch router** — `src/turingos/dispatch_router.py` picks model + thinking effort PER TASK,
  **fast by default**, escalating on risk/breadth/retry. Fixes the expensive-default problem (claude
  opus-4.8 xhigh; codex gpt-5.5 high). ADR-0008.
- **GitHub PR/CI MacroAdapter** — `src/turingos/macro.py` via `gh`: create/push/PR/observe-CI/import-anchor/
  **human-confirmed merge**/dispose. Merge refuses without a recorded human-confirm Tape event.

## Spike gates (live)
- **S-6 PRE** (`s6_probe_result.json`) — PASS: claude/codex/agy produced the artifact headless; PG-reap confirmed.
- **S-6 GATE** (`s6_gate_result.json`) — PASS: ONE fixed capsule → 3 real adapters at the **router fast tier**
  (claude sonnet/low · codex effort=low · agy Gemini-Flash-Low); each candidate worktree-confined, in-scope,
  acceptance-passing, schema-valid adapter-agnostic receipt, no orphan, **no capability ranking**.
- **S-5** (`s5_github_result.json`) — PASS on a disposable repo `gretjia/turingos-s5-a51cb9dc`: PR #1 opened;
  **real CI check observed** (`ok` pass, 3s, live Actions run); PR head tree OID imported as
  `MacroObservationImported`; merge **refused without** a confirm and **merged after** the recorded
  human-confirm event (`mu:fc1384e3…`). Repo disposal: **archived** (full delete needs the `delete_repo`
  token scope — `gh auth refresh -h github.com -s delete_repo`; adapter self-heals to archive).

## Constitution / forbidden-pattern audit (clean)
Macro never directly sovereign (PR/CI imported as PRESERVE observation; only Predicate-PASS CandidateAccepted
advances accepted_head) · merge=human-confirmed (recorded on the Tape) · no credential bundling (native gh) ·
worker self-report never the gate (Predicate re-runs) · adapters interchangeable, router tunes cost not vendor.

## Residual
- `delete_repo` token scope absent → disposable repos are **archived** not deleted (minor; one-time scope refresh fixes).
