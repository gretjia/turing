# C1 — Turing-Completeness Under Governance: Reduction Proof Note

**Certificate:** C1 (RES_AOC_preagi_certification_ladder.md §C1)
**Atom:** C1.a — the mechanized Turing-completeness reduction
**Claim (honest phrasing):** *The TuringOS kernel loop is Turing-complete up to
bounded storage, under governance.*
**Status:** Implementer ceiling `ADDRESSED`. Artifact 1 (this note) + the mechanized
core (`lean/Reduction.lean`). Artifact 2 (the executable Rule-110 / small-TM witness
that replay-verifies from genesis) is a separate deliverable and is *out of scope for
this note*; the boundary section states exactly what this note does and does not
establish.

---

## 1. The reduction in one paragraph

A Turing machine is the tuple `M = (Q, Γ, δ, q0, ...)` evolving a configuration
`⟨q, HEAD, tape⟩` by a transition function `δ`. The TuringOS kernel evolves a
version-control triple `Q_t = ⟨q_t, HEAD_t, tape_t⟩` (constitution Art. 0.1 / Art. IV
flowchart, lines 587–619) by a *governed* step: a black-box worker proposes an output,
a white-box predicate product `∏p` verifies it against frozen tape bytes, and the
sovereign truth advances **iff** `∏p = 1`, otherwise `Q_{t+1} = Q_t`. We show this
governed step is a faithful implementation of `δ`: for any transition function `f`, a
correct worker (`δ`) whose candidate the predicate accepts drives *exactly one* `f`-step,
and `N` governed steps reproduce `fᴺ`. Instantiating `f` with the step function of a
**universal cyclic tag system** (Cook 2004 / Neary–Woods 2006 — the same reduction that
makes Rule 110 universal) yields: the governed machine computes anything a Turing
machine can, bounded only by physical storage. Governance therefore costs
*verification, not expressiveness*.

---

## 2. The four-element mapping (Turing 1948 → TuringOS → code)

Constitution Art. 0.1 fixes the mapping; we formalize it against the live code.

| Turing machine | TuringOS kernel | Implementation anchor |
|---|---|---|
| State `q ∈ Q` | `q_t`, carried as the *accepted config* — the payload of the latest PASSed `SOVEREIGN_ACCEPT` event on the `accepted_head` chain | `crates/turing-contracts/src/envelope.rs` `HeadSet.accepted_head` |
| Tape `tape` | MicroTape — the append-only Git commit chain (`refs/turingos/tape_tip`) | `crates/turing-git-tape/` ; `crates/turing-loop/src/lib.rs::rtool::read_q` |
| Head `HEAD` | `HEAD_t` — the sovereign ref triple `⟨tape_tip, authorization_head, accepted_head⟩` | `envelope.rs::HeadSet` ; `head_set.rs` (torn-read-defended read) |
| Transition `δ` | worker **proposal** (the black-box δ), *gated* by `∏p` | `crates/turing-loop/src/lib.rs::tick` ; gate in `crates/turing-kernel/src/reducer.rs::apply` |

The load-bearing subtlety is **which head is `q_t`**. The kernel keeps three refs.
`tape_tip` advances on *every* append (including failures — "failure is state"), so it is
not the computational state. `accepted_head` advances *only* on a verified transition and
is the **truth**. Reading `reducer::apply` (lines 116–160):

```
advancing      = (head_effect == ADVANCE) ∧ (product == PASS)
accepted_head' = new_event_oid              if advancing ∧ class == SOVEREIGN_ACCEPT
               = accepted_head (unchanged)   otherwise
```

So the TM state advances **iff** `class = SOVEREIGN_ACCEPT ∧ head_effect = ADVANCE ∧
∏p = PASS`, and on any failure it is carried forward unchanged. That is exactly the
constitution's `Q_{t+1} = wtool(output)` on `∏p = 1`, `Q_{t+1} = Q_t` on `∏p = 0`.
This boolean is reproduced verbatim in Lean as `acceptedAdvances` and its transition as
`acceptedAfter`.

