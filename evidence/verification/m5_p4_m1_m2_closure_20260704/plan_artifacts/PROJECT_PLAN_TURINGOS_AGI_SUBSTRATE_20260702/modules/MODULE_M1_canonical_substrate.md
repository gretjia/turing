# MODULE M1 — Canonical Substrate Integrity (G2)

- Version: 1.0.0 (2026-07-02). Planning artifact; confers no CLOSED/RATIFIED status.
- Grounding: `research/RES_M1_canonical_substrate_integrity.md` (sha256 pinned in `PROGRESS_TRACKER.md`), Intent §2 row G2, audit findings F3 (Python canonical-bytes second owner, C02 recurrence), F5 (worker identity not on tape), F7 (estimated cost only), R9 (`authorization_head` never PASS on a real run).
- Reconciliation: gate IDs, flags, and tool names here govern over the assumptions in `09_FINAL_CERTIFICATION_EVALS.md` §0.1 (its own reconciliation rule).

## 1. Written spec

### 1.1 Functional requirements

1. **Single canonical-bytes owner (R-M1-1 / ADR-M1-001/006):** designate `crates/turing-contracts/src/jcs.rs` (profile `turingos.jcs.v1`) the singleton owner; demote `src/turingos/codec.py` to a cross-checked derived view; land the CI gate quartet in the same change: (i) cross-impl byte-equality xcheck on an extended corpus (control chars, surrogate boundaries, non-ASCII values, U+2028/U+2029, integer extremes), (ii) grep gate banning `sort_keys=True` canonicalization and canonical-def names outside a reasoned allowlist, (iii) stdlib-AST lint catching aliased calls, (iv) ref-lint banning `update-ref refs/turingos/` outside the designated writer. Every gate must pass its own tamper self-test.
2. **Real-run authorization (R-M1-3 / ADR-M1-003; audit R9):** one real worker run wrapped in a headless gnome-keyring session (`dbus-run-session` + `gnome-keyring-daemon --unlock`) with `--authorization-mode required --authority-provider os-keyring`; strict audit passes `--require-authorization-head` with no LEGACY_MISSING. Passphrase from a 0600 file outside the repo; never on tape.
3. **Tape-canonical cost + worker identity (R-M1-4 / ADR-M1-004):** `CostEvent.v2` at the `WorkerAdapter` seam — mandatory `cost_source_kind ∈ {provider_receipt_inline, provider_usage_api_reconciled, bounded_estimate, fixture}`, integer micro-USD only, pinned `price_table_digest`, provider request IDs, provider usage verbatim including the DeepSeek cache-hit/miss split; auditor flag `--require-cost-provenance`; the word-count estimator abolished.
4. **Mutation-boundary sandbox gate (R-M1-5 / ADR-M1-005):** every substrate-driven mutation step under `runsc --rootless --network=none do`; runsc version + binary sha256 in the run manifest; `SandboxBoundaryAssumed`/HOST_ASSUMED PRESERVE event on self-test failure; auditor flag `--require-sandbox-provenance`. Upstream Docker scorer runtime untouched; OCI pinning deferred to the omega track.
5. **Python routing through the owner (R-M1-2 / ADR-M1-002):** phase 1 — batch-capable `turing jcs` CLI verb behind `codec.canonical_bytes`; phase 2 — new tapes appended only via turingd `event.append_preserve`; Python `Tape` demoted to a labeled test fixture; historical tapes never rewritten.

### 1.2 Non-functional requirements

- Forward-only: historical tapes/evidence are never rewritten; designation must cost zero byte churn (8/8 xcheck equality already proven — re-prove on the extended corpus BEFORE routing).
- Fail-closed: nonzero exit from the owner binary → reject, never fall back to a Python serializer; NOT_RUN blocks.
- Goodhart shielding: receipts and price tables live supervisor-side; the worker-safe packet leakage audit gains these fields in its blocklist (Art. III.4).
- Genesis-key separation: approval keys are host-minted by the signing backend and are categorically NOT the genesis key (red line §5.1).

### 1.3 Performance targets

