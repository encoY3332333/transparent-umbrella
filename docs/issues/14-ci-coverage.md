# [Chore] CI 门禁、覆盖率与性能基线

## 背景 / Background

`.github/workflows/ci.yml` 已入库，但当前后端/前端目录为空，CI 走的是「跳过」分支——看起来是绿的，其实什么都没测。这个 Issue 负责让 CI 真正开始工作，并把它绑定为合并的必需状态检查。

对应考核方案：A6（自动化测试与 CI/CD，10 分）、A4（分支保护）

## 需求描述 / Description

补齐 CI 四步的真实执行，产出覆盖率报告，配置性能基线测试，并把 CI 结果设置为 main 分支的必需状态检查。

## 任务清单 / Tasks

- [ ] 配置 `jacoco-maven-plugin`：`prepare-agent` + `report`，覆盖率报告输出到 `target/site/jacoco/`
- [ ] 配置 `maven-checkstyle-plugin`：使用 Google Checks 或自定义 `checkstyle.xml`
- [ ] 配置前端 `vitest` + `@vitest/coverage-v8`，`npm test` 产出 `coverage/`
- [ ] 核心 Service 层（schedule / budget 包）覆盖率门槛设为 40%，在 `pom.xml` 中配置 `jacoco:check` 规则
- [ ] 添加性能基线测试 `PlanPerformanceTest`：200 个 POI、7 天行程，断言 P95 ≤ 10 秒（NFR-P1）
- [ ] 确认 CI 在 PR 上真实运行（不再是跳过分支），并截图 Actions 面板
- [ ] 在 Settings → Rules 中把 `Backend (Java 17)` / `Frontend (Node 22)` / `CI Summary` 设为必需状态检查
- [ ] 在 README 中添加 CI 徽章
- [ ] 配置 `actions/upload-artifact` 上传覆盖率报告，保留 14 天

## 验收标准 / Acceptance Criteria

- [ ] 向 main 发起 PR 时，CI 的四个 job 全部真实执行（无「跳过」提示）
- [ ] 故意提交一个失败测试的 PR，CI 变红且**无法合并**（验证门禁生效）
- [ ] 覆盖率报告可在 Actions 的 artifacts 中下载并打开
- [ ] 核心 Service 层覆盖率低于 40% 时 CI 失败
- [ ] 性能基线测试在 CI 上稳定通过（连续 3 次运行无 flaky）
- [ ] README 顶部显示 CI 状态徽章，且徽章为绿色
- [ ] Actions 面板中最近 5 次 PR 运行均绿灯

## 关联 / Related

- 依赖 #1

## 元信息

- 预估工作量：4 小时
- Labels：`ci` `P0`
- Milestone：`M0-工程启动`
- Assignee：【组长】
- 分支：`feature/14-ci-coverage`

## 备注

CI 里的「跳过」分支是为了让仓库在骨架未就绪时也能合并文档 PR。**这个 Issue 关闭后，跳过分支应保留**（作为防御），
但必须以「真实执行」的状态作为验收依据，否则等于没做门禁。
