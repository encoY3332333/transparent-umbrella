# 接口清单（API Specification）

> **本文件是前后端并行开发的契约**。先定接口，再各写各的实现——这是 ADR-002 的直接后果。
>
> 改动规则：任何**路径、请求字段、响应字段、错误码**的变更，都必须先提 Issue，PR 描述里标注「**破坏性变更**」，并同时通知前端与后端对接人。不允许在功能分支里悄悄改。

## 0. 通用约定

### 0.1 基础

| 项 | 约定 |
|---|---|
| Base URL | `http://localhost:8000`（开发）/ `https://<domain>`（演示） |
| 前缀 | 所有业务接口以 `/api` 开头 |
| 编码 | UTF-8，`Content-Type: application/json` |
| 时间格式 | 日期 `YYYY-MM-DD`；日期时间 `YYYY-MM-DDTHH:MM:SS`（ISO 8601，无时区，按服务器本地时区解释） |
| 金额 | 十进制数，单位**元**，JSON 中为 number，保留 2 位小数 |
| 分页 | `?page=1&size=20`（page 从 1 开始），响应含 `page` `size` `total` `pages` |
| 鉴权 | **HttpOnly Cookie**：登录成功后服务端下发 `access_token`（`HttpOnly; SameSite=Lax; Path=/`），浏览器自动携带。除标注「公开」的接口外均需登录（ADR-001 复核节） |

### 0.2 统一响应体

**成功**（HTTP 200/201）：

```json
{
  "code": "OK",
  "message": "success",
  "data": { }
}
```

**失败**（HTTP 4xx/5xx）：

```json
{
  "code": "CONDITION_INVALID_DATE_RANGE",
  "message": "结束日期不能早于开始日期",
  "details": [
    { "field": "endDate", "reason": "must be on or after startDate" }
  ],
  "traceId": "b3f1c2a4e5d6"
}
```

- `code`：**机器可读**，前端按 code 分支处理，不解析 message
- `message`：**面向用户**的中文提示，前端可直接展示
- `details`：可选，字段级错误数组；表单校验失败时必填
- `traceId`：可选，服务端生成的请求追踪号，便于日志定位

### 0.3 错误码表

**通用**

| code | HTTP | 含义 | 前端处理建议 |
|---|---|---|---|
| `OK` | 200 | 成功 | — |
| `PARAM_INVALID` | 400 | 参数校验失败 | 展示 `details` 中的字段错误 |
| `UNAUTHORIZED` | 401 | 未登录 / token 过期 | 清除 Cookie，跳转登录 |
| `FORBIDDEN` | 403 | 无权限（如非管理员访问后台） | 提示无权限并返回上一页 |
| `NOT_FOUND` | 404 | 资源不存在 | 展示空状态页 |
| `CONFLICT` | 409 | 状态冲突（如重复保存） | 提示并刷新数据 |
| `RATE_LIMITED` | 429 | 请求过于频繁 | 提示稍后重试 |
| `INTERNAL_ERROR` | 500 | 服务端异常 | 提示并展示 traceId |

**认证（UC-01）**

| code | HTTP | 含义 |
|---|---|---|
| `SMS_CODE_INVALID` | 400 | 验证码错误 |
| `SMS_CODE_EXPIRED` | 400 | 验证码已过期（5 分钟） |
| `SMS_SEND_TOO_FREQUENT` | 429 | 同一手机号 60 秒内重复请求 |
| `AUTH_SERVICE_UNAVAILABLE` | 503 | 认证服务不可用（降级：已登录用户可继续，见 architecture 6.2） |

**出行条件（UC-02）**

| code | HTTP | 含义 | 对应规则 |
|---|---|---|---|
| `CONDITION_INVALID_DATE_RANGE` | 400 | `endDate < startDate` | BR-04 |
| `CONDITION_DURATION_OUT_OF_RANGE` | 400 | 天数不在 [1,15] | BR-05 |
| `CONDITION_BUDGET_OUT_OF_RANGE` | 400 | 预算不在 [500,200000] | BR-06 |
| `CONDITION_PARTY_SIZE_OUT_OF_RANGE` | 400 | 人数不在 [1,20] | BR-07 |
| `CONDITION_TOO_MANY_TAGS` | 400 | 偏好标签超过 6 个 | BR-02 |
| `CONDITION_CITY_UNRESOLVED` | 400 | 城市名无法解析为坐标 | BR-11 |
| `CONDITION_MUST_VISIT_CONFLICT` | 400 | 必去与必避列表有交集 | BR-09 |