- Full CI gate quartet ≤ 5 minutes on this host (grep/AST/ref-lint are seconds; xcheck bounded by corpus size — target corpus run ≤ 60 s).
- `turing jcs` subprocess overhead acceptable at current call rates (the repo already shells out to git per tape operation, RES_M1 §2.3); measure batch-mode throughput in ATOM-M1e-1 and record it in the evidence bundle.

### 1.4 Interfaces

| Artifact | Path (repo `/home/zephryj/turingos_backup/work/turing` unless noted) | Schema source |
|---|---|---|
| Owner codec | `crates/turing-contracts/src/jcs.rs` (existing) | profile `turingos.jcs.v1` |
| xcheck harness | `crates/turing-xcheck/` + `tools/gates/xcheck_emit.py` | RES_M1 §5.1 |
| Singleton gate | `tools/gates/gate_singleton_codec.sh` (exit 0/1/3, `--self-test`, `--wide`) | RES_M1 §5.2; gate_g10 pattern |
| CostEvent.v2 | tape event schema + `receipts/` files | RES_M1 §2.6, ADR-M1-004 |
| Sandbox events | `sandbox` block per mutation event; `SandboxBoundaryAssumed` PRESERVE event | RES_M1 §2.7, ADR-M1-005 |
| Auditor flags | `tools/bench/audit_micro_tape_decision_dag.py` gains `--require-cost-provenance`, `--require-sandbox-provenance` (existing `--require-authorization-head`) | RES_M1 §2.6–2.7 |
| ADRs | plan directory `adr/ADR-M1-001..006.md` | RES_M1 §6 |

### 1.5 Agentic considerations

- Execution order is load-bearing: M1a's gates land FIRST because they protect everything after (RES_M1 §3 execution order); M1e is deliberately last, protected by the already-green gates.
- The keyring session can hang on a locked keyring (headless prompt) — wrap all secret-tool calls in timeouts; timeout = NOT_RUN, which blocks and never passes (pitfall 5).
- M1 owns `crates/turing-contracts` + CI in the one-writer-per-tree partition (playbook §3.2); the `TapeReader` split is coordinated with M6 (ADR-M6-005).

### 1.6 Risks & mitigations

Adopt RES_M1 §4 items 1–14 verbatim as the module risk register. Highest-severity: (2) event-ID rigidity — serialization changes alter all future event IDs; designation is forward-only, byte-equality re-proven on the extended corpus before routing; (3) gate false positives destroying legitimate independence — the strict auditor's deliberate duplicate is allowlisted BY PATH with in-gate reasons; (7) genesis-key conflation — runbook language fixed in ADR-M1-003; (10) DeepSeek cache split — price table keys on (provider, model, token_class) or cost is wrong by up to ~50x.

### 1.7 Architecture guidance

Ports-and-adapters: the codec becomes a frozen port with one Rust adapter; Python consumes it across a process boundary (CLI now, daemon appends as end-state; PyO3 rejected this increment — ADR-M1-002). The three-ref tape model and daemon infrastructure already exist and already match what the strict auditor derives (RES_M1 §2.3).

## 2. KPIs

Intent §2 row G2 (verbatim): *"Single canonical-bytes owner; real-run authorization; tape-canonical cost — Cross-impl byte-equality gate green in CI; 0 canonical writers outside the designated owner (lint gate); ≥1 real worker run passing `--require-authorization-head`; 100% of LLM calls carry provider receipts or an explicit estimated-cost boundary on tape."*

Measurable sub-KPIs: (a) all 4 CI gates green, each with clean/tamper self-test evidence; (b) first-ever non-fixture `--require-authorization-head` PASS artifact; (c) 0 events with `cost_source_kind: unspecified` on any new tape; (d) float-cost tamper fixture rejected by CI; (e) 100% of mutation events carry a `sandbox` block or a preceding HOST_ASSUMED event.

## 3. Ship Gate (M1.G)

