# TuringOS 1.0 — the Minimum Complete Loop

A sovereign, constitution-governed OS for code projects. TuringOS boots a real project, drives a
**replaceable AI Worker** through it under a **deterministic Predicate**, records every decision — including
every failure — on an **append-only SHA-256 Micro Git ChainTape** that **replays byte-for-byte**, and hands
the project off cleanly. Projection / SQLite / TUI are *derived views only*; the Tape is the single truth.

> **Status: TuringOS 1.0 is COMPLETE — all 4 stages shipped.** 386 unit tests pass; every targeted spike
> (S-1…S-7) is green on real artifacts; the loop has been dogfooded with real Worker CLIs + a real GitHub
> PR/CI round-trip. Built autonomously, predicate-first, Verifier ≠ Implementer, failure-on-tape.

---

## 🚦 Start here (resume from a new context)

**Read in this order — highest authority wins:**
1. **`PROGRESS.md`** — the durable build ledger (current status, what shipped, next action). *Always read first.*
2. **`CLAUDE.md`** — the build harness rules (loop + Workflow, autonomous operation, invariants).
3. **`MILESTONE_REPORT.md`** — the full final report (what was built, evidence, roadmap).
4. **Root law (external):** the constitution — `/Users/zephryj/work/turingos_research/Reference Docs/Turingos宪法.md`
5. **The spec (external):** `/Users/zephryj/work/turingos_research/TURINGOS_1_0_PLAN/` (plan + appendices A–E).
6. **Project contracts:** `contracts/` (frozen; `contracts/INTERFACES.md` is the API glossary) and `docs/adr/`.

**Authority order:** constitution › the finalized plan › this repo's ADRs/contracts. Where they differ, the
plan governs; the constitution is amended by human `sudo` only.

> Any further work resumes from `PROGRESS.md` — **never restart from zero.** New units of work go through the
> loop harness (`~/.claude/skills/loop/`) predicate-first, with an adversarial ship-gate (Verifier ≠ Implementer).

---

## ✅ Test it yourself

```bash
cd /Users/zephryj/work/turing            # all commands are stdlib-only; prefix PYTHONPATH=src
# (or once:  pip install -e .  → then the `turingos` command works without PYTHONPATH)

# Level 1 — deterministic gates (no AI, no GitHub, free)
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'   # 386 tests
PYTHONPATH=src python3 tests/integration/kernel_smoke.py             # substrate: 2 refs, failure-is-state, replay
PYTHONPATH=src python3 tests/integration/loop_e2e.py                 # full fake-worker loop, both predicate branches

# Level 2 — drive the loop + inspect the real Micro Tape (fake worker, free)
echo '{"project_id":"demo","goal":"try the loop","writer_id":"W1","modules":[{"module_id":"m1","intent":"demo"}]}' > /tmp/spec.json
PYTHONPATH=src python3 -m turingos.cli loop --spec /tmp/spec.json --tape /tmp/t
PYTHONPATH=src python3 -m turingos.cli panorama --tape /tmp/t        # q_t + Authorized-vs-Accepted
git -C /tmp/t for-each-ref refs/turingos/                            # exactly tape_tip + accepted_head
git -C /tmp/t log --oneline refs/turingos/tape_tip                  # every event = one commit (incl. failures)

# Level 3 — real workers at the router's fast tier (costs a little; needs the CLIs logged in)
PYTHONPATH=src python3 evidence/stage2/s6_gate.py                    # one capsule -> claude+codex+agy, isolated
PYTHONPATH=src python3 evidence/stage3/dogfood.py                    # full loop, real workers, first-attempt pass rate
PYTHONPATH=src python3 tools/try_atom.py --worker claude --file mathx.py \
  --intent "Create mathx.py with is_prime(n)" \
  --accept "python3 -c \"import mathx; assert mathx.is_prime(7) and not mathx.is_prime(8)\""

# Level 4 — GitHub PR/CI round-trip on a disposable repo (needs gh auth + delete_repo scope)
PYTHONPATH=src python3 evidence/stage2/s5_github.py
```

