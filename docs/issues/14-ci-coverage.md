# [Chore] CI 门禁、覆盖率与性能基线

## 背景 / Background

`.github/workflows/ci.yml` 已入库，但当前 `backend/` 目录为空，CI 走的是「跳过」分支——看起来是绿的，其实什么都没测。这个 Issue 负责让 CI 真正开始工作，并把它绑定为合并的必需状态检查。

对应考核方案：A6（自动化测试与 CI/CD，10 分）、A4（分支保护）

## 需求描述 / Description

补齐 CI 各步骤的真实执行，产出覆盖率报告，配置性能基线测试，并把 CI 结果设置为 `main` 分支的必需状态检查。

## 任务清单 / Tasks

- [ ] 在 `backend/pyproject.toml` 的 `[tool.coverage.run]` 中开启 `branch = true`，`source = ["app"]`，`omit = ["app/seed/*", "*/migrations/*"]`
- [ ] 在 `[tool.pytest.ini_options]` 中设置 `addopts = "-q --strict-markers"`，注册 `slow` 与 `perf` 两个 marker
- [ ] 确认 Ruff 规则集足够严格：`select = ["E","F","I","UP","B","SIM","RUF"]`，`ignore = ["E501"]`（行长由 formatter 管）
- [ ] 核心模块覆盖率门槛：`engine/` 与 `services/` 单独设 60%，其余 40%；用 `[tool.coverage.report]` 的 `fail_under` 与 CI 的 `--cov-fail-under` 双重约束
- [ ] 添加性能基线测试 `tests/perf/test_plan_performance.py`，标记 `@pytest.mark.perf`：200 个 POI、7 天行程，断言 P95 ≤ 10 秒（NFR-P1）
- [ ] 在 CI 中新增 `perf` 步骤，仅对 `main` 分支与 `workflow_dispatch` 运行（PR 上跑太慢）
- [ ] 添加 `scripts/check-doc-links.py`，检查 docs 下 Markdown 的相对链接是否有效，接入 `lint-repo` job
- [ ] 确认 CI 在 PR 上真实运行（不再是跳过分支），并截图 Actions 面板
- [ ] 在 Settings → Rules 中把 `Backend (Python 3.11)` / `Templates (Jinja2)` / `CI Summary` 设为必需状态检查
- [ ] 在 README 中添加 CI 徽章
- [ ] 确认 `actions/upload-artifact` 上传 `coverage.xml` 与 `htmlcov/`，保留 14 天

## 验收标准 / Acceptance Criteria

- [ ] 向 `main` 发起 PR 时，CI 的四个 job（`Backend` / `Templates` / `Repo Conventions` / `CI Summary`）全部真实执行（无「跳过」提示）
- [ ] 故意提交一个失败测试的 PR，CI 变红且**无法合并**（验证门禁生效）
- [ ] 故意把 `engine/scoring.py` 的覆盖率降到 60% 以下，CI 变红并指出是哪个文件
- [ ] 覆盖率报告可在 Actions 的 artifacts 中下载，`htmlcov/index.html` 可正常打开
- [ ] 性能基线测试连续 3 次运行结果稳定，无 flaky（记录三次耗时）
- [ ] README 顶部显示 CI 状态徽章，且徽章为绿色
- [ ] Actions 面板中最近 5 次 PR 运行均绿灯

## 关联 / Related

- 依赖 #1
- 依赖 #3、#4、#5、#6、#7（没有业务代码时覆盖率无意义）

## 元信息

- 预估工作量：4 小时
- Labels：`ci` `P0`
- Milestone：`M0-工程启动`
- Assignee：@richkoijx
- 分支：`feature/14-ci-coverage`

## 备注

CI 里的「跳过」分支是为了让仓库在骨架未就绪时也能合并文档 PR。**这个 Issue 关闭后，跳过分支应保留**（作为防御），
但必须以「真实执行」的状态作为验收依据，否则等于没做门禁。

## 技术备注

- **`--cov-fail-under` 与 `fail_under` 不要同时用**。两者都在时，CI 会按更严的那个判定，排查时容易困惑。约定：CI 命令里用 `--cov-fail-under=40` 做总门槛，`pyproject.toml` 里用 `[tool.coverage.report]` 的 `exclude_lines` 排除 `if TYPE_CHECKING:`、`raise NotImplementedError` 等不可测分支
- **性能测试不能用 `pytest-benchmark` 的默认断言**。CI 机器性能波动大，绝对耗时断言会 flaky。做法：取 5 次运行的中位数，断言 `median <= 10.0`，并在失败时打印全部 5 次耗时供判断
- **`pytest.mark.perf` 必须注册在 `pytest.ini_options.markers` 里**，否则 `--strict-markers` 会直接报错。这是 `--strict-markers` 的常见首个坑
- **分支保护的 job 名称变更**：从 Java 时代的 `Backend (Java 17)` / `Frontend (Node 22)` 改为 `Backend (Python 3.11)` / `Templates (Jinja2)`。GitHub 的分支保护按**名称**匹配，改名不会自动迁移——老规则会永远「等待一个不存在的检查」。若之前已配置过，必须先删旧规则再建新规则
- **文档链接检查脚本不要写成 CI 内联 bash**。写成 `scripts/check-doc-links.py` 可以本地跑、可以单测，比塞在 YAML 里的几十行 `for` 循环可维护
