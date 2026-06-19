# ADR-0005 — Capsule + Receipt schemas

**Status:** Accepted (Stage 0). **Layer:** 3. **Contract:** `contracts/capsule.schema.json`, `contracts/receipt.schema.json`.

## Context
The loop needs a **Shielded Work Capsule** (scope the Worker may touch, with gate logic kept OUT — Art. III.4
Goodhart) and an **adapter-agnostic Receipt** (identical terms regardless of which Worker ran — S-6).

## Decision
- **Capsule v1** (`turingos.capsule.v1`): `atom_id`, `allowed_files` (scope), `budget`, `acceptance_commands`
  (frozen declared tests), `injected_rules` (ONLY relevant abstract FailureClass rules — raw payloads/stdout
  forbidden), `context` (tape_tip/accepted_head). **No gate/scoring logic in the capsule.**
- **Receipt v1** (`turingos.receipt.v1`): `capsule_id`, `worker_id` (adapter-agnostic), `worktree_path`,
  `candidate.tree_oid` (Macro anchor), `files_touched`, `declared_test_results` (self-report, recorded NOT
  trusted — predicate P6 re-runs), normalized `status`, `no_orphan`.
- ASCII-only load-bearing keys, no floats (`turingos.jcs.v1`).

## Consequences
- Additive field = minor; breaking = migration + ADR (v2 family).
- The shield seam (`injected_rules`) is where adaptive broadcast/reputation plug in later (3.0).

## Constitution
Art. III (shield/Goodhart), I.1 (declared tests as a mechanical check).
