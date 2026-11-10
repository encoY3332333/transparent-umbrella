# [Feature] 行程生成编排入口

## 背景 / Background

UC-03 是整个系统的核心，但一次性做完不可控（预估 24 小时，超出 Issue 粒度上限）。拆成三个可独立验证的子任务后，本 Issue 只负责**编排**：把 #5 候选筛选、#6 排程引擎、#7 预算迭代串成一条可调用的链路，并负责结果持久化与返回。这样三个子任务可以并行推进，也能各自被单独测试。

对应 SRS：3.3.3 · 用例 UC-03（主流程 1–8 步的串联）

## 需求描述 / Description

提供 `POST /api/itineraries/generate` 接口，接收已校验的 `TravelCondition`，依次调用三个子模块，生成 1–3 套候选方案并落库为 `PROPOSED` 状态。

## 任务清单 / Tasks

- [ ] 后端：`app/api/itineraries.py` 的 `generate` 路由 + `app/services/plan_service.py` 的 `PlanService.generate(condition, tourist)` 编排骨架
- [ ] 后端：定义三个子模块的协议（先写 `typing.Protocol`，不写实现，便于并行开发）
  - `engine/selector.py`：`select(condition, pois) -> list[Candidate]`
  - `engine/packer.py`：`plan(condition, candidates, context) -> list[PlanResult]`
  - `engine/feasibility.py`：`validate(plan) -> list[Conflict]`
- [ ] 后端：外部调用计数器，累计超过 60 次（BR-10）直接抛 `ExternalCallLimitExceeded` 并走降级。计数器挂在 `adapters/base.py` 的请求上下文中
- [ ] 后端：结果落库 `Itinerary`（状态 PROPOSED）+ `ItineraryDay` + `Activity`，用 `with session.begin():` 保证原子性
- [ ] 后端：生成耗时打点，用 `time.perf_counter()` 记录并通过结构化日志输出 `plan.generate.duration_ms`（**不引入 Prometheus 客户端**，课程项目用日志足够）
- [ ] 页面：S4 生成页的加载态——HTMX 的 `hx-indicator` + 5 步进度提示（候选筛选 → 人流 → 活动 → 通勤 → 装箱）
- [ ] 测试：`tests/services/test_plan_service.py` 用假实现替换三个子模块，验证编排顺序、异常传播、事务回滚

## 验收标准 / Acceptance Criteria

- [ ] 对同一组输入条件，接口返回至少 1 套完整方案，HTTP 200
- [ ] 三个子模块按 `select → plan → validate` 顺序被调用（用一个 `calls: list[str]` 记录调用顺序后断言 `calls == ["select", "plan", "validate"]`）
- [ ] 任一子模块抛异常时，整个事务回滚，数据库中不残留半成品行程（测试里查 `Itinerary` 计数为 0）
- [ ] 外部调用超限时返回 `EXTERNAL_CALL_LIMIT_EXCEEDED`，页面提示并给出「稍后重试」
- [ ] 生成耗时有日志记录，包含 `duration_ms` 与 `plan_id`
- [ ] 接口返回体包含：方案列表、每套方案的推荐理由、可行性提示、预算明细
- [ ] `engine/` 三个子模块的协议与实现分离：`#5`/`#6`/`#7` 未完成时，用假实现也能跑通编排层的测试

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

本 Issue **不实现**算法。先定义协议再并行开发，是本项目的一条架构决策（见 ADR-002）。

## 技术备注

- **协议用 `typing.Protocol` 而非抽象基类**。`Protocol` 支持结构化子类型，`#5`/`#6`/`#7` 的实现类不需要显式继承，只要方法签名对得上就能通过 Mypy 检查——减少三个人之间的耦合
- **事务边界只在 service**。`api/` 层不写 `session.begin()`，测试验证回滚时直接在 service 里注入一个会抛异常的假 `Feasibility`
- **外部调用计数用 `contextvars`**。一次请求可能跨多个 async 任务，用模块级全局变量会串数据。`adapters/base.py` 里放一个 `ContextVar[int]`，在请求入口重置
- **不要在 service 里 `try/except` 包住整个编排**。让异常往上抛，由 `core/handlers.py` 统一转成错误响应；service 里只捕获**需要降级**的特定异常（如 `WeatherUnavailable`）
- **进度提示是假的**。服务端渲染做不到真正的推送进度，5 步提示只是按预估值定时切换的视觉反馈。**在页面文案上不要承诺百分比**，写「正在计算，通常需要 3–10 秒」，否则用户会以为卡住了
