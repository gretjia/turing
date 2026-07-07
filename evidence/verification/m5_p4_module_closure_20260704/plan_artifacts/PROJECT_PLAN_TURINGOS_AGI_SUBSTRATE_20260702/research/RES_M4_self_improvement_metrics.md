# RES_M4 — Research Report: Self-Improvement & North-Star Metrics (H-VPPUT measurability + failure-memory causality)

- Module: M4 — Self-Improvement & North-Star Metrics
- Date: 2026-07-02
- Author: Research agent (Fable-5-class), M4 research track (commissioned as atom M4.P0 per playbook §3.4)
- Status: RESEARCH INPUT to the M4 module plan. This document confers no CLOSED/RATIFIED status on anything. All on-disk claims below were verified against the workspace on 2026-07-02 at repo `./turing` (branch `goal/mini-swe-bench-grok-worker`, HEAD `bed759777f9cb21c53e5701c8070654ad4dc4212`); every such claim carries an absolute path. Claims sourced from the public web are marked WEB and dated; claims that are reasoned analysis (not measured) are marked ANALYSIS.
- Serves: KPI G5 (self-improvement measurability). Directly answers audit finding F7 (H-VPPUT unmeasurable — estimated cost only; failure-memory efficacy lineage-proven only, zero causal evidence) in `/home/zephryj/turingos_backup/work/TURINGOS_RETROSPECTIVE_AUDIT_FINDINGS_20260702.md`.
- Binding anchor: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/01_PROJECT_INTENT.md` (G5: "Ablation delta from G4; H-VPPUT computed on held-out tasks with billing-complete (or explicitly bounded) cost; PPUT/heldout internals never visible to workers").
- Schema authority note (binding): everything cost-shaped in this report defers to ADR-M1-004 CostEvent.v2 (RES_M1 §2.6/§5.5) per playbook §3.5 — integer micro-USD only, closed `cost_source_kind` enum, pinned `price_table_digest`. M4 owns no tape schema; it is a pure derived-view consumer.
- Revision 1.1 (2026-07-02, same session date): append-only extension completing the commissioned M4.P0 scope — §2.7 (provider usage reporting + receipt-to-tape binding + classification rules), §2.8 (broadcast-rule lifecycle with Art. II.1 discipline and the Stage10 leakage denylist), §5.7 (worked FIXTURE H-VPPUT example), §5.8 (lifecycle audit commands), pitfalls P11–P14, ADR-M4-006/-007. Every pre-existing section number (§2.1–2.6, §3, §4 P1–P10, §5.1–5.6, §6 ADR-M4-001..005) is unchanged, so all citations in `modules/MODULE_M4_self_improvement.md` v1.0.0 and the tracker M4 rows remain resolvable. This revision changes the file's sha256; the tracker pin (`30244d86…`) requires a Decision Log re-pin entry per playbook §1 step 3 — flagged to the orchestrator, not performed here.

---

## 1. Questions this research answers

1. What, exactly, is H-VPPUT as defined by the repo's own north-star documents, and which parts of that definition are currently unmeasurable (audit F7)?
2. How is H-VPPUT made *computable* from CostEvent.v2 receipt events — including the integer-only/no-floats-on-tape constraint — and what does the frozen metric script look like?
3. How are billing-complete and bounded-estimate cost inputs handled without laundering incompleteness (the two-class discipline)?
4. What is the "held-out" task set for the H-VPPUT computation, how is the registry represented, and how is worker-invisibility of PPUT/heldout internals enforced mechanically (Art. III.4)?
5. What causal-analysis design turns M3's arm-B-vs-arm-C ablation into evidence about failure-memory efficacy — and what may NEVER be claimed from lineage-only signals (the stage14 lesson)?
6. What does an honest "no measurable self-improvement" report look like, verbatim, so a null result is a valid PASS?
7. Which existing repo components (PPUT crate, strict auditor checks, leakage blocklists, stage14 audits) are reused versus what must be built?
8. What usage reporting do the four candidate providers (OpenAI, Anthropic, xAI, DeepSeek) actually offer — inline response `usage` vs org-level usage/cost APIs — and what are the exact mechanical rules that bind a provider receipt to a tape event and assign it a cost class?
9. What is the full broadcast-rule lifecycle (mine → certificate → abstract rule → activation → consumption → retirement) as evidenced on tape today, where does it enforce Art. II.1's abstract-rules-only broadcast discipline via the Stage10 leakage denylist, and which lifecycle stage does not exist yet?
10. What does a worked, checkable H-VPPUT computation look like on a small FIXTURE input, end to end (receipts → classes → portfolio pair → decimal rendering)?

---

## 2. Candidate methodologies, patterns, and stacks

### 2.1 On-disk ground truth this module builds on (all verified 2026-07-02)

- **The north-star definition exists and is prescriptive.** `/home/zephryj/turingos_backup/work/turing/docs/adr/ADR-PPUT-North-Star.md` ("Held-Out Verified PPUT as North Star", status "Accepted for P0 Greenfield execution baseline") defines: `Progress_i = 1 iff verified golden path exists`; `VPPUT_i = 1[GroundTruth(G_i)=1] / (C_i * T_i)`; `PPUT-M = 1_000_000 * VPPUT_i`, where `C_i` "includes all agents, branches, failed proposals, hidden trials, reranks, tool calls, tool stdout context, abandoned market bets, replay verification, and other counted token costs" and `T_i` is "wall time from first read to final accept". It mandates six event families (`CostEvent`, `BranchCostEvent`, `ToolStdoutCostEvent`, `PPUTProposalRecord`, `PPUTAccounted`, `HeldoutGuardViolation`) and gates `G-PPUT-01..07`, and declares "PPUT is a hidden evaluator, not a Worker-visible objective". The greenfield book's north-star line is `Maximize held-out Verified PPUT under constitutional constraints.` (`/home/zephryj/turingos_backup/work/turing/docs/project_books/TURINGOS_AGENT_ECONOMY_RUNTIME_GREENFIELD_v1_0.md:50`).
- **PPUT plumbing exists in Rust.** `/home/zephryj/turingos_backup/work/turing/crates/turing-pput/src/lib.rs`: `CostEvent` struct (line 21), `PPUTAccounted` produced by `account()` (lines 126–171), `WorkerPromptShield` (line 234). The shield is tested to reject held-out references in worker prompts: `crates/turing-pput/tests/pput_accounting.rs:118` asserts `WorkerPromptShield::validate("Optimize PPUT on heldout ids.").is_err()`. The loop contract already carries `pub heldout_ids: Vec<String>` (`crates/turing-loop/src/lib.rs:390`, serialized at line 500) — held-out IDs are a supervisor-side contract field, never a worker field.
- **The strict auditor already enforces PPUT truth-shape, but only conservation, not source.** `/home/zephryj/turingos_backup/work/turing/tools/bench/audit_micro_tape_decision_dag.py`: an accepted run must carry a post-accept final `PPUTAccounted` with `progress == 1` (lines 668–687); a failed run with nonzero PPUT progress is a hard FAIL — "Failed runs must have Progress_i = 0 and VPPUT_i = 0" (lines 688–699); `cost_conservation_status` checks final `PPUTAccounted.total_run_token_count` equals the sum of matching `CostEvent` token counts (lines 738–776); `--strict-vpput` requires `vpput_accounting == PASS` (lines 931–949, flag at 1133). None of these checks knows anything about cost SOURCE — that is M1c's `--require-cost-provenance` extension (RES_M1 §2.6 item 4).
- **The F7 defect is concrete and located.** The live cost numbers are word-count pseudo-estimates: `prompt_tokens_estimate: len(prompt.split())` (`/home/zephryj/turingos_backup/work/turing/tools/bench/run_mini_swe_bench_substrate_smoke.py:498–500`). Where a `cost_source_kind` is written at all it is the non-enum value `"estimated_tokens"` (`tools/bench/build_stage16r_unsolved_repair.py:351,445`), and the stage16 audit defaults absent kinds to `["unspecified"]` (`tools/bench/audit_stage16_sealed_campaign.py:111–117`). No monetary amount, price table, or provider receipt exists on any tape. H-VPPUT's denominator is therefore currently a fiction; the audit's F7 verdict is exactly right.
- **The causal gap is also concrete and self-documented.** The only failure-memory efficacy artifact in the repo says so itself: `/home/zephryj/turingos_backup/work/turing/evidence/bench/mini_swe_bench_stage14_corpus_failure_memory_20260628/broadcast_rule_efficacy_audit.json` = `{"causal_claim_allowed": false, "claim": "Observed association only; no causal claim from fixture sample.", "consumed_rule_attempts": 1, "non_consumed_comparable_attempts": 0, "sample_size": 4, ...}`. The same root's `cross_task_memory_lineage.md` proves rule generation→consumption lineage only. Reusable audit tooling exists: `tools/bench/audit_failure_memory_activation.py` (activation + later capsule consumption; FORBIDDEN_VISIBLE_MARKERS include `pput formula`, `vpput formula`, `heldout`) and `tools/bench/audit_corpus_failure_memory.py`.
- **Leakage enforcement exists and already blocklists this module's internals.** `/home/zephryj/turingos_backup/work/turing/tools/bench/audit_prompt_leakage.py:16–28` FORBIDDEN_MARKERS include `pput`, `vpput`, `heldout`, `hidden predicate`, `gold patch`, `official solution`.
- **Upstream inputs this module consumes (plan-directory, pinned):** CostEvent.v2 receipt schema — RES_M1 §5.5 payload shape, §2.6 constraints (integer micro-USD; closed enum `{provider_receipt_inline, provider_usage_api_reconciled, bounded_estimate, fixture}`; the codec rejects floats — `turing/src/turingos/codec.py:50–63`, `crates/turing-contracts/src/jcs.rs:132–135` per RES_M1 §2.6 item 1). M3 experiment outputs — evidence-root layout RES_M3 §5.1, receipts RES_M3 §5.3, frozen-analysis idiom RES_M3 §5.6, hypotheses H1/H2 RES_M3 §2.3.

### 2.2 Operationalizing H-VPPUT: three candidate definitions

| Candidate | What it is | Pros | Cons |
|---|---|---|---|
| **A. Verbatim ADR formula, token-denominated** — `VPPUT_i = progress_i / (tokens_i × wall_ms_i)` | Direct reading of ADR-PPUT-North-Star with `C_i` in tokens | Matches the existing `PPUTAccounted.total_run_token_count` conservation check (§2.1); no price table needed | Not billing-grounded — tokens across providers are incommensurable (a Haiku token ≠ a DeepSeek token in $); leaves F7's "billing-complete" requirement unmet; unit product token·ms is unintuitive |
| **B. Money-denominated H-VPPUT from CostEvent.v2 receipts (RECOMMEND as primary)** — per task: `progress_i ∈ {0,1}`, `cost_i` = Σ `cost_microusd` over ALL of the task's run receipts (failed attempts included, per the ADR's C_i definition), `time_i` = Σ `wall_time_ms`; report the exact rational `progress_i / (cost_i × time_i)` and the portfolio aggregates of §2.3 | Billing-grounded (F7 closure); provider-heterogeneous rosters comparable; the receipts are already integer micro-USD by schema | Requires M1c landed (hard dependency, already in the tracker); division produces non-integers — resolved by keeping the metric OFF-tape (§2.4) |
| C. Cost-only efficiency (`solves per dollar`), dropping `T_i` | Simpler denominator | Robust, easy to explain | Silently amends the accepted ADR (drops wall time); wall-time is a real physical cost the ADR deliberately counts. REJECT as the *primary*; keep `solves_per_dollar` and `solves_per_1M_tokens` as mandatory companion aggregates (they are also RES_M3 §2.3's pre-registered exploratory metrics — do not fork definitions) |

**Integer/floats resolution (load-bearing; ANALYSIS grounded in the codec constraint):** the no-floats rule applies to TAPE bytes, not to analysis artifacts. The clean split: tape carries only the *inputs* (CostEvent.v2 receipts — integers); the metric lives in derived-view analysis JSONs in the evidence root, where each H-VPPUT value is represented as an exact integer pair `{"numerator": p, "denominator_microusd_ms": c*t}` plus a decimal-string rendering `"hvpput_m_str"` (the ADR's PPUT-M scaling, `1_000_000 × VPPUT_i`, rendered to fixed precision) — never a JSON float, so the artifact stays codec-subset-clean and byte-reproducible. This also honors the ADR's own "PPUT projections must be rebuildable from Micro Tape": the analysis JSON is a projection, recomputable from receipts (§5.2).

**Aggregation (ANALYSIS):** per-task VPPUT is noisy and zero-inflated (progress=0 ⇒ VPPUT=0 exactly — enforced shape, §2.1 auditor check). Do not average per-task ratios (ratio-of-averages vs average-of-ratios instability at n=50). Report, in this order: (1) portfolio H-VPPUT = `Σ progress_i / (Σ cost_i × Σ time_i normalized per task)` — concretely the pair `total_solves`, `total_cost_microusd`, `total_wall_ms` plus derived `solves_per_dollar` and `solves_per_wall_hour`; (2) per-arm portfolio values for A, B, C so the *uplift-efficiency* contrast (arm B vs arm A cost-normalized) is visible; (3) per-task exact rationals in a table for auditability. Confidence intervals via the same cluster-by-task bootstrap machinery as RES_M3 §5.6 (resample tasks, recompute portfolio aggregates), labeled with RES_M3's MDE honesty rule.

### 2.3 The two cost classes: billing-complete vs explicitly bounded

The Intent's G5 KPI phrase "billing-complete (or explicitly bounded) cost" becomes machine-checkable via `cost_source_kind` (closed enum, RES_M1 §2.6 item 4):

| Run class | Definition (mechanical) | H-VPPUT treatment |
|---|---|---|
| **BILLING_COMPLETE** | 100% of the run's cost events have `cost_source_kind ∈ {provider_receipt_inline, provider_usage_api_reconciled}` | Point estimate reported |
| **BOUNDED** | ≥1 event with `cost_source_kind = bounded_estimate` (each carrying its `bound_kind` derivation per RES_M1 §2.6 item 5), zero `unspecified`, zero `fixture` | Interval reported: the bounded events contribute their upper-bound cost, so the published H-VPPUT is a **lower bound** and is labeled `hvpput_bound_kind: "lower_bound_via_cost_upper_bound"`; no point estimate |
| **INADMISSIBLE** | any event with `cost_source_kind` absent, `unspecified`, or non-enum (e.g. the legacy `estimated_tokens` string, §2.1); or any `fixture` event in a REAL run | Run EXCLUDED from H-VPPUT, listed by run_id in the report's exclusion table with the offending event refs. Exclusions are never silent |

Class is computed per RUN, and the report states the class breakdown (`n_billing_complete / n_bounded / n_excluded`) in its headline block. Laundering rule: a report that mixes classes without the breakdown, or averages a bounded run into a point estimate, is invalid by construction — the frozen metric script (§5.2) enforces this structurally, not by reviewer vigilance. Historical (pre-M1c) tapes are permanently INADMISSIBLE for H-VPPUT (they are word-count estimates, §2.1); they may appear only in a clearly-labeled "legacy, not H-VPPUT" appendix. This mirrors the M1.G scoping already in the tracker (post-M1c tapes only).

### 2.4 Held-out discipline: registry, computation surface, and worker-invisibility

- **What "held-out" means here (ANALYSIS, grounded in the ADR + Intent):** tasks whose identities and outcomes were never available to tune the substrate's policies, prompts, or memory contents, and whose IDs are never worker-visible as a *set* (a worker necessarily sees the one task it is solving; it must never see that the task belongs to a measurement set, nor the set's membership, nor the metric computed over it). For this increment the held-out set is **shard S01 exactly as frozen by M3's pre-registration** — verified untouched before the experiment (RES_M3 §2.5: S01 contains only `shard_manifest.json`, no packets, no predictions) and sealed by digest before any worker call. H-VPPUT is computed post-hoc over M3's frozen S01 outputs; no new worker calls are needed or permitted (FCE §1.2: S01 confirmatory results are never re-run).
- **Registry representation:** a supervisor-side file `heldout_task_registry.v1.json` in the M4 evidence area: `{schema_id, shard: "S01", shard_manifest_sha256, instance_ids: [...], registry_sha256_self_excluded, created_at_utc}` — digest-pinned and cited by the north-star report. It lives OUTSIDE every worker-visible directory (never under any `worker_safe_tasks/` tree) and its path is added to the leakage sweep surface. FCE-B1 check 8 requires exactly this: recompute H-VPPUT "from tape receipt events and the held-out task registry ONLY" and "assert ... that the held-out registry has no worker-visible read path" (`09_FINAL_CERTIFICATION_EVALS.md` §5, line 210).
- **Enforcement is a blocklist re-run, not prose:** the existing markers already cover this module (`pput`, `vpput`, `heldout` — `audit_prompt_leakage.py:16–28`; `pput formula`, `vpput formula`, `heldout` — `audit_failure_memory_activation.py` FORBIDDEN_VISIBLE_MARKERS). M4's evals re-run `audit_prompt_leakage.py` over every worker-visible artifact of the runs it consumes and additionally grep for the registry filename and `hvpput` (add the marker — the existing list predates the H-prefix). `WorkerPromptShield` (§2.1) remains the in-loop guard; `HeldoutGuardViolation` is the ADR's event family for a tripped guard.

### 2.5 Failure-memory causal analysis: design candidates

| Candidate | What it is | Pros | Cons |
|---|---|---|---|
| **A. Consume M3's pre-registered H2 contrast verbatim (RECOMMEND as the only confirmatory analysis)** | The causal estimand is fixed by M3: H2 = p(resolved\|B) > p(resolved\|C), exact McNemar + cluster-bootstrap CI, Holm step 2, on frozen S01 (RES_M3 §2.3, ADR-M3-03). Arms B and C differ ONLY in broadcast-rule injection, enforced by the ablation-honesty byte-diff audit (RES_M3 §5.5). M4 re-reads `UPLIFT_REPORT.json` + the per-arm `evaluation_results.json` files and the honesty-audit output; it re-derives nothing and re-runs nothing | The ablation IS the causal design (randomization surrogate: same tasks, same worker, same budgets, single intervention); pre-registered, so zero analyst degrees of freedom; a second analysis pipeline reaching a different number would be a defect, not insight | M4 produces no *new* confirmatory number — by design. If M3's H2 is null, M4's causal section is a null report (that is a valid PASS, §2.6) |
| B. Fresh confirmatory analysis by M4 (re-test H2 with different statistics) | e.g. Bayesian or regression-adjusted re-analysis | "More" analysis | Post-hoc metric shopping — exactly what pre-registration forbids; REJECT for confirmatory use; permitted only as clearly-labeled sensitivity analysis noting it was not pre-registered |
| **C. Exploratory mechanism analyses (RECOMMEND as labeled EXPLORATORY companions)** | From tape only: (i) dose-response — per-task count of `consumed_broadcast_rule_ids` (the consumption field already exists in the loop capsule payloads, RES_M3 §2.2 arm C definition) vs outcome; (ii) memory cost accounting — tokens/µUSD spent on rule injection per task (receipts) vs marginal outcome; (iii) rule-lineage table reusing `audit_failure_memory_activation.py`'s consumption tracing | Mechanistic texture; feeds the FCE-C1 injection-budget comparative eval's design; cheap (pure post-processing) | Zero error control — every output stamped EXPLORATORY with `causal_claim_allowed: false`, the stage14 idiom (§2.1) |

**Claim discipline (binding, from the evidence):** lineage/consumption/association signals NEVER support "failure memory works" — the repo's own stage14 artifact models this honesty (`causal_claim_allowed: false` with `sample_size: 4`, §2.1). The sentence "failure memory causally improves solve probability" is permitted ONLY if M3's pre-registered H2 passes with positive direction (mirror of RES_M3's H1 claim rule); otherwise the report states the estimand, Δ_BC, CI, and MDE, and stops.

### 2.6 The honest-null report: what "no measurable self-improvement" looks like

The north-star report (M4.P3) has a fixed skeleton written BEFORE results exist (frozen with the metric script), with every field mandatory regardless of direction (ANALYSIS; language rules inherited from RES_M3 §2.1's reporting-honesty rule, which FCE-B1 check 6 enforces mechanically — "a null result phrased as 'no effect' is a FAIL"):

1. Headline block: run-class breakdown (§2.3), per-arm portfolio H-VPPUT (or bounds), Δ_BC with CI, MDE statement verbatim from the M3 pre-registration.
2. Mandatory sentence templates: positive → "Δ_BC = x [CI a,b], H2 passed at pre-registered α; failure-memory contribution is supported at this scale." Null → "Δ_BC = x [CI includes 0]; the study was powered for MDE = y; smaller true effects are not excluded. No failure-memory efficacy claim is made." Negative → same as null plus "the point estimate is negative; a harm hypothesis was not pre-registered and is flagged for a future pre-registered study."
3. `CLAIM_BOUNDARY.json` with `failure_memory_causal_claim_allowed: <bool tied to H2>`, `hvpput_is_capability_claim: false`, `absolute_rate_is_capability_claim: false` (reuse the campaign pattern at `/home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_verified_500_campaign_20260629/CLAIM_BOUNDARY.json`).
4. Exclusion and deviation tables (from §2.3's inadmissibility rules and M3's `DEVIATIONS.md`), always present even when empty.

### 2.7 Provider usage reporting and receipt-to-tape binding (what makes BILLING_COMPLETE real)

Schema ownership stays with ADR-M1-004 (header note); this section is M4's *consumption-side* specification: what each provider verifiably reports, and the mechanical rules the metric script applies when reading receipts. Two layers, per RES_M1 §2.6:

**Layer 1 — per-call inline `usage` (the load-bearing receipt):**

| Provider | Inline usage fields (verbatim capture) | Receipt anchors | Source / label |
|---|---|---|---|
| OpenAI | `usage: {prompt_tokens, completion_tokens, total_tokens, prompt_tokens_details.cached_tokens}`; `completion_tokens` includes hidden reasoning tokens on reasoning models (breakdown in `completion_tokens_details.reasoning_tokens`) | response `model` (resolved), response `id`, `x-request-id` header | RES_M1 §2.6 Layer 1 (WEB, 2026-07-02); reasoning-token inclusion: ANALYSIS from the details-field semantics — billed as output either way, so top-level fields remain cost-sufficient |
| xAI (Grok) | OpenAI-compatible: `usage: {prompt_tokens, completion_tokens, total_tokens, prompt_tokens_details.cached_tokens, completion_tokens_details.reasoning_tokens}` | response `model`, response `id`, `x-request-id` | WEB, verified 2026-07-02: [xAI docs — consumption](https://docs.x.ai/docs/key-information/consumption-and-rate-limits), [Promptfoo xAI provider](https://www.promptfoo.dev/docs/providers/xai/) |
| Anthropic | `usage: {input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens}` | response `model`, `request-id` header / `_request_id` | RES_M1 §2.6 Layer 1 (WEB, 2026-07-02); also RES_M3 §2.8 via the local claude-api skill catalog |
| DeepSeek | OpenAI-compatible PLUS top-level `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens`; cache-hit vs cache-miss unit prices differ ~50x, so collapsing them into `prompt_tokens` mis-costs runs badly | response `model`, response `id` | RES_M1 §2.6 Layer 1 + pitfall 10 (WEB, 2026-07-02: DeepSeek pricing/context-caching docs) |

**Layer 2 — org-level usage/cost APIs (optional reconciliation, never a dependency):** OpenAI `GET /v1/organization/usage/completions` + `/v1/organization/costs` (Admin API key required); Anthropic `usage_report/messages` + `cost_report` (Admin key + **Team/Enterprise plan** — individual accounts cannot access); xAI Management API at `https://management-api.x.ai` with a billing-usage endpoint (historical usage aggregated by group-by fields, separate management key required) — WEB, verified 2026-07-02: [xAI Management API billing reference](https://docs.x.ai/developers/rest-api-reference/management/billing), [Management API guide](https://docs.x.ai/developers/management-api-guide); OpenAI/Anthropic rows per RES_M1 §2.6 Layer 2 (WEB, 2026-07-02). DeepSeek: no org-level usage API found in its public docs (WEB-NEGATIVE, 2026-07-02 — absence claim, treat as "not relied upon"). REASONED consequence (inherited from RES_M1): Layer 2 is plan/key-gated and may be unavailable to this program's accounts; therefore BILLING_COMPLETE must be reachable from Layer 1 alone.

