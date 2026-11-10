> ## 状态：✅ 已于 2026-11-10 完成推送
>
> 4 个 commit 已推到 `main`（`f33eca7..9ee6fdf`），首次 CI 跑通并成功；
> Labels、5 个 Milestone、14 个 Issue、`v0.0.1` Release 均已通过 GitHub API 建好。
>
> **本文件现在只作为参考手册**：给新加入的组员拉代码时用，或在遇到网络问题时查故障排查章节。
> 不需要再照着下面的推送步骤执行一遍。
>
> 仍需人工处理的只剩两项，都要求 **Admin 权限**（当前账号只有 `push` + `triage`）：
> 邀请组员 Collaborator、开启 main 分支保护。见 `.github/BRANCH_PROTECTION.md` 第 0 节。
>
> **本机已处理的前置修复**：git 默认的 `schannel` SSL 后端连 GitHub 会报 `server closed abruptly`，已全局改为 `openssl`（`git config --global http.sslBackend openssl`）。

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

# 推送之后必须做的事（更新于 2026-11-10）

| # | 事项 | 状态 | 说明 |
|---|---|---|---|
| 1 | 推代码，等 CI 跑一次 | ✅ 已完成 | `9ee6fdf` 触发 CI 并成功，status checks 现在可选 |
| 2 | 邀请 2 名 Collaborator | ⬜ **待组长** | 需 Admin。组员1 已加入（`richkoijx`），组员2 待定 |
| 3 | 创建 10 个 Labels | ✅ 已完成 | 另有 7 个 GitHub 默认标签保留 |
| 4 | 创建 5 个 Milestone | ✅ 已完成 | 截止日期按「第 1 周 = 2026-10-26」推算，可改 |
| 5 | 创建 14 个 Issue | ✅ 已完成 | 编号 `#1`–`#14`，含 Label + Milestone；Assignee 待指派 |
| 6 | 开启分支保护 9 项 | ⬜ **待组长** | 需 Admin。对照表见 `BRANCH_PROTECTION.md` 第 2 节 |
| 7 | 开 Discussions（可选） | ⬜ 可选 | 无 API 开关，只能网页勾选 |
| 8 | 建 v0.0.1 Release | ✅ 已完成 | pre-release，标签 `v0.0.1` |

完整操作步骤见 [`.github/BRANCH_PROTECTION.md`](../.github/BRANCH_PROTECTION.md)。

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

# 故障排查：`CONNECT tunnel failed, response 502`

**症状**：`git push` 报

```
fatal: unable to access 'https://github.com/.../': CONNECT tunnel failed, response 502
```

**原因**：环境变量里存在 `HTTP_PROXY` / `HTTPS_PROXY`（指向本机某个代理端口），git 自动走了它，
而该代理不放行 GitHub 的 CONNECT 隧道。注意这跟证书无关，换 SSL 后端也修不好。

**解决**：推送时临时绕过代理。

```bash
git -c http.proxy= -c https.proxy= push origin main
```

如果长期需要绕过，可用 `git config --global --unset http.proxy` 清掉全局配置；
但更常见的是反过来的情况——公司网络**必须**走代理，那就改成
`git config --global http.proxy http://127.0.0.1:<端口>`。

**诊断顺序**（避免误判成「被墙」）：

```bash
# 1. TCP 通不通
#    python -c "import socket;socket.create_connection(('github.com',443),5);print('ok')"
# 2. git 自己怎么连的
git config --get http.proxy ; git config --get https.proxy
# 3. 环境变量里有没有代理
#    Windows: set | findstr /i proxy
```

本次的真实原因就是第 3 条：环境里注入了代理，而代理返回 502。绕过之后一次成功。

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

# 推送结果（已验证）

```
9ee6fdf  docs: rewrite push guide with the real root cause and VS Code flow   ← origin/main
78502d7  docs: fix relative link in push guide
83615d0  docs: add push guide for first-time repository setup
4ce9be0  chore(repo): bootstrap project skeleton and collaboration setup
f33eca7  Initial commit
```

推送命令与输出：

```
$ git -c http.proxy= -c https.proxy= push origin main
To https://github.com/encoY3332333/transparent-umbrella.git
   f33eca7..9ee6fdf  main -> main
```

远程 `refs/heads/main` 已指向 `9ee6fdf`，Actions 面板首次 CI 为绿色。
`D:\软件工程\transparent-umbrella-骨架.bundle` 仍然保留，可作为离线备份或在新机器上恢复历史。
