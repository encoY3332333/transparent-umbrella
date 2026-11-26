# 附录 A 需求-设计-代码-测试 追踪矩阵

> 用途：答辩被问"这条需求你在哪实现的、怎么证明它实现了"，直接查这张表。
> 状态口径：✅ 已实现且有用例；◐ 部分实现（存在 mock 或降级路径）；○ 仅设计。

## A.1 用例级追踪

| 用例 | 主要接口 | 服务/算法 | 关键代码 | 测试 | 本册章节 | 状态 |
|---|---|---|---|---|---|---|
| UC-01 登录与偏好 | `POST /api/auth/sms-code`、`POST /api/auth/login`、`POST /api/auth/logout`、`GET /api/auth/me`、`GET|PUT /api/tourists/me/preference` | `auth_service` | `backend/app/api/auth.py`、`api/tourist.py`、`services/auth_service.py`、`core/deps.py`、`core/security.py` | `tests/test_tourist_auth.py`(26) | 3.1、4.1 | ✅ |
| UC-02 出行条件 | `POST /api/conditions/validate` | `condition_service` | `api/conditions.py`、`services/condition_service.py`、`schemas/condition.py` | `tests/test_conditions.py` | 3.2、4.2 | ✅ |
| UC-03 行程生成 | `POST /api/itineraries/generate` | `plan_service` + `engine` | `api/itineraries.py`、`services/plan_service.py`、`engine_bridge.py`、`engine/selector.py`、`packer.py`、`scorer.py` | `tests/services/test_plan_service.py`、`test_scorer_units.py`、`test_candidate_selector.py` | 3.3、4.3 | ✅（外部数据部分降级） |
| UC-04 行程查看 | 结果页 `GET /pages/itineraries/{id}`、展示接口 | `plan_service` 查询路径 | `api/pages.py`、`api/itineraries.py` | `tests/test_pages.py` | 3.4 | ◐ 结果页数据曾为 mock，#8 接真实查询中 |
| UC-05 行程调整 | `GET /pages/itineraries/{id}/adjust` | `adjust_service`（未落地） | `api/pages.py::adjustment_page` | `tests/test_adjust_page.py` | 3.5 | ◐ 页面可渲染，**数据为 mock**，无版本推进 |
| UC-06 保存与分享 | 规划中 | `itinerary_service` / `share_service`（未落地） | `core/security.py` 已有 HMAC 分享签名 | `tests/test_security.py`（签名部分） | 3.6 | ○ 仅设计（#10） |
| UC-07 规划反馈 | 规划中 | `feedback_service`（未落地） | — | — | 3.7 | ○ 仅设计（#11） |
| UC-08 POI 维护 | 规划中 | `poi_service`（未落地，现有 `poi_repository` 只读） | `services/poi_repository.py` | 间接（plan_service 用例） | 3.8 | ○ |
| UC-09 策略参数 | `GET /api/admin/strategies/current`、`GET|POST /api/admin/strategies`、`POST /api/admin/strategies/normalize` | `strategy_service` | `api/admin_strategy.py`、`services/strategy_service.py`、`models/strategy.py`、`migrations/0003` | `tests/test_admin_strategy_api.py`、`tests/services/test_strategy_service.py`、`test_strategy_engine.py` | 3.9、4.9 | ✅ |

## A.2 业务规则追踪（只列有硬性数值、易被追问的）

| 规则 | 内容 | 落点 | 守护方式 |
|---|---|---|---|
| BR-01 | 手机号唯一 | `tourist.phone` 唯一约束 + `migrations/0004` | 迁移约束 + 登录用例 |
| BR-02 | 偏好标签 ≤ 6 | `models/tourist.py::MAX_PREFERENCE_TAGS`、`auth_service.save_preferences` | 单测：超限返回 `CONDITION_TOO_MANY_TAGS` |
| BR-03 | 未登录可生成、不可保存 | `itinerary.tourist_id` 可空；写接口用 `CurrentTouristDep` | 单测：未登录 401 |
| BR-05 | 预算/天数/人数区间 | `condition_service` | `tests/test_conditions.py` |
| BR-10 | 单次规划外部调用 ≤ 60 | `adapters/call_budget.py`、`Settings.plan_external_call_limit` | `tests/test_traffic_adapter.py`、plan_service 用例 |
| BR-14 | 历史版本 ≤ 10 | 设计于 `adjust_service`（未落地） | 待 #8 后的调整类用例 |
| BR-15 | 调序只重算相邻两项 | 设计于 `adjust_service`（未落地） | 待 #8 |
| BR-17 | 分享链接防遍历 | `core/security.py::sign_share_token/verify_share_token` | `tests/test_security.py` |
| BR-23 | 权重和 = 1，允差 ±0.01 | `config.py::STRATEGY_WEIGHTS_TOLERANCE`、`engine/scorer.py` | `test_strategy_engine.py::TestWeightsTolerance` |

## A.3 非功能需求追踪

| 指标 | 目标 | 现状证据 | 测量前提（必须一起写） |
|---|---|---|---|
| 行程生成 P95 | ≤ 10s | 待第 2 次报告压测节 | 300 POI / 15 天上限 / 外部缓存命中 / 单次重试 ≤ 2 |
| 结果页首屏 | ≤ 3s | 服务端渲染直出 | 本地 SQLite、冷启动、无外部依赖 |
| 调序重算 | ≤ 1.5s | 设计目标（未实现） | 只重算相邻两项、地图缓存命中 |
| 并发 | 200 规划请求 | CI 的 Perf Baseline job（不设门禁） | 4 workers / 连接池 10 / 外部信号量限流 |

## A.4 文档一致性自检

| 检查项 | 结果 |
|---|---|
| 接口数量：`docs/api.md` 章节 ↔ `backend/app/api/` 实际路由 | 已对齐（`auth.py`/`tourist.py`/`conditions.py`/`itineraries.py`/`admin_strategy.py`/`health.py`） |
| 表数量：本册第 5 章 ↔ `migrations/0002-0004` | 5 张已实现表；SRS 中 `preference`/`travel_condition`/`poi`/`crowd_index`/`feedback` 为**设计值，尚未建表**，第 5 章必须显式标注 |
| 状态机：SRS 状态图 ↔ `models/itinerary.py` 常量 | 代码仅定义 `PROPOSED/ADJUSTED/CONFIRMED` 三态，SRS 六态需在第 5 章对齐并说明差异 |
| ADR 编号：本册第 6 章 ↔ `docs/adr/` | 7 条一一对应 |
