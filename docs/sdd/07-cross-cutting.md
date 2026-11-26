# 第 7 章 横切设计

> 负责人：B（刘婕）｜骨架由 A 搭建。本章写"跨模块、每个用例都会碰到"的机制：缓存、外部调用配额、事务、异常、日志、安全、并发。`⬜` 处需补齐。

## 7.1 配置管理

| 机制 | 实现 | 约束 |
|---|---|---|
| 唯一入口 | `backend/app/core/config.py::Settings`（pydantic-settings 读 `.env`） | `.env.example` 的每一项与 `Settings` 字段一一对应，多一项少一项都不行 |
| 环境区分 | `app_env ∈ {dev, test, ci, prod}` + `is_production` 计算属性 | 生产环境才加 `Secure` Cookie、才隐藏 `debugCode` |
| 校验 | `model_validator` 校验五项权重和 = 1（允差 ±0.01） | 启动即失败，不把错误配置带进运行期 |
| 测试隔离 | `get_settings.cache_clear()` + `reset_engine_cache()` | 每个用例独立，避免 `.env` 渗进断言 |

## 7.2 数据库与事务

| 主题 | 设计 |
|---|---|
| 引擎构建 | `core/db.py::build_engine` 按 URL 前缀决定参数；SQLite 内存库强制 `StaticPool`（否则每个连接一个库） |
| 会话 | `expire_on_commit=False`，避免 service 提交后读属性触发 `DetachedInstanceError` |
| 事务边界 | **只在 `services/` 开事务**；`api/` 与 `engine/` 不得开（`docs/architecture.md` 分层约束第 2 条） |
| 失败回滚 | 外部调用已发生但落库失败时，不回滚外部副作用（不可撤销），通过日志与 `traceId` 关联排查 |

⬜ B 需补：现状核对——`auth_service` 里 `login` / `save_preferences` 使用 `session.commit()` 而非显式 `session.begin()`，需在本章说明"提交式事务"与"上下文事务"的取舍，并把分层约束的描述改成与代码一致（否则又是一处文档与实现不一致）。

## 7.3 外部调用配额与降级

| 机制 | 实现位置 | 说明 |
|---|---|---|
| 配额 | `adapters/call_budget.py`（`record` / `check` / `budget` 上下文管理器） | 单次规划 ≤ `plan_external_call_limit`（默认 60，BR-10）；超限抛 `ExternalCallLimitExceeded`（`EXTERNAL_CALL_LIMIT_EXCEEDED`） |
| 超时 | `Settings.external_connect_timeout`（1.5s）/ `external_read_timeout`（3.0s） | 全局限定，避免单个外部系统拖垮 P95 |
| 重试 | `Settings.external_max_retries`（2） | 只对幂等 GET 重试 |
| 缓存 | `BaseAdapter` 内置 `TTLCache`（默认 `cache_ttl_seconds`，可按适配器覆写） | 人流量等按天缓存 |
| 降级 | 适配器返回"不可用"标记 → `degraded[]` → 响应字段 `degraded` → 页面提示 | **降级必须在界面说出来**，不能悄悄用估算值 |

⬜ B 需补：每个外部系统的"降级后用户可见文案"表格（天气/人流/地图/活动/票务/酒店/认证），与 `docs/architecture.md` 6.2 节对齐并核对文案是否已在页面模板里真实存在。

## 7.4 异常与错误码

| 层 | 责任 | 落点 |
|---|---|---|
| Pydantic | 拦类型与格式 | 返回 `PARAM_INVALID` + `details[]` |
| service | 拦业务规则，抛 `BusinessError(code)` | 状态码由 `ERROR_SPECS` 决定，service 不改状态码 |
| handlers | 统一转响应体，附 `traceId` | 业务异常 / 校验异常 / HTTP 异常 / 兜底 `Exception` → 500 |
| 前端 | 按 `code` 分支，不按 message 文本分支 | message 是给人看的，`code` 才是契约 |

**兜底规则**：未捕获异常一律 500 + `INTERNAL_ERROR`，响应体里**不返回堆栈**，堆栈只进日志。

## 7.5 日志与追踪

| 项 | 设计 |
|---|---|
| 格式 | 结构化日志，含 `trace_id`、`method`、`path`、`status`、`duration_ms` |
| 中间件 | `core/logging.py::TraceIdMiddleware`，请求入口生成/透传 `traceId` |
| 敏感信息 | 手机号在日志里只打后 4 位；验证码**永不落日志**；`.env` 不打印 |
| 级别 | `log_level` 由配置控制，CI 用 `WARNING` 减少噪音 |

⬜ B 需补：贴一段真实的请求日志样例（脱敏后），说明 `traceId` 如何从响应追到日志。

## 7.6 安全

| 面 | 措施 | 证据 |
|---|---|---|
| 认证 | JWT + HttpOnly Cookie（ADR-001） | `core/security.py`、`api/auth.py` |
| 分享 | HMAC-SHA256 签名，含过期时间与行程 id，防遍历（BR-17） | `core/security.py::sign_share_token` |
| 输入 | Pydantic 类型校验 + service 业务校验双层 | `schemas/`、`services/` |
| 模板 | Jinja2 自动转义；用户内容禁止 `\|safe` | Code Review 检查项 |
| 密钥 | 全部走环境变量，`.env` 永久忽略；CI 扫描硬编码 | `.gitignore`、CI |
| 隐私 | 响应手机号脱敏；分享响应不携带账号字段 | `schemas/tourist.py::mask_phone` |

⬜ B 需补：管理员鉴权的现状（`api/admin_strategy.py` 当前**是否有** admin 依赖），没有就标 `○` 并写风险。

## 7.7 并发与性能手段

| 手段 | 目的 |
|---|---|
| 无状态服务 + 连接池 | 支持多 worker 水平扩展 |
| 外部调用批量 + 缓存 | 把 8–12 次/规划压到可接受 |
| 贪心算法替代 ILP | 求解时间可控（ADR-003） |
| 只重算相邻两项 | 调序 ≤ 1.5s（BR-15，待实现） |
| 服务端渲染直出 | 首屏 ≤ 3s，无 JS 打包等待 |

## 7.8 本章自检清单

- [ ] 每条机制都指到具体文件/函数
- [ ] 降级文案与页面模板里真实存在的文本一致
- [ ] 7.2 的事务描述与代码真实写法一致
- [ ] 7.6 管理员鉴权状态如实标注
