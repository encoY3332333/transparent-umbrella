# [Chore] 初始化仓库与工程基建

## 背景 / Background

仓库当前只有 `README.md`，后端与前端目录尚未创建，`.github/` 下的模板与 CI 已就位但无法运行（CI 会走跳过分支）。
本 Issue 是整个项目的**阻塞项**：后续所有功能 Issue（#2–#13）都依赖可运行的骨架。

对应 SRS：`docs/srs/SRS-v1.0.md` 第 4.2 节 设计约束

## 需求描述 / Description

搭建前后端可运行的最小工程骨架，并验证「克隆 → 启动 → 访问」全链路可用。

## 任务清单 / Tasks

- [ ] 创建 `backend/`：Spring Boot 3.2 + Java 17 + Maven 工程，含 `pom.xml`、`application.yml`、`SmartTripApplication.java`、`/api/health` 健康检查接口
- [ ] 创建 `frontend/`：Vue 3 + Vite + TypeScript 工程，含 `package.json`、`vite.config.ts`、`src/main.ts`、`src/App.vue`、`src/router/index.ts`
- [ ] 后端接入 MyBatis-Plus 与 MySQL 驱动，配置 `application-dev.yml` 从环境变量读取连接信息
- [ ] 添加 `docker-compose.yml`（仅 db 服务，含初始化 SQL 脚本挂载）
- [ ] 前端配置 `/api` 代理到 `http://localhost:8080`，避免开发期跨域
- [ ] 补充 `backend/src/test/` 与 `frontend/tests/` 各 1 个冒烟测试
- [ ] 更新 README 的「快速开始」，确认步骤可被组外同学照做成功

## 验收标准 / Acceptance Criteria

- [ ] `git clone` 后执行 `cd backend && mvn -B test` 全绿
- [ ] `mvn spring-boot:run` 启动成功，`GET http://localhost:8080/api/health` 返回 `{"status":"UP"}`
- [ ] `cd frontend && npm ci && npm run dev` 启动成功，浏览器访问 `http://localhost:5173` 显示首页
- [ ] `npm run build` 产出 `dist/` 且无 TS 类型错误
- [ ] GitHub Actions 上 `Backend (Java 17)`、`Frontend (Node 22)` 两个 job 由「跳过」变为「通过」
- [ ] `.env.example` 中的每一项在 `application.yml` / `vite.config.ts` 中都有对应的读取点（无遗漏、无多余）
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

- `pom.xml` 中 `maven-checkstyle-plugin` 与 `jacoco-maven-plugin` 必须配置，否则 CI 的 Lint 与覆盖率步骤会失败
- 前端 `package.json` 的 `scripts` 需包含 `dev` / `build` / `test` / `lint`，CI 按这四个名字调用
- 若 `mvn dependency:go-offline` 在 CI 上偶发失败，可在 workflow 里改为 `mvn -B -q compile` 预热依赖
