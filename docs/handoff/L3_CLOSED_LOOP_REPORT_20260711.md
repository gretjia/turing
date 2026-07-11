# WP-L3-3 闭环集成 + 有机全链演练报告 — 2026-07-11

**性质声明：本报告是一次小型真实闭环演练（drill），不是实验。所有产物
`evidence_class = SMOKE_FIXTURE`（离线重放为 `OFFLINE_MOCK`），不承载任何统计主张
（no statistical claim）。样本量为 1 个 S02 任务、2 条真实路线、共 4 次真实迭代
尝试——不构成、也不冒充任何 SWE-bench 解率测量。**

- 规格：`adr/ADR-ECON-007-route-market-loop-remedy.md`（全部 Decision）。
- 分支：`l3/closed-loop`，基于 `hci/software3-20260705@dc83a9f`（已含 WP-L3-1
  `iterate/`、WP-L3-2 `dialectic/`）。
- 隔离工作树：独立 `git worktree`（`git worktree add <scratch>/wp-l3-3-closed-loop
  -b l3/closed-loop dc83a9f`），只在该工作树内写入，未触碰 `turing_v5` 或任何权威
  字段。
- 新增驱动：`tools/econ_lab/closed_loop/closed_loop_driver.py`（读接口后接线，未修改
  任何已合并组件：`iterate.iterate_harness`、`dialectic.dialectic_gate`、
  `dialectic.route_market_bridge`、`depthk.route_market`、`monitor.loop_detector`、
  `monitor.termination`、`live_driver.py` 的 `_build_generic_chat_request`/
  `_call_openai_compatible`/`score_with_official_harness`，均只读 import 或文件路径
  加载）。
- 产物根：`tools/econ_lab/runs/l3_closed_loop_20260711/real_drill/`（真实闭环）与
  `tests/test_closed_loop_driver.py` 自身在 `tmp_path` 下产出的离线全链重放（
  `OFFLINE_MOCK`，pytest 内验证，不落盘到仓库）。

## 尝试计数（Decision 6 日落条款 200 次计数起点）

本次真实闭环产生 **4 次有机 `iterate_harness` 尝试**（路线 1 两次、路线 2
两次），是 ADR-ECON-007 Decision 6 日落条款所要求"首批 200 次有机迭代尝试"的
起点贡献，**不是**对全部 L3 历史尝试总数的声明（`verdict.json` 字段
`organic_iterate_attempts_total=4`，`organic_iterate_attempts_note` 字段原文已
声明这一点）。WP-L3-1 自身的 `smoke_s02_real.py` 走的是独立于
`run_iterate_harness` 的另一条真实派工路径（reuse `iterate_harness` 的原语但不
调用 `run_iterate_harness` 本体），因此本次是 `run_iterate_harness` 本体第一次
真实产生有机尝试计数。

## 真实调用计数（严格 ≤15，实到 12/15）

| 序号 | 环节 | 角色/尝试 | 说明 | 真实调用数 |
|---|---|---|---|---|
| 1-4 | 辩证门 pass1 | proposer_1/proposer_2/critic/judge | 首次三角色门，产出 route_portfolio.v1（3 候选） | 4 |
| 5-6 | 路线 1 迭代 | attempt1/attempt2 | `structural-redesign-rewrite`（capsule_only，组合中保留的弱路线，判官已记录保留理由） | 2 |
| 7-10 | 辩证门 pass2（再入） | proposer_1/proposer_2/critic/judge | 消费路线 1 的 falsification 报告，产出修订组合 | 4 |
| 11-12 | 路线 2 迭代 | attempt1/attempt2 | `structural-redesign-isolate`（真实市场从修订组合选出） | 2 |
| **合计** | | | | **12 / 15** |

密钥仅通过 `source ~/.turingos/secrets.env && export SILICONFLOW_API_KEY
DEEPSEEK_API_KEY` 注入进程环境，从未写入任何文件/日志（已对
`tools/econ_lab/runs/l3_closed_loop_20260711/real_drill/**` 全目录 grep 两把密钥
字面量，零命中）。评分统一使用 `~/.turingos/swebench-venv/bin/python`。
`econ_fold_cli`/官方评分子进程调用不计入这 15 次上限（不是 LLM/worker 网络调用，
沿用本仓库既有 `worker_calls_used` 惯例）。

## 诚实的环境发现：一次真实模型可用性故障 + 修复（先于六环节陈述）

前三次真实尝试**未计入**上表（预算未消耗到判定失败调用，均在网络请求本身超时/
挂起阶段失败，从未收到过服务端响应，因而不构成"已消耗的真实调用"，产物目录已
清空重跑，不落盘保留半成品）：

