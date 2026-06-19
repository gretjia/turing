# CLAUDE.md — TuringOS 1.0 build harness

## What this repo is
`/Users/zephryj/work/turing` is the **implementation** of TuringOS 1.0 — a sovereign, constitution-governed OS for code projects. We build the **Minimum Complete Loop**: a *constitution-compatible PARTIAL realization*, P0-only (private local dogfood). **The plan is the spec; the constitution is root law.** Build it **AGI-like** — predicate-first, evidence-on-tape, Verifier ≠ Implementer, no shortcuts in the substrate.

## Authority (read order — highest wins)
1. **Constitution** (root law; human-`sudo`-only): `/Users/zephryj/work/turingos_research/Reference Docs/Turingos宪法.md`
2. **The finalized plan** (build spec): `/Users/zephryj/work/turingos_research/TURINGOS_1_0_PLAN/`
   - `TURINGOS_1_0_CORE_PROJECT_PLAN.md` (§0–9) · App. **A** governance · **B** the loop + 7 slices · **C** state model + 18-event registry · **D** atom backlog (M0–M4) · **E** targeted spikes
3. This repo's **ADRs / registries / schemas** — *project contracts, subordinate to the constitution*.

Where the plan and any older doc or skill checklist differ, **the plan governs** (e.g. identity prefix is ASCII `mu:` not Greek `μ:`; `accepted_head` advances **only** on a `SOVEREIGN_ACCEPT` event with a deterministic Predicate PASS).

## How we build — loop + workflow (the smart harness)
- **Every unit of work runs through `/Loop`** (installed system skill): route → **predicate-first** → execute → verify → IPQC → ship gate. **No IMPLEMENT before `PREDICATE.md` + frozen `acceptance_commands`.** On gate fail: one targeted rework + a rule to `LESSONS.md`; escalate on the second fail. `/PlanLoop` and `/TuringLoop` redirect to the same skill (`~/.claude/skills/loop`).
- **Inside a module, use the Workflow tool** to fan out **multi-agents**: implement the module's atoms in parallel (each atom in its own worktree, predicate-first, only `allowed_files`), then a **second adversarial stage of ship-gate auditors** — **Verifier ≠ Implementer** — that run the atom `acceptance_commands`, the IPQC checklist (`~/.claude/skills/loop/references/turing/ipqc-checklist.md`), and the constitution-slice checks. A finding kills the atom until fixed.
- **The orchestrator (you) drives module-by-module and *decides the QC interval*** from real project needs. IPQC cadence during implement: `bash ~/.claude/skills/loop/scripts/calc-ipqc-interval.sh <eta_steps> <failure_rate>` (= `max(3, round(eta·0.12/(1+rate)))`). Intermediate QC **between** modules is orchestrator-chosen — **not necessarily every module**; insert one after a module with reworks, chain clean modules. The loop skill has the QC concept built in — lean on it; don't over-QC.
- **Invoke the loop harness by path, not by slash** (`~/.claude/skills/loop/SKILL.md` + `scripts/route.py`) — Claude Code's built-in `/loop` is a *different* (recurring-runner) command; don't conflate them.

## Autonomous operation (one prompt, unattended)
This build runs **end-to-end from a single prompt, hands-off**. The orchestrator:
- **Never asks the human for routing inputs** — self-estimate ETA from atom counts; force `plan_depth = none` for execution (the finalized plan *is* the approved canonical proposal — write only per-module `CONTEXT.md` + `PREDICATE.md`, no debate, no approval step); log routing to `routing_decision.json` / `PROGRESS.md` instead of "telling the user."
- **Chains continuously, never idles** — each module runs as a background **Workflow**; on completion the orchestrator auto-continues to the next. **Never end a turn idle while the build is incomplete** — always have a workflow in flight or be actively working; if you must pause, spawn the next module's workflow *first*.
- **Self-approves ordinary execution** — atom batches that stay inside the ratified module contract (no `does_not_own` change, no Goal-Amendment trigger, App. A / plan Q10) are the Planner's domain and proceed without the human. Only a **real Goal-Amendment trigger** or a **credentialed gate** may stop the run.
- **Survives context limits** — keep `PROGRESS.md` (the build ledger: modules shipped, current module, open lessons, next action) + a horizon `state/` tree; **on any compaction or restart, resume from `PROGRESS.md`** — never restart from scratch.
- **Skip-and-log hard gates** — a step needing human credentials/decision (QB-2 real-vendor worker, QB-3 keyring secrets, QB-4 real signing, live GitHub) is written to `BLOCKED.md` and **skipped**; continue with every other buildable module; stop only when nothing buildable remains.
- **Stops only** at (a) the milestone — full locally-buildable scope + the fake/manual-worker full-loop E2E + replay/handoff green; or (b) nothing buildable remains — then write the final report. **Discipline is never traded for speed:** predicate-first, Verifier ≠ Implementer, failure-on-tape always hold.

