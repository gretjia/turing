# SPEC_ECONOMY — Agent Economy Invariants (INV-1..INV-18)

Produced under capsule PART A of `PROJECT_ECON_VERIFY_EVAL_AUTORESEARCH.md`
(branch `hci/software3-20260705`). Every row below was hand-verified against
the current source at the stated `file:line` — not copied from the capsule's
approximate anchors. Where no enforcement exists, the row is marked
**GAP → 见 PART C** per the capsule's honesty rule (a GAP is a valid, expected
finding, not a failure to report).

Each invariant has four fields: **陈述**(statement) | **依据**(constitutional/
design basis) | **现在在哪强制**(file:line, or GAP) | **如何机器检查**(machine
check).

Line numbers verified 2026-07-07 against:
`crates/turing-economy/src/lib.rs` (1122 lines),
`crates/turing-predicate/src/lib.rs`,
`crates/turing-daemons/src/lib.rs`,
`pack/04_registries/event_registry_v5_3_1.json`.

---

## A.1 守恒类 (Conservation)

### INV-1 — 铸造守恒 (mint conservation)
- **陈述**: 每次 `PositionMinted`, `coin_in == yes_out == no_out`。
- **依据**: D1/D7 (RES_ECON_agent_economy_v2_design.md §D1, §D7); Art 经济 CTF 设计。
- **现在在哪强制**: 双重强制。(1) 构造函数
  `EconomyEvent::position_minted` (`crates/turing-economy/src/lib.rs:68-82`)
  parses a single `coin` value and sets `yes_out`/`no_out`/`coin_in` all from
  that same value (lines 76-79) — structurally cannot diverge. (2)
  `check_conservation` re-derives and hard-fails on divergence per event
  (lines 547-561, `EconomyError::MintInvariantViolated`) — defense-in-depth
  against a forged/corrupted tape event that bypassed (1).
- **如何机器检查**: unit test constructs `PositionMinted` via the API and
  asserts the three fields are string-equal; a property test additionally
  constructs a *hand-forged* `EconomyEvent::PositionMinted` struct literal
  with `coin_in != yes_out` and asserts `check_conservation` returns
  `Err(MintInvariantViolated)`.

### INV-2 — 结算守恒 (settlement conservation, per market)
- **陈述**: 每 `MarketSettled`, 赎回 Coin ≤ 铸造 Coin + 声明补贴 (D7)。
- **依据**: D7 (RES_ECON_agent_economy_v2_design.md §D7 "Conservation predicate").
- **现在在哪强制**: `check_conservation`
  (`crates/turing-economy/src/lib.rs:526-614`). `declared_subsidy` accumulates
  `initial_pool_y + initial_pool_n` from `MarketCreated` (line 545);
  `minted_coin` accumulates `PositionMinted.coin_in` (line 555); `redeemed_coin`
  sums winning-side positions at `MarketSettled` (lines 579-594); `holds =
  redeemed_coin <= minted_coin + declared_subsidy` (line 604). Existing test:
  `crates/turing-economy/tests/economy_market.rs:139-177`
  (`conservation_holds_across_a_full_market_lifecycle`) and
  `:201-251` (`conservation_flags_over_redemption_beyond_minted_plus_subsidy`,
  proves the negative case is caught too).
- **如何机器检查**: `cargo test -p turing-economy conservation` (existing);
  `turing audit market --micro-git <tape>` CLI path calls the same fn (per
  `market_settle_response`, `crates/turing-daemons/src/lib.rs:1627-1750`,
  which runs `MarketReplay`/`check_conservation` against the real tape before
  appending `MarketSettled`).

### INV-3 — 全局无凭空 Coin (no free Coin, whole-tape)
- **陈述**: 全市场累计, Σ赎回 ≤ Σ铸造 + Σ补贴; 更强地, 没有任何路径能凭空产生
  `coin_in` (即铸造前该 Coin 必须来自某个已记录的发放来源)。
- **依据**: D7 conservation (global form) + Art 0.2 (tape-canonical: every
  balance must be tape-derivable, not asserted out of thin air).
