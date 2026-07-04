# MODULE M2 — Turing-Completeness Witness (G3)

- Version: 1.0.0 (2026-07-02). Planning artifact; confers no CLOSED/RATIFIED status. No Turing-completeness claim exists or is implied by this file (Intent §5.3).
- Grounding: `research/RES_M2_turing_completeness_witness.md` (sha256 pinned in `PROGRESS_TRACKER.md`), Intent §2 row G3, the frozen obligations file `turing/evidence/bench/swe_bench_verified_500_campaign_20260629/TURING_COMPLETENESS_PROOF_OBLIGATIONS_20260629.md` (sha256 `7be0980e…` — STOP if drifted).
- Reconciliation: gate IDs/tool names here govern over `09_FINAL_CERTIFICATION_EVALS.md` §0.1 assumptions.

## 1. Written spec

### 1.1 Functional requirements

1. Two-counter Minsky machine witness with a generic n-counter interpreter core; v1 tape schema fixed verbatim to the obligations file's `{program_counter, counter_a, counter_b, halted}`; `multiply_small` defined as multiplication by a compile-time constant (general multiply is an explicitly labeled v2 stretch — ADR-M2-001, Schroeppel caveat).
2. Independent Python reference interpreter ≤80 lines, stdlib only, `tools/theory/reference_interpreter.py`, written from the obligations file alone (ideally by a different agent/family); mandatory DECJZ edge-order unit test (if counter==0 jump to `zero_pc` WITHOUT decrement, else decrement and go to `nonzero_pc`). The reference never writes a tape.
3. Rust crate `turing-witness` (interpreter core + tape emitter + reducer) appending through the existing canonical append path (post-M1a designated owner; until then the single existing `Tape` writer) — it must NOT become canonical-owner #4 (RES_M2 pitfall 7; F3 recurrence).
4. Closed-registry discipline: instruction schema registry + payload schemas (integers/strings/bools only — auditor codec subset); additive registry rows proposed via M0's chain; the pre-existing 61/62 registry-count defect is REPORTED to M0, never silently fixed (TC0).
5. Runs and evidence: 5 halting + 3 non-halting programs (non-halting certificates classed C1/C2/C3), git bundles (object-format sha256), seed-pinned stdlib fuzz campaign (T1); evidence root `turing/evidence/theory/turing_completeness_witness_YYYYMMDD/` per the RES_M2 §5.7 layout, labeled `REAL_DETERMINISTIC_EXECUTION`.
6. Audit battery: differential equality vs the reference, mutation matrix m1–m7 (surviving mutants recorded as FAILs, never deleted), interleave-invariance non-interference gate WITH sabotage meta-test (so it can never pass vacuously), replay-twice determinism → verdict JSONs TC-01..TC-09.
7. External closure: exact-SHA packet published; TC-10 run by an independent cross-family verifier on a clean clone — by construction not executable by the implementer. `CLAIM_BOUNDARY.json` sets `turing_completeness_claim_allowed: false` until the TC-10 artifact path exists.

### 1.2 Non-functional requirements

- Fully deterministic, token-free, zero LLM spend; every stage resumable from tracker + tape alone.
- Machine state is a derived fold of tape events (Art. 0.2), mirroring the proven `reduce.py`/`replay.py` idiom.
- Claim language after all gates is locked to the RES_M2 §3 permitted sentence (Minsky 1967; Schroeppel 1972 caveat included); the unqualified sentence "TuringOS is Turing-complete" is permanently forbidden.
- Hypothesis/proptest artifacts are dev-time only; load-bearing fuzz evidence comes exclusively from the seed-pinned T1 campaign.

### 1.3 Performance targets

- Estimated total code ≈ 1.5–3k lines including tests (RES_M2 §3); no per-run wall-clock constraint, but the replay-twice determinism check must produce byte-identical verdicts, and each gate run must complete unattended (no interactive steps).
- Fuzz campaign size and seed are pinned in its manifest; runtime bounded by a step-count cap per program (the C3 non-halting language is locked to "did not halt within N steps").

### 1.4 Interfaces

| Artifact | Path (repo `turing/`) | Schema source |
|---|---|---|
| Reference interpreter | `tools/theory/reference_interpreter.py` (+ tests) | RES_M2 §5.6 skeleton |
| Rust crate | `crates/turing-witness/` | RES_M2 §3 |
| Instruction schema registry | `evidence/theory/.../programs/instruction_schema_registry.v1.json` | RES_M2 §5.4 |
| Gate verdicts | `evidence/theory/.../verdicts/TC-01.json … TC-10.json` (TC-10 slot NOT_RUN until external) | RES_M2 §5.7 |
| Evidence root | `evidence/theory/turing_completeness_witness_YYYYMMDD/` full layout | RES_M2 §5.7 |
| ADRs | plan directory `adr/ADR-M2-001..007.md` | RES_M2 §6 |

### 1.5 Agentic considerations

