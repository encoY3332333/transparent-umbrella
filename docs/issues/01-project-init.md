# [Chore] 初始化仓库与工程基建

## 背景 / Background

仓库当前只有 `README.md` 与文档，`backend/` 目录尚未创建，`.github/` 下的模板与 CI 已就位但无法运行（CI 会走跳过分支）。
本 Issue 是整个项目的**阻塞项**：后续所有功能 Issue（#2–#13）都依赖可运行的骨架。

对应 SRS：`docs/srs/` 第 4.2 节 设计约束
技术栈决策：ADR-007（Python + FastAPI + Jinja2 单体）

## 需求描述 / Description

搭建一个可运行的最小工程骨架——**单一 Python 应用，服务端渲染页面 + JSON 接口**，并验证「克隆 → 装依赖 → 启动 → 访问」全链路可用。

## 任务清单 / Tasks

- [ ] 创建 `backend/pyproject.toml`：Python 3.11，运行依赖 `fastapi` `uvicorn[standard]` `sqlalchemy[asyncio]` `alembic` `pydantic-settings` `jinja2` `python-multipart` `httpx` `pyjwt` `passlib[bcrypt]`；开发依赖 `ruff` `mypy` `pytest` `pytest-cov` `pytest-asyncio`
- [ ] 在同一文件内配置 `[tool.ruff]`（`line-length=100`，`select` 至少含 `E,F,I,UP,B,SIM`）、`[tool.mypy]`（`strict` 从宽起步）、`[tool.pytest.ini_options]`、`[tool.coverage.*]`
- [ ] 创建 `app/main.py`：实例化 FastAPI、挂载静态资源、注册异常处理器与路由
- [ ] 创建 `app/core/config.py`：`Settings` 类用 `pydantic-settings` 从 `.env` 读取，字段与 `.env.example` 一一对应
- [ ] 创建 `app/core/deps.py`：`get_db()` 会话依赖、`get_settings()` 缓存依赖
- [ ] 创建 `app/core/errors.py` + `app/core/handlers.py`：业务异常基类与统一错误响应 `{code, message, details}`
- [ ] 创建 `app/api/health.py`：`GET /api/health` 返回 `{"status": "ok", "version": "..."}`
- [ ] 初始化 Alembic：`alembic.ini` + `migrations/env.py`，`env.py` 从 `Settings` 读连接串而非硬编码
- [ ] 创建 `app/templates/base.html` + `app/templates/index.html`，`app/static/` 放 CSS、HTMX、Alpine.js（**本地文件，不引 CDN**，避免演示时断网） 
- [ ] 创建 `app/api/pages.py`：`GET /` 渲染首页模板
- [ ] 创建 `app/adapters/base.py`：`BaseAdapter` 抽象基类，封装超时、重试、缓存、降级、调用计数（空实现即可）
- [ ] 添加 `docker-compose.yml`（`db` 用 MySQL 8 + 初始化脚本，`web` 用 `python:3.11-slim`；**开发默认走 SQLite，这个文件只用于演示环境**）
- [ ] 补充 `tests/test_health.py` 与 `tests/test_pages.py` 各 1 个冒烟测试
- [ ] 更新 README 的「快速开始」，确认步骤可被组外同学照做成功

## 验收标准 / Acceptance Criteria

- [ ] `git clone` 后执行 `cd backend && pip install -e ".[dev]"` 成功，无依赖冲突
- [ ] `pytest -q` 全绿，覆盖率不低于 40%（CI 的 `--cov-fail-under=40` 会卡）
- [ ] `uvicorn app.main:app --port 8000` 启动成功，`GET http://localhost:8000/api/health` 返回 `{"status":"ok","version":"..."}`
- [ ] 浏览器访问 `http://localhost:8000/` 显示首页（引用了本地 HTMX 与 CSS，**断网状态下样式与脚本仍正常**）
- [ ] `alembic upgrade head` 在空 SQLite 上执行成功，重复执行幂等
- [ ] `ruff check app tests` 与 `ruff format --check app tests` 均通过
- [ ] `python ../scripts/check-templates.py` 通过
- [ ] GitHub Actions 上 `Backend (Python 3.11)`、`Templates (Jinja2)` 两个 job 由「跳过」变为「通过」
- [ ] `.env.example` 中的每一项在 `Settings` 类里都有对应字段（无遗漏、无多余）
- [ ] 仓库根目录不存在任何真实密钥（`git grep -nE '(api[_-]?key|password)\s*=' -- ':!.env.example'` 为空）

## 关联 / Related

- 阻塞 #2
- 阻塞 #3
- 阻塞 #4
- 阻塞 #5
- 阻塞 #6
- 阻塞 #7
- 阻塞 #8
- 阻塞 #14

## 元信息

- 预估工作量：4 小时
- Labels：`ci` `backend` `frontend` `P0`
- Milestone：`M0-工程启动`
- Assignee：【组长】
- 分支：`feature/1-project-init`

## 技术备注

- **`pyproject.toml` 是唯一的配置入口**。Ruff、Mypy、Pytest、Coverage 全写在这一个文件里，不额外建 `setup.cfg` / `.pytest.ini` / `tox.ini`，否则四个人四种读法
- **Ruff 的 `line-length` 必须显式设**。默认 88 会让编辑器自动格式化与 `ruff format` 打架，团队统一 100
- **`Settings` 用 `pydantic-settings` 的 `BaseSettings`**，字段名与 `.env.example` 完全一致（大小写不敏感）。这样「`.env.example` 里有的都能读到、读到的都在 `.env.example` 里」这条验收标准可以靠肉眼核对
- **SQLite 的坑**：`create_engine` 需要 `connect_args={"check_same_thread": False}`；测试用 `sqlite+pysqlite:///:memory:` 时，每个连接是独立的内存库，必须用 `StaticPool` 共享，否则 `alembic upgrade head` 建的表在测试里查不到
- **`migrations/env.py` 不要从 `alembic.ini` 读 URL**。从 `app.core.config.Settings` 读，保证开发/CI/演示三处只有一份配置来源
- **页面静态资源必须本地化**。HTMX 与 Alpine.js 各约 40KB，下载到 `app/static/vendor/` 入库。演示环境可能没有外网，引用 CDN 会在答辩时白屏
- **CI 的 `templates` job 依赖本 Issue 产出 `scripts/check-templates.py` 与 `app/templates/` 目录**，两者缺一个都会让 CI 报「找不到路径」
- 若 `pip install` 在 CI 上偶发超时，可在 workflow 加 `pip install --retries 5 --timeout 60`，不要用 `--no-cache-dir`（会让后续步骤变慢）
