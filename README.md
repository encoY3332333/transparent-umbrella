# transparent-umbrella

[![CI](https://github.com/encoY3332333/transparent-umbrella/actions/workflows/ci.yml/badge.svg)](https://github.com/encoY3332333/transparent-umbrella/actions/workflows/ci.yml)

> 智能旅游规划系统（SmartTrip）——输入出发地、目的地、时间与预算，结合天气、历史游览人数与当地活动，自动编排一份可执行、可调整的旅行行程。

![status](https://img.shields.io/badge/status-v0.1.0--planning-blue)
![course](https://img.shields.io/badge/course-软件工程与项目管理-green)
![license](https://img.shields.io/badge/license-MIT-yellow)

---

## 这是什么

自由行游客规划一次 2–5 天的中短途旅行，通常要在多个 App 之间反复切换、手工拼行程，耗时 2 小时以上，而且容易踩坑：把户外景点排在暴雨天、把两个通勤 90 分钟的景点塞进同一个上午、玩到一半发现超预算。

SmartTrip 把这些重复劳动自动化。用户只需输入少量条件，系统即综合**天气、历史人流量、当地活动、通勤距离、预算**五类约束，生成 1–3 套可行行程，并给出推荐理由、拥挤度提示与预算明细；行程支持拖拽调整、锁定必去项后重排、只读分享与日历导出。

**差异化定位**：现有产品各有一项能力，但没有一个把「天气 + 人流量 + 预算」同时纳入自动排程的约束体系。本项目就做这一件事。

## 功能特性

| 编号 | 功能 | 优先级 | 状态 |
|---|---|---|---|
| F1 | 游客登录与偏好建档 | P0 | 规划中 |
| F2 | 出行条件录入与校验 | P0 | 规划中 |
| F3 | 智能行程生成（核心） | P0 | 规划中 |
| F4 | 行程可视化与预算明细 | P0 | 规划中 |
| F5 | 行程局部调整 | P1 | 规划中 |
| F6 | 行程收藏与分享 | P1 | 规划中 |
| F7 | 规划反馈 | P1 | 规划中 |
| F8 | POI 与活动数据维护 | P2 | 规划中 |
| F9 | 推荐策略参数配置 | P2 | 规划中 |

详细需求见 [`docs/srs/`](./docs/srs/)。

## 当前进度

| 里程碑 | 内容 | 状态 |
|---|---|---|
| 文档基线 | SRS v1.0（14 张 UML 图已嵌入）、架构说明、接口清单、6 份 ADR | ✅ 已冻结（`v0.0.1`） |
| 工程配置 | CI、Issue/PR 模板、CODEOWNERS、分支规范 | ✅ 已生效，CI 绿灯 |
| 任务拆分 | [14 个 Issue](https://github.com/encoY3332333/transparent-umbrella/issues?q=is%3Aissue) 分入 5 个 Milestone，共 92 人时 | ✅ 已创建 |
| 代码 | `backend/` 应用脚手架（FastAPI + Jinja2 单体） | ✅ 已跑通（Issue #1） |

- 版本发布：[`v0.0.1`](https://github.com/encoY3332333/transparent-umbrella/releases/tag/v0.0.1)（pre-release，仅文档与配置）
- 任务看板：[Issues](https://github.com/encoY3332333/transparent-umbrella/issues) · [Milestones](https://github.com/encoY3332333/transparent-umbrella/milestones)
- 考核项对照：[`docs/assessment-checklist.md`](./docs/assessment-checklist.md)（A1–A8 / B1–B7 逐项自查）
- 会议记录：[`docs/meetings/`](./docs/meetings/) · 进展报告：[`docs/reports/`](./docs/reports/) · 架构决策：[`docs/adr/`](./docs/adr/)

## 技术栈

**纯 Python 技术栈**，前后端同仓同语言，一条 `pip install` 即可跑起来，不需要 Node、JDK 或数据库服务。

| 层 | 技术选型 | 选型理由 |
|---|---|---|
| 表现层 | Jinja2 模板 + HTMX + Alpine.js | 服务端渲染，改完刷新即见效果；HTMX 用 HTML 属性做局部刷新，省掉一套前端状态同步 |
| 业务层 | Python 3.11 + FastAPI | 类型注解即校验：Pydantic v2 直接承载 SRS 的 24 条业务规则；自动生成 OpenAPI 文档 |
| 排程引擎 | 纯 Python（标准库） | 算法写成无副作用的纯函数，不碰数据库，单测不需要 mock，覆盖率好拉 |
| 数据层 | SQLAlchemy 2.0 + Alembic | 声明式模型 + 版本化迁移；开发用 SQLite 零配置，生产切 MySQL 只改一行 `DATABASE_URL` |
| 质量工具 | Ruff + Mypy + Pytest | Ruff 一个工具承担 lint 与格式化；Mypy 卡住类型漂移；Pytest 的 fixture 便于构造行程测试数据 |
| CI/CD | GitHub Actions | 与课程要求的 PR 门禁、状态检查天然集成 |

> **为什么不用 Java / Vue**：初版设计是 Spring Boot + Vue 3，后来全组评估后改成纯 Python。决策记录见 [ADR-007](./docs/adr/ADR-007-switch-to-python-stack.md)——里面写了切换的代价（重写架构文档与 14 个 Issue 的技术备注）和收益（三人无需切换语言、CI 从 2 套运行时降到 1 套、本地环境从「JDK + Maven + Node + MySQL」降到「Python + SQLite」）。

架构说明与 ADR 见 [`docs/architecture.md`](./docs/architecture.md)、[`docs/adr/`](./docs/adr/)。

## 快速开始

> ✅ **当前版本 v0.1.0-alpha：工程骨架已跑通**。健康检查、首页、静态资源、Alembic 基线迁移、
> 统一错误响应、外部调用代理基类与测试全部就位，CI 里 `Backend (Python 3.11)` 与
> `Templates (Jinja2)` 两个 job 已由「跳过」变为「真实执行」。
>
> 业务功能（登录、条件录入、行程生成……）按 [14 个 Issue](https://github.com/encoY3332333/transparent-umbrella/issues) 逐步落地。

### 环境要求

- **Python >= 3.11**（唯一必需项）
- 可选：MySQL >= 8.0（不装则用 SQLite，零配置）
- 可选：Docker Desktop（用于演示环境 `docker compose up`）

### 启动步骤

```bash
git clone https://github.com/encoY3332333/transparent-umbrella.git
cd transparent-umbrella/backend

# 1. 虚拟环境与依赖
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 2. 配置环境变量
cp ../.env.example .env            # 默认 SQLite，无需改任何值即可启动

# 3. 建表（Alembic 迁移）
alembic upgrade head

# 4. 启动
uvicorn app.main:app --reload --port 8000
```

打开 http://localhost:8000 即可访问。接口文档在 http://localhost:8000/docs（FastAPI 自动生成，与 `docs/api.md` 同源）。

> 首次启动会自动创建 SQLite 文件；切换到 MySQL 只需把 `.env` 里的 `DATABASE_URL` 改成 `mysql+pymysql://...` 并 `pip install -e ".[mysql]"`，再执行一次 `alembic upgrade head`。
> 演示 POI 数据在 `backend/app/seed/pois.json`，由 Issue #12 的数据导入脚本读入（当前尚未接入）。

### 常用命令

```bash
pytest -q --cov=app            # 跑测试并输出覆盖率
ruff check app tests --fix     # 静态检查并自动修复
ruff format app tests          # 格式化
mypy app                       # 类型检查
python ../scripts/check-templates.py   # 检查 Jinja2 模板语法与静态资源引用
```


### 演示账号

| 角色 | 账号 | 密码 |
|---|---|---|
| 游客 | 手机号 + 短信验证码（开发环境固定 `123456`），登录功能在 Issue #2 落地 | — |
| 运营管理员 | `admin` | 见 `.env` 中的 `ADMIN_INIT_PASSWORD` |

## 项目结构

```
transparent-umbrella/
├── README.md                    项目说明（本文件）
├── LICENSE                      MIT
├── CONTRIBUTING.md              分支 / Commit / PR / 评审规范
├── CHANGELOG.md                 按版本记录变更
├── .gitignore
├── .env.example                 环境变量样例（不含真实密钥）
├── .github/
│   ├── workflows/ci.yml         CI：backend / templates / lint-repo / ci-summary 四段
│   ├── ISSUE_TEMPLATE/          feature.md / bug.md
│   ├── pull_request_template.md
│   ├── CODEOWNERS               路径 → 负责人映射
│   └── BRANCH_PROTECTION.md     组长手动配置清单（分支保护 / Labels / Milestones）
├── docker-compose.yml           演示环境：MySQL 8 + web（开发不用它）
├── backend/                     Python 应用（Issue #1 已落地）
│   ├── pyproject.toml           依赖与工具配置（Ruff / Mypy / Pytest 均在此）
│   ├── Dockerfile               演示镜像：python:3.11-slim + uvicorn
│   ├── alembic.ini              数据库迁移配置
│   ├── app/
│   │   ├── main.py              应用入口，挂载路由与中间件
│   │   ├── core/                配置、异常、安全、日志、依赖注入
│   │   ├── api/                 路由层，一个用例一个模块
│   │   ├── services/            业务编排，唯一的事务边界
│   │   ├── engine/              排程算法（纯函数，不依赖数据库）
│   │   ├── adapters/            7 个外部系统代理（超时 / 缓存 / 降级）
│   │   ├── models/              SQLAlchemy 模型
│   │   ├── schemas/             Pydantic 模型（请求 / 响应 / 校验）
│   │   ├── templates/           Jinja2 模板
│   │   ├── static/              CSS、HTMX、Alpine.js
│   │   └── seed/                演示数据
│   ├── migrations/              Alembic 版本文件
│   └── tests/                   单元测试 + 接口测试
├── docs/
│   ├── srs/                     软件需求规格说明书（基线 V1.0）+ 基线管理说明
│   ├── architecture.md          架构说明（分层、数据流、ADR 索引）
│   ├── api.md                   接口清单（9 个用例、30 个错误码）
│   ├── diagrams/                UML 图源文件（PlantUML）：用例图 / 9 张顺序图 / 类图 / 3 张状态图
│   ├── adr/                     架构决策记录（ADR-001 ~ 007）
│   ├── issues/                  14 个 Issue 的完整正文
│   ├── meetings/                会议纪要（md + docx 双份）
│   ├── contributions/           个人工程贡献说明书模板
│   ├── guides/                  协作规范、需求获取问卷与访谈提纲
│   ├── reports/                 项目进展报告存档
│   ├── release-notes/           版本发布说明
│   ├── PUSH_GUIDE.md            首次推送与仓库配置的操作指引
│   └── 附件5_需求清单与Issue拆分表.xlsx
└── scripts/
    ├── check-templates.py       CI 调用：模板语法与静态资源引用检查
    └── render-diagrams.py       PlantUML 渲染（生成 SRS 插图）
```


## 团队与分工

| 成员 | 角色 | 主要职责 | GitHub |
|---|---|---|---|
| 【组长】 | Maintainer / Tech Lead | 架构、排程引擎、仓库治理、CI、评审、发布 | @encoY3332333 |
| 【组员1】 | Requirements / 页面与交互 | 需求获取与用例建模、Jinja2 模板与 HTMX 交互、评审 | @【组员1的GitHub名】 |
| 【组员2】 | QA & Data / 接口与数据 | 外部数据源适配、SQLAlchemy 模型、路由与 Schemas、测试与覆盖率 | @【组员2的GitHub名】 |

评审交叉安排：组长的 PR 由组员1 评审，组员1 的 PR 由组员2 评审，组员2 的 PR 由组长评审——**任何 PR 都不允许自评自合**。

## 贡献流程

所有改动都必须走：`Issue → Branch → Commit → Push → PR → Review → CI → Merge → 删除分支`。

```bash
git switch main && git pull origin main
git switch -c feature/12-itinerary-schedule
# ... 开发 ...
git commit -m "feat(schedule): add greedy packing for daily activities"
git push -u origin feature/12-itinerary-schedule
```

详细规范（分支命名、Commit 类型、PR 模板、评审 6 维度清单、6 条硬性约束）见 [`CONTRIBUTING.md`](./CONTRIBUTING.md)。

**main 分支受保护**：禁止直推，至少 1 名他人 Approve，CI 必须通过。

## 版本规划

| 版本 | 时间 | 内容 |
|---|---|---|
| v0.1.0 Alpha | 第 8 周 | 工程基建 + F1/F2/F3/F4 可用 |
| v0.2.0 Beta | 第 12 周 | F5/F6/F7 完成，覆盖率 ≥ 40% |
| v0.3.0 Pre | 第 13 周 | F8/F9 后台功能 |
| v1.0.0 | 第 16 周 | P0 全完成、P1 ≥ 70%，文档齐全 |

## 许可证

[MIT](./LICENSE)
