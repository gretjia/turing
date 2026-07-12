---
name: econ-kernel-review-hotspots
description: How to audit turing-economy WP code - always diff formulas against ADR-ECON-003 pins verbatim; known recurring hazard classes
metadata:
  type: project
---

When reviewing turing-economy / routing_fold / diversity_metrics work, the authoritative pinned spec is
`/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/adr/ADR-ECON-003-emergence-routing-spec-pins.md`.

**Why:** the Rust kernel's doc comments quote the ADR formulas, but the quotes can silently drop terms
(2026-07-07 audit found `derive_selection_seed_u64` omitted the pinned `trigger_event_hash` seed input while
the Python harness `tools/econ_lab/selection.py` kept it - a cross-implementation divergence the tests never saw
because each side only round-trips against itself).

**How to apply:**
- Compare each pinned formula (Decision 3/4/6) against the Rust implementation token by token, not against the Rust doc comment.
- Q32.32 helpers are duplicated in lib.rs and routing_fold.rs (deliberate, pre-merge worktrees) - a bug found in one copy exists in the other. Known: `exp2_q32` `base << floor_part` wraps sign-negative at floor_part=95 (guard is `>= 96`, should be `>= 95`).
- Tape events are Deserialize-able with untrusted fields: derived digests (e.g. `RoutingPriorUpdated.event_hash`) are NOT recomputed/verified on the consume path, only format-checked; `parse_event_hash` chunks accept a leading `+` and uppercase hex (from_str_radix), looser than the constructor's `validate_digest`.
- Cross-check tests (econ_fold_cli_cross_check.rs) compare CLI vs same-crate library, never vs the Python side - "PASS" there says nothing about Rust/Python parity.