---

## 3. The governed step as a transition function

Model the computational state abstractly as `σ` (for the TM configuration it is
`⟨q, HEAD, tape⟩`; for the universal target below it is a `CTConfig`). One governed tick
at a `SOVEREIGN_ACCEPT`/`ADVANCE` event is (`Reduction.lean §3`):

```
tick worker predicate q
  = acceptedAfter SOVEREIGN_ACCEPT ADVANCE (predicate q (worker q)) q (worker q)
  = if (predicate q (worker q) = PASS) then (worker q) else q
```

- `worker : σ → σ` is the black-box middle layer (an LLM, a swarm, anything) proposing
  the next configuration. **Faithful** means `worker = f`, the intended transition.
- `predicate : σ → σ → Product` is the white-box gate over frozen bytes. **Sound** means
  it PASSes the correct candidate `f q` and FAILs everything else
  (`soundPredicate f q cand := if cand = f q then PASS else FAIL` — the ladder's
  "predicate that validates the local rule application").

Three machine-checked facts pin down the step:

- **`tick_faithful_all`** — a faithful worker + a predicate that PASSes `f q` gives
  `tick f predicate q = f q`: one governed tick = one `δ`-step.
- **`tick_reject_stutter`** — if the predicate does *not* PASS the candidate, then
  `tick worker predicate q = q`: a wrong or lying worker cannot move the truth (this is
  the mechanized form of "no unverified state advance").
- **`acceptedAfter_fail_preserves`** — the constitution Art. 0.1 invariant itself:
  for *any* class and head effect, a non-PASS product yields `Q_{t+1} = Q_t`.

---

## 4. The reduction: whole-run faithfulness

Let `iterate g n` denote `gⁿ`. The reduction theorem (`run_faithful`, by induction on
`n`, machine-checked, `sorry`-free) is:

> For any transition `f` and any predicate that PASSes each correct candidate `f q`,
> `iterate (tick f predicate) n q = iterate f n q` for all `n, q`.

I.e. **the governed machine's `n`-step evolution equals the ungoverned model's `n`-step
evolution, exactly** — governance changes *how* each step is licensed (a verification
gate) but not *what* is computed. The gate is a filter on the *worker*, not a restriction
on the *reachable computations*: any computable transition can be proposed and, once
verified, is faithfully applied.

---

## 5. Universality: the cyclic tag system target

To land the universality claim we pick the lightest universal model, matching Rule 110's
own proof route. A **cyclic tag system** (`CTConfig = ⟨marker, data⟩`, fixed cyclic
production list `prods`) steps by: pop the front symbol; on `1` append the current
production; advance the marker cyclically (`ctStep`, `Reduction.lean §5`). The
development:

- **defines** `ctStep` concretely and **executes** it on concrete inputs, checked by
  `rfl` (discard-on-`0`, copy-on-`1` — the copying is the engine of universality — and a
  two-production cyclic run);
- **instantiates** the reduction at `f = ctStep prods`: `governed_simulates_cts` proves
  the governed machine with the *sound* predicate reproduces the cyclic tag system's
  evolution step-for-step, for every `n` and every start config, with a concrete
  3-step governed-vs-pure witness also checked;
- **imports** the external universality theorem as a single, clearly-marked axiom
  `exists_universal_cts` (§6 boundary) and concludes `governed_machine_universal`:
  there is a universal cyclic tag system whose evolution the governed truth head
  reproduces exactly.

---

## 6. Boundary: proven vs. assumed (the scope statement)

Per the ladder's scope-statement discipline (seL4/SOC-2 lesson: verify the narrow gate
surface, disclose the rest), here is the exact line.

**Machine-checked in `Reduction.lean` (`sorry`-free; `#print axioms` shows only
`propext`, Lean's standard propositional-extensionality axiom — no `sorryAx`, no
`Classical.choice`, no domain axioms):**