**Receipt-to-tape binding rules (mechanical, enforced by the metric script when reading):**

1. **One CostEvent.v2 per LLM call**, appended supervisor-side at the `WorkerAdapter` seam (RES_M1 R-M1-4); the binding chain is: tape event (usage integers + digests) ↔ `receipts/<request_sha256>.json` (full receipt) ↔ zstd-compressed raw request/response bodies keyed by digest (RES_M3 §2.8). The tape never carries bodies or secrets; `provider_request_id` is the external dispute anchor.
2. **`provider_receipt_inline` requires ALL of:** verbatim `usage` object with the provider-appropriate field set (table above, keyed by `usage_schema`), `model_reported` non-empty, `provider_request_id` non-empty, `request_sha256` + `response_sha256` present, `price_table_digest` matching the pre-registration's pinned table. Any missing element downgrades the CALL (not the run) to `bounded_estimate` at WRITE time by the adapter — the metric script re-verifies and hard-fails on a `provider_receipt_inline` event missing any element (misclassification is a defect, never silently reclassified at read time).
3. **Deterministic integer costing with ceiling rounding:** `cost_microusd = Σ_token_class ceil(tokens_class × unit_price_microusd_per_mtok(provider, model, token_class) / 10^6)`, price table keyed on (provider, model, token_class) so DeepSeek's cache split and Anthropic's cache-write/read classes each get their own row. Ceiling (never round-half) so recomputation is byte-identical and cost is never undercounted (ANALYSIS; codec-driven — floats are unrepresentable anyway).
4. **`provider_usage_api_reconciled` is an upgrade, not a source:** it may be assigned only in a post-hoc reconciliation pass that cites the Layer-2 bucket reference (endpoint, time bucket, group-by key) AND finds the run's Layer-1 totals within the bucket's totals under a pre-stated tolerance. Layer-2 buckets are aggregates and cannot be matched per-call; on any mismatch the events KEEP their Layer-1 class and the discrepancy is logged in the report's reconciliation note. Reconciliation never rescues an INADMISSIBLE run.
5. **Streaming caveat (ANALYSIS):** streamed responses only carry `usage` when explicitly requested (OpenAI-compat `stream_options: {include_usage: true}`); the adapter must either request it or use non-streaming calls for measured arms. A streamed call that arrives without usage is `bounded_estimate` by rule 2 — this is the most likely accidental BOUNDED-class source and the pre-registration should simply forbid streaming in measured arms.
6. **`fixture` events** appear only in FIXTURE-labeled runs (self-tests, dry-runs); rule inherited from §2.3 — any `fixture` event in a REAL run makes the run INADMISSIBLE.

