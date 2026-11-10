# Changelog

本项目的所有重要变更都记录在此文件中。
格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Changed

- **技术栈整体切换为 Python**（ADR-007）
  - 后端：Spring Boot 3.2 + Java 17 → **Python 3.11 + FastAPI + Pydantic v2 + SQLAlchemy 2.0**
  - 前端：Vue 3 + Vite + TypeScript → **Jinja2 模板 + HTMX + Alpine.js**（服务端渲染，取消前后端分离）
  - 数据库：MySQL 8（唯一） → **SQLite 开发 / MySQL 生产**，切换只改 `DATABASE_URL`
  - 测试：JUnit 5 + Mockito + JaCoCo → **Pytest + pytest-cov**
  - Lint：Checkstyle + Spotless → **Ruff**（lint 与格式化二合一）
- CI 的 `Frontend (Node 22)` job 改为 `Templates (Jinja2)`，新增 `scripts/check-templates.py` 检查模板语法与静态资源引用
- `.github/BRANCH_PROTECTION.md` 中必需状态检查的名称同步更新（**改名不会自动迁移旧规则**，须重新勾选）
- ADR-001 补充复核节：JWT 载体由 `Authorization` 头改为 HttpOnly Cookie（跨域约束消失后，顺带消除 localStorage 的 XSS 风险）
- 14 个 Issue 的技术备注、`docs/architecture.md` 的分层与包结构、`.env.example`、README 快速开始同步改写
- `.gitignore` 移除 Java/Maven/Node 规则，新增 Python 规则（`__pycache__`、`.venv`、`.pytest_cache`、`*.db` 等）

### Added

- `docs/adr/ADR-007-switch-to-python-stack.md`：技术栈切换的决策记录，含被否决的三个方案与切换代价
- `scripts/check-templates.py`：Jinja2 模板编译与静态资源引用检查，接入 CI
- `scripts/render-diagrams.py`：PlantUML 批量渲染脚本（此前为手动命令）
- `docs/reports/`：项目进展报告入库
- `docs/assessment-checklist.md`：A1–A8 / B1–B7 逐项自查表

### 计划中

- 工程脚手架：Python 3.11 + FastAPI + Jinja2/HTMX 单体应用（#1）
- CI 流水线与分支保护（#14）
- UC-01 游客登录与偏好建档（#2）
- UC-02 出行条件录入与校验（#3）
- UC-04 行程结果页（#8）

---

## [0.0.1] - 2026-11-09

### Added

- 仓库初始化：README、LICENSE、CONTRIBUTING、CHANGELOG、.gitignore、.env.example
- `.github/` 协作配置：CI 工作流（backend / frontend / lint-repo / ci-summary）、Issue 模板（feature / bug）、PR 模板、CODEOWNERS、分支保护操作手册
- `docs/` 文档体系
  - `srs/` 需求规格说明书（基线 V1.0）+ 基线管理与变更流程说明
  - `architecture.md` 三层架构、模块划分、两条主链路数据流、数据模型、降级策略
  - `api.md` 9 个用例的完整接口契约、统一响应体、39 个错误码
  - `adr/` 6 份架构决策记录（JWT / 排程拆分 / 贪心算法 / 服务端代理 / 副本调整 / 统计拥挤度）
  - `diagrams/` 15 张 PlantUML 源文件：用例图 1、顺序图 9、分析类图 1、状态图 3
  - `issues/` 14 个 Issue 完整正文（含任务清单、验收标准、依赖关系）
  - `meetings/` 前两次会议纪要（md + docx 双份）
  - `contributions/` 个人工程贡献说明书模板与硬性数据自查表
  - `guides/` 协作规范、需求获取问卷与访谈提纲
  - `release-notes/v0.0.1.md`
- 需求基线 V1.0：9 个功能（F1–F9）、9 个用例（UC-01–UC-09）、24 条业务规则（BR-01–BR-24）

### Notes

- 本版本仅包含文档与工程配置，**不含可运行代码**；代码将从 v0.1.0 Alpha 开始交付。
- CI 的 `backend` / `frontend` job 通过 `guard` 步骤探测目录是否存在，当前会被主动跳过，`#1` 合入后自动生效。
- `docs/` 中的 `【组长】【组员1】【组员2】【GitHub用户名】` 为占位符，由组长统一替换。

---

<!-- 版本链接占位，仓库地址确定后由组长补充 -->
[Unreleased]: https://github.com/encoY3332333/transparent-umbrella/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/encoY3332333/transparent-umbrella/releases/tag/v0.0.1
