# RES-M3 — Research Report: Worker Uplift Laboratory (the central AGI-relevant experiment)

- Module: M3 — Worker Uplift Laboratory
- Date: 2026-07-02
- Author: Research agent (Fable-5-class), M3 research track
- Status: RESEARCH INPUT to the M3 module plan. This document confers no CLOSED/RATIFIED status on anything. All on-disk claims below were verified against the workspace on 2026-07-02 at repo `./turing` (branch `goal/mini-swe-bench-grok-worker`); every such claim carries an absolute path. Claims sourced from the public web are marked WEB and dated; claims that are reasoned analysis (not measured) are marked ANALYSIS.
- Serves: KPI G4 (uplift measurement), feeds G5 (failure-memory causality / H-VPPUT). Directly answers audit findings F5 and R2/R7 in `/home/zephryj/turingos_backup/work/TURINGOS_RETROSPECTIVE_AUDIT_FINDINGS_20260702.md`.
- Binding anchor: `/home/zephryj/turingos_backup/work/PROJECT_PLAN_TURINGOS_AGI_SUBSTRATE_20260702/01_PROJECT_INTENT.md` (G4: "The KPI is a *valid measurement*, not a positive result").

---

## 1. Questions this research answers

1. What experimental design lets us measure, with defensible statistics, whether the TuringOS loop makes a weak worker better on a fixed SWE-bench Verified shard — including the failure-memory ablation and a deterministic floor?
2. What statistical test and CI machinery are appropriate for paired binary outcomes on n ≤ 50 tasks, what minimum detectable effect (MDE) does n = 50 actually buy, and how should 2–3 workers and 3 pairwise contrasts be handled (pooling, clustering, multiple comparisons)?
3. How should the experiment be pre-registered so that a negative result is still a PASS and no post-hoc metric shopping is possible?
4. Which frozen shard should be used (and why NOT the Django-only Stage16 20-task shard and NOT S00), and how is it frozen?
5. What is operationally known about the upstream `swebench==4.1.0` Docker harness in this environment — exact working invocation, flags, image-cache disk/time costs, per-instance flakiness, and the pre-registered rerun policy?
6. Which cheap, API-stable models circa July 2026 are appropriately *weak* workers, at what price, and how is "appropriately weak" defined and calibrated?
7. How is worker identity made machine-verifiable — what exactly goes on tape per LLM call (model ID, version, provider usage receipts) — fixing audit finding F5?
8. What contamination/leakage controls are needed (gold-patch guard, worker-safe packets, supervisor-taint protocol, dataset-contamination caveats)?
9. What are the S00 resume protocol conditions once the worker policy is fixed?
10. What existing repo tooling can be reused versus what must be built?

---

## 2. Candidate methodologies, patterns, and stacks

### 2.1 Statistical design for the primary question (paired binary outcomes, n ≤ 50)

The outcome per (task, arm) is binary: `resolved` per the upstream harness `report.json`. All arms run on the **same** frozen task set, so the design is paired (matched on task). Candidates:

| Candidate | What it is | Pros | Cons |
|---|---|---|---|
| **Exact McNemar test** (conditional binomial on discordant pairs) | Test of marginal homogeneity for paired binary data; primary p-value for arm B vs arm A | Exact (no asymptotic approximation — critical at n=50 where discordant counts may be < 25); uses pairing, which absorbs between-task difficulty variance; standard, referee-proof | Tests only the sign of the difference; needs a companion CI; conditions on discordant pairs so concordant tasks contribute no information |
| Asymptotic McNemar with continuity correction | χ² version | Familiar | Unreliable when discordant count < ~25, which is likely here; strictly dominated by the exact version — REJECT |
| Two-proportion z / Fisher on pooled solve rates | Unpaired comparison of arm solve rates | Simple | Throws away the pairing; wildly underpowered at n=50; wrong model (same tasks in both arms are not independent samples) — REJECT as primary |
| **Paired (task-level) bootstrap CI on Δ = p(B) − p(A)** | Resample tasks with replacement, recompute Δ per replicate, percentile/BCa interval, ≥10,000 replicates | Gives the effect-size CI the intent document demands ("uplift delta reported with confidence intervals"); naturally extends to cost-normalized metrics (solves per dollar) and to clustering (see below); assumption-free | Bootstrap on n=50 binary pairs is slightly granular; report alongside the exact test, not instead of it |
| Bayesian beta-binomial / logistic mixed model | Posterior over Δ; GLMM with task random effect for >2 arms | Graceful with small n; mixed model handles worker×task crossing | Prior choice is attack surface for an adversarial audit; heavier stack (PyMC/statsmodels). Keep as pre-registered *secondary* analysis at most |
| Permutation test on paired differences | Shuffle arm labels within task | Exact, assumption-free | For binary pairs it reduces to McNemar's sign-randomization; adds nothing — subsumed |

**Power / MDE — computed, not guessed** (ANALYSIS; script at §5.6, run 2026-07-02, exact unconditional power of the two-sided α=0.05 exact McNemar test, n=50 paired tasks; `p10` = P(worker-alone solves, TuringOS-arm fails) = "harm rate", `p01` = P(worker-alone fails, TuringOS-arm solves); Δ = p01 − p10):

| p10 (harm) | Δ needed for ≈80% power (MDE) | Example powers |
|---|---|---|
| 0.00 | **≈ 0.155** (i.e. +8/50 tasks) | Δ=0.10 → 38%; Δ=0.20 → 95% |
| 0.02 | **≈ 0.19** | Δ=0.10 → 32%; Δ=0.20 → 84% |
| 0.05 | **≈ 0.23** | Δ=0.20 → 70% |
| 0.10 | **≈ 0.29** | Δ=0.20 → 55% |

