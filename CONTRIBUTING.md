# 贡献指南（CONTRIBUTING）

本文件是 SmartTrip 项目的协作规范仓储版，与《GitHub 小组协作规范》一致。**所有成员在提交第一行代码前必须完整阅读。**

---

## 0. 六条硬性约束

违反以下任一条都会被记录在案，直接影响课程考核项 A4 / B2 / B3。

1. **禁止直接向 `main` 推送**。每次直推扣 A4 项 1 分。
2. **禁止自评自合**。自己的 PR 必须由他人 Approve 后才能合并。
3. **禁止空提交、刷量提交、拆分微小改动凑 Commit 数**。累计 3 次 B2 项判 0。
4. **禁止将密钥、数据库口令、API Key 提交入库**。一律使用 `.env` + `.env.example` + `.gitignore`。
5. **禁止无主的 Issue 进入开发**。Issue 必须有 Assignee、Labels、Milestone、验收标准。
6. **禁止无意义提交信息**（`update` / `修改` / `final` / `final2` / `fix bug` / `asdf`）。

---

## 1. 标准开发流程

```
Issue  →  Assign  →  Branch  →  Develop  →  Commit  →  Push  →  PR  →  Review  →  CI  →  Merge  →  Delete Branch
```

```bash
# 1. 永远从最新的 main 切出新分支
git switch main
git pull origin main
git switch -c feature/12-itinerary-schedule

# 2. 小步提交：一个逻辑变更一次提交
git add backend/src/main/java/.../StrategyEngine.java
git commit -m "feat(schedule): add greedy packing for daily activities"
git add backend/src/main/java/.../BudgetCalculator.java
git commit -m "feat(budget): sum cost by four categories"

# 3. 推送并发起 PR（描述中写 Closes #12）
git push -u origin feature/12-itinerary-schedule

# 4. 合并后同步并清理
git switch main
git pull origin main
git branch -d feature/12-itinerary-schedule
```

---

## 2. 分支命名

| 类型 | 格式 | 示例 |
|---|---|---|
| 主分支 | `main` | — （受保护，只接受 PR 合并） |
| 新功能 | `feature/<issue号>-<英文简述>` | `feature/12-itinerary-schedule` |
| 缺陷修复 | `bugfix/<issue号>-<英文简述>` | `bugfix/21-budget-mismatch` |
| 紧急修复 | `hotfix/<issue号>-<英文简述>` | `hotfix/30-token-leak` |
| 文档/构建 | `chore/<英文简述>` | `chore/add-coverage` |

**短生命周期**：Feature Branch 合并后立即删除，不要留残枝。

---

## 3. Commit Message 规范（Conventional Commits）

格式：`<type>(<scope>): <subject>`

**type 限定 8 种**：

| type | 含义 |
|---|---|
| `feat` | 新功能 |
| `fix` | 缺陷修复 |
| `docs` | 文档 |
| `test` | 测试 |
| `refactor` | 重构（非功能、非修复） |
| `perf` | 性能优化 |
| `style` | 格式调整（不影响逻辑） |
| `chore` | 构建 / 依赖 / 工具 |

**规则**：

- subject 使用英文祈使句，首字母小写，结尾不加句号
- 一行不超过 72 字符
- 一个 Commit 只做一件事
- 必要时在正文说明 **why**，而非 what

**本项目 scope 约定**：

- 业务代码：`auth` / `condition` / `schedule` / `budget` / `itinerary` / `poi` / `strategy` / `feedback`
- 文档：`srs` / `readme` / `adr` / `api`
- 构建：`ci` / `deps` / `build`

**对比**：

```
✅ feat(schedule): add greedy packing for daily activities
✅ fix(auth): prevent empty verification code from being submitted
✅ test(budget): add boundary cases for zero-budget input
✅ docs(srs): update business rule BR-08 with thunderstorm

❌ update
❌ 修改
❌ final / final2 / 真的最终版
❌ fix bug
❌ asdf
```

---

## 4. Issue 规范

