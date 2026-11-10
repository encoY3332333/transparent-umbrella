# 架构设计（Architecture）

> 本文档随代码演进，每次架构变更须同步更新并更新末尾的修订记录。
> 图形文件在 `docs/diagrams/`，用 PlantUML 或 draw.io 绘制，**必须入库**（不接受仅存在于答辩 PPT 中的图）。

---

## 1. 总体架构

系统采用**单体应用 + 服务端渲染**的分层架构。前后端不再分离部署，同一个 FastAPI 进程既返回 HTML 页面，也提供 `/api/**` 的 JSON 接口。

| 层 | 职责 | 技术选型 |
|---|---|---|
| 表现层 | 页面渲染、局部刷新、表单校验 | Jinja2 模板 + HTMX + Alpine.js |
| 应用层 | 路由、参数校验、鉴权、响应包装 | FastAPI + Pydantic v2 |
| 业务层 | 业务编排、事务、排程算法 | Python 3.11（services / engine） |
| 数据层 | 持久化、迁移、缓存 | SQLAlchemy 2.0 + Alembic + SQLite/MySQL |

```
┌──────────────────────────────────────────────────────────┐
│  浏览器                                                   │
│  HTML + HTMX + Alpine.js                                 │
└──────────────────────┬───────────────────────────────────┘
                       │  HTTP  (整页 GET / 局部 hx-get / 表单 POST)
                       ▼
┌──────────────────────────────────────────────────────────┐
│  FastAPI  (port 8000，单进程)                             │
│  ┌────────────────────────────────────────────────────┐  │
│  │ api 层：路由 + Pydantic 校验 + 鉴权依赖             │  │
│  │   pages.py（HTML）  auth.py  conditions.py          │  │
│  │   itineraries.py    feedback.py  admin_*.py         │  │
│  ├────────────────────────────────────────────────────┤  │
│  │ services 层：业务编排，唯一的事务边界                │  │
│  │   AuthService  PlanService  ItineraryService        │  │
│  │   AdjustService  ShareService  POIService …         │  │
│  ├────────────────────────────────────────────────────┤  │
│  │ engine 层：纯函数排程算法，无 I/O、无 ORM            │  │
│  │   Selector  Scorer  Packer  Feasibility             │  │
│  │   BudgetIterator                                    │  │
│  ├────────────────────────────────────────────────────┤  │
│  │ adapters 层：7 个外部系统代理（超时+缓存+降级）      │  │
│  ├────────────────────────────────────────────────────┤  │
│  │ models 层：SQLAlchemy 2.0 声明式模型                 │  │
│  └────────────────────────────────────────────────────┘  │
└──────┬───────────────────────────────┬───────────────────┘
       │                               │
       ▼                               ▼
┌──────────────┐          ┌────────────────────────────┐
│ SQLite（开发）│          │  7 个外部遗留系统           │
│ MySQL（生产） │          │  天气 / 地图 / 人流 / 票务 / │
│  8 张核心表   │          │  活动 / 酒店 / 认证         │
└──────────────┘          └────────────────────────────┘
```

**为什么从前后端分离改回单体**：行程规划是「表单 → 结果页 → 局部调整」的短链路，SPA 带来的路由与状态管理成本大于收益；改为服务端渲染后，三人只需维护一种语言、一套依赖、一个 CI 运行时。代价是页面局部刷新依赖 HTMX 而非组件化，交互复杂度上限更低——这对本项目的 8 个页面是够的。决策记录见 [ADR-007](./adr/ADR-007-switch-to-python-stack.md)。


## 2. 模块划分