> **Run mode:** for true hands-off operation the session must be launched in an **auto-approve / unattended permission mode** (else tool calls prompt). The build is otherwise self-driving.

## Build sequence (App. C / D)
**Stage 0 — FREEZE the small baseline** (project contracts in `contracts/`): the **2 refs**, the **7-field append envelope** (5 load-bearing in 1.0), the **18 provisional events**, the **deterministic predicate set**, the capsule + receipt schemas, the JCS+ASCII codec policy. Run the **PRE spikes** (App. E: S-1 SHA-256 2-ref tape + failure-is-state; S-2 one-writer handoff) before building on the substrate.
Then implement modules **M0 → M4 first** (fully atomized in App. D); **M5 → M12 later** as contract + ship-gate + expansion only (progressive elaboration — never all atoms up front).
`M0` Constitutional Contracts & Baseline · `M1` Canonical Codec/Identity · `M2` Micro Git ChainTape & 2 Refs · `M3` Event Registry/Predicate Kernel · `M4` Evidence Store/Replay · … `M12` E2E Qualification.

## Load-bearing invariants (what IPQC + ship-gates check)
- **Tape-Canonical** [Art. 0.2] — all 1.0 state rebuildable from the Micro Tape; projection / SQLite / TUI are **derived only**.
- **Failure-is-state** [Art. 0.3] — every sovereignty-boundary change = one Micro Git commit; failure commits too; `tape_tip` moves, `accepted_head` does **not**.
- **2 refs** — `refs/turingos/tape_tip` + `refs/turingos/accepted_head` (`HEAD_t = accepted_head`); **no `authorization_head`** in 1.0 (ordinary authorization is a PRESERVE Tape event).
- **One active sovereign writer** + read-only observers + explicit handoff (multi-writer deferred; interface kept open).
- **Deterministic Predicate only** [Art. I.1] — schema / parent-tip (FF-only) / scope / worktree isolation / receipt hash / declared tests / Macro anchor / replay equality / advance rule. **Quality, UI, taste are RiskFindings or human review — never a Predicate.**
- **Broadcast + Shield** [Art. II/III] — raw failure → private evidence → FailureClass → abstract rule → inject **only** the relevant rule into the next capsule (PRESERVE/derived; moves no head).
- **WorkGraph = derived projection** of serialized `q_t` + tape + declared Macro observations (**not** `q_t`).
- **ASCII-only load-bearing keys**, one RFC-8785 JCS codec, no floats — a *codec policy* (changing it is a project ADR + schema migration, **not** a constitution amendment).
- **Governance** — project spec / registry / schemas / codec & evidence policy are **project contracts subordinate to the constitution**; **ArchitectAI/Veto-AI are deferred to 2.0** — in 1.0 an architecture change uses a **manual ADR + a constitution-only audit**. The constitution changes by **human sudo only**.

## Forbidden — the 临时违宪 release audit (never commit these)
failure off-Tape · projection as hidden truth · blackbox bypassing the Predicate · accepted state not rebuildable from Tape · natural-language faking a hard gate · overwriting/deleting history for convenience · mistaking project Spec for the constitution.

## Conventions
- This repo is a normal git repo (the build). The **TuringOS Micro Tape is a *separate* native-SHA-256 git repo** the code manages — never confuse the two.
- Each atom: own worktree · predicate-first · frozen `acceptance_commands` · evidence on disk with `sha256` in a `MANIFEST.sha256`.
- ADRs → `docs/adr/`. Frozen project contracts (registries/schemas) → `contracts/`. Code → `src/`, tests → `tests/`.
- **Source control:** commit to *this* repo's git after Stage 0 and after each shipped module, then `git push origin main`. Public remote = **`github.com/gretjia/turing`** (`origin`, HTTPS, `gh`-authenticated). **Never push the TuringOS Micro Tape repo to a forge** — it is a separate private SHA-256 repo.
- **Honesty:** declare unimplemented scope; BLOCKED stays BLOCKED; never narrate a result you didn't produce.