**Predicate (tracker M1.G row):** G2 KPIs — 0 canonical writers outside owner (lint), cross-impl equality in CI, ≥1 real authorized run, 100% LLM calls receipted/bounded; Drift-Check 7/7 with all phase verdicts re-checked. Verifier class: M5-class (custody-separated). NOT_RUN == FAIL.

**Required artifacts:**
1. ADR-M1-001 through ADR-M1-006 accepted (plan directory).
2. CI configuration + four gate scripts, each with a clean/tamper self-test transcript and a green run at a named repo SHA.
3. Real-run evidence root: keyring provider recorded, strict-audit verdict JSON with `--require-authorization-head` PASS, REAL label, no passphrase material anywhere.
4. CostEvent.v2 schema + a real tape segment with receipts + the rejected float-cost tamper fixture output.
5. Sandbox gate evidence: run manifest with runsc digest/version, mutation events with sandbox blocks, auditor `--require-sandbox-provenance` PASS.
6. Routing evidence: extended-corpus byte-equality proof (pre-routing), `turing jcs` verb tests, daemon-append path tests, Python `Tape` fixture label.
7. **Mandatory `PROGRESS_TRACKER.md` update** with evidence paths per playbook §6.2.

## 4. Evals

### 4.1 Automated

```bash
tools/gates/gate_singleton_codec.sh --self-test   # SELF-TEST PASS required (clean rc=0 / tamper rc=1)
tools/gates/gate_singleton_codec.sh               # rc 0 PASS | 1 FAIL | 3 NOT_RUN (blocks)
python3 tools/gates/xcheck_emit.py corpus.jsonl > py.tsv && cargo run -q -p turing-xcheck < corpus.jsonl > rs.tsv && diff py.tsv rs.tsv
```
Plus the AST lint, ref-lint, and the strict auditor with all three `--require-*` flags; every command's exit code recorded in the gate verdict.

### 4.2 Scenario / LLM-judge

Scoped-down FCE-S1 fragments (09 §3): a fresh-context agent is given only the M1b evidence root and asked to state (i) whether the authorization PASS is REAL or FIXTURE and (ii) which keyring provider was used. Rubric: PASS iff both answers are derivable and derived from the artifacts alone (README label + verdict JSON), with no appeal to implementer narrative. A second fragment: agent recomputes one receipt's cost from usage × pinned price table and matches the tape value exactly (integer micro-USD).

### 4.3 Performance

Gate-quartet CI wall-clock ≤ 5 min; xcheck corpus run ≤ 60 s; `turing jcs` batch throughput measured and recorded (target: no worse than 2x the current Python serializer at batch sizes ≥ 100). Bounds recorded in M1a/M1e evidence, enforced as regression alarms not hard gates.

### 4.4 Sandboxed harness

M1d's own deliverable IS the sandbox eval: run-start self-test `runsc --rootless --network=none do <probe>` (RES_M1 §2.7, EXECUTED-verified on this host); one scripted mutation step executed under runsc with the `sandbox` block asserted on the resulting tape event; the HOST_ASSUMED path exercised once against a deliberately broken runsc PATH to prove the exception event fires.

### 4.5 Thresholds

4/4 gates green + 4/4 self-tests discriminating; extended corpus equality 100% (any diff line = FAIL); authorization strict audit PASS with zero LEGACY_MISSING; 0 `cost_source_kind: unspecified`; float-fixture rejection = required FAIL of the tamper input; sandbox self-test PASS on this host (HOST_ASSUMED on this host during M1 evals = FAIL, since runsc is proven available).

### 4.6 Runnable instructions

RES_M1 §5.1–5.5 carries the verified command shapes verbatim (xcheck job, singleton lint, keyring-session wrapper with strict audit, runsc self-test). Execute from `/home/zephryj/turingos_backup/work/turing` with `. ~/.cargo/env`; expected outputs are annotated in the report (XCHECK_PASS, SELF-TEST PASS, auditor PASS verdict JSON).

## 5. Dependencies

