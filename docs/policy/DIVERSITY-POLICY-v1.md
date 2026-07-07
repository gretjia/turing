# Diversity Policy v1 — Routing Lineage Monoculture Guardrail

Status: Accepted (A-zone public artifact, ADR-ECON-003 Decision 5).

Authority: subordinate to `constitution_root_law.md`; governed by
`research/RES_ECON_emergence_toplevel_design_20260707.md` §1.5 and
`ADR-ECON-003-emergence-routing-spec-pins.md` Decision 3 ("N_eff / H_lineage
估计式与 A 区地板"). This document does not restate or override either source;
it is the standing public disclosure that the guardrail described below exists
and applies to every `MarketRouter::suggest` call.

## What this policy commits to (A-zone: safe to disclose)

1. Every window of routing decisions is continuously measured for two
   quantities: **N_eff** (an effective-independent-lineage count derived from
   the Pearson correlation structure of recent settlement outcomes) and
   **H_lineage** (the Shannon entropy, in bits, of which lineage gets routed
   to).
2. Both quantities feed a standing **monoculture guardrail**: when measured
   diversity falls to or below the floor values fixed in ADR-ECON-003
   Decision 3, the router's temperature-annealing schedule is held at its
   high-exploration setting (anneal is paused) instead of continuing to cool
   toward exploitation, until diversity recovers above the ADR's hysteresis
   band. This is a hard, code-enforced arbitration, not a discretionary
   judgment call.
3. The estimator is a deterministic, tape-fold-only pure function of already
   -committed settlement history (Art 0.2): identical settlement tapes always
   reproduce identical N_eff/H_lineage measurements and identical guardrail
   arbitration, independent of wall-clock time, input ordering, or any
   platform-specific floating point behavior.
4. The two numeric floor values themselves, and the fact that this
   softmax-based routing/guardrail mechanism exists at all, are the
   ADR-ECON-003 Decision 5 "A 区(公开)" facts — they are intentionally not a
   secret. What this document deliberately does **not** restate is any
   B-zone quantity (temperature schedule constants, annealing horizon,
   domain-bucket/scaffold-id key material, or any other parameter Art III.4
   requires to be withheld from agent-visible surfaces). Those remain sourced
   exclusively from the ADR's own B-zone mechanism and are never echoed
   through error messages, logs, tool schemas, or docstrings.

## Change control

This is a versioned, owner-governed document (v1, dated 2026-07-07). Any
revision to the guardrail's existence, its estimator's defining formula, or
its floor values requires a new ADR decision and a new version of this
document with its own hash; no implicit drift is permitted (Art 0.2 / F3).
The `diversity_policy_hash` field carried on every `BudgetSuggestion` is the
SHA-256 digest of the exact bytes of the current version of this file,
allowing any downstream consumer to verify, without trusting the router's
runtime, exactly which version of this policy governed a given routing
decision.

## Non-goals

This document is not itself a source of truth for the numeric floor values,
the estimator's formula, or the arbitration hysteresis band — those are
pinned once, in ADR-ECON-003 Decision 3, and implemented once, in
`crates/turing-economy/src/diversity_metrics.rs` and
`crates/turing-economy/src/routing_fold.rs`. This document exists solely so
that the fact of the guardrail's existence has a public, hashable, versioned
artifact independent of the ADR's own change history.
