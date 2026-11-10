# ADR-007 技术栈整体切换为 Python（FastAPI 单体 + Jinja2 服务端渲染）

- **状态**：已采纳
- **日期**：2026-11-10
- **决策人**：【组长】、【组员1】、【组员2】
- **关联 Issue**：#1（工程脚手架）、#14（CI 覆盖率）、#2（登录，鉴权载体受影响）
- **取代**：`docs/architecture.md` v0.1 中的技术栈章节；影响 ADR-001 的约束 1

## 背景

v0.1 的架构文档确定的方案是 **Vue 3 + Vite + TypeScript / Spring Boot 3.2 + Java 17 / MySQL 8 + MyBatis-Plus**。选型理由是「全组三人对 Java 更熟」。

这个理由在需求分析阶段结束时被推翻了。第一次会议（2026-10-28）后，三人在准备脚手架时实际动手验证，暴露了三个问题：

1. **「对 Java 更熟」是印象，不是事实**。三人实际写过的最大 Java 项目是课程作业的几百行，没有一个人配过 Spring Boot 的多环境配置、事务传播、Maven 多模块。第一个 Issue（脚手架）就在 `pom.xml` 的 BOM 版本冲突上卡了半天。
2. **环境成本吃掉进度**。完整跑起来需要 JDK 17 + Maven + Node 22 + npm + MySQL，四个人（含评审同学）四台机器的组合各不相同，README 的「快速开始」在组外实测时失败了两次。
3. **两套运行时 = 两套 CI**。CI 要同时配 `setup-java` 与 `setup-node`，任何一个依赖缓存失效都表现为「PR 莫名红了」，而排查这类问题的能力三人都不具备。

同时，三人日常写 Python，用过的库包括 FastAPI、SQLAlchemy、Pydantic。**语言熟悉度是团队产能的乘数**，在这个项目里它比「框架的工程完备度」重要得多。

## 备选方案

### 方案 A：维持 Java + Vue

不改技术栈，用两周时间补齐 Spring Boot 与 Vue 的知识缺口。

| 维度 | 评估 |
|---|---|
| 优点 | 文档（架构、接口、14 个 Issue 的技术备注）已经写好，零返工；Java 的强类型在排程算法上确实更好维护 |
| 缺点 | 学习成本压在关键路径上；脚手架 Issue 预估会从 8h 涨到 20h+；后续 13 个 Issue 都要在陌生框架里做 |
| 风险 | 第 8 周的 Alpha 里程碑大概率完不成，A3（功能与质量，16 分）直接受损 |

### 方案 B：Python 后端 + 保留 Vue 3 前端

后端换 FastAPI，前端仍是 Vue 3 + Vite，前后端分离保持不变。

| 维度 | 评估 |
|---|---|
| 优点 | 接口清单、`docs/api.md`、9 张顺序图全部不用改；前端分工（组员1）职责不变 |
| 缺点 | 仍需维护 Node 依赖与 `npm ci`；CI 仍需两套运行时；本地仍需两个终端；**问题 2 和 3 只解决了一半** |
| 风险 | 三人中只有组员1 熟悉 Vue，前端仍是瓶颈 |

### 方案 C：纯 Python 单体（FastAPI + Jinja2 + HTMX）✅

| 维度 | 评估 |
|---|---|
| 优点 | 一种语言、一套依赖、一个 CI 运行时、一条启动命令；服务端渲染让「改完刷新即见」，调试链路短；HTMX 用 HTML 属性做局部刷新，不需要写 JS 状态管理 |
| 缺点 | 交互复杂度上限低；页面局部更新依赖服务端返回 HTML 片段；**SRS 第 5 章的界面原型描述与接口章节需要重写** |
| 风险 | 若某个功能需要复杂前端交互（如拖拽调整行程），HTMX 会吃力 |

### 方案 D：Django + DRF + 模板

| 维度 | 评估 |
|---|---|
| 优点 | 全家桶：ORM、Admin 后台、权限、迁移、模板引擎开箱即用；**#12（POI 管理后台）可以用自带 Admin 直接交付** |
| 缺点 | 与 `docs/api.md` 已定的 REST 契约风格差异大；DRF 的 serializer 与 Pydantic 的校验模型不同，等于重写 39 个错误码的映射；Admin 虽然省事，但意味着那个 Issue 没有开发量，个人贡献数据会受影响 |

## 决策

**采用方案 C：Python 3.11 + FastAPI + Pydantic v2 + SQLAlchemy 2.0 + Jinja2/HTMX，数据库开发用 SQLite、生产可切 MySQL。**

具体到各层：