**行程生成（UC-03）**

| code | HTTP | 含义 | 对应规则 |
|---|---|---|---|
| `PLAN_NO_CANDIDATE` | 422 | 候选 POI 不足（少于 1 天所需） | BR-08 |
| `PLAN_INFEASIBLE` | 422 | 无法生成满足硬约束的方案 | BR-09 |
| `PLAN_BUDGET_TOO_LOW` | 422 | 迭代降本后仍超预算 | BR-12 |
| `EXTERNAL_CALL_LIMIT_EXCEEDED` | 503 | 单次生成外部调用超过 60 次 | BR-10 |
| `EXTERNAL_SERVICE_DEGRADED` | 200 | **不是错误**，响应体 `data.degraded[]` 中列出降级项 | — |

**行程调整（UC-05）**

| code | HTTP | 含义 | 对应规则 |
|---|---|---|---|
| `ADJUST_LOCKED_ACTIVITY` | 409 | 试图移动已锁定的活动 | BR-16 |
| `ADJUST_TIME_OVERLAP` | 409 | 调整后同日时间重叠 | BR-14 |
| `ADJUST_POI_UNAVAILABLE` | 409 | 替换目标 POI 已下架 | — |
| `ADJUST_VERSION_LIMIT` | 409 | 历史版本已达 10 个 | BR-14 |

**分享（UC-06）**

| code | HTTP | 含义 |
|---|---|---|
| `SHARE_TOKEN_INVALID` | 400 | 分享链接签名校验失败或已失效 |
| `SHARE_ITINERARY_NOT_FOUND` | 404 | 分享的行程已被删除 |

---

## 1. 认证与偏好（UC-01）

### 1.1 发送验证码 `公开`

```
POST /api/auth/sms-code
```

**请求**

```json
{ "phone": "13800138000" }
```

**响应**

```json
{ "code": "OK", "message": "success", "data": { "expiresIn": 300 } }
```

**说明**：同一手机号 60 秒内只能请求一次；验证码 5 分钟有效。开发环境下若未配置短信服务，验证码固定为 `123456` 并打印到日志。

---

### 1.2 登录 `公开`

```
POST /api/auth/login
```

**请求**

```json
{
  "phone": "13800138000",
  "smsCode": "123456"
}
```

**响应**

```json
{
  "code": "OK",
  "data": {
    "accessToken": "eyJhbGciOiJIUzI1NiJ9...",
    "expiresIn": 86400,
    "tourist": {
      "id": 1001,
      "phone": "138****8000",
      "nickname": "游客1001",
      "hasPreference": false
    }
  }
}
```

**说明**：`hasPreference = false` 时前端弹出偏好设置浮层（S1 界面）。首次登录自动创建 `tourist` 记录。

---

### 1.3 查询我的偏好

```
GET /api/tourists/me/preference
```

**响应**

```json
{
  "code": "OK",
  "data": {
    "id": 201,
    "preferenceTags": ["人文历史", "美食"],
    "partyType": "COUPLE",
    "pace": "RELAXED",
    "budgetLevel": "COMFORT",
    "updatedAt": "2026-11-09T20:30:00"
  }
}
```

未建档时 `data` 为 `null`，不返回 404。

---

### 1.4 保存偏好

```
PUT /api/tourists/me/preference
```

**请求**

```json
{
  "preferenceTags": ["人文历史", "美食", "摄影"],
  "partyType": "COUPLE",
  "pace": "RELAXED",
  "budgetLevel": "COMFORT"
}
```

| 字段 | 类型 | 必填 | 取值 |
|---|---|---|---|
| `preferenceTags` | string[] | 是 | 人文历史 / 自然风光 / 亲子 / 美食 / 摄影 / 夜生活，≤ 6 个 |
| `partyType` | enum | 是 | `SOLO` / `COUPLE` / `FAMILY` / `FRIENDS` |
| `pace` | enum | 是 | `TIGHT` / `MODERATE` / `RELAXED` |
| `budgetLevel` | enum | 是 | `ECONOMY` / `COMFORT` / `QUALITY` |

