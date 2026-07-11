# WP-H6 CAPSULE H 端到端集成冒烟报告 — 2026-07-11

**性质声明:本报告是一次小型真实演练(smoke),不是实验。所有产物
`evidence_class = SMOKE_FIXTURE`,不承载任何统计主张(no statistical claim)。**

- 规格来源:`adr/ADR-ECON-007-route-market-loop-remedy.md`(全部 Decision)。
- 分支:`h6/integration-smoke`,基于 `hci/software3-20260705@68a8e3f`(已含 h1..h5 全部合并)。
- 隔离工作树:独立 `git worktree`,只在该工作树内写入,未触碰权威字段 /
  `turing_v5`。
- 产物根目录:`tools/econ_lab/runs/h6_smoke_20260711/`。
- 驱动脚本(本 WP 新增,读接口后接线,未修改任何已合并组件):
  `tools/econ_lab/wp_h6_integration_smoke.py`。
- 离线重放测试(新增):`tests/test_wp_h6_smoke_replay.py`(3 项,全 PASS)。

## 真实 worker 调用计数(严格 ≤10)

| 阶段 | 说明 | 真实调用数 |
|---|---|---|
| armA 主车道(2 个 S02 任务,`--monitor`) | `django__django-11119`(deepseek)、`django__django-11133`(qwen,市场按 Q 反馈自动切换的真实血统) | 2 |
| armA 探针 3 | `django__django-11141`(deepseek) | 1 |
| armA 探针 4 | `sphinx-doc__sphinx-7590`(deepseek,跨仓库多样性探针) | 1 |
| armB 正常路线车道 | `django__django-11138`(deepseek) | 1 |
| **合计** | | **5 / 10** |

密钥仅通过 `source ~/.turingos/secrets.env && export SILICONFLOW_API_KEY
DEEPSEEK_API_KEY` 注入进程环境,从未写入任何文件/日志(可在
`tools/econ_lab/runs/h6_smoke_20260711/**` 全目录 grep 验证零命中)。评分统一使用
`~/.turingos/swebench-venv/bin/python`。

环境说明(与本 WP 无关的预先存在问题,已定位并绕过,未修改任何全局配置):全局
`turing` CLI 的 editable-install 指向一个不相关项目目录
(`/home/zephryj/projects/turingoslite/...`),导致 `src/turingos/codec.py` 的
`canonical_bytes()` 默认走不通。`codec.py` 本身已预留 `TURING_JCS_BIN` 环境变量
覆盖点;本仓库自带 `crates/turing-cli`(bin `turing`),编译后通过
`export TURING_JCS_BIN=<本仓库 target/debug/turing>` 指向本仓库自己的二进制即可,
零源码改动。

## 诚实的经验发现(先于六环节陈述,避免误导)

本次 5 次真实 armA/armB 派工(源上下文禁用的坏路线 x4、含源上下文的正常路线
x1)**全部**落在真实 SWE-bench 官方评分线束跑到完成、给出确定性 FAIL
裁决(`harness_error_reason=patch_apply_failed`)的分支 —— 即**都携带了真实验证器
证据**(哪怕结果是 FAIL)。WP-H1 `loop_detector.py` 在真实数据桥接下**唯一可达**的
规则是 `RULE_TERMINATION_WITHOUT_VERIFIER_EVIDENCE`(规则 1-3 需要逐编辑轨迹,
`events_from_real_settlement_checkpoint` 结构性地从不合成 `edit` 事件 ——
`loop_detector.py` 模块 docstring 自己承认的既有 gap);而"验证器判了 FAIL"本身
就是合法证据,不是"裸终止无证据",因此正确地**没有**在这 5 次真实派工上触发
——这本身是检测器语义正确性的证据,不是本冒烟的失败。

为了仍然在预算内端到端演示规则 4 的真实触发路径(①②③),第 1 步额外
**重放**了 WP-H1 自己已建立、已合并、真实存在的历史 fixture
(`tools/econ_lab/monitor/fixtures/real_settlement_pytest_dev_pytest_5787_tau_0p5.json`
—— `pytest-dev__pytest-5787::armA::deepseek` 的一次真实历史派工,worker 记账为
`ERROR`,`scoring_result.status=SKIPPED_NO_PATCH`,真实无证据裸终止),调用与
`live_driver.py --monitor` 钩子内部完全相同的生产函数
(`events_from_real_settlement_checkpoint` → `detect` → `build_diagnostic` →
`execute_rollback`)。这不是新造数据 —— 是复用 WP-H1 自己已经确立的经验证明物。

本会话自己的 5 次真实派工的"未触发"结果同样作为证据存档
(`detector/00_own_session_dispatches_no_trip.json`),两组证据互不混淆。

## 六环节证据

### ① 检测器在坏路线上触发