| 层 | 原方案 | 新方案 | 对应关系 |
|---|---|---|---|
| 表现层 | Vue 3 + Vite + TS + Pinia | Jinja2 模板 + HTMX + Alpine.js | 页面模板 ↔ 组件；`hx-get` ↔ 路由跳转；Alpine 局部状态 ↔ Pinia |
| 应用层 | Spring `@RestController` + `@Valid` | FastAPI 路由 + Pydantic v2 | 路由函数 ↔ Controller；Pydantic 模型 ↔ DTO + 校验注解 |
| 业务层 | `@Service` + `@Transactional` | `services/` + `session.begin()` | 事务边界从方法注解变为显式上下文管理器 |
| 排程引擎 | Java class | `engine/` 下纯函数 | 纯函数比 class 更容易单测，不需要 mock |
| 数据层 | MyBatis-Plus + Mapper XML | SQLAlchemy 2.0 + Alembic | ORM 模型 ↔ Entity；Alembic 迁移 ↔ Flyway |
| 外部代理 | `RestTemplate` / `WebClient` | `httpx` + `adapters/base.py` | 统一封装超时/重试/缓存/降级 |
| 测试 | JUnit 5 + Mockito + JaCoCo | Pytest + `httpx.AsyncClient` + `pytest-cov` | fixture 构造测试数据比 Mockito 直观 |
| Lint | Checkstyle | Ruff（lint + format 二合一） | 一个工具替代 Checkstyle + Spotless |
| 类型检查 | Java 编译期 | Mypy | 编译期→静态检查，强度略降，但 Pydantic 补上了运行时校验 |

**明确排除 Django**：不是因为它不好，而是本项目的接口契约（9 个用例、39 个错误码、统一响应体 `{code, message, details}`）已经在 SRS 里冻结，用 Django 意味着要么放弃这套契约、要么在 DRF 上再包一层，两头不讨好。FastAPI 的 Pydantic 模型与这份契约是天然对应的。

## 理由

1. **产能优先于框架完备度**。这是三个人的课程项目，不是产品。方案 A 的「Java 更强类型」是真实优势，但它换不来两周的学习时间。三人用 Python 能立刻开始写业务，第一周就能产出可评审的 PR——这对 B1（任务闭环）和 B2（代码质量）的成绩是直接正向的。
2. **问题 2、3 只有方案 C 能同时解决**。方案 B 解决了后端，前端仍然要 `npm ci`。方案 C 把「四台机器四种环境」压成「一台机器一个 Python」。
3. **服务端渲染让「可测试」更容易**。CI 里跑的是同一个进程，模板渲染也能被测试覆盖（`scripts/check-templates.py` 就是为此写的）。SPA 的组件测试需要 jsdom、需要 mock API，成本高得多。
4. **HTMX 的风险可量化**。本项目只有 8 个页面，最复杂的交互是「拖拽调整行程活动顺序」。HTMX 官方有 `sortable` 扩展，配合 `hx-put` 提交新顺序即可；若实测不行，退回「上移/下移按钮」也能满足 UC-05 的验收标准。**这个风险有明确的降级路径**，不像方案 A 的风险（学不会 Spring）无从降级。

## 影响

### 正面

- CI 从 2 套运行时降为 1 套：`setup-python` 替代 `setup-java` + `setup-node`
- 本地启动从「JDK + Maven + Node + MySQL」降为「Python + SQLite」，**README 的快速开始变成真正的三条命令**
- 排程引擎写成纯函数，单测不需要 mock 数据库，`engine/` 的覆盖率容易做到 80%+
- 一人一语言，Code Review 时三人都看得懂对方的代码（原方案里组员1 的 Vue 代码组长未必看得懂）

### 负面（必须如实记录）

| 代价 | 具体影响 | 谁承担 |
|---|---|---|
| 架构文档重写 | `docs/architecture.md` 第 1、2、3、6、7 章全改，新增本 ADR | 组长 |
| Issue 技术备注重写 | #1 改动最大（21 处），#14、#4、#2 等 10 个 Issue 的类名/命令/依赖清单 | 组长 |
| 接口契约的鉴权载体变更 | `docs/api.md` 与 ADR-001 需补充 Cookie 方案 | 组长 |
| **没有前端框架** | 组员1 的「前端」职责变为「Jinja2 模板 + HTMX」，需要学 HTMX（约 2 小时） | 组员1 |
| 团队失去 SPA 经验 | 若将来做交互更重的项目，这次的经验迁移性弱 | 全组 |
| **SRS 第 5 章界面原型** | 原文按 Vue 组件描述页面结构，需补充「服务端渲染 + HTMX 局部刷新」的说明 | 组员1 |

### 后续动作

- [x] 重写 `docs/architecture.md` 的分层表、架构图、包结构、5 条分层约束、部署章节
- [x] CI 改造：`Backend (Java 17)` / `Frontend (Node 22)` → `Backend (Python 3.11)` / `Templates (Jinja2)`
- [x] 新增 `scripts/check-templates.py`，把模板错误前移到 CI
- [x] ADR-001 补充复核节（JWT 承载体改为 HttpOnly Cookie）
- [x] README 技术栈表与快速开始重写
- [x] 14 个 Issue 的技术备注同步
- [ ] SRS 第 5 章界面原型补一节渲染方式说明（归入 #2 或单开 Issue）
- [ ] 分支保护的必需状态检查需重新勾选（job 名称已变，见 `.github/BRANCH_PROTECTION.md`）

### 待验证的假设

1. **HTMX 能撑住 UC-05 的拖拽调整** —— 由 #9 验证。若失败，降级为「上移/下移」按钮，验收标准不变。
2. **SQLite 能撑住演示并发** —— 演示是单用户，理论上无压力。若演示时需要多人同时访问，切 MySQL 只改 `DATABASE_URL`。
3. **Ruff + Mypy 的严格度足够替代 Java 编译期检查** —— 需在 #1 落地后观察前 3 个 PR 的缺陷率，若类型错误频发，再把 Mypy 从 `continue-on-error` 改为阻断。
