# 第 8 章 部署与运维

> 负责人：B（刘婕）｜骨架由 A 搭建。部署事实来自 `docker-compose.yml`、`.github/workflows/ci.yml`、`scripts/`，`⬜` 处需补齐。

## 8.1 环境矩阵

| 环境 | 组成 | 数据库 | 启动 | 用途 |
|---|---|---|---|---|
| 开发 | 本地 uvicorn `--reload` | SQLite 文件（`./smarttrip.db`，不入库） | `uvicorn app.main:app --reload` | 日常开发 |
| CI | GitHub Actions `ubuntu-latest` + Python 3.11 | SQLite `:memory:` | `pytest` | 每次 push / PR |
| 演示 | `docker compose up --build`（db + web） | MySQL 8（`character-set-server=utf8mb4`） | compose 一条命令 | 答辩现场 |

**环境差异只有 `DATABASE_URL` 一个变量**（详见 `docs/architecture.md` 第 7 节）。

## 8.2 容器化

| 服务 | 镜像 | 关键配置 |
|---|---|---|
| `db` | `mysql:8.0` | `utf8mb4` / `utf8mb4_unicode_ci`；初始化脚本 `docs/docker/mysql-init.sql`；数据卷 `db-data`；端口映射 `3307:3306`（避开本地已占用的 3306）；`healthcheck` 用 `mysqladmin ping` |
| `web` | `python:3.11-slim` | `depends_on: db`（等 healthcheck 通过）；生产不用 `--reload`；启动前跑 `alembic upgrade head` |

⬜ B 需补：
- [ ] `web` 服务的实际启动命令、`workers` 设置与依据
- [ ] 首次启动顺序：建库 → 迁移 → 种子数据（`backend/app/seed/`，若存在）
- [ ] 演示环境密码 `root_in_demo_only` 的说明：仅演示用，写进"不可用于生产"清单

## 8.3 CI 流水线

| Job | 内容 | 失败意味着 |
|---|---|---|
| Backend (Python 3.11) | Ruff check → Ruff format --check → Mypy → pytest（覆盖率 ≥ 40%，且 engine/services ≥ 60%） | 代码规范或测试不过，不能合 |
| Templates (Jinja2) | 模板语法检查 | 页面渲染会报错 |
| Repo Conventions | 分支名 / 提交信息 / 文档规范 | 命名不合规范（如 `docs/xxx`、`chore/` 前缀问题） |
| Perf Baseline | 性能基线，**不设门禁** | 只记录，不阻塞合并 |
| CI Summary | 汇总各 job | 任一失败即整体红 |

**必需检查**：`Backend (Python 3.11)` + `CI Summary` 为 `protect-main` 规则集的必需状态检查，未通过不能合并到 `main`。

⬜ B 需补：
- [ ] 覆盖率门禁的实际口径（40% 全局 / engine+services 60%），以及当前实际覆盖率数字（从 CI 的 `coverage.xml` 取）
- [ ] Perf Baseline 的测量项与结果存放位置

## 8.4 分支保护与发布流程

| 项 | 配置 |
|---|---|
| 规则集 | `protect-main`（id 27102459），`enforcement=active` |
| 要求 | 至少 1 个 approving review；push 后旧 approval 自动失效（`dismiss_stale_reviews_on_push`）；评论线程必须 resolve；禁删除；禁强推 |
| 证据 | `docs/evidence/protect-main-ruleset.json`、`docs/evidence/branch-protection-20261112.png` |
| 发布 | 功能分支 `feature/<issue>-<slug>` → PR → 评审 → Squash merge 到 `main` |

**已知约束**：PR 作者不能自己 Approve 自己的 PR；跨 fork 的 PR 若需改动，必须由 fork 所有者推分支，不能替对方开替代 PR（第一阶段 #48 的教训）。

## 8.5 备份与回滚

| 场景 | 手段 |
|---|---|
| 数据回滚 | Alembic `downgrade`（每次迁移必须验证 `upgrade→downgrade→upgrade` 往返） |
| 应用回滚 | `main` 上 revert 对应 squash commit；因禁强推，历史永远可追溯 |
| 演示环境重建 | `docker compose down -v && docker compose up --build` |

⬜ B 需补：演示库的备份建议（`mysqldump` 命令 + 何时跑），以及"演示前 30 分钟检查清单"。

## 8.6 运维观测

| 观测点 | 现状 |
|---|---|
| 健康检查 | `GET /api/health`，返回版本与关键配置是否就绪 |
| 日志 | 结构化 + `traceId`，见第 7.5 节 |
| 外部调用计数 | `adapters/call_budget.py` 的 `current()` 可读取已用量 |
| 错误率 | 暂未接入监控，靠日志人工排查（⬜ B 说明取舍） |

## 8.7 本章自检清单

- [ ] 环境矩阵与 `docker-compose.yml` 实际内容一致
- [ ] CI job 名称与 `ci.yml` 一致（含拼写）
- [ ] 覆盖率数字是从 CI 取的真实值，不是估计
- [ ] 「演示环境密码」明确标注不可用于生产
