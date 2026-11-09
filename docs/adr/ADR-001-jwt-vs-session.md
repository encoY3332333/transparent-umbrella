# ADR-001 认证采用 JWT 而非服务端 Session

- **状态**：已采纳
- **日期**：2026-11-09
- **决策人**：【组长】、【组员1】、【组员2】
- **关联 Issue**：#2（游客登录与偏好档案）、#4（行程生成编排入口）

## 背景

UC-01 要求游客用手机号验证码登录，登录后才能保存行程（BR-03：未登录可生成行程但不可保存）。系统需要一套鉴权方案，且必须是**三个人能在一周内做完、能写测试、能过 CI** 的方案。

硬性约束：

1. 前后端分离，前端 Vue 3 部署在 5173（开发）/ nginx（演示），后端 8080，跨域
2. 演示环境用 `docker compose up` 一条命令起，**不希望额外引入 Redis 这类中间件**——多一个容器就多一处答辩时可能挂掉的地方
3. 课程要求"可测试"，CI 里跑集成测试时要能方便地造出"已登录"状态

## 备选方案

### 方案 A：JWT（自包含 token）

登录成功后签发 `access_token`，payload 内含 `touristId`、`exp`，前端存 `localStorage`，每次请求带 `Authorization: Bearer <token>`。后端用 `OncePerRequestFilter` 验签，验过则把 `touristId` 塞进 `SecurityContext`。

- 优点：无状态，后端不用存任何东西；水平扩展不需要共享 session；测试里直接构造 token 即可
- 缺点：**无法主动失效**——用户改密码或退出后，旧 token 在 `exp` 到期前仍然有效；token 泄露风险窗口较长；payload 明文可解（不能放敏感字段）

### 方案 B：Session + Redis

Spring Session 把 session 存 Redis，前端靠 Cookie（`JSESSIONID`）识别。

- 优点：服务端可随时踢人（`DELETE session`）；session 内容不暴露给前端
- 缺点：**多一个 Redis 容器**；跨域 Cookie 需要 `SameSite=None; Secure`，本地 http 开发环境要额外配 HTTPS 或降级 `Lax`，容易踩坑；测试需要连 Redis

### 方案 C：内存 Session（单机）

Spring 默认的 `HttpSession`，不做持久化。

- 优点：零依赖，最简单
- 缺点：后端重启即全员掉线；无法水平扩展（虽然本课程单机部署够用）

## 决策

**采用方案 A：JWT**。有效期 24 小时，不实现 refresh token。

## 理由

1. **约束 2 是决定性的**。本课程演示环境追求"一条命令起来"，方案 B 引入 Redis 后 `docker-compose.yml` 多一个服务、多一处端口冲突、多一处"容器起来了但连不上"的排查成本，收益不匹配。
2. **方案 A 最大的缺点（无法主动失效）在本项目中影响可忽略**。本系统是行程规划工具，不涉及支付、不涉及资金，权限模型只有"游客 / 管理员"两级。退出登录只清前端 `localStorage`，即使旧 token 理论有效，也没有可被恶意利用的高价值操作。若将来真需要，再引入"token 版本号"字段即可（用户表加一列 `token_version`，验签时比对），这个演进路径是清晰且低成本的。
3. **课程要求"可测试"**。方案 A 在测试中只需 `request.header("Authorization", "Bearer " + buildTestToken(touristId))`，一条静态辅助方法搞定；方案 B 需要在测试上下文里维护 Cookie 或 MockMvc 的 Session。
4. 方案 C 的"重启掉线"在答辩现场是明显的减分项（重新演示要重新登录），排除。

**明确排除 refresh token**：本项目 24 小时有效期覆盖单次完整演示，refresh 机制会带来"两套 token、两个过期时间、前端拦截器要处理 401 重试"的复杂度，属于过度设计。这是个有意识的取舍，不是遗漏。

## 影响

- **正面**：后端无状态；CI 集成测试造身份简单；`docker-compose.yml` 只需 db + backend + frontend 三个服务
- **负面**：
  - 无法即时踢下线 —— 已在 `docs/architecture.md` 6.3 安全章节注明
  - token 存 `localStorage` 存在 XSS 窃取风险 —— 缓解手段：Vue 默认转义模板插值；CI 增加硬编码密钥扫描；不在 URL 中传 token
  - 未来若需强制下线，必须加 `token_version` 字段并让 Filter 查一次库（届时会削弱无状态的性能优势，需重新评估）
- **后续动作**：
  - JWT 密钥走环境变量 `JWT_SECRET`，`.env.example` 已留位，`.gitignore` 已忽略 `.env`
  - 测试工具类 `TestTokenFactory` 由 #2 落地
  - 若 #2 实现中发现 payload 需要携带权限之外的更多信息，回来补一条 ADR