- **现在在哪强制**: **部分 GAP**. The per-market form (Σ redeemed ≤ Σ minted +
  Σ subsidy *within that market*) follows algebraically from INV-2 holding for
  every market (`check_conservation` returns one report per market,
  `crates/turing-economy/src/lib.rs:600-613`; no single function sums across
  markets into one global boolean, but since YES/NO tokens are market-scoped
  and non-fungible across markets, the per-market form is equivalent to the
  global form for the *redemption* side).
  **However**, the *mint* side has a real gap: `market_mint_response`
  (`crates/turing-daemons/src/lib.rs:1361-1458`) accepts an arbitrary
  caller-supplied `coin_in` (line 1381) and calls
  `EconomyEvent::position_minted` (line 1400) with **no check that the minting
  `agent_id` actually holds that much Coin** beforehand — there is no
  `CoinIssued`/genesis/faucet event type anywhere in the crate or registry
  (`grep -n "CoinIssued\|coin_issu\|Faucet" crates/turing-economy/src/lib.rs
  crates/turing-daemons/src/lib.rs` → 0 hits) and no balance-sufficiency
  predicate check in `market_mint_response`'s check list (only
  `principal_position_cap`, line 1406-1416). So `coin_in` is conserved
  *within* the CTF/AMM/settlement chain once minted, but nothing on the
  minting boundary itself prevents an agent from minting Coin it never
  possessed — **GAP → 见 PART C** (candidate bug class: unlimited free Coin
  via repeated `market.mint` calls).
- **如何机器检查**: full-tape replay: build a tape with N markets, M mints, K
  swaps, J settlements (fixed seed); sum `MarketConservationReport` fields
  across all N reports and assert the global inequality; separately, a
  negative test that calls `market.mint` twice for the same agent with no
  prior Coin-granting event and asserts *some* rejection — this test will
  currently **fail** (no rejection exists), which is the machine-checkable
  form of the GAP above.

### INV-4 — 声誉可重建 (F3: reputation must be deterministically re-derivable)
- **陈述**: 任何声誉/价格派生视图满足 `assert_eq!(view, derive_from_tape(tape))`。
- **依据**: Art 0.2 (Tape Canonical Axiom); F3
  (`DEV_PLAN_constitutional_emergence_20260707.md` line 51: "所有度量漂移必须
  确定性可重建 (Art 0.2)").
- **现在在哪强制**: **GAP (vacuous today, unenforced going forward)**. No
  reputation system exists anywhere in `crates/turing-economy/src/lib.rs`,
  `crates/turing-daemons/src/lib.rs`, or `crates/turing-predicate/src/lib.rs`
  (`grep -rn "reputation\|Reputation"` → 0 hits in all three). The invariant
  is trivially satisfied today because there is nothing to violate it — but
  there is also no `derive_from_tape`-style function, no `assert_eq!(view,
  replay(view))` test, and no schema slot proving *future* reputation state
  will be tape-derived rather than held as untracked mutable state. This
  matches DEV_PLAN's own framing (支柱一 "持久声誉" is listed as future work,
  not yet built) — **GAP → 见 PART C / PART D.2 (must land before any
  reputation feature ships)**.
- **如何机器检查**: not machine-checkable today (no subject exists); the
  eval to write once reputation lands: build tape, compute view once, replay
  tape from scratch, recompute view, `assert_eq!`.

---

## A.2 AMM/算术类 (Arithmetic)

