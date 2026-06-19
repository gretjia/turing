# Shipgate 0 — receipt (Stage 0: freeze baseline + prove substrate)

**Date:** 2026-06-20 · **Mode:** autonomous · **Result:** PASS

## Exit criteria (plan §6.1)
1. **S-1 PRE green** — `evidence/stage0/s1_result.json`, ALL_PASS=true:
   - `rev-parse --show-object-format == sha256` ✓
   - FailureNode append advances `tape_tip`, NOT `accepted_head` (failure-is-state) ✓
   - CandidateAccepted advances `accepted_head` (== `tape_tip`) ✓
   - mixed-hash push fails closed (sha256→sha1 exit **128**); same-hash exit **0** ✓
   - replay rebuilds `accepted_head` byte-identically from the Tape alone (digests recomputed) ✓
   - exactly two `refs/turingos/*`, no `authorization_head` ✓
2. **S-2 PRE green** — `evidence/stage0/s2_result.json`, ALL_PASS=true:
   - only current writer's FF append admits; wrong-writer + non-FF rejected by the GUARD ✓
   - `HandoffGenerated` Tape event changes who the guard treats as writer; old writer then rejected ✓
   - no epoch/lease/fencing field required ✓
3. **B-1…B-5 contracts written, versioned, ASCII-key validated** — `contracts/` (8 files) + `docs/adr/` (8 ADRs).
   `MANIFEST.sha256` recorded for every spike artifact (this dir).

## Contracts frozen (the small baseline)
B-1 two refs (`refs.md`) · B-2 append envelope (`append_envelope.md`) · B-3 18-event registry
(`event_registry.{json,md}`) · B-4 predicate set (`predicate_set.md`) · B-5 capsule+receipt schemas
(`capsule.schema.json`,`receipt.schema.json`) · codec policy (`codec_policy.md`) · ApprovalCard
(`approval_card.md`) · frozen interfaces (`INTERFACES.md`). ADRs: 0001–0007 + ADR-WORKER-001.

## Notes
- Spikes are throwaway PRE probes on scratch repos (`/tmp/turingos_s1`, `/tmp/turingos_s2`); the GATE
  versions (S-1, S-3, S-7…) re-run on the REAL Tape in later stages.
- No spike result converted to a score; nothing asserted-without-execution.
- Next: launch the foundation Workflow (MOD-CODEC, MOD-REGISTRY, MOD-TAPE, MOD-PREDICATE, MOD-EVIDENCE, MOD-REPLAY).
