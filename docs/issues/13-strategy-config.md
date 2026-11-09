# [Feature] 推荐策略参数配置

## 背景 / Background

排程引擎的五项权重（w_pref / w_weather / w_crowd / w_travel / w_cost）直接决定推荐结果长什么样。把它硬编码在代码里意味着每次调参都要发版；做成可配置，运营可以按季节调整（夏季提高天气权重、节假日提高拥挤度权重），也便于做 A/B 对比。

对应 SRS：3.3.9 · 用例 UC-09

## 需求描述 / Description

后台配置五项权重与规则阈值，在线热生效（只影响新发起的规划，不影响已生成行程），支持版本列表与一键回滚。

## 任务清单 / Tasks

- [ ] 后端：`StrategyParameter` 实体 + 版本表，版本号自增，历史版本永久保留（BR-24）
- [ ] 后端：`GET/PUT /api/admin/strategy`
- [ ] 后端：`StrategyManager.checkSum()`——五项权重之和为 1（允许 ±0.01），每项 ∈ [0,1]（BR-23）
- [ ] 后端：一键归一化（把当前输入按比例缩放到和为 1）
- [ ] 后端：`StrategyEngine.reload()` 热加载，用 volatile 引用或版本号比对实现
- [ ] 后端：`POST /api/admin/strategy/rollback/{version}` 回滚
- [ ] 后端：某项权重被设为 0 且对应兜底规则关闭时，返回警告并要求二次确认
- [ ] 前端：`AdminStrategyView.vue`——五项滑块（实时显示和是否为 1）+ 阈值输入 + 版本列表 + 回滚按钮
- [ ] 测试：`StrategyManagerTest` 覆盖和为 1 校验、越界校验、归一化、版本自增、回滚

## 验收标准 / Acceptance Criteria

- [ ] AC-1 保存后 5 秒内新参数对新发起的规划生效
- [ ] AC-2 权重和不为 1 时，保存操作被拒绝且给出明确提示（显示当前和）
- [ ] AC-3 回滚操作 5 秒内生效，且参数版本号新增一条回滚记录
- [ ] 权重滑块数值实时求和展示，和 ≠ 1 时求和数字标红
- [ ] 「一键归一化」后五项权重之和精确为 1（误差 ≤ 0.001）
- [ ] 任一权重被设为 0 时，若对应兜底规则也关闭，弹出二次确认
- [ ] 回滚到历史版本后，`StrategyEngine` 加载的是该版本参数（可通过健康检查接口查看当前生效版本）

## 关联 / Related

- 依赖 #6（需要引擎支持热加载）
- 阻塞 无

## 元信息

- 预估工作量：6 小时
- Labels：`feature` `backend` `P2`
- Milestone：`v0.3.0 Pre`
- Assignee：【组长】
- 分支：`feature/13-strategy-config`
- 涉及业务规则：BR-23、BR-24

## 界面参考

SRS 第 5 章 S8 界面说明。