**响应**：同 1.3 的 `data`。

---

## 2. 出行条件（UC-02）

### 2.1 校验出行条件 `公开`

```
POST /api/conditions/validate
```

**用途**：前端「下一步」按钮点击时先调此接口做**服务端校验**，通过后才进入生成流程。前端本地校验只做必填与格式，业务规则一律以本接口为准。

**请求**

```json
{
  "originCity": "杭州",
  "destCity": "西安",
  "startDate": "2026-12-01",
  "endDate": "2026-12-04",
  "budget": 6000.00,
  "partySize": 2,
  "partyType": "COUPLE",
  "preferenceTags": ["人文历史", "美食"],
  "mustVisit": [101, 205],
  "avoidPOI": [310]
}
```

**响应（通过）**

```json
{
  "code": "OK",
  "data": {
    "valid": true,
    "days": 4,
    "resolved": {
      "origin": { "city": "杭州", "lat": 30.274085, "lng": 120.155070 },
      "dest":   { "city": "西安", "lat": 34.341568, "lng": 108.940174 }
    },
    "budgetBreakdownHint": { "perDay": 1500.00, "perPersonPerDay": 750.00 },
    "warnings": []
  }
}
```

**响应（不通过）**

```json
{
  "code": "CONDITION_DURATION_OUT_OF_RANGE",
  "message": "行程天数须在 1 到 15 天之间",
  "details": [{ "field": "endDate", "reason": "duration=20, allowed=[1,15]" }]
}
```

**warnings 示例**（不影响通过，仅提示）：

- `BUDGET_TIGHT`：人均日预算低于 300 元，可能只能安排经济型方案
- `WEATHER_RISK`：行程中包含暴雨橙色预警日期

---

## 3. 行程生成（UC-03）

### 3.1 生成行程

```
POST /api/itineraries/generate
```

**请求**：与 2.1 相同（服务端会重新走一遍校验，不信任前端）。

可选参数：

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `variantCount` | int | 2 | 返回方案数，1–3 |
| `seed` | long | 随机 | 用于复现同一套方案（测试与演示用） |

**响应**

```json
{
  "code": "OK",
  "data": {
    "itineraries": [
      {
        "id": 3001,
        "title": "西安 4 日 · 人文深度线",
        "status": "PROPOSED",
        "version": 1,
        "totalCost": 5680.00,
        "budget": 6000.00,
        "budgetBreakdown": {
          "ticket": 820.00,
          "meal": 1200.00,
          "hotel": 2400.00,
          "transit": 1260.00
        },
        "score": {
          "total": 78.4,
          "preference": 0.86,
          "weather": 0.92,
          "crowd": 0.35,
          "travel": 0.71,
          "cost": 0.63
        },
        "reasons": [
          "偏好匹配：4 个景点中有 3 个属于你选择的人文历史类",
          "天气：12 月 2 日有雨，已将室内景点（陕西历史博物馆）排在该日",
          "拥挤度：避开 12 月 3 日周末高峰，兵马俑安排在工作日"
        ],
        "days": [
          {
            "dayIndex": 1,
            "date": "2026-12-01",
            "weather": { "condition": "晴", "tempHigh": 9, "tempLow": 1, "risk": "NONE" },
            "activities": [
              {
                "id": 40001,
                "poiId": 205,
                "poiName": "陕西历史博物馆",
                "category": "SIGHT",
                "startTime": "2026-12-01T09:00:00",
                "endTime": "2026-12-01T11:30:00",
                "cost": 0.00,
                "isEstimated": false,
                "locked": false,
                "crowdIndex": 42,
                "lat": 34.222680,
                "lng": 108.945680
              }
            ]
          }
        ]
      }
    ],
    "degraded": ["WEATHER", "HOTEL"],
    "durationMs": 4820,
    "strategyVersion": 3
  }
}
```

**要点**