With **2 workers × 50 tasks pooled (n=100 worker-task pairs, ignoring task clustering)**: MDE ≈ 0.08 (p10=0), ≈ 0.11 (p10=0.02), ≈ 0.145 (p10=0.05). With 3 workers, n=150, MDE drops further (≈ 0.06–0.12). Clustering by task inflates these slightly; the cluster bootstrap (resample *tasks*, keep all workers' outcomes for a resampled task together) gives honest CIs. Illustrative CI width: for pA=0.30, pB=0.50 at n=50 the naive paired 95% CI half-width is ±0.14.

**Consequence (load-bearing):** a single weak worker on 50 tasks can only *confirm* an uplift of roughly ≥15–20 percentage points. That is a realistic scaffold effect size (WEB, 2026-07: scaffolds routinely move weak models by tens of points on SWE-bench — e.g. Qwen3-Coder-Next is reported ~71% *with* the OpenHands scaffold, per [OpenRouter/kilo.ai model pages](https://openrouter.ai/qwen/qwen3-coder-next/pricing), far above bare-model one-shot patching), but a 5–10 pp uplift will read as "CI includes 0". The design must therefore (a) pool across 2–3 workers with cluster-by-task bootstrap as the pre-registered *pooled primary*, (b) report per-worker estimates as forest-plot-style secondaries, and (c) pre-register the MDE so that "not significant" is reported as "Δ = x [CI], study powered for MDE = y", never as "no effect". A negative or null result under this framing is a valid PASS for M3.

**Handling >2 arms:** do NOT run an omnibus test (Cochran's Q) as the gate; pre-register exactly two confirmatory pairwise contrasts (§2.3) and control family-wise error over those two with Holm–Bonferroni (test the larger contrast at α/2 = 0.025 first; if significant, test the second at α = 0.05). The deterministic-floor arm is a *manipulation check*, not a hypothesis (expected solve count 0; any solve indicates leakage or harness error and triggers a stop).

**Attempts/replications per cell:** exactly **one scored attempt-budgeted run per (worker, task, arm)** — the run itself may contain up to the budgeted attempts inside the loop (matching `budget_profile.max_attempts_per_instance: 5` in `/home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_phase_g_verified_500_manifest_20260628/loop_manifest.json`), but exactly one final prediction per cell is submitted to the harness. Replicated sampling (pass@k) multiplies cost ~k× and answers a different question; REJECT for this increment, note as future work.

### 2.2 Arm design (what each arm is, concretely)

| Arm | Name | Definition | Existing tooling to reuse (verified on disk) |
|---|---|---|---|
| A | Weak worker alone | Worker gets the worker-safe capsule + a plain "produce a unified diff" instruction, fixed small attempt budget, NO TuringOS loop, no failure memory, no market/routing | `/home/zephryj/turingos_backup/work/turing/tools/bench/run_direct_grok_baseline_smoke.py` — docstring: "This intentionally bypasses TuringOS. It exists only as the paired baseline arm for small-scale smoke and benchmark ramps." Needs generalizing from grok CLI to API workers |
| B | Weak worker + full TuringOS loop | Full loop: MicroTape events, candidate audit, retry authorization, failure-memory broadcast rules injected into worker-visible capsule | `/home/zephryj/turingos_backup/work/turing/tools/bench/run_mini_swe_bench_substrate_smoke.py` — has `worker_mode`, `broadcast_rules` injection (`read_broadcast_rules`, `visible_grok_prompt(..., broadcast_rules=...)` at lines 132/343/1329), module map incl. `M11_failure_memory` (line 41) |
| C | Weak worker + TuringOS, failure memory DISABLED (ablation) | Identical to B except broadcast-rule injection is off: no `consumed_broadcast_rule_ids` / `injected_broadcast_rule_ids` in the capsule payload; everything else byte-identical | Same runner; ablation = run with `broadcast_rules=None` (the injection path is already conditional: `broadcast_section = "" if not broadcast_rules`). A machine-checkable "ablation honesty" audit must assert the two arms' capsules differ ONLY in the broadcast section |
| D | Deterministic fake worker (floor) | A scripted worker that emits a syntactically valid but semantically null patch (or empty patch) deterministically; runs through the full B pipeline | Same runner, `worker_mode == "fake"` already exists: `worker_id = "worker:sha256:" + "f"*64 if worker_mode == "fake"` (line 744) |

Important design subtlety for arm B/C (ANALYSIS): failure memory only helps if there is memory to consume. Pre-register the memory protocol: within arm B, tasks are processed in a fixed, pre-registered order; broadcast rules generated from failures on earlier tasks are available to later tasks (cross-task memory, matching the Stage14 lineage design in `/home/zephryj/turingos_backup/work/turing/evidence/bench/mini_swe_bench_stage14_corpus_failure_memory_20260628/cross_task_memory_lineage.md`), plus within-task retry memory. Arm C gets the identical task order with injection disabled. The task order must be frozen in the pre-registration to prevent order-shopping.

### 2.3 Hypotheses and contrasts (pre-registration content)

- **H1 (primary, confirmatory): uplift.** Pooled across workers, p(resolved | B) > p(resolved | A). Test: exact McNemar on worker-task pairs, pooled; effect size Δ_BA with 95% cluster-by-task BCa bootstrap CI; Holm step 1.
- **H2 (secondary, confirmatory): failure-memory contribution.** p(resolved | B) > p(resolved | C). Same machinery; Holm step 2. This is the G5 causal evidence the audit says is missing ("failure-memory efficacy is lineage-proven only", F7).
- **M1 (manipulation check): floor.** Arm D resolves 0 tasks. Any D solve = STOP + investigate (leakage or harness misconfiguration).
- **Exploratory (labeled as such, no error control claimed):** per-worker Δs; cost-normalized uplift (resolved per $ and per 1M tokens, from receipts); Δ on ≤15-min-difficulty subset vs harder subset (the `difficulty` field is present in worker-safe packets, e.g. `"difficulty": "<15 min fix"` in `/home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_verified_500_campaign_20260629/shards/S00/ipqc/S00-W00/worker_safe_tasks/django__django-10097/task_packet.json`); wall-clock per attempt.
- **Directionality:** tests two-sided (a *negative* uplift — the scaffold hurting the worker — is a finding, not a failure).

### 2.4 Pre-registration practice adapted to agent experiments

Standard practice (OSF-style pre-registration, clinical-trial SAPs) adapted to this constitution-bound, tape-canonical setting (ANALYSIS grounded in the repo's existing evidence-packet idiom):

1. **The pre-registration is a frozen file set, sha256-pinned, committed to the tape/evidence root BEFORE any arm-B/C/D worker call and before any arm-A call on shard tasks.** Contents: hypotheses & contrasts (§2.3), arms (§2.2), frozen shard manifest digest, worker roster with pinned model IDs, budgets, harness identity & rerun policy, analysis code itself (the exact script that will compute the results), MDE statement, stop conditions, and a deviations-log protocol. This mirrors the existing sealed-manifest idiom: `task_manifest.sha256` = `sha256:37f6e092ca1d5cac8b9790ea81777fa0f39191a90794ad6f1a981b019358bee6` in `/home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_verified_500_campaign_20260629/`.
2. **Analysis code frozen with the pre-registration and dry-run on synthetic data.** Generate fake outcome tables (null and effect scenarios), run the frozen analysis end-to-end, include the dry-run outputs labeled FIXTURE in the pre-registration packet. This proves the pipeline works before real data exists and eliminates "we had to change the script" excuses later.
3. **Blinding surrogate:** the scorer is the deterministic upstream harness, so assessor blinding is moot; the analyst-degrees-of-freedom risk is metric shopping, killed by (1)+(2). The one human-judgment surface left is the rerun decision — pre-register it (§2.6).
4. **Deviations log:** any deviation (a worker API dies mid-run, a task's image fails to build) is recorded as a tape event + a `DEVIATIONS.md` entry with a pre-registered handling rule (§4, P6). Tasks are never silently dropped.
5. **Who freezes it:** implementer proposes; the pre-registration digest is echoed by an independent verifier context (cross-family, per the constitution's implementer-never-self-closes rule) before run start. The M3 module plan should make "pre-registration ACK by independent verifier" a gate.

### 2.5 Frozen shard selection

| Option | Evidence | Verdict |
|---|---|---|
| Stage16 "full sealed" 20 tasks | 20 Django-only tasks (`/home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_stage16_full_sealed_20260628/`); audit F4 flags the naming; single-repo → no repo generalization | REJECT (charter explicitly excludes it) |
| S00 (50 tasks) | Diverse (12 repos: astropy 5, django 5, matplotlib 5, psf 5, pydata 5, pylint-dev 5, pytest-dev 5, scikit-learn 4, sphinx-doc 4, sympy 4, mwaskom 2, pallets 1 — computed from `/home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_verified_500_campaign_20260629/shards/S00/shard_manifest.json`) but has 48 old-policy frontier-worker predictions, worker packets already materialized, and the astropy-12907 supervisor taint (`/home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_verified_500_campaign_20260629/shards/S00/ipqc/S00-W00/SUPERVISOR_TAINT_NOTE.md`) | REJECT for the uplift experiment (reserve for the separate S00 resume protocol, §2.9). Mixing the uplift lab into S00 would entangle old-policy inventory with new-policy arms |
| **S01 (50 tasks)** | Verified diverse and untouched: 10 repos (scikit-learn 6, sphinx-doc 6, sympy 5, astropy 5, django 5, matplotlib 5, pydata 5, pylint-dev 5, pytest-dev 5, psf 3), and the S01 directory contains ONLY `shard_manifest.json` — no worker packets, no predictions, no IPQC residue (verified 2026-07-02: `/home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_verified_500_campaign_20260629/shards/S01/`) | **RECOMMEND.** Already sealed under the campaign's `task_manifest.sha256`; drawn from the full 500 manifest (dataset digest `sha256:43ed5a3d...` and HF repo sha `91aa3ed5...` pinned in `dataset_descriptor.json`, same directory); zero contact with any prior worker |
| Fresh stratified 50-task draw | Maximum cleanliness | Unnecessary: S01 is already clean, sealed, and stratified; a fresh draw adds a seed-choice degree of freedom. REJECT unless S01 is later shown tainted |

Freeze mechanics: the pre-registration pins (a) the campaign `task_manifest.sha256`, (b) the S01 `shard_manifest.json` sha256, (c) the per-task worker-safe packet sha256s once materialized (the S00 pattern: `worker_safe_tasks_report.json` lists `task_packet_sha256` + `worker_capsule_sha256` per task — reuse `/home/zephryj/turingos_backup/work/turing/tools/bench/materialize_swebench_worker_safe_tasks.py`, whose `FORBIDDEN_FIELDS` removal is already audited, `forbidden_field_count_removed: 5` per packet).

### 2.6 Upstream harness operations (SOLE scorer)

**Verified working setup on this host** (all paths verified 2026-07-02):

- Venv: `/home/zephryj/turingos_backup/work/turing/.venv_swebench` — live import check returns `swebench 4.1.0`.
- Docker: `Docker version 20.10.24+dfsg1, build 297e128` per `/home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_official_harness_qualification_20260629/official_harness_qualification.json`.
- Qualified invocation (exact command that produced the 20/20 repaired replay, same file):
  `python -m swebench.harness.run_evaluation --dataset_name princeton-nlp/SWE-bench_Verified --split test --predictions_path predictions_phase_f_20_repaired.jsonl --max_workers 2 --timeout 1800 --run_id turingos_phase_f_20_official_repaired_20260629 --report_dir phase_f_20_repaired_run`
  (Note: the campaign's shard packets use `--dataset_name SWE-bench/SWE-bench_Verified` — see `/home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_verified_500_campaign_20260629/shards/S00/shard_run_packet.json`. Both dataset names exist on HF; the pre-registration must pin ONE, matching the sealed dataset digest.)
- Full flag surface (from the recorded `--help`, `/home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_official_harness_qualification_20260629/harness/run_evaluation_help.txt`): `-d/--dataset_name`, `-s/--split`, `-i/--instance_ids` (space-separated subset), `-p/--predictions_path` (`gold` = gold patches), `--max_workers` (default 4; "should be <= 75% of CPU cores"), `--timeout` (default 1800 s/instance), `--force_rebuild`, `--cache_level {none,base,env,instance}` (default `env`), `--clean`, `-id/--run_id` (required), `-n/--namespace` (default `swebench` = pull prebuilt images from Docker Hub; `none` = build locally), `--instance_image_tag`, `--env_image_tag`, `--rewrite_reports` (regenerate reports from existing test outputs without re-running), `--report_dir`, `--modal`.
- Predictions JSONL shape (verified against `/home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_verified_500_campaign_20260629/predictions/shard_S00_predictions.jsonl`): one object per line with `instance_id`, `model_name_or_path`, `model_patch` (+ the repo's own extensions `candidate_patch_sha256`, `candidate_source`). **F5 lesson:** the old file says `"model_name_or_path": "turingos-internal-rehearsal"` — under the new worker policy this field must carry the pinned worker+arm identity, e.g. `deepseek-v4-flash__armB__uplift-v1`.
- Output shape: `evaluation_results.json` with `total_instances / submitted / completed / resolved / unresolved / empty_patch / error` counts and the corresponding id-lists (`resolved_ids`, `unresolved_ids`, `error_ids`, `incomplete_ids`), `schema_version: 2` (verified at `/home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_official_harness_qualification_20260629/phase_f_20_run/evaluation_results.json`); per-instance upstream logs (`eval.sh`, `test_output.txt`, `report.json`, `patch.diff`) preserved in `harness_logs_raw.tar.gz` per the audit's verification.
- **Costs** (WEB, 2026-07): default `--cache_level env` stores base+env images, ~100–120 GB disk; `instance` caches all ~2,290 instance images, ~2 TB ([SWE-bench Docker setup guide](https://www.swebench.com/SWE-bench/guides/docker_setup/), [harness reference](https://www.swebench.com/SWE-bench/reference/harness/)). Epoch AI's optimized public registry gets all 500 Verified images to ~30 GiB and a full 500-task eval to ~62 min on a 32-core machine ([Epoch blog](https://epoch.ai/blog/swebench-docker)); LogicStar compresses further ([LogicStar blog](https://logicstar.ai/blog/how-we-made-swe-bench-50x-smaller)). **Recommendation: do NOT switch registries** — the qualification evidence was produced with the upstream default (`swebench` namespace); scoring identity beats speed. For 4 arms × ≤3 workers × 50 tasks the runs are ≤ 10 shard-sized evals; at the observed Phase-F scale (20 tasks, `--max_workers 2`) each 50-task eval is roughly 1–3 h on this class of host (ANALYSIS from qualification timestamps; measure in the pilot).
- **Flakiness** (WEB): ~11.3% of SWE-bench *Lite* tasks have order/set-nondeterministic tests ("Large Language Monkeys", [arXiv:2407.21787](https://arxiv.org/pdf/2407.21787)); Epoch excludes 16 Verified tasks that don't run reliably in their infra ([Epoch](https://epoch.ai/blog/swebench-docker)); UTBoost found inadequate tests in 26/500 Verified tasks ([Kang, Medium](https://medium.com/@danieldkang/swe-bench-verified-is-flawed-despite-expert-review-utboost-exposes-gaps-in-test-coverage-4b75c6b940c6)); image-build errors sometimes vanish on rerun ([SWE-bench issue #293](https://github.com/swe-bench/SWE-bench/issues/293)). **Pre-registered rerun policy (recommendation):** each prediction is scored once; if an instance lands in `error_ids` or `incomplete_ids` (harness/build error, NOT a test failure), up to 2 retries of that instance alone via `--instance_ids`, each retry logged on tape with reason; if still erroring, the task is marked `HARNESS_ERROR` and excluded *pairwise across all arms* (never per-arm), with the exclusion count reported. `resolved`/`unresolved` outcomes are never re-rolled. `--rewrite_reports` may be used only for report regeneration, never to alter test outputs.

### 2.7 Weak worker selection (mid-2026 landscape)

**Definition of "appropriately weak" (recommendation):** the worker's arm-A (worker-alone) solve rate on a 10-task pilot subset of the shard should land in **15–45%**. Below ~10% there is no signal for failure memory to compress (and floor effects crush McNemar power — most pairs concordant-fail); above ~55% ceiling effects crush headroom. Calibrate in a budgeted pilot (pre-registered as pilot, excluded from confirmatory analysis or — cleaner — pilot on 10 tasks drawn from S02, keeping S01 virgin; S02 verified diverse and untouched, 8 repos, `/home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_verified_500_campaign_20260629/shards/S02/shard_manifest.json`). **Deterministic pilot-selection rule (no analyst degree of freedom):** pilot tasks = the first 10 instance IDs in S02's `shard_manifest.json` stored order (identical set for all workers); the ID list is enumerated verbatim in `PREREGISTRATION.md`, and FCE §1.2's cert-slice exclusion rule keys off that enumerated list.

Roster candidates (prices per 1M tokens; WEB, checked 2026-07-02):

| Candidate | ID to pin | Price in/out | Notes |
|---|---|---|---|
| **DeepSeek V4 Flash** | `deepseek-v4-flash` (non-thinking mode) | $0.14 / $0.28 (cache-hit input $0.0028) | **CRITICAL API-stability fact: `deepseek-chat` and `deepseek-reasoner` are retired 2026-07-24 15:59 UTC** — never write `deepseek-chat` into the policy; pin `deepseek-v4-flash` ([DeepSeek API docs/pricing](https://api-docs.deepseek.com/quick_start/pricing), [change log](https://api-docs.deepseek.com/updates), [migration note](https://wavespeed.ai/blog/posts/blog-deepseek-v4-model-name-migration/)). OpenAI-compatible AND Anthropic-compatible interfaces; no SLA, expect 429/503 under load → backoff + deviations log. In thinking mode, sampling params are ignored — use non-thinking mode for a "small/non-thinking" worker profile |
| **GPT-5 Nano / GPT-5.4-nano class** | `gpt-5-nano` (or current nano alias — verify against the [OpenAI pricing page](https://developers.openai.com/api/docs/pricing) at pre-registration time) | ~$0.05 / $0.40 (nano); GPT-5.4-nano ~$0.20 / $1.25 | Genuinely weak tier; heterogeneous provider family vs DeepSeek; reasoning variants burn hidden thinking tokens — pin a non-reasoning/nano config ([pricepertoken](https://pricepertoken.com/pricing-page/model/openai-gpt-5-nano), [aipricing.guru July 2026](https://www.aipricing.guru/openai-pricing/)) |
| **Claude Haiku 4.5** | `claude-haiku-4-5` | $1.00 / $5.00 | Verified via the local claude-api skill catalog (cached 2026-06-24): 200K context, 64K max output. Third family (Anthropic); usage receipts are first-class (`usage.input_tokens/output_tokens/cache_*`, `_request_id`) |
| Qwen3-Coder-30B-A3B (open weights, via OpenRouter) | `qwen/qwen3-coder-30b-a3b-instruct` | ~$0.07 / $0.27 | Cheapest; open-weights reproducibility story; but OpenRouter multi-provider routing weakens the "exact model identity" guarantee — if used, pin a single upstream provider in the request ([OpenRouter Qwen pages](https://openrouter.ai/qwen)) |
| Qwen3-Coder-Next | — | $0.11 / $0.80 | REJECT as "weak": reported ~71% on Verified with OpenHands scaffolding ([kilo.ai](https://kilo.ai/open-source-models), [OpenRouter](https://openrouter.ai/qwen/qwen3-coder-next/pricing)) — too strong, ceiling risk |
| Kimi K2.x (Fireworks) | — | $0.95–$4.00 | Frontier-adjacent agentic coder; too strong and too expensive for the *weak* roster ([Fireworks blog](https://fireworks.ai/blog/kimi-k2p7-code)) |

**Recommended roster: DeepSeek V4 Flash + GPT-5 nano-class + (budget permitting) Claude Haiku 4.5** — three families, all with provider-reported usage in responses, all cheap enough that the LLM cost of the whole experiment is dominated by harness compute, not tokens (ANALYSIS: 4 arms × 3 workers... arms B/C/D share workers; ≈ 3 workers × 3 LLM-arms × 50 tasks × ≤400K tokens/instance budget ceiling ≈ 180M tokens worst case; at Flash/nano prices ≪ $200, at Haiku ≤ ~$700 worst case; typical usage will be far below ceiling).

**Contamination caveat (must appear in the pre-registration):** SWE-bench Verified is public and old; OpenAI deprecated it in Feb 2026 over contamination concerns and scores are vendor-reported (WEB: [benchmarkingagents.com](https://benchmarkingagents.com/swe-bench/), [morphllm leaderboard notes](https://www.morphllm.com/best-ai-model-for-coding)). Mid-2026 weak models have likely seen the repos and possibly the patches. This biases *absolute* solve rates upward but the *differential* (same worker, same tasks, arms A vs B vs C) is largely immune — contamination is a per-(worker,task) constant absorbed by pairing (ANALYSIS). It does mean absolute rates must never be quoted as capability claims — consistent with the intent document's "benchmarks are substrate stress tests".

### 2.8 Worker identity + usage receipts on tape (fixes F5)

Audit F5 (verified): S00 predictions carry `model_name_or_path: "turingos-internal-rehearsal"`; no receipt records a model ID or API usage. The fix is a per-call receipt event appended to the MicroTape (tape-canonical, Art. 0.2) with this minimum schema (see §5.3 for full JSON):

- `worker_policy_id` (digest of the Worker Policy ADR text), `arm`, `instance_id`, `attempt`
- `provider` + `endpoint_base_url` (no path secrets), `model_requested` (the pinned ID) and `model_reported` (the `model` field the provider echoes in the response — providers may serve a dated snapshot; both must be recorded)
- `request_sha256` (canonical digest of the full request body EXCLUDING auth headers), `response_sha256`
- `provider_request_id` (Anthropic: `request-id` header / `_request_id`; OpenAI-compatible incl. DeepSeek: response `id` + `x-request-id` header where present)
- `usage` verbatim as returned: OpenAI/DeepSeek shape `{prompt_tokens, completion_tokens, total_tokens, prompt_cache_hit_tokens?, prompt_cache_miss_tokens?}`; Anthropic shape `{input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens}` (field names verified via the local claude-api skill docs)
- `cost_source_kind: "provider_receipt_inline"` (from the closed enum in RES_M1 §2.6, owned by M1c's CostEvent.v2 — see §5.3), with the published unit prices pinned in the pre-registration as an **integer micro-USD** price table (`price_table_digest`), plus integer `computed_cost_microusd` and `wall_clock_ms`. This directly upgrades the tape from the audited `cost_source_kind: unspecified / provider_reported_cost: false` state (F3/F7) and feeds G5/H-VPPUT.
- **Never on tape:** API keys, Authorization headers, org IDs. Reuse the existing discipline: `/home/zephryj/turingos_backup/work/turing/tools/bench/run_deepseek_meta_review.py` already reads the key only from env (`DEEPSEEK_API_KEY`) and never serializes it; `audit_prompt_leakage.py` FORBIDDEN_MARKERS include `sk-`, `private key`, `auth.json`.

Raw request/response bodies: store zstd-compressed under the evidence root keyed by `request_sha256` (worker-safe side only; responses may quote problem statements — fine; they must never contain gold fields since the request never contained them). The tape stores digests + usage, not bodies, keeping tape events small while making receipts independently verifiable.

### 2.9 Leakage / Goodhart controls and the S00 resume protocol

Existing controls to reuse (all verified on disk):

- **Worker-safe packet materializer:** `/home/zephryj/turingos_backup/work/turing/tools/bench/materialize_swebench_worker_safe_tasks.py` (FORBIDDEN_FIELDS removal; per-task sha256s in `worker_safe_tasks_report.json`).
- **Prompt-leakage audit:** `/home/zephryj/turingos_backup/work/turing/tools/bench/audit_prompt_leakage.py` (FORBIDDEN_MARKERS: `pput`, `vpput`, `heldout`, `gold patch`, `official solution`, `hidden predicate`, secrets markers).
- **Gold-patch guard:** `/home/zephryj/turingos_backup/work/turing/tools/bench/audit_gold_patch_guard.py` (FORBIDDEN_SOURCES on `candidate_source`) — extend with a byte-similarity check: the harness-qualification packet already demonstrated "0/20 model patches byte-identical to gold" (audit F8); add normalized-diff similarity (e.g. token-level Jaccard > 0.9 vs gold triggers manual review) run AFTER scoring so gold never enters the pipeline before predictions are frozen.
- **Candidate audit:** `/home/zephryj/turingos_backup/work/turing/tools/bench/audit_worker_candidate_patch.py` + `build_predictions_jsonl.py` for prediction assembly.
- **Supervisor-taint protocol:** the S00-W00 taint note pattern — any operator/supervisor context that sees a raw dataset row must be recorded and that context barred from producing the affected task's patch.

**S00 resume protocol (separate from the uplift lab; only after the Worker Policy ADR is accepted):** (1) label the existing 48 predictions (`shard_S00_predictions.jsonl`, sha `f067029f...`) as OLD-POLICY INVENTORY — auditable, never quoted as performance (they are machine-marked FAIL/BLOCKED already: `prediction_report_status: FAIL`, `shard_run_packet_status: BLOCKED` in `SUPERVISOR_STOP_AUDIT_20260629.json`); (2) generate the 2 missing predictions (`pydata__xarray-3677`, `pylint-dev__pylint-6386`) under the NEW policy with receipts on tape, labeled new-policy; (3) quarantine `astropy__astropy-12907` per the taint note: its patch must come from an independent worker context receiving only the worker-safe capsule; (4) S00 may then be scored as *inventory characterization* only — a mixed-policy shard can never feed the uplift analysis; never quote 48/50 or any S00 score as performance.

---

## 3. Recommendation (tied to project goals)

**Adopt: pre-registered 4-arm paired design on frozen shard S01, 2–3 weak workers (DeepSeek V4 Flash + GPT-5-nano-class, optionally Haiku 4.5), exact McNemar + cluster-by-task BCa bootstrap CIs pooled across workers with Holm over two confirmatory contrasts, upstream `swebench==4.1.0` Docker harness in the already-qualified configuration as sole scorer, per-call receipt events on tape, and a sha256-frozen pre-registration packet gated by an independent verifier ACK.**

Rationale against each project goal:

- **Long-running autonomy:** every unit of work is an idempotent atom keyed by (worker, arm, instance_id, attempt); state lives in tape + per-cell result JSONs, so a fresh orchestrator resumes from artifacts alone (drift-check item 6). Budgets reuse the frozen `loop_manifest.json` shape (`max_attempts_per_instance: 5`, `max_tokens_per_instance: 400000`, wall-clock caps) so exhaustion is a recorded terminal event (`BudgetExhausted`), not a hang.
- **Replayability:** everything that determines an outcome is pinned by digest — dataset (`sha256:43ed5a3d...` + HF sha `91aa3ed5...`), shard manifest, worker-safe packet sha256s, model IDs (requested AND provider-reported), request/response digests, harness version + run_id, analysis code. A negative result is replayable and therefore a PASS.
- **Sandboxed execution:** scoring runs entirely inside upstream Docker containers; worker patch generation in arms B/C runs under the existing loop's sandbox policy (gVisor/runsc where available per intent §5.6, else `HOST_ASSUMED` on tape). Arm A needs no repo mutation at all if the worker emits a diff from the capsule text (recommended: capsule-only arm A, no checkout — matching `run_direct_grok_baseline_smoke.py`'s shape).
- **Goodhart shielding:** workers see only audited worker-safe capsules (gold fields stripped, leakage-audited); gold patches enter the pipeline only inside the scoring containers after predictions are frozen; the deterministic floor arm detects gross leakage (any D solve = alarm); PPUT/heldout internals never appear in capsules (enforced by `audit_prompt_leakage.py` markers).
- **Observability:** structured verdict JSONs at every layer (per-cell result, per-arm predictions report, harness `evaluation_results.json`, receipts, final `UPLIFT_REPORT.json` with Δs + CIs + MDE statement + claim boundary). No prose-only status.
- **Modularity:** the three deltas over existing tooling are cleanly separable — (i) API-worker adapter with receipts (new, one module), (ii) ablation flag + ablation-honesty audit (thin), (iii) frozen analysis script (new, pure-Python stdlib, §5.6). Everything else is reuse of verified tools listed in §2.2/2.9.
- **Cost:** LLM spend bounded ≪ $1K (§2.7); harness compute is the dominant cost — ~10 fifty-task evals at 1–3 h each on the existing host with the already-cached env images (~100–120 GB disk, already provisioned by the Phase-F qualification runs); no new infrastructure.
- **Honest reporting / claim boundaries:** the KPI is the measurement. The report template pre-commits to publishing Δ with CI and the MDE even when CI includes 0, and forbids "TuringOS improves workers" language unless H1 passes AND the effect direction is positive; conversely a tight CI around 0 is reported as evidence the current loop does not help these workers at these budgets — an equally valid M3 PASS.

Explicitly rejected alternatives and why: unpaired tests (power, wrong model); Cochran's-Q omnibus gating (obscures the two contrasts that matter); pass@k replication (cost, different question); switching to Epoch's fast image registry (breaks scoring identity with the qualified evidence); reusing S00 for the lab (old-policy contamination + taint); Django-only 20 (no generalization, charter exclusion); frontier workers (measures the worker, not the substrate — the exact reason the supervisor stop happened, `SUPERVISOR_STOP_AUDIT_20260629.json` `reason` field).

---

## 4. Pitfalls & mitigations

| # | Pitfall | Mitigation |
|---|---|---|
| P1 | **Underpowered single-worker reading**: n=50 MDE is ~15–23 pp; a real 8-pp uplift will look null | Pool 2–3 workers (MDE → ~6–14 pp) with cluster-by-task bootstrap; pre-register the MDE and the "Δ with CI, powered for MDE=y" reporting template so null ≠ "no effect" |
| P2 | **`deepseek-chat` retirement 2026-07-24** breaks mid-run if the legacy alias is pinned | Pin `deepseek-v4-flash`; record `model_reported` from every response; pre-flight a canary call per worker per day of running |
| P3 | **Provider silently swaps model snapshot mid-experiment** | Record request+response model strings per call; pre-register a stop rule: if `model_reported` changes mid-arm, halt, log deviation, decide (independent verifier) whether to restart the affected cells |
| P4 | **Harness flakiness / image-build errors miscounted as failures** (11.3% flaky in Lite; build errors vanish on rerun) | Pre-registered rerun policy §2.6: retries only for `error_ids`/`incomplete_ids`, max 2, logged; pairwise exclusion across ALL arms for persistent harness errors; never re-roll `resolved`/`unresolved` |
| P5 | **Ablation arm differs from full arm in more than failure memory** (invalidates H2 causality) | Machine-checkable ablation-honesty audit: byte-diff arm-B vs arm-C capsules per task; assert the only delta is the broadcast-rules section; frozen task order shared by B and C |
| P6 | **Mid-run worker API outage** corrupts the paired structure | Idempotent per-cell atoms + deviations log; a cell that cannot complete within budget after logged retries becomes `WORKER_UNAVAILABLE` and is excluded pairwise; >10% exclusions = pre-registered abort-and-restart threshold |
| P7 | **Cross-task memory ordering leaks analysis degrees of freedom** (choosing a lucky task order for arm B) | Task order frozen in the pre-registration (manifest order of S01); same order for B and C |
| P8 | **Gold leakage via supervisor context** (repeat of astropy-12907) | Supervisor never opens raw dataset rows; packets materialized by the audited tool only; any accidental exposure → taint note + task patch quarantined to an independent context (existing protocol) |
| P9 | **Deterministic floor solves a task** (leakage or scoring bug) | Pre-registered STOP + root-cause before any confirmatory analysis; floor arm runs FIRST as a cheap canary of the whole pipeline |
| P10 | **Quoting absolute scores** (contaminated benchmark, weak workers) as capability claims | CLAIM_BOUNDARY.json in the evidence root: `full_score_claim_allowed: false`, `leaderboard_equivalence_claim_allowed: false`, `absolute_rate_is_capability_claim: false` — reuse the existing pattern (`/home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_verified_500_campaign_20260629/CLAIM_BOUNDARY.json`) |
| P11 | **Token-budget asymmetry between arms** (loop arms get more total tokens than worker-alone, confounding "scaffold" with "more compute") | Pre-register budget policy explicitly: arms share the same per-instance ceilings (`max_tokens_per_instance: 400000`, `max_attempts_per_instance: 5`, same wall-clock cap); report actual token usage per arm from receipts; run the exploratory cost-normalized analysis (solves per 1M tokens) so reviewers can see uplift-per-compute, not just uplift |
| P12 | **Implementer self-closure** of the experiment result | Status ceiling ADDRESSED; the UPLIFT_REPORT and pre-registration conformance are certified only by an independent cross-family verifier on a fresh clone (constitutional rule; intent §5.2) |
| P13 | **Disk exhaustion** during harness runs (env cache ~100–120 GB; instance images accumulate) | Keep `--cache_level env` (default), monitor `df` between shard evals; do not enable `instance` caching (~2 TB) on this host |
| P14 | **Two dataset-name aliases** (`princeton-nlp/SWE-bench_Verified` vs `SWE-bench/SWE-bench_Verified`) drift against the sealed digest | Pre-registration pins one name AND the dataset content digest `sha256:43ed5a3d...`; the runner asserts the digest of the fetched rows before any packet materialization |

---

## 5. How to use this in an agentic loop (concrete)

### 5.1 Evidence-root layout (create under `turing/evidence/bench/`, name it honestly)

```
worker_uplift_lab_S01_<date>/
  PREREGISTRATION.md              # hypotheses, arms, MDE, rerun policy, roster, budgets
  PREREGISTRATION.sha256          # digest of everything below the freeze line
  CLAIM_BOUNDARY.json
  analysis/analyze_uplift.py      # frozen BEFORE data; stdlib-only (see 5.6)
  analysis/dryrun_fixture/        # synthetic-data dry-run outputs, labeled FIXTURE
  shard/shard_manifest.json       # copy of S01 manifest + its sha256
  worker_safe_tasks/<instance_id>/{task_packet.json,worker_capsule.md}
  arms/{A,B,C,D}/<worker_id>/<instance_id>/  # per-cell result.json + tape refs
  receipts/<request_sha256>.json  # per-call receipts (also appended as tape events)
  predictions/preds_<worker>_<arm>.jsonl
  scoring/<run_id>/               # harness report_dir per (worker, arm)
  DEVIATIONS.md
  UPLIFT_REPORT.json / UPLIFT_REPORT.md   # final; status ceiling ADDRESSED
```

### 5.2 Commands (verified shapes)

Materialize worker-safe packets for S01 (reuse the audited tool; check its exact CLI with `--help` first — the S00 packets it produced are at `.../shards/S00/ipqc/S00-W00/worker_safe_tasks/`):

```bash
cd /home/zephryj/turingos_backup/work/turing
python tools/bench/materialize_swebench_worker_safe_tasks.py --help   # confirm flags, then materialize for shard S01
python tools/bench/audit_prompt_leakage.py --help                     # leakage audit over produced capsules
python tools/bench/audit_gold_patch_guard.py --root <evidence_root> --shard S01
```

Score one (worker, arm) prediction file with the qualified harness (sole scorer):

```bash
cd /home/zephryj/turingos_backup/work/turing
source .venv_swebench/bin/activate   # swebench==4.1.0 verified importable
python -m swebench.harness.run_evaluation \
  --dataset_name princeton-nlp/SWE-bench_Verified \
  --split test \
  --predictions_path evidence/bench/worker_uplift_lab_S01_<date>/predictions/preds_deepseek-v4-flash_armB.jsonl \
  --max_workers 2 \
  --timeout 1800 \
  --cache_level env \
  --run_id uplift_S01_deepseek-v4-flash_armB_v1 \
  --report_dir evidence/bench/worker_uplift_lab_S01_<date>/scoring/uplift_S01_deepseek-v4-flash_armB_v1
```

Retry ONLY harness-errored instances (pre-registered rerun policy):

```bash
python -m swebench.harness.run_evaluation ... --instance_ids <id1> <id2> --run_id uplift_..._retry1
```

### 5.3 Per-call receipt schema (tape event payload + `receipts/` file)

```json
{
  "schema_id": "turingos.worker_call_receipt.v1",
  "worker_policy_id": "sha256:<digest of ADR-M3-01 accepted text>",
  "arm": "B",
  "instance_id": "django__django-11099",
  "attempt": 1,
  "provider": "deepseek",
  "endpoint_base_url": "https://api.deepseek.com",
  "model_requested": "deepseek-v4-flash",
  "model_reported": "<response.model verbatim>",
  "provider_request_id": "<response id / request-id header>",
  "request_sha256": "sha256:...",
  "response_sha256": "sha256:...",
  "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
             "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 0},
  "usage_schema": "openai_compat",
  "unit_prices_microusd_per_mtok": {"input": 140000, "output": 280000},
  "price_table_digest": "sha256:<digest of the pinned, dated unit-price table in PREREGISTRATION.md>",
  "computed_cost_microusd": 0,
  "cost_source_kind": "provider_receipt_inline",
  "wall_clock_ms": 0,
  "created_at_utc": "..."
}
```

**Schema ownership (binding):** the schema owner is M1c (`turingos.cost_event.v2`, RES_M1 §5.5 / ADR-M1-004); the worker_call_receipt fields above are carried inside/alongside CostEvent.v2, and M3 consumes M1c's landed schema verbatim. Constraints inherited from that owner: all monetary amounts are **integer micro-USD** (the codec rejects floats on tape — RES_M1 §2.6 "No floats on tape"), and `cost_source_kind` takes values only from RES_M1 §2.6's closed enum `{provider_receipt_inline, provider_usage_api_reconciled, bounded_estimate, fixture}` — for this experiment's live calls the value is `provider_receipt_inline`.

(Anthropic workers: `usage_schema: "anthropic"` with `input_tokens/output_tokens/cache_creation_input_tokens/cache_read_input_tokens` and `provider_request_id` from the `request-id` header. Secrets never appear; assert with the existing `sk-` marker scan.)

### 5.4 Worker adapter sketch (arm A; arms B/C wrap the same callable inside the loop runner)

```python
# stdlib + provider SDK; one function per provider, same signature
def call_worker(capsule_text: str, model: str, base_url: str, api_key_env: str,
                max_output_tokens: int) -> tuple[str, dict]:
    """Returns (raw_response_text, receipt_dict). NEVER logs the key.
    OpenAI-compatible shape works for DeepSeek and OpenAI nano models."""
    import json, os, time, hashlib, urllib.request
    body = {"model": model, "max_tokens": max_output_tokens,
            "messages": [{"role": "user", "content": capsule_text}]}
    raw = json.dumps(body, sort_keys=True).encode()
    req = urllib.request.Request(base_url + "/v1/chat/completions", data=raw,
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + os.environ[api_key_env]})
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=600) as r:
        resp_bytes = r.read()
        req_id_hdr = r.headers.get("x-request-id", "")
    resp = json.loads(resp_bytes)
    receipt = {
        "schema_id": "turingos.worker_call_receipt.v1",
        "model_requested": model, "model_reported": resp.get("model", ""),
        "provider_request_id": resp.get("id", "") or req_id_hdr,
        "request_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "response_sha256": "sha256:" + hashlib.sha256(resp_bytes).hexdigest(),
        "usage": resp.get("usage", {}), "usage_schema": "openai_compat",
        "wall_clock_ms": int((time.monotonic() - t0) * 1000),
    }
    return resp["choices"][0]["message"]["content"], receipt
```

The prompt instruction for arm A should mirror the existing capsule candidate policy verbatim ("Produce a worker-derived unified diff against the base commit. Do not use dataset gold patches, official solution patches, or hidden evaluator labels." — from the S00 capsules) plus a strict output contract (single fenced `diff` block). Patch extraction + `git apply --check` validation happens harness-side via the prediction, not by a repo-local evaluator (the repo-local evaluator has a demonstrated false positive, django-11885 — audit F4 — and is advisory only).

### 5.5 Ablation-honesty audit (arm B vs C)

For every task: load the two capsule texts, strip the broadcast-rules section from B's capsule (delimited exactly as `visible_grok_prompt` emits it), assert byte-equality with C's capsule; write `ablation_honesty_audit.json` with per-task PASS/FAIL and the diff hunk on FAIL. Wire it as a gate before scoring arm C.

### 5.6 Frozen analysis script (core; stdlib-only, no external deps)

```python
# analyze_uplift.py -- frozen at pre-registration. Inputs: per-(worker,arm) resolved_ids
# from the harness evaluation_results.json files ONLY.
import json, random, math
from math import comb

def exact_mcnemar_p(b, c):
    """b = pairs solved only in arm2 (uplift), c = pairs solved only in arm1. Two-sided exact."""
    nd = b + c
    if nd == 0: return 1.0
    lo = sum(comb(nd, k) for k in range(0, min(b, c) + 1)) / 2**nd
    return min(1.0, 2 * lo)

def paired_table(res1: set, res2: set, tasks: list):
    b = sum(1 for t in tasks if t not in res1 and t in res2)   # uplift discordant
    c = sum(1 for t in tasks if t in res1 and t not in res2)   # harm discordant
    return b, c

def cluster_bootstrap_delta(cells, tasks, workers, arm1, arm2, reps=10000, seed=20260702):
    """cells[(worker, arm)] = set(resolved instance_ids). Resample TASKS (clusters)."""
    rng = random.Random(seed)
    deltas = []
    for _ in range(reps):
        sample = [tasks[rng.randrange(len(tasks))] for _ in tasks]
        n1 = sum(t in cells[(w, arm1)] for w in workers for t in sample)
        n2 = sum(t in cells[(w, arm2)] for w in workers for t in sample)
        deltas.append((n2 - n1) / (len(sample) * len(workers)))
    deltas.sort()
    return deltas[int(0.025 * reps)], deltas[int(0.975 * reps)]

# Pooled primary H1: pool (worker,task) pairs for McNemar; CI from cluster bootstrap.
# Holm: test H1 at alpha=0.025; if reject, H2 at alpha=0.05. Report Δ, CI, b, c, MDE
# statement, and per-worker exploratory tables regardless of significance.
```

(The MDE/power table in §2.1 was produced by an exact-power extension of this script; embed both in `analysis/` so the numbers are reproducible.)

### 5.7 Orchestration order (atoms for the loop)

1. Freeze pre-registration (incl. analysis dry-run on FIXTURE data) → independent verifier ACK → record digest on tape.
2. Materialize + audit S01 worker-safe packets (leakage audit, gold-patch guard) → sha256 table.
3. Run arm D (deterministic floor) end-to-end for one worker pipeline → score → assert 0 resolved (pipeline canary, P9).
4. Pilot: 10 tasks from S02 per worker (the first 10 instance IDs in S02's `shard_manifest.json` stored order, identical for all workers — deterministic rule in §2.7, ID list enumerated verbatim in `PREREGISTRATION.md`), arm A only → confirm each worker lands in the 15–45% weakness band; drop/replace workers outside the band (logged decision, pre-registered rule).
5. Run arm A for all workers on S01 → freeze predictions → score.
6. Run arm B, then arm C (frozen task order; ablation-honesty audit between) → freeze predictions → score.
7. Run frozen analysis → `UPLIFT_REPORT.{json,md}` with claim boundary → status ADDRESSED → hand to independent cross-family verifier.
8. Only after ADR-M3-01 is accepted and (optionally) the lab has run: execute the S00 resume protocol (§2.9) as a separate atom chain.

---

## 6. ADR-ready decision records (MADR-style, one paragraph each)

**ADR-M3-01 — Worker Policy: machine-recorded worker identity with provider receipts on tape.** Context: the central experiment was unanswerable because worker identity was prose-only (`model_name_or_path: "turingos-internal-rehearsal"`, no usage records — audit F5, Art. 0.2 violation). Decision: every LLM call in any benchmark-adjacent pipeline MUST append a receipt event to the tape carrying pinned `model_requested`, provider-echoed `model_reported`, provider request ID, request/response sha256 digests, verbatim provider `usage`, a pinned integer micro-USD price table (`price_table_digest`), integer `computed_cost_microusd`, `cost_source_kind: provider_receipt_inline` (from RES_M1 §2.6's closed enum), and wall-clock — with API keys and auth headers categorically excluded; prediction files' `model_name_or_path` must encode `worker__arm__experiment`. Schema owner is M1c (CostEvent.v2, RES_M1 §5.5 / ADR-M1-004); the worker_call_receipt fields are carried inside/alongside CostEvent.v2 and M3 consumes M1c's landed schema verbatim — no floats ever appear on tape (the codec rejects them). Consequences: F5 closes mechanically; H-VPPUT gains billing-grounded cost inputs (G5, F7); all runs get slightly heavier plumbing (one adapter module, depends on M1c tape access); any run lacking receipts is invalid by construction and cannot be quoted.

**ADR-M3-02 — Pre-registered 4-arm paired experiment on frozen shard S01.** Context: R2 requires a controlled uplift measurement; prior evidence conflated worker capability with substrate value; S00 is old-policy-contaminated and Stage16 is Django-only. Decision: run arms A (worker alone), B (full TuringOS loop), C (B minus failure-memory injection), D (deterministic fake floor) over the sealed 50-task, 10-repo shard S01 (verified untouched: directory contains only `shard_manifest.json`), with identical per-instance budgets across arms (5 attempts / 400K tokens / fixed wall-clock from the frozen `loop_manifest.json` profile), frozen task order shared by B and C, an ablation-honesty byte-diff audit, and a sha256-frozen pre-registration (hypotheses, MDE, rerun policy, roster, analysis code + FIXTURE dry-run) ACKed by an independent verifier before any worker call. Consequences: G4 gets a valid measurement where a null/negative result is a PASS; the experiment consumes ~10 fifty-task harness evals; S01 is spent for other purposes; deviations require logged entries rather than silent judgment.

**ADR-M3-03 — Statistical analysis plan: exact McNemar primary, cluster-by-task bootstrap CIs, pooling across 2–3 workers, Holm over two contrasts.** Context: n=50 paired binary outcomes; computed MDE for a single worker is ~15–23 percentage points at 80% power — honest but coarse; pooling 2–3 workers reaches ~6–14 pp; multiple arms invite metric shopping. Decision: primary H1 (B>A) and secondary H2 (B>C) are the only confirmatory tests, evaluated on pooled worker-task pairs with the exact (conditional binomial) McNemar test, Holm–Bonferroni ordered H1-then-H2; effect sizes reported as Δ with 10,000-replicate cluster-by-task percentile/BCa bootstrap 95% CIs; arm D is a manipulation check (any solve = stop); per-worker, per-difficulty, and cost-normalized analyses are labeled exploratory; the analysis script is stdlib-only and frozen at pre-registration. Consequences: results are referee-proof and reproducible without heavyweight stats stacks; small true uplifts (<~6 pp) remain undetectable at this scale and must be reported as "CI includes 0, powered for MDE=y"; adding workers later requires a new pre-registration.

**ADR-M3-04 — Weak-worker roster: DeepSeek V4 Flash + GPT-5-nano-class (+ optional Claude Haiku 4.5), calibrated to a 15–45% baseline band.** Context: a frontier worker measures the worker (the recorded reason for the S00 supervisor stop); "weak" must be operationalized, cheap, API-stable, and heterogeneous across providers; `deepseek-chat` retires 2026-07-24 so legacy aliases are a live hazard. Decision: pin `deepseek-v4-flash` (non-thinking; $0.14/$0.28 per MTok), one OpenAI nano/mini-class model verified against the official pricing page at pre-registration time (~$0.05–0.75 in), and optionally `claude-haiku-4-5` ($1/$5) as a third family; each worker must land in the 15–45% arm-A band on a 10-task S02 pilot or be replaced under a logged rule; model IDs, echoed model strings, and unit prices are frozen in the pre-registration. Consequences: total token spend bounded well under $1K; three provider families de-risk single-provider drift; absolute solve rates remain contaminated-benchmark numbers and are never quoted as capability (claim boundary); roster changes after freeze force re-registration.

**ADR-M3-05 — Upstream `swebench==4.1.0` Docker harness is the sole scorer, in the already-qualified configuration, with a pre-registered rerun policy.** Context: the repo-local evaluator produced a demonstrated false positive (django-11885, audit F4); the upstream harness is qualified on this host (20/20 repaired replay, `.venv_swebench`, Docker 20.10.24); public sources document per-instance flakiness and image-build transients. Decision: only `python -m swebench.harness.run_evaluation` outputs determine `resolved`; configuration is pinned to the qualified defaults (dataset name + sealed content digest, default `swebench` image namespace, `--cache_level env`, `--timeout 1800`, `--max_workers 2`); each prediction is scored once; instances landing in `error_ids`/`incomplete_ids` get ≤2 logged single-instance retries and, if still erroring, pairwise exclusion across all arms; `resolved`/`unresolved` outcomes are never re-rolled; repo-local evaluators are advisory-only and never appear in the analysis inputs. Consequences: scoring identity matches the qualification evidence; ~100–120 GB image cache and 1–3 h per 50-task eval are accepted costs; faster third-party registries (Epoch/LogicStar) are explicitly deferred until re-qualified.

**ADR-M3-06 — S00 resume protocol (post-Worker-Policy).** Context: S00 sits at 48/50 machine-marked BLOCKED predictions generated under the old (frontier, receipt-less) policy, with a recorded supervisor taint on `astropy__astropy-12907`; R7 forbids quoting 48/50 as performance. Decision: after ADR-M3-01 acceptance — (1) stamp the existing 48 predictions OLD-POLICY INVENTORY (auditable, non-performance); (2) produce the 2 missing predictions (`pydata__xarray-3677`, `pylint-dev__pylint-6386`) under the new policy with tape receipts; (3) produce `astropy__astropy-12907`'s patch only from an independent worker context fed solely the worker-safe capsule, per the taint note; (4) any S00 scoring is labeled mixed-policy inventory characterization, excluded from uplift analyses, and never quoted as a score. Consequences: S00 reaches 50/50 auditable coverage without laundering old-policy work into new claims; the uplift lab stays statistically clean on S01; the Verified-500 campaign remains paused until M3's gate passes (intent §7).

---

### Appendix — key verified paths (for the implementation agent)

- Harness qualification packet: `/home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_official_harness_qualification_20260629/` (`official_harness_qualification.json`, `harness/run_evaluation_help.txt`, `phase_f_20_run/evaluation_results.json`)
- Venv: `/home/zephryj/turingos_backup/work/turing/.venv_swebench` (swebench 4.1.0 import verified)
- Campaign root incl. sealed manifests, shards S00–S09, claim boundary, stop audit, taint note: `/home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_verified_500_campaign_20260629/`
- Budget profile to reuse: `/home/zephryj/turingos_backup/work/turing/evidence/bench/swe_bench_phase_g_verified_500_manifest_20260628/loop_manifest.json`
- Reusable tools: `tools/bench/{materialize_swebench_worker_safe_tasks,audit_prompt_leakage,audit_gold_patch_guard,audit_worker_candidate_patch,build_predictions_jsonl,run_direct_grok_baseline_smoke,run_mini_swe_bench_substrate_smoke,run_swebench_shard,audit_micro_tape_decision_dag}.py` under `/home/zephryj/turingos_backup/work/turing/`
- Web sources: [DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing) · [DeepSeek change log](https://api-docs.deepseek.com/updates) · [SWE-bench harness reference](https://www.swebench.com/SWE-bench/reference/harness/) · [Docker setup](https://www.swebench.com/SWE-bench/guides/docker_setup/) · [Epoch fast-eval blog](https://epoch.ai/blog/swebench-docker) · [LogicStar compression](https://logicstar.ai/blog/how-we-made-swe-bench-50x-smaller) · [Large Language Monkeys (flakiness)](https://arxiv.org/pdf/2407.21787) · [UTBoost critique](https://medium.com/@danieldkang/swe-bench-verified-is-flawed-despite-expert-review-utboost-exposes-gaps-in-test-coverage-4b75c6b940c6) · [OpenAI pricing](https://developers.openai.com/api/docs/pricing) · [GPT-5 Nano pricing](https://pricepertoken.com/pricing-page/model/openai-gpt-5-nano) · [OpenRouter Qwen](https://openrouter.ai/qwen) · [Fireworks Kimi](https://fireworks.ai/blog/kimi-k2p7-code) · [SWE-bench Verified caveats](https://benchmarkingagents.com/swe-bench/)
