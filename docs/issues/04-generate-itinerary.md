# [Feature] 行程生成编排入口

## 背景 / Background

UC-03 是整个系统的核心，但一次性做完不可控（预估 24 小时，超出 Issue 粒度上限）。拆成三个可独立验证的子任务后，本 Issue 只负责**编排**：把 #5 候选筛选、#6 排程引擎、#7 预算迭代串成一条可调用的链路，并负责结果持久化与返回。这样三个子任务可以并行推进，也能各自被单独测试。

对应 SRS：3.3.3 · 用例 UC-03（主流程 1–8 步的串联）

## 需求描述 / Description

提供 `POST /api/itineraries/generate` 接口，接收已校验的 TravelCondition，依次调用三个子模块，生成 1–3 套候选方案并落库为 `PROPOSED` 状态。

## 任务清单 / Tasks

- [ ] 后端：`PlanController.generate()` + `PlanManager.generateItinerary(condition)` 编排骨架
- [ ] 后端：定义三个子模块的接口契约（先写接口，不写实现，便于并行开发）
  - `CandidateSelector.select(condition) -> List<POI>`
  - `StrategyEngine.plan(condition, pois, context) -> List<Itinerary>`
  - `FeasibilityChecker.validate(itinerary) -> ValidationResult`
- [ ] 后端：外部调用计数器，累计超过 60 次（BR-10）直接抛 `ExternalCallLimitExceeded` 并走降级
- [ ] 后端：结果落库 `Itinerary`（状态 PROPOSED）+ `ItineraryDay` + `Activity`，事务保证原子性
- [ ] 后端：生成耗时打点（Micrometer Timer），暴露 `plan.generate.duration` 指标
- [ ] 前端：`/api/itineraries/generate` 的加载态与骨架屏对接（S4 界面），进度分 5 步展示
- [ ] 测试：`PlanManagerTest` 用 Mock 子模块，验证编排顺序、异常传播、事务回滚

## 验收标准 / Acceptance Criteria

- [ ] 对同一组输入条件，接口返回至少 1 套完整方案，HTTP 200
- [ ] 三个子模块按 `select → plan → validate` 顺序被调用（可用 Mockito `InOrder` 断言）
- [ ] 任一子模块抛异常时，整个事务回滚，数据库中不残留半成品行程
- [ ] 外部调用超限时返回 `EXTERNAL_CALL_LIMIT_EXCEEDED`，前端提示并给出「稍后重试」
- [ ] 生成耗时有指标记录，可在日志中看到 `duration_ms`
- [ ] 接口返回体包含：方案列表、每套方案的推荐理由、可行性提示、预算明细

## 关联 / Related

- 依赖 #1
- 依赖 #3
- 依赖 #5
- 依赖 #6
- 依赖 #7
- 阻塞 #8

## 元信息

- 预估工作量：4 小时
- Labels：`feature` `backend` `P0`
- Milestone：`v0.1.0 Alpha`
- Assignee：【组长】
- 分支：`feature/4-generate-itinerary`
- 涉及业务规则：BR-10

## 设计说明

本 Issue **不实现**算法。先定义接口契约再并行开发，是本项目的一条架构决策（见 ADR-002）。
