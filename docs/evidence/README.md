# 过程证据（evidence）

本目录存放**无法从 git 历史直接读出来的证据**——那些发生在 GitHub 设置界面、CI 面板、教学平台上的动作。
课程评分时「说做了」和「能证明做了」是两件事，这里就是补后者。

## 放什么

| 文件命名 | 内容 | 由谁在什么时候提交 |
|---|---|---|
| `branch-protection-<YYYYMMDD>.png` | Settings → Rules 中 main 分支保护规则页面截图 | A，开启后立刻 |
| `ci-<pr号>-<YYYYMMDD>.png` | 某次 CI 全绿的 job 列表 | 提交 PR 的人，合并前 |
| `review-<pr号>-<YYYYMMDD>.png` | PR 页面上第三方 Approve + 行内评论的截图 | 评审人 |
| `structure-<YYYYMMDD>.png` | Issues 列表按 Assignee 筛选的截图 | A，每次进展报告前 |
| `external-test-<YYYYMMDD>.md` | 组外同学按 README 启动的实测记录（系统、命令、报错、结果） | C |

## 规则

1. 截图必须能看清**日期、页面标题、关键数值**，不要裁剪掉浏览器地址栏。
2. 一个文件只证明一件事，文件名写清楚证明的是哪件事。
3. 不要放大段纯文字复述。文字结论写进 `docs/assessment-checklist.md` 或报告正文，这里只放原始证据。
4. 涉及个人账号信息的截图（邮箱、通知中心）先打码，只保留 GitHub 用户名。
