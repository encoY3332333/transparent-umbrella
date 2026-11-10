# ADR-001 认证采用 JWT 而非服务端 Session

- **状态**：已采纳（2026-11-10 复核，决策不变，token 载体由 `Authorization` 头改为 HttpOnly Cookie，见文末「复核」）
- **日期**：2026-11-09
- **决策人**：【组长】、【组员1】、【组员2】
- **关联 Issue**：#2（游客登录与偏好档案）、#4（行程生成编排入口）

## 背景

UC-01 要求游客用手机号验证码登录，登录后才能保存行程（BR-03：未登录可生成行程但不可保存）。系统需要一套鉴权方案，且必须是**三个人能在一周内做完、能写测试、能过 CI** 的方案。

硬性约束：

1. ~~前后端分离，前端 Vue 3 部署在 5173（开发）/ nginx（演示），后端 8080，跨域~~ → 2026-11-10 技术栈切换后，前端改为 Jinja2 服务端渲染，与后端同进程同源，**跨域约束消失**（见 ADR-007）
2. 演示环境用 `docker compose up` 一条命令起，**不希望额外引入 Redis 这类中间件**——多一个容器就多一处答辩时可能挂掉的地方
3. 课程要求「可测试」，CI 里跑集成测试时要能方便地造出「已登录」状态

## 备选方案

### 方案 A：JWT（自包含 token）

登录成功后签发 `access_token`，payload 内含 `tourist_id`、`exp`。后端在依赖注入中验签，验过则把当前游客对象注入到路由函数参数里。

- 优点：无状态，后端不用存任何东西；水平扩展不需要共享 session；测试里直接构造 token 即可
- 缺点：**无法主动失效**——用户改密码或退出后，旧 token 在 `exp` 到期前仍然有效；payload 明文可解（不能放敏感字段）

### 方案 B：Session + Redis

Session 存 Redis，靠 Cookie 中的 session id 识别。

- 优点：服务端可随时踢人（删除对应 key）；session 内容不暴露给客户端
- 缺点：**多一个 Redis 容器**；测试需要连 Redis，或者搭一套假的 session 存储；多一处「容器起来了但连不上」的排查成本

### 方案 C：内存 Session（单机）

Starlette 的 `SessionMiddleware`，默认签名 Cookie 存放 session 数据，不做持久化。

- 优点：零依赖，最简单，一行代码接入
- 缺点：session 数据全在 Cookie 里（签名防篡改但不加密）；后端重启后密钥轮换即全员掉线；无法在服务端主动失效（与 JWT 相同的缺点，却少了 JWT 的标准化工具链）

## 决策

**采用方案 A：JWT**。有效期 24 小时，不实现 refresh token。

## 理由

1. **约束 2 是决定性的**。本课程演示环境追求「一条命令起来」，方案 B 引入 Redis 后 `docker-compose.yml` 多一个服务、多一处端口冲突、多一处排查成本，收益不匹配。
2. **方案 A 最大的缺点（无法主动失效）在本项目中影响可忽略**。本系统是行程规划工具，不涉及支付、不涉及资金，权限模型只有「游客 / 管理员」两级。退出登录即清除 Cookie，即使旧 token 理论有效，也没有可被恶意利用的高价值操作。若将来真需要，再引入「token 版本号」字段即可（`tourist` 表加一列 `token_version`，验签时比对），这个演进路径是清晰且低成本的。
3. **课程要求「可测试」**。方案 A 在测试中只需一个 fixture：`client.cookies.set("access_token", make_token(tourist_id))`，或者在 `conftest.py` 里封装成 `auth_client` fixture。方案 B 需要在测试上下文里维护 Redis 连接或伪造 session 后端。
4. 方案 C 的「重启掉线」在答辩现场是明显的减分项（重新演示要重新登录），且它的失效能力与 JWT 相同却缺少生态支持，排除。

**明确排除 refresh token**：本项目 24 小时有效期覆盖单次完整演示，refresh 机制会带来「两套 token、两个过期时间、401 自动重试」的复杂度，属于过度设计。这是个有意识的取舍，不是遗漏。

## 影响

- **正面**：后端无状态；CI 集成测试造身份简单；`docker-compose.yml` 只需 db + web 两个服务
- **负面**：
  - 无法即时踢下线 —— 已在 `docs/architecture.md` 6.3 安全章节注明
  - 未来若需强制下线，必须加 `token_version` 字段并让鉴权依赖查一次库（届时会削弱无状态的性能优势，需重新评估）
- **后续动作**：
  - JWT 密钥走环境变量 `JWT_SECRET`，`.env.example` 已留位，`.gitignore` 已忽略 `.env`
  - 测试夹具 `auth_client` 由 #2 落地
  - 若 #2 实现中发现 payload 需要携带权限之外的更多信息，回来补一条 ADR

---

## 复核（2026-11-10）：技术栈切换后的重新评估

ADR-007 把技术栈从「Spring Boot + Vue 3 前后端分离」改成「FastAPI + Jinja2 单体服务端渲染」。这直接推翻了本 ADR 的**约束 1**，必须重新评估。

### 变化点

| 维度 | 切换前 | 切换后 |
|---|---|---|
| 部署形态 | 前端 5173 / 后端 8080，跨域 | 同进程同源，无跨域 |
| 谁发起受保护请求 | 前端 JS 的 `fetch` | HTMX（浏览器原生发起） |
| 自然的凭据载体 | `Authorization: Bearer` | Cookie |

### 结论：**维持 JWT，但改用 HttpOnly Cookie 承载**

理由：

1. **Session 方案的成本没变，JWT 的优势也没失效**。约束 2（不引入 Redis）依然成立，方案 B 仍然被排除。方案 C 仍然有「重启掉线」问题。
2. **HttpOnly Cookie 恰好修掉了原方案自己写的那个缺点**。原文「负面」里写着「token 存 `localStorage` 存在 XSS 窃取风险」——改为 HttpOnly Cookie 后，JS 读不到 token，这个风险从根上消失。
3. **HTMX 不需要额外配置**。HTMX 的请求由浏览器发起，Cookie 自动携带；若用 `Authorization` 头，需要给每个 `hx-*` 元素配 `hx-headers` 或用 `htmx:configRequest` 事件注入，两处容易漏，漏了就表现为「某些操作莫名 401」。
4. **不便之处**：Cookie 方案需要防 CSRF。缓解措施是 `SameSite=Lax`（跨站 POST 不带 Cookie，覆盖绝大多数攻击面），加上写操作一律用 POST/PUT 而非 GET。对课程项目这一级别足够，且不引入 CSRF token 的额外复杂度。

### 由此产生的改动

- `docs/api.md` 的鉴权说明改为 Cookie 方案（`Set-Cookie: access_token=...; HttpOnly; SameSite=Lax; Path=/`）
- 路由层的 `current_tourist` 依赖从读 `Authorization` 头改为读 Cookie，未登录时的错误码仍是 `AUTH_REQUIRED`（401），错误码表不变
- #2 的验收标准需同步（见该 Issue 的技术备注）
- 原「负面」中关于 `localStorage` 与 XSS 的那一条**已消除**，保留原文以便追溯，不重写历史
