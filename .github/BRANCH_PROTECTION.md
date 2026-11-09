# 分支保护与仓库设置操作手册

> 本文件是**给组长的手动操作清单**。GitHub 的分支保护规则、Collaborator 邀请、Labels、Milestone 无法通过提交文件配置，必须在网页上操作。
> 完成后请截图，作为中期检查（第 8 周）A4 项的交付材料。

---

## 1. 邀请组员（Settings → Collaborators）

`https://github.com/encoY3332333/transparent-umbrella/settings/access`

1. 点击 **Add people**
2. 输入组员1、组员2 的 GitHub 用户名或邮箱
3. 权限选择 **Write**（不要给 Admin）
4. 组员收到邮件后在 7 天内接受邀请

**验收**：Settings → Collaborators 列表中显示 3 人。

---

## 2. 开启 main 分支保护（Settings → Rules → Rulesets 或 Branches）

`https://github.com/encoY3332333/transparent-umbrella/settings/rules`

新建一条 Target branches = `main` 的规则，逐项对照勾选：

| # | 保护项（新版界面名称） | 设置值 | 状态 |
|---|---|---|---|
| 1 | Require a pull request before merging | 启用 | [ ] |
| 2 | ↳ Required approvals | **1** | [ ] |
| 3 | ↳ Dismiss stale pull request approvals when new commits are pushed | 启用 | [ ] |
| 4 | ↳ Require review from Code Owners | 启用（CODEOWNERS 填好后） | [ ] |
| 5 | Require status checks to pass | 启用 | [ ] |
| 6 | ↳ 选择状态检查 | `Backend (Java 17)`、`Frontend (Node 22)`、`CI Summary` | [ ] |
| 7 | Require conversation resolution before merging | 启用 | [ ] |
| 8 | Block force pushes | 启用 | [ ] |
| 9 | Restrict deletions | 启用 | [ ] |

> ⚠️ 第 6 项的 status checks 只有在 CI 至少成功跑过一次之后才会出现在下拉列表中。
> 因此顺序是：**先推送 `.github/workflows/ci.yml` → 等第一次 CI 跑完 → 再回来勾选 status checks**。

**验收**：直接 `git push origin main` 应被拒绝，提示 `protected branch hook declined`。

---

## 3. 配置 Labels（Issues → Labels）

`https://github.com/encoY3332333/transparent-umbrella/labels`

GitHub 默认已有 `bug` / `documentation` / `enhancement` 等，建议**新建或改名**为以下集合（与课程考核方案一致）：

| Label | 颜色 | 说明 |
|---|---|---|
| `feature` | `#0E8A16` | 新功能 |
| `bug` | `#D73A4A` | 缺陷 |
| `frontend` | `#1D76DB` | 前端相关 |
| `backend` | `#5319E7` | 后端相关 |
| `docs` | `#0075CA` | 文档 |
| `ci` | `#FBCA04` | 构建与 CI |
| `P0` | `#B60205` | 核心功能，必须完成 |
| `P1` | `#D93F0B` | 争取完成 |
| `P2` | `#FBCA04` | 后续版本 |
| `good first issue` | `#7057FF` | 适合首次上手 |

---

## 4. 创建 Milestone（Issues → Milestones）

`https://github.com/encoY3332333/transparent-umbrella/milestones`

| 标题 | Due date | 描述 |
|---|---|---|
| `M0-工程启动` | 第 4 周末 | 仓库可克隆可启动、CI 全绿、分支保护生效 |
| `v0.1.0 Alpha` | 第 8 周末 | F1/F2/F3/F4 可用，Alpha Release 发布（中期检查） |
| `v0.2.0 Beta` | 第 12 周末 | F5/F6/F7 完成，覆盖率 ≥ 40% |
| `v0.3.0 Pre` | 第 13 周末 | F8/F9 后台功能 |
| `v1.0.0` | 第 16 周末 | P0 全部、P1 ≥ 70%，答辩 |

---

## 5. 创建 14 个 Issue

`docs/issues/` 目录下已备好 14 个 Issue 的完整正文（Markdown）。三种创建方式任选：

### 方式 A：网页逐条粘贴（推荐，最直观）

1. 打开 `https://github.com/encoY3332333/transparent-umbrella/issues/new/choose`
2. 选择 **功能需求** 模板
3. 打开 `docs/issues/01-project-init.md`，把标题填进 Title，正文粘进 Body
4. 右侧设置 Assignee / Labels / Milestone
5. 提交后记录真实 Issue 编号，回填到 `docs/issues/README.md`

### 方式 B：GitHub CLI 批量导入

```bash
cd transparent-umbrella
for f in docs/issues/0*.md; do
  title=$(head -1 "$f" | sed 's/^# //')
  gh issue create --title "$title" --body-file "$f" --label feature
done
```

### 方式 C：先建再改

直接按 `docs/issues/README.md` 的清单表逐条建，标题和要素照抄。

**验收**：Issues 面板共 14 个，每个都有 Assignee、至少 1 个 Label、1 个 Milestone，且备注了预估工时。

---

## 6. 开启 Discussions（可选但加分）

Settings → General → Features → 勾选 **Discussions**。
用于记录需求讨论（B6「协作与文档贡献」中「在 Issue/Discussion 中留下 ≥ 5 条实质性讨论」）。

---

## 7. 发布 v0.0.1 Release

1. 打开 `https://github.com/encoY3332333/transparent-umbrella/releases/new`
2. Tag：`v0.0.1`，Target：`main`
3. Title：`SmartTrip v0.0.1 — 需求基线与工程规范`
4. Release notes 见 `docs/release-notes/v0.0.1.md`
5. 勾选 **Set as a pre-release**（因为还不能运行）
6. Publish release

---

## 8. 自检清单

- [ ] 3 名成员均为 Collaborator（Write 权限）
- [ ] main 分支保护 9 项已勾选，直推被拒绝
- [ ] Labels 至少 10 个，与考核方案一致
- [ ] Milestone 5 个，与 SRS 3.6 节版本规划一致
- [ ] Issue 14 个，人均 4.67 个 ≥ 下限 4
- [ ] CI 至少成功运行 1 次（Actions 面板绿灯）
- [ ] `v0.0.1` Release 已发布
- [ ] README 中的启动步骤已由组外同学实测（A7 要求）

---

## 附：参考链接

- 分支保护（Rulesets）：https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets
- CODEOWNERS 语法：https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners
- Issue / PR 模板：https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests
