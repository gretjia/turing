# MODULE M3 — Worker Uplift Laboratory (G4)

- Version: 1.0.0 (2026-07-02). Planning artifact; confers no CLOSED/RATIFIED status. The KPI is a valid MEASUREMENT, not a positive result (Intent §2 G4).
- Grounding: `research/RES_M3_worker_uplift_laboratory.md` (sha256 pinned in `PROGRESS_TRACKER.md`), Intent §2 row G4 and §7 non-goals, audit findings F4 (repo-local evaluator false positive django-11885), F5 (worker identity not on tape), R2, R7.
- Reconciliation: gate IDs/tool names here govern over `09_FINAL_CERTIFICATION_EVALS.md` §0.1 assumptions. FCE §1.2 policy binds: S01 confirmatory results are never re-run by certification.

## 1. Written spec

### 1.1 Functional requirements

1. **Pre-registration (ADR-M3-01..05):** a sha256-frozen packet (hypotheses H1: B>A and H2: B>C only; MDE statement; rerun policy; worker roster with pinned model IDs and prices; per-instance budgets identical across arms — 5 attempts / 400K tokens / fixed wall-clock from the frozen `loop_manifest.json` profile; frozen stdlib-only analysis script `analyze_uplift.py` with a FIXTURE-labeled synthetic-data dry-run) ACKed by an independent verifier BEFORE any worker call; digest recorded on tape.
2. **4 arms on frozen shard S01 (50 tasks, 10 repos, verified untouched):** A worker alone (capsule-only, no checkout); B full TuringOS loop; C = B minus failure-memory injection (ablation); D deterministic fake floor (manipulation check — any solve = pre-registered STOP + root-cause). Frozen task order shared by B and C; ablation-honesty byte-diff audit asserts the only B-vs-C capsule delta is the broadcast-rules section.
3. **Worker-safe packets:** materialized by the audited tool only; leakage audit + gold-patch guard PASS; dataset content digest (`sha256:43ed5a3d…`) asserted before materialization; sha256 table published. The supervisor never opens raw dataset rows (P8/astropy lesson).
4. **Roster:** `deepseek-v4-flash` + one GPT-5-nano-class model + optional `claude-haiku-4-5`; each must land in the 15–45% arm-A weakness band on a 10-task S02 pilot or be replaced under a logged pre-registered rule (ADR-M3-04).
5. **Scoring:** upstream `python -m swebench.harness.run_evaluation` (swebench==4.1.0, `.venv_swebench`, qualified defaults: pinned dataset name + sealed digest, `swebench` namespace, `--cache_level env`, `--timeout 1800`, `--max_workers 2`) is the SOLE scorer; repo-local evaluators advisory only (ADR-M3-05). Rerun policy: ≤2 logged retries for `error_ids`/`incomplete_ids` only; persistent errors excluded pairwise across ALL arms; `resolved`/`unresolved` never re-rolled.
6. **Receipts:** every LLM call appends a `turingos.worker_call_receipt.v1` tape event (model requested + provider-echoed, request ID, request/response digests, verbatim usage, pinned prices, integer-micro-USD cost, wall-clock); `model_name_or_path` encodes `worker__arm__experiment` (ADR-M3-01; depends on M1c).
7. **Analysis and report:** exact McNemar primary on pooled worker-task pairs, Holm H1-then-H2, 10,000-replicate cluster-by-task bootstrap CIs, MDE statement; `UPLIFT_REPORT.{json,md}` with claim boundary; a null/negative result is a valid PASS (ADR-M3-03).
8. **S00 resume protocol (ADR-M3-06, separate atom chain after ADR-M3-01):** stamp 48 predictions OLD-POLICY INVENTORY; produce the 2 missing predictions under the new policy; astropy-12907 patch only from an independent context fed solely the worker-safe capsule; any S00 scoring labeled mixed-policy inventory, excluded from uplift analyses, 48/50 never quoted as performance.

### 1.2 Non-functional requirements

- Idempotent per-cell atoms keyed by (worker, arm, instance_id, attempt); state in tape + per-cell result JSONs; a fresh orchestrator resumes from artifacts alone.
- Budget exhaustion is a recorded terminal event (`BudgetExhausted`), never a hang; >10% pairwise exclusions = pre-registered abort-and-restart.
- Deviations from the pre-registration require logged `DEVIATIONS.md` entries, never silent judgment; roster or design changes after freeze force re-registration.
- Claim boundaries: "TuringOS improves workers" forbidden unless H1 passes with positive direction; absolute solve rates never quoted as capability (contaminated benchmark, weak workers).