- `degraded[]` 中的每一项对应 `architecture.md` 6.2 的降级表，前端需在结果页顶部展示对应提示
- `reasons[]` 由 `ScoreCalculator` 的分数分解生成，是产品的差异化卖点（ADR-003）
- `durationMs` 便于前端在超时提示中展示；P95 ≤ 10 秒（NFR-P1）
- **生成结果的 `status = PROPOSED`，用户未确认前不会出现在「我的行程」列表里**

---

### 3.2 放弃生成结果

```
DELETE /api/itineraries/{id}/proposed
```

**用途**：用户点了「重新生成」，前端主动弃用旧方案，服务端将其 `status` 置为 `ARCHIVED`，避免 `PROPOSED` 记录堆积。

**响应**：`{ "code": "OK", "data": null }`

---

## 4. 行程查看（UC-04）

### 4.1 行程详情

```
GET /api/itineraries/{id}
```

响应结构同 3.1 中 `itineraries[i]`，额外字段：

| 字段 | 说明 |
|---|---|
| `createdAt` / `updatedAt` | 创建与最后修改时间 |
| `shareToken` | 已生成分享链接时返回，否则 `null` |

**权限**：非本人访问返回 `FORBIDDEN`（分享场景走 7.1）。

---

### 4.2 我的行程列表

```
GET /api/itineraries?status=SAVED&page=0&size=10
```

**响应**

```json
{
  "code": "OK",
  "data": {
    "content": [
      {
        "id": 3001,
        "title": "西安 4 日 · 人文深度线",
        "destCity": "西安",
        "startDate": "2026-12-01",
        "endDate": "2026-12-04",
        "totalCost": 5680.00,
        "status": "SAVED",
        "coverImage": "https://.../poi-205.jpg",
        "updatedAt": "2026-11-09T21:00:00"
      }
    ],
    "page": 0, "size": 10, "totalElements": 3, "totalPages": 1
  }
}
```

**status 过滤值**：`SAVED`（默认）/ `COMPLETED` / `ARCHIVED` / `ALL`
**说明**：列表**不返回** `PROPOSED` 和 `SUPERSEDED`。

---

### 4.3 导出 ICS 日历

```
GET /api/itineraries/{id}/export.ics
```

**响应**：`Content-Type: text/calendar; charset=utf-8`，`Content-Disposition: attachment; filename="itinerary-3001.ics"`

**说明**：每个 `Activity` 生成一个 `VEVENT`，`SUMMARY` 为 POI 名称，`LOCATION` 为经纬度，`DTSTART/DTEND` 用本地时间无时区格式。

---

## 5. 行程调整（UC-05）

> 预览与保存两个接口**共用同一段应用操作的代码**（ADR-005），区别仅在是否落库。

### 5.1 预览调整（不落库）

```
PUT /api/itineraries/{id}/preview-adjust
```

**请求**

```json
{
  "operations": [
    { "op": "MOVE", "activityId": 40003, "targetDay": 2, "targetIndex": 1 },
    { "op": "REPLACE", "activityId": 40005, "newPoiId": 218 },
    { "op": "DELETE", "activityId": 40007 },
    { "op": "INSERT", "dayIndex": 3, "poiId": 230, "startTime": "2026-12-03T14:00:00" },
    { "op": "REORDER_LOCKED", "dayIndex": 2 }
  ]
}
```

**操作类型**

| op | 必填字段 | 说明 |
|---|---|---|
| `MOVE` | `activityId`, `targetDay`, `targetIndex` | 拖拽调序（含跨天） |
| `REPLACE` | `activityId`, `newPoiId` | 替换为同城其他 POI |
| `DELETE` | `activityId` | 删除活动 |
| `INSERT` | `dayIndex`, `poiId`, `startTime` | 新增活动 |
| `LOCK` / `UNLOCK` | `activityId` | 锁定/解锁，锁定的活动不参与重排 |
| `REORDER_LOCKED` | `dayIndex` | 保持锁定项不动，重排其余 |

**响应**：完整行程视图（结构同 4.1）+ 冲突清单

```json
{
  "code": "OK",
  "data": {
    "itinerary": { "id": 3001, "days": [] },
    "conflicts": [
      {
        "type": "TIME_OVERLAP",
        "severity": "ERROR",
        "activityId": 40003,
        "message": "与「碑林博物馆」时间重叠 30 分钟",
        "suggestion": "将开始时间推迟至 14:30"
      },
      {
        "type": "BUDGET_EXCEEDED",
        "severity": "WARN",
        "message": "调整后总费用 6120 元，超出预算 120 元",
        "suggestion": null
      }
    ],
    "affectedActivities": [40002, 40003, 40004]
  }
}
```