---

## The loop (what it implements)

> BOOT/ADOPT → GoalState + Module Map → progressively expand the active Module into Atoms → build a **Shielded
> Work Capsule** → dispatch a **replaceable Worker** (isolated worktree) → import Receipt + Macro Git anchor →
> **deterministic Predicate** → { FAIL → `FailureNode` on Tape → classify → shielded retry | PASS →
> `CandidateAccepted` → `accepted_head` FF-advance } → re-reduce WorkGraph → Goal-first Panorama → Replay/Handoff.

A complete Turing-machine step: **Read → Propose → Verify → Append(Failure|Accepted) → Reduce →
Broadcast/Shield → Continue|Halt.** Two refs only (`tape_tip` + `accepted_head`); one active sovereign writer
+ explicit handoff; `accepted_head` advances *only* on a `SOVEREIGN_ACCEPT` event with a Predicate PASS.

## Repo map
| Path | What |
|---|---|
| `src/turingos/` | the kernel: `codec` (jcs.v1) · `registry` (18 events) · `tape` (SHA-256, 2 refs, guard) · `predicate` (9 mechanical checks) · `evidence` · `replay` · `reduce` · `boot` · `planner` · `capsule` (+ FailureMemory shield) · `signing` · `explore` · `panorama` · `loop` · `dispatch_router` (cost/effort) · `macro` (GitHub) · `worker/` (adapter + FakeWorker + CliWorkerAdapter) · `cli` |
| `contracts/` | frozen project contracts (the 2 refs, append envelope, 18-event registry, predicate set, capsule/receipt schemas, codec policy, ApprovalCard, **INTERFACES.md**) |
| `docs/adr/` | ADRs 0001–0008 + ADR-WORKER-001 |
| `tests/` | unit tests (stdlib `unittest`) + `tests/integration/` gates |
| `evidence/stage{0,foundation,1,2,3}/` | spike scripts, results, Shipgate receipts, `MANIFEST.sha256` |
| `tools/try_atom.py` | run one real atom through the loop with a chosen worker/tier |
| `PROGRESS.md` · `LESSONS.md` · `BLOCKED.md` · `MILESTONE_REPORT.md` | ledger · rules learned · gates · final report |

## Workers & cost (ADR-0008)
Real adapters: **claude · codex · agy · grok**, invoked headless one-shot (`-p`/`exec`), each in an isolated
worktree. The **smart dispatch router** (`dispatch_router.py`) picks model + thinking effort **per task, fast
by default** (claude sonnet/low · codex `model_reasoning_effort=low` · agy Gemini-Flash-Low · grok
composer-fast/low), escalating only on risk/breadth/retry — so a `-p` call never silently runs the operator's
expensive default (e.g. opus-4.8 xhigh). Worker quality is **not** load-bearing: the Predicate gates every
accept, so a cheap miss fails-on-Tape and escalates rather than corrupting accepted state.

## Honest scope (1.0 partial realization — DEFERRED ≠ rejected)
1.0 is a constitution-compatible partial realization. Deferred to 1.x/2.0/3.0 (each behind an open seam):
OS-keyring/hardware signing · the 3rd ref `authorization_head` · concurrent multi-writer + epoch/lease/fencing
· the Agent Protocol server · the full 46-event registry · AES evidence store + retention matrix · a 2nd
renderer · ArchitectAI/Veto-AI (the meta loop). None of the seven 临时违宪 anti-patterns is present.

**Residual:** `gh repo delete` needs the `delete_repo` token scope; without it disposable repos are archived.

---
*Conventions:* this git repo is the **build**; the TuringOS **Micro Tape** is a *separate* native-SHA-256 git
repo the code manages (never pushed to a forge). Commit + push after each shipped module. Generated by Claude Code.