### INV-5 — k 单调 (constant-product invariant never decreases)
- **陈述**: 每 swap 后 `poolY'·poolN' ≥ k` (等号仅到 favor-pool 的 dust)。
- **依据**: D6 (RES_ECON_agent_economy_v2_design.md §D6, "Post-trade predicate:
  poolY′·poolN′ ≥ k").
- **现在在哪强制**: `assert_k_non_decreasing`
  (`crates/turing-economy/src/lib.rs:301-316`), called from both
  `AmmPool::buy_yes` (line 233) and `AmmPool::buy_no` (line 267) — a swap that
  would violate it returns `Err(PostTradeInvariantViolated)` before the
  `AmmSwapExecuted` event is even constructed, so no such event can exist.
  Audit-path re-check on an already-recorded event:
  `verify_swap_post_trade_invariant` (lines 323-329). Existing test:
  `crates/turing-economy/tests/economy_market.rs:272-292`
  (`repeated_rounding_favorable_trades_cannot_extract_pool_value`, 500
  iterations against a deliberately thin pool) — this is a fixed, deterministic
  sequence (alternating pay=1/pay=3), **not** a hand-written random-seeded
  property loop, so it does not yet meet the capsule's PART-B property-test
  bar (≥1000 iterations, fixed-seed random), but it is real in-process
  enforcement today.
- **如何机器检查**: `cargo test -p turing-economy amm_cpmm` /
  `repeated_rounding_favorable_trades_cannot_extract_pool_value` (existing);
  PART B should add a fixed-seed random-pay/pool-size property loop (≥1000
  iters) per the capsule's B.1 spec.

### INV-6 — 舍入 favor pool (rounding never favors the trader)
- **陈述**: `mul_div`/swap 舍入方向永远不利 trader (禁 money-pump)。
- **依据**: D6 ("Rounding always favors the pool... PRBMath shipped a
  signed-rounding bug for years, so verify, don't assume").
- **现在在哪强制**: `DecimalAmount::mul_div`
  (`crates/turing-economy/src/lib.rs:971-982`) uses `self.units *
  numerator.units / denominator.units` — plain integer division, which
  truncates toward zero. Every operand reaching `mul_div` is non-negative
  (`DecimalAmount::parse_non_negative` at line 923 rejects negatives/`-`
  prefix at every call site, per the doc comment on line 294-300), so
  truncation-toward-zero on non-negative operands is always a **floor**: the
  trader's derived output (`d_y_abs`/`d_n_abs` at lines 230/264) can only be
  under-computed relative to the exact rational value, which is the
  pool-favoring direction. This is design reasoning verified against the
  actual division semantics (Rust `i128` division truncates toward zero,
  confirmed: `-7i128 / 2 == -3`, but all operands here are non-negative so
  this reduces to floor division) — not yet backed by a dedicated
  `mul_div`-only unit test with adversarial (near-boundary) inputs; the
  end-to-end evidence is the same `repeated_rounding_favorable_trades_...`
  test as INV-5.
- **如何机器检查**: PART B should add a `mul_div`-focused property test:
  fixed-seed random `(self, numerator, denominator)` triples, comparing
  `mul_div` output against an exact rational (e.g. via `i128`→bignum or
  cross-check with `f64` at low precision) and asserting the integer result
  is never greater than the true value on the trader's receiving side.

### INV-7 — 无溢出 (no overflow/panic/wrap on extreme inputs)
- **陈述**: i128 定点在极端输入(接近 `i128::MAX`/`MIN`, 0, 1)不 panic/wrap。
- **依据**: D6 ("Integer safety as gated predicates" — the incident casebook:
  Balancer $128M, zkLend, Bunni were all rounding/overflow bugs).
- **现在在哪强制**: **GAP, confirmed by inspection**.
  `DecimalAmount::mul` (`crates/turing-economy/src/lib.rs:965-969`) computes
  `left.units * right.units / SCALE` with a bare `*` (no `checked_mul`);
  `mul_div` (971-982) and `ratio` (984-994) likewise use bare `*`/`/`. Only
  `parse_non_negative` (923-959) uses `checked_mul` (line 941, whole-part ×
  `SCALE` overflow check on string parse). `grep -n "checked_mul\|checked_add\|checked_sub"
  crates/turing-economy/src/lib.rs` → only line 941 (parse path); the
  arithmetic *inside* `mul`/`mul_div`/`ratio` — which is exactly where D6
  demands gated integer-safety predicates — has none. In a debug build this
  panics on overflow (Rust's default); in a release build (`overflow-checks =
  false` is Cargo's default release profile unless overridden) this would
  **silently wrap**, which is worse than a panic because it would corrupt
  `pool_y_after`/`pool_n_after` without raising `PostTradeInvariantViolated`
  first (the multiplication overflow happens before the k-check runs on the
  now-corrupted value). — **GAP → 见 PART C** (lens 1, arithmetic/rounding).
- **如何机器检查**: fixed-seed property test feeding `DecimalAmount` values
  near `i128::MAX / SCALE` into `buy_yes`/`buy_no`/`mul`/`mul_div`/`ratio` and
  asserting either a clean `Err` (if checked arithmetic were added) or, today,
  documenting the observed panic/wrap as the confirmed bug signature; also
  check release-profile `overflow-checks` setting in the workspace
  `Cargo.toml`/`crates/turing-economy/Cargo.toml` (currently absent → defaults
  apply, i.e. checked in dev, silently wrapping in release).

### INV-8 — 最小流动性 (minimum-liquidity floor against first-depositor attack)
- **陈述**: 首次注入锁定最小流动性底 (防 first-depositor)。
- **依据**: D6 ("Minimum-liquidity floor locked at market creation
  (first-depositor class)" — explicit design requirement, not optional).
- **现在在哪强制**: **GAP, confirmed**. `AmmPool::new`
  (`crates/turing-economy/src/lib.rs:204-219`) only rejects a *zero* pool
  (`EconomyError::ZeroPool`, line 212) — no minimum-size floor, no locked
  first-depositor share, no distinct "add liquidity after creation" event or
  function exists at all (`grep -n "liquidity"` in the crate only matches a
  doc comment, line 490). The event registry has a schema slot reserved for
  this (`MarketLiquidityAdded`, `pack/04_registries/event_registry_v5_3_1.json`
  lines 564-573, `payload_schema_id: market_liquidity_added.v1`,
  `ADDITIVE_AGENT_ECONOMY_V1_0`) but it is **not implemented** anywhere in
  `crates/turing-economy/src/lib.rs` or `crates/turing-daemons/src/lib.rs`
  (`grep -n "MarketLiquidityAdded\|market_liquidity_added"` → 0 hits in
  either). — **GAP → 见 PART C** (lens 2, conservation/first-depositor class).
- **如何机器检查**: construct a market with a deliberately tiny pool (e.g.
  `pool_y=pool_n="0.000000001"`, the smallest non-zero unit at SCALE=1e9) and
  assert either `AmmPool::new` rejects it below some floor (does not today)
  or that a subsequent trade cannot extract disproportionate value from a
  thin pool (partially covered today by the same money-pump test as
  INV-5/6, but that test uses pool size 1000, not the first-depositor
  minimum case).

---

## A.3 权威/边界类 (Authority) — 最硬红线

### INV-9 — 价格非真相 (price never moves accepted_head)
- **陈述**: 所有经济事件 `head_effect=PRESERVE`, 无代码路径移动 `accepted_head`。
- **依据**: Art 0.1 (四要素映射, "Strict discipline"); Art I.1 (谓词唯一权威)。
- **现在在哪强制**: Two independent layers. (1) **Registry-level**: every one
  of the 15 `ECONOMY`-class events in
  `pack/04_registries/event_registry_v5_3_1.json` has `"head_effect":
  "PRESERVE"` (verified by direct read of lines 554-... through the
  `RewardDistributed` entry at line 642-650; `grep -c '"event_class": "ECONOMY"'
  pack/04_registries/event_registry_v5_3_1.json` → 15, all 15 PRESERVE —
  confirms the capsule's "已核实注册表 15/15 PRESERVE" claim). (2)
  **Code-level**: `BudgetSuggestion.can_move_accepted_head` is hardcoded
  `false` at construction (`crates/turing-economy/src/lib.rs:846`, inside
  `MarketRouter::suggest`), and `BudgetSuggestion.head_effect` is hardcoded
  `"PRESERVE"` (line 847); `PriceBroadcast.head_effect` is likewise hardcoded
  `"PRESERVE"` (line 880, inside `PriceBroadcast::new`). No field on any
  economy struct is settable to anything else by a caller (all such fields
  are set inside constructors, not passed in).
- **如何机器检查**: unit test: call `MarketRouter::suggest` and
  `PriceBroadcast::new` with arbitrary inputs, assert
  `can_move_accepted_head == false` and `head_effect == "PRESERVE"` always;
  registry test: parse `event_registry_v5_3_1.json`, filter
  `event_class=="ECONOMY"`, assert every entry's `head_effect=="PRESERVE"`
  (machine-checkable count: 15/15).

### INV-10 — 谓词唯一接受权威 (market price never becomes accept authority)
- **陈述**: 市场共识/价格永不成为"接受候选解"的权威; 接受只由 ∏p。
- **依据**: Art I.1 (布尔信号唯一接受权威)。
- **现在在哪强制**: `PredicateKernel::run`
  (`crates/turing-predicate/src/lib.rs:51-97`) computes `product =
  PredicateProduct::Pass` iff `failed_predicates.is_empty()` (lines 76-80) —
  a pure AND (∏p) over the `Vec<PredicateCheck>` passed in by the caller.
  `derive_candidate_predicate_checks`
  (`crates/turing-daemons/src/lib.rs:2024-...`, the function that builds the
  check list for `CandidateAccepted`) only reads tape facts about
  `capsule_id`/`macro_anchor_id`/`worker_receipt_id`/
  `official_evaluator_evidence_id` (lines 2054-2067) — no `PriceSignal`,
  `MarketRouter`, `BudgetSuggestion`, or any economy type appears anywhere in
  that function or in `candidate_decision_response`'s check-building path
  (verified: `MarketRouter`/`BudgetSuggestion`/`PriceSignal` are imported at
  `crates/turing-daemons/src/lib.rs:27` and used only inside
  `market_shadow_suggest_response`, lines 1036-1087, a wholly separate
  `market.shadow.suggest` RPC that never appends `CandidateAccepted`).
- **如何机器检查**: `grep -n "MarketRouter\|BudgetSuggestion\|PriceSignal"
  crates/turing-daemons/src/lib.rs` and assert every hit's enclosing function
  is NOT `candidate_decision_response`/`derive_candidate_predicate_checks`
  (i.e. no economy identifier reachable from the accept path); this is a
  static grep-based CI check, not a runtime test.

### INV-11 — 结算 oracle 绑定 (G-MKT-06)
- **陈述**: `MarketSettled` 合法 iff `settlement_event_id` 引用同 capsule 的真实
  `CandidateAccepted`(YES)/`FailureNode`(NO), 且冻结 `predicate_set_hash` 未被
  弱化, 且结算事件严格晚于市场创建。
- **依据**: D4 (RES_ECON_agent_economy_v2_design.md §D4, "The market question and
  its oracle").
- **现在在哪强制**: `market_settlement_gate_g_mkt_06`
  (`crates/turing-predicate/src/lib.rs:324-371`) checks, in order: (1) the
  settlement id is a well-formed Micro event id (line 327); (2) frozen
  `predicate_set_hash` matches the current `candidate_predicate_set_hash()`
  (lines 329-334, `PredicateSetWeakened` on mismatch); (3) for YES, the
  referenced `CandidateAccepted.capsule_id` matches the market's frozen
  `capsule_id` exactly, and the market's `capsule_id` is non-empty (lines
  337-346, `SettlementCapsuleMismatch`); (4) for NO, only existence/type of
  `FailureNode` is checked (capsule cross-check is a documented, unrecoverable
  limitation — no `capsule_id` field on `FailureNode`'s payload, lines
  288-291); (5) any other `(result, reference)` combination is refused (lines
  350-359); (6) the referenced event's tape index must be strictly after the
  market's own `MarketCreated` tape index (lines 362-370,
  `SettlementOrderingViolated`). Caller wiring:
  `market_settle_response` (`crates/turing-daemons/src/lib.rs:1627-1750`)
  gathers all these facts from the real tape (lines 1683-1716) and refuses to
  append `MarketSettled` unless `PredicateKernel.run(...).product ==
  PredicateProduct::Pass` (lines 1717-1730).
- **如何机器检查**: build a fixture tape with (a) a legitimate settlement, (b)
  a settlement referencing a `CandidateAccepted` from a *different* capsule,
  (c) a settlement referencing a `FailureNode` for a YES result, (d) a
  settlement whose referenced event predates `MarketCreated`, (e) a settlement
  after the predicate-check-id set has been mutated; assert (a) passes and
  (b)-(e) each return the specific `MarketPputPredicateError` variant above.

---

## A.4 抗操纵类 (Anti-manipulation)

### INV-12 — 自成交拒绝 (self-trade rejection)
- **陈述**: 同 principal 对侧同轮 → refused。
- **依据**: D5 (RES_ECON_agent_economy_v2_design.md §D5, "Defenses for an
  all-agent market").
- **现在在哪强制**: `check_self_trade`
  (`crates/turing-economy/src/lib.rs:626-649`): scans the tape for the most
  recent swap on `market_id` (lines 632-639); if the same `trader_id` just
  took the opposite `side` with no other principal's swap interposed, returns
  `Err(SelfTradeRejected)` (lines 640-647). Trading the *same* side again, or
  opposite side *after* another principal traded, is explicitly allowed (per
  the doc comment, lines 618-625) — this is a deliberate scope boundary, not
  an oversight.
- **如何机器检查**: construct a tape where trader A buys YES then immediately
  buys NO on the same market with no intervening trader; assert
  `check_self_trade` returns `Err`. Construct a second case where trader B
  trades between A's two swaps; assert `check_self_trade` returns `Ok`.

### INV-13 — principal 级仓位上限 (per-principal position cap)
- **陈述**: 跨账户按 principal 聚合封顶。
- **依据**: D5.
- **现在在哪强制**: `check_principal_position_cap`
  (`crates/turing-economy/src/lib.rs:662-683`), backed by `principal_position`
  (lines 726-750, aggregates minted + swapped YES/NO exposure for a
  `principal_id` from the tape alone). **Known, documented limitation
  (not solved, per the capsule)**: `principal_id` here is literally
  `agent_id` — the doc comment (lines 655-661) states explicitly "this
  codebase has no principal/account-grouping concept distinct from
  `agent_id`... A Sybil that spreads the same economic actor across multiple
  `agent_id`s formally defeats this cap." Confirmed by inspection: no
  `principal` identifier exists anywhere else in the workspace outside this
  comment. Called from `market_mint_response`
  (`crates/turing-daemons/src/lib.rs:1406-1416`) before every mint.
- **如何机器检查**: construct a tape where a single `agent_id` mints up to the
  cap, then attempts one more unit; assert `Err(PrincipalPositionCapExceeded)`.
  Sybil-defeat is **not** machine-checkable as a pass/fail today since it is
  an acknowledged gap, not a bug in this function's stated contract — flagged
  instead under INV-15's neighbor gap and D.2's roadmap (principal registry
  with `principal_id != agent_id`).

### INV-14 — proposer 冲突 (proposer conflict-of-interest cap)
- **陈述**: capsule proposer 不得在自己市场持 NO 超 de-minimis。
- **依据**: D5.
- **现在在哪强制**: `check_proposer_conflict`
  (`crates/turing-economy/src/lib.rs:693-722`): no-op when `proposer_id` is
  empty or `trader_id != proposer_id` (lines 702-704); otherwise computes
  **net** NO exposure (`no - yes`, floored at zero, lines 709-713) so the
  proposer's own CTF mint (which always yields `yes_out == no_out` per
  INV-1) never trips this by itself — only a directional swap into NO does;
  rejects with `Err(ProposerConflictRejected)` if net NO exceeds
  `de_minimis_cap` (lines 714-720).
- **如何机器检查**: construct a tape where the market's proposer swaps into
  NO past the de-minimis cap; assert `Err`. Construct a case where the
  proposer only mints (equal YES/NO) and never swaps; assert `Ok` regardless
  of mint size (proves the net-exposure design, not raw no_position).

### INV-15 — 难度定价 (reputation must not be cheaply farmable via trivial capsules)
- **陈述**: 声誉计价单位(一次 PASS)不得被 trivial-capsule 廉价量产; 声誉应按
  "被他者成功复用次数"计而非自产 PASS。
- **依据**: Art II (信号的选择性广播, 原文); F1
  (`DEV_PLAN_constitutional_emergence_20260707.md` line 37, "谓词作奖励的自指
  防线"); DEV_PLAN Phase 1 explicitly lists "难度加权或'被复用计数'落地(挡
  trivial-capsule farming)" as unbuilt future work.
- **现在在哪强制**: **未强制 → 关键 GAP, confirmed**. There is no reputation
  system at all in this codebase (see INV-4) — a fortiori there is no
  difficulty-weighting or reuse-count mechanism, and no defense against an
  agent proposing many trivial capsules to accumulate cheap PASS units. This
  is the single most severe unclosed gap identified in this SPEC: F1's
  self-referential "predicate as reward" danger (a predicate that is both the
  accept authority AND the reward source can be farmed by an agent who
  controls both what gets proposed and how hard it is) has no code-level
  countermeasure yet. — **GAP → 见 PART C** (lens 4, 防御绕过镜头) — this is
  the highest-priority item for PART D.2.
- **如何机器检查**: not machine-checkable today (no subject exists); the
  eval to write once difficulty-weighting lands: construct N trivial
  capsules vs 1 hard capsule, assert reputation-per-capsule is not equal
  (trivial capsules must not earn full-weight PASS credit).

---

## A.5 价格-MCTS 类 (Price-as-signal, target state)

### INV-16 — softmax 良态 (softmax routing well-behaved at both temperature extremes)
- **陈述**: 路由 `P=softmax(price/τ)`, τ=0 退化为现 argmax(向后兼容), τ→∞ 退化为
  均匀。
- **依据**: `RES_ECON_price_as_mcts_core_20260707.md` line 8 ("价格 = MCTS 的
  Q 值; 路由 = softmax(价格/τ)"), gap-1 (lines 15-18).
- **现在在哪强制**: **未实现 → GAP, confirmed**. `MarketRouter::suggest`
  (`crates/turing-economy/src/lib.rs:800-849`) is a hard argmax: it iterates
  `routes`, looks up each route's `yes_price` from `signals` (lines 814-823),
  and keeps whichever has strictly the highest `yes_price` so far (lines
  824-830, ties keep the first-seen route — i.e. τ is implicitly 0 today,
  exactly as the design doc states). `grep -n
  "softmax\|temperature\|boltzmann\|\.exp(\|ucb\|visit_count\|exploration"
  crates/turing-economy/src/lib.rs` → 0 hits, confirming no τ parameter
  exists anywhere in the crate. — **GAP → 见 PART D.3 (G1)**.
- **如何机器检查**: once implemented — fixed-seed property test sweeping
  τ∈{0, 0.5, 1, 2, ∞} against a fixed `(routes, signals)` fixture, asserting
  τ=0 reproduces today's argmax output bit-for-bit (backward compatibility)
  and τ→∞ converges to uniform route selection across repeated draws.

### INV-17 — backup 确定性 (settlement backup is deterministic and tape-replayable)
- **陈述**: `MarketSettled` 回灌先验必须是确定性 PRESERVE tape 事件, 可 replay
  重建。
- **依据**: `RES_ECON_price_as_mcts_core_20260707.md` line 25 ("缺口 3 — 无
  backup: 结算不回灌先验"); F3 (确定性可重建).
- **现在在哪强制**: **未实现 → GAP, confirmed**. `MarketSettled`
  (`crates/turing-economy/src/lib.rs:178-184`) only records
  `result`/`settlement_event_id`/`price_not_truth_ack`; nothing in
  `market_settle_response` (`crates/turing-daemons/src/lib.rs:1627-1750`)
  emits any follow-on event that feeds settlement outcomes back into a prior
  for the *next* round's `MarketRouter::suggest` call — `suggest` takes
  `signals: &[PriceSignal]` purely as a caller-supplied parameter (line 803),
  with no internal state carried between calls (`MarketRouter` is a
  stateless, `Copy` struct, lines 789-792). No backup mechanism exists.
- **如何机器检查**: once implemented — build a tape with N sequential
  markets where market k+1's initial `PriceSignal` is claimed to derive from
  market k's `MarketSettled`; replay the tape from scratch and recompute the
  derived prior; `assert_eq!` against the recorded value (same pattern as
  INV-4).

### INV-18 — Goodhart 屏蔽 (price/τ/reputation formula never leaks via feedback channels)
- **陈述**: τ/价格/声誉公式不经 error message / `failed_predicates` 回传 / tool
  schema 泄漏。
- **依据**: Art III.4 (屏蔽 Goodhart 问题); F4
  (`DEV_PLAN_constitutional_emergence_20260707.md` line 56, "经济评分绝不经
  error message 泄漏").
- **现在在哪强制**: **Trivially holds today, but by absence of the mechanism,
  not by an enforced barrier — treat as GAP for forward-compatibility.**
  Verified the two candidate leak channels that exist today: (1)
  `candidate_decision_response`'s JSON-RPC result
  (`crates/turing-daemons/src/lib.rs:884-903`) returns
  `predicate_report_hash`/`failed_predicates`/`reject_class` — these are
  Boolean-signal (∏p) fields only; no `PriceSignal`/`yes_price`/τ value is
  anywhere in that struct or its construction path (confirmed:
  `MarketRouter`/`PriceSignal`/`BudgetSuggestion` do not appear between lines
  700-905). (2) `market_shadow_suggest_response`
  (`crates/turing-daemons/src/lib.rs:1036-1087`) *does* return `route_id`
  and `market_id` (i.e. which route won) in its RPC result (lines 1070-1071),
  which is a coarse-grained signal ("you were/weren't picked") but not the
  raw price or a τ value (neither field is returned, and τ does not exist
  yet per INV-16). Since no τ/softmax formula exists in code at all today,
  there is nothing to leak — but there is also no `grep`-based CI guard or
  test asserting this property, so the moment INV-16/17 land (adding a real
  τ and a real backup formula), this invariant has **zero enforcement
  in place to catch a regression**. — **GAP → 见 PART D.3** (must add the
  firewall grep/test *before* or *alongside* G1-G3 implementation, not after).
- **如何机器检查**: static grep CI check: no numeric τ/softmax-coefficient
  field may appear in any JSON-RPC response struct reachable from
  `candidate_decision_response`/`market_settle_response`'s `failed_predicates`
  or `reject_class` construction; once τ exists, add a positive test that
  the RPC response for a rejected candidate never contains the τ value or
  raw softmax logits, only the coarse route_id/pass-fail signal.

---

## Summary table (grep-friendly)

| INV | One-line verdict |
|---|---|
| INV-1 | ENFORCED — constructor (68-82) + check_conservation (547-561) |
| INV-2 | ENFORCED — check_conservation (526-614), tested |
| INV-3 | PARTIAL GAP — per-market redemption side OK; mint side has no balance/issuance check (market_mint_response 1361-1458) |
| INV-4 | GAP — no reputation system exists yet; no derive_from_tape guard |
| INV-5 | ENFORCED — assert_k_non_decreasing (301-316), tested (not yet random-seeded property) |
| INV-6 | ENFORCED by construction (non-negative operands + truncating div = floor); no dedicated adversarial test yet |
| INV-7 | GAP — mul/mul_div/ratio use unchecked `*`/`/`, no checked_mul; release-profile wrap risk |
| INV-8 | GAP — no minimum-liquidity floor; MarketLiquidityAdded reserved in registry but unimplemented |
| INV-9 | ENFORCED — registry 15/15 PRESERVE + hardcoded can_move_accepted_head=false (846) |
| INV-10 | ENFORCED — derive_candidate_predicate_checks has no economy identifiers reachable |
| INV-11 | ENFORCED — market_settlement_gate_g_mkt_06 (324-371), wired in market_settle_response |
| INV-12 | ENFORCED — check_self_trade (626-649) |
| INV-13 | ENFORCED with known Sybil limitation (principal_id == agent_id, documented) |
| INV-14 | ENFORCED — check_proposer_conflict (693-722), net-NO semantics |
| INV-15 | GAP (critical) — no difficulty-weighting/reuse-count reputation exists |
| INV-16 | GAP — MarketRouter::suggest is hard argmax, no τ/softmax |
| INV-17 | GAP — no settlement-to-prior backup mechanism |
| INV-18 | GAP (latent) — trivially holds only because nothing to leak yet; no firewall guard for when it lands |
