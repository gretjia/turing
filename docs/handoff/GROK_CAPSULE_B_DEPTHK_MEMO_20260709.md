# CAPSULE B — depth-k 可行性备忘 (2026-07-09)

**状态上限:** ADDRESSED（实现者交付；非 CLOSED/RELEASED/RATIFIED）  
**性质:** 探索性构建（feasibility build）——**禁止任何显著性主张**  
**基线:** `0ebd7ad` · 分支 `depthk/grok-20260709` · worktree `work/grok_depthk`  
**派发:** `CAPSULE_B_DEPTHK_grok_20260709.md` sha `004f2f681c3138b7020718098184621cdc1be536d8326ac99ef8ccf8b71fe7b6`

---

## 0. 交付摘要

| 交付物 | 落位 |
|---|---|
| Rust 加性扩展（scaffold_descriptor.v2 阶段键 + stage fold/suggest） | `crates/turing-economy/src/routing_fold.rs`、`lib.rs::suggest_with_stage`、`econ_fold_cli` 新子命令 |
| depth_driver | `tools/econ_lab/depthk/depth_driver.py` |
| 离线测试 | `tests/test_depthk_driver.py` + `econ_fold_cli_cross_check` 增补 |
| 真实冒烟 | `tools/econ_lab/runs/depthk_smoke_20260709/` |
| 本备忘 | `docs/handoff/GROK_CAPSULE_B_DEPTHK_MEMO_20260709.md` |
| ADR-ECON-005 草案 | `docs/handoff/ADR-ECON-005-depthk-layered-market-DRAFT.md`（status: **proposed**） |
| HANDOFF | worktree 根 `HANDOFF_CAPSULE_B.json` |

**核心机制（已物化）:**

1. **阶段正交化（v0 冻结）:**  
   - stage-1 `context` ∈ {minimal, source_context}  
   - stage-2 `repair` ∈ {single_shot, loop}  
   - stage-3 `verify` ∈ {none, self_check}  
   - 组合 2×2×2=8；dispatch 映射 armA/B/C 为 worker 兼容层，**市场键不在 arm 上**。
2. **分层市场键:** `(domain_bucket, stage_name, option)`，wire 编码为  
   `scaffold_id = stage:sha256:JCS(stage_option.v1)`，复用既有 (Q,N,P) 折 tape。
3. **种子域分隔:** Decision 4 派生式追加 `‖ stage_name`（仅 `suggest_with_stage` / `fold-and-suggest-stage`）；旧 12 路由 `suggest` 路径逐字节不变。
4. **信用分配 v0:** verify 裁决同时回灌该任务用到的三个 stage 节点——**均摊，非因果归因**（已知天花板）。

---

## 1. E-transfer 实验草案（供 orchestrator 钉死）

**目标（设计 §3 主张 6）:** 仅 depth-k 允许谈「学到函数」——必须在未见 query class 上观测到正迁移。

### 1.1 协议草图（held-out family）

| 阶段 | 动作 |
|---|---|
| **Train families X** | 在族集 X 上跑 stage 级活价格（三 stage 顺序选择 + lineage），积累 stage 节点 Q |
| **Held-out families Y** | 冻结 train 得到的 stage 后验 P 注入；在 Y 上对比： |
| **Treatment** | depth-2 分层路由（共享 stage 节点 Q） |
| **Baseline A** | 原子路由 Q（现行 12 路由 arm×lineage，无 stage 共享） |
| **Baseline B（可选）** | 均匀 / 静态 oracle |
| **主端点（建议）** | Y 上 settled pass rate 差值；次级：rank-inversion 计数、共享节点 visit 分布 |
| **推翻观测** | Treatment 相对 Baseline A 零/负迁移 ⇒ 仍是查找表，不得称「学到函数」 |

**钉死权在 orchestrator：** α、n、族划分 X/Y、是否配对 McNemar、地板、预注册脚本 sha——本 capsule **不**冻结这些判据（探索性构建边界）。

### 1.2 建议族划分（示例，非冻结）

可复用 P3-E3 的 PHASE1/PHASE2 族切分作为 held-out 原型：

- X = {astropy, django, pydata, pytest-dev}
- Y = {matplotlib, scikit-learn, sphinx-doc, sympy}