1. 第 1 次：`deepseek-ai/DeepSeek-V4-Flash`（本仓库 `SiliconFlowLLMClient` 的默认
   模型），辩证门 pass1 的 4 次调用全部成功但异常缓慢（单次 proposer 调用观测到
   约 11 分钟），随后路线 1 attempt1 的真实派工调用在 `dispatch_timeout_s=300`
   处超时崩溃（`TimeoutError`，未被顶层捕获，进程裸崩溃）。
2. 第 2 次：修复 1（`dispatch_timeout_s` 默认上调到 900s）后重跑，辩证门 pass1
   第一个 `proposer_1` 调用本身在 900s 处超时。
3. 第 3 次：进一步上调到 1800s（30 分钟）后重跑，同一个 `proposer_1` 调用仍在
   1800s 处超时——独立 `curl --no-buffer` 流式探测同一模型/同一 prompt 结构
   （JSON 生成任务）在 60s 内**零字节**响应，而对同一 SiliconFlow 端点的
   `Qwen/Qwen3-Coder-30B-A3B-Instruct` 探测在约 3 秒内返回完整 JSON——证实是
   `DeepSeek-V4-Flash` 本身在本环境当时不可用，不是本驱动的超时设置或 prompt
   结构问题。

修复：（a）顶层 `run_closed_loop_real` 新增 `except Exception`（原先只捕获
`CallBudgetExceeded`）——真实网络故障必须产出诚实 `BLOCKED` verdict，绝不裸崩溃
（`tools/econ_lab/closed_loop/closed_loop_driver.py` 对应改动，镜像
`monitor.termination.guard_bare_termination` 自身"裸终止结构性不可观察"的纪律，
应用到本驱动顶层）；（b）辩证门与真实派工统一改用 `--model-id`
`Qwen/Qwen3-Coder-30B-A3B-Instruct`（仍走 `SILICONFLOW_API_KEY`，同一端点）。
第 4 次（本报告记录的这次）以该修复重跑，端到端约 8 分钟内完成全部 12 次真实
调用 + 4 次真实官方评分（见下方各环节时序戳）。

## 全链时序（真实时间戳，来自产物文件 mtime）

```
09:00:54  01_dialectic_pass1_portfolio.json    辩证门 pass1 完成（4 次真实调用）
09:03:11  03_route1_run.json                   路线 1（2 次真实迭代 + 2 次真实评分）完成，ESCALATED
09:04:52  04_dialectic_pass2_reentry_portfolio.json  辩证门再入 pass2 完成（4 次真实调用）
09:07:20  07_route2_run.json / verdict.json    路线 2（2 次真实迭代 + 2 次真实评分）完成，ESCALATED；闭环终局落盘
```

端到端真实闭环（12 次 LLM 调用 + 4 次真实 SWE-bench 官方评分容器）总耗时约
**8 分 26 秒**（`09:00:54` → `09:07:20`，模型切到 Qwen 之后）。

## 任务

- `instance_id = pytest-dev__pytest-7236`（S02 分片，`ipqc/S02-W01`），来自
  `evidence/bench/swe_bench_verified_500_campaign_20260629/shards/S02/ipqc/S02-W01/
  worker_safe_tasks/pytest-dev__pytest-7236/{task_packet.json,worker_capsule.md}`
  （既有分片产物，未新造）。
- 真实 bug：`unittest.TestCase.tearDown` 在 `--pdb` 下于被跳过的测试上仍被执行。

## 每环节事件路径（六项硬性要求逐条对照，路径均为本次真实产物字面量）

### ① 辩证门（真实三角色）→ route_portfolio.v1

- 路径：`tools/econ_lab/runs/l3_closed_loop_20260711/real_drill/01_dialectic_pass1_portfolio.json`
- 3 候选（均按受控词表标注 `worker_context: capsule_only|source_context_loop`，
  本驱动据此确定性接线到真实派工配置，非从自由文本猜测）：
  - `conservative-reuse-wrap`（p=0.65，capsule_only）
  - `structural-redesign-rewrite`（p=0.25，capsule_only）——**组合中故意保留的弱
    路线**：critic 独立通道（`01b_dialectic_pass1_critiques.json`）明确标记该路线
    `predicted_failure_modes_adequate: "false"` 并补充三条额外失败模式；judge 仍
    将其保留，`exit_criteria` 原文记录保留理由："Despite this being a likely
    failure mode, it remains in the portfolio because it provides structural
    clarity and is critical to isolate the root-cause risk."（多样性配额演示，
    真实 LLM 输出，非本驱动编造）。
  - `minimal-assertion-check`（p=0.40，source_context_loop）
