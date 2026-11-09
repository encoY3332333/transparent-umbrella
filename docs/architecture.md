# 架构设计（Architecture）

> 本文档随代码演进，每次架构变更须同步更新并更新末尾的修订记录。
> 图形文件在 `docs/diagrams/`，用 PlantUML 或 draw.io 绘制，**必须入库**（不接受仅存在于答辩 PPT 中的图）。

---

## 1. 总体架构

系统采用**前后端分离的三层架构**：

| 层 | 职责 | 技术选型 |
|---|---|---|
| 表现层 | 页面渲染、用户交互、表单校验 | Vue 3 + Vite + TypeScript + Pinia |
| 业务层 | 业务编排、权限校验、排程算法 | Spring Boot 3.2 + Java 17 |
| 数据层 | 持久化、事务、缓存 | MySQL 8 + MyBatis-Plus + Caffeine |

```
┌──────────────────────────────────────────────────────┐
│  浏览器 / 移动端浏览器                                │
│  Vue 3 + Vite + TS  (port 5173)                      │
└────────────────────┬─────────────────────────────────┘
                     │  REST / JSON  ( /api/** )
                     ▼
┌──────────────────────────────────────────────────────┐
│  Spring Boot 3  (port 8080)                          │
│  ┌────────────────────────────────────────────────┐  │
│  │ Controller 层：参数校验（@Valid）、鉴权          │  │
│  ├────────────────────────────────────────────────┤  │
│  │ Manager 层：事务边界、业务编排                   │  │
│  │  AuthManager / PlanManager / ItineraryManager  │  │
│  │  FeedbackManager / POIManager / StrategyManager│  │
│  ├────────────────────────────────────────────────┤  │
│  │ Engine 层：StrategyEngine（排程算法）           │  │
│  │            BudgetCalculator / BudgetIterator   │  │
│  ├────────────────────────────────────────────────┤  │
│  │ Adapter 层：7 个外部系统代理（超时 + 降级 + 缓存）│  │
│  ├────────────────────────────────────────────────┤  │
│  │ Mapper 层：MyBatis-Plus                         │  │
│  └────────────────────────────────────────────────┘  │
└──────┬───────────────────────────────┬───────────────┘
       │                               │
       ▼                               ▼
┌──────────────┐          ┌────────────────────────────┐
│  MySQL 8     │          │  7 个外部遗留系统           │
│  8 张核心表   │          │  天气 / 地图 / 人流量 /     │
└──────────────┘          │  票务 / 活动 / 酒店 / 认证  │
                          └────────────────────────────┘
```

## 2. 模块划分

```
backend/src/main/java/com/smarttrip/
├── SmartTripApplication.java
├── common/                  公共组件
│   ├── exception/           统一异常与错误码
│   ├── response/            统一响应体 ApiResponse<T>
│   ├── config/              配置类（CORS、MyBatis、Cache）
│   └── util/                工具类
├── auth/                    认证与偏好（UC-01）
│   ├── controller/  AuthController
│   ├── manager/     AuthManager
│   ├── adapter/     AuthServerAdapter
│   └── entity/      Tourist, Preference
├── condition/               出行条件（UC-02）
│   ├── controller/  ConditionController
│   ├── manager/     ConditionValidator
│   └── entity/      TravelCondition
├── plan/                    行程生成（UC-03）
│   ├── controller/  PlanController
│   ├── manager/     PlanManager
│   ├── selector/    CandidateSelector
│   ├── engine/      StrategyEngine, ScoreCalculator
│   ├── budget/      BudgetCalculator, BudgetIterator
│   ├── validator/   FeasibilityChecker
│   └── entity/      Itinerary, ItineraryDay, Activity
├── itinerary/               行程查看与调整（UC-04, UC-05, UC-06, UC-07）
│   ├── controller/  ItineraryController, ShareController
│   ├── manager/     ItineraryManager, AdjustService, ShareService
│   └── export/      IcsExportService
├── poi/                     POI 与数据维护（UC-08）
│   ├── controller/  AdminPOIController
│   ├── manager/     POIManager
│   └── entity/      POI, Event
├── strategy/                策略参数（UC-09）
│   ├── controller/  AdminStrategyController
│   ├── manager/     StrategyManager
│   └── entity/      StrategyParameter
└── external/                外部系统代理
    ├── WeatherServerAdapter
    ├── MapServerAdapter
    ├── TrafficServerAdapter
    ├── TransitServerAdapter
    ├── EventServerAdapter
    ├── HotelServerAdapter
    └── AuthServerAdapter
```