- An orchestrator can run TC0→TC5 unattended with zero judgment calls — every stage's exit gate is "all listed verdict JSONs exist with verdict PASS and `not_run_is_fail` honored" (RES_M2 §5.8 discipline).
- The reference interpreter should be delegated to a different agent context (ideally different model family) fed ONLY the obligations file, to break correlated-failure blindness (pitfall 4).
- M2 owns `crates/turing-witness` + `tools/theory/` in the write partition (playbook §3.2); no repo mutation beyond those trees plus its evidence root.

### 1.6 Risks & mitigations

Adopt RES_M2 §4 items 1–12 verbatim. Highest-severity: (1) the Schroeppel overclaim — caveat baked into the permitted claim sentence, `THEORY.md`, and the machine-readable forbidden-phrase list; (7) becoming canonical-owner #4 — emitter reuses the designated append path, lint asserts `tools/theory/` contains no tape-append calls; (10) self-closure of the namesake gate — TC-10 is structurally external; module ceiling ADDRESSED.

### 1.7 Architecture guidance

Four ports: interpreter core (pure function), emitter (tape adapter), reducer (derived view), reference (independent checker). Payloads restricted to the auditor codec subset (no floats, ASCII keys). Non-interference gate mechanically demonstrates market/PPUT/HCI signals cannot touch transitions, including the sabotage meta-test (RES_M2 §2.9).

## 2. KPIs

Intent §2 row G3 (verbatim): *"Executable Turing-completeness witness under MicroTape rules — Gates TC-01..TC-10 all PASS; halting and non-halting examples; replay == reference interpreter; independent audit from clean clone; no market/PPUT/HCI shortcut affects transitions."*

Measurable sub-KPIs: (a) 9/9 verdict JSONs TC-01..TC-09 PASS locally; (b) 7/7 mutation operators with kill evidence (survivors = recorded FAILs); (c) sabotage meta-test fires (non-interference gate proven non-vacuous); (d) TC-10 external verifier artifact exists at a cited path, produced from a clean clone; (e) `turing_completeness_claim_allowed` flips true only when (d) holds.

## 3. Ship Gate (M2.G)

**Predicate (tracker M2.G row):** G3 KPI — TC-01..TC-10 PASS; permitted claim language only per RES_M2 §3; Drift-Check 7/7; claim boundary keeps `turing_completeness_claim_allowed:false` until the TC-10 artifact path exists. Verifier class: M5-class. NOT_RUN == FAIL. Implementer ceiling for TC0–TC4 completion: ADDRESSED.

**Required artifacts:**
1. ADR-M2-001 through ADR-M2-007 accepted (plan directory).
2. Obligations-file pin verification transcript (`7be0980e…`).
3. Instruction schema registry + payload schemas + registry self-consistency lint output (including the report of the pre-existing 61/62 defect filed to M0).
4. Reference interpreter + unit tests (DECJZ edge-order test green) with authorship provenance note (which agent context, fed what).
5. `turing-witness` crate + reducer conservation test transcript.
6. Full evidence root per RES_M2 §5.7 (README with `evidence_class: REAL_DETERMINISTIC_EXECUTION`, THEORY.md, CLAIM_BOUNDARY.json, bundles, traces, fuzz manifest, mutation matrix, non-interference results, verdicts).
7. Exact-SHA external packet + TC-10 slot status (NOT_RUN until the external verifier writes it).
8. **Mandatory `PROGRESS_TRACKER.md` update** with evidence paths per playbook §6.2.

## 4. Evals

### 4.1 Automated

- Registry self-consistency lint (RES_M2 §5.3): exit 0 = PASS.
- Reference unit tests incl. DECJZ edge-order: `python3 -m pytest tools/theory/ -q`, exit 0.
- Reducer conservation test: `cargo test -p turing-witness --tests`, exit 0.
- TC-04..TC-09 audit battery via the strict auditor + witness-specific runners (RES_M2 §5.8); each emits its verdict JSON with `not_run_is_fail: true`.

### 4.2 Scenario / LLM-judge

Scoped-down FCE-S2 pattern (09 §3): a fresh-context agent on a pristine checkout at the pinned SHA re-runs TC-01..TC-09 from the evidence root's own instructions and reports each verdict. Rubric (mechanical): PASS iff 9/9 re-derived verdicts match the stored JSONs byte-meaningfully AND the agent's report contains no claim-language violation (judge greps the report against the CLAIM_BOUNDARY forbidden-phrase list — any hit = FAIL).

### 4.3 Performance

Replay-twice determinism: two runs of the full reducer/audit over the same bundles produce identical verdicts (byte-compare); fuzz campaign completes within its manifest's step/seed budget; record wall-clock per gate in the verdicts (operational data, no hard bound).

### 4.4 Sandboxed harness

No repo mutation occurs in witness runs; execution under `runsc --rootless --network=none` where available, with HOST_ASSUMED recorded otherwise (RES_M2 §2.10 posture, RES_M1 §2.7 mechanics). On this host runsc is proven available, so witness evidence produced here must not carry HOST_ASSUMED.