```
backend/app/
├── main.py                      应用入口：创建 app、挂中间件与路由、启动钩子
├── core/                        横切关注点
│   ├── config.py                Settings（pydantic-settings 读 .env）
│   ├── errors.py                错误码枚举 + 业务异常基类（39 个码，与 docs/api.md 一致）
│   ├── handlers.py              异常 → 统一错误响应的转换
│   ├── security.py              JWT 签发/校验、密码哈希、分享链接 HMAC 签名
│   ├── deps.py                  依赖注入：get_db / current_tourist / require_admin
│   └── logging.py               结构化日志（含 trace_id）
├── api/                         路由层，一个用例一个模块
│   ├── router.py                汇总挂载，统一 /api 前缀
│   ├── pages.py                 HTML 页面路由（服务端渲染入口）
│   ├── auth.py                  UC-01 登录与偏好
│   ├── conditions.py            UC-02 出行条件
│   ├── itineraries.py           UC-03 生成 / UC-04 查看 / UC-05 调整 / UC-06 分享
│   ├── feedback.py              UC-07 反馈
│   ├── admin_poi.py             UC-08 POI 维护
│   ├── admin_strategy.py        UC-09 策略参数
│   └── health.py                /api/health
├── services/                    业务编排，唯一的事务边界
│   ├── auth_service.py
│   ├── condition_service.py
│   ├── plan_service.py          生成主链路编排
│   ├── itinerary_service.py     查询、列表、删除
│   ├── adjust_service.py        副本调整事务
│   ├── share_service.py         分享链接签发与只读视图
│   ├── feedback_service.py
│   ├── poi_service.py
│   └── strategy_service.py      权重读写与版本管理
├── engine/                      排程算法（纯函数，禁止 import models / adapters）
│   ├── models.py                纯 dataclass：Candidate / DayPlan / PlanResult
│   ├── selector.py              候选集筛选与规模收敛
│   ├── scoring.py               Score 公式实现
│   ├── packer.py                按天贪心装箱 + 用餐/休息预留
│   ├── feasibility.py           硬约束校验，产出冲突清单
│   └── budget_iterator.py       超预算时的降本迭代
├── adapters/                    外部系统代理
│   ├── base.py                  统一封装：超时 / 重试 / 缓存 / 降级 / 调用计数
│   ├── weather.py  map.py  traffic.py  event.py
│   ├── ticket.py   hotel.py  auth.py
├── models/                      SQLAlchemy 2.0 声明式模型（8 张表）
├── schemas/                     Pydantic 模型：请求 / 响应 / 内部数据类
├── templates/                   Jinja2 模板（base.html + 8 个页面 + 局部片段）
├── static/                      CSS / HTMX / Alpine.js
└── seed/                        演示 POI 与活动数据（JSON）
```

**分层约束**（Code Review 时逐条检查）：

- **路由不写业务**：`api/` 下的函数只做参数绑定、调用 service、返回 schema，不出现 SQL 与计算逻辑
- **事务只在 service**：`session.begin()` 只允许出现在 `services/`，`api/` 与 `engine/` 不得开事务
- **engine 保持纯净**：只依赖标准库与 `engine/models.py`，不得 `import` `models/`、`adapters/`、`sqlalchemy`——这样排程算法可以脱离数据库单测
- **外部调用只走 adapter**：`services/` 不得直接 `import httpx` / `requests`，必须经 `adapters/` 以获得统一的超时、缓存、降级与调用计数
- **ORM 不出 service**：路由拿到的必须是 Pydantic schema，不得把 SQLAlchemy 对象直接返回（否则 `DetachedInstanceError` 与字段泄露同时发生）


## 3. 关键数据流

### 3.1 行程生成主链路（UC-03）

```
POST /api/itineraries/generate
  │
  ▼  api/itineraries.py：TravelConditionIn（Pydantic）自动校验 → 业务规则二次校验
PlanService.generate(condition, tourist)   [session.begin() 事务]
  │
  ├─(1)→ Selector.select(condition, poi_repo)
  │        └→ 查同城 PUBLISHED POI
  │        └→ 按偏好标签 / 必去 / 必避 过滤
  │        └→ 规模收敛至 [20, 300]
  │
  ├─(2)→ TrafficAdapter.get_historical_volume(poi_ids, date_range)  [批量]
  │        └→ 计算各日 CrowdIndex ∈ [0,100]
  │
  ├─(3)→ EventAdapter.get_events(city, date_range)
  │        └→ 与偏好标签匹配，附加入候选集（category=EVENT）
  │
  ├─(4)→ MapAdapter.get_travel_matrix(poi_ids)   [批量，缓存 1h]
  │        └→ 通勤时长矩阵 N×N
  │
  ├─(5)→ WeatherAdapter.get_forecast(city, date_range)
  │        └→ 逐日天气（暴雨/大风/高温标记）
  │
  └─(6)→ Packer.plan(condition, candidates, context)   ← 纯函数，无 I/O
           ├→ Scorer.compute()          综合评分排序
           ├→ 按天贪心装箱 + 预留用餐/休息
           ├→ Feasibility.validate()
           ├→ BudgetIterator.iterate()  超预算降本
           └→ 1–3 套方案（含推荐理由）

  ▼  持久化 Itinerary(PROPOSED) + Day + Activity
返回 list[ItineraryOut]
```

**外部调用预算**（BR-10，单次 ≤ 60 次）：

