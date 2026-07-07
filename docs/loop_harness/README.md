# Loop Harness — TuringOS-native reference (HW-SW-002 B4)

This is the canonical harness reference for this repo. It documents the
TuringOS-native IPQC formula, the checkpoint calculator that implements it,
the AgenticForgeLoop v1.4 autonomy tiers and 8-step cycle, and the
ready-block shape emitted at loop exit.

**Supersession note (founder instruction, 2026-07-03):** do NOT use
`.grok/skills/**`. Harness docs for this repository live at
`docs/loop_harness/` (this file), and the IPQC calculator lives at
`scripts/calc-ipqc-interval.sh`. The unified `loop` skill (v2.0) is the
single harness entrance; roadmap references to `.grok/skills/**` are
superseded by it.

## Canonical TuringOS IPQC formula

```
ipqc_interval = max(25, floor(eta_steps * (0.15 - min(0.10, failure_rate))))
```

Implemented exactly by `scripts/calc-ipqc-interval.sh` (integer/fixed-point
math only — no floating-point rounding):

```
scripts/calc-ipqc-interval.sh <eta_steps> <failure_rate>
```

This formula is distinct from the harness-internal checkpoint formula used
by the unified `loop` skill's own `scripts/calc-ipqc-interval.sh`
(`max(3, round(eta * 0.12 / (1 + failure_rate)))`) — the two live at
different scopes and must not be confused. The formula above is the
roadmap/TuringOS-native contract that this repository's audits bind to.

## Autonomy tiers (Tier 0–4) and high_risk downgrade

| Tier | Behavior |
|------|----------|
| Tier 0 | Human confirms every step |
| Tier 1 | Auto-runs unit tests |
| Tier 2 | Auto-commits drafts; human approves each propose |
| Tier 3 (default) | Agent capsule auto_execute; Autonomy >= 50% auto-dispatches Worker |
| Tier 4 | All proposes auto-approved (mock/CI only) |

Long-horizon tasks start at **Tier 3**. `high_risk: true` downgrades the run
to **Tier 1** for that atom/phase.

## The v1.4 8-step list (AgenticForgeLoop)

The 8-step core loop is fixed; TestForge and BestPractice-Alignment are
embedded sub-tools, not extra nodes:

1. **INTENT** — instantiate TaskCapsule (frontier_mode, test_mode,
   alignment_topics); parse ETA -> eta_steps; decide human_ux_gate.
2. **PLAN** (+ mandatory `fresh_bp` unless `frontier_mode: off`) — write
   acceptance_commands before code; write allowed/forbidden files; compute
   the IPQC interval via `scripts/calc-ipqc-interval.sh`.
3. **IMPLEMENT** — surgical changes to allowed_files only; IPQC ticks may
   trigger TestForge(mode=ipqc).
4. **SIMPLIFY** (+ mandatory `fresh_bp`) — delete redundancy without
   changing acceptance semantics.
5. **VERIFY / IPQC** — TestForge(mode=standard) is the primary gate;
   Verifier != Implementer; failure increments failure_rate and triggers
   Mini-Recovery.
6. **REFLECT** (+ mandatory `fresh_bp`) — extract `rules_learned` from
   TestForge passes; update autonomy estimate.
7. **SHIP** — requires a recent TestForge standard pass plus shipgate
   evidence.
8. **HANDOFF** — emit the ready-block (see below) and clean up.

Mini-Recovery (triggered by TestForge/IPQC/VERIFY failure): 3-why root
cause -> targeted fix + mandatory Simplifier pass -> burst verification
(TestForge selfheal) -> merge the rule into `rules_learned`, then resume the
main loop. Escalate to a human on 2x Mini-Recovery failure, `high_risk`, or
any Charter-invariant risk.

## Ready-block shape

The "ready-block" is the structured block that launches the NEXT atom, in the
exact shape locked by the secure OS roadmap (docs/roadmap/secure_os_18_month/,
spec §8: every phase ends with one):

```text
Activate AgenticForgeLoop v1.4 / TuringLoop
Task: <phase/atom task>
ETA estimate: <hours / steps>
frontier_mode: auto
test_mode: auto_full
Start at autonomy tier <tier>
human_ux_gate: <true|false>
allowed_files:
  - <paths>
acceptance_commands:
  - <commands>
next_atom ID: <ID>
```

At loop exit the run also emits status evidence, in two layers:

- **Routing/gate layer** (unified `loop` v2.0, Step 3 Exit): write
  `routing_decision.json` + `timing.json` + a gate receipt; the HANDOFF
  message states the `path` taken and whether escalation triggered.
- **TaskCapsule HANDOFF layer** (AgenticForgeLoop v1.4, Step 8): a YAML
  block with this shape:

```yaml
handoff:
  branch: <target branch>
  commit_sha: <sha>
  pr_url: <url>
  freshness_delta: "<e.g. 3 new SOTA practices applied>"
  test_summary: "<e.g. IPQC + N journeys PASS | M new test rules extracted>"
  new_rules_added: <int>
  autonomy_achieved: <0-100%>
  failure_rate: <float>
  rules_learned: []
  open_risks: []
  index_updated: <true if HARNESS_INDEX.md synced>
next_recommended_atom: <id or "done">
```

A ready-block is only valid once every step in the checklist above has run
(or was explicitly skipped by a documented predicate) and the acceptance
commands for the atom/phase all exit 0.

## Substrate freeze pre-commit hook (HW-SW-003)

This repo ships a pre-commit hook (`.githooks/pre-commit`) that runs the
forbidden-file guard and the substrate freeze audit before every commit.
Enable it once per clone with:

```
git config core.hooksPath .githooks
```
