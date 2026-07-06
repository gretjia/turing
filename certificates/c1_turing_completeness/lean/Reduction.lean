/-
  C1 — Turing-completeness under governance: the mechanized reduction.

  This development formalizes the CORE claim of certificate C1 (RES_AOC ladder §C1,
  constitution Art. 0.1): the TuringOS kernel loop is Turing-complete *up to bounded
  storage, under governance*. It is deliberately self-contained (core Lean 4 only, no
  Mathlib) so `lake build` is fast and the trusted base is small.

  What is machine-checked here (all `sorry`-free):
    1. The gate law (`acceptedAfter`) is a faithful model of
       `turing-kernel::reducer::apply`, restricted to the sovereign truth head
       (`accepted_head` = the TM state Q_t). The truth head advances IFF
       `class = SOVEREIGN_ACCEPT ∧ head_effect = ADVANCE ∧ product = PASS`.
    2. Gate-failure preservation (constitution Art. 0.1): on any product ≠ PASS,
       Q_{t+1} = Q_t  (`acceptedAfter_fail_preserves`, `tick_reject_stutter`).
    3. Faithful one-step simulation: a correct worker (δ = the model's transition f)
       whose candidate the predicate PASSes drives exactly one f-step
       (`tick_faithful_all`).
    4. Faithful full-run simulation: N governed ticks reproduce f^N by induction
       (`run_faithful`). This is the reduction: governed evolution = pure evolution.
    5. A concrete universal target — a cyclic tag system (Rule 110's own proof
       route) — defined and executed, with the governed machine shown to reproduce
       its evolution step-for-step (`governed_simulates_cts`, concrete witnesses).

  What is STATED-AS-ASSUMPTION (imported, not re-derived — see PROOF_NOTE §Boundary):
    * `exists_universal_cts` : the external mathematical theorem that some cyclic tag
      system is computationally universal (Cook 2004 / Neary–Woods 2006, via Rule
      110). Re-proving Rule 110 universality is a multi-year effort outside this
      certificate's boundary; we cite it as an `axiom` and clearly mark it.
    * Bounded storage: physical Tape (Git objects) is finite — hence the honest
      qualifier "up to bounded storage".
    * Everything above the gate (worker LLMs, market, facilitator) is OUTSIDE the
      verified boundary; we model only that the gate faithfully relays a correct
      proposal (PASS) and preserves truth on anything else (FAIL/NOT_RUN).
-/

namespace C1

/-! ## 1. The frozen kernel vocabulary (mirrors `turing-contracts`) -/

/-- Predicate product ∏p over frozen Tape bytes.
    Mirrors `turing_contracts::envelope::PredicateProduct`. -/
inductive Product where
  | pass
  | fail
  | notRun
deriving DecidableEq, Repr

/-- Registry head-effect discriminator.
    Mirrors `turing_contracts::envelope::HeadEffect`. -/
inductive HeadEffect where
  | advance
  | preserve
deriving DecidableEq, Repr

/-- Event class. Mirrors `turing_contracts::registry::EventClass`. Only
    `sovereignAccept` may carry the computational truth (`accepted_head`). -/
inductive EventClass where
  | sovereignAccept
  | authorization
  | proposal
  | observation
  | receipt
  | failure
  | economy
deriving DecidableEq, Repr

/-! ## 2. The gate law (faithful model of `reducer::apply`, accepted-head slice)

`turing-kernel/src/reducer.rs` decides `accepted_head` by
`advancing = (head_effect == ADVANCE ∧ product == PASS)` and then
`accepted_head := new_oid` iff `advancing ∧ class == SovereignAccept`, else it is
carried forward. `acceptedAdvances` below is that exact boolean. -/

/-- Whether this transition advances the sovereign truth head (`accepted_head`).
    True iff SOVEREIGN_ACCEPT ∧ ADVANCE ∧ PASS — nothing else. -/
def acceptedAdvances : EventClass → HeadEffect → Product → Bool
  | EventClass.sovereignAccept, HeadEffect.advance, Product.pass => true
  | _, _, _ => false

/-- The truth-head transition over an abstract computation state `σ`.
    The accepted config becomes the candidate `cand` iff the gate opens; else the
    previous accepted config `prev` is carried forward (append-only: `tape_tip`
    still moves, but the *truth* does not). Mirrors the `accepted_head` branch of
    `HeadDecision` in `reducer::apply`. -/
def acceptedAfter {σ : Type} (cls : EventClass) (he : HeadEffect) (p : Product)
    (prev cand : σ) : σ :=
  cond (acceptedAdvances cls he p) cand prev

/-- Gate law, part 1: a non-PASS product opens no gate — for every class and head
    effect. This is the "verification, not expressiveness" invariant. -/
theorem acceptedAdvances_not_pass {cls he p} (hp : p ≠ Product.pass) :
    acceptedAdvances cls he p = false := by
  cases p with
  | pass => exact absurd rfl hp
  | fail => cases cls <;> cases he <;> rfl
  | notRun => cases cls <;> cases he <;> rfl

/-- Gate law, part 2: only SOVEREIGN_ACCEPT can ever advance the truth head. -/
theorem acceptedAdvances_requires_sovereign {cls he p}
    (h : acceptedAdvances cls he p = true) : cls = EventClass.sovereignAccept := by
  cases cls <;> cases he <;> cases p <;> simp_all [acceptedAdvances]

/-- **Constitution Art. 0.1, mechanized**: on gate failure (∏p ≠ 1), Q_{t+1} = Q_t.
    The candidate is discarded and the accepted truth is carried forward unchanged. -/
theorem acceptedAfter_fail_preserves {σ} {cls he p} (prev cand : σ)
    (hp : p ≠ Product.pass) :
    acceptedAfter cls he p prev cand = prev := by
  unfold acceptedAfter
  rw [acceptedAdvances_not_pass hp]
  rfl

/-! ## 3. One governed tick and the faithful-simulation lemma

A tick at a SOVEREIGN_ACCEPT / ADVANCE event: the black-box `worker` (δ) proposes a
candidate next config; the white-box `predicate` returns ∏p over the frozen candidate;
the truth advances iff PASS. This is exactly the constitution's
`Q_{t+1} = wtool(output)` on ∏p=1, `Q_{t+1}=Q_t` on ∏p=0. -/

/-- One governed step of the truth head at a SOVEREIGN_ACCEPT / ADVANCE event. -/
def tick {σ} (worker : σ → σ) (predicate : σ → σ → Product) (q : σ) : σ :=
  acceptedAfter EventClass.sovereignAccept HeadEffect.advance
    (predicate q (worker q)) q (worker q)

/-- If the predicate PASSes the correct candidate `f q`, one governed tick with a
    faithful worker (`worker = f`) equals exactly one model step `f q`. -/
theorem tick_faithful_all {σ} (f : σ → σ) (predicate : σ → σ → Product)
    (hsound : ∀ q, predicate q (f q) = Product.pass) (q : σ) :
    tick f predicate q = f q := by
  unfold tick acceptedAfter
  rw [hsound q]
  rfl

/-- Safety companion: if the predicate does NOT PASS the worker's candidate, the
    tick stutters — a lying/wrong worker cannot move the truth. -/
theorem tick_reject_stutter {σ} (worker : σ → σ) (predicate : σ → σ → Product) (q : σ)
    (hpred : predicate q (worker q) ≠ Product.pass) :
    tick worker predicate q = q := by
  unfold tick
  exact acceptedAfter_fail_preserves q (worker q) hpred

/-! ## 4. Full-run simulation: the reduction itself -/

/-- Iterated application, defined locally (no Mathlib). `iterate g n q = g^n q`. -/
def iterate {σ} (g : σ → σ) : Nat → σ → σ
  | 0,     q => q
  | n + 1, q => iterate g n (g q)

/-- **The reduction.** With a faithful worker and a predicate sound on the correct
    candidate, N governed ticks reproduce the model's N-step evolution exactly:
    governed evolution = pure evolution. Machine-checked by induction on N. -/
theorem run_faithful {σ} (f : σ → σ) (predicate : σ → σ → Product)
    (hsound : ∀ q, predicate q (f q) = Product.pass) :
    ∀ n q, iterate (tick f predicate) n q = iterate f n q := by
  intro n
  induction n with
  | zero => intro q; rfl
  | succ n ih =>
    intro q
    show iterate (tick f predicate) n (tick f predicate q) = iterate f n (f q)
    rw [tick_faithful_all f predicate hsound q]
    exact ih (f q)

/-! ## 5. A concrete universal target: cyclic tag systems (Rule 110's route)

A cyclic tag system has a fixed cyclic list of productions (`prods`), a data word
(`data`), and a marker cursor (`marker`). Each step: pop the front symbol; if it is
`1` (`true`), append the current production; the marker advances cyclically. Cyclic
tag systems are Turing-complete (Cook 2004; Neary–Woods 2006), the same machinery
that proves Rule 110 universal. -/

/-- A cyclic tag system configuration. `marker` cycles through the productions. -/
structure CTConfig where
  marker : Nat
  data   : List Bool
deriving DecidableEq, Repr

/-- One cyclic-tag-system step under a fixed production list `prods`.
    Empty data halts (fixed point). Otherwise pop the front symbol `b`; on `true`
    append production `prods[marker mod |prods|]`; advance the marker. -/
def ctStep (prods : List (List Bool)) (c : CTConfig) : CTConfig :=
  match c.data with
  | []          => c
  | b :: rest =>
    let m         := c.marker % prods.length
    let appendant := prods.getD m []
    let newData    := match b with
      | true  => rest ++ appendant
      | false => rest
    { marker := c.marker + 1, data := newData }

/-! ### Concrete executable witnesses (checked by `rfl`) -/

-- discard-on-0: the front `0` is consumed, nothing appended, marker advances.
example : ctStep [[true]] ⟨0, [false]⟩ = ⟨1, []⟩ := by rfl

-- copy-on-1: the production `[1,1]` is appended when the front symbol is `1`.
-- (This copying is the mechanism behind cyclic-tag universality.)
example : ctStep [[true, true]] ⟨0, [true]⟩ = ⟨1, [true, true]⟩ := by rfl

-- a two-step run cycles the marker across two distinct productions.
example :
    iterate (ctStep [[false], [true, false]]) 2 ⟨0, [true, true]⟩
      = ctStep [[false], [true, false]] (ctStep [[false], [true, false]] ⟨0, [true, true]⟩) := by
  rfl

/-! ## 6. Sound predicate + governed simulation of the universal target -/

/-- A concrete *sound* predicate: PASS iff the candidate equals the model step
    `f q` (the ladder's "a predicate that validates the local rule application").
    It PASSes the correct candidate and FAILs every wrong one. -/
def soundPredicate {σ} [DecidableEq σ] (f : σ → σ) : σ → σ → Product :=
  fun q cand => if cand = f q then Product.pass else Product.fail

theorem soundPredicate_pass {σ} [DecidableEq σ] (f : σ → σ) (q : σ) :
    soundPredicate f q (f q) = Product.pass := by
  unfold soundPredicate; rw [if_pos rfl]

theorem soundPredicate_reject {σ} [DecidableEq σ] (f : σ → σ) (q cand : σ)
    (h : cand ≠ f q) : soundPredicate f q cand = Product.fail := by
  unfold soundPredicate; rw [if_neg h]

/-- The governed machine reproduces a cyclic tag system's evolution step-for-step,
    for every N and every start config, using the genuinely sound predicate. -/
theorem governed_simulates_cts (prods : List (List Bool)) (n : Nat) (c0 : CTConfig) :
    iterate (tick (ctStep prods) (soundPredicate (ctStep prods))) n c0
      = iterate (ctStep prods) n c0 :=
  run_faithful (ctStep prods) (soundPredicate (ctStep prods))
    (soundPredicate_pass (ctStep prods)) n c0

-- concrete governed-vs-pure witness (checked, not assumed).
example :
    iterate (tick (ctStep [[true, true]]) (soundPredicate (ctStep [[true, true]]))) 3 ⟨0, [true]⟩
      = iterate (ctStep [[true, true]]) 3 ⟨0, [true]⟩ :=
  governed_simulates_cts [[true, true]] 3 ⟨0, [true]⟩

/-! ## 7. The main claim, up to the single cited external theorem -/

/-- `Universal f`: the transition system `(σ, f)` can simulate any state-transition
    system `(Q, tm)` under a faithful encode/decode, up to a bounded number `k` of
    micro-steps per simulated step. A clean formal proxy for "computationally
    universal / Turing-complete". -/
def Universal {σ : Type} (f : σ → σ) : Prop :=
  ∀ (Q : Type) (tm : Q → Q) (encode : Q → σ) (decode : σ → Q),
    (∀ q, decode (encode q) = q) →
    ∀ q, ∃ k, decode (iterate f k (encode q)) = tm q

/--
  CITED, NOT PROVED HERE (see PROOF_NOTE §Boundary). Cook (2004) and Neary–Woods
  (2006): some cyclic tag system is computationally universal — it simulates any
  Turing machine — which is precisely the reduction underlying Rule 110's
  universality. This development imports this single external fact as an axiom
  rather than re-deriving it (a multi-year formalization effort), and marks it
  explicitly as the boundary of the mechanized proof.
-/
axiom exists_universal_cts : ∃ prods : List (List Bool), Universal (ctStep prods)

/-- **C1 main theorem (up to bounded storage, under governance).** There is a
    universal cyclic tag system whose entire evolution the governed machine
    reproduces step-for-step under a sound predicate; hence governance costs
    verification, not expressiveness. The governed truth head is universal — the
    only imported fact is `exists_universal_cts`. -/
theorem governed_machine_universal :
    ∃ (prods : List (List Bool)),
      Universal (ctStep prods)
      ∧ (∀ n c0,
          iterate (tick (ctStep prods) (soundPredicate (ctStep prods))) n c0
            = iterate (ctStep prods) n c0) := by
  obtain ⟨prods, huniv⟩ := exists_universal_cts
  exact ⟨prods, huniv, fun n c0 => governed_simulates_cts prods n c0⟩

end C1