- 证据:`tools/econ_lab/runs/h6_smoke_20260711/detector/01_detector_trip.json`
- 来源:对上述真实 fixture 的重放,`rule_id=TERMINATION_WITHOUT_VERIFIER_EVIDENCE`,
  `at_seq=3`,`evidence={fact_class: BARE_TERMINATION, phase: dispatch,
  reason_class: ERROR}`(纯事实,无 B 区量)。

### ② 诊断消息注入(存档 + 无 B 区量断言)

- 证据:`tools/econ_lab/runs/h6_smoke_20260711/detector/02_diagnostic_injection.json`
- 内容:`Diagnostic.text` = "Termination without verifier evidence: the trajectory
  ended (reason: ERROR) in phase 'dispatch' without any prior verification result.
  A termination must carry verifier evidence; do not end without it." —— 与
  `live_driver.py::dispatch_via_siliconflow` 真实会预置到下一次派工 capsule 的
  `## Prior-step diagnostic` 区块文本逐字相同(同一生产函数产出)。
- 断言:`build_diagnostic` 内部三层校验(`assert_decision3_legal` /
  `assert_no_bzone_terms_in_text` / `assert_no_unexplained_numbers_in_text`)已通过
  (否则函数会抛 `InterventionError`,不会返回);本冒烟驱动脚本额外**冗余重跑**
  同三个断言并记录 `"decision3_legal_reassert": "PASS"`。

### ③ TrajectoryRolledBack PRESERVE 事件

- 证据:`tools/econ_lab/runs/h6_smoke_20260711/detector/03_trajectory_rolled_back.json`
- `event_type=TrajectoryRolledBack`,`head_effect=PRESERVE`,四字段齐全
  (`fork_point_event_hash`/`reason_class`/`detector_rule_id`/`diagnostic_digest`),
  `event_hash` 为规范 JSON→SHA256。工作区正确重置到分叉点(`new_workspace_length=1`),
  tape 仅追加(`new_tape_length=5`,历史完整保留,回滚本身可重放)。

### ④ RouteFuseTripped → 暂停掩码(掩码前后候选集对比)

- 证据:`tools/econ_lab/runs/h6_smoke_20260711/route_market/04_route_pause_mask.json`
- 真实子进程调用 `target/debug/econ_fold_cli`:
  `build-route-fuse-tripped`(`detector_rule_id`/`diagnostic_digest` 取自①②的真实
  重放输出)→ 两次 `fold-and-suggest-route`(掩码前 `committed_routing_events=[]`,
  掩码后 `committed_routing_events=[fuse_trip_event]`)。
- route key 真实来源:`django/django` domain_bucket +
  `armA::deepseek`/`armB::deepseek` 的真实 `scaffold_id`(与本会话自己的真实 armA/
  armB 派工用的是同一把 key,命令字面量见下"路线键"一节)。
- 掩码前:候选集 = {armA_bad_route, armB_normal_route},armA(高 P=0.9)胜出。
- 掩码后:`paused_route_ids=["armA_bad_route"]`,armA 退出候选集,armB 胜出。
- Q 未被熔断触碰:两次调用都没有提交任何 `RoutingPriorUpdated` 事件,
  `node_states` 两侧一致为空 —— 熔断只窄化候选集,从不写 Q(Decision 2 核心属性,
  也是 `crates/turing-economy/src/route_pause_mask.rs` 自带单测
  `filter_paused_candidates_only_narrows_the_candidate_list_never_touches_q` 已经
  钉死的属性,本冒烟只是在真实候选数据上复核它)。

### ⑤ 路线切换到正常路线的选择记录

- 证据:`tools/econ_lab/runs/h6_smoke_20260711/route_market/05_route_reselection.json`
- `before_mask_chosen_route = "armA_bad_route"`,
  `after_mask_chosen_route = "armB_normal_route"` —— 真实 `econ_fold_cli` 二进制的
  `suggest_with_stage` 选择输出,不是手工构造。

### ⑥ 终局:RouteFalsified(带真实验证器证据)

- 证据:`tools/econ_lab/runs/h6_smoke_20260711/termination/06_termination.json`
- 走的是 `monitor.termination.terminate_falsified`(WP-H3,Decision 4 的"放弃"路径,
  始终合法)。`status=FALSIFIED`(本会话 5 次真实派工全部 FAIL,无一 pass,因此没有
  `terminate_accepted` 的合法路径 —— 如实报告,不伪造 accept)。
- `verifier_evidence`:5 条真实 `{phase: dispatch, result: fail}`,逐一来自本会话
  armA x4 + armB x1 的真实 `live_split_verdict.accept_verdict`。
- `attempts`:4 条真实 armA 派工事实(`route_id` + `harness_error_reason`,均为
  `patch_apply_failed`,无一 B 区量)。
- `detector_events`:①的真实重放触发。
- `remaining_candidates=["armB_normal_route"]`。
- `report.proposal_only=true`(`build_route_falsification_report` 自校验通过才能
  构造出这个对象,否则会抛 `RouteFalsificationError`)。