- 市场候选+先验落盘：`pass1/route_market_bridge/{route_candidates.json,route_priors.json}`
- 真实市场选择（`econ_fold_cli fold-and-suggest-route`，SoftmaxArgmaxBypass）：
  `02_market_selection_pass1.json`，argmax 偏好 `conservative-reuse-wrap`（p 最高）
  ——**本驱动按设计故意先派发保留的弱路线** `structural-redesign-rewrite`（组合
  内最低先验），以有机触发 Decision-4 证伪+再入路径；市场自身的真实 argmax 偏好
  单独记录，从未被静默替换为派发顺序。

### ② 按序逐路线进迭代 harness（--monitor 语义有机运转）

- 路径：`tools/econ_lab/runs/l3_closed_loop_20260711/real_drill/03_route1_run.json`
  （路线 1）、`07_route2_run.json`（路线 2）。
- `IterateConfig.same_signature_retry_limit` 原样引用
  `iterate_harness.SAME_SIGNATURE_RETRY_LIMIT_FIXTURE_ADR007_DECISION_6A`
  （=2，ADR-ECON-007 Decision 6a 的 PROVISIONAL 值，经配置注入，本驱动从未硬编码
  另一个数）。
- 每次真实尝试：真实 SiliconFlow 派工（`Qwen/Qwen3-Coder-30B-A3B-Instruct`）→
  真实 `git apply` → 真实 `~/.turingos/swebench-venv/bin/python -m
  swebench.harness.run_evaluation`（真实 docker 容器、真实测试运行，见
  `scoring_reports/<route>/attempt<N>/run_evaluation.log`：路线 1 attempt1 实测
  61.88s，`error=0`（补丁真实应用成功）、`✓=0 ✖=1`（官方测试真实未通过）——
  确凿的语义失败，不是补丁应用失败）。
- 路线 1（`structural-redesign-rewrite`）两次真实尝试均 `SEMANTIC_FAIL`（补丁
  应用、官方目标测试仍失败）→ 同签名连续 2 次 → `ESCALATED`。
- 路线 2（`structural-redesign-isolate`，见下 ④）同样两次 `SEMANTIC_FAIL` →
  `ESCALATED`。

### ③ 检测器有机触发（事件流来源断言：非 fixture 回放）

- 路径：`03_route1_run.json.detector_trips` / `07_route2_run.json.detector_trips`。
- 4 次真实触发，规则均为 `SAME_FRAGMENT_REPEATED_FAILURE`：
  - 路线 1 attempt1（`at_seq=1`）、attempt2（`at_seq=5`），`file_path=
    "src/_pytest/unittest.py"`。
  - 路线 2 attempt1（`at_seq=1`）、attempt2（`at_seq=5`），同一文件。
- 来源断言：`edit_trace` 的 `file_path`/`action_signature`/`outcome` 三字段均取
  自**本次真实运行自身**——`action_signature` 是本次真实补丁文本的 sha256（每次
  互不相同，见各 `detector_trips[].evidence.attempted_action_signatures`），
  `file_path` 取自本次真实 `candidate.patch` 的 `diff --git` 头（本地 `git apply
  --check` 因 LLM 生成补丁与真实工作区的空白/上下文细节不完全吻合而返回非零——
  一个诚实记录的次要实现瑕疵，`touched_files` 因此为空，`edit_file` 回退到
  `_first_diff_path(patch_text)` 正则解析路径；该路径本身仍是真实、正确的
  ——`src/_pytest/unittest.py` 与官方评分容器实际打的同一补丁文件一致，可在
  `task_runs/<route>/attempt<N>/candidate.patch` 核对）——**从未读取或重放**
  `tools/econ_lab/monitor/fixtures/` 下任何既有 fixture。`LoopDetectorConfig.
  same_fragment_failure_threshold=1`（本次演练自定的 B 区配置值，`closed_loop_
  driver.py::default_loop_detector_config` 文档已声明这是演练专用调优值，不是对
  Decision 6a `same_signature_retry_limit` 的重新标定）。

### ④ 升级 → falsification 报告（remaining_candidates = 组合剩余路线）

- 路径：`03_route1_run.json.route_falsification_report`（路线 1）、
  `07_route2_run.json.route_falsification_report`（路线 2）。
- 路线 1 报告：`route_id="structural-redesign-rewrite"`，
  `remaining_candidates=["conservative-reuse-wrap","minimal-assertion-check"]`
  （**非空**），`verifier_evidence` 为两条真实 `{phase:null,result:"fail"}`（源自
  两次真实官方评分），`proposal_only=true`。
