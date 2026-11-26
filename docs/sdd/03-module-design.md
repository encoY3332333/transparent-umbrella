# 第 3 章 模块设计

> 负责人：C（铁昳萱）｜骨架由 A 搭建，已把能直接从代码读到的内容预填，`⬜` 标记处需补齐。
> 写作要求：每个模块写"职责 → 对外接口（类/函数签名）→ 协作关系 → 异常路径"；图必须标注源文件路径。

## 3.0 本章结构

| 小节 | 模块 | 预填状态 |
|---|---|---|
| 3.1 | 认证与偏好（`services/auth_service.py`、`api/auth.py`、`api/tourist.py`） | ✅ 已预填 |
| 3.2 | 条件校验（`services/condition_service.py`） | ✅ 已预填 |
| 3.3 | 生成编排（`services/plan_service.py`、`engine_bridge.py`） | ⬜ 待补：时序图 + 事务边界 |
| 3.4 | 排程引擎（`engine/*.py`） | ✅ 已预填（类清单）⬜ 待补：类图 |
| 3.5 | 行程调整（`adjust_service`，规划中） | ⬜ 待补：设计说明（当前无实现，写清"仅设计"） |
| 3.6 | 保存与分享（规划中） | ⬜ 待补 |
| 3.7 | 反馈（规划中） | ⬜ 待补 |
| 3.8 | POI 维护（规划中，现有只读仓储） | ⬜ 待补 |
| 3.9 | 策略参数（`services/strategy_service.py`） | ⬜ 待补 |
| 3.10 | 页面渲染（`api/pages.py`） | ⬜ 待补（**必须标注哪些页面数据是 mock**） |

## 3.1 认证与偏好模块（UC-01）

**职责**：把"手机号 + 验证码"换成可跨请求识别的登录态，并提供偏好档案的读写。

**对外接口**

| 符号 | 位置 | 签名要点 | 说明 |
|---|---|---|---|
| `request_code` | `services/auth_service.py` | `(session, settings, phone, *, now=None) -> (expires_in, debug_code)` | 60s 频控，超频抛 `SMS_SEND_TOO_FREQUENT` |
| `verify_code` | 同上 | `(phone, code, *, now=None) -> None` | 过期抛 `SMS_CODE_EXPIRED`，错误抛 `SMS_CODE_INVALID`，成功即作废 |
| `login` | 同上 | `(session, settings, phone, code, *, now=None) -> Tourist` | 首次登录即注册；连续失败达 `login_max_attempts` 后锁定 |
| `save_preferences` | 同上 | `(session, tourist, *, tags, party_type, pace, budget_level, now=None) -> Tourist` | 标签去空去重保序，上限 6 |
| `create_access_token` / `tourist_id_from_token` | `core/security.py` | `(tourist_id, settings) -> (token, expires_in)` / `(token, settings) -> int` | JWT；`exp` 自行校验（pyjwt 2.9–3.0 不支持 `now` 参数） |
| `get_optional_tourist` / `get_current_tourist` | `core/deps.py` | FastAPI 依赖 | Cookie 优先，其次 `Authorization: Bearer`；无效 token 一律当未登录 |

**协作关系（登录时序）**

```
浏览器 → POST /api/auth/sms-code → auth_service.request_code → 内存码表（phone → code, ttl=300s）
浏览器 → POST /api/auth/login    → auth_service.login
                                    ├ verify_code（一次性作废）
                                    ├ 失败计数 → 达上限锁定 login_lock_minutes
                                    ├ get_or_create Tourist
                                    └ 返回 Tourist → api/auth.py 写 HttpOnly Cookie
浏览器 → GET /api/auth/me        → get_optional_tourist（Cookie → JWT → Tourist）
```

**异常路径**

| 场景 | 错误码 | HTTP | 前端行为 |
|---|---|---|---|
| 60 秒内重复请求验证码 | `SMS_SEND_TOO_FREQUENT` | 400 | 按钮倒计时禁用 |
| 验证码过期 | `SMS_CODE_EXPIRED` | 400 | 提示重新获取 |
| 验证码错误 | `SMS_CODE_INVALID` | 400 | 提示重试，计入失败次数 |
| 失败次数超限 | `RATE_LIMITED` | 429 | 提示锁定分钟数 |
| 未登录访问偏好写入 | `UNAUTHORIZED` | 401 | 跳转登录 |
| 标签超 6 个 | `CONDITION_TOO_MANY_TAGS` | 400 | 高亮多选控件 |

**设计说明（答辩可能追问）**

- 验证码**不落库**：它是一次性短时效凭证，落库只多一处敏感数据；接真实短信网关时只替换 `_send_sms()`。
- `debugCode` 仅非生产环境返回，生产环境恒为 `null`——否则等于把验证码印在响应里。
- 响应中的手机号脱敏为 `138****8000`，明文只存服务端。

## 3.2 条件校验模块（UC-02）