## 路线键(真实派生,非编造)

```
$ target/debug/econ_fold_cli derive-keys <<< '{"schema":"econ_fold_cli.derive_keys.request.v1","task_family":"django/django","scaffold_descriptors":[
  {"label":"armA::deepseek","decomposition_kind":"single_shot_capsule_repair","toolchain":["deepseek"],"team_spec":"solo_worker_capsule_only","verify_loop":"swebench_official_harness_v1"},
  {"label":"armB::deepseek","decomposition_kind":"source_context_loop_repair","toolchain":["deepseek"],"team_spec":"solo_worker_with_source_context","verify_loop":"swebench_official_harness_v1"}
]}'
```
→ `domain_bucket = "django/django"`,
`armA::deepseek → scaffold:sha256:2b7dd79d70ebba84a1517a9801acd2a74ed7a12d599e84767e4277e1a72b1faf`,
`armB::deepseek → scaffold:sha256:fd3a4aa896d508dd2cf46e51a4a04cb89f4c1f44878b4956582f234dfcb70d08`
(命令、输入、输出均为本次真实执行的字面量,非虚构)。

## 事件流确定性(离线重放)

- 证据:`tools/econ_lab/runs/h6_smoke_20260711/replay/replay_determinism.json`
- 对 fixture 输入两次独立调用 `events_from_real_settlement_checkpoint` →
  `detect` → `build_diagnostic` → `execute_rollback` 全链条,完整结果字典逐字节
  相同(`run1_sha256 == run2_sha256`)。
- 固化为可重复运行的 pytest:`tests/test_wp_h6_smoke_replay.py`(3 项,PASS)。

```
$ python3 -m pytest tests/test_wp_h6_smoke_replay.py -v
tests/test_wp_h6_smoke_replay.py::test_real_fixture_still_trips_the_detector PASSED
tests/test_wp_h6_smoke_replay.py::test_replay_is_byte_identical_across_two_independent_runs PASSED
tests/test_wp_h6_smoke_replay.py::test_diagnostic_never_carries_a_bzone_quantity PASSED
3 passed in 0.03s
```

## 回归验证(未改动任何已合并组件,只新增)

```
$ python3 -m pytest tests/test_econ_lab_loop_detector.py tests/test_econ_lab_interventions.py \
    tests/test_econ_lab_termination.py tests/test_live_driver_monitor_hook.py \
    tests/test_live_driver_termination_hook.py -q
....................................................................  [100%]

$ cargo test -p turing-economy
... 全部 crate 测试(包含 route_pause_mask 10 项单测)0 failed
```

## gate_f4(泄漏门,产物生成后仍 PASS)

```
$ bash tools/gates/gate_f4_econ_leakage.sh
F4_LEAK_PASS (12 surface files scanned, 12 patterns)
```
证据落盘:`tools/econ_lab/runs/h6_smoke_20260711/gate_f4/gate_f4_post_artifacts.txt`
(产物全部生成之后重新运行,exit 0;文件后缀特意用 `.txt` 而非 `.log` ——
仓库根 `.gitignore` 有全局 `*.log` 规则,`.log` 后缀的证据不会被 git 追踪)。

## 上限声明

- 实现方(orchestrator/sonnet 执行)上限:`ADDRESSED`。不自称 `CLOSED`/
  `RELEASED`/`RATIFIED`、OG-10/genesis 签名或 M2 使能。
- 未触碰 `turing_v5` 或任何权威字段。
- 全程只在独立 git worktree(`h6/integration-smoke` 分支)内写入。

## 文件清单

```
tools/econ_lab/wp_h6_integration_smoke.py          # 本 WP 新增驱动脚本
tests/test_wp_h6_smoke_replay.py                    # 本 WP 新增离线重放测试
tools/econ_lab/runs/h6_smoke_20260711/
  config/                                            # priors / monitor-config / stream-manifest
  live_driver_armA/                                  # 真实派工 x2 (django-11119, django-11133)
  live_driver_armA_probe3/                           # 真实派工 x1 (django-11141)
  live_driver_armA_probe4/                            # 真实派工 x1 (sphinx-7590)
  live_driver_armB/                                   # 真实派工 x1 (django-11138)
  detector/00_own_session_dispatches_no_trip.json     # 诚实反例存档
  detector/01_detector_trip.json                      # ①
  detector/02_diagnostic_injection.json               # ②
  detector/03_trajectory_rolled_back.json             # ③
  route_market/04_route_pause_mask.json                # ④
  route_market/05_route_reselection.json               # ⑤
  termination/06_termination.json                      # ⑥
  replay/replay_determinism.json                       # 重放确定性
  gate_f4/gate_f4_post_artifacts.txt                    # gate_f4 产物后 PASS
```