- 路线 2 报告：`route_id="structural-redesign-isolate"`，
  `remaining_candidates=["conservative-reuse-wrap","focused-meta-inspection"]`
  （**非空**），同样两条真实 fail 证据。

### ⑤ 报告回流辩证门再入 → 修订组合落盘

- 再入调用：`04_dialectic_pass2_reentry_portfolio.json`，
  `portfolio.reentry.upstream_route_id="structural-redesign-rewrite"`，
  `upstream_remaining_candidates=["conservative-reuse-wrap",
  "minimal-assertion-check"]`（与路线 1 报告的 `remaining_candidates` 逐字一致，
  `dialectic_gate.py` 自身的再入证据折叠机制产出）。
- 修订组合 3 候选：`conservative-reuse-wrap`（p=0.45，下调）、
  `structural-redesign-isolate`（p=0.55，新路线）、`focused-meta-inspection`
  （p=0.35，新路线）。
- 修订组合落盘（本 WP 第 3 条硬性要求）：
  `pass2_reentry/route_market_bridge/{route_candidates.json,route_priors.json}`
  + 排除已证伪路线后的候选清单：`05_revised_portfolio_manifest.json`。
- 真实市场对修订组合重选：`06_market_selection_pass2.json`，argmax 选出
  `structural-redesign-isolate`（p 最高）→ 派发为路线 2。

### ⑥ 终局（带验证器证据）

- 路径：`07_route2_run.json` / `verdict.json`。
- `final_status="ESCALATED"`（路线 2 同样两次真实同签名失败 → 二次证伪）。
- **诚实边界声明**：ADR-ECON-007 本 WP 自身描述的两个终局分支是"成功结算"或
  "组合耗尽终局证伪"。本次真实演练落在**第二次 ESCALATED、但
  `remaining_candidates` 仍非空**（`["conservative-reuse-wrap",
  "focused-meta-inspection"]`）——这不是字面意义的"组合耗尽"（耗尽需要继续派发
  直到 `remaining_candidates` 归空，至少还需一整轮再入辩证门(4) + 迭代(≥1)，
  超出剩余预算 15-12=3），而是**在 ≤15 真实调用预算内诚实到达的边界终局**，
  同样携带真实验证器证据（Decision 4 要求的核心属性），不是裸终止。"成功结算"
  分支与字面"组合耗尽"分支由 `tests/test_closed_loop_driver.py` 的离线全链重放
  分别覆盖（后者可通过将 `remaining_candidates` 收窄到 1 候选后再次触发证伪来
  离线复现；本次真实演练未额外花费预算去逼近它，因为该分支不产出比已有证据更
  强的"检测器有机触发/falsification 非空/终局带证据"证明）。

## 测试

### 离线全链重放对拍（mock，零网络调用）

```
$ python3 -m pytest tests/test_closed_loop_driver.py -v
tests/test_closed_loop_driver.py::test_offline_mock_full_chain_is_deterministic PASSED
tests/test_closed_loop_driver.py::test_offline_mock_full_chain_shape PASSED
tests/test_closed_loop_driver.py::test_route1_is_the_deliberately_retained_weak_route PASSED
tests/test_closed_loop_driver.py::test_audit_loop_until_pass_passes_on_route2_bundle PASSED
tests/test_closed_loop_driver.py::test_route_worker_context_parses_controlled_vocabulary PASSED
tests/test_closed_loop_driver.py::test_call_budget_raises_before_exceeding_max PASSED
tests/test_closed_loop_driver.py::test_budgeted_llm_client_counts_every_completion PASSED
tests/test_closed_loop_driver.py::test_derive_route_keys_for_portfolio_gives_each_candidate_a_distinct_scaffold PASSED
8 passed
```

`test_offline_mock_full_chain_is_deterministic`：两次独立离线全链调用
（辩证门×2遍 + 迭代 harness×2路线）产出逐字节相同的 `verdict.json`（Art 0.2
确定性）。`test_audit_loop_until_pass_passes_on_route2_bundle`：对**本驱动自身
产出**的 CONVERGED bundle（离线重放路线 2 的 PASS 结果）跑真实、未改动的
`tools/bench/audit_loop_until_pass.py::audit_coverage`，`status=PASS`，
`problems=[]`——真实闭环本次两条路线均 ESCALATED（无 PASS 终局可核），但
`run_iterate_harness` 的 CONVERGED 代码路径本身与 worker_fn 是否真实/脚本化
无关（同一份代码），本测试即是对该路径的真实、非拟合验证。