| 调用 | 次数 | 说明 |
|---|---|---|
| 地图解析 | 2 | 出发地 + 目的地 |
| 天气 | 1 | 批量按日期范围 |
| 人流量 | 1–3 | 批量分页（每页 100 个 POI） |
| 活动 | 1 | 按城市 + 日期范围 |
| 通勤矩阵 | 1–3 | 批量分页 |
| 票务 + 酒店 | 2 | 各 1 次查询 |
| **合计** | **8–12** | 留出充足余量应对重试 |

### 3.2 行程调整链路（UC-05）

```
PUT /api/itineraries/{id}/adjust
  │
  ▼
AdjustService.adjust(plan_id, operation, tourist)   [session.begin() 事务]
  ├→ 加载行程 → 复制为新版本副本（不覆盖原方案）
  ├→ 应用操作（调序 / 替换 / 删增 / 锁定重排）
  ├→ MapAdapter.get_travel_time()  只重算受影响相邻两项（BR-15）
  ├→ Feasibility.revalidate()      返回冲突清单
  └→ 用户确认后 commit：version+1，旧版本 SUPERSEDED
     （历史最多 10 个版本，BR-14）
```

## 4. 数据模型

核心 8 张表（详见 SRS 附录 A 数据字典）：

```
tourist ──1:0..1── preference
   │
   └──1:0..*── itinerary ──1:1..15── itinerary_day ──1:1..*── activity ──*:1── poi
                    │                                                          │
                    └──1:0..1── feedback                          event ──*:1──┘
strategy_parameter（独立表，版本号自增）
```

| 表名 | 说明 | 关键约束 |
|---|---|---|
| `tourist` | 游客档案 | 手机号唯一（BR-01） |
| `preference` | 偏好档案 | 标签最多 6 个（BR-02） |
| `travel_condition` | 出行条件 | 天数 ∈ [1,15]、预算 ∈ [500,200000]、人数 ∈ [1,20] |
| `itinerary` | 行程主表 | `version` 支持多版本；`status` 六态 |
| `itinerary_day` | 行程天 | `dayIndex` 从 1 开始 |
| `activity` | 活动 | 同日 `startTime < endTime`，不重叠 |
| `poi` | 兴趣点 | 承载量 ∈ [1,200000]（BR-21） |
| `crowd_index` | 拥挤度快照 | 按 poiId + date 唯一 |
| `feedback` | 反馈 | 关联策略版本快照（BR-20） |
| `strategy_parameter` | 策略参数 | 权重和 = 1（BR-23），版本不可删（BR-24） |

## 5. 关键技术决策（ADR 索引）

| 编号 | 决策 | 理由 | 备选方案 | 文档 |
|---|---|---|---|---|
| ADR-001 | 采用 JWT 而非 Session | 前后端分离，便于水平扩展；无状态便于 CI 测试 | Session + Redis | [adr/001](./adr/ADR-001-jwt-vs-session.md) |
| ADR-002 | 排程模块拆分为 3 个子模块，先定接口契约 | UC-03 预估 24h 超出 Issue 粒度；契约先行支持并行开发 | 一个人做完整个引擎 | [adr/002](./adr/ADR-002-split-schedule-engine.md) |
| ADR-003 | 贪心装箱 + 综合评分，不用整数规划 | 15 天 × 300 POI 的规模下，贪心 8 秒内可解；ILP 求解时间不可控，且对课程项目属于过度设计 | OR-Tools / 动态规划 | [adr/003](./adr/ADR-003-greedy-vs-ilp.md) |
| ADR-004 | 外部数据全部走服务端代理 | 防止 API Key 暴露在前端；统一超时、缓存、限流、降级 | 前端直连第三方 | [adr/004](./adr/ADR-004-server-side-proxy.md) |
| ADR-005 | 行程调整在副本上执行，确认后覆盖 | 保证「撤销」语义天然成立；避免用户误操作污染已保存方案 | 直接改原对象 + 操作日志回滚 | [adr/005](./adr/ADR-005-adjust-on-copy.md) |
| ADR-006 | 拥挤度用「历史同期均值 + 节假日系数」，不用 ML | 缺乏训练数据；简单统计模型可解释，便于归因 | LSTM / XGBoost | [adr/006](./adr/ADR-006-crowd-index-statistical.md) |
| ADR-007 | 技术栈整体切换为 Python（FastAPI + Jinja2），放弃 Spring Boot + Vue 3 | 三人 Python 熟练度高，Java 需现学；CI 从两套运行时降为一套；本地环境从 4 项依赖降为 1 项 | 保持 Java；或 Java + Node 双栈并行 | [adr/007](./adr/ADR-007-switch-to-python-stack.md) |

