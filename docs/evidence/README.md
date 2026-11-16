# 分支保护证据（考核 A4 / B2）

## 证据清单

| 文件 | 内容 | 来源 |
|---|---|---|
| `branch-protection-20261112.png` | ruleset `protect-main` 页面截图（上：名称/Active/Bypass 空/target=main；下：4 条勾选规则） | 浏览器截图 |
| `protect-main-ruleset.json` | 规则完整配置的 API 原始返回，含审批数、作废批准、线程解决、required checks 名单 | `gh api repos/.../rulesets/27102459` |

## 配置要点

- **pull_request**：`required_approving_review_count=1`（至少 1 人 Approve）；`dismiss_stale_reviews_on_push=true`；`required_review_thread_resolution=true`
- **required_status_checks**：`Backend (Python 3.11)`、`CI Summary`
- **non_fast_forward**：禁止 force push；**deletion**：禁止删除 main
- enforcement=active；bypass list 空；target=main

复核：`gh api repos/encoY3332333/transparent-umbrella/rulesets/27102459`