These six rules are the complete bridge from Intent §2 G5's phrase "billing-complete" to bytes: a run is BILLING_COMPLETE exactly when every one of its calls satisfies rule 2 (or was upgraded under rule 4), and the resulting integers recompute under rule 3 from tape + price table alone.

### 2.8 Broadcast-rule lifecycle: mine → certificate → abstract rule → activation → consumption → retirement

The failure-memory object M4 must measure has a defined lifecycle, five-sixths of which already exists on tape (all paths verified 2026-07-02); Art. II.1 of the constitution (`turing_v5/pack_v5_3_1/00_authority/constitution_root_law.md` §2.1 "广播典型错误 [Art. II.1]") fixes its discipline: when multiple agents fail the same way, the top layer must (1) abstract the typical error, (2) update the global architecture document, (3) broadcast the ABSTRACTED rule — and must never mass-broadcast concrete error logs ("灾难性的上下文污染" — catastrophic context pollution).

| Stage | Tape evidence (verified) | Mechanics |
|---|---|---|
| **1. Mine** | `FailureNode` events with `failure_class` from the closed 10-class Stage10 taxonomy (`INSTALL_FAIL, TEST_TIMEOUT, WRONG_FILE, NO_REPRO, OVERBROAD_PATCH, SEMANTIC_FAIL, FLAKY_ORACLE, DEPENDENCY_GAP, CONTEXT_MISSING, PATCH_APPLIES_BUT_WRONG` — `turing/tools/bench/audit_failure_taxonomy.py:16–27`); stage10 fixture root covers all 10 (`evidence/bench/mini_swe_bench_stage10_failure_taxonomy_20260628/failure_taxonomy_audit.json`) | Failed attempt → classified failure node; raw logs go to CAS as `raw_log_ref` digests only |
| **2. Certificate** | `FailureCertificate` with `source_failure_node_id`, `failure_class`, `abstract_pattern`, `raw_log_ref` (digest), `raw_log_text_absent: true`, and a `broadcast_rule_candidate {candidate_only: true, activation_event_id: null, new_instruction, hidden_predicates_absent: true, pput_or_heldout_details_absent: true}` (`run_mini_swe_bench_substrate_smoke.py:940–960`) | Preserve-only: the Stage10 auditor FAILs any taxonomy fixture containing `BroadcastRuleActivated` or `CandidateAccepted` (`audit_failure_taxonomy.py:104–107`) — candidates are mined without being empowered |
| **3. Abstract rule + activation** | `BroadcastRuleActivated` with `rule_id`, `source_failure_nodes[]`, `failure_class`, `abstract_pattern`, `guidance`, `raw_log_refs` (digests), `raw_log_text_absent`/`hidden_predicates_absent` (`run_mini_swe_bench_substrate_smoke.py:2146–2160`); stage14 shows cluster-gated activation: `min_source_failures: 3`, `source_failure_count: 3` (`.../stage14_.../corpus_failure_memory_audit.json`) | Art. II.1's "typical error" test made mechanical: activation from a CLUSTER of same-class failures, not one anecdote; the rule payload is abstract guidance, never log text |
| **4. Consumption** | `WorkCapsuleBuilt` carrying `injected_broadcast_rule_ids`, `consumed_broadcast_rule_ids`, `broadcast_rule_event_id`, and `visible_known_failures_to_avoid` (guidance strings only — `run_mini_swe_bench_substrate_smoke.py:2195–2206, 5257–5259`); worker-visible rendering is exactly `"Known failures to avoid:\n- {failure_class}: {guidance} (source rule {rule_id})"` (`visible_grok_prompt`, lines 343–351); `audit_failure_memory_activation.py` proves `later_capsule_consumed_rule: true` (stage11: 3/3 PASS, stage14 cross-task: `cross_task_memory_lineage.md`) | The `consumed_broadcast_rule_ids` field is the dose variable for §2.5 C's exploratory dose-response; injection cost is measurable from receipts (rule text tokens are prompt tokens) |
| **5. Leakage denylist (cross-cutting)** | `FORBIDDEN_BROADCAST_MARKERS` (`audit_failure_taxonomy.py:28–45`): `traceback, stack trace, raw stdout, raw stderr, hidden predicate, hidden_predicate, private_micro_contract, pput formula, vpput formula, heldout, official_solution, gold patch, auth.json, signing_key_hex, private key, sk-` — swept over EVERY string in the candidate via a recursive walker (`candidate_strings`, lines 69–87), plus boolean attestations `raw_log_text_absent`/`hidden_predicates_absent` checked at lines 130–137 | This is the Stage10 approach the module adopts wholesale: denylist + attestation booleans + recursive string sweep, run per rule at certificate AND activation time. M4 adds `hvpput` and the registry filename to the marker set (consistent with §2.4) |
| **6. Retirement** | **VERIFIED GAP — does not exist.** No retirement/deactivation/expiry mechanism anywhere: grep over `tools/`, `crates/`, `src/` for retire/deactivate/`rule_status`/expired in any broadcast-rule context returns zero hits (2026-07-02); `read_broadcast_rules` (`run_mini_swe_bench_substrate_smoke.py:132–140`) loads every rule in the file unconditionally | Design below (ANALYSIS) |

