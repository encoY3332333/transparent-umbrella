# 第 2 章 总体设计

## 2.1 设计目标与约束

| 目标 | 约束来源 | 设计上的应对 |
|---|---|---|
| 3 人 6 周内交付 9 个用例 | 课程周期 | 单体 + 服务端渲染，一套语言一套 CI；用例按 Issue 并行 |
| 行程生成 P95 ≤ 10s | SRS 非功能需求 | 排程算法纯函数化、外部调用批量 + 缓存、超时降级 |
| 未登录可生成、不可保存 | BR-03 | 行程归属字段可空，写权限由依赖注入统一拦 |
| 外部 API Key 零暴露 | ADR-004 | 全部外部调用只走服务端 adapter |
| 换库不改代码 | 课程答辩要求 MySQL | SQLAlchemy + Alembic，环境差异收敛到 `DATABASE_URL` 一个变量 |

## 2.2 架构视图

### 2.2.1 分层视图

| 层 | 职责 | 禁止事项 | 技术 |
|---|---|---|---|
| 表现层 | 页面渲染、局部刷新、表单校验 | 禁止写业务判断、禁止 `|safe` 渲染用户输入 | Jinja2 + HTMX + Alpine.js |
| 接口层 `api/` | 参数绑定、鉴权依赖、响应包装 | 禁止出现 SQL、禁止开事务 | FastAPI + Pydantic v2 |
| 业务层 `services/` | 业务编排、**唯一事务边界** | 禁止直接 `import httpx`，必须经 adapters | Python 3.11 |
| 算法层 `engine/` | 排程纯函数 | 禁止 import models / adapters / sqlalchemy | 纯 stdlib + dataclass |
| 适配层 `adapters/` | 外部系统代理（超时/重试/缓存/降级/配额） | 禁止把业务规则放进来 | httpx |
| 数据层 `models/` + `migrations/` | ORM 模型与迁移 | 禁止在模型里写业务校验 | SQLAlchemy 2.0 + Alembic |

**为什么把 engine 独立成"纯净层"**：排程算法是项目里最容易改、最需要反复验证的部分。让它不依赖数据库和外部服务，它就可以被单测直接打桩（`backend/tests/test_scorer_units.py` 的 11 个用例不建库、不联网）。这是 ADR-002 的直接产物。

### 2.2.2 运行时视图

```
浏览器 (HTML/HTMX)
   │  HTTP
   ▼
FastAPI 单进程（uvicorn, port 8000）
   ├─ api/         路由、校验、依赖注入
   ├─ services/    编排 + 事务
   ├─ engine/      纯函数排程
   ├─ adapters/    外部代理（当前已接：人流 traffic；其余按 Issue 排期）
   └─ models/      ORM
   │
   ├─→ SQLite（开发/CI，内存库）
   ├─→ MySQL 8（演示/生产）
   └─→ 外部遗留系统：天气 / 地图 / 人流 / 票务 / 活动 / 酒店 / 认证
```

### 2.2.3 部署视图

| 环境 | 组成 | 数据库 | 启动方式 |
|---|---|---|---|
| 开发 | 本地 uvicorn `--reload` | SQLite 文件 | `uvicorn app.main:app --reload` |
| CI | GitHub Actions ubuntu-latest + Python 3.11 | SQLite `:memory:` | `pytest`（不依赖任何外部服务） |
| 演示 | docker compose（db + web） | MySQL 8 | `docker compose up --build` |

三个环境的差异**只有 `DATABASE_URL`**，其余全部由 `backend/app/core/config.py` 的 `Settings` 从环境变量读取。

## 2.3 模块清单（以当前代码为准）

> 标记含义：✅ 已实现并有用例覆盖；◐ 部分实现；○ 仅设计（有目录/契约，无实现）。

