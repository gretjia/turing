# MODULE M4 — Self-Improvement & North-Star Metrics (G5)

- Version: 1.1.0 (2026-07-02). Planning artifact; confers no CLOSED/RATIFIED status. Firm (zero PROVISIONAL content). Regenerated at M4.P0b from the landed research report `research/RES_M4_self_improvement_metrics.md` including its Revision 1.1 (§2.7 receipt binding, §2.8 broadcast-rule lifecycle, §5.7 worked FIXTURE example, §5.8 lifecycle audits, pitfalls P11–P14, ADR-M4-006/-007). Supersedes v1.0.0 of the same date (which predated Rev 1.1 and carried terse atoms) and, transitively, 0.1.0-PROVISIONAL. Re-pin via a tracker Decision Log entry is REQUIRED for both this file and RES_M4 (on-disk RES_M4 digest `a21178f2af435d7add39927abbe49b5b4825c24478c3eba2e1b358992c6ca2e8` differs from the pinned `30244d86…` because Rev 1.1 was append-only — flagged in RES_M4's own header, line 10).
- Grounding: `research/RES_M4_self_improvement_metrics.md` (RES_M4; every "§x.y" citation below resolves there), Intent §2 row G5 and §5.4–5.5, audit finding F7 (H-VPPUT unmeasurable — estimated cost only; failure-memory efficacy lineage-proven only, zero causal evidence).
- Schema authority: everything cost-shaped defers to ADR-M1-004 CostEvent.v2 (playbook §3.5; RES_M4 header note). M4 owns no tape schema — it is a pure derived-view consumer of M1c receipts and M3 frozen outputs; the one tape-event addition it needs (`BroadcastRuleRetired`, RES_M4 §2.8) is PROPOSED to M1 as schema owner, never landed by M4.

## 1. Written spec

### 1.1 Functional requirements

1. **H-VPPUT metric spec (RES_M4 §2.2 candidate B, ADR-M4-001):** money-denominated H-VPPUT — per task, `progress ∈ {0,1}` from upstream-harness results, cost = Σ `computed_cost_microusd` over ALL of the task's CostEvent.v2 receipts (failed attempts included, per the ADR-PPUT-North-Star C_i definition), time = Σ `wall_clock_ms`; computed OFF-tape by a frozen stdlib-only script as exact integer numerator/denominator pairs plus decimal strings (no JSON floats — the tape carries inputs, projections are rebuildable); portfolio (ratio-of-sums) aggregates with cluster-by-task bootstrap CIs (RES_M3 §5.6 machinery) are the reported quantities; token-only H-VPPUT and cost-only primary metrics are REJECTED per RES_M4 §2.2 A/C (kept only as companion aggregates) (M4.P1).
2. **Two-class cost discipline (RES_M4 §2.3, ADR-M4-002):** run class computed mechanically from the closed `cost_source_kind` enum — BILLING_COMPLETE (100% receipt/reconciled → point estimate), BOUNDED (well-formed `bounded_estimate` with `bound_kind` → lower-bound H-VPPUT via upper-bound cost, never a point estimate), INADMISSIBLE (absent/`unspecified`/non-enum/`fixture`-in-REAL → excluded, listed per run with offending event refs); class breakdown (`n_billing_complete / n_bounded / n_excluded`) is a mandatory headline field; pre-M1c tapes permanently INADMISSIBLE, legacy numbers only in a labeled non-H-VPPUT appendix (M4.P1).
3. **Receipt-to-tape binding verification, read side (RES_M4 §2.7 rules 1–6, ADR-M4-007):** the metric script re-verifies every `provider_receipt_inline` event against the per-provider field set keyed by `usage_schema` (verbatim `usage`, `model_reported`, `provider_request_id`, `request_sha256`/`response_sha256`, `price_table_digest`) and HARD-FAILS on a mislabeled event — misclassification is a defect, never silently reclassified at read time; costing recomputes via deterministic ceiling arithmetic per (provider, model, token_class); `provider_usage_api_reconciled` is accepted only with a Layer-2 bucket citation within a pre-stated tolerance; streaming is forbidden in measured arms (usage-omission hazard, pitfall P11) (M4.P1).
4. **Held-out registry (RES_M4 §2.4, ADR-M4-004):** `heldout_task_registry.v1.json` generated from M3's frozen S01 shard manifest (S01-as-frozen is the held-out set for this increment; H-VPPUT is computed post-hoc over M3's frozen S01 outputs, no new worker calls — FCE §1.2); sole task-selection input to H-VPPUT; supervisor-side only, outside every worker-visible tree; metric script hard-fails on out-of-registry receipts; leakage sweep gains `hvpput` + registry-filename markers (M4.P1).
5. **Failure-memory causal analysis (RES_M4 §2.5 A/C, ADR-M4-003):** confirmatory content = digest-pinned verbatim copy of M3's pre-registered H2 result (arm B vs arm C); no new confirmatory statistics — a second pipeline reaching a different number would be a defect, not insight; mechanism analyses (dose-response over `consumed_broadcast_rule_ids`, memory-cost accounting, lineage tables via `audit_failure_memory_activation.py`) stamped EXPLORATORY with `causal_claim_allowed: false` — the stage14 idiom; the sentence "failure memory causally improves solve probability" is permitted iff H2 passed with positive direction (M4.P2).
6. **Broadcast-rule lifecycle measurement + retirement proposal (RES_M4 §2.8, §5.8, ADR-M4-006):** audit the five existing lifecycle stages (mine → certificate → cluster-gated activation → consumption; Stage10 denylist + attestation sweep re-run with M4's added markers) and produce the exploratory per-rule lifecycle table (consumption, injection cost from receipts, post-consumption outcomes); PROPOSE the missing sixth stage — supervisor-side append-only `BroadcastRuleRetired` event with reason enum + active-set filter + pre-registered per-capsule injection budget — to M1 as schema owner (Art. II.1 context-pollution discipline; feeds FCE-C1's injection-budget design); claim ceiling per lifecycle stage: stages 1–4 license protocol claims only, efficacy language stays gated on H2 (M4.P2).
7. **North-star metrics report (RES_M4 §2.6, ADR-M4-005):** report skeleton (headline class breakdown, per-arm portfolio H-VPPUT or bounds, Δ_BC + CI + MDE verbatim from the M3 pre-registration, the three mandatory sentence templates for positive/null/negative, `CLAIM_BOUNDARY.json`, always-present exclusion/deviation tables) frozen with sha256 BEFORE any M3 output is read; assembled report must diff-conform to the skeleton regardless of result direction — "no measurable self-improvement" is a first-class, publishable PASS (M4.P3).

### 1.2 Non-functional requirements

