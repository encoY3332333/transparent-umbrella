# 第 4 章 接口设计

> 负责人：C（铁昳萱）｜骨架由 A 搭建。**本章不重抄 `docs/api.md`**，只写"设计层面的约定 + 与代码的对应关系 + 差异说明"，字段级契约一律指向 `docs/api.md` 对应小节。

## 4.1 通用约定

| 约定 | 内容 | 实现位置 |
|---|---|---|
| 成功响应 | `{code:"OK", message:"success", data}` | `schemas/common.py::ApiResponse` |
| 失败响应 | `{code, message, details[], traceId}` | `core/handlers.py` |
| 错误码 | 集中在 `ErrorCode` + `ERROR_SPECS`，状态码也由它决定 | `core/errors.py` |
| 参数校验失败 | 统一 `PARAM_INVALID`（400），字段级明细进 `details[]` | `core/handlers.py::handle_validation_error` |
| 鉴权 | HttpOnly Cookie `access_token`；亦支持 `Authorization: Bearer` | `core/deps.py` |
| 分页 | `page` 从 1 开始，`size` 默认 20 | `schemas/common.py::PageMeta` |
| 追踪 | 每个响应带 `traceId`，与日志一致 | `core/logging.py` |

## 4.2 接口清单（以实际路由为准）

> 共 6 个 API 模块 + 1 个页面模块。标 `◐` 的接口存在 mock 或降级路径。

| # | 方法 | 路径 | 用例 | 模块 | 状态 |
|---|---|---|---|---|---|
| 1 | POST | `/api/auth/sms-code` | UC-01 | `api/auth.py` | ✅ |
| 2 | POST | `/api/auth/login` | UC-01 | `api/auth.py` | ✅ |
| 3 | POST | `/api/auth/logout` | UC-01 | `api/auth.py` | ✅ |
| 4 | GET | `/api/auth/me` | UC-01 | `api/auth.py` | ✅ |
| 5 | GET | `/api/tourists/me/preference` | UC-01 | `api/tourist.py` | ✅ |
| 6 | PUT | `/api/tourists/me/preference` | UC-01 | `api/tourist.py` | ✅ |
| 7 | POST | `/api/conditions/validate` | UC-02 | `api/conditions.py` | ✅ |
| 8 | POST | `/api/itineraries/generate` | UC-03 | `api/itineraries.py` | ✅（外部数据部分降级） |
| 9 | GET | `/api/health` | — | `api/health.py` | ✅ |
| 10 | GET | `/api/admin/strategies/current` | UC-09 | `api/admin_strategy.py` | ✅ |
| 11 | GET | `/api/admin/strategies` | UC-09 | `api/admin_strategy.py` | ✅ |
| 12 | POST | `/api/admin/strategies` | UC-09 | `api/admin_strategy.py` | ✅ |
| 13 | POST | `/api/admin/strategies/normalize` | UC-09 | `api/admin_strategy.py` | ✅ |
| 14 | POST | `/api/admin/strategies/rollback`（⬜ 待确认是否已实现） | UC-09 | `api/admin_strategy.py` | ⬜ |
| 15 | GET | `/pages/itineraries/{id}/adjust` | UC-05 | `api/pages.py` | ◐ mock |

⬜ **C 需要核对**：第 14 行的回滚接口在 `api/admin_strategy.py` 里只看到 5 个路由装饰器，是否含 rollback 需逐条核对后再定稿；若未实现，在第 4 章标 `○` 而不能保留在"已实现"清单里。

## 4.3 与 `docs/api.md` 的差异清单（必须写进本章）

| 项 | docs/api.md 写法 | 实际实现 | 处理 |
|---|---|---|---|
| 登录响应 | v0.1 回传 `accessToken` | 只下发 HttpOnly Cookie | 文档已改 v0.4 |
| 验证码字段 | `smsCode` | `code`（同时兼容 `smsCode`） | 文档已注明两者等价 |
| 偏好接口路径 | `/api/tourists/me/preference` | 同 | 一致 |
| 偏好字段 | tags/partyType/pace/budgetLevel | 同（`tourist` 表四列 + 建档时间） | 一致 |
| 未建档查询 | `data: null` | 同 | 一致 |

⬜ 待补：`docs/api.md` 第 5~8 章（调整、保存、分享、反馈）对应的接口**均未实现**，本章需列出"契约已定、实现待排期"的清单，标明 Issue 编号。

## 4.4 接口与鉴权的对应

| 鉴权级别 | 接口 | 依赖 |
|---|---|---|
| 公开 | `sms-code`、`login`、`conditions/validate`、`health`、页面 GET | 无 |
| 可选登录 | `auth/me`、`tourists/me/preference` GET | `get_optional_tourist` |
| 必须登录 | `tourists/me/preference` PUT、将来的保存/分享 | `get_current_tourist` |
| 管理员 | `api/admin/**`（⬜ 需确认当前是否已挂 admin 鉴权依赖） | ⬜ |

## 4.5 本章自检清单

- [ ] 接口清单与 `grep -rn "@router." backend/app/api/` 输出逐条一致，数量对得上
- [ ] 每个 `◐` 都写了"哪部分是 mock / 哪部分降级"
- [ ] 未实现接口明确标 `○` 并写 Issue 编号
- [ ] 不重复抄写字段表，全部指向 `docs/api.md` 小节号