### 4.5 Thresholds

TC-01..TC-09: 9/9 PASS; mutation matrix: 7/7 operators exercised, kill evidence per operator, 0 silently deleted survivors; sabotage meta-test: required FAIL of the sabotaged fixture; replay-twice: byte-identical; TC-10: external artifact present for module closure (absent = module stays ADDRESSED, never re-labeled).

### 4.6 Runnable instructions

RES_M2 §5.2 (freeze commands), §5.3 (lint), §5.8 (audit + TC-10 clean-clone procedure) carry copy-pasteable commands with expected outputs. Entry check every session:

```bash
cd /home/zephryj/turingos_backup/work/turing
sha256sum evidence/bench/swe_bench_verified_500_campaign_20260629/TURING_COMPLETENESS_PROOF_OBLIGATIONS_20260629.md
# expect 7be0980ee1a3ddf157f65096180c836341da548debcc93fe6957f355a7cf7cae — STOP if drifted
```

## 5. Dependencies

- Upstream: M0 (registry rows proposed via the M0 chain; GateVerdict machinery); owner activation for repo writes. Soft dependency on M1a: the emitter uses the designated owner path once it lands, and the single existing `Tape` writer until then (no hard block either way — playbook §3.2 W1 note).
- Downstream: TC5's packet feeds M5 (TC-10 is executed by M5-class machinery); M2 completion is an HCI-B precondition (ADR-M6-001).

## 6. Effort estimate + parallelization

- Tiering: gate design, mutation matrix, non-interference sabotage test = xhigh; `turing-witness` crate = high; running/exporting programs, packaging = medium.
- Wall-clock estimate: TC0 ≈ 0.5–1 agent-day; TC1 ≈ 0.5 day (small by design, ≤80 lines + tests); TC2 ≈ 1–2 days; TC3 ≈ 0.5–1 day; TC4 ≈ 1–2 days; TC5 packaging ≈ 0.5 day (external verification latency separate). Module total ≈ 4–7 agent-days, zero LLM spend.
- Parallelization: TC0–TC2 in wave W1 (parallel with M1a), TC3–TC4 in W2, TC5→TC-10 in W4; TC1 delegable to a separate agent family concurrently with TC2.

---

## Phases and atoms

Authoritative status lives in `PROGRESS_TRACKER.md` (M2 table).

### M2.TC0 — Freeze

#### ATOM-TC0-1 — Verify obligations pin `7be0980e…`; STOP on drift. Gate: transcript recorded.
#### ATOM-TC0-2 — Instruction schema registry + payload schemas; DECJZ semantics written into the registry. Gate: schemas validate; codec subset respected.
#### ATOM-TC0-3 — Additive registry rows proposed via M0 chain; self-consistency lint; 61/62 defect reported to M0. Gate: lint output + M0 filing.
#### ATOM-TC0-4 — ADR-M2-001..007 drafted. Gate: front matter valid.

### M2.TC1 — Reference interpreter

#### ATOM-TC1-1 — `reference_interpreter.py` ≤80 lines from the obligations file alone (separate agent context preferred) + unit tests incl. DECJZ edge order. Gate: tests green; authorship provenance recorded; zero tape-append calls in `tools/theory/` (lint).

### M2.TC2 — Rust witness crate

#### ATOM-TC2-1 — Interpreter core (pure, generic over counter count) + emitter via existing canonical append path. Gate: crate tests green; no new canonical-bytes code (M1a gates green).
#### ATOM-TC2-2 — Reducer + conservation test (Art. 0.2 idiom). Gate: conservation test green.

### M2.TC3 — Run/export

#### ATOM-TC3-1 — Execute 5 halting + 3 non-halting programs; class C1/C2/C3 certificates; export git bundles + manifest. Gate: bundles + digests on record.
#### ATOM-TC3-2 — Seed-pinned T1 fuzz campaign into the evidence root. Gate: manifest with seed; differential results recorded.

### M2.TC4 — Audit

#### ATOM-TC4-1 — Differential equality vs reference on all programs + fuzz corpus. Gate: TC-04 verdict PASS.
#### ATOM-TC4-2 — Mutation matrix m1–m7 (state-chain mutants m3/m5 mandatory); survivors recorded as FAILs. Gate: matrix + per-mutant outputs.
#### ATOM-TC4-3 — Interleave-invariance + sabotage meta-test; replay-twice. Gate: verdicts TC-01..TC-09 all PASS; sabotage fixture FAILs as required.

### M2.TC5 — External packet

#### ATOM-TC5-1 — Exact-SHA packet published; TC-10 slot NOT_RUN; hand to M5-class cross-family verifier (clean clone). Gate: packet digests recorded; implementer stops at ADDRESSED.

### M2.G — Module gate

#### ATOM-M2.G-1 — Assemble §3 artifact list; run §4 evals; Drift-Check 7/7. Gate: module ADDRESSED; EXTERNALLY_VERIFIED only when the TC-10 artifact is cited.
