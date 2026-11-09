# transparent-umbrella

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

## 技术栈

| 层 | 技术选型 | 选型理由 |
|---|---|---|
| 表现层 | Vue 3 + Vite + TypeScript | 构建快，适合短周期；组合式 API 便于复用行程卡片逻辑 |
| 业务层 | Spring Boot 3 + Java 17 | 排程算法用 Java 便于写单元测试（JUnit 5 + JaCoCo 覆盖率） |
| 数据层 | MySQL 8 + MyBatis-Plus | 行程/POI 为强关系结构；本地可用 docker compose 一键起库 |
| CI/CD | GitHub Actions | 与课程要求的 PR 门禁、状态检查天然集成 |

架构说明与 ADR 见 [`docs/architecture.md`](./docs/architecture.md)、[`docs/adr/`](./docs/adr/)。

## 快速开始

> ⚠️ **当前版本 v0.0.1，代码尚未初始化**（前后端目录为空）。以下为约定好的启动方式，脚手架（Issue #1）落地后即可执行。
>
> 此刻仓库里可用的东西是：需求基线、架构与接口契约、14 个可开工的 Issue、CI 与协作配置。详见 [Release v0.0.1](./docs/release-notes/v0.0.1.md)。

### 环境要求

- Node.js >= 22
- JDK >= 17
- MySQL >= 8.0（或使用 docker compose）
- Docker Desktop（可选）

### 启动步骤

```bash
git clone https://github.com/encoY3332333/transparent-umbrella.git
cd transparent-umbrella

# 1. 配置环境变量
cp .env.example .env          # 填写数据库连接与第三方 API Key

# 2. 启动数据库（二选一）
docker compose up -d db

# 3. 启动后端
cd backend
mvn spring-boot:run           # 默认 http://localhost:8080

# 4. 启动前端（另开终端）
cd frontend
npm ci
npm run dev                   # 默认 http://localhost:5173
```

### 演示账号

| 角色 | 账号 | 密码 |
|---|---|---|
| 游客 | （脚手架落地后补充） | — |
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
│   ├── workflows/ci.yml         CI：backend / frontend / lint-repo / ci-summary 四段
│   ├── ISSUE_TEMPLATE/          feature.md / bug.md
│   ├── pull_request_template.md
│   ├── CODEOWNERS               路径 → 负责人映射
│   └── BRANCH_PROTECTION.md     组长手动配置清单（分支保护 / Labels / Milestones）
├── docs/
│   ├── srs/                     软件需求规格说明书（基线 V1.0）+ 基线管理说明
│   ├── architecture.md          架构说明（分层、数据流、ADR 索引）
│   ├── api.md                   接口清单（9 个用例、39 个错误码）
│   ├── diagrams/                UML 图源文件（PlantUML）：用例图 / 9 张顺序图 / 类图 / 3 张状态图
│   ├── adr/                     架构决策记录（ADR-001 ~ 006）
│   ├── issues/                  14 个 Issue 的完整正文
│   ├── meetings/                会议纪要（md + docx 双份）
│   ├── contributions/           个人工程贡献说明书模板
│   ├── guides/                  协作规范、需求获取问卷与访谈提纲
│   ├── release-notes/           版本发布说明
│   └── 附件5_需求清单与Issue拆分表.xlsx
├── backend/                     Spring Boot 3 服务端（Issue #1 创建）
├── frontend/                    Vue 3 + Vite 前端（Issue #1 创建）
└── tests/                       集成测试与测试数据
```

## 团队与分工

| 成员 | 角色 | 主要职责 | GitHub |
|---|---|---|---|
| 【组长】 | Maintainer / Tech Lead | 架构、排程算法、仓库治理、CI、评审、发布 | @encoY3332333 |
| 【组员1】 | Requirements / Frontend | 需求获取与用例建模、前端页面与交互、评审 | @【组员1的GitHub名】 |
| 【组员2】 | QA & Data / Backend | 外部数据源对接、数据模型、后端接口、测试与覆盖率 | @【组员2的GitHub名】 |

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