**性能**：调序响应 ≤ 1.5 秒（NFR-P4），只重算受影响的相邻两项通勤时长（BR-15）。

---

### 5.2 保存调整（落库）

```
PUT /api/itineraries/{id}/adjust
```

**请求**：与 5.1 完全相同。

**响应**：`{ "code": "OK", "data": { "id": 3001, "version": 2, "updatedAt": "..." } }`

**事务行为**：`version + 1`，旧版本 `status` 置为 `SUPERSEDED`；超过 10 个历史版本时返回 `ADJUST_VERSION_LIMIT`（BR-14）。

**幂等**：请求头带 `Idempotency-Key`（前端生成的 UUID），重复提交返回首次结果，避免用户双击产生两个版本。

---

### 5.3 版本历史

```
GET /api/itineraries/{id}/versions
```

**响应**：版本号、状态、创建时间、总费用的数组，按 `version` 倒序。

**说明**：本课程版本**不支持回滚到历史版本**，仅展示。这是一个明确的边界，写在 SRS 的「不做什么」里，避免答辩时被追问而答不上来。

---

## 6. 保存（UC-06）

### 6.1 保存行程

```
POST /api/itineraries/{id}/save
```

**请求**

```json
{ "title": "西安 4 日 · 人文深度线" }
```

**响应**：`{ "code": "OK", "data": { "id": 3001, "status": "SAVED" } }`

**状态机**：`PROPOSED → SAVED`。若当前不是 `PROPOSED`，返回 `CONFLICT`。

**未登录**处理：本接口需鉴权。页面在 `PROPOSED` 结果页点「保存」时若未登录，先跳登录，登录成功后回到原 `id` 继续。

---

## 7. 分享（UC-06）

### 7.1 生成分享链接

```
POST /api/itineraries/{id}/share
```

**请求**（可选）

```json
{ "expiresInDays": 7 }
```

**响应**

```json
{
  "code": "OK",
  "data": {
    "token": "eyJpZCI6MzAwMSwiaWF0IjoxNzYyNjg0MDAwfQ.a3f9c1",
    "url": "http://localhost:8000/share/eyJpZCI6MzAwMSwiaWF0IjoxNzYyNjg0MDAwfQ.a3f9c1",
    "expiresAt": "2026-11-16T21:00:00"
  }
}
```

**安全**：token 用 HMAC-SHA256 签名（BR-17），防遍历。响应体为独立的 `ShareItineraryOut`，不含手机号、真实姓名等字段。

---

### 7.2 查看分享行程 `公开`

```
GET /api/share/{token}
```

**响应**：脱敏后的行程视图，不含 `touristId`、`phone`、`version`。

**失败**：token 无效返回 `SHARE_TOKEN_INVALID`；行程已删除返回 `SHARE_ITINERARY_NOT_FOUND`。

---

## 8. 反馈（UC-07）

### 8.1 提交反馈

```
POST /api/itineraries/{id}/feedback
```

**请求**

```json
{
  "rating": 4,
  "tags": ["行程太赶", "推荐不准确"],
  "comment": "第三天安排有点满，希望留出休息时间"
}
```

| 字段 | 约束 |
|---|---|
| `rating` | 1–5 整数，必填 |
| `tags` | 0–5 个，从预设标签中选择 |
| `comment` | ≤ 500 字，选填 |

**响应**：`{ "code": "OK", "data": { "id": 501, "strategyVersion": 3 } }`

**说明**：反馈记录关联生成时所用的策略版本号（BR-20），用于后续分析。

---

### 8.2 查询预设标签 `公开`

```
GET /api/feedback/tags
```

**响应**：`{ "code": "OK", "data": ["行程太赶", "行程太松", "推荐不准确", "预算估算偏差大", "交通衔接不合理", "其他"] }`

---

## 9. 后台：POI 管理（UC-08）

> 以下接口均需管理员权限，非管理员返回 `FORBIDDEN`。

