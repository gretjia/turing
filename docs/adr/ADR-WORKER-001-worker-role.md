# ADR-WORKER-001 — The Worker is a 1.0 PROJECT role

**Status:** Accepted (Stage 0). **Layer:** 5 (Code) / 4 (ordinary execution for swap).

## Context
The prior plan cited **Art. V.1.2** as the source of the Worker root role. **Art. V.1.2 defines ArchitectAI,
not Worker AI.** This is the keystone mis-leveling the rewrite corrects (plan §5.3 Fix 1).

## Decision
The Worker AI is a single **TuringOS 1.0 PROJECT role**: *execute one Atom inside an isolated Macro
worktree, under a Shielded Work Capsule (contract + atom allowlist + budget); its work is observed via
imported Macro Git evidence + a Receipt; its candidate is accepted or rejected by the deterministic Micro
Predicate.* The Worker is **replaceable** (≥2 real subscription adapters in Stage 2; a deterministic
**FakeWorker** in Stage 1). Replacing/adding a Worker is **ordinary execution (layer 4)** — no Veto-AI, no
constitution amendment. `WorkerProfile.dispatch_purpose` (`PRIMARY_EXECUTION` / `CAPABILITY_SECONDARY` /
`PROVIDER_CONTINUITY` / `OFFLINE_BOOTSTRAP`) is a **routing enum**, not a role and not a constitutional concept.

## Consequences
- **Never cite Art. V.1.2 for the Worker.** ArchitectAI/Veto-AI (the META loop, Art. V) are DEFERRED to 2.0.
- The `WorkerAdapter` seam admits more adapters, an Agent Protocol server, agent-native VCS — all additive.
- No capability ranking is produced or relied upon; adapters are interchangeable at the seam (S-6).

## Constitution
Cites Art. IV (boot/dispatch) and the §5.6 citation discipline. Subordinate to `constitution.md`.
