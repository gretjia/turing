# PREDICATE — Foundation module (the substrate kernel) ship gate

**Module:** Foundation = MOD-CODEC · MOD-REGISTRY · MOD-TAPE · MOD-PREDICATE · MOD-EVIDENCE · MOD-REPLAY
(+ support: errors, envelope, schemas, reduce). **CONTEXT/glossary:** `contracts/INTERFACES.md` (frozen API).
**No IMPLEMENT before this gate + acceptance_commands are frozen.** predicate-first.

## What "shipped" means (all must hold)
The foundation realizes the Tape substrate + deterministic predicate kernel exactly per the frozen contracts,
and the GATE versions of S-1/S-3(partial)/S-7(partial) pass on the **real** kernel (not the scratch spikes).

## acceptance_commands (frozen — the gate; re-run every build)
```bash
# 1. all foundation unit tests pass (stdlib unittest — hermetic, no third-party dep)
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
# 2. real-Tape kernel integration smoke (S-1 GATE on the real kernel)
PYTHONPATH=src python3 -m turingos.cli tape-init /tmp/tos_fnd_tape
PYTHONPATH=src python3 tests/integration/kernel_smoke.py   # init->append(boot,fail,accept)->replay; asserts below
```
**Test framework:** stdlib `unittest` (NOT pytest — pytest is not installed; the kernel stays dependency-free).

## Mechanical assertions the gate proves (S-1/S-3/S-7 recalibrated to the real kernel)
1. **codec determinism** — `content_digest(p)` byte-stable across calls; ascii-key guard raises on non-ASCII
   load-bearing key; no-float guard raises on any float; `event_id` matches `^mu:[0-9a-f]{64}$`.
2. **registry closed-world** — `is_known('Nope') == False`; `head_effect` is registry-derived; the carried
   `head_effect` disagreeing with `registry[type].class` is rejected at append.
3. **tape substrate** — `object_format()=='sha256'`; FF-only append; one commit per event; **FailureNode
   advances `tape_tip` only, NOT `accepted_head`** (failure-is-state); **CandidateAccepted (predicate PASS)
   advances `accepted_head`==`tape_tip`**; exactly two `refs/turingos/*`, no `authorization_head`.
4. **single-writer guard** — wrong-writer append + non-FF append are **rejected by the guard** (raise
   GuardReject, no commit); `handoff()` emits HandoffGenerated and changes `current_writer`.
5. **predicate determinism + correctness** — `evaluate(...)` twice on identical inputs → identical
   `passed` AND identical `reason_digest`; each negative case (receipt-hash mutate, scope violation,
   isolation violation, anchor mismatch, test-fail, ascii-key) FAILs with the **correct reason_code**;
   **no quality/taste/UI check anywhere** in the predicate; PASS emits accept event + advance, FAIL emits FailureNode.
6. **replay equality (S-7 partial)** — `replay(tape)` rebuilds `accepted_head` == on-disk, consulting the
   **Tape only** (delete any projection cache → identical result); two replays byte-identical; `q_t` rebuilt;
   `make_handoff_bundle` + `replay_from_handoff` reproduce the same accepted state; emits ReplayVerified.
7. **forbidden-pattern clean** — no failure off-Tape; no projection-as-truth (WorkGraph/q_t derived, conservation
   holds); no predicate bypass; accepted state rebuildable from Tape; no NL gate; append-only/FF-only (no
   history overwrite); contracts treated as subordinate to the constitution.

## On gate fail
One targeted rework + a rule to LESSONS.md; escalate (log to PROGRESS + BLOCKED if structural) on second fail.
Verifier ≠ Implementer: the auditor that runs this gate is never the agent that wrote the module.