**分层约束**（Code Review 时检查）：

- Controller 不写业务逻辑，只做参数绑定、校验、调用 Manager、包装响应
- Manager 是**唯一**的事务边界（`@Transactional` 只允许标在 Manager 方法上）
- Engine 层不依赖 Mapper，只接受领域对象作为输入（便于单元测试）
- Adapter 层负责超时、重试、缓存、降级，Manager 不直接发 HTTP 请求
- 实体类不跨层透传到 Controller，统一转 DTO

## 3. 关键数据流

### 3.1 行程生成主链路（UC-03）

```
POST /api/itineraries/generate
  │
  ▼  Controller 校验 TravelCondition（@Valid + 业务校验）
PlanManager.generateItinerary(condition)   [@Transactional]
  │
  ├─(1)→ CandidateSelector.select(condition)
  │        └→ POILib 查同城 PUBLISHED POI
  │        └→ 按偏好标签 / 必去 / 必避 过滤
  │        └→ 规模收敛至 [20, 300]
  │
  ├─(2)→ TrafficServerAdapter.getHistoricalVolume(poiIds, dateRange)  [批量]
  │        └→ CrowdIndexCalculator 计算各日 CrowdIndex ∈ [0,100]
  │
  ├─(3)→ EventServerAdapter.getEvents(city, dateRange)
  │        └→ 与偏好标签匹配，附加入候选集（category=EVENT）
  │
  ├─(4)→ MapServerAdapter.getTravelMatrix(poiIds)   [批量，缓存 1h]
  │        └→ 通勤时长矩阵 N×N
  │
  ├─(5)→ WeatherServerAdapter.getForecast(city, dateRange)
  │        └→ 逐日天气（暴雨/大风/高温标记）
  │
  └─(6)→ StrategyEngine.plan(condition, candidates, context)
           ├→ ScoreCalculator.compute()  综合评分排序
           ├→ 按天贪心装箱 + 预留用餐/休息
           ├→ FeasibilityChecker.validate()
           ├→ BudgetIterator.iterate()   超预算降本
           └→ 1–3 套方案（含推荐理由）

  ▼  持久化 Itinerary(PROPOSED) + Day + Activity
返回 List<ItineraryDTO>
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
AdjustService.adjust(planId, operation)   [@Transactional]
  ├→ 加载行程 → 复制为新版本副本（不覆盖原方案）
  ├→ 应用操作（调序 / 替换 / 删增 / 锁定重排）
  ├→ MapServerAdapter.getTravelTime()  只重算受影响相邻两项（BR-15）
  ├→ FeasibilityChecker.revalidate()   返回冲突清单
  └→ 用户确认后 save()：version+1，旧版本 SUPERSEDED
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

## 6. 非功能设计要点

### 6.1 性能

| 指标 | 目标 | 手段 |
|---|---|---|
| 行程生成 P95 | ≤ 10 秒 | 外部调用批量 + 缓存；贪心算法 O(n²) 而非指数级；超 10 秒时异步化 + 轮询 |
| 结果页首屏 | ≤ 3 秒 | 前端路由懒加载；时间轴虚拟滚动；图片懒加载 |
| 调序重算 | ≤ 1.5 秒 | 只重算受影响相邻两项（BR-15）；前端乐观更新 |
| 并发 | 200 规划请求 | 无状态服务 + 连接池 + 外部调用限流 |

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

- 所有外部 API Key 只存服务端环境变量，前端零暴露（ADR-004）
- 分享链接使用 HMAC-SHA256 签名 token，防遍历（BR-17）
- 分享响应体使用脱敏 DTO，剔除手机号、真实姓名
- 用户输入全部经 Bean Validation + 业务校验双层把关
- `.env` 永久忽略，CI 有硬编码密钥扫描步骤

## 7. 部署

```
开发环境：localhost（Vite dev server 代理 /api 到 8080）
CI    ：GitHub Actions ubuntu-latest，每次 PR 跑四步
演示  ：docker compose up（db + backend + frontend nginx）
```

`docker-compose.yml`（Issue #1 创建）：

```yaml
services:
  db:        # MySQL 8，挂载 init.sql
  backend:   # Spring Boot，depends_on db
  frontend:  # nginx 托管 dist，反代 /api 到 backend
```

---

## 修订记录

| 日期 | 版本 | 修订人 | 说明 |
|---|---|---|---|
| 2026-11-09 | v0.1 | 【组长】 | 初稿：三层架构、模块划分、主链路数据流、ADR 索引 |