或按 S02 内自然族做 leave-one-family-out（LOFO）——LOFO 更贵但更贴「未见 class」。

---

## 2. 诚实成本估计（草算，非功效分析终稿）

记号：

- \(F_X, F_Y\)：train / held-out 族任务数  
- \(C\)：每题真实 worker 调用数（depth-2 全链 = **1** worker + 1 评分；选择本身是本地 CLI）  
- 臂数 \(A\)：Treatment + BaselineA（+ 可选 BaselineB）  

| 场景 | 题量级 | 臂 | 调用量级 \(n \cdot A \cdot C\) | 备注 |
|---|---|---|---|---|
| 冒烟（本 capsule） | 2 | 1 | **2**（≤8 硬顶） | 仅通路证明 |
| 最小方向性 | \(F_X{=}20, F_Y{=}20\) | 2 | ≈80 | 不足以显著性 |
| 可注册最小 | \(F_X{=}50, F_Y{=}50\) | 2 | ≈200 | 需正式功效分析 |
| LOFO 全 8 族 | ~50×8 折 | 2 | 量级 \(10^3\) | 昂贵；应先做 2 折试点 |

**结算饥饿风险（见 §3）:** stage 空间 6 节点 × 多 domain_bucket，若 N 稀疏则 Q 几乎等于先验——迁移实验可能「看起来活」但信息量不足。建议预注册 **每 stage 节点最小 N 地板**（例如 N≥5 才进入 readout），否则标 `STARVED` 不判读。

---

## 3. 风险清单

| # | 风险 | 影响 | 缓解（建议，非本包义务） |
|---|---|---|---|
| R1 | **信用分配 v0 均摊** | 错误 stage 也吃到成功/失败，污染 Q | 后续 credit 因果归因（leave-one-stage-out / 反事实）入 ADR 修订 |
| R2 | **stage 空间扩大后的结算饥饿** | 6 节点 × buckets，visit 被摊薄 | N 地板；或先只启用 2 stage（context+repair）做 E-transfer 试点 |
| R3 | **与 Phase 3 E 路径关系** | Phase 3 规格是参与者学习主链；depth-k 是近亲转向预案 | 勿把 P3-E3 显著性外推到 depth-k；E-transfer 独立预注册 |
| R4 | **dispatch arm 近似** | armC 与 armB worker 内容在 live_driver 上本就接近（已知 gap） | verify 轴可能弱辨识；E-transfer 前应用真实 self_check 语义加固 |
| R5 | **Docker/API 共享** | 与 CAPSULE A 并行时 daemon 争用 | 评分 `--max_workers 1`；总调用预算隔离 |
| R6 | **显著性诱惑** | 冒烟 pass/fail 被误读为结果 | 产物与本备忘显式 `significance_claims: NONE` |

---

## 4. ADR-ECON-005 草案指针

完整草案：`docs/handoff/ADR-ECON-005-depthk-layered-market-DRAFT.md`

- **status:** `proposed`  
- **decision-makers:** orchestrator / owner（本实现者 **不得** self-accept）  
- 覆盖：分层键、种子扩展、信用分配 v0、与 ADR-ECON-003 Decision 1/4/6 的兼容与版本化纪律  

---

## 5. 实现边界与诚实缺口

1. **repair=loop 的 worker 语义**仍映射到现有 arm 描述子；真实多轮 repair 循环未新建——depth-2 的「决策深度」在**市场层**已成立，在**执行层**仍是 v0 近似。  
2. **lineage 选择**走既有 `fold-and-suggest` v2（无 stage 后缀），与 stage 选择正交。  
3. **A 领地零改动：** `live_driver.py` / `run_*.sh` / `analysis/stage_*` 未修改（SHIP GATE 对拍）。  
4. **authority 三字段**未触碰：`emits_authorization=false` / `can_move_accepted_head=false` / `head_effect=PRESERVE`。

---

## 6. 给 orchestrator 的下一步建议（非自动执行）

1. 审阅 ADR-ECON-005 proposed → 决定是否 accepted。  
2. 设计正式 E-transfer 预注册（本备忘 §1 仅草案）。  
3. 评估是否需要 credit assignment v1 后再开 held-out 实验。  
4. 合并策略：B 的 Rust 加性 + `depthk/` 与 A 的 `live_driver` 扩展无文件冲突，可并行审后合入。