一个 Issue 对应一个可独立交付的任务，预估工作量 **2–8 小时**。超出 8 小时必须拆分。

**必填要素**：标题（带 `[Feature]` / `[Bug]` / `[Chore]` 前缀）、背景、任务清单（checkbox）、验收标准（可验证陈述）、关联 Issue（依赖/阻塞）、Assignee、Labels、Milestone、预估工时。

模板位于 [`.github/ISSUE_TEMPLATE/`](./.github/ISSUE_TEMPLATE/)。

---

## 5. Pull Request 规范

PR 标题与对应 Commit 主体一致。PR 描述必须填写模板中的 **5 个固定小节**（关联 Issue / 变更说明 / 变更类型 / 测试说明 / 自查清单），缺一项不予评审。

**硬性要求**：

- 描述中必须写 `Closes #<issue号>`，实现 Issue 与代码的双向可追溯
- 建议 diff ≤ 400 行；超过 800 行必须拆分并说明理由
- 禁止自评自合
- PR 创建后 48 小时内必须有人评审；作者需对每条意见 24 小时内响应

模板位于 [`.github/pull_request_template.md`](./.github/pull_request_template.md)。

---

## 6. Code Review 规范

评审不能只写「LGTM」「可以」「+1」。必须使用**行内评论**定位到具体代码行，并给出 **问题 + 原因 + 建议** 三要素。

**6 个检查维度**：

| 维度 | 检查要点 | 示例意见 |
|---|---|---|
| 功能正确性 | 是否满足 Issue 验收标准；边界条件是否覆盖 | AC-3 要求空关键字不触发检索，当前未做 trim，建议提交前 trim 并判空 |
| 可读性 | 命名达意、函数单一职责、无魔法数字 | `plan()` 已 120 行，建议把预算迭代抽为 `rebudget()` 便于单测 |
| 健壮性 | 异常处理、空值、超时、外部失败降级 | 调用 WeatherServer 未设超时，建议 1.5s connect / 3s read + catch 降级 |
| 安全 | 输入校验、密钥是否入库、分享链是否脱敏 | 分享接口返回体含 `tourist.phone`，违反 BR-17，建议改用 DTO |
| 性能 | N+1 查询、循环内调用、无缓存的外部请求 | 循环内逐个调 `getRouteTime()` 会产生近 4 万次调用，违反 BR-10，改批量矩阵接口 |
| 测试 | 是否为自己改的逻辑补测试；断言是否有实际校验 | 新增 `revalidate()` 缺「时间冲突」「超预算」两条分支，建议补充 |

**评审结论**只能是三种：`Approve`（通过）、`Comment`（提建议不阻塞）、`Request changes`（必须修改）。

**有效评审** = 具体问题 + 原因 + 建议。仅 Approve 无评论不计入。

---

## 7. CI 门禁

`.github/workflows/ci.yml` 在 `push` 到 main 与向 main 发起 PR 时触发，四步：**安装依赖 → Lint → 测试（含覆盖率）→ 构建**。

CI 是**必需状态检查**，红灯期间禁止合并。连续红灯超过 7 天每次扣 A6 项 1 分，因此红灯必须当天处理。

---

## 8. 其他约定

- 提交业务代码时同步更新对应测试；核心 Service 层覆盖率不低于 40%
- 涉及架构决策时，在 `docs/adr/` 新增一条 ADR
- 涉及接口变更时，同步更新 `docs/api.md`
- 会议结束后 24 小时内把纪要提交到 `docs/meetings/`
- 使用 AI 辅助生成的代码必须经本人理解、测试、改造，并在 PR 描述中注明

---

## 9. 冲突处理

```bash
git switch feature/12-itinerary-schedule
git fetch origin
git merge origin/main

# 出现 CONFLICT，手工解决后：
git add .
git commit -m "chore(merge): resolve conflict with main in schedule service"
git push
# PR 自动更新，CI 重新检查
```

**主动解决冲突，不要把冲突甩给他人。**
