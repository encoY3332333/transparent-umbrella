> 这份文件的用途：仓库内容已全部准备好并在本地完成提交（3 个 commit）。**只剩「推送 + GitHub 网页配置」两步需要人来做**——认证与网页设置无法由工具代劳。
>
> **重要前提已处理**：本机 git 默认的 `schannel` SSL 后端连接 GitHub 会报 `server closed abruptly`，已全局改为 `openssl`（`git config --global http.sslBackend openssl`）。若换机器操作遇到同样报错，执行这一条命令即可。

---

# 方案 B：用 VS Code 推送（本机已就绪，推荐）

VS Code 已打开仓库窗口（识别到 66 个文件）。只需三步：

**第 1 步：登录 GitHub（只需一次）**
左下角人形图标 → **使用 GitHub 登录** → 浏览器会弹出授权页 → 点 **Authorize Visual Studio Code** → 回到 VS Code。

**第 2 步：推送**
左侧「源代码管理」图标（`Ctrl+Shift+G`）→ 三个点 `...` 菜单 → **拉取、推送** → **推送**（或直接点状态栏底部的同步图标）。

**第 3 步：验证**
浏览器打开 https://github.com/encoY3332333/transparent-umbrella ，应看到 66 个文件与 3 条 commit 记录。

> 若第 2 步报 `could not read Username`：说明第 1 步未成功。VS Code 的 Git 认证走凭据管理器，需先在 VS Code 内完成 GitHub 登录，而不是在网页上登录。

---

# 方案 A：用 GitHub Desktop 推送

前提：你的电脑装了 GitHub Desktop，且已登录 `encoY3332333` 账号。

1. 打开 GitHub Desktop → 菜单 **File → Add local repository**
2. 选择路径：`D:\软件工程\transparent-umbrella`
3. 如果提示「这不是一个 Git 仓库」，点 **create a repository** 时把路径指向同一目录即可（不要勾选初始化 README）
4. 左侧会显示待推送的 commit：`chore(repo): bootstrap project skeleton and collaboration setup`
5. 右上角点 **Push origin**

推送完成后到 https://github.com/encoY3332333/transparent-umbrella 确认文件已出现。

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
| `【组长】` | 50 | 组长真实姓名 |
| `【组员1】` | 35 | 组员1 真实姓名 |
| `【组员2】` | 32 | 组员2 真实姓名 |
| `【组员1的GitHub名】` / `【组员2的GitHub名】` | 各 2 | GitHub 用户名 |
| `【GitHub用户名】` | 4 | 你自己的 GitHub 用户名（在 `docs/contributions/_template.md` 中） |
| `【姓名】` `【学号】` | 各 2 | 同上 |

**注意**：`docs/contributions/_template.md` 里的 `【方案内容】`「【具体事件】」等是**模板引导语**，不是占位符，不要替换。

批量替换建议用 VS Code 的「在文件中替换」（Ctrl+Shift+H），逐个确认后再提交——**不要**用脚本一把梭，容易误伤。

---

# 故障排查：`schannel: server closed abruptly`

**症状**：`git push` / `git ls-remote` / VS Code 的同步按钮报

```
fatal: unable to access 'https://github.com/...': schannel: server closed abruptly (missing close_notify)
```

**原因**：Windows 自带的 `schannel` SSL 后端与 GitHub 的 TLS 握手在该网络环境下会被中断。网络本身是通的（`ping`/`curl` 正常），只是 git 走了 schannel 这条路径。

**解决**：切换为 OpenSSL 后端。

```bash
git config --global http.sslBackend openssl
```

**验证**：

```bash
cd D:\软件工程\transparent-umbrella
git ls-remote origin
# 应输出 f33eca78...  refs/heads/main
```

本机已执行过这条命令。**组员在新机器上 clone 时如果遇到同样报错，也执行这一条。**

> 这个改动是全局的（`~/.gitconfig`），对本机所有仓库生效。如果之后某个企业内网仓库需要 schannel（例如依赖 Windows 证书存储做客户端证书认证），把 `openssl` 改回 `schannel` 即可，或对该仓库单独设置 `git config http.sslBackend schannel`。

---

# 本地提交现状

推送前，本地 `main` 领先 `origin/main` 三个提交：

```
78502d7  docs: fix relative link in push guide
83615d0  docs: add push guide for first-time repository setup
4ce9be0  chore(repo): bootstrap project skeleton and collaboration setup
f33eca7  Initial commit          ← origin/main 当前指向这里
```

推送后仓库将包含 66 个文件。若网络不可用，可用 `D:\软件工程\transparent-umbrella-骨架.bundle`（含完整提交历史）拷到其他机器：`git clone <bundle> repo && cd repo && git remote set-url origin <远程地址> && git push origin main`。