### 9.1 POI 列表

```
GET /api/admin/pois?city=西安&status=PUBLISHED&keyword=博物馆&page=0&size=20
```

**响应**：分页的 POI 摘要列表。

---

### 9.2 POI 详情

```
GET /api/admin/pois/{id}
```

**响应**

```json
{
  "code": "OK",
  "data": {
    "id": 205,
    "name": "陕西历史博物馆",
    "city": "西安",
    "category": "INDOOR",
    "lat": 34.222680,
    "lng": 108.945680,
    "openTime": "09:00",
    "closeTime": "17:30",
    "crossMidnight": false,
    "price": 0.00,
    "capacity": 12000,
    "tags": ["人文历史"],
    "status": "PUBLISHED",
    "updatedAt": "2026-11-01T10:00:00"
  }
}
```

---

### 9.3 新增 / 修改 POI

```
POST /api/admin/pois
PUT  /api/admin/pois/{id}
```

**请求**：同 9.2 的 `data`（去掉 `id`、`updatedAt`）。

**字段校验**

| 字段 | 约束 |
|---|---|
| `lat` / `lng` | `lat ∈ [-90,90]`、`lng ∈ [-180,180]` |
| `price` | ≥ 0 |
| `capacity` | ∈ [1, 200000]（BR-21） |
| `openTime` / `closeTime` | `HH:mm`；跨天营业须 `crossMidnight = true` |

---

### 9.4 下架 POI

```
PATCH /api/admin/pois/{id}/status
```

**请求**：`{ "status": "INACTIVE" }`（取值 `DRAFT` / `PUBLISHED` / `INACTIVE`）

**说明**：下架不影响已保存行程中的历史引用（活动记录冗余存了 `poiName`），但新的生成与替换操作不会再选中它。

---

## 10. 后台：策略参数（UC-09）

### 10.1 当前生效策略

```
GET /api/admin/strategies/current
```

**响应**

```json
{
  "code": "OK",
  "data": {
    "version": 3,
    "weights": {
      "preference": 0.10, "weather": 0.25, "crowd": 0.23,
      "travel": 0.14, "cost": 0.28
    },
    "holidayFactors": { "春节": 2.2, "国庆": 1.8, "普通周末": 1.3, "工作日": 1.0 },
    "effectiveFrom": "2026-11-05T00:00:00",
    "createdBy": "admin"
  }
}
```

---

### 10.2 发布新策略

```
POST /api/admin/strategies
```

**请求**：同 10.1 的 `data`（去掉 `version`、`effectiveFrom`、`createdBy`）。

**校验**：五项权重**和必须等于 1**（误差 < 0.001），否则返回 `PARAM_INVALID` 并指名字段 `weights`（BR-23）。

**行为**：版本号自增，旧版本保留不可删（BR-24）。新策略只影响**此后**的生成请求，已生成的行程不回溯。

---

### 10.3 策略版本历史

```
GET /api/admin/strategies
```

**响应**：版本号、权重、生效时间、创建人的列表，按版本倒序。

---

## 11. 健康检查 `公开`

```
GET /actuator/health
```

**响应**：`{ "status": "UP", "components": { "db": {"status":"UP"} } }`

**用途**：CI 的冒烟测试、`docker compose` 的 healthcheck。

---

## 附：接口与用例对照

| 用例 | 接口 |
|---|---|
| UC-01 登录与偏好 | 1.1 / 1.2 / 1.3 / 1.4 |
| UC-02 出行条件 | 2.1 |
| UC-03 行程生成 | 3.1 / 3.2 |
| UC-04 行程查看 | 4.1 / 4.2 / 4.3 |
| UC-05 行程调整 | 5.1 / 5.2 / 5.3 |
| UC-06 保存与分享 | 6.1 / 7.1 / 7.2 |
| UC-07 反馈 | 8.1 / 8.2 |
| UC-08 POI 维护 | 9.1 – 9.4 |
| UC-09 策略配置 | 10.1 – 10.3 |

## 修订记录

| 日期 | 版本 | 修订人 | 说明 |
|---|---|---|---|
| 2026-11-09 | v0.1 | 【组长】 | 初稿：9 个用例的接口契约、统一响应体、39 个错误码 |