**Retirement design (ANALYSIS; the missing lifecycle stage, ADR-M4-006):** rules that never help (or that stop applying) must leave the active set, or the active-rule pile grows without bound — precisely the "indiscriminate full broadcast → communication overload" failure Art. II.1 exists to prevent, plus an unbounded prompt-token cost visible in receipts. Mechanism: a supervisor-side `BroadcastRuleRetired` tape event `{rule_id, activated_rule_event_id, retirement_reason ∈ {superseded_by_rule, dose_response_null, scope_expired, injection_budget_pressure}, evidence_ref, retired_at_utc}` — append-only (retirement is an event, never deletion; replay reconstructs the active set at any head), with `read_broadcast_rules` gaining an active-set filter. Discipline: (i) retirement decisions MAY cite M4's EXPLORATORY dose-response artifacts as `evidence_ref`, but retirement is an operational pruning decision, never a causal claim — the artifact it cites keeps `causal_claim_allowed: false`; (ii) the active-rule injection budget (max rules and max rule-tokens per capsule) is pre-registered, feeding FCE-C1's injection-budget comparative eval; (iii) the event type is a tape-schema addition, so M4 *proposes* it and M1 (tape owner) lands it — M4 owns lifecycle measurement, never lifecycle events. Ownership split for the rest of the lifecycle: the loop/M3 own stages 1–4 at run time; M4 consumes them read-only.