- PPUT/heldout internals never worker-visible (Art. III.4; Intent §5.5): enforced by re-running `audit_prompt_leakage.py` (markers verified at `turing/tools/bench/audit_prompt_leakage.py:16–28`) plus the added `hvpput`/registry-filename greps over all worker-visible artifacts of consumed runs (RES_M4 §2.4); `WorkerPromptShield` remains the in-loop guard, `HeldoutGuardViolation` the tripped-guard event family (RES_M4 §2.1).
- Zero `cost_source_kind` absent/`unspecified`/non-enum values in any admitted H-VPPUT input; bounded estimates carry `bound_kind` derivations; BILLING_COMPLETE is reachable from Layer-1 inline `usage` alone — no plan/key-gated org-level API on the critical path (RES_M4 §2.3, §2.7 Layer 2, ADR-M4-007).
- Analysis is read-only over frozen M3 artifacts (input-digest table must match M3's published digests, RES_M4 §5.4); no confirmatory re-runs (FCE §1.2: S01 confirmatory results are never re-run).
- Byte-reproducibility: the frozen script re-emits byte-identical JSON on re-run (integer pairs + decimal strings, sorted keys, zero float tokens); every number in the north-star report is a pure function of digest-pinned inputs (Intent §6 replayability; RES_M4 §3).
- Totals reconcile against the strict auditor's cost-conservation numbers (`audit_micro_tape_decision_dag.py:738–776`); any tape receipt not consumed by the script is a FAIL (RES_M4 §4 P7).
- All rule-surface audits keep the Stage10 denylist as necessary-not-sufficient (lowercase-substring sweep is paraphrase-bypassable, pitfall P14): attestation booleans asserted by the generator and independently swept.

### 1.3 Performance targets

- Pure post-processing: full H-VPPUT pass over the M3 corpus in minutes (target ≤30 min wall-clock; record actuals in the report). Zero LLM spend across P1–P3 — exploratory and lifecycle analyses are tape/file post-processing only (RES_M4 §2.5 C, §5.8).
- Fixture self-test (RES_M4 §5.7 worked example) completes in seconds and runs at every session bootstrap that touches M4 artifacts.

### 1.4 Interfaces

Inputs: CostEvent.v2 receipt events (RES_M1 §5.5 shape; `worker_call_receipt.v1` per RES_M3 §5.3; provider `usage` field sets per RES_M4 §2.7 Layer-1 table), M3 frozen evidence root (per-arm `evaluation_results.json`, `UPLIFT_REPORT.json`, receipts, ablation-honesty audit output, `DEVIATIONS.md`), M3 pre-registration shard manifest (S01), pinned integer price table via `price_table_digest`, lifecycle tape events (`FailureNode`, `FailureCertificate`, `BroadcastRuleActivated`, `WorkCapsuleBuilt` — verified shapes in RES_M4 §2.8 table).

Outputs (evidence-area layout fixed by RES_M4 §5.1 — plan directory until repo writes are authorized, then `turing/evidence/bench/selfimprove_northstar_<date>/`): `heldout_task_registry.v1.json`, `metric/compute_hvpput.py` + `metric/selftest_fixture/`, `inputs/INPUT_DIGESTS.json`, `hvpput_report.v1.json`, `causal/h2_consumption_note.json`, `causal/exploratory/*.json` (incl. `rule_lifecycle_table.json`, RES_M4 §5.8), `NORTHSTAR_REPORT.md`, `CLAIM_BOUNDARY.json`, plus the `BroadcastRuleRetired` proposal packet addressed to M1 (RES_M4 §2.8). ADRs: plan directory `adr/ADR-M4-001..007` (texts in RES_M4 §6).

### 1.5 Agentic considerations

- Orchestration order is pre-answered in RES_M4 §5.6 (freeze script+skeleton+registry-generator → digests+registry+invisibility sweep at M3 freeze → metric run + conservation reconcile → causal consumption + stamped exploratory → report assembly → M5-class hand-off). Do not re-derive it.
- P1's freeze half is plan-directory/W0-adjacent work runnable on FIXTURE data before M3 finishes (the §5.7 worked example is the fixture); the strongest drift temptation in this module is a metric or phrasing chosen after seeing results — the skeleton freeze (ADR-M4-005) exists precisely to kill it. Freeze digests must demonstrably PREDATE any read of M3 outputs.
- M4 writes analysis artifacts only; it owns no tape writers, no worker paths, no gates other modules consume (write-partition discipline, playbook §3.2). The `BroadcastRuleRetired` event is a proposal artifact handed to M1, not an M4 write.
- Confirmatory numbers are copied, never recomputed with new code (RES_M4 §5.5); any sub-agent that finds itself writing statistics code for H2 is off-spec — stop, record scope-creep per playbook §4.3.

### 1.6 Risks & mitigations

Adopt RES_M4 §4 P1–P14 verbatim as the risk register. Highest-severity: P1 metric Goodharting → hidden-evaluator rule + leakage sweep + `WorkerPromptShield` + FCE-B2 re-test; P2 cost-incompleteness laundering → structural two-class discipline (mixed reporting unrepresentable in the report schema); P3 causal overclaim from lineage → H2-verbatim rule + `causal_claim_allowed: false` stamps (the stage14 lesson); P7 denominator gaming → auditor-conservation reconciliation, ALL attempts counted; P10 self-closure → M5-class verifier for M4.P3/M4.G. Rev 1.1 additions: P11 silent usage loss on streamed calls → streaming forbidden in measured arms + read-side field-completeness hard-fail; P12 rule pile-up without retirement → ADR-M4-006 retirement proposal + pre-registered injection budget + receipt-visible injection cost; P13 reconciliation laundering → Layer-2 upgrade only with bucket citation + tolerance, never rescuing INADMISSIBLE runs; P14 denylist bypass by paraphrase → templated supervisor-side rule text, length caps, attestations independently swept.

### 1.7 Architecture guidance

Four small components, all new code stdlib-only (RES_M4 §3): (i) frozen metric script `compute_hvpput.py` (skeleton RES_M4 §5.2, worked fixture §5.7) including the §2.7 read-side receipt-binding verifier; (ii) registry generator + invisibility sweep commands (RES_M4 §5.3); (iii) report assembler over the frozen skeleton; (iv) exploratory post-processors (dose-response, memory-cost, `rule_lifecycle_table.json` builder, RES_M4 §5.5/§5.8). Everything else reuses turing-pput shapes, the strict auditor's conservation checks, RES_M3 §5.6's bootstrap machinery, and the existing leakage/taxonomy/activation auditors (`audit_prompt_leakage.py`, `audit_failure_taxonomy.py`, `audit_failure_memory_activation.py` — verified paths in RES_M4 §2.1/§2.8). Single-implementation rule for aggregates: M4's script reproduces RES_M3 §5.6's aggregation and both reports cite the same script hash (P8).

## 2. KPIs

Intent §2 row G5 (verbatim): *"Failure memory causally improves solve probability; verified progress efficiency is measurable — Ablation delta from G4; H-VPPUT computed on held-out tasks with billing-complete (or explicitly bounded) cost; PPUT/heldout internals never visible to workers."* The KPI framing is measurement validity, not direction (Intent §5.5 anti-Goodhart; RES_M4 §3): the first clause is satisfied by a VALID causal measurement whose claim language is gated on H2's outcome, never by asserting efficacy.

Measurable sub-KPIs: (a) `hvpput_report.v1.json` recomputes byte-identically from tape receipt events + harness results + the held-out registry ONLY (FCE-B1 check 8 shape, 09 §5); (b) run-class breakdown present with zero INADMISSIBLE runs silently dropped (RES_M4 §2.3); (c) 100% of admitted `provider_receipt_inline` events pass the §2.7 field-set re-verification; (d) causal section equals M3's H2 verbatim (digest match) and its phrasing satisfies FCE-B1 check 6's reporting-honesty rule (null = "Δ = x [CI], powered for MDE = y", never "no effect"); (e) every exploratory/lifecycle artifact carries `causal_claim_allowed: false`; (f) 0 `pput`/`vpput`/`heldout`/`hvpput`/registry-filename hits in any worker-visible artifact; (g) north-star report diff-conforms to the pre-frozen skeleton regardless of result direction.

## 3. Ship Gate (M4.G)

**Predicate (tracker M4.G row):** G5 KPI roll-up over the §1.1 requirements; Drift-Check 7/7 (Intent §8). Verifier class: M5-class. NOT_RUN == FAIL. Roll-up rule (playbook §4.2): no phase FAILED/BLOCKED/NOT_RUN.

**Required artifacts:**
1. ADR-M4-001 through ADR-M4-007 accepted in the plan directory (texts from RES_M4 §6; extended-MADR per playbook §0 ADR convention).
2. Frozen `metric/compute_hvpput.py` + FIXTURE self-test output (byte-identical to the RES_M4 §5.7 expected JSON) + recorded sha256s, with evidence the freeze PREDATES any read of M3 outputs (timestamp/digest chain).
3. `heldout_task_registry.v1.json` + worker-invisibility sweep transcript (leakage audit + `hvpput`/registry greps, all clean) + out-of-registry hard-fail test evidence.
4. `inputs/INPUT_DIGESTS.json` matching M3's published digest table 100%.
5. `hvpput_report.v1.json` with class breakdown + per-arm portfolio values (or bounds) + per-task rational table + receipt-binding verification note (§2.7 rules) + auditor-conservation reconciliation note.
6. `causal/h2_consumption_note.json` (verbatim H2 + source digest), stamped exploratory artifacts, `causal/exploratory/rule_lifecycle_table.json`, and the `BroadcastRuleRetired` proposal packet addressed to M1 (RES_M4 §2.8, ADR-M4-006).
7. `NORTHSTAR_REPORT.md` + `CLAIM_BOUNDARY.json`, diff-conforming to the frozen skeleton, with the mandatory sentence template matching the observed direction.
8. **Mandatory `PROGRESS_TRACKER.md` update** with evidence paths per playbook §6.2. Implementer status ceiling: **ADDRESSED** — CLOSED/EXTERNALLY_VERIFIED only via the M5.P4 closure job's certificate-or-FAIL artifact.

## 4. Evals

### 4.1 Automated

- Metric self-test: `python3 metric/compute_hvpput.py --fixture metric/selftest_fixture/` — exit 0, output byte-identical to the RES_M4 §5.7 expected JSON, zero `.` inside any JSON number token (RES_M4 §5.2 self-test clause).
- Receipt-binding lint (§2.7 rule 2): every admitted `provider_receipt_inline` event carries the complete per-provider field set for its `usage_schema`; any mislabeled event = script hard-fail (this IS the test — run it against a deliberately incomplete synthetic receipt and assert failure).
- Cost-class lint: zero events with `cost_source_kind` absent/`unspecified`/non-enum among admitted runs; every `bounded_estimate` carries `bound_kind`; ceiling-arithmetic recomputation of `computed_cost_microusd` matches tape values exactly (RES_M4 §2.7 rule 3).
- Input-digest check: sha256 of every consumed M3 artifact equals M3's published table (RES_M4 §5.4).
- Registry enforcement test: a synthetic out-of-registry receipt makes the script hard-fail (RES_M4 §5.2 assert, pitfall P6).
- Conservation reconcile: script totals equal the strict auditor's cost-conservation totals per run (`audit_micro_tape_decision_dag.py:738–776`; RES_M4 §4 P7).
- Exploratory stamp assertion: every `causal/exploratory/*.json` loads with `causal_claim_allowed == false` and `label == "EXPLORATORY"` (RES_M4 §5.5 snippet).
- Lifecycle audits: `audit_failure_taxonomy.py` (denylist + preserve-only + coverage) and `audit_failure_memory_activation.py` over consumed runs, exit codes recorded (RES_M4 §5.8 commands).

### 4.2 Scenario / LLM-judge

Scoped-down FCE-B1 check 8 (09 §5): a fresh-context agent recomputes H-VPPUT for the full held-out set from tape receipt events + the registry ONLY, using the frozen script, and must match `hvpput_report.v1.json` exactly; it also asserts zero `cost_source_kind: unspecified` events in the inputs and that the registry has no worker-visible read path. Companion phrasing check (FCE-B1 check 6 shape): the report's H2 sentence conforms to the mandatory templates — a null phrased as "no effect" is a FAIL. Rubric: exact numeric match + correct per-run class assignment + clean invisibility assertion + template conformance = PASS; any reliance on implementer narrative = FAIL.

### 4.3 Performance

Full metric pass ≤30 min wall-clock over the M3 corpus (post-processing only); fixture self-test in seconds; record actuals in the report. Zero LLM spend (RES_M4 §3).

### 4.4 Sandboxed harness

No mutation paths — analysis-only module; runsc not required (Intent §5.6 scope). If any future exploratory run makes worker calls, it inherits M1d's sandbox gate and M3's receipt requirements first; the FCE-C1 injection-budget eval that consumes M4's lifecycle data runs under FCE's own sandbox rules, not M4's.

### 4.5 Thresholds

Fixture recomputation byte-exact; input digests 100% match; leakage/invisibility sweep 0 hits; receipt-binding re-verification 100% of admitted inline receipts; class breakdown present; exclusion table complete (possibly empty); H2 verbatim-copy digest match; every exploratory/lifecycle artifact stamped; skeleton diff-conformance regardless of direction. Direction of any Δ does NOT affect PASS (Intent G5 measurement-validity framing).

### 4.6 Runnable instructions

RES_M4 §5 carries the command shapes: §5.2 frozen metric script + self-test; §5.3 registry generation + invisibility sweep; §5.4 input-digest table build; §5.5 causal consumption + exploratory stamp assertion; §5.6 orchestration order; §5.7 worked fixture with hand-checkable arithmetic (7560 × 105000 = 793,800,000; ⌊10¹²/7560⌋ = 132,275,132); §5.8 lifecycle audits. Canonical sweep and lifecycle-audit shapes:

```bash
cd /home/zephryj/turingos_backup/work/turing
python tools/bench/audit_prompt_leakage.py --help   # confirm flags, then run over worker-visible artifacts
grep -ril "heldout_task_registry\|hvpput" <m3_root>/worker_safe_tasks/ && echo LEAK-FAIL || echo clean
python tools/bench/audit_failure_taxonomy.py \
  --coverage <run_root>/turingos/substrate_coverage.json --out <m4_out>/failure_taxonomy_audit.json
python tools/bench/audit_failure_memory_activation.py --help   # confirm flags, then run over consumed runs
```

## 5. Dependencies

- Upstream: M4.P0/P0b none (plan-directory, W0). M4.P1 depends on M1c (CostEvent.v2 landed schema — HARD PREREQUISITE per the tracker M1c row) for real inputs; the freeze half (atoms P1-1..P1-3) runs earlier on FIXTURE data. M4.P2/P3 depend on M3.P6/P7 frozen outputs (playbook §3.1: M1c → M4, M3 → M4). ADR acceptance via the M0 governance chain. The `BroadcastRuleRetired` schema addition lands via M1 (tape owner) following the ADDITIVE_* event-registry precedent (RES_M2 §2.4, mirrored in the tracker M1c row) — M4's atom only produces the proposal packet.
- Downstream: M5.P4 certifies M4.G (closure job per RES_M5 §2.8/§5.8); M4.P3 feeds FCE-B1 checks 6+8, FCE-S4, FCE-B2 (M4 experiment roots in the leak sweep), FCE-R4, and the G5 threshold row (09 §8); `rule_lifecycle_table.json`'s `injection_cost_microusd_total` is the input FCE-C1's budget-knob design needs (09 §7; RES_M4 §5.8).

## 6. Effort estimate + parallelization

- Tiering (playbook §2.4): P0 research + metric spec + causal/lifecycle analysis design + report/gate design = xhigh (statistics/gate-design — never downgraded); registry/fixture plumbing + running pre-specified audits = medium; tracker updates = low.
- Wall-clock estimate: P0 ≈ 0.5–1 agent-day (DELIVERED); P0b ≈ 0.5 day (this regeneration + reconciliation); P1 ≈ 1–1.5 days (ADRs + script + fixture + skeleton freeze + registry + sweeps + real-input run); P2 ≈ 1 day (consumption note + stamped exploratory + lifecycle audits + retirement proposal); P3 ≈ 0.5 day (assembly + conformance + hand-off); M4.G ≈ 0.25 day. Module total ≈ 3.5–4.5 agent-days, zero LLM spend.
- Parallelization (playbook §3.2 waves): P0/P0b in W0 (done); P1's freeze half in W0–W2 parallel with everything; P1's real-input half + P2 in W3 alongside M3 as its outputs freeze; P3 in W4 with M5.P4 convergence. M4 never blocks M3; one writer per file tree — M4's write surface is its own evidence area + plan-directory ADRs only.

---

## Phases and atoms

Authoritative status lives in `PROGRESS_TRACKER.md` (M4 table). Atom format: description+why, inputs, outputs, acceptance criteria, methodology citation, implementation notes, sub-prompt, complexity (S/M/L), verification method. Every sub-agent executing an atom inherits the playbook §0 write-permission model, the Intent §5 red lines, the §6 status vocabulary (ceiling ADDRESSED), and reports per playbook §6.2.

### M4.P0 — Research (DELIVERED — recorded for the tracker)

Phase gate: report exists in house format with all six sections; on-disk claims carry verified absolute paths; playbook §3.4 minimum scope covered. Both atoms delivered 2026-07-02; fresh-context re-verification per playbook §2.2 step 3 remains due at the next verification pass (tracker M4.P0 note).

#### ATOM-M4.P0-1 — Produce `research/RES_M4_self_improvement_metrics.md` (initial landing)

- **Description / why:** the commissioned xhigh research atom (playbook §3.4) that makes M4 executable at all — without it, P1+ work is forbidden improvisation. Covers H-VPPUT computability from CostEvent.v2 (F7), billing-complete vs bounded classes, held-out discipline, B-vs-C causal design, honest-null template.
- **Inputs:** playbook §3.4 scope; Intent §2 G5; audit F7; the turing repo read-only. **Outputs:** RES_M4 §1–§6 core (§2.1–2.6, §3, §4 P1–P10, §5.1–5.6, ADR-M4-001..005).
- **Acceptance criteria:** house format complete; every on-disk claim carries a verified absolute path; scope items of playbook §3.4 all answered. **Methodology:** RES_M4 header + §1.
- **Implementation notes / verification:** DELIVERED 2026-07-02 and pinned (`30244d86…`, tracker Decision Log "M4/M5 repair pass EXECUTED"). Verification = tracker pin + on-disk existence. Complexity: L (xhigh tier).
- **Sub-Prompt:** n/a — delivered; do not re-run. Any future amendment is append-only with a Decision Log re-pin.

#### ATOM-M4.P0-2 — RES_M4 Revision 1.1 (append-only scope completion)

- **Description / why:** completes the commissioned scope with the consumption-side receipt-binding rules (§2.7), the broadcast-rule lifecycle including the verified retirement gap (§2.8), the worked FIXTURE H-VPPUT example (§5.7), lifecycle audit commands (§5.8), pitfalls P11–P14, ADR-M4-006/-007 — the parts P1/P2 atoms below are built on.
- **Inputs:** RES_M4 v1.0 + repo verification + WEB provider-docs checks (labeled/dated in the report). **Outputs:** RES_M4 Rev 1.1 (append-only; all pre-existing section numbers unchanged, so every citation stays resolvable).
- **Acceptance criteria:** append-only (verified — §2.1–2.6/§3/§4 P1–P10/§5.1–5.6/§6 001..005 unchanged); new sections labeled WEB/ANALYSIS where applicable. **Methodology:** RES_M4 header line 10.
- **Implementation notes / verification:** DELIVERED 2026-07-02. Consequence: RES_M4 on-disk digest is now `a21178f2…` ≠ pin `30244d86…` — a tracker Decision Log re-pin entry is REQUIRED (RES_M4 flags this itself); handled at ATOM-M4.P0b-2. Complexity: M.
- **Sub-Prompt:** n/a — delivered.

### M4.P0b — Module-spec regeneration (this atom)

Phase gate: module spec regenerated firm from RES_M4 incl. Rev 1.1; pins updated via Decision Log; every M4.P1+ tracker Deliverable/Gate cell cites a specific RES_M4 section; entry criterion for M4.P1.

#### ATOM-M4.P0b-1 — Regenerate `modules/MODULE_M4_self_improvement.md` firm from RES_M4 (this file)

- **Description / why:** the seeded/provisional spec and the v1.0.0 regeneration predate RES_M4 Rev 1.1 and carried terse atoms; running P1+ from them is the improvisation playbook §3.4 forbids. This atom produces the firm spec: full 1.1–1.7, KPIs quoting Intent §2 G5, Ship Gate with artifact list + tracker mandate + ADDRESSED ceiling, Evals 4.1–4.6, dependencies, effort, and fully-specified atoms with sub-prompts.
- **Inputs:** RES_M4 (all sections incl. Rev 1.1), MODULE_M3 exemplar, Intent, playbook, 09 FCE cross-references, tracker M4 rows. **Outputs:** this file, v1.1.0.
- **Acceptance criteria:** zero PROVISIONAL markers; every RES_M4 citation resolvable; inbound cross-reference IDs preserved (phases M4.P0..M4.G, FCE-B1 checks 6+8, M5.P4, wave slots); every atom carries description+why, inputs, outputs, acceptance, methodology citation, implementation notes, sub-prompt, complexity, verification. **Methodology:** playbook §3.4 P0b protocol.
- **Implementation notes / verification:** DELIVERED by this edit sequence (2026-07-02). Verification: fresh-context read confirms the acceptance list; sha256 recorded at re-pin. Complexity: M.
- **Sub-Prompt:** n/a — this file is the execution record.

#### ATOM-M4.P0b-2 — Re-pin + tracker reconciliation (Decision Log)

- **Description / why:** playbook §1 step 3 treats unlogged digest drift as a stop-work event; both this file's new digest and RES_M4's Rev 1.1 digest must be re-pinned through a Decision Log entry, and the M4.P1–P3/G tracker rows must be reconciled to the atom decomposition below (Rev 1.1 citations included) BEFORE any P1+ work starts.
- **Inputs:** this file's final sha256; RES_M4 on-disk sha256 `a21178f2…`; proposed row texts (returned by the P0b agent as `tracker_row_updates`). **Outputs:** tracker Decision Log entry; updated Pins rows; updated M4 table rows; regenerated seed per tracker convention.
- **Acceptance criteria:** `sha256sum -c` passes for both pins; every M4.P1–P3 Deliverable/Gate cell cites a specific RES_M4 section; M4.P0b row ADDRESSED citing this file. **Methodology:** playbook §1 step 3; §3.4.
- **Implementation notes:** orchestrator bookkeeping (low tier); never a silent re-pin — the Decision Log entry IS the adjudication record (LESSON from the RES_M2 drift). Complexity: S. **Verification:** bootstrap pin-check green on next session start.
- **Sub-Prompt:** *"Update PROGRESS_TRACKER.md only. Add a Decision Log entry re-pinning `research/RES_M4_self_improvement_metrics.md` (append-only Rev 1.1, new digest a21178f2…) and `modules/MODULE_M4_self_improvement.md` v1.1.0 (digest: compute with sha256sum). Apply the M4 row updates supplied by the P0b agent verbatim after checking each RES_M4 §-citation resolves. Regenerate and re-pin the tracker seed. Status ceiling ADDRESSED; cite openable paths for every claim."*

### M4.P1 — H-VPPUT spec + frozen metric machinery

Phase gate: ADRs accepted; freeze digests recorded BEFORE any M3 output read; self-test byte-exact with zero float tokens; registry generated with sweep 0 hits; real-input `hvpput_report.v1.json` produced with class breakdown + conservation reconcile. Atoms P1-1..P1-3 are the freeze half (FIXTURE-only, runnable W0–W2); P1-4/P1-5 need M3's frozen outputs and M1c-conformant receipts (W3).

#### ATOM-M4.P1-1 — Author ADR-M4-001..007 in `adr/`

- **Description / why:** the seven decision records fix every contested design point (metric definition, cost classes, causal discipline, registry, honest-null skeleton, lifecycle/retirement, receipt binding) before code exists, so later atoms are mechanical. ADR-M4-006/-007 are Rev 1.1 additions absent from any earlier module version.
- **Inputs:** RES_M4 §6 paragraph texts; `adr/ADR_TEMPLATE.md`; playbook §0 ADR convention. **Outputs:** `adr/ADR-M4-001-hvpput-definition.md` … `adr/ADR-M4-007-provider-receipt-binding.md` (slugs at author's discretion, numbers fixed).
- **Acceptance criteria:** all seven present in extended-MADR format with front-matter status `proposed`→`accepted-addressed` via the M0 chain, `status_ceiling: ADDRESSED`, evidence lists citing RES_M4 §6 + the verified repo paths from §2.1/§2.8; ADR-M4-007 records its subordination to ADR-M1-004.
- **Methodology:** RES_M4 §6 (verbatim context/decision/consequences); playbook §0. **Implementation notes:** plan-directory work, no owner gate; do not paraphrase decision content — expand the §6 paragraphs into the template without changing decisions. Complexity: M. **Verification:** fresh-context reader confirms each ADR's decision text is semantically identical to its RES_M4 §6 paragraph.
- **Sub-Prompt:** *"Read `research/RES_M4_self_improvement_metrics.md` §6 and `adr/ADR_TEMPLATE.md`. Author ADR-M4-001..007 in `adr/`, one file each, expanding the §6 paragraphs into extended-MADR without altering any decision. Front matter per playbook §0 (status vocabulary, decision-makers, authority_level, constitution_articles — Art. 0.2/II.1/III.4 as applicable, evidence with sha256s, status_ceiling ADDRESSED). ADR-M4-007 must state it binds M4's read-side verification only, subordinate to ADR-M1-004. Plan-directory writes only. Report per playbook §6.2."*

#### ATOM-M4.P1-2 — Freeze `metric/compute_hvpput.py` + FIXTURE self-test

- **Description / why:** the frozen stdlib-only metric script is the single implementation of H-VPPUT (P8 anti-drift) and the structural enforcement of the two-class discipline (P2) and registry restriction (P6); freezing it before M3 outputs are readable removes analyst degrees of freedom.
- **Inputs:** RES_M4 §5.2 skeleton; §2.2 integer-pair representation; §2.3 classification; §2.7 rules 1–6 (read-side receipt-binding verifier + ceiling costing); §5.7 worked example as `metric/selftest_fixture/` (inputs + expected output JSON, labeled FIXTURE). **Outputs:** `metric/compute_hvpput.py`, `metric/selftest_fixture/`, recorded sha256s.
- **Acceptance criteria:** self-test exit 0 and byte-identical to the §5.7 expected JSON; zero `.` inside any JSON number token of the output; out-of-registry receipt → hard fail; mislabeled `provider_receipt_inline` (missing field) → hard fail; classification of the §5.7 fixture = {t1 BILLING_COMPLETE, t2 BOUNDED, t3 INADMISSIBLE with exclusion row}; freeze sha256 recorded in the evidence area BEFORE any M3 output is read.
- **Methodology:** RES_M4 §5.2, §5.7, ADR-M4-001/-002/-007. **Implementation notes:** stdlib only; sorted keys; decimal strings via integer arithmetic only (the §5.7 hand-checks: 7560×105000=793,800,000; ⌊10¹²/7560⌋=132,275,132); reproduce RES_M3 §5.6's portfolio aggregation so both reports cite one implementation. Complexity: M (xhigh tier — load-bearing gate code). **Verification:** self-test run recorded (command + exit code); adversarial fixture variants (out-of-registry, mislabeled receipt, float smuggling) each fail as specified.
- **Sub-Prompt:** *"Implement `metric/compute_hvpput.py` per RES_M4 §5.2 extended with the §2.7 rule-2/rule-3 read-side verification (per-provider `usage_schema` field sets; ceiling costing per (provider, model, token_class)). Build `metric/selftest_fixture/` from the §5.7 worked example verbatim, labeled FIXTURE. Assert: byte-identical expected output; no float tokens; hard-fail on out-of-registry, mislabeled inline receipts, and non-enum kinds. Record sha256s of script + fixture + expected output. Do NOT read any M3 output artifact. Report commands + exit codes per playbook §6.2."*

#### ATOM-M4.P1-3 — Freeze north-star report skeleton + `CLAIM_BOUNDARY` template + registry generator

- **Description / why:** ADR-M4-005's core move — the report's shape (and its three mandatory sentence templates) is fixed before results exist so direction cannot change phrasing; the registry generator is frozen alongside so held-out selection is also pre-committed.
- **Inputs:** RES_M4 §2.6 skeleton items 1–4; the campaign `CLAIM_BOUNDARY.json` pattern (path in §2.6); §5.3 generator contract (S01 manifest → registry with embedded manifest sha256). **Outputs:** `NORTHSTAR_REPORT.skeleton.md`, `CLAIM_BOUNDARY.template.json`, `metric/gen_registry.py`, freeze-digest record.
- **Acceptance criteria:** skeleton contains all mandatory fields (class breakdown, per-arm portfolio H-VPPUT/bounds, Δ_BC+CI+MDE-verbatim slot, positive/null/negative templates exactly as RES_M4 §2.6 item 2, exclusion + deviation tables present-even-when-empty); `CLAIM_BOUNDARY` template carries `failure_memory_causal_claim_allowed`, `hvpput_is_capability_claim: false`, `absolute_rate_is_capability_claim: false`; sha256s recorded in the same freeze record as P1-2, before any M3 read.
- **Methodology:** RES_M4 §2.6, §5.3, ADR-M4-004/-005. **Implementation notes:** the null template must read "Δ_BC = x [CI includes 0]; the study was powered for MDE = y; smaller true effects are not excluded. No failure-memory efficacy claim is made." — never "no effect" (FCE-B1 check 6). Complexity: S. **Verification:** diff of assembled P3 report against skeleton is the later conformance test; at freeze time, a checklist against §2.6 items 1–4.
- **Sub-Prompt:** *"From RES_M4 §2.6, write `NORTHSTAR_REPORT.skeleton.md` with every mandatory block and the three sentence templates verbatim; write `CLAIM_BOUNDARY.template.json` mirroring `turing/evidence/bench/swe_bench_verified_500_campaign_20260629/CLAIM_BOUNDARY.json`'s pattern with the §2.6 item-3 fields; write `metric/gen_registry.py` per §5.3 (input: M3 shard manifest path + shard id; output: `heldout_task_registry.v1.json` embedding the manifest sha256). Record sha256s in the freeze record. Do not read M3 outputs. FIXTURE-test the generator on a synthetic manifest."*

#### ATOM-M4.P1-4 — Generate `heldout_task_registry.v1.json` + worker-invisibility sweep

- **Description / why:** turns "held-out" from aspiration into an artifact (ADR-M4-004): the registry is the sole task-selection input to H-VPPUT, and its mechanical worker-invisibility is what FCE-B1 check 8 will re-assert. Runs at the M3 freeze boundary (RES_M4 §5.6 step 2).
- **Inputs:** M3's frozen S01 `shard_manifest.json` (digest-verified against M3's pre-registration); `metric/gen_registry.py`; `audit_prompt_leakage.py`. **Outputs:** `heldout_task_registry.v1.json` (+ digest), sweep transcript, hard-fail test evidence.
- **Acceptance criteria:** registry embeds the S01 manifest sha256 and instance IDs exactly; registry path is outside every worker-visible tree (never under any `worker_safe_tasks/`); leakage audit + `grep -ril "heldout_task_registry\|hvpput"` over `<m3_root>/worker_safe_tasks/` return 0 hits; synthetic out-of-registry receipt hard-fails the metric script.
- **Methodology:** RES_M4 §2.4, §5.3, pitfall P6. **Implementation notes:** generate FROM the pre-registration's shard copy, never from a live dataset fetch; add `hvpput` + registry filename to the marker set used in all M4 sweeps (the existing lists predate the H-prefix). Complexity: S. **Verification:** sweep transcript with commands + exit codes; registry digest recorded and cited by the P3 report.
- **Sub-Prompt:** *"Run `metric/gen_registry.py --shard-manifest <m3_root>/shard/shard_manifest.json --shard S01 --out heldout_task_registry.v1.json` (RES_M4 §5.3). Verify the embedded manifest sha256 equals M3's published digest. Run `audit_prompt_leakage.py` over every worker-visible artifact of the consumed M3 runs, then `grep -ril \"heldout_task_registry\\|hvpput\" <m3_root>/worker_safe_tasks/` — any hit is LEAK-FAIL, stop and record. Prove the out-of-registry hard-fail with a synthetic receipt. Registry stays supervisor-side; never copy it into any worker-visible directory."*

#### ATOM-M4.P1-5 — Real-input metric run → `hvpput_report.v1.json` + conservation reconcile

- **Description / why:** the F7-closing computation: H-VPPUT over M3's frozen S01 receipts and harness results, per-arm, under the two-class discipline — the first billing-grounded north-star number (or bound) in the project's history.
- **Inputs:** frozen script (P1-2 digest), registry (P1-4), M3 receipts + per-(worker,arm) `evaluation_results.json` (digest-checked via `inputs/INPUT_DIGESTS.json`, built here per RES_M4 §5.4), strict-auditor conservation totals. **Outputs:** `hvpput_report.v1.json`, `inputs/INPUT_DIGESTS.json`, receipt-binding verification note, conservation reconciliation note.
- **Acceptance criteria:** report contains class breakdown, per-arm portfolio values (BILLING_COMPLETE point estimates; BOUNDED as `lower_bound_via_cost_upper_bound`), per-task exact-rational table, exclusion table with offending event refs (possibly empty); every admitted inline receipt passed §2.7 rule-2 re-verification; script totals == auditor cost-conservation totals per run; every tape receipt consumed (unconsumed receipt = FAIL, P7); zero float tokens.
- **Methodology:** RES_M4 §2.2 aggregation, §2.3 classes, §2.7 rules, §5.4, §5.6 step 3, ADR-M4-001/-002. **Implementation notes:** run the frozen bytes (verify script sha256 before execution); INPUT_DIGESTS must equal M3's published table 100% or the report is invalid by construction; legacy/pre-M1c material goes only to the labeled appendix (P9). Complexity: M. **Verification:** independent recomputation from the same inputs is byte-identical (this is rehearsed here exactly as FCE-B1 check 8 will run it).
- **Sub-Prompt:** *"Verify `metric/compute_hvpput.py` sha256 equals the freeze record. Build `inputs/INPUT_DIGESTS.json` per RES_M4 §5.4 and assert 100% match with M3's published digests. Run the script over receipts + harness results + registry ONLY → `hvpput_report.v1.json`. Reconcile totals against `audit_micro_tape_decision_dag.py` cost-conservation output; list any INADMISSIBLE run with its offending event refs — exclusions are never silent. Then re-run the script and assert byte-identity. Report all commands, exit codes, and digests."*

### M4.P2 — Failure-memory causal analysis + lifecycle measurement

Phase gate: confirmatory content is a verbatim, digest-pinned copy of M3's H2; every exploratory/lifecycle artifact stamped `causal_claim_allowed: false`; lifecycle audits green; retirement proposal packet handed to M1. Depends on M3.P6/P7 frozen outputs.

#### ATOM-M4.P2-1 — `causal/h2_consumption_note.json` (verbatim H2 consumption)

- **Description / why:** the only confirmatory causal content M4 is permitted (ADR-M4-003): M3's pre-registered H2 (arm B vs arm C — the ablation IS the causal design) copied verbatim with its source digest. Re-testing H2 with different statistics is post-hoc metric shopping — rejected in RES_M4 §2.5 B.
- **Inputs:** M3's frozen `UPLIFT_REPORT.json` + its published sha256; ablation-honesty audit output (confirms arms differed only in broadcast-rule injection). **Outputs:** `causal/h2_consumption_note.json` = {Δ_BC, CI, p, MDE statement verbatim, source path + sha256, H2 pass/fail + direction}.
- **Acceptance criteria:** every number byte-equal to `UPLIFT_REPORT.json`; source digest matches M3's publication; NO recomputation code exists in the confirmatory path; the note records whether the "failure memory causally improves solve probability" sentence is permitted (iff H2 passed positive).
- **Methodology:** RES_M4 §2.5 A, §5.5, ADR-M4-003. **Implementation notes:** if H2 is null, this atom still PASSes — the note carries the null verbatim and the claim flag `false`; a harm-direction point estimate additionally gets the §2.6 negative-template flag. Complexity: S. **Verification:** fresh-context diff of the note's numbers against `UPLIFT_REPORT.json`.
- **Sub-Prompt:** *"Copy H2's Δ_BC, CI, p, and MDE statement VERBATIM from `<m3_root>/UPLIFT_REPORT.json` into `causal/h2_consumption_note.json` with the file's sha256. Set `failure_memory_causal_claim_allowed` true only if H2 passed at the pre-registered α with positive direction. Write no statistics code. If any number needs 'adjusting', stop — that is a defect to report, not a task."*

#### ATOM-M4.P2-2 — Stamped exploratory mechanism analyses

- **Description / why:** mechanistic texture without error control (RES_M4 §2.5 C): dose-response over `consumed_broadcast_rule_ids`, memory-cost accounting (rule-injection tokens/µUSD from receipts vs marginal outcome), and lineage tables. Feeds FCE-C1's budget-knob design; must never contaminate confirmatory claims — hence structural stamping (the stage14 idiom).
- **Inputs:** M3 arm-B tape events + receipts (read-only); `audit_failure_memory_activation.py` for lineage tracing. **Outputs:** `causal/exploratory/dose_response.json`, `causal/exploratory/memory_cost.json`, lineage table — each with `label: "EXPLORATORY"`, `causal_claim_allowed: false`.
- **Acceptance criteria:** the §5.5 stamp assertion passes on every artifact; inputs are tape/receipt/frozen-file only (zero LLM calls); no exploratory number appears in the report's headline block.
- **Methodology:** RES_M4 §2.5 C, §5.5, ADR-M4-003; claim discipline §2.5 (lineage/association NEVER supports "failure memory works"). **Implementation notes:** dose variable = per-task count of `consumed_broadcast_rule_ids` (field verified in the loop capsule payloads); injection cost prices rule text as prompt tokens via receipts. Complexity: M. **Verification:** run the RES_M4 §5.5 assertion snippet over every output; spot-check one dose-response row against raw tape.
- **Sub-Prompt:** *"Produce the three exploratory analyses of RES_M4 §2.5 C from `<m3_root>` tape events and receipts only. Stamp every output `{\"label\": \"EXPLORATORY\", \"causal_claim_allowed\": false}` and run the §5.5 assertion. Forbidden in any output prose: 'failure memory works/improves/causes'. These artifacts inform pruning and FCE-C1 design; they prove nothing causal."*

#### ATOM-M4.P2-3 — Lifecycle audits + `rule_lifecycle_table.json` + `BroadcastRuleRetired` proposal to M1

- **Description / why:** measures the failure-memory object end to end (RES_M4 §2.8): re-runs the Stage10 denylist/attestation/cluster-activation audits over consumed runs, builds the per-rule lifecycle table (activation → consumption → injection cost → post-consumption outcomes → retirement slot), and packages the missing sixth stage — event-based retirement — as a schema proposal for M1. Without retirement the active set only grows: the Art. II.1 context-pollution failure plus unbounded prompt cost (P12).
- **Inputs:** consumed runs' `substrate_coverage.json` + tape; `audit_failure_taxonomy.py`, `audit_failure_memory_activation.py` (RES_M4 §5.8 commands); ADR-M4-006. **Outputs:** `failure_taxonomy_audit.json`, activation-audit outputs, `causal/exploratory/rule_lifecycle_table.json` (§5.8 shape, stamped), proposal packet: `BroadcastRuleRetired` event spec (reason enum `{superseded_by_rule, dose_response_null, scope_expired, injection_budget_pressure}`, `evidence_ref`, append-only semantics) + active-set filter for `read_broadcast_rules` + pre-registered per-capsule injection budget, addressed to M1 via the M0 chain.
- **Acceptance criteria:** both audits exit 0 with outputs archived; lifecycle table has one row per activated rule with `injection_cost_microusd_total` computed from receipts; table stamped EXPLORATORY/`causal_claim_allowed: false`; proposal packet cites only EXPLORATORY artifacts as retirement evidence (pruning is operations, not causal inference) and names M1 as landing owner (ADDITIVE_* precedent); M4 lands NO tape event itself.
- **Methodology:** RES_M4 §2.8 (six-stage table + claim ceilings), §5.8, ADR-M4-006; Art. II.1. **Implementation notes:** extend the sweep marker set with `hvpput` + registry filename here too (§2.8 stage 5); stages 1–4 license protocol claims only — keep lifecycle prose at "lineage-proven", never efficacy. Complexity: M. **Verification:** audit exit codes recorded; a fresh-context reader confirms the proposal changes no repo bytes and the table's claim ceiling.
- **Sub-Prompt:** *"Run the RES_M4 §5.8 commands (`audit_failure_taxonomy.py --coverage … --out …`; `audit_failure_memory_activation.py` after `--help` flag check) over the consumed M3 runs. Build `rule_lifecycle_table.json` per the §5.8 shape, pricing each rule's injected text from the consuming capsules' receipts. Draft the `BroadcastRuleRetired` proposal packet per ADR-M4-006 addressed to M1 — you own zero tape schema; if you find yourself editing `run_mini_swe_bench_substrate_smoke.py` or any crate, stop. Stamp everything EXPLORATORY with `causal_claim_allowed: false`."*

### M4.P3 — North-star metrics report

Phase gate: report + claim boundary assembled from the frozen skeleton, diff-conformant, direction-independent; handed to the M5-class verifier. Verifier class for this phase (tracker M4.P3 row): M5-class.

#### ATOM-M4.P3-1 — Assemble `NORTHSTAR_REPORT.md` + `CLAIM_BOUNDARY.json`

- **Description / why:** the G5 deliverable: fills the pre-frozen skeleton (P1-3) with the P1-5 metric outputs, the P2-1 verbatim H2 numbers, and pointers to the stamped exploratory/lifecycle artifacts — using the ONE mandatory sentence template that matches the observed direction. An honest null here is a first-class PASS (ADR-M4-005); "no measurable self-improvement" written per template is publishable.
- **Inputs:** frozen skeleton + template digests (P1-3); `hvpput_report.v1.json`; `h2_consumption_note.json`; exclusion/deviation sources (P1-5 exclusions; M3 `DEVIATIONS.md`); registry digest. **Outputs:** `NORTHSTAR_REPORT.md`, `CLAIM_BOUNDARY.json`.
- **Acceptance criteria:** headline block = run-class breakdown + per-arm portfolio H-VPPUT/bounds + Δ_BC with CI + MDE verbatim (RES_M4 §2.6 item 1); sentence template exact for the direction (item 2); `CLAIM_BOUNDARY.json` fields tied to H2 outcome (item 3); exclusion + deviation tables present even when empty (item 4); every number traceable to a digest-pinned input; lifecycle section stays at protocol-claim ceiling if H2 is null (RES_M4 §2.8).
- **Methodology:** RES_M4 §2.6, §5.6 step 5, ADR-M4-005. **Implementation notes:** no new numbers may be computed during assembly — the assembler only transcribes; any "improvement" to phrasing outside the templates is the exact drift ADR-M4-005 forbids. Complexity: M. **Verification:** structural diff against the skeleton (next atom) + digest trace of every headline number.
- **Sub-Prompt:** *"Assemble `NORTHSTAR_REPORT.md` by filling `NORTHSTAR_REPORT.skeleton.md` (verify its sha256 against the freeze record first) with values transcribed from `hvpput_report.v1.json` and `causal/h2_consumption_note.json`. Use the RES_M4 §2.6 sentence template matching the observed direction, verbatim. Fill `CLAIM_BOUNDARY.json` from the template with `failure_memory_causal_claim_allowed` equal to the H2 flag. Compute nothing. Include exclusion and deviation tables even if empty."*

#### ATOM-M4.P3-2 — Conformance + claim-boundary lint + M5-class hand-off packet

- **Description / why:** mechanical pre-verification so the M5-class verifier receives a self-contained packet: skeleton diff-conformance, forbidden-phrase lint (the FCE-B1 check-6 "no effect" trap; the H2-gated efficacy sentence), and assembly of everything check 8 needs (registry, frozen script, receipts pointers, report) with zero implementer narrative.
- **Inputs:** P3-1 outputs; freeze record; the claims-lint conventions (M0.P6's claims/status lint where landed). **Outputs:** conformance/lint transcript; hand-off packet index (paths + sha256s only).
- **Acceptance criteria:** report diff-conforms to the skeleton (only value slots differ); lint finds zero forbidden phrasings ("no effect" for a null; efficacy language without H2-pass; CLOSED/RELEASED anywhere); packet contains gate spec + artifact paths + Drift-Check + status vocabulary and NO implementer transcript (playbook §2.3).
- **Methodology:** RES_M4 §2.6; playbook §2.3 verifier-isolation rules; FCE-B1 checks 6+8 shapes (09 §5). **Implementation notes:** the lint can be a grep set now, upgraded to M0.P6's tool when available. Complexity: S. **Verification:** lint transcript with exit codes; packet reviewed for context-bleed before hand-off.
- **Sub-Prompt:** *"Diff `NORTHSTAR_REPORT.md` against the frozen skeleton: only designated value slots may differ. Grep the report for forbidden phrasings: 'no effect' (null must use the MDE template), any efficacy sentence if `failure_memory_causal_claim_allowed` is false, and the strings CLOSED/RELEASED/RATIFIED. Build the M5-class hand-off packet: gate predicate, artifact path+sha256 list, Drift-Check checklist, status vocabulary — and nothing about how the work was done. Status ceiling ADDRESSED."*

### M4.G — Module gate

Phase gate: §3 predicate. Verifier class: M5-class (tracker M4.G row); the implementer's ceiling is ADDRESSED — the gate's external outcome is recorded, never conferred (playbook §5.2).

#### ATOM-M4.G-1 — Assemble the §3 artifact list; run §4 evals; Drift-Check 7/7; tracker update

- **Description / why:** the module-level roll-up: every §3 artifact verified present at its cited path, every §4.1 automated eval re-run, the Intent §8 checklist answered with an artifact path per answer — then the mandatory tracker update. Stale green is the F4 failure mode, so child evidence is re-opened, not trusted.
- **Inputs:** all P0–P3 evidence; §3 artifact list; §4 eval commands; Intent §8. **Outputs:** module evidence bundle index; drift-check record (7/7 with paths); tracker M4 rows updated per playbook §6.2.
- **Acceptance criteria:** all eight §3 items present and re-checked (at minimum one child gate re-run adversarially, playbook §4.2); §4.1 evals all exit 0; drift-check 7/7 recorded; tracker rows cite openable paths; module status ADDRESSED, not higher.
- **Methodology:** playbook §2.2, §4.1–4.2; Intent §8. **Implementation notes:** the adversarial re-run should target the metric self-test or the registry hard-fail (cheap, load-bearing). Complexity: M. **Verification:** the drift-check record itself, plus the M5.P4 job's independent pass.
- **Sub-Prompt:** *"Open every artifact in MODULE_M4 §3 at its cited path and re-verify (digest or re-run). Re-run all §4.1 automated evals, recording commands + exit codes. Answer the 7-item Drift-Check with an artifact path per answer. Update the tracker M4 rows per playbook §6.2 with evidence_class labels. Set M4.G ADDRESSED at most. Any missing artifact or failing eval → the gate FAILS; record honestly and stop."*

#### ATOM-M4.G-2 — Enqueue the M5.P4 closure job; record certificate-or-FAIL

- **Description / why:** the F1 antidote applied to M4: closure only via M5's custody-separated machinery. M4.G reaching ADDRESSED triggers a queue job in the M5.P4 standing service (one line in that tracker row); the outcome — ClosureCertificate.v1 or a recorded FAIL — is what moves M4.G beyond ADDRESSED, and only the orchestrator recording that external artifact may do so.
- **Inputs:** ATOM-M4.G-1's evidence bundle; the P3-2 hand-off packet; M5.P4 queue protocol (RES_M5 §2.8/§5.8). **Outputs:** queue-job line in the tracker M5.P4 row; eventually a cited certificate path or FAIL artifact on the M4.G row.
- **Acceptance criteria:** job enqueued with the packet (no implementer narrative); no silent queue drop — certificate or FAIL is recorded either way (RES_M5 §4 P8); M4.G row status changes only by citing the external artifact.
- **Methodology:** playbook §2.3/§5.2; RES_M5 §2.8; tracker M5.P4 row rules (owner-provided auditor channel — if absent, this atom is BLOCKED-on-owner per playbook §5.1, recorded, and M4.G rests at ADDRESSED).
- **Implementation notes:** bookkeeping plus packet hygiene; the verifier works from a fresh clone/pristine paths. Complexity: S. **Verification:** the certificate/FAIL artifact itself, cited on both the M4.G and M5.P4 rows.
- **Sub-Prompt:** *"Enqueue an M5.P4 closure job for M4.G: add the queue line to the tracker M5.P4 row citing the hand-off packet path. If the owner-provided auditor channel is not yet recorded in the Decision Log, record BLOCKED-on-owner instead and leave M4.G at ADDRESSED. When the job completes, record the ClosureCertificate.v1 path or the FAIL artifact on the M4.G row — never summarize the verdict in prose without the path."*