- Upstream: M0 (authority chain + GateVerdict.v1 machinery); owner activation for all repo writes (playbook §1 step 6).
- Internal: M1a precedes M1b/M1c/M1d/M1e (playbook §3.1).
- Downstream: M1c is a HARD PREREQUISITE for M3 (receipts) and M4 (H-VPPUT inputs); M1d for M3 (sandbox kind constant within the experiment); M1b feeds M5.P3 packet candidates; M2's emitter uses the designated owner path post-M1a.

## 6. Effort estimate + parallelization

- Tiering: gate predicates + self-tests = xhigh; keyring real run, CostEvent.v2 plumbing, adapter = high; running pre-specified sequences, evidence packaging = medium.
- Wall-clock estimate: M1a ≈ 1–2 agent-days (gates + corpus + CI wiring); M1b ≈ 0.5–1 day (session wrapper + one real run + audit); M1c ≈ 1–2 days (schema + adapter + auditor flag); M1d ≈ 0.5 day; M1e ≈ 1–2 days (routing + re-proof). Module total ≈ 4–7 agent-days.
- Parallelization: waves W1 (M1a) and W2 (M1b ∥ M1c ∥ M1d) per playbook §3.2; M1e in W3.

---

## Phases and atoms

Authoritative status lives in `PROGRESS_TRACKER.md` (M1 table).

### M1a — Singleton owner + CI gate quartet

#### ATOM-M1a-1 — ADR-M1-001/002/006 drafted in the plan directory. Gate: MADR front matter valid; allowlist rationale included.
#### ATOM-M1a-2 — Extended xcheck corpus + `turing-xcheck` harness + Python emitter. Gate: 100% byte equality incl. non-ASCII vector.
#### ATOM-M1a-3 — grep + AST + ref-lint gates with `--self-test`. Gate: each discriminates clean/tampered fixtures.
#### ATOM-M1a-4 — CI wiring; all four jobs green at a named SHA. Gate: CI run artifact.

### M1b — Real-run authorization

#### ATOM-M1b-1 — ADR-M1-003 drafted; keyring runbook (passphrase discipline, timeouts). Gate: ADR accepted; runbook names the NOT_RUN-on-timeout rule.
#### ATOM-M1b-2 — Unlocked-keyring session wrapping one real worker run; strict audit with `--require-authorization-head`. Gate: non-fixture PASS, no LEGACY_MISSING; evidence root labeled REAL with keyring provider recorded.

### M1c — CostEvent.v2 + worker identity

#### ATOM-M1c-1 — ADR-M1-004 drafted; schema + pinned price table (keys: provider, model, token_class). Gate: schema validates; DeepSeek split present.
#### ATOM-M1c-2 — WorkerAdapter seam implementation + receipts files + tape events. Gate: one real call produces a complete receipt; keys/auth headers absent.
#### ATOM-M1c-3 — Auditor `--require-cost-provenance` + float-cost tamper fixture. Gate: fixture rejected; flag PASS on the real segment.

### M1d — runsc mutation-boundary gate

#### ATOM-M1d-1 — ADR-M1-005 drafted; run-start self-test + `sandbox` block emission + HOST_ASSUMED path. Gate: self-test PASS on this host; broken-PATH drill emits the PRESERVE event.
#### ATOM-M1d-2 — Auditor `--require-sandbox-provenance`. Gate: PASS on a sandboxed run; FAIL on a fixture missing the block.

### M1e — Python routing through the owner

#### ATOM-M1e-1 — `turing jcs` CLI verb (batch mode) + byte-equality re-proof on the extended corpus BEFORE routing. Gate: equality 100%; throughput recorded.
#### ATOM-M1e-2 — Route `codec.canonical_bytes` through the verb; fail-closed on nonzero exit. Gate: test suite green; gates still green.
#### ATOM-M1e-3 — New-tape appends via turingd `event.append_preserve`; Python `Tape` demoted to labeled fixture. Gate: historical tapes byte-unchanged; auditor reads both generations.

### M1.G — Module gate

#### ATOM-M1.G-1 — Assemble §3 artifact list; run §4 evals; hand to M5-class custody-separated verifier. Gate: Drift-Check 7/7; status ceiling ADDRESSED.
