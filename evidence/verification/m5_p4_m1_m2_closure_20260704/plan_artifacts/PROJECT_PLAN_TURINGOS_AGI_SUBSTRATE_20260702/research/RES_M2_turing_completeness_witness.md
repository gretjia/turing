# RES_M2 — Research Report: Turing-Completeness Witness

- Module: M2 — Turing-Completeness Witness (audit R3; retrospective Loop 2; KPI G3, the project's namesake claim)
- Date: 2026-07-02
- Author: Research agent (Fable-5-class), TuringOS AGI-Substrate Convergence Program
- Serves: KPI G3 — "Executable Turing-completeness witness under MicroTape rules. Gates TC-01..TC-10 all PASS; halting and non-halting examples; replay == reference interpreter; independent audit from clean clone; no market/PPUT/HCI shortcut affects transitions" (`/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/01_PROJECT_INTENT.md`, §2 row G3).
- Grounding anchors: Project Intent (path above); `/home/zephryj/turingos_backup/work/TURINGOS_RETROSPECTIVE_AUDIT_FINDINGS_20260702.md` (R3 at line 134; §5 "no Turing-completeness witness exists (TC-01..TC-10 defined, zero artifacts)").
- Binding gate specification: `/home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_verified_500_campaign_20260629/TURING_COMPLETENESS_PROOF_OBLIGATIONS_20260629.md` — sha256 `7be0980ee1a3ddf157f65096180c836341da548debcc93fe6957f355a7cf7cae` (computed 2026-07-02; pin this hash at Stage TC0 to freeze scope).
- Constitution (READ-ONLY, absolute): `/home/zephryj/turingos_backup/work/turing_v5/pack_v5_3_1/00_authority/constitution_root_law.md`. Load-bearing articles for this module: Art. 0.2 Tape Canonical (line 52: "所有信号必须可从 tape 重建" — all signals must be reconstructible from tape; operational item 2: every derived view needs an `assert_eq!(view, derive_from_tape(tape))` conservation test) and Art. III.4 Goodhart shielding (line 413).
- Evidence discipline in this report: every factual claim about the codebase cites an exact on-disk path opened or executed during this research (marked **verified**). Web-sourced claims are marked **WEB** with URLs. Literature facts from standard references not re-fetched this session are marked **LITERATURE**. Pure reasoning is marked **REASONED**.
- Repo state at research time: `turing` HEAD `bed7597`, branch `goal/mini-swe-bench-grok-worker` (verified via `git rev-parse`; matches Project Intent §4's `bed75977`).

---

## 1. Questions this research answers

1. Which minimal universal machine class should the witness use — two-counter Minsky machine, n-counter register machine, tag systems, Rule 110, or another minimal model — evaluated on construction complexity, encoding overhead, state-representation size, halting-semantics clarity, and auditability?
2. What must a credible **non-mechanized** universality argument contain (simulation-lemma chain, encoding correctness, the Schroeppel two-counter caveat), and exactly what scoped claim language does it license afterwards?
3. How do the five prescribed witness events (`ComputationStarted`, `InstructionAuthorized`, `InstructionApplied`, `MachineStateObserved`, `ComputationHalted`) enter the closed event-registry discipline, given that **none of them exists** in `turing/pack/04_registries/event_registry_v5_3_1.json` and that registry's `unknown_event_policy` is `REJECT` (both verified)?
4. How should machine state be canonically encoded and hash-chained (TC-02 `prev_state_hash`/`next_state_hash`) on top of the existing tape envelope, without creating a new canonical-bytes owner (audit F3)?
5. How should reference-interpreter differential testing be designed so it is genuinely independent (Knight–Leveson correlated-failure risk) and constitutionally clean (the reference is a derived-view checker, never a tape writer)?
6. What property-based/fuzz testing stack fits a repo whose Python package declares `dependencies = []` and whose environment has no `hypothesis` installed and no `proptest` in any Cargo manifest (all verified)?
7. What concrete mutation operators on exported tapes satisfy TC-07 (tamper rejected) and TC-08 (dropped event detected), and which existing auditor check category must each mutation trip?
8. What halting AND non-halting example set should ship, and what are the three distinct evidential strengths of a "does not halt" claim (static certificate, recurrence certificate, budget-bounded observation)?
9. How is "no market/PPUT/HCI shortcut can affect state transitions" turned into a mechanical gate rather than an assertion?
10. Where should the implementation live (language, module boundaries), and in what order should the TC0–TC5 stages execute inside an agentic loop?

---

## 2. Candidate methodologies, patterns, and stacks

### 2.1 On-disk ground truth this module builds on (all verified 2026-07-02)

- **The gate spec is frozen prose and already prescriptive.** `turing/evidence/bench/swe_bench_verified_500_campaign_20260629/TURING_COMPLETENESS_PROOF_OBLIGATIONS_20260629.md` prescribes: a two-counter Minsky machine "preferably" (line 20); `MachineState = {program_counter, counter_a, counter_b, halted}` and instruction forms `INC counter -> next_pc`, `DECJZ counter -> zero_pc | nonzero_pc`, `HALT` (lines 24–33); the five MicroTape event names (lines 35–41); "the reducer must reconstruct the current MachineState only from MicroTape events" (lines 43–45); gates TC-01..TC-10 verbatim (lines 50–59); witness programs `copy_a_to_b`, `add_a_b`, `multiply_small`, `branch_zero_nonzero`, `known_halting_busy_loop_with_budget` (lines 65–69); stages TC0–TC5 (lines 96–101); and the permitted post-TC4/TC5 claim sentence (lines 106–109).
- **Zero witness artifacts exist.** `turing/evidence/theory/` does not exist (`ls` returns "No such file or directory"); `find turing -iname "*minsky*" -o -iname "*counter_machine*" -o -iname "*witness*"` (excluding `target/`) returns nothing. The module starts from a clean slate, exactly as the audit states.
- **The closed event registry does not contain the witness events.** `turing/pack/04_registries/event_registry_v5_3_1.json` (sha256 `caa38f5cdd93df9d6d5aceac9e6009651d93cd9517ef43c8e3ce03ae93552dd7`): `grep` for `Computation|Instruction|MachineState` exits 1. Policy fields: `unknown_event_policy: "REJECT"`, `append_only_by_name: true`, `never_renumber: true`. **Additive-extension precedent exists in this same file**: 46 rows carry `status: FROZEN_V5_3_1`, 15 carry `ADDITIVE_AGENT_ECONOMY_V1_0`, 1 carries `ADDITIVE_BENCHMARK_V1` (`OfficialEvaluatorEvidenceImported`) — counted by script over the parsed JSON.
- **The registry has a live self-consistency defect the witness work must not repeat.** Declared `counts.total` = 61 and `counts.preserve` = 41, but the `events` list contains **62** rows, 42 of them `PRESERVE` (counted by script). The `registry_name_set_sha256` could not be reproduced from the obvious serialization (sorted names joined by newline yields a different digest), and no serialization convention is documented in the file — so that pin is currently unverifiable by an outside auditor. Both defects predate M2; report them to M0/owner, and make registry self-consistency a lint inside TC-01 (see §5.3).
- **The strict auditor is reusable as-is and takes a registry override.** `turing/tools/bench/audit_micro_tape_decision_dag.py` (1,163 lines): default registry path at line 24; `--event-registry` CLI flag at line 1132; `CRITICAL_REPLAY_CHECKS = {bundle_integrity, git_topology, canonical_payload_hash, ref_reconstruction, registry_head_effect, accepted_head_authority}` (lines 26–33). `validate_chain` enforces: seven required envelope fields (`writer_id`, `authority_epoch`, `prev_tape_tip`, `accepted_head_before`, `head_effect`, `event_schema_id`, `payload_hash`), contiguous `sequence`, `prev_tape_tip` linkage, `accepted_head_before`/`authorization_head_before` correctness, registry-derived `head_effect` and `payload_schema_id` equality, ADVANCE-requires-predicate-PASS, and canonical payload digest recomputation. Its canonical codec (`canonical_bytes`, lines ~80–107) is **sorted-key compact JSON, ASCII keys only, floats forbidden** — the witness payloads must stay inside that subset (integers only for counters, budgets, indices).
- **The tape substrate is real and already hash-chained at the event level.** `turing/src/turingos/tape.py`: `git init --object-format=sha256` (line 92), one non-merge commit per event carrying a 7-field `AppendEnvelope`, `head_effect` registry-derived "never writer-supplied", `tape_tip` always advances, `accepted_head` advances only on ADVANCE (append method around lines 280–330). This file is simultaneously the audit-F3 "canonical second owner" — a constraint on how M2 may append (see §2.7, §4 pitfall 7).
- **The reducer/replay idiom is established and documented in-repo.** `turing/src/turingos/reduce.py` (docstring: q_t is "a DERIVED fold of the Micro Tape — there is no separate persisted q_t"; stdlib only) and `turing/src/turingos/replay.py` (replay walks tape bytes alone, recomputes `payload_hash` per node, **raises on mismatch** rather than silently replaying; `verify_replay_equal` replays twice and compares canonical digests). The witness reducer should copy this exact idiom.
- **Authorization-class rows are ADVANCE targeting `authorization_head`.** All 8 AUTHORIZATION rows (e.g. `AtomAuthorized`, `ToolActionAuthorized`) are `head_effect: ADVANCE`, `target_ref: authorization_head`, `predicate_required: true`, `human_required: "policy"` (script over the registry). Relevant because `InstructionAuthorized` naturally belongs to this class, and because the Intent notes `authorization_head` has never passed on non-fixture evidence (Intent §4; audit R9).
- **Reusable failure rows exist for the non-halting/budget path.** `BudgetExhausted` (`FAILURE`, `PRESERVE`, `budget_exhausted.v1`) and `FailureNode` (`FAILURE`, `PRESERVE`) are already frozen registry rows — the witness does not need to invent a budget-stop event.
- **Evidence-bundle layout precedent.** `turing/evidence/bench/mini_swe_bench_stage6_strict_microtape_20260628/` contains `README.md`, `bundle_manifest.json`, `bundle_sha256s.txt`, `instances/`, `micro_tape_audit_strict/`, `strict_audit_summary.md`, `substrate_coverage.json` — the shape the witness evidence root should mirror.
- **Test-stack reality.** `turing/pyproject.toml`: `dependencies = []`, pytest configured (`testpaths = ["tests"]`). Host has pytest 7.2.1; `import hypothesis` fails (ModuleNotFoundError). `turing/Cargo.toml`: 17-crate workspace, edition 2024, `rust-version 1.96.0`, `unsafe_code = "forbid"`; `grep proptest` over all Cargo manifests returns nothing.

### 2.2 Machine-class candidates

**Candidate A — Two-counter Minsky machine (INC / DECJZ / HALT), as prescribed.**
- *Universality basis:* LITERATURE — Minsky, *Computation: Finite and Infinite Machines* (1967): two counters suffice to simulate any Turing machine **provided input/output is Gödel-encoded** (the tape content packed into one counter as an exponent-coded integer). WEB confirmation of the caveat's sharpness: Schroeppel, *A Two Counter Machine Cannot Calculate 2^N*, MIT AI Memo 257, 1972 — proves that with plain unary I/O (N in one counter, 0 in the other) a two-counter machine cannot compute 2^N, N², √N, log₂N, etc.; universality holds only under the encoding ([MIT DSpace AIM-257](https://dspace.mit.edu/handle/1721.1/6202); [Counter machine — Wikipedia](https://en.wikipedia.org/wiki/Counter_machine)).
- *Pros:* smallest possible closed instruction schema (exactly 3 forms → TC-01 registry is ~30 lines of JSON); machine state is 4 scalar fields → canonical state encoding is one tiny sorted-key JSON object inside the auditor's existing codec subset; branch/loop/halt gates (TC-04/05/06) map to 2-instruction test programs; deterministic total-step semantics (every non-HALT instruction always has a successor) make non-halting certificates tractable (§2.8); it is exactly what the frozen obligations file asks for, so no scope renegotiation.
- *Cons:* the Schroeppel caveat must appear in every claim (a two-counter machine is universal only up to I/O encoding); **general binary multiplication `a×b` is not directly writable with only two counters** (accumulating a product while decrementing requires a third register or exponential Gödel packing). REASONED resolution that keeps TC-05 satisfiable verbatim: define `multiply_small` as multiplication by a compile-time constant k (loop: `DECJZ a -> (halt_pc | body)`; body: k consecutive `INC b`; jump back) — that IS "a terminating multiplication/addition program" in the obligations file's words, runs on exactly two counters, and is honest as long as the program README says "multiplication by constant".

**Candidate B — n-counter Minsky/register machine (same 3 instruction forms; register count declared per program, n ≥ 2).**
- *Universality basis:* LITERATURE — Minsky 1967: TM → two-stack machine → 4-counter machine is a direct, teachable simulation chain with no exponential encoding until the final 4→2 compression. WEB — Korec, *Small universal register machines*, TCS 168(2):267–301, 1996, gives concrete small strongly-universal machines (down to 14–32 instructions depending on base/notion; the standard U22 has 22 instructions) ([ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0304397596000801); [CMU PDF](http://www.cs.cmu.edu/~cdm/resources/Korec1996-small-universal-RM.pdf)).
- *Pros:* general `a×b` multiply is a natural 3–4 counter program; opens a spectacular stretch goal — actually **running a literal universal program (Korec U22) on the witness interpreter** as an executable universality exhibit.
- *Cons:* departs from the obligations file's literal `MachineState {counter_a, counter_b}` (line 26–29), so either the frozen spec's letter is violated or a v2 schema is needed; slightly larger state encoding and schema surface.

**Candidate C — 2-tag systems.**
- *Universality basis:* LITERATURE — Cocke & Minsky, *Universality of Tag Systems with P=2*, JACM 11(1), 1964.
- *Pros:* strings instead of numbers; historically the bridge used by small-UTM results.
- *Cons (disqualifying):* REASONED — machine state is an unbounded word, so canonical state encoding and state hashing are string-length-dependent; the TM-configuration encoding is intricate (per-symbol production tables); halting conventions are subtle (word shorter than deletion number, or a designated halting symbol); the natural witness programs (add, multiply, branch) have no direct expression. Audit cost strictly higher than counters with zero offsetting benefit for G3.

**Candidate D — Rule 110 (elementary cellular automaton).**
- *Universality basis:* WEB — Cook, *Universality in Elementary Cellular Automata*, Complex Systems 15:1–40, 2004 ([abstract](https://www.complex-systems.com/abstracts/v15_i01_a01/); [PDF](https://content.wolfram.com/sites/13/2023/02/15-1-1.pdf)) — universality via emulating cyclic tag systems with glider collisions on an infinitely repeating background; Neary & Woods, *P-completeness of Cellular Automaton Rule 110*, ICALP 2006, LNCS 4051, removed the exponential simulation overhead ([Semantic Scholar](https://www.semanticscholar.org/paper/P-completeness-of-Cellular-Automaton-Rule-110-Neary-Woods/37f31fae33ef4ced69b2915853a552463cc6b7f5)).
- *Cons (disqualifying):* REASONED — only *weak* universality (requires an infinite periodic background, so "entire machine state on tape" becomes an encoding argument in itself); the simulation chain (TM → clockwise TM/2-tag → cyclic tag → glider choreography) is the most complex construction in this candidate set; "halting" is glider-pattern detection, not a machine flag — TC-06 has no natural meaning. Famous, but the opposite of auditable. Reject.

**Candidate E — other minimal models (briefly).** REASONED. SUBLEQ/OISC: one instruction but state = a whole signed-integer memory array, and universality arguments are folklore-grade rather than citable-clean; FRACTRAN (Conway 1987): elegant, tiny state (one integer), but program semantics (first applicable fraction) are opaque to a non-mathematician auditor and the integers explode; lambda calculus / SKI: the interpreter itself (substitution, normal-order strategy) is the largest and most bug-prone artifact in the set, moving audit burden into the interpreter. All rejected on audit cost.

**Comparison summary (REASONED):**

| Criterion | A: 2-counter | B: n-counter | C: 2-tag | D: Rule 110 |
|---|---|---|---|---|
| Instruction schema size (TC-01) | 3 forms | 3 forms | per-symbol tables | 8-bit rule + window |
| State encoding | 4 scalars | 3 + n scalars | unbounded word | unbounded row + background |
| Universality argument | citation + encoding caveat | citation, direct chain | citation, intricate encoding | citation, weak universality |
| Halting semantics | explicit HALT | explicit HALT | convention-dependent | pattern detection |
| Natural add/multiply/branch programs | yes (multiply by constant) | yes (general multiply) | no | no |
| Matches frozen obligations file | exactly | schema deviation | no | no |
| Non-halting certificates (§2.8) | tractable | tractable | hard | intractable |

### 2.3 Structure of a credible non-mechanized universality argument

REASONED, with LITERATURE anchors. The witness makes an **empirical-plus-citational** claim, and the argument must be explicit about which layer is which:

- **Layer 0 — interpreter correctness (empirical, mechanical).** Evidence that the implemented operational semantics equals the spec in the obligations file: differential testing against an independent reference interpreter (§2.5), a seeded fuzz corpus (§2.6), and the TC-03/04/05/06 trace gates. This layer is testing, not proof — say so.
- **Layer 1 — bounded witness executions (empirical, mechanical).** The named witness programs run to completion (or to certified non-halt) with every state transition on tape, replayable, tamper-evident (TC-02, TC-07..TC-09).
- **Layer 2 — universality of the machine class (citational, never mechanized here).** A `THEORY.md` in the evidence root stating precisely: (i) counter machines with `INC`/`DECJZ` and ≥2 counters are Turing-universal **with Gödel-encoded I/O** (Minsky 1967, chs. 11/14 — LITERATURE); (ii) the encoding caveat is essential, per Schroeppel 1972 (WEB, [AIM-257](https://dspace.mit.edu/handle/1721.1/6202)); (iii) the simulation-lemma template that any reader can check against the citations: a state-correspondence relation R between simulated-machine configurations and witness-machine states; a step lemma (one simulated step = k witness steps preserving R); encoding/decoding correctness at input and output boundaries; and halting correspondence (simulated machine halts iff witness reaches HALT). The witness does **not** re-derive these lemmas; it cites them and demonstrates that the substrate faithfully executes the machine class they are about.
- **Layer 3 — substrate property (the actual G3 claim).** What TuringOS itself proves: *the state/tape/reducer loop can represent, replay, and tamper-protect every step of a machine from a universal class, within declared budgets*. This is a statement about the substrate, not a new theorem of computability.

A fully mechanized alternative exists — LITERATURE: the Coq Library of Undecidability Proofs contains formalized Minsky/counter-machine reductions (uds-psl/coq-library-undecidability; not re-fetched this session) — but importing a proof assistant to certify a 3-instruction interpreter is over-engineering for G3's KPI and adds a toolchain no other module needs. Record it as future work in the ADR, not scope.

### 2.4 Event-registry integration options (closed-registry discipline)

**Option R-A — additive extension of the shared registry (recommended).** Append five rows to `turing/pack/04_registries/event_registry_v5_3_1.json` with `status: "ADDITIVE_TC_WITNESS_V1"`, following the exact precedent of `ADDITIVE_BENCHMARK_V1` and the 15 `ADDITIVE_AGENT_ECONOMY_V1_0` rows already in that file (verified §2.1). The file's own policy permits this (`append_only_by_name: true`); the frozen core rows are untouched. Update `counts` and (with M0/owner sign-off) either fix or explicitly annotate the pre-existing 61-vs-62 inconsistency; add the registry self-consistency lint (§5.3) so the drift class dies. *Pros:* one registry remains the single closed authority; the default auditor path validates witness bundles with no flags; `unknown_event_policy: REJECT` keeps protecting everything. *Cons:* touches a shared file (coordinate through M0's governance chain; note the `turing/pack/` copy is demonstrably the amendable working registry, distinct from the frozen `turing_v5/pack_v5_3_1/` pack which no agent may touch).

**Option R-B — standalone witness registry via `--event-registry`.** The auditor supports a registry override (line 1132, verified). *Pros:* zero edits to the shared registry. *Cons (decisive):* forks registry authority — two closed sets, and a witness bundle **fails** the default audit configuration (its events are unknown under `REJECT`), which is exactly the wrong shape for TC-10's independent audit; every external auditor must be told which registry governs which bundle. REASONED: reject except as a temporary dev-time scaffold before the additive rows land.

**Proposed additive rows (REASONED design, consistent with observed row shapes):**

| canonical_name | event_class | head_effect | target_ref | predicate_required | human_required | payload_schema_id |
|---|---|---|---|---|---|---|
| ComputationStarted | OBSERVATION | PRESERVE | tape_tip | true | false | computation_started.v1 |
| InstructionAuthorized | AUTHORIZATION | ADVANCE | authorization_head | true | false | instruction_authorized.v1 |
| InstructionApplied | OBSERVATION | PRESERVE | tape_tip | true | false | instruction_applied.v1 |
| MachineStateObserved | OBSERVATION | PRESERVE | tape_tip | true | false | machine_state_observed.v1 |
| ComputationHalted | OBSERVATION | PRESERVE | tape_tip | true | false | computation_halted.v1 |

Rationale for the one ADVANCE row: all 8 existing AUTHORIZATION rows are `ADVANCE → authorization_head` (verified §2.1), so an AUTHORIZATION-class `InstructionAuthorized` is the registry-consistent choice; its predicate is deterministic and honest ("instruction at pc is in the closed program table AND step budget remains > 0"), so `predicate_product: PASS` is mechanically computed, never fabricated. Side benefit: the witness becomes the first evidence family in which `authorization_head` advances on real, non-fixture runs — it does not discharge R9 (which requires a real *worker* run with keyring), but it exercises the `accepted_head`/`authorization_head` separation that existing evidence only claims abstractly. `human_required: false` (not "policy") because witness steps are pure deterministic computation with no external effect. **The witness never emits SOVEREIGN_ACCEPT events and never moves `accepted_head`** — G3 is about computation, not authority. **Append-route consequence (verified):** this ADVANCE→`authorization_head` row is representable only by the Rust three-ref writer (`crates/turing-git-tape/src/append.rs`); the Python `Tape` writer in `src/turingos/tape.py` explicitly excludes that ref ("There is NO `refs/turingos/authorization_head` in 1.0" — docstring, verified), so the witness emitter must use the Rust writer from its first append (§3, ADR-M2-002).

Non-halting budget stops reuse the frozen `BudgetExhausted` row (`budget_exhausted.v1`, PRESERVE — verified §2.1); no new failure event is needed.

### 2.5 Reference-interpreter differential testing

REASONED, with LITERATURE caution. The pattern: two implementations of the same operational semantics, written from the spec independently, compared on **the full per-step state-hash trace** (not merely final state — final-state-only comparison is blind to compensating double errors).

- **Independence design.** SUT: the Rust emitter+reducer (production path). Reference: a deliberately tiny Python interpreter (≤ ~80 lines, stdlib only, direct transcription of the obligations file's instruction semantics), living under `tools/theory/`, sharing **no code** with the SUT — the only shared artifact is the canonical state-encoding definition, which must be shared (it defines what a state hash *is*) and is itself cross-checked by the existing canonical-codec discipline. LITERATURE caution: Knight & Leveson (*An experimental evaluation of the assumption of independence in multiversion programming*, IEEE TSE 1986) showed independently written versions fail on correlated inputs more than independence would predict; mitigate by (a) keeping the reference so small it can be audited by eye against the spec in minutes, and (b) driving both with an adversarial generated-program corpus, not just the 5 named programs.
- **Constitutional cleanliness (anti-F3).** The reference interpreter is a **derived-view checker under Art. 0.2 item 2** (verified constitution line ~60: every derived view needs a conservation check against the tape): it never appends to any tape, never canonicalizes bytes for storage, and only emits a state-hash trace file that the comparison gate consumes. The audit's F3 finding (three canonical-bytes owners) makes this boundary load-bearing: the witness must not become owner number four (§4 pitfall 7).
- **Precedent.** Cross-implementation byte-equality has already been proven once in this program: C02 Rust JCS == Python on the omega track (workspace `CLAUDE.md`, "Current state"). The witness's TC-03 gate is the same discipline applied to interpreter traces.

### 2.6 Property-based / fuzz testing stack

- **Option T1 — seeded stdlib generator (recommended for load-bearing evidence).** A ~60-line generator using Python's `random.Random(seed)` producing well-formed programs only (all jump targets in range, counters in {a, b}, bounded length), plus a fuzz manifest `{generator_version, seed, program_count, max_steps}` recorded in the evidence bundle. *Pros:* zero new dependencies (matches `dependencies = []`, verified); the seed makes the entire campaign a replayable artifact — evidence-grade under Art. 0.2. *Cons:* no shrinking; mitigate by keeping generated programs short (≤ 32 instructions) so failures are readable raw.
- **Option T2 — Hypothesis (optional, dev-time only).** WEB: Hypothesis is deterministic under `derandomize=True` (seeds from a hash of the test function; the built-in "ci" profile sets `derandomize=True, database=None`), and profiles are registered in `conftest.py` ([settings tutorial](https://hypothesis.readthedocs.io/en/latest/tutorial/settings.html); [API reference](https://hypothesis.readthedocs.io/en/latest/settings.html)). *Cons:* new dev dependency in a zero-dependency repo; the example database and shrinking history are not tape-reconstructible artifacts. Use for exploratory bug-hunting locally if desired; never cite as gate evidence.
- **Option T3 — proptest (optional, Rust dev-time only).** WEB: proptest persists failing seeds in checked-in `proptest-regressions` files and supports a fixed `rng_seed` in `Config` for full determinism; strategies must be deterministic for persistence to work ([failure persistence](https://altsysrq.github.io/proptest-book/proptest/failure-persistence.html); [Config docs](https://docs.rs/proptest/latest/proptest/test_runner/struct.Config.html)). Same verdict as T2.

**Properties worth asserting (REASONED, the actual value of this section):**
1. *Differential equality:* for every generated program and every step ≤ N, reference state hash == reducer state hash (TC-03 generalized).
2. *Determinism:* running emitter+reducer twice yields byte-equal traces (mirrors `verify_replay_equal` in `replay.py`, verified).
3. *Chain integrity:* `next_state_hash(step i)` == `prev_state_hash(step i+1)` for all i; recomputing state hashes from payload fields matches stored hashes (TC-02).
4. *Halt absorbency:* no event after `ComputationHalted` changes reduced machine state; a forged post-halt `InstructionApplied` is rejected (TC-06).
5. *Mutation kill:* every operator in the §2.7 matrix is detected (TC-07/08) — a surviving mutant fails the gate.
6. *Economy-interleave invariance:* inserting legal PRESERVE economy events between witness events leaves the reduced machine state byte-identical (§2.9).
7. *Budget correctness:* execution stops with `BudgetExhausted` after exactly `budget` applied instructions and emits no `ComputationHalted`.

### 2.7 Hash-chained event-sourced state, and where TC-02 sits

REASONED on verified substrate. The tape already chains **events** three ways: git sha256 commit parentage, envelope `prev_tape_tip`, and per-payload `payload_hash` (all enforced by `validate_chain`, verified §2.1). TC-02 adds a fourth chain at the **machine-state** level: each `InstructionApplied` payload carries `prev_state_hash` and `next_state_hash`. This is not redundant — event-level chaining proves *these bytes in this order*; state-level chaining proves *this computation* (it catches a semantically corrupted but correctly re-chained tape, and it is what makes the recurrence-based non-halting certificate (§2.8) a two-line check).

Canonical state encoding (fits the auditor's codec subset — ASCII keys, integers only, no floats):

```json
{"counter_a": 3, "counter_b": 7, "halted": false, "program_counter": 4}
```

`state_hash = canonical_payload_digest(state)` — reuse the exact `canonical_bytes` definition (sorted-key compact JSON) already in `audit_micro_tape_decision_dag.py` lines ~80–107 (verified). **Exclude the step index from the hashed state** (carry `step_index` as a separate payload field): identical machine states at different steps must hash identically, or the recurrence certificate is impossible.

Mutation operators for TC-07/08 (each names the auditor category that must FAIL; categories verified in `CRITICAL_REPLAY_CHECKS` / `validate_chain`):

| # | Mutation on exported bundle copy | Must be caught by |
|---|---|---|
| m1 | Flip one payload byte inside a committed event blob | `bundle_integrity` / `git_topology` (git object hash breaks) |
| m2 | Drop event i, leave rest untouched | `ref_reconstruction` (`sequence` gap, `prev_tape_tip` mismatch) |
| m3 | Drop event i AND forge re-chained envelopes | TC-02 state-hash chain break: `next_state_hash(i−1) ≠ prev_state_hash(i+1)`; plus final-state divergence vs reference (TC-08) |
| m4 | Reorder two adjacent events (re-chained) | state-hash chain break; `registry_head_effect` if class order becomes illegal |
| m5 | Duplicate an `InstructionApplied` (re-chained) | state-hash chain break (a duplicated step cannot satisfy both neighbors unless the state is a fixed point — and a HALT/INC step never is) |
| m6 | Tamper payload and update `payload_hash` consistently | git commit oid changes → `ref_reconstruction` (refs point at vanished oids) / `bundle_integrity` |
| m7 | Corrupt a counter value inside `MachineStateObserved` only | reducer cross-check: observed state hash ≠ reduced state hash (`canonical_payload_hash` category or witness-specific check) |

This is mutation testing applied to tapes: the gate artifact is a matrix with one row per operator per witness program, each row PASS = "mutant killed", and **any surviving mutant is a gate FAIL** — never delete a surviving-mutant row; that would be fabricating PASS.

### 2.8 Halting and non-halting example sets, with a claim-strength taxonomy

Halting set (all strict two-counter; names match the obligations file lines 65–69):

| Program | Semantics | Gate served |
|---|---|---|
| `copy_a_to_b` | `while a>0 {a--; b++}` — destructive move (README must say "destructive"; a true non-destructive copy needs a third counter) | TC-03 |
| `add_a_b` | `b := a+b; a := 0` (same loop shape, initial b ≠ 0) | TC-05 |
| `multiply_small` | `b := k·a` for compile-time constant k (k unrolled `INC b` per loop pass) — labeled "multiplication by constant"; general `a×b` is impossible on two counters without Gödel packing (Schroeppel; §2.2 A) | TC-05 |
| `branch_zero_nonzero` | one `DECJZ`, run twice: initial a=0 (zero edge) and a=5 (nonzero edge) | TC-04 |
| `known_halting_busy_loop_with_budget` | countdown from N, halts within declared budget | TC-06, budget accounting |

Non-halting set — the module charter demands non-halting examples; the honest design distinguishes **three certificate strengths** (REASONED; this taxonomy is the module's main intellectual guard against overclaim):

- **C1 — static HALT-unreachability (sound, machine-checkable).** In this machine class every non-HALT instruction always has a successor (INC and both DECJZ branches are total), so execution stops **only** at HALT. Compute the control-flow-graph reachability over-approximation (edges: `INC → next_pc`; `DECJZ → {zero_pc, nonzero_pc}`); if no HALT instruction is reachable from pc 0, the program provably never halts, for **all** inputs. Example program `spin_no_halt`: `0: INC a -> 0`. Certificate artifact: the reachable-pc set plus the checker's verdict.
- **C2 — exact state recurrence (sound for this deterministic machine).** If the same `state_hash` (which excludes step index) appears at two different steps, the machine is in a cycle and never halts. Example `pingpong_constant`: `0: DECJZ a -> (0 | 1); 1: HALT` started with a=0 — state `(pc=0, a=0, b=0)` recurs immediately. Certificate artifact: the two step indices and the shared hash — a two-line check any auditor can redo from the tape.
- **C3 — budget-bounded observation (bounded claim ONLY).** Example `grow_forever`: `0: INC a -> 1; 1: INC b -> 0` — state never recurs (counters grow), HALT is statically unreachable here too, but for programs where neither C1 nor C2 applies the only mechanical evidence is: ran N steps, emitted `BudgetExhausted` (frozen registry row, verified), no `ComputationHalted`. The permitted sentence is "did not halt within N steps under budget B", **never** "is non-halting". A prose induction argument may accompany it, labeled REASONED and non-mechanical.

Ship at least one example of each certificate class. This also inoculates the project against the obvious external criticism: claiming decided non-halting in general would contradict the undecidability of halting — the taxonomy shows the project knows exactly where that line is.

### 2.9 The market/PPUT/HCI non-interference gate (Goodhart shielding, Art. III.4)

REASONED on verified substrate. "No market/PPUT/HCI shortcut can affect state transitions" must be mechanical, in three layers:

1. **Interleave invariance (dynamic).** Build tape T1 = witness events only; tape T2 = same witness events with legal PRESERVE economy events (`MarketCreated`, `AgentBidSubmitted`, `MarketPriceBroadcast`, `PPUTAccounted` — all frozen PRESERVE rows, verified §2.1) interleaved between steps. Assert: reduced final machine state and full state-hash trace byte-identical across T1/T2.
2. **Sabotage meta-test (proves the test has teeth).** A deliberately broken reducer variant that reads a market event (e.g., adds a broadcast price to `counter_a`) must FAIL the interleave test. Without this, layer 1 could pass vacuously forever.
3. **Read-surface lint (static).** The witness reducer's accepted event-type set is exactly the five TC names (+ `BudgetExhausted`); a lint asserts no other `event_type` string literal or registry class is consulted in the reducer module.

Layer 1+2 is the same conservation-test discipline Art. 0.2 item 2 already mandates for derived views (verified constitution §0.2); layer 3 is the cheap regression lock.

### 2.10 Sandboxing and cost posture

REASONED on verified context. The witness mutates no repository and calls no LLM — it is pure CPU over a private tape repo. The Intent's sandbox red line (§5.6) targets *mutation paths*; the witness's only writes are to its own evidence root and its own tape repos. Running the emitter under gVisor/runsc where available is cheap and removes any argument (precedent: runsc references in `turing/tools/headless/run_local_gates.py` et al., verified); otherwise record `HOST_ASSUMED` on tape per the red line. Cost: zero tokens; the entire module is deterministic code — the cheapest gate family in the whole program, which is exactly why it should not be allowed to slip again.

---

## 3. Recommendation

**Build the witness as a two-counter Minsky machine (Candidate A) with a generic n-counter interpreter core, v1 tape schema fixed verbatim to the obligations file's two-counter `MachineState`, additive registry rows (Option R-A), an independent ≤80-line Python reference interpreter, a seeded stdlib fuzz campaign (T1), the m1–m7 mutation matrix, and the three-tier non-halting certificate set.** Deliverables live in the `turing` repo (during execution, not by this plan): Rust interpreter/emitter/reducer as a new crate (working name `turing-witness`) appending **through the Rust three-ref tape writer from the start** — `turing/crates/turing-git-tape/src/append.rs`, which owns `refs/turingos/authorization_head` (`REF_AUTHORIZATION_HEAD`, line 59, and advances it only for AUTHORIZATION+PASS, lines 738–763; verified 2026-07-02) — the Python reference under `tools/theory/`, and evidence at `turing/evidence/theory/turing_completeness_witness_YYYYMMDD/`. The append route is not a free choice: the Python `Tape` writer in `src/turingos/tape.py` verifiably cannot represent §2.4's `InstructionAuthorized` head effect at all (its docstring: "There is NO `refs/turingos/authorization_head` in 1.0"; "Frozen ref names — exactly two, never a third" — verified), so routing witness appends through it would either fail every AUTHORIZATION append or provoke an improvised third ref-writer, the exact F3 defect class. Using the Rust writer anticipates M1's canonical-owner designation rather than waiting for it; if M1 later designates a different owner, the emitter migrates then (recorded in ADR-M2-002).

Rationale against the project's stated goals (Intent §§1–6):

- **Long-running autonomy:** the module is fully deterministic, token-free, and decomposes into small atoms with mechanical pass/fail gates — an orchestrator can run TC0→TC5 unattended with zero judgment calls, and every stage is resumable from the tracker plus tape alone (Intent §8.6).
- **Replayability (Art. 0.2):** the entire machine state is a derived fold of tape events (mirroring the proven `reduce.py`/`replay.py` idiom, verified); the fuzz campaign is seed-pinned; every gate verdict cites bundle paths — the same discipline the strict auditor already enforces, extended to computation.
- **Sandboxed execution:** no repo mutation; runsc where available, `HOST_ASSUMED` recorded otherwise (§2.10).
- **Goodhart shielding (Art. III.4):** no workers participate at all, and the non-interference gate (§2.9) mechanically demonstrates that economy/HCI signals cannot touch transitions — including a sabotage meta-test so the gate can never pass vacuously.
- **Observability:** one verdict JSON per gate TC-01..TC-10 in a fixed schema (§5.6), a mutation matrix, and a `THEORY.md` separating empirical from citational layers — no prose-only status (Intent §6).
- **Modularity:** four ports — interpreter core (pure function), emitter (tape adapter), reducer (derived view), reference (independent checker) — so M2 parallelizes across implementation agents and the reference can be reassigned to a different agent/model family for genuine independence.
- **Cost:** zero LLM spend; estimated total code ≈ 1.5–3k lines including tests; the binding cost is discipline, not compute.
- **Claim integrity (the namesake):** the two-counter class carries the cleanest citable universality chain *with* a sharp, documented caveat (Schroeppel), which makes the scoped claim honest and externally defensible; Candidates C/D would multiply audit cost 10–100× for zero additional claim strength.

**Permitted claim language after TC-01..TC-09 PASS + TC-10 independent PASS (deliverable required by the module charter):**

> "TuringOS carries a MicroTape-backed executable computation witness: a two-counter Minsky machine interpreter whose entire machine state is reconstructible from tape events alone, whose replay equals an independent reference interpreter on all tested programs, and whose tapes reject tampering and event loss. Two-counter Minsky machines are Turing-universal up to Gödel-encoded input/output (Minsky 1967; Schroeppel 1972). On this basis the TuringOS state/tape/reducer loop can represent unbounded discrete computation — universal up to resource bounds, subject to time and budget."

This is deliberately at most as strong as the obligations file's own permitted sentence (lines 106–109) plus the encoding caveat. **Remains forbidden, permanently or until stated conditions:** the unqualified sentence "TuringOS is Turing-complete"; "proved Turing-completeness" (implies mechanized proof); "can compute anything"; any universality claim **before** the TC-10 external artifact exists (Intent §5.3); any suggestion that SWE-bench results evidence universality (the obligations file's own opening verdict, lines 3–13); any claim that non-halting is decided in general (§2.8 C3); and any self-declared CLOSED — the implementer ceiling is ADDRESSED (Intent §5.2), with CLOSED only via the independent cross-family verifier on a fresh clone.

---

## 4. Pitfalls and mitigations

1. **The Schroeppel overclaim.** Two-counter machines cannot even compute 2^N with unary I/O (WEB, AIM-257). *Mitigation:* the caveat sits inside the permitted claim sentence itself, in `THEORY.md`, and in `CLAIM_BOUNDARY.json` as a machine-readable forbidden-phrase list.
2. **`multiply_small` is quietly impossible as general multiplication on two counters.** An implementer following the obligations file naively will discover this mid-build and be tempted to add a third counter ad hoc, breaking the frozen v1 schema. *Mitigation:* define `multiply_small` = multiplication by compile-time constant up front (§2.8); general multiply is an explicitly-labeled v2/stretch program (ADR-M2-001).
3. **Registry drift recurrence.** The registry already has stale `counts` (61 declared vs 62 actual, preserve 41 vs 42) and an unreproducible `registry_name_set_sha256` (verified §2.1). Appending five rows the same careless way deepens the rot. *Mitigation:* registry self-consistency lint as part of TC-01 (§5.3); report the pre-existing defect to M0 rather than silently fixing history.
4. **Correlated-failure blindness in differential testing.** If the reference shares code, canonicalization bugs, or even the same author-session's misreading of `DECJZ` (does it decrement before or after the zero test? — the spec means: if counter==0 jump to `zero_pc` **without decrement**, else decrement and go to `nonzero_pc`; write this in the instruction schema registry), both sides agree on wrong semantics. *Mitigation:* reference ≤80 lines, different language, ideally a different agent/model family writes it from the obligations file alone; adversarial fuzz corpus; the DECJZ edge-order test is mandatory (TC-04).
5. **Event-chain-only tamper evidence (compensating errors).** Git-level chaining alone cannot catch a semantically corrupted, correctly re-chained tape. *Mitigation:* TC-02's machine-state hash chain plus mutation m3/m5 which specifically require the state-level chain to fire (§2.7).
6. **Vacuous tamper gates.** Testing only mutations git already catches (m1) fabricates confidence. *Mitigation:* the full m1–m7 matrix with per-operator kill evidence; surviving mutants are FAILs on the record, never deleted rows.
7. **Becoming canonical-bytes owner number four (F3 recurrence).** The witness emitter must reuse an existing canonical append path and codec — concretely the Rust `turing-git-tape` three-ref writer (§3, ADR-M2-002), since the Python `Tape` writer cannot advance `authorization_head` (verified §2.4) — and the reference interpreter must never write a tape. *Mitigation:* the pre-M1 append route is named in ADR-M2-002 (no improvisation window); anti-F3 assertion in ADR-M2-004; lint that `tools/theory/` contains no tape-append calls.
8. **Codec-subset violations.** The auditor refuses floats and non-ASCII keys (verified lines ~80–107). A careless `budget: 1e6` or a duration float in a payload bricks the audit. *Mitigation:* integers only, schema-validated at emit time; property 2.6#3 recomputes digests.
9. **Non-halting overclaim.** "We include non-halting examples" drifts into "we detect non-halting". *Mitigation:* the C1/C2/C3 taxonomy with per-program certificate class stamped in the bundle; C3 language locked to "did not halt within N steps".
10. **Self-closure of the namesake gate.** The strongest temptation in the whole program: the implementing agent declaring G3 done. *Mitigation:* TC-10 is by construction not executable by the implementer (fresh clone, cross-family verifier, custody-separated per Intent G6); module status ceiling ADDRESSED; the evidence root's `CLAIM_BOUNDARY.json` sets `turing_completeness_claim_allowed: false` until the external artifact path exists.
11. **Hypothesis/proptest nondeterminism leaking into evidence.** Example databases and shrink history are not tape-reconstructible. *Mitigation:* T2/T3 are dev-time only; load-bearing fuzz evidence comes exclusively from the seed-pinned T1 campaign (§2.6).
12. **Fixture/real mislabeling.** Witness runs are real deterministic executions but involve no worker and no external system; an auditor might read "REAL" as "real LLM run". *Mitigation:* label the evidence root `evidence_class: REAL_DETERMINISTIC_EXECUTION` with one explanatory sentence in `README.md`, satisfying the audit's R8 hygiene direction.

---

## 5. How to use this in an agentic loop

### 5.1 Stage map (TC0–TC5 from the obligations file → atoms)

```
TC0 freeze     : pin obligations sha256 7be0980e…; write instruction schema registry + payload schemas
                 + additive registry rows (proposal to M0 chain); ADRs M2-001..007 accepted-addressed.
TC1 reference  : Python reference interpreter (tools/theory/reference_interpreter.py) + unit tests
                 incl. DECJZ edge-order test.
TC2 emit/reduce: Rust crate turing-witness (core + emitter + reducer); emitter appends via the
                 turing-git-tape three-ref writer (crates/turing-git-tape/src/append.rs — the only
                 writer that can advance authorization_head; ADR-M2-002); reducer conservation test
                 (Art. 0.2 item 2 idiom, mirroring src/turingos/reduce.py).
TC3 run/export : execute the 5 halting + 3 non-halting programs; export git bundles + fuzz campaign
                 (seeded, manifest on record) into evidence root.
TC4 audit      : differential equality, mutation matrix m1–m7, interleave invariance + sabotage
                 meta-test, replay-twice; emit verdicts TC-01..TC-09.
TC5 external   : publish exact-SHA packet; independent cross-family verifier runs from clean clone
                 (TC-10). Implementer stops at ADDRESSED.
```

### 5.2 Freeze commands (Stage TC0)

```bash
cd /home/zephryj/turingos_backup/work/turing
sha256sum evidence/bench/swe_bench_verified_500_campaign_20260629/TURING_COMPLETENESS_PROOF_OBLIGATIONS_20260629.md
# expect: 7be0980ee1a3ddf157f65096180c836341da548debcc93fe6957f355a7cf7cae   (STOP if drifted)
sha256sum pack/04_registries/event_registry_v5_3_1.json   # pre-extension baseline: caa38f5c…
```

### 5.3 Registry self-consistency lint (part of TC-01; also catches the pre-existing 61/62 defect)

```python
import json, sys
d = json.load(open("pack/04_registries/event_registry_v5_3_1.json"))
names = [e["canonical_name"] for e in d["events"]]
assert len(names) == len(set(names)), "duplicate canonical_name"
assert d["counts"]["total"] == len(names), f"counts.total {d['counts']['total']} != {len(names)}"
from collections import Counter
he = Counter(e["head_effect"] for e in d["events"])
assert d["counts"]["advance"] == he["ADVANCE"] and d["counts"]["preserve"] == he["PRESERVE"]
# name-set hash: document the serialization convention in-file, then enforce it here.
```

(As of 2026-07-02 this lint FAILS on the untouched registry — total 61 vs 62, preserve 41 vs 42, verified. Escalate to M0 before appending the TC rows.)

### 5.4 Closed instruction schema registry (TC-01 artifact, `programs/instruction_schema_registry.v1.json`)

```json
{
  "schema_id": "turingos.tc_witness.instruction_registry.v1",
  "machine_class": "minsky_counter_machine",
  "counters": ["counter_a", "counter_b"],
  "unknown_instruction_policy": "REJECT",
  "pc_range_policy": "REJECT_OUT_OF_RANGE_AT_LOAD",
  "decjz_semantics": "if counter==0: jump zero_pc WITHOUT decrement; else: decrement then jump nonzero_pc",
  "instructions": [
    {"op": "INC",   "fields": {"counter": "counter_name", "next_pc": "pc"}},
    {"op": "DECJZ", "fields": {"counter": "counter_name", "zero_pc": "pc", "nonzero_pc": "pc"}},
    {"op": "HALT",  "fields": {}}
  ]
}
```

Loader contract: every jump target ∈ [0, program_length); execution therefore stops **only** at an explicit HALT — the precondition for the C1 static non-halting certificate (§2.8).

### 5.5 Payload schemas (v1, all values integers/strings/bools — auditor codec subset)

```json
// computation_started.v1
{"program_id": "copy_a_to_b", "program_digest": "sha256:…", "program": [ …instruction rows… ],
 "initial_state": {"counter_a": 5, "counter_b": 0, "halted": false, "program_counter": 0},
 "state_hash": "sha256:…", "step_budget": 10000,
 "instruction_registry_digest": "sha256:…"}

// instruction_authorized.v1   (AUTHORIZATION/ADVANCE -> authorization_head; deterministic predicate)
{"program_id": "…", "step_index": 12, "pc": 4,
 "instruction": {"op": "DECJZ", "counter": "counter_a", "zero_pc": 9, "nonzero_pc": 5},
 "predicate": "instruction_in_closed_table_and_budget_remaining", "budget_remaining": 9988}

// instruction_applied.v1      (the TC-02 carrier)
{"program_id": "…", "step_index": 12, "pc_before": 4, "pc_after": 5,
 "instruction": { … }, "prev_state_hash": "sha256:…", "next_state_hash": "sha256:…"}

// machine_state_observed.v1   (full state; per-step in v1 since programs are tiny)
{"program_id": "…", "step_index": 12,
 "state": {"counter_a": 2, "counter_b": 3, "halted": false, "program_counter": 5},
 "state_hash": "sha256:…"}

// computation_halted.v1
{"program_id": "…", "final_step_index": 40, "final_state": { … }, "final_state_hash": "sha256:…",
 "halt_kind": "EXPLICIT_HALT"}
```

`state_hash` = `canonical_payload_digest({counter_a, counter_b, halted, program_counter})` — step index **excluded** (§2.7); reuse the existing `canonical_bytes`/`canonical_payload_digest` definitions rather than re-implementing them (anti-F3). Non-halting budget stops emit the frozen `BudgetExhausted` (`budget_exhausted.v1`) instead of `ComputationHalted`, with a payload noting `steps_executed` and `certificate_class: "C3_BUDGET_BOUNDED"` (or C1/C2 events carry their certificates in a `non_halting_certificate` field of a final `MachineStateObserved`).

### 5.6 Reference interpreter skeleton (Python, stdlib only, tools/theory/)

```python
def step(program, state):
    """One step of the two-counter machine. Total except at HALT."""
    if state["halted"]:
        return state
    ins = program[state["program_counter"]]
    s = dict(state)
    if ins["op"] == "HALT":
        s["halted"] = True
    elif ins["op"] == "INC":
        s[ins["counter"]] += 1
        s["program_counter"] = ins["next_pc"]
    elif ins["op"] == "DECJZ":
        if s[ins["counter"]] == 0:
            s["program_counter"] = ins["zero_pc"]          # NO decrement on zero
        else:
            s[ins["counter"]] -= 1
            s["program_counter"] = ins["nonzero_pc"]
    else:
        raise ValueError(f"unknown op {ins['op']!r}")       # closed registry: REJECT
    return s

def trace_hashes(program, initial_state, budget):
    st, out = initial_state, [state_hash(initial_state)]
    for _ in range(budget):
        if st["halted"]: break
        st = step(program, st)
        out.append(state_hash(st))
    return out
```

Differential gate (TC-03): `trace_hashes(...)` == the sequence of `state_hash`es reduced from the tape, for every witness program and every fuzz program. Fuzz manifest: `{"generator_version": "v1", "seed": 20260702, "program_count": 500, "max_program_len": 32, "max_steps": 4096}` stored in `fuzz/manifest.json`.

### 5.7 Gate verdict schema and evidence-root layout

```json
{"gate_id": "TC-07", "verdict": "PASS", "not_run_is_fail": true,
 "command": "python tools/theory/run_mutation_matrix.py --bundle tapes/copy_a_to_b.bundle",
 "exit_code": 0, "evidence": ["mutations/matrix.json", "mutations/m3_copy_a_to_b_audit.json"],
 "auditor_categories_tripped": ["ref_reconstruction"], "timestamp_utc": "…"}
```

```
turing/evidence/theory/turing_completeness_witness_YYYYMMDD/     (created during execution)
├── README.md                  # evidence_class: REAL_DETERMINISTIC_EXECUTION; no worker, no LLM
├── THEORY.md                  # layers 0–3 (§2.3): empirical vs citational, Minsky/Schroeppel cites
├── CLAIM_BOUNDARY.json        # turing_completeness_claim_allowed:false until TC-10 artifact path set
├── bundle_manifest.json / bundle_sha256s.txt        # mirror stage6 bundle shape (verified precedent)
├── programs/                  # instruction_schema_registry.v1.json + 8 program JSONs + digests
├── tapes/                     # one git bundle per program run (object-format=sha256)
├── traces/                    # reference-interpreter state-hash traces
├── fuzz/                      # manifest.json + differential results
├── mutations/                 # matrix.json + per-mutant auditor outputs (survivors = FAIL, kept)
├── noninterference/           # T1-vs-T2 interleave results + sabotage meta-test result
└── verdicts/                  # TC-01.json … TC-10.json (TC-10 slot: NOT_RUN until external)
```

### 5.8 Audit and independent-verification commands

```bash
# TC-04..TC-09 local audit (default registry once additive rows land):
python tools/bench/audit_micro_tape_decision_dag.py \
  --bundle evidence/theory/turing_completeness_witness_YYYYMMDD/tapes/copy_a_to_b.bundle \
  --out /tmp/tc_audit    # plus witness-specific reducer/differential/mutation runners

# TC-10 (executed by the independent cross-family verifier, NEVER the implementer):
git clone <repo> fresh && cd fresh && git checkout <exact_sha>
sha256sum -c evidence/theory/turing_completeness_witness_YYYYMMDD/bundle_sha256s.txt
<re-run all TC gates from the clean clone; write verifier-signed verdict OUTSIDE implementer custody>
```

Orchestrator discipline: each stage's exit gate is "all listed verdict JSONs exist with verdict PASS and `not_run_is_fail` honored"; the module tracker records ADDRESSED at TC4-complete and **never** writes CLOSED (Intent §5.2, §8.7).

---

## 6. ADR-ready decision records (MADR-style)

**ADR-M2-001 — Machine class: two-counter Minsky machine with generic interpreter core.** Context: the frozen obligations file (sha `7be0980e…`) prescribes a two-counter Minsky machine, but general two-operand multiplication is impossible on two counters (Schroeppel, AIM-257), and richer models (tag systems, Rule 110) carry 10–100× audit cost. Decision: implement an interpreter core generic over counter count, freeze the v1 tape schema to exactly `{program_counter, counter_a, counter_b, halted}`, define `multiply_small` as multiplication by a compile-time constant, and defer general multiply / Korec-U22 universal-program execution to an explicitly-labeled v2 stretch schema. Consequences: verbatim fidelity to the frozen spec; the universality citation chain (Minsky 1967 + Schroeppel 1972) attaches cleanly; a documented upgrade path exists without schema churn; the claim language permanently carries the I/O-encoding caveat.

**ADR-M2-002 — Registry integration: additive extension `ADDITIVE_TC_WITNESS_V1`, plus a self-consistency lint.** Context: none of the five witness event names exists in `turing/pack/04_registries/event_registry_v5_3_1.json`, whose `unknown_event_policy` is REJECT; the file already contains additive rows (`ADDITIVE_BENCHMARK_V1`, `ADDITIVE_AGENT_ECONOMY_V1_0`) but its `counts` block is stale (61 declared vs 62 actual). Decision: append the five TC rows with status `ADDITIVE_TC_WITNESS_V1` (four OBSERVATION/PRESERVE; `InstructionAuthorized` as AUTHORIZATION/ADVANCE→authorization_head with a deterministic predicate), reuse frozen `BudgetExhausted` for budget stops, coordinate through M0's governance chain, and land a registry self-consistency lint that fails on count/name-set drift. Because the Python `Tape` writer (`src/turingos/tape.py`) verifiably cannot advance `authorization_head` ("There is NO `refs/turingos/authorization_head` in 1.0" — docstring), the witness emitter appends exclusively through the Rust three-ref writer `crates/turing-git-tape/src/append.rs` (owner of `REF_AUTHORIZATION_HEAD`) from the start; this anticipates M1's canonical-owner designation and forecloses any improvised third ref-writer (F3 recurrence), with migration to a differently-designated owner only if M1 later so decides. Consequences: one closed registry remains the single authority and default audits validate witness bundles; the pre-existing counts defect is surfaced to M0 rather than silently patched; the witness incidentally produces the first non-fixture tape family where `authorization_head` advances.

**ADR-M2-003 — Universality argument: executable bounded witnesses + citation-based theory memo; no mechanized proof.** Context: G3 needs a credible claim, not a new theorem; mechanized options (Coq undecidability library) add a toolchain no other module uses. Decision: structure the argument in four labeled layers (interpreter correctness — empirical; bounded witness executions — empirical; machine-class universality — citational with the simulation-lemma template stated; substrate property — the actual claim), recorded in `THEORY.md`, with the exact permitted claim sentence and forbidden-phrase list in `CLAIM_BOUNDARY.json`. Consequences: the claim is externally defensible and precisely bounded ("universal up to resource bounds, subject to time and budget", with the Gödel-encoding caveat); no false implication of formal verification; future mechanization remains open as recorded non-scope.

**ADR-M2-004 — Differential oracle: independent minimal Python reference as a derived-view checker, never a tape writer.** Context: replay==reference is gate TC-03; the repo already suffers a canonical-bytes multi-owner defect (audit F3), and multiversion programming exhibits correlated failures (Knight–Leveson 1986). Decision: a ≤80-line stdlib-only Python reference interpreter, written from the obligations file alone (ideally by a different agent family), sharing no code with the Rust SUT except the canonical state-encoding definition; it emits state-hash traces and never appends to any tape; comparison covers full per-step traces, not final states. Consequences: genuine two-implementation evidence in the house's proven cross-impl style (C02 precedent); Art. 0.2's derived-view conservation discipline is satisfied; F3 does not gain a fourth owner.

**ADR-M2-005 — Load-bearing randomized testing via a seed-pinned stdlib generator; hypothesis/proptest confined to dev-time.** Context: the Python package declares zero dependencies and hypothesis is absent from the environment; evidence-grade artifacts must be tape-reconstructible, which shrink databases are not. Decision: the fuzz campaign that feeds gate evidence uses a stdlib `random.Random(seed)` program generator with a recorded manifest (generator version, seed, counts, bounds); Hypothesis (derandomize/CI profile) and proptest (rng_seed, persisted regressions) are permitted locally for bug-hunting but never cited as gate evidence. Consequences: the whole campaign replays byte-identically from the manifest; no dependency-posture change; the loss of shrinking is absorbed by small bounded programs.

**ADR-M2-006 — Non-halting evidence taxonomy: three certificate classes.** Context: the module must ship non-halting examples without ever implying the halting problem is decided. Decision: classify every non-halting artifact as C1 (static HALT-unreachability in the control-flow graph — sound because execution in this machine class stops only at HALT), C2 (exact state-recurrence via duplicate state hashes — sound for a deterministic machine), or C3 (budget-bounded observation via the frozen `BudgetExhausted` event — bounded claim only, "did not halt within N steps"); ship at least one example of each; state hashes exclude the step index so C2 is checkable in two lines. Consequences: honest, mechanically distinguishable non-halting evidence; the strongest available claim is made in each case and no stronger; external reviewers see the undecidability line drawn explicitly.

**ADR-M2-007 — Goodhart/economy non-interference as a three-layer mechanical gate.** Context: G3 requires that no market/PPUT/HCI shortcut can affect state transitions (Art. III.4 analog), and assertions without teeth rot. Decision: (1) interleave-invariance test — reduced machine state byte-identical with and without legal PRESERVE economy events interleaved; (2) sabotage meta-test — a deliberately market-reading reducer variant must fail test (1), proving non-vacuity; (3) static read-surface lint — the witness reducer consumes exactly the five TC event types plus `BudgetExhausted`. Consequences: the shielding property is demonstrated, self-verifying, and regression-locked; the pattern is reusable by M-track modules that must prove other projections are pure.

---

*End of report. All absolute paths cited were opened or executed on 2026-07-02 against `turing` HEAD `bed7597`. This report is a planning artifact: it confers no PASS/ADDRESSED/CLOSED status on anything, and the evidence root it describes is created during execution, not by this plan.*