| 符号 | 位置 | 说明 |
|---|---|---|
| `validate_condition` | `services/condition_service.py` | 跨字段业务规则：天数 1–15、预算 500–200000、人数 1–20、必去/必避冲突、城市可解析 |
| `_lookup_city` | 同上 | 城市名 → 坐标；无法解析抛 `CONDITION_CITY_UNRESOLVED` |
| `_fail` | 同上 | 统一抛 `BusinessError` 并携带 `FieldError` 列表 |

**协作关系**：Pydantic 只拦类型（`TravelConditionIn`），业务规则在 service 拦。这样同一个规则在页面表单与 API 两侧的行为一致，且错误码统一。

## 3.3 生成编排模块（UC-03）⬜

需补齐：

- [ ] `plan_service.generate()` 的完整时序图（标出 `session.begin()` 位置）
- [ ] `engine_bridge` 的 ORM ↔ dataclass 转换清单（哪些字段映射到 `Candidate` / `PlanDraft`）
- [ ] `call_budget` 在每个外部调用点的扣减位置
- [ ] 事务边界说明：落库失败时外部调用已发生的后果
- [ ] 降级链：哪一步失败会导致 `degraded` 里出现 `WEATHER` / `CROWD` / `TRAVEL`

## 3.4 排程引擎模块（纯函数层）

> 关键约束：`engine/` 不得 import `models/`、`adapters/`、`sqlalchemy`（`docs/architecture.md` 分层约束第 3 条）。

| 文件 | 主要符号 | 职责 |
|---|---|---|
| `engine/protocols.py` | `Requirement`、`PlanContext`、`ActivityDraft`、`PlanDraft`、`Conflict`、`CandidateSelector`、`PlanPacker`、`FeasibilityChecker` | 三个子模块的接口契约（ADR-002） |
| `engine/selector.py` | `Poi`、`SelectionCriteria`、`Candidate`、`CandidateSelector`、`InsufficientPoiData` | 偏好/必去/必避过滤 + 规模收敛到 [20,300] |
| `engine/scorer.py` | `Weights`、`TouristProfile`、`Scorer`、`ScoreBreakdown` | 五项加权评分（`pref_match` / `weather_fit` / `travel_cost` / `cost_ratio` / `crowd_penalty`） |
| `engine/packer.py` | `Packer`、`DayPlan`、`PlanResult`、`PackError`、`build_reasons` | 按天贪心装箱，预留用餐/休息，产出推荐理由 |
| `engine/crowd.py` | `CrowdIndexCalculator`、`calculate_crowd_index`、`apply_crowd_index` | 历史同期均值 + 节假日系数（ADR-006） |
| `engine/travel.py` | `TravelMatrix`、`build_matrix`、`required_pairs` | 通勤矩阵；只算需要的那几对 |
| `engine/strategy_engine.py` | `StrategyEngine`、`PlanRequest`、`_scope_pool`、`_cheap_pool`、`_pref_pool` | 参数装载与多策略并行产出 |

⬜ 待补：一张类图（`docs/diagrams/class-engine.puml`），标注每个类的源文件；以及"评分公式"小节把 `scorer.py` 的公式如实抄成数学式。

## 3.5 行程调整（UC-05）⬜

**当前事实**：`adjust_service` **不存在**；调整页 `api/pages.py::adjustment_page` 为 mock 渲染，任意 `itinerary_id` 返回 200，无版本推进。
本章必须写成"设计 + 现状差异"，不得描述成已实现。

需补齐：

- [ ] 副本调整的状态机（`PROPOSED → ADJUSTED → CONFIRMED`，`SUPERSEDED` 用于旧版本）
- [ ] 版本上限 10 的判定位置（BR-14）
- [ ] "只重算相邻两项"的实现路径（BR-15）
- [ ] 404 判定：行程不存在 / 不属于当前用户

## 3.6 ~ 3.8 保存分享、反馈、POI 维护 ⬜

三个模块均**未落地**，对应 Issue #10（分享）、#11（反馈）、#7/#8 的依赖部分。写作要求：只写"设计意图 + 依赖关系"，状态标 `○`，并注明"待第 2 阶段实现"。

## 3.9 策略参数模块（UC-09）⬜

现有：`services/strategy_service.py`、`api/admin_strategy.py`、`models/strategy.py`、`migrations/0003`。
需补齐：版本发布事务、进程内缓存失效点、权重归一化与 ±0.01 允差的实现位置。

## 3.10 页面渲染模块 ⬜

现有路由：`/`、`/conditions/new`、`/conditions/validate`、`/itineraries/new`、`/itineraries/{id}/adjust`、`/admin/strategy`。
需补齐：**逐页标注数据来源**（真实 service / mock / 待联调）——这是老师批阅第 2 条的直接落点。

## 3.11 本章自检清单

- [ ] 每个类/函数都标了源文件路径
- [ ] 每个"规划中"模块都标了 `○` 与对应 Issue 编号
- [ ] 调整页、结果页明确写了"当前数据为 mock"
- [ ] 与第 4 章接口清单交叉一致（模块里的入口都能在第 4 章找到）