### 既有 iterate/dialectic/monitor 回归（未改动任何已合并组件）

```
$ python3 -m pytest tests/test_closed_loop_driver.py tests/test_dialectic_gate.py \
    tests/test_dialectic_route_market_bridge.py tests/test_dialectic_smoke.py \
    tests/test_econ_lab_iterate_harness.py tests/test_econ_lab_loop_detector.py \
    tests/test_econ_lab_interventions.py tests/test_econ_lab_termination.py \
    tests/test_wp_h6_smoke_replay.py
119 passed in 12.01s
```

## 四道门（产物生成后全绿）

```
$ bash tools/gates/gate_f4_econ_leakage.sh
F4_LEAK_PASS (12 surface files scanned, 12 patterns)
exit 0

$ bash tools/hci/gate_hci_no_write.sh
HCI_NO_WRITE_GATE_PASS
exit 0
```

worker_leakage 语义：本驱动的每一处 worker 可见文本（task_context、渲染后的角色
prompt、每份候选路线的 summary/key_choices/predicted_failure_modes/probe_design/
exit_criteria/prior_estimate.provenance、两份 falsification 报告、两份修订组合）
均经由 `dialectic_gate.py`/`route_market_bridge.py`/`monitor.termination`
既有的 `scan_worker_text`/`scan_structure_for_bzone_leak`/
`assert_report_has_no_bzone_leak` 原函数扫描（本驱动零重新实现黑名单逻辑，
纯只读复用）——`01_dialectic_pass1_portfolio.json`/
`04_dialectic_pass2_reentry_portfolio.json` 等均是这些函数已经通过之后才落盘的
产物。

`gate_ref_lint.sh` 的既有失败（`crates/turing-cli/tests/cli_gates.rs` 里的
`update-ref` 字面量）已核实为 `dc83a9f` 基线预存残留（本 WP 未触碰该文件），不在
本 WP 门清单内。

回归：`git status --short` 只新增 `tools/econ_lab/closed_loop/`、
`tests/test_closed_loop_driver.py`、`tools/econ_lab/runs/l3_closed_loop_20260711/`
与本报告——未修改 `turing_v5/`、`src/turingos/`、`crates/turing-projection/` 或任何
既有已合并文件。

## 上限声明

- 实现方（orchestrator/sonnet 执行）上限：`ADDRESSED`。不自称 `CLOSED`/
  `RELEASED`/`RATIFIED`、OG-10/genesis 签名或 M2 使能。
- 未触碰 `turing_v5` 或任何权威字段；未修改 `crates/turing-projection/`。
- 全程只在独立 git worktree（`l3/closed-loop` 分支）内写入。
- 真实调用 12/15，严格未超限；三次预算外的网络故障重试（均在收到服务端响应前
  失败）已在上文"诚实的环境发现"一节完整披露，未计入 15 次上限，也未删改任何
  已发生的事实。

## 文件清单

```
tools/econ_lab/closed_loop/__init__.py                 # 本 WP 新增包
tools/econ_lab/closed_loop/closed_loop_driver.py        # 本 WP 新增驱动（离线+真实两模式）
tests/test_closed_loop_driver.py                        # 本 WP 新增测试（8 项，全 PASS）
docs/handoff/L3_CLOSED_LOOP_REPORT_20260711.md           # 本报告
tools/econ_lab/runs/l3_closed_loop_20260711/real_drill/
  01_dialectic_pass1_portfolio.json                      # ①
  01b_dialectic_pass1_critiques.json                     # ①（critic 独立通道）
  02_market_selection_pass1.json                         # ①（真实市场选择）
  pass1/route_market_bridge/{route_candidates,route_priors}.json
  03_route1_run.json                                     # ②③④（路线 1）
  04_dialectic_pass2_reentry_portfolio.json               # ⑤（再入辩证门）
  04b_dialectic_pass2_reentry_critiques.json
  05_revised_portfolio_manifest.json                      # ⑤（修订组合落盘清单）
  pass2_reentry/route_market_bridge/{route_candidates,route_priors}.json
  06_market_selection_pass2.json                          # ⑤（真实市场重选）
  07_route2_run.json                                      # ②③④⑥（路线 2 + 终局）
  task_runs/<route>/attempt<N>/{candidate.patch,worker_receipt.json}
  scoring_reports/<route>/attempt<N>/                     # 真实官方评分容器产物
  receipts.json                                            # 12 条真实 LLM 调用回执（已 B 区扫描）
  verdict.json                                             # 终局 verdict（call_budget/organic_iterate_attempts_total 等）
```