1. The gate law `acceptedAdvances` — truth advances iff `SOVEREIGN_ACCEPT ∧ ADVANCE ∧
   PASS` — is a faithful model of `reducer::apply`'s `accepted_head` branch
   (`acceptedAdvances_requires_sovereign`, `acceptedAdvances_not_pass`).
2. Gate-failure preservation `Q_{t+1} = Q_t` for every class/effect on non-PASS
   (`acceptedAfter_fail_preserves`) — constitution Art. 0.1, mechanized.
3. Faithful one-step simulation (`tick_faithful_all`) and the wrong-worker stutter
   safety companion (`tick_reject_stutter`).
4. The reduction: governed `n`-step evolution = pure `n`-step evolution
   (`run_faithful`), and its instantiation to cyclic tag systems
   (`governed_simulates_cts`), with concrete executed witnesses.

**Stated-as-assumption (imported, not re-derived):**

- **`exists_universal_cts`** — that *some* cyclic tag system is computationally universal.
  This is Cook (2004) / Neary–Woods (2006), the reduction underlying Rule 110's
  universality. It is a decades-established mathematical theorem whose full mechanization
  is a multi-year effort (cf. Wolfram's 2,3-machine prize dispute over "weak
  universality") — outside this certificate's boundary. It appears in the code as one
  explicit `axiom` and is the *only* domain assumption the main theorem depends on
  (verified: `governed_machine_universal` depends on `[propext, exists_universal_cts]`).
- **Bounded storage.** Physical MicroTape is a finite set of Git objects. All physical
  systems are finite-memory; the honest claim is therefore "Turing-complete **up to
  bounded storage**", never unqualified "can compute anything".
- **Above-the-gate harnesses are OUTSIDE the boundary.** The worker (LLM/swarm), the
  market layer, the facilitator, and Boltzmann routing are the black box `δ`. We model
  only the *governed relay*: the gate faithfully applies a correct proposal (PASS) and
  preserves the truth on anything else (FAIL/NOT_RUN). We prove nothing about, and rely
  on nothing from, worker internals — that is the point: universality of the *substrate*
  does not depend on the intelligence of the worker.
- **Executable end-to-end witness (Artifact 2).** The claim that a concrete Rule-110 /
  small-TM run replay-verifies from genesis with an independently re-derived final hash
  is a *separate* deliverable. This note + Lean core establish the reduction; the
  executable witness is necessary-but-not-sufficient corroboration and is not asserted
  here.

**Measurement-ceiling disclosure.** This certificate establishes *computational
universality of the governed transition relation*. It does **not** establish liveness
(that a useful worker exists for a given task), performance, or that the deployed daemon
stack is bug-for-bug identical to the Lean model beyond the `accepted_head` gate slice
formalized here. The faithful-model claim is scoped to that slice; the reducer's
authority-epoch and authorization-head logic are modeled only insofar as they do not
move `accepted_head`.

---

## 7. Why this matters

The predicate gate is often read as a *restriction*. The reduction shows the opposite at
the level that counts: the gate constrains *which proposals become truth*, not *which
computations are expressible*. Any Turing computation can be run as a sequence of
governed `SOVEREIGN_ACCEPT` steps whose predicate validates each local transition. Price
is not truth; verification is not a computational ceiling. Governance buys auditable,
replayable, lie-proof state evolution at the cost of *verification work per step* — and
`run_faithful` proves that cost is paid without surrendering universality.

---

### Reproduce

```
cd certificates/c1_turing_completeness/lean
lake build          # → Build completed successfully (3 jobs).
# axiom audit:
echo 'import Reduction
#print axioms C1.governed_machine_universal
#print axioms C1.run_faithful' > Check.lean && lake env lean Check.lean && rm Check.lean
# → governed_machine_universal depends on: [propext, exists_universal_cts]
# → run_faithful               depends on: [propext]
```