### 1.3 Performance targets

- LLM spend bounded well under US$1K total (RES_M3 §3); harness compute dominates: ~10 fifty-task evals at **1–3 h each** on this host with the cached env images (~100–120 GB disk, already provisioned). Measure actual per-eval wall-clock in the pilot and record it.
- MDE: single worker ~15–23 pp; pooled 2–3 workers ~6–14 pp at 80% power — pre-registered and reported verbatim ("CI includes 0, powered for MDE=y").

### 1.4 Interfaces

Evidence-root layout is fixed by RES_M3 §5.1 (`turing/evidence/bench/worker_uplift_lab_S01_<date>/` with PREREGISTRATION.md/.sha256, CLAIM_BOUNDARY.json, analysis/, shard/, worker_safe_tasks/, arms/{A,B,C,D}/…, receipts/, predictions/, scoring/<run_id>/, DEVIATIONS.md, UPLIFT_REPORT.*). Receipt schema: RES_M3 §5.3. Predictions JSONL shape: RES_M3 §2.6. Harness output: `evaluation_results.json` schema_version 2. ADRs: plan directory `adr/ADR-M3-01..06.md`.

### 1.5 Agentic considerations

- Orchestration order is pre-answered in RES_M3 §5.7 (freeze → packets → floor canary FIRST → pilot → A → B then C → frozen analysis → S00 protocol last).
- LLM-spend-bearing work is never parallelized beyond the pre-registered design; budget ceilings are not an orchestrator degree of freedom (playbook §3.2).
- Pre-flight a canary call per worker per running day (`deepseek-chat` retires 2026-07-24 — pin `deepseek-v4-flash`); if `model_reported` changes mid-arm: halt, log deviation, independent verifier decides restart of affected cells.
- M3 owns `evidence/bench/<uplift root>` + the adapter module in the write partition; monitor `df` between shard evals; never enable `instance` caching (~2 TB).

### 1.6 Risks & mitigations

Adopt RES_M3 §4 P1–P14 verbatim as the risk register. Highest-severity: P5 ablation-arm contamination → machine-checkable byte-diff audit; P8 gold leakage via supervisor context → packets via audited tool only, taint protocol; P9 floor solves a task → pre-registered STOP; P11 token-budget asymmetry → identical ceilings + cost-normalized exploratory analysis; P12 self-closure → M5-class cross-family verifier certifies the report on a fresh clone.

### 1.7 Architecture guidance

