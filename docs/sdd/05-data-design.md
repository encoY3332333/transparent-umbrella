# 第 5 章 数据设计

> 负责人：B（刘婕）｜骨架由 A 搭建，表清单与列名已从 `backend/app/models/` 与 `migrations/0002–0004` 抄出，`⬜` 处需补齐。
> **红线**：本章的 ER 图与表清单必须与 `migrations/` 完全一致。SRS 里写的表若尚未建表，只能放在"设计值"小节并显式标注，不能混进"已实现"清单——第 1 次批阅扣分的第 4 条就是模型图与实现不同步。

## 5.1 已实现表（以迁移为准，共 5 张）

| 表 | 迁移 | 用途 | 关键约束 | 索引 |
|---|---|---|---|---|
| `itinerary` | 0002 | 行程主表（一套候选方案） | `batch_id` 关联同批方案；`status ∈ {PROPOSED, ADJUSTED, CONFIRMED}`；`tourist_id` 可空（BR-03） | `batch_id`、`status`、`tourist_id` |
| `itinerary_day` | 0002 | 行程的一天的容器 | `day_index` 从 0 开始；外键 → `itinerary` | 组合索引见 0002 |
| `itinerary_activity` | 0002 | 一天内的单个活动 | 指向 POI；含起止时间、费用、通勤时长 | 外键 → `itinerary_day` |
| `strategy_parameter` | 0003 | 策略参数版本 | 五项权重和 = 1（允差 ±0.01，BR-23）；版本不可删（BR-24）；`effective_from` 决定"当前生效版本" | `version` |
| `tourist` | 0004 | 登录游客 | `phone` 唯一（BR-01）；偏好标签 JSON；`preference_saved_at` 判断是否建档 | `phone` 唯一 |

列级明细请直接从模型读，不在此重复抄写（列一改就不同步）：

```
backend/app/models/itinerary.py   → Itinerary / ItineraryDay / Activity
backend/app/models/strategy.py    → StrategyParameter
backend/app/models/tourist.py     → Tourist
```

⬜ B 需补：把上述 5 张表整理成**列级数据字典**（列名 / 类型 / 可空 / 默认 / 含义 / 对应 BR 编号），建议直接由模型生成后人工校对一遍。

## 5.2 ER 图

⬜ B 需补 `docs/diagrams/er.puml`，至少覆盖：

```
tourist ──1:0..*── itinerary ──1:1..15── itinerary_day ──1:1..*── itinerary_activity
strategy_parameter（独立表，无外键）
```

绘图要求：实体名与表名一致；每张表标注迁移文件编号；**不要**画出还没建的表（`poi` / `feedback` 等），否则图与库不一致。

## 5.3 状态机（必须与代码常量对齐）

代码里 `models/itinerary.py::ItineraryStatus` 只定义了三个值：

```
PROPOSED ──(用户调整并确认)──► ADJUSTED ──(用户保存)──► CONFIRMED
```

而 SRS 的状态图写了六态（含 `SUPERSEDED`、`SHARED`、`EXPIRED` 等）。⬜ B 需补：

- [ ] 明确列出"代码已支持"的三态与"设计中有"的六态的差异表
- [ ] 说明 `SUPERSEDED`（旧版本）将在 #8 引入，落在 `itinerary.version` 与 `status` 上
- [ ] 状态迁移的触发点指回接口（调整 / 确认 / 保存）

## 5.4 设计值表（尚未建表，禁止标为已实现）

| 表 | SRS 出处 | 现状 | 计划 Issue |
|---|---|---|---|
| `preference` | SRS 附录 A | ❌ 未建表（已并入 `tourist` 四列） | 不需要单独建，需在 SRS 侧同步说明 |
| `travel_condition` | SRS 附录 A | ❌ 未建表（当前条件随请求传入，只存进行程） | 若要支持"条件复用"再建表 |
| `poi` | UC-08 | ❌ 未建表（`poi_repository` 读的是内存/种子数据） | #7 / UC-08 |
| `crowd_index` | UC-03 / ADR-006 | ❌ 未建表（拥挤度实时计算，不落快照） | 需要历史对比时再落 |
| `feedback` | UC-07 | ❌ 未建表 | #11 |

⬜ B 需补：为每张设计值表写"为什么现在不建"（如 `preference` 并入 `tourist` 是为减少一次 join 且字段少），以及"什么条件下才建"。

## 5.5 迁移策略

| 约定 | 内容 |
|---|---|
| 版本链 | `0001 baseline → 0002 itinerary → 0003 strategy → 0004 tourist` |
| 手写 vs autogenerate | 新表手写 `create_table`；加列/加约束一律走 `op.batch_alter_table`（SQLite 不支持 ALTER 约束） |
| 往返验证 | 每次迁移都必须 `upgrade → downgrade → upgrade` 往返一次（`0004` 已验证） |
| 命名约定 | `base.py` 的 `MetaData(naming_convention=...)` 统一约束命名，避免 SQLite 匿名约束无法 drop |

## 5.6 本章自检清单

- [ ] 表清单与 `migrations/0002–0004` 逐张对齐，数量一致（5 张）
- [ ] ER 图不含未建表
- [ ] 状态机与 `ItineraryStatus` 常量一致，差异有说明
- [ ] 每张设计值表都有"为什么不建"与"何时建"
