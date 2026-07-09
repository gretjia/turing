# ADR-ECON-005 — depth-k 分层 scaffold 市场（草案）

| 字段 | 值 |
|---|---|
| **ADR** | ADR-ECON-005 |
| **title** | Layered (depth-k) scaffold markets: stage keys, seed extension, credit v0 |
| **status** | **proposed** |
| **date** | 2026-07-09 |
| **authors** | CAPSULE B implementer (Grok build session) |
| **decision-makers** | orchestrator / owner（**不得**由实现者 self-accept） |
| **supersedes** | — |
| **related** | ADR-ECON-003 (Decisions 1/4/6), design doc §1.4 / §5, CAPSULE B dispatch 2026-07-09 |

---

## Context

深度-1 路由把 scaffold 当作原子动作：市场键 = `(domain_bucket, scaffold_id)`，12 路由（3 arm × 4 lineage）无共享子决策。设计文档 §1.4 明确：只有 depth-k（scaffold = 多步可组合决策，内部节点跨 scaffold 共享统计）且在未见 class 上观测到正迁移时，才允许谈「学到函数」。

CAPSULE B 物化最小 depth-2 基底：把 armA/B/C 语义正交为三 stage，分层市场键共享统计节点。本 ADR 冻结实现已采用的契约，供正式 E-transfer 实验前 accepted。

## Decision (proposed)

### D1 — scaffold_descriptor.v2 阶段分解（v0 冻结）

完整 scaffold 是三阶段顺序选择，而非原子 arm 标签：

| stage | 名称 | options (v0) |
|---|---|---|
| 1 | `context` | `minimal`, `source_context` |
| 2 | `repair` | `single_shot`, `loop` |
| 3 | `verify` | `none`, `self_check` |

正交近似：

- armA ≈ (minimal, single_shot, none)
- armB ≈ (source_context, loop, none)
- armC-like ≈ (source_context, loop, self_check)

**演进纪律（同 ADR-ECON-003 Decision 1）:** 阶段名/option 空间变更必须新 schema 版本 + 本 ADR 修订；禁隐式漂移。

### D2 — 分层市场键

每 stage 独立 fold 键：

```
StageRoutingKey = (domain_bucket, stage_name, option)
```

**Wire 编码（兼容既有 tape）:**

```
stage_option_id = "stage:sha256:" + hex(SHA256(JCS({
  "schema": "stage_option.v1",
  "stage_name": stage_name,
  "option": option
})))
```

折入既有 `RoutingKey = (domain_bucket, scaffold_id)` 时，`scaffold_id := stage_option_id`。  
前缀 `stage:` 与 `scaffold:` 命名空间隔离，永不碰撞。

一次任务的路由 = 3 次顺序 stage 选择（每次对该 stage 的 option 集做 Decision 4 选择）× lineage 选择（lineage 仍用 Decision 1 的 `scaffold:` 描述子路径）。

### D3 — 选择种子扩展（B1 先例版本化）

**既有路径（不变）:** ADR-ECON-003 Decision 4：

```
u64 = LE(SHA256("routing-select.v1" ‖ price_signal_hash ‖ pput_prior_hash
              ‖ join(sorted(route_ids), "\x00") ‖ trigger_event_hash)[0..8])
```

**Stage 路径（加性）:**

```
u64 = LE(SHA256("routing-select.v1" ‖ price_signal_hash ‖ pput_prior_hash
              ‖ join(sorted(route_ids), "\x00") ‖ trigger_event_hash
              ‖ stage_name)[0..8])
```

- 公共 API：`MarketRouter::suggest` 保持原语义；新增 `suggest_with_stage(..., stage_name)`。  
- CLI：新子命令 `derive-stage-keys` / `fold-and-suggest-stage`（**不**改 `fold-and-suggest` v2 字节）。  
- 旧 schema 请求输出与基线逐字节不变（对拍测试锁死）。

### D4 — 信用分配 v0（诚实天花板）

任务完成后，独立验证器（或 live_split verify 侧）给出裁决 `v`：

- **v0 规则:** 将该任务路径上使用的 **三个** stage 节点各写入一次 `RoutingPriorUpdated(verdict=v)`。  
- **标签（强制出现在驱动产物）:** `"v0_equal_share_not_causal"` / 「v0 均摊,非因果归因」。  
- **已知缺陷:** 非因果；错误 stage 同样更新。这是能力天花板标注，不是实现 bug。  
- **未来 v1（非本 ADR 范围）:** 反事实 / leave-one-stage-out / 梯度式信用——需独立 ADR 修订。

### D5 — 与 authority / Art 0.1 的非干涉

`BudgetSuggestion` 三权威字段保持：

- `emits_authorization = false`
- `can_move_accepted_head = false`
- `head_effect = "PRESERVE"`

分层选择只改「选谁」，不推进 `accepted_head`。`tests/hunt_authority.rs` 继续锁死。

### D6 — 与 ADR-ECON-003 的关系

| ADR-ECON-003 | 本 ADR |
|---|---|
| Decision 1 scaffold_id/domain_bucket | 保留；stage 用并行 schema + 前缀隔离 |
| Decision 4 种子 | 加性 `‖ stage_name`；旧路径不动 |
| Decision 6 Q_eff / 折 | 复用 NodeState；键空间扩展 |
| Decision 2 独立验证器 | 回灌仍仅 verify 侧；credit v0 复制到三节点 |

## Consequences

### Positive

- 跨 scaffold 共享 stage 统计节点 → E-transfer 实验的最小机制成立。  
- 旧 12 路由实验（Stage A/B′/P3-E3）路径隔离，无回归风险。  
- 版本化纪律与 B1（fold-and-suggest v1→v2）一致。

### Negative / risks

- 结算饥饿（节点数↑）。  
- credit v0 偏差。  
- worker 执行层对 repair/verify 的语义仍是 v0 近似（市场深度 > 执行深度）。

### Out of scope (explicit)

- 正式 E-transfer 预注册与显著性检验。  
- credit assignment v1。  
- 将 depth-k 标为 FUGU / 「已学到函数」。  
- self-claim CLOSED / RELEASED / RATIFIED。

## Acceptance criteria (when promoted from proposed)

1. 本文件 status → accepted 仅由 decision-makers 变更。  
2. 既有 `cargo test -p turing-economy` + gate_f4 双向仍绿。  
3. 旧 `fold-and-suggest` v2 对拍测试仍通过。  
4. 跨 scaffold 共享节点与种子域分隔有自动化测试。

## Implementation pointers (CAPSULE B)

- `crates/turing-economy/src/routing_fold.rs` — `stage_option_id`, `ScaffoldDescriptorV2`, stage walk  
- `crates/turing-economy/src/lib.rs` — `suggest_with_stage`, seed `‖ stage_name`  
- `crates/turing-economy/src/bin/econ_fold_cli.rs` — `derive-stage-keys`, `fold-and-suggest-stage`  
- `tools/econ_lab/depthk/depth_driver.py` — 分层选择 + 回灌 + 冒烟  
- 可行性备忘：`docs/handoff/GROK_CAPSULE_B_DEPTHK_MEMO_20260709.md`
