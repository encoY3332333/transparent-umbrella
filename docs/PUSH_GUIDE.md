> 这份文件的用途：我（AI）已经把仓库内容全部准备好并在本地完成提交，但当前环境**无法访问 github.com 完成推送**（详见文末「为什么我推不上去」）。请按下面的步骤把提交推上去。可选方案从「最省事」到「最可控」排列，**选一个就行**。

---

# 方案 A：用 GitHub Desktop 推送（最省事，推荐）

前提：你的电脑装了 GitHub Desktop，且已登录 `encoY3332333` 账号。

1. 打开 GitHub Desktop → 菜单 **File → Add local repository**
2. 选择路径：`D:\软件工程\transparent-umbrella`
3. 如果提示「这不是一个 Git 仓库」，点 **create a repository** 时把路径指向同一目录即可（不要勾选初始化 README）
4. 左侧会显示 1 个待推送的提交：`chore(repo): bootstrap project skeleton and collaboration setup`
5. 右上角点 **Push origin**

推送完成后到 https://github.com/encoY3332333/transparent-umbrella 确认文件已出现。

---

# 方案 B：用 VS Code 推送

1. VS Code → **文件 → 打开文件夹** → `D:\软件工程\transparent-umbrella`
2. 左侧「源代码管理」图标（Ctrl+Shift+G）会显示 1 个未推送的提交
3. 点 **同步更改**（或 **推送**），按提示用浏览器登录 GitHub 授权

VS Code 会用 GitHub 账号的 OAuth 完成认证，不需要手动生成 Token。

---

# 方案 C：装 GitHub CLI 后一条命令

```bash
# 1. 安装（Windows，二选一）
winget install --id GitHub.cli
# 或到 https://cli.github.com/ 下载 msi

# 2. 登录（会打开浏览器）
gh auth login

# 3. 推送
cd D:\软件工程\transparent-umbrella
git push origin main
```

---

# 方案 D：生成 Personal Access Token 后命令行推送

1. 打开 https://github.com/settings/tokens → **Generate new token (classic)**
2. Note 填 `course-project`，Expiration 选 30 天，勾选 **`repo`** 权限
3. 生成后复制 token（只显示一次）

```bash
cd D:\软件工程\transparent-umbrella
git push https://<你的token>@github.com/encoY3332333/transparent-umbrella.git main
```

> 注意：这条命令会把 token 写进 shell 历史。更安全的做法是
> `git remote set-url origin https://<token>@github.com/...` 用完后
> `git remote set-url origin https://github.com/encoY3332333/transparent-umbrella.git` 改回来。

---

# 方案 E：如果你在别的机器上操作，用 bundle 文件

我在 `D:\软件工程\transparent-umbrella-骨架.bundle` 打了一个 git bundle（235 KB，含全部提交历史）。拷到任何一台能上 GitHub 的机器：

```bash
git clone D:\软件工程\transparent-umbrella-骨架.bundle my-repo
cd my-repo
git remote set-url origin https://github.com/encoY3332333/transparent-umbrella.git
git push origin main
```

---

# 推送之后必须做的 8 件事（组长操作，不能代劳）

这些是 GitHub **网页设置**，任何工具都无法代替你点。完整操作步骤见
[`.github/BRANCH_PROTECTION.md`](../.github/BRANCH_PROTECTION.md)。

| # | 事项 | 位置 | 说明 |
|---|---|---|---|
| 1 | **推进去之后第一件事：不要马上开分支保护** | — | 先让 CI 跑一次，否则「Require status checks」里选不到任何检查项 |
| 2 | 邀请 2 名 Collaborator | Settings → Collaborators | 用组员真实的 GitHub 用户名 |
| 3 | 创建 10 个 Labels | Issues → Labels | 清单见 BRANCH_PROTECTION.md 第 4 节 |
| 4 | 创建 5 个 Milestone | Issues → Milestones | M0-工程启动 / v0.1.0 Alpha / v0.2.0 Beta / v0.3.0 Pre / v1.0.0 |
| 5 | 创建 14 个 Issue | Issues → New issue | 三种方式（手动 / CLI / 网页批量）见 BRANCH_PROTECTION.md 第 6 节 |
| 6 | 开启分支保护 9 项 | Settings → Branches → Add rule | 对照表见 BRANCH_PROTECTION.md 第 3 节 |
| 7 | 开 Discussions（可选） | Settings → General → Features | 用于课程讨论留痕 |
| 8 | 建 v0.0.1 Release | Releases → Draft a new release | 正文直接粘贴 `docs/release-notes/v0.0.1.md` |

---

# 另外：替换占位符（建议组长在一个 PR 里统一改）

全仓库还有 122 处占位符：

| 占位符 | 出现次数 | 替换为 |
|---|---|---|
| `【组长】` | 49 | 组长真实姓名 |
| `【组员1】` | 34 | 组员1 真实姓名 |
| `【组员2】` | 31 | 组员2 真实姓名 |
| `【组员1的GitHub名】` / `【组员2的GitHub名】` | 2 | GitHub 用户名 |
| `【GitHub用户名】` | 3 | 你自己的 GitHub 用户名（在 `docs/contributions/_template.md` 中） |
| `【姓名】` `【学号】` | 2 | 同上 |

**注意**：`docs/contributions/_template.md` 里的 `【方案内容】`「【具体事件】」等是**模板引导语**，不是占位符，不要替换。

批量替换建议用 VS Code 的「在文件中替换」（Ctrl+Shift+H），逐个确认后再提交——**不要**用脚本一把梭，容易误伤。

---

# 为什么我推不上去

我做了三轮排查：

| 尝试 | 结果 |
|---|---|
| `git ls-remote origin`（直连） | `schannel: server closed abruptly` —— TLS 层被中断 |
| 走环境里的 `HTTP_PROXY=http://127.0.0.1:25099` | `CONNECT tunnel failed, response 502` —— 代理不放行 git 协议 |
| 绕过代理直连 | `Could not connect to github.com:443 after 21096 ms` —— 超时 |
| `api.github.com` 只读访问 | **200 OK** —— 说明能读到，但推送所需的认证通道走不通 |
| 检查 `GITHUB_TOKEN` / `GH_TOKEN` 环境变量 | **不存在** |

结论：这个沙箱环境对 GitHub 只有只读的 HTTPS API 通道，**没有 git 的认证推送通道**，也没有你的凭据。所以我能做到的最远处是「本地 commit 完成 + 生成 bundle」，最后一步必须由你在本地完成。

本地提交已经就绪，你不需要重新生成任何文件：

```
4ce9be0  chore(repo): bootstrap project skeleton and collaboration setup
f33eca7  Initial commit
```