**Claim ceiling per lifecycle stage (binding, extends §2.5):** stages 1–4 on tape license only protocol claims ("rules are mined, certified, activated from clusters, and consumed — lineage-proven"), which is exactly what stage14's own artifacts claim and no more. Efficacy language for the lifecycle as a whole remains gated on M3's H2 (§2.5). If H2 is null, the lifecycle sections of the north-star report state the protocol result and the null verbatim (§2.6 templates) — the lifecycle machinery is still a valid, publishable protocol PASS.

---

## 3. Recommendation (tied to project goals)

**Adopt: money-denominated H-VPPUT computed by a frozen stdlib-only metric script over CostEvent.v2 receipts and the upstream-harness results of M3's frozen S01 runs, with the two-class billing-complete/bounded discipline, S01-as-held-out registry, confirmatory failure-memory causality taken verbatim from M3's pre-registered H2, and exploratory mechanism analyses stamped `causal_claim_allowed: false`.**

- **G5 KPI, directly:** "H-VPPUT computed on held-out tasks with billing-complete (or explicitly bounded) cost" becomes three mechanical predicates — enum-checked receipts (§2.3), registry-only task selection (§2.4), recomputable analysis JSON (§2.2) — each testable by FCE-B1 check 8. "Ablation delta from G4" is consumed, not duplicated (§2.5). "PPUT/heldout internals never visible to workers" rides existing blocklists plus one added marker (§2.4).
- **Anti-Goodhart (Intent §5.5, Vision):** the metric never becomes a worker objective (hidden-evaluator ADR reaffirmed); the report certifies measurement validity, not direction — a tight null is a PASS, matching Intent G4/G5's "valid measurement" framing and FCE §8's anti-Goodhart threshold note.
- **Replayability (Intent §6):** every number in the north-star report is a pure function of digest-pinned inputs (receipt events on tape, harness result files, registry file, price table via `price_table_digest`); the frozen script re-emits byte-identical JSON on re-run (integer pairs + decimal strings, no floats, sorted keys).
- **Modularity/effort:** zero new tape writers, zero worker paths, zero new confirmatory statistics — the module is a disciplined post-processor. New code: one metric script (§5.2), one registry file (§5.3), one report assembler. Everything else reuses turing-pput shapes, the strict auditor, RES_M3 §5.6's bootstrap, and the leakage auditors.
- **Billing-complete from Layer 1 alone (Rev 1.1):** the six binding rules of §2.7 make BILLING_COMPLETE reachable with nothing but inline response `usage` — no plan-gated admin APIs on the critical path (RES_M1's Layer-2 availability risk is absorbed as an optional upgrade). Ceiling-rounded integer costing makes recomputation byte-identical, serving Intent §6 replayability directly.
- **Lifecycle honesty (Rev 1.1):** adopt the Stage10 denylist + attestation + cluster-activation pattern verbatim for all rule surfaces; propose `BroadcastRuleRetired` to M1 rather than letting the active set grow unboundedly (Art. II.1 context-pollution discipline); keep every lifecycle claim at its stage's ceiling (§2.8) so the failure-memory story can never outrun H2.
- Explicitly rejected: token-only H-VPPUT as primary (not billing-grounded — F7 would survive); any fresh confirmatory re-analysis of H2 (metric shopping); computing H-VPPUT on S00 or any mixed-policy inventory (RES_M3 §2.9: never feeds analyses); putting metric values on tape (floats/derived-view discipline — the tape carries inputs, projections are rebuildable); Layer-2 usage APIs as a BILLING_COMPLETE prerequisite (plan/key-gated, aggregate-only — reconciliation upgrade at most); M4-owned tape events for rule retirement (schema belongs to M1).

---

## 4. Pitfalls & mitigations

| # | Pitfall | Mitigation |
|---|---|---|
| P1 | **Metric Goodharting** — H-VPPUT or its components leak into worker context and become an optimization target | Hidden-evaluator rule (ADR-PPUT-North-Star) re-enforced: leakage sweep over all worker-visible artifacts with `pput`/`vpput`/`heldout` + new `hvpput` + registry-filename markers; `WorkerPromptShield` in-loop; FCE-B2 re-tests at certification |
| P2 | **Cost incompleteness laundered as billing-complete** — a bounded or unspecified event slips into a point estimate | Two-class discipline is structural in the frozen script (§2.3, §5.2): class computed per run from the enum, mixed reporting is unrepresentable; INADMISSIBLE runs listed, never dropped silently |
| P3 | **Causal overclaim from lineage/association** (the F7 second clause; stage14's explicit trap) | Only M3's pre-registered H2 supports causal language; every exploratory output carries `causal_claim_allowed: false`; claims lint (M0.P6) can grep for the forbidden sentence outside an H2-pass context |
| P4 | **Float leakage into analysis artifacts** breaks byte-reproducibility and the codec-subset hygiene | Integer-pair + decimal-string representation (§2.2); script self-test asserts no `.` in any JSON number token of its output |
| P5 | **Ratio instability at n=50** — averaging per-task VPPUT ratios produces garbage | Portfolio aggregates (ratio of sums) as the reported quantity; per-task rationals published for audit only; cluster-by-task bootstrap CIs reusing RES_M3 §5.6 |
| P6 | **Held-out contamination** — pilot tasks or S00 old-policy tasks counted as held-out | Registry is generated FROM the M3 pre-registration's S01 manifest digest; script refuses any receipt whose `instance_id` is outside the registry; S00/S02-pilot IDs structurally absent |
| P7 | **Denominator gaming** — wall-time or cost trimmed (e.g. excluding failed attempts) to inflate H-VPPUT | The ADR's C_i definition (ALL attempts, failed branches included) is asserted by reconciling script totals against the auditor's cost-conservation totals (`audit_micro_tape_decision_dag.py:738–776`); any receipt on tape not consumed by the script is a FAIL |
| P8 | **Two metric definitions drift apart** — M4's H-VPPUT vs RES_M3's exploratory `solves per $` | Single implementation: the M4 script imports/reproduces RES_M3 §5.6's aggregation and both reports cite the same script hash |
| P9 | **Legacy-tape laundering** — pre-M1c word-count tapes averaged into H-VPPUT | Permanent INADMISSIBLE class (§2.3); legacy numbers only in a labeled non-H-VPPUT appendix |
| P10 | **Implementer self-closure** of the north-star report | Status ceiling ADDRESSED; M4.P3/M4.G certified by an M5-class verifier (tracker rows); FCE-B1 check 8 independently recomputes |
| P11 | **Silent usage loss on streamed calls** — OpenAI-compat streams omit `usage` unless `stream_options.include_usage` is set, quietly demoting runs to BOUNDED (or worse, tempting a backfill) | Forbid streaming in measured arms (pre-registration rule, §2.7 rule 5); adapter downgrades at write time, metric script re-verifies field completeness per `usage_schema` and hard-fails on a mislabeled `provider_receipt_inline` |
| P12 | **Rule pile-up without retirement** — the active broadcast-rule set grows monotonically (no retirement mechanism exists, §2.8 stage 6), inflating every capsule's prompt cost, polluting context (the Art. II.1 failure), and confounding arm-B cost accounting over time | `BroadcastRuleRetired` event proposed to M1 (ADR-M4-006); pre-registered injection budget (max rules / max rule-tokens per capsule); injection cost tracked per capsule from receipts so growth is visible, not silent |
| P13 | **Reconciliation laundering** — treating a coarse Layer-2 usage bucket "match" as per-call verification and upgrading events to `provider_usage_api_reconciled` without per-call evidence | §2.7 rule 4: upgrade requires the bucket reference + pre-stated tolerance; buckets are aggregates, so mismatch keeps the Layer-1 class and logs the discrepancy; reconciliation can never rescue an INADMISSIBLE run |
| P14 | **Denylist bypass by paraphrase** — the Stage10 marker sweep is lowercase-substring matching (`audit_failure_taxonomy.py:85–87`); an LLM-authored `abstract_pattern`/`guidance` could paraphrase a hidden predicate or log content past every marker | Treat the denylist as necessary-not-sufficient: rule text is generated supervisor-side from templated abstractions (never verbatim model prose), length-capped, and the attestation booleans (`raw_log_text_absent`, `hidden_predicates_absent`) are asserted by the generator, then independently swept; FCE-B2 re-tests at certification |

---

## 5. How to use this in an agentic loop (concrete)

### 5.1 Evidence-area layout (plan directory until repo writes are authorized; then `turing/evidence/bench/` sibling of the M3 root)

```
selfimprove_northstar_<date>/
  heldout_task_registry.v1.json      # §2.4; digest-pinned; supervisor-side ONLY
  metric/compute_hvpput.py           # frozen stdlib-only script (5.2); sha256 recorded
  metric/selftest_fixture/           # FIXTURE-labeled worked example + expected output
  inputs/INPUT_DIGESTS.json          # sha256 of every consumed M3 artifact (5.4)
  hvpput_report.v1.json              # per-arm portfolio + per-task rationals (§2.2/2.3)
  causal/h2_consumption_note.json    # verbatim H2 numbers copied from UPLIFT_REPORT + digest
  causal/exploratory/*.json          # each with causal_claim_allowed:false (§2.5 C)
  NORTHSTAR_REPORT.md                # §2.6 skeleton
  CLAIM_BOUNDARY.json
```

### 5.2 Frozen metric script (core; stdlib-only; freeze BEFORE M3 outputs are read)

```python
# compute_hvpput.py — inputs: (a) heldout_task_registry.v1.json, (b) receipt JSONs
# (CostEvent.v2 / worker_call_receipt.v1 per RES_M1 §5.5 / RES_M3 §5.3), (c) per-(worker,arm)
# harness evaluation_results.json. NO other inputs. Output JSON: integers and strings only.
import json, sys
ENUM_OK = {"provider_receipt_inline", "provider_usage_api_reconciled"}
ENUM_BOUND = {"bounded_estimate"}

def classify_run(receipts):                       # §2.3 two-class discipline
    kinds = {r["cost_source_kind"] for r in receipts}
    if not kinds or (kinds - ENUM_OK - ENUM_BOUND): return "INADMISSIBLE"
    return "BOUNDED" if (kinds & ENUM_BOUND) else "BILLING_COMPLETE"

def portfolio(cells, resolved, registry_ids):
    tot = {"solves": 0, "cost_microusd": 0, "wall_ms": 0, "n_tasks": 0}
    for (task, receipts) in cells:
        assert task in registry_ids               # P6: held-out only, hard stop
        tot["n_tasks"] += 1
        tot["solves"] += 1 if task in resolved else 0
        tot["cost_microusd"] += sum(r["computed_cost_microusd"] for r in receipts)
        tot["wall_ms"] += sum(r["wall_clock_ms"] for r in receipts)
    return tot

def hvpput_pair(tot):                             # §2.2: exact integer pair, no floats
    return {"numerator_solves": tot["solves"],
            "denominator_microusd_ms": tot["cost_microusd"] * tot["wall_ms"],
            "solves_per_dollar_e6_str": str((tot["solves"] * 10**12) // max(1, tot["cost_microusd"]))}
# Self-test: run on metric/selftest_fixture (FIXTURE label), assert byte-identical expected
# output and assert no '.' occurs inside any JSON number token of the emitted report.
```

### 5.3 Held-out registry generation + invisibility check

```bash
# Generate from the M3 pre-registration's shard copy (never from a live dataset fetch):
python3 metric/gen_registry.py \
  --shard-manifest <m3_root>/shard/shard_manifest.json --shard S01 \
  --out heldout_task_registry.v1.json            # embeds shard_manifest sha256
# Worker-invisibility sweep (must all be clean):
python /home/zephryj/turingos_backup/work/turing/tools/bench/audit_prompt_leakage.py --help  # confirm flags
#   run it over every worker-visible artifact of the consumed runs; then:
grep -ril "heldout_task_registry\|hvpput" <m3_root>/worker_safe_tasks/ && echo LEAK-FAIL || echo clean
```

### 5.4 Input-digest table (build before reading content; recheck after)

```bash
( cd <m3_root> && sha256sum UPLIFT_REPORT.json analysis/analyze_uplift.py \
    scoring/*/evaluation_results.json receipts/*.json ) > inputs/INPUT_DIGESTS.json.txt
# The M4 report is invalid unless every digest here equals M3's published table (frozen outputs only).
```

### 5.5 Causal consumption + exploratory stamps

```bash
# Confirmatory: copy H2 verbatim (Δ_BC, CI, p, MDE) from UPLIFT_REPORT.json + its sha256 into
# causal/h2_consumption_note.json. Never recompute confirmatory numbers with new code.
# Exploratory dose-response (tape-only inputs), stamped:
python3 causal/exploratory/dose_response.py --receipts <m3_root>/receipts/ \
  --tape-events <m3_root>/arms/B/ --out causal/exploratory/dose_response.json
python3 - <<'EOF'
import json;d=json.load(open("causal/exploratory/dose_response.json"))
assert d["causal_claim_allowed"] is False and d["label"] == "EXPLORATORY"
EOF
```

### 5.6 Orchestration order (atoms for the loop)

1. Freeze `compute_hvpput.py` + fixture self-test + report skeleton + registry generator; record sha256s (M4.P1; needs only M1c's schema text, runnable on FIXTURE data before M3 finishes).
2. When M3's outputs freeze: build `INPUT_DIGESTS`, generate the registry, run the invisibility sweep (M4.P1/P2 boundary).
3. Run the metric script over receipts + harness results → `hvpput_report.v1.json`; reconcile totals against the strict auditor's conservation numbers (P7).
4. Write `causal/h2_consumption_note.json`; run exploratory analyses with stamps (M4.P2).
5. Assemble `NORTHSTAR_REPORT.md` from the frozen skeleton + `CLAIM_BOUNDARY.json` (M4.P3); status ADDRESSED; hand to M5-class verifier.

### 5.7 Worked H-VPPUT example (FIXTURE — synthetic numbers, the shape of `metric/selftest_fixture/`)

Held-out registry: `{t1, t2, t3}`. Arm B, one worker, DeepSeek-shaped price table `{input: 140000, output: 280000}` µUSD/Mtok (the RES_M3 §5.3 example values). Receipts on tape:

| Task | Receipt | `cost_source_kind` | Tokens (in/out) | `computed_cost_microusd` (rule 3, §2.7) | `wall_clock_ms` | Outcome |
|---|---|---|---|---|---|---|
| t1 | attempt 1 (failed) | `provider_receipt_inline` | 20,000 / 2,000 | ceil(20000·140000/10⁶) + ceil(2000·280000/10⁶) = 2800 + 560 = **3360** | 45,000 | attempt failed |
| t1 | attempt 2 (accepted) | `provider_receipt_inline` | 24,000 / 3,000 | 3360 + 840 = **4200** | 60,000 | resolved (harness) |
| t2 | attempt 1 | `bounded_estimate` (`bound_kind: upper_bound_bytes_over_2`) | — | **9000** (upper bound) | 50,000 | unresolved |
| t3 | attempt 1 | `estimated_tokens` (legacy non-enum) | — | — | — | (irrelevant) |

Classification (§2.3): t1 → BILLING_COMPLETE (both events in the receipt enum); t2 → BOUNDED; t3 → INADMISSIBLE (non-enum kind), listed in the exclusion table with its event ref. Per the ADR's C_i rule, t1's FAILED attempt counts: `cost_t1 = 3360 + 4200 = 7560` µUSD, `time_t1 = 45000 + 60000 = 105000` ms, `progress_t1 = 1`.

Expected output (excerpt of `hvpput_report.v1.json` — integers and strings only, no float tokens):

```json
{"class_breakdown": {"n_billing_complete": 1, "n_bounded": 1, "n_excluded": 1},
 "exclusions": [{"task": "t3", "reason": "cost_source_kind=estimated_tokens (non-enum)"}],
 "billing_complete_portfolio": {
   "total_solves": 1, "total_cost_microusd": 7560, "total_wall_ms": 105000,
   "hvpput_pair": {"numerator_solves": 1, "denominator_microusd_ms": 793800000},
   "hvpput_m_str": "0.001259763",
   "solves_per_dollar_e6_str": "132275132"},
 "bounded_portfolio": {
   "total_solves": 0, "total_cost_microusd_upper_bound": 9000, "total_wall_ms": 50000,
   "hvpput_pair": {"numerator_solves": 0, "denominator_microusd_ms": 450000000},
   "hvpput_bound_kind": "lower_bound_via_cost_upper_bound"}}
```

Checkable by hand: denominator 7560 × 105000 = 793,800,000; `hvpput_m_str` = 10⁶/793,800,000 rendered as a decimal string ("0.001259763…", fixed precision set by the frozen script); `solves_per_dollar_e6_str` = ⌊1 × 10¹² / 7560⌋ = 132,275,132 (≈ 132.3 solves per dollar — FIXTURE-scale numbers, meaningless as capability). The zero-progress BOUNDED stratum shows the enforced shape: progress 0 ⇒ VPPUT exactly 0 (§2.1 auditor rule). The self-test asserts this exact JSON byte-identically and asserts no `.` inside any JSON number token.

### 5.8 Broadcast-rule lifecycle audits (reuse verbatim; exploratory lifecycle table)

```bash
cd /home/zephryj/turingos_backup/work/turing
# Stage10 denylist + preserve-only + taxonomy coverage (exit 1 on FAIL; CLI verified at
# tools/bench/audit_failure_taxonomy.py:206-213):
python tools/bench/audit_failure_taxonomy.py \
  --coverage <run_root>/turingos/substrate_coverage.json \
  --out <m4_out>/failure_taxonomy_audit.json
# Activation + later-capsule consumption lineage (the stage11/stage14 auditor; includes
# pput/vpput/heldout FORBIDDEN_VISIBLE_MARKERS):
python tools/bench/audit_failure_memory_activation.py --help   # confirm flags, then run over consumed runs
```

Exploratory lifecycle table (one row per activated rule; `causal/exploratory/rule_lifecycle_table.json`, stamped per §2.5 C):

```json
{"label": "EXPLORATORY", "causal_claim_allowed": false,
 "rules": [{"rule_id": "...", "activated_rule_event_id": "mu:...",
   "failure_class": "CONTEXT_MISSING", "source_failure_count": 3,
   "consuming_capsule_ids": ["wc_..."], "injection_cost_microusd_total": 0,
   "outcomes_after_consumption": {"resolved": 0, "unresolved": 0},
   "retirement_event_id": null}]}
```

`injection_cost_microusd_total` prices the rule's injected text via the receipts of the capsules that consumed it — the input FCE-C1's budget-knob design needs, and the operational signal for `injection_budget_pressure` retirement (§2.8).

---

## 6. ADR-ready decision records (MADR-style, one paragraph each)

**ADR-M4-001 — H-VPPUT operational definition: money-denominated, receipts-only, computed off-tape as exact integer pairs.** Context: the accepted north-star ADR defines `VPPUT_i = 1[GroundTruth]/(C_i·T_i)` with all-cost C_i, but the audit (F7) found cost is word-count-estimated with `cost_source_kind: unspecified`, making the metric a fiction; the codec rejects floats on tape. Decision: H-VPPUT's cost denominator is Σ `computed_cost_microusd` over ALL of a task's CostEvent.v2 receipts (failed attempts included) and `T_i` is Σ `wall_clock_ms`; the metric is computed by a frozen stdlib-only script over tape receipts + upstream-harness results + the held-out registry ONLY, and lives in derived-view analysis JSON as exact integer numerator/denominator pairs plus decimal strings — never on tape, never as JSON floats; portfolio (ratio-of-sums) aggregates with cluster-by-task bootstrap CIs are the reported quantities. Consequences: F7's measurability clause closes mechanically; FCE-B1 check 8 can recompute to byte equality; per-task ratios remain audit-table-only; the metric inherits M1c as a hard dependency.

**ADR-M4-002 — Two cost classes, structurally separated: BILLING_COMPLETE point estimates, BOUNDED intervals, INADMISSIBLE exclusions.** Context: Intent G5 permits "billing-complete (or explicitly bounded)" cost; the live hazard is incomplete cost laundered into a headline number (legacy `estimated_tokens`/`unspecified` values exist on disk). Decision: run class is computed mechanically from the closed `cost_source_kind` enum (100% receipt/reconciled → BILLING_COMPLETE point estimate; any well-formed `bounded_estimate` → BOUNDED, published only as a lower-bound H-VPPUT via upper-bound cost; anything else → INADMISSIBLE, excluded with per-run listing); the class breakdown is a mandatory headline field; pre-M1c tapes are permanently INADMISSIBLE. Consequences: mixed-class point estimates are unrepresentable in the report schema; exclusions are visible and countable; historical numbers survive only in a labeled legacy appendix.

**ADR-M4-003 — Failure-memory causality: consume M3's pre-registered H2 verbatim; everything else is stamped EXPLORATORY.** Context: the audit found zero causal evidence for failure-memory efficacy (lineage only), and the repo's own stage14 artifact records `causal_claim_allowed: false`; M3 pre-registers exactly one causal contrast (H2: arm B vs arm C, ablation-honesty-audited). Decision: M4's confirmatory causal content is a digest-pinned verbatim copy of M3's H2 result; M4 performs no new confirmatory statistics; mechanism analyses (dose-response over `consumed_broadcast_rule_ids`, memory-cost accounting, lineage tables) are permitted only with `causal_claim_allowed: false` and an EXPLORATORY label; the sentence "failure memory causally improves solve probability" is permitted iff H2 passed with positive direction. Consequences: zero analyst degrees of freedom at the causal layer; a null H2 yields an honest null report that still PASSes; exploratory texture feeds FCE-C1's budget-knob design without contaminating confirmatory claims.

**ADR-M4-004 — Held-out registry: S01-as-frozen, supervisor-side, mechanically worker-invisible.** Context: "held-out" was aspirational — `heldout_ids` exists in the loop contract and shields exist (`WorkerPromptShield`), but no registry artifact defines the measurement set, and Art. III.4 forbids worker visibility of held-out identifiers. Decision: `heldout_task_registry.v1.json` (S01 instance IDs + shard-manifest digest) is the sole task-selection input to H-VPPUT; it lives outside every worker-visible tree; the metric script hard-fails on any out-of-registry receipt; the leakage sweep gains `hvpput` and the registry filename as markers and is re-run over all consumed runs' worker-visible artifacts. Consequences: FCE-B1 check 8's registry assertions become satisfiable; pilot/S00 contamination is structurally excluded; the registry is reusable by future shards via re-generation, never by editing.

**ADR-M4-005 — Honest-null reporting is frozen before results exist.** Context: the strongest drift temptation in M4 is a metric or phrasing chosen after seeing results (the audit's meta-lesson); FCE-B1 check 6 mechanically FAILs a null phrased as "no effect". Decision: the north-star report skeleton — headline class breakdown, per-arm portfolio H-VPPUT, Δ_BC + CI + MDE verbatim, the three mandatory sentence templates (positive/null/negative), claim-boundary JSON, always-present exclusion and deviation tables — is frozen (sha256) together with the metric script BEFORE any M3 output is read, and the assembled report must diff-conform to the skeleton. Consequences: direction cannot change the report's shape; "no measurable self-improvement" is a first-class, publishable outcome; reviewers and the M5-class verifier check conformance mechanically.

**ADR-M4-006 — Broadcast-rule lifecycle: cluster-gated activation under the Stage10 denylist, and event-based retirement proposed to the tape owner.** Context: five lifecycle stages exist on tape (FailureNode mining under the closed 10-class taxonomy → preserve-only FailureCertificate candidates → cluster-gated BroadcastRuleActivated → capsule consumption via `injected/consumed_broadcast_rule_ids` — all verified in stage8/10/11/14 evidence and `run_mini_swe_bench_substrate_smoke.py`), enforced by the Stage10 denylist + attestation sweep (`audit_failure_taxonomy.py` FORBIDDEN_BROADCAST_MARKERS); Art. II.1 mandates abstract-rules-only broadcast and forbids mass-broadcasting raw logs; NO retirement mechanism exists (verified grep, 2026-07-02), so the active set can only grow — an Art. II.1 context-pollution and cost-inflation hazard. Decision: M4 adopts the Stage10 pattern verbatim for every rule surface it audits (denylist markers + `raw_log_text_absent`/`hidden_predicates_absent` attestations + recursive string sweep, extended with `hvpput` and the registry filename); activation remains cluster-gated (≥3 same-class source failures, the stage14 precedent); M4 PROPOSES a supervisor-side append-only `BroadcastRuleRetired` event (`rule_id`, reason enum `{superseded_by_rule, dose_response_null, scope_expired, injection_budget_pressure}`, `evidence_ref`) plus an active-set filter in `read_broadcast_rules` and a pre-registered per-capsule injection budget — with M1 as the landing schema owner, and retirement decisions permitted to cite only EXPLORATORY (`causal_claim_allowed: false`) artifacts, since pruning is operations, not causal inference. Consequences: the lifecycle becomes fully replayable end to end including exit; per-stage claim ceilings keep lineage-proven protocol language separate from H2-gated efficacy language; capsule prompt cost stays bounded and receipt-visible; M4 stays a pure consumer (no M4-owned tape events).

**ADR-M4-007 — Provider receipt binding: Layer-1 inline usage is the load-bearing BILLING_COMPLETE source; Layer-2 APIs are citation-bearing upgrades only; ceiling-rounded integer costing.** Context: all four candidate providers return per-call inline `usage` (OpenAI/xAI OpenAI-compatible incl. cached/reasoning detail fields; Anthropic input/output/cache fields; DeepSeek cache-hit/miss split with ~50x price divergence), while org-level usage/cost APIs are admin-key- and plan-gated (Anthropic Team/Enterprise only; xAI needs a separate management key; DeepSeek has none found) — verified WEB 2026-07-02 here and in RES_M1 §2.6. Decision: `provider_receipt_inline` requires the complete per-provider field set (verbatim `usage`, `model_reported`, `provider_request_id`, request/response digests, `price_table_digest`) — anything less is downgraded to `bounded_estimate` at write time and hard-failed by the metric script if mislabeled; `provider_usage_api_reconciled` may be assigned only by a post-hoc pass citing the Layer-2 bucket reference within a pre-stated tolerance, never rescuing INADMISSIBLE runs; costing is deterministic ceiling arithmetic per (provider, model, token_class) against the pinned integer price table; streaming is forbidden in measured arms (usage omission hazard). Consequences: BILLING_COMPLETE is reachable from response bodies alone (no plan-gated dependency on G5's critical path); recomputation is byte-identical; DeepSeek cache economics are priced correctly; the enum's semantics are now mechanical rather than descriptive. Subordinate to ADR-M1-004 — this record binds M4's read-side verification, not the tape schema.
