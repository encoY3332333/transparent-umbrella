> ## 这份文件是什么
>
> 给组员和新加入同学的**本地环境与推送操作手册**，不含任何个人令牌、本机路径或一次性命令。
> 仓库现状与推进计划看 `README.md`，评审流程看 `docs/guides/评审与互评操作指南.md`。
>
> **安全红线**：任何情况下不要把 Personal Access Token 拼进 `git remote` 的 URL，
> 也不要把它贴进 Issue、PR、聊天记录或文档。令牌泄露等于仓库被接管，撤销也未必来得及。

# 首次配置与推送

## 一、验证 GitHub 身份

```bash
git config user.name      # 应输出你自己的 GitHub 用户名
git config user.email     # 应输出你自己的 GitHub 关联邮箱
```

本项目三人必须各自配置，否则提交会记到别人名下（已发生过：B 的提交一度以 `realpcy` 身份出现）：

```bash
git config --global user.name  "<你的 GitHub 用户名>"
git config --global user.email "<你的 GitHub 邮箱>"
```

校验方法：推一个提交后到仓库 Commits 页面看，作者头像和名字要能点进你自己的主页。

## 二、拉取仓库

```bash
git clone https://github.com/encoY3332333/transparent-umbrella.git
cd transparent-umbrella
```

## 三、认证方式（二选一，都不要写进 URL）

**方式 1：SSH（推荐，一次配置长期有效）**

```bash
ssh-keygen -t ed25519 -C "<你的邮箱>"     # 一路回车
cat ~/.ssh/id_ed25519.pub                 # 复制内容到 GitHub → Settings → SSH and GPG keys
ssh -T git@github.com                     # 看到 "successfully authenticated" 即可
git remote set-url origin git@github.com:encoY3332333/transparent-umbrella.git
```

**方式 2：HTTPS + 凭据管理器**

```bash
# Windows
git config --global credential.helper manager
# macOS
git config --global credential.helper osxkeychain
```

首次 `git push` 时浏览器会弹登录窗口，登录后由系统保管，后续不再询问。

## 四、分支与提交

```bash
git switch -c feat/uc-01-preference-form    # 分支名：<type>/<issue号>-<短描述>
git add -A
git commit -m "feat(pref): 实现偏好建档表单与校验"
git push -u origin feat/uc-01-preference-form
```

提交信息格式见 `CONTRIBUTING.md` 第 5 章，CI 的 `lint-repo` 会校验，不合规直接红。

## 五、开 PR 与合并

1. 推送后 GitHub 页面顶部出现 **Compare & pull request**，点它。
2. 标题用「类型(scope): 做了什么」，正文按模板填**改了什么 / 为什么改 / 怎么验证**。
3. 右侧指定 **Reviewer**（不能是自己）和 **Assignee**（自己），关联 Issue（`Closes #5`）。
4. 至少 1 个 Approve、CI 全绿后才能点 Merge。
5. 合并方式选 **Squash and merge**，避免 `main` 上堆满合并提交。

## 六、常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| `server closed abruptly` / TLS 报错 | Windows 的 schannel SSL 后端与 GitHub 不兼容 | `git config --global http.sslBackend openssl` |
| `Permission denied (publickey)` | SSH key 未加到 GitHub，或 remote 仍是 HTTPS | 重做第三节方式 1 |
| 推送后作者不是自己 | 全局 `user.name` / `user.email` 错 | 修正后对新提交生效，旧提交需 rebase 才改 |
| `Updates were rejected` | 远端有你本地没有的提交 | `git pull --rebase` 后重推 |
| 中文文件名显示为转义 | `core.quotepath` 默认转义 | `git config --global core.quotepath false` |

## 七、现在只剩两件需要 Admin 权限的事

1. 邀请组员为 Collaborator（B、C 已完成，可跳过）
2. 开启 `main` 分支保护——见 `.github/BRANCH_PROTECTION.md` 第 2 节，必须由仓库所有者 `encoY3332333` 操作