Only three new components over verified existing tooling (RES_M3 §3): (i) API-worker adapter with receipts (one module, on M1c's seam); (ii) ablation flag + ablation-honesty audit (thin); (iii) frozen stdlib-only analysis script. Everything else reuses the qualified harness setup, the audited packet materializer, `audit_prompt_leakage.py`, and the sealed campaign manifests (paths in RES_M3 appendix).

## 2. KPIs

Intent §2 row G4 (verbatim): *"Measure whether TuringOS improves weak/heterogeneous workers — Pre-registered 4-arm experiment (worker-alone / worker+TuringOS / worker+TuringOS-minus-failure-memory / deterministic floor) on a frozen shard, scored ONLY by the upstream Docker harness; uplift delta reported with confidence intervals. The KPI is a valid measurement, not a positive result."*

Measurable sub-KPIs: (a) pre-registration digest on tape with independent ACK dated BEFORE the first worker call; (b) 100% of outcomes harness-scored; (c) leakage audit + gold-patch guard PASS on all packets; (d) ablation-honesty audit PASS; (e) floor arm 0 resolved (or documented STOP); (f) 100% of calls receipted; (g) `UPLIFT_REPORT.json` contains Δ, CI, MDE statement, and claim boundary regardless of direction.

## 3. Ship Gate (M3.G)

**Predicate (tracker M3.G row):** G4 KPI — a valid measurement exists (not a positive result); Drift-Check 7/7; pre-registration conformance certified. Verifier class: M5-class (cross-family, fresh clone). NOT_RUN == FAIL. P8 (S00 resume) is tracked separately and does not gate M3.G.

**Required artifacts:**
1. ADR-M3-01 through ADR-M3-05 accepted (ADR-M3-06 for the P8 chain).
2. Frozen `PREREGISTRATION.md` + `.sha256` + independent verifier ACK artifact + tape digest event.
3. Packet materialization evidence: sha256 table, leakage-audit PASS, gold-patch-guard PASS, dataset digest assertion transcript.
4. Arm D floor report (0 resolved) and pilot calibration report (workers in the 15–45% band or logged replacement).
5. Per-arm frozen predictions + harness `evaluation_results.json` per (worker, arm) + rerun/exclusion log.
6. Ablation-honesty byte-diff audit output.
7. `UPLIFT_REPORT.{json,md}` produced by the frozen script only, + `DEVIATIONS.md` (complete, possibly empty).
8. **Mandatory `PROGRESS_TRACKER.md` update** with evidence paths per playbook §6.2.

## 4. Evals

### 4.1 Automated

- Analysis dry-run: `python3 analysis/analyze_uplift.py --fixture analysis/dryrun_fixture/` at freeze time — exit 0, outputs labeled FIXTURE.
- Leakage audit + gold-patch guard over every packet (existing audited tools; exit codes recorded).
- Ablation-honesty audit (RES_M3 §5.5): byte-diff of arm-B vs arm-C capsules per task; nonzero diff outside the broadcast-rules section = FAIL.
- Dataset digest assertion before materialization: fetched-rows digest == `sha256:43ed5a3d…`, else STOP (P14).

### 4.2 Scenario / LLM-judge

Scoped-down FCE-B1 checks (09 §5): a fresh-context agent, given only the evidence root, must (1) recompute the published Δ and CI by re-running the frozen script over the harness result files and match exactly; (2) confirm the pre-registration digest matches the packet bytes and predates the first receipt timestamp on tape. Rubric: both mechanical equalities hold = PASS; any reliance on implementer narrative = FAIL.

### 4.3 Performance

Per-50-task harness eval: 1–3 h expected (RES_M3 §2.6 — measure in the pilot; a pilot eval exceeding 5 h triggers a logged investigation before confirmatory arms). Total experiment: ~10 shard-sized evals. LLM spend tracked from receipts against the pre-registered ceiling (< US$1K); exceeding the ceiling is a pre-registered STOP.

### 4.4 Sandboxed harness

Arms B/C worker patch generation runs under the loop's sandbox policy — runsc where available per Intent §5.6 (constant sandbox kind within the experiment, M1d), else HOST_ASSUMED on tape; on this host runsc is available so HOST_ASSUMED = investigate. Scoring runs entirely inside upstream Docker containers (out of runsc scope by red line §5.7). Arm A is capsule-only with no repo mutation.

### 4.5 Thresholds

Pre-registration ACK before call #1 (timestamp comparison); floor arm: 0 resolved; pilot band: 15–45% per worker; leakage audit: 0 gold/held-out/PPUT markers in worker-visible artifacts; receipts: 100% of calls, 0 `cost_source_kind: unspecified`; harness exclusions ≤10% pairwise (else abort-restart); analysis: recomputation exact-match. Direction of Δ does NOT affect PASS.

### 4.6 Runnable instructions

RES_M3 §5.2 carries the verified command shapes (packet materializer — check `--help` first; qualified harness invocation with exact flags; receipts). Canonical scorer call shape (from the qualification packet):

```bash
cd /home/zephryj/turingos_backup/work/turing && source .venv_swebench/bin/activate
python -m swebench.harness.run_evaluation --dataset_name <pinned-name> --split test \
  --predictions_path predictions/preds_<worker>_<arm>.jsonl --max_workers 2 --timeout 1800 \
  --run_id uplift_<worker>_<arm>_<date> --report_dir scoring/uplift_<worker>_<arm>_<date>
# expected output: evaluation_results.json (schema_version 2) with resolved_ids/unresolved_ids/error_ids/incomplete_ids
```

## 5. Dependencies

- Upstream (hard): M1c (CostEvent.v2 receipts — ADR-M3-01 depends on the seam) and M1d (constant sandbox kind); M0 (governance chain, GateVerdict machinery); owner activation for repo writes. M3.P1 drafting may start in W0 (plan-directory work); the FREEZE needs M1c.
- Downstream: M4 consumes the frozen arm-B/arm-C outputs and receipts; M5.P4 certifies M3.G; the Verified-500 campaign stays paused until M3's gate passes (Intent §7).

## 6. Effort estimate + parallelization

- Tiering: pre-registration + frozen analysis script + all statistics = xhigh; worker adapter with receipts = high; running pre-specified arm sequences and packaging = medium.
- Wall-clock estimate: P1 drafting ≈ 1–2 agent-days (+ verifier ACK latency); P2 ≈ 0.5 day; P3 ≈ 2–4 h (one 50-task eval); P4 ≈ 0.5–1 day (pilot calls + one small scoring pass per worker); P5–P6 ≈ 3–6 days dominated by ~8 harness evals at 1–3 h each (RES_M3 §2.6) plus worker-call time; P7 ≈ 0.5 day; P8 ≈ 1 day. Module total ≈ 7–13 agent-days elapsed; M3 is the program's long pole (playbook §3.2 W3).
- Parallelization: strictly limited — arms run in the pre-registered order (D canary first, then pilot, A, B, then C); harness evals for different workers may interleave only within the pre-registered design and disk budget.

---

## Phases and atoms

Authoritative status lives in `PROGRESS_TRACKER.md` (M3 table).

### M3.P1 — Pre-registration freeze

#### ATOM-M3.P1-1 — Draft ADR-M3-01..05 + PREREGISTRATION.md (hypotheses, MDE, rerun policy, roster, budgets, task order). Gate: complete per ADR-M3-02 checklist. (Plan-directory work; may start in W0.)
#### ATOM-M3.P1-2 — Frozen `analyze_uplift.py` (stdlib-only, RES_M3 §5.6) + FIXTURE dry-run. Gate: dry-run exit 0, outputs labeled FIXTURE.
#### ATOM-M3.P1-3 — Freeze: sha256 packet, independent verifier ACK, digest on tape. Gate: ACK artifact predates any worker call.

### M3.P2 — Worker-safe packets

#### ATOM-M3.P2-1 — Assert dataset content digest; materialize S01 packets with the audited tool. Gate: sha256 table; supervisor never opens raw rows.
#### ATOM-M3.P2-2 — Leakage audit + gold-patch guard over all packets. Gate: both PASS; receipts/price fields on the blocklist.

### M3.P3 — Arm D floor canary

#### ATOM-M3.P3-1 — Run deterministic floor end-to-end through one full pipeline + harness scoring. Gate: 0 resolved; any solve = STOP + root-cause.

### M3.P4 — Pilot calibration

#### ATOM-M3.P4-1 — 10 S02 tasks per worker, arm A; score; check 15–45% band; replace out-of-band workers under the logged rule. Gate: calibration report; per-eval wall-clock measured.

### M3.P5 — Arm A

#### ATOM-M3.P5-1 — Arm A for all workers on S01; receipts per call; freeze predictions; harness score. Gate: predictions frozen before scoring; receipts 100%.

### M3.P6 — Arms B then C

#### ATOM-M3.P6-1 — Arm B (full loop, frozen task order). Gate: budgets identical to A; receipts 100%.
#### ATOM-M3.P6-2 — Arm C (ablation) + ablation-honesty byte-diff audit. Gate: only delta = broadcast-rules section.

### M3.P7 — Frozen analysis + report

#### ATOM-M3.P7-1 — Run the frozen script only; produce `UPLIFT_REPORT.{json,md}` with Δ, CIs, MDE statement, claim boundary; complete DEVIATIONS.md. Gate: recomputation-exact; null reported as valid PASS; hand to M5-class verifier.

### M3.P8 — S00 resume protocol (separate chain, after ADR-M3-01)

#### ATOM-M3.P8-1 — Stamp 48 predictions OLD-POLICY INVENTORY. Gate: stamps auditable; 48/50 never quoted as performance.
#### ATOM-M3.P8-2 — Produce the 2 missing predictions (`pydata__xarray-3677`, `pylint-dev__pylint-6386`) under new policy with receipts. Gate: receipts on tape.
#### ATOM-M3.P8-3 — astropy-12907 patch from an independent context fed solely the worker-safe capsule (taint protocol). Gate: context isolation evidenced.
#### ATOM-M3.P8-4 — Optional S00 scoring labeled mixed-policy inventory characterization. Gate: label present; excluded from uplift analyses.

### M3.G — Module gate

#### ATOM-M3.G-1 — Assemble §3 artifact list; run §4 evals; Drift-Check 7/7; M5-class cross-family verification of pre-registration conformance. Gate: module ADDRESSED.