| 模块 | 路径 | 状态 | 职责 |
|---|---|---|---|
| 应用入口 | `backend/app/main.py` | ✅ | 创建 app、挂中间件、注册异常处理、启动钩子 |
| 配置 | `backend/app/core/config.py` | ✅ | 唯一环境变量入口，`Settings` 与 `.env.example` 一一对应 |
| 错误模型 | `backend/app/core/errors.py` | ✅ | 错误码枚举 + `ERROR_SPECS`（状态码与中文文案）+ `BusinessError` |
| 异常处理 | `backend/app/core/handlers.py` | ✅ | 业务异常 / 参数校验 / HTTP 异常 / 兜底异常 → 统一响应体 |
| 安全 | `backend/app/core/security.py` | ✅ | JWT 签发校验、分享链接 HMAC-SHA256 |
| 依赖注入 | `backend/app/core/deps.py` | ✅ | `get_db`、`get_optional_tourist`、`get_current_tourist` |
| 结构化日志 | `backend/app/core/logging.py` | ✅ | trace_id 贯穿请求、统一日志格式 |
| 数据库 | `backend/app/core/db.py` | ✅ | `DATABASE_URL` → Engine（SQLite 内存库走 StaticPool） |
| 认证接口 | `backend/app/api/auth.py` | ✅ | UC-01 sms-code / login / logout / me |
| 偏好接口 | `backend/app/api/tourist.py` | ✅ | UC-01 偏好查询与保存 |
| 条件接口 | `backend/app/api/conditions.py` | ✅ | UC-02 条件校验 |
| 行程接口 | `backend/app/api/itineraries.py` | ✅ | UC-03 生成 / UC-04 展示 |
| 策略接口 | `backend/app/api/admin_strategy.py` | ✅ | UC-09 策略版本读写与归一化 |
| 页面路由 | `backend/app/api/pages.py` | ◐ | 首页、条件录入、结果页、调整页、后台策略页；**部分页面数据为 mock** |
| 认证服务 | `backend/app/services/auth_service.py` | ✅ | 验证码频控/过期/锁定、登录、偏好建档 |
| 条件服务 | `backend/app/services/condition_service.py` | ✅ | UC-02 业务规则二次校验 |
| 生成编排 | `backend/app/services/plan_service.py` | ✅ | UC-03 主链路：选点 → 外部数据 → 装箱 → 落库 |
| 算法桥 | `backend/app/services/engine_bridge.py` | ✅ | ORM 与纯 dataclass 的双向转换 |
| POI 仓储 | `backend/app/services/poi_repository.py` | ✅ | 同城已发布 POI 查询与规模收敛 |
| 策略服务 | `backend/app/services/strategy_service.py` | ✅ | 权重读写、版本发布、进程内缓存 |
| 选点 | `backend/app/engine/selector.py` | ✅ | 偏好/必去/必避过滤，规模收敛到 [20,300] |
| 评分 | `backend/app/engine/scorer.py` | ✅ | 五项加权公式（BR-23 允差 ±0.01） |
| 装箱 | `backend/app/engine/packer.py` | ✅ | 按天贪心装箱，预留用餐与休息 |
| 拥挤度 | `backend/app/engine/crowd.py` | ✅ | 历史同期均值 + 节假日系数（ADR-006） |
| 通勤 | `backend/app/engine/travel.py` | ✅ | 通勤时长的纯函数计算 |
| 策略引擎 | `backend/app/engine/strategy_engine.py` | ✅ | 参数装载与权重归一 |
| 协议 | `backend/app/engine/protocols.py` | ✅ | engine 与外部交互的最小接口定义 |
| 外部代理基座 | `backend/app/adapters/base.py` | ✅ | 超时 / 重试 / 缓存 / 降级 统一封装 |
| 调用配额 | `backend/app/adapters/call_budget.py` | ✅ | 单次规划外部调用计数（BR-10 ≤ 60） |
| 人流代理 | `backend/app/adapters/traffic.py` | ◐ | 真实接口 + 演示降级路径 |
| 天气/地图/票务/活动/酒店/认证代理 | `backend/app/adapters/` | ○ | 契约已定（`docs/api.md` 附录），实现按 Issue 排期 |

## 2.4 关键数据流

### 2.4.1 行程生成（UC-03）

```
POST /api/itineraries/generate
  → api/itineraries.py：Pydantic 类型校验 → condition_service 业务二次校验
  → plan_service.generate()  [事务边界]
      1. poi_repository 取同城 PUBLISHED POI
      2. selector 按偏好/必去/必避过滤 + 规模收敛
      3. adapters：人流、活动、通勤矩阵、天气（批量，受 call_budget 约束）
      4. packer 按天贪心装箱 → scorer 五项加权排序
      5. 超预算时 budget_iterator 降本（当前由 packer 的降级路径承担）
  → 落库 Itinerary(PROPOSED) + ItineraryDay + Activity
  → 返回 1–3 套方案（含推荐理由 + 降级说明）
```

**降级可见**：任何外部数据缺失都会写进 `degraded_json`，随响应返回并在结果页提示"某类数据为估算"。这一条是回应老师"Mock 与真实服务必须区分"的要求——降级必须在界面上说出来，而不是悄悄用假数据。

### 2.4.2 行程调整（UC-05）

```
GET /pages/itineraries/{id}/adjust → 调整页
PUT /api/itineraries/{id}/adjust（规划中）
  → adjust_service：加载 → 复制副本 → 应用操作 → 只重算受影响相邻两项
  → feasibility 重新校验硬约束 → 返回冲突清单
  → 用户确认后才 commit：version+1，旧版本 SUPERSEDED（ADR-005）
```

**当前状态**：调整页 `backend/app/api/pages.py::adjustment_page` 仍是 **mock 渲染**——行程数据写死，任意 `itinerary_id` 都返回 200。真实的 404 与版本推进要等 #8 接入真实行程查询后再做。这一点必须在本册与报告里如实标注，不能把"页面能打开"写成"调整功能可用"。

## 2.5 跨模块约定

| 约定 | 内容 | 落点 |
|---|---|---|
| 统一响应体 | `{code, message, data}`；失败走错误形状 `{code, message, details[], traceId}` | `schemas/common.py`、`core/handlers.py` |
| 错误码 | 全部集中在 `ErrorCode` 枚举 + `ERROR_SPECS`，service 只抛不改状态码 | `core/errors.py` |
| 事务边界 | 只允许 `services/` 开事务；`api/` 与 `engine/` 不得开 | `docs/architecture.md` 分层约束 |
| ORM 不出 service | 路由拿到的一律是 Pydantic schema | 同上 |
| 时间 | 全部用带时区的 UTC（`datetime.now(UTC)`），展示层再转本地 | `models/*.py` 的 `_utcnow()` |
| 追踪 | 每个请求带 `traceId`，贯穿日志与错误响应 | `core/logging.py` |

## 2.6 与既有文档的关系

`docs/architecture.md` 是本项目架构的**演进记录**，随开发过程更新；本册是面向交付的**结构化设计说明**。两者若出现不一致，以本册与代码为准，并回头修正 architecture.md——第一阶段被扣分的第 4 条正是"文档之间不同步"。