## 6. 非功能设计要点

### 6.1 性能

| 指标 | 目标 | 手段 |
|---|---|---|
| 行程生成 P95 | ≤ 10 秒 | 外部调用批量 + 缓存；贪心算法 O(n²) 而非指数级；超 10 秒时改为后台任务 + 轮询（HTMX `hx-trigger="every 2s"`） |
| 结果页首屏 | ≤ 3 秒 | 服务端渲染直接出 HTML，无需等待 JS 打包；静态资源带 hash 指纹走强缓存 |
| 调序重算 | ≤ 1.5 秒 | 只重算受影响相邻两项（BR-15）；HTMX 局部替换行程卡片段，不整页刷新 |
| 并发 | 200 规划请求 | 无状态服务 + SQLAlchemy 连接池；`uvicorn --workers 4`；外部调用信号量限流 |

### 6.2 降级策略

| 外部系统故障 | 降级行为 | 用户可见提示 |
|---|---|---|
| 天气服务 | 天气字段 `UNKNOWN`，排程取消天气惩罚 | 「天气数据暂不可用」 |
| 地图服务 | 通勤时长按直线距离 × 1.5 估算 | 「通勤时间为估算值」 |
| 人流量服务 | `CrowdIndex = UNKNOWN`，取消拥挤度惩罚 | 「拥挤度数据暂不可用」 |
| 活动日历 | 跳过活动插入，仅排 POI | 「当地活动暂未获取」 |
| 票务 / 酒店 | 预算中该两项按目的地均价估算 | 「交通/住宿价格为预估值」 |
| 认证服务 | 已登录用户可用缓存 token，未登录用户禁止进入 | 「登录服务暂不可用」 |

### 6.3 安全

- 所有外部 API Key 只存服务端环境变量（`Settings` 从 `.env` 读取），页面与静态资源中零暴露（ADR-004）
- 分享链接使用 HMAC-SHA256 签名 token，防遍历（BR-17）
- 分享响应使用独立的 `ShareItineraryOut` schema，不包含手机号、真实姓名等字段
- 用户输入经 **Pydantic v2 类型校验 + service 层业务校验**双层把关：前者拦格式（如 `days` 必须是 1–15 的整数），后者拦跨字段规则（如预算与天数的下限组合，BR-05）
- Jinja2 模板默认开启自动转义，渲染用户内容时禁止使用 `|safe`（Code Review 检查项）
- `.env` 永久忽略；CI 有硬编码密钥扫描步骤

## 7. 部署

```
开发环境：localhost:8000（uvicorn --reload，SQLite 文件随仓库外创建）
CI    ：GitHub Actions ubuntu-latest，Python 3.11，SQLite 内存库，不依赖外部服务
演示  ：docker compose up（db + web），或直接 uvicorn 单进程 + MySQL
```

`docker-compose.yml`（Issue #1 创建）：

```yaml
services:
  db:     # MySQL 8，挂载 init.sql 建库
  web:    # python:3.11-slim，pip install -e .，uvicorn 启动，depends_on db
          # 生产不用 --reload，workers 按 CPU 核数设置
```

**环境差异只有一个变量**：`DATABASE_URL`。

| 环境 | `DATABASE_URL` |
|---|---|
| 开发（默认） | `sqlite+pysqlite:///./smarttrip.db` |
| 测试 / CI | `sqlite+pysqlite:///:memory:` |
| 演示 / 生产 | `mysql+pymysql://user:pass@db:3306/smarttrip?charset=utf8mb4` |

切换数据库只改这一行、再跑一次 `alembic upgrade head`，代码零改动。这是选择 SQLAlchemy 而非直接写 SQL 的主要收益。

---

## 修订记录

| 日期 | 版本 | 修订人 | 说明 |
|---|---|---|---|
| 2026-11-09 | v0.1 | 【组长】 | 初稿：三层架构、模块划分、主链路数据流、ADR 索引 |
| 2026-11-10 | v0.2 | 【组长】 | 技术栈切换为 Python：修改分层表与架构图（FastAPI 单体 + Jinja2 服务端渲染）；模块划分改为 Python 包结构并重写 5 条分层约束；数据流伪代码同步为 service/engine 调用；新增 ADR-007；部署章节改为 SQLAlchemy 多数据库方案 |
