# [Feature] 游客登录与偏好建档

## 背景 / Background

SmartTrip 的行程推荐需要「个性化」的输入：同样去杭州、同样 3 天，一个偏好人文历史的人和一个带孩子的人，行程应该完全不同。
偏好必须在首次使用时建档，否则每次规划都要重填，用户会流失（问卷 Q3：56.2% 的用户规划耗时超过 2 小时，任何额外填写成本都会被放大）。

对应 SRS：3.3.1 · 用例 UC-01
鉴权方案：ADR-001（JWT，HttpOnly Cookie 承载）

## 需求描述 / Description

对接统一身份认证系统完成手机号验证码登录；首次登录引导填写偏好档案（偏好标签、同行人员构成、出行节奏、消费档次）；再次登录直接回显。

## 任务清单 / Tasks

- [ ] 后端：`app/api/auth.py` 提供 `POST /api/auth/send-code`、`POST /api/auth/login`、`POST /api/auth/logout`、`GET /api/auth/me`、`PUT /api/auth/preference`
- [ ] 后端：`app/services/auth_service.py`，负责令牌签发、游客查找/创建、偏好保存；**事务边界在这一层**
- [ ] 后端：`app/adapters/auth.py` 的 `AuthAdapter`，对接 AuthServer 的 `verify_token()`，配置 1.5s/3s 超时与降级
- [ ] 后端：`app/core/security.py` 的 `create_access_token()` / `decode_token()`，用 `pyjwt`；密码或验证码哈希用 `passlib[bcrypt]`
- [ ] 后端：验证码错误计数（5 次/5 分钟锁定），用 `cachetools.TTLCache` 内存实现（**不引入 Redis**，见 ADR-001 约束 2）
- [ ] 后端：`GET /api/auth/me` 与 `PUT /api/auth/preference` 通过 `Depends(current_tourist)` 取当前用户
- [ ] 页面：`templates/auth/login.html`（手机号 + 验证码 + 60 秒倒计时，用 Alpine.js 管倒计时状态）
- [ ] 页面：`templates/auth/preference.html`（标签多选、构成单选、节奏滑块、消费档次），表单用普通 `POST` 提交，成功后 302 跳首页
- [ ] 登录态：JWT 写入 **HttpOnly Cookie**（`SameSite=Lax; Path=/; Max-Age=86400`），`current_tourist` 依赖从 Cookie 读取
- [ ] 测试：`tests/services/test_auth_service.py` 覆盖登录成功、验证码错误、锁定、首次建档、偏好回显 5 个场景

## 验收标准 / Acceptance Criteria

- [ ] AC-1 输入正确验证码后，3 秒内完成登录并跳转首页
- [ ] AC-2 首次登录必须进入偏好设置页；偏好可成功保存，并在下次登录时完整回显
- [ ] AC-3 连续 5 次输入错误验证码后，账号被临时锁定 5 分钟，提示剩余时间
- [ ] 登录响应的 `Set-Cookie` 中 `access_token` 带 `HttpOnly` 与 `SameSite=Lax`（用浏览器 DevTools 或 `curl -i` 可验证）
- [ ] 页面 JS 中**无法**通过 `document.cookie` 读到 token（XSS 缓解，ADR-001 复核节）
- [ ] 同一手机号只能绑定一个游客档案（BR-01），重复注册返回 409
- [ ] 偏好标签最多选 6 个（BR-02），超出时提交按钮禁用并提示
- [ ] 跳过偏好设置时以默认值（节奏适中、消费中等、无标签）建档
- [ ] AuthServer 不可用时返回明确错误码 `AUTH_SERVICE_UNAVAILABLE`，页面提示「登录服务暂不可用，请稍后重试」
- [ ] 未登录访问 `/api/auth/me` 返回 401 与 `AUTH_REQUIRED`，不返回 500

## 关联 / Related

- 依赖 #1
- 阻塞 #3（需要登录态才能录入条件）

## 元信息

- 预估工作量：6 小时
- Labels：`feature` `backend` `P0`
- Milestone：`v0.1.0 Alpha`
- Assignee：@encoY3332333
- 分支：`feature/2-tourist-login`
- 涉及业务规则：BR-01、BR-02

## 技术备注

- **Cookie 与 HTMX 的配合**：HTMX 的请求由浏览器发起，Cookie 自动带上，不需要配 `hx-headers`。如果用 `Authorization` 头，每个 `hx-*` 元素都得配一遍，漏一个就表现为「某个按钮莫名 401」
- **CSRF**：`SameSite=Lax` 已挡住跨站 POST。所有写操作必须是 POST/PUT/DELETE，**不允许用 GET 产生副作用**（如 `/api/auth/logout` 必须是 POST）
- **`current_tourist` 依赖**写成 `async def current_tourist(request: Request, db: Session = Depends(get_db)) -> Tourist`，从 `request.cookies.get("access_token")` 取；解码失败统一抛 `AuthRequiredError`，由全局处理器转 401，不在依赖里自己 `return JSONResponse`
- **`cachetools.TTLCache` 是进程内缓存**，`uvicorn --workers 4` 时每个 worker 各有一份，锁定计数会不准。演示环境用单 worker，**在 Issue 里注明这个限制**，不要假装它是分布式的
- **偏好标签的顺序要保留**，用户先选「人文」再选「亲子」和反过来选，语义不同。存 `JSON` 数组而非逗号分隔字符串
