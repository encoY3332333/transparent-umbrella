# Issue 清单与创建指引

本目录存放 14 个 Issue 的**完整正文**，与 `附件5_需求清单与Issue拆分表.xlsx` 的「2-Issue拆分表」一一对应。

## 为什么放在这里

课程考核方案 A1 要求「需求被拆分为可独立交付的任务单元，每个任务对应一个 GitHub Issue」，且「不复用口头协商，需求变更有记录」。
把 Issue 正文以文件形式入库，可以：

- 让 Issue 内容随代码一起被 Review、被追溯
- 避免「答辩前集中补建 Issue」的嫌疑（文件提交时间早于 Issue 创建时间，是可查的证据）
- 便于用 GitHub CLI 批量创建

## 创建步骤

见 [`.github/BRANCH_PROTECTION.md`](../../.github/BRANCH_PROTECTION.md) 第 5 节。

## 清单

| 文件 | 标题 | 用例 | Milestone | Assignee | 预估 | Labels |
|---|---|---|---|---|---|---|
| `01-project-init.md` | [Chore] 初始化仓库与工程基建 | — | M0-工程启动 | 【组长】 | 4h | `ci` `backend` `frontend` `P0` |
| `02-tourist-login.md` | [Feature] 游客登录与偏好建档 | UC-01 | v0.1.0 Alpha | 【组员2】 | 6h | `feature` `backend` `P0` |
| `03-travel-condition.md` | [Feature] 出行条件录入与校验 | UC-02 | v0.1.0 Alpha | 【组员1】 | 8h | `feature` `frontend` `P0` |
| `04-generate-itinerary.md` | [Feature] 行程生成编排入口 | UC-03 | v0.1.0 Alpha | 【组长】 | 4h | `feature` `backend` `P0` |
| `05-poi-crowd-index.md` | [Feature] 候选 POI 筛选与拥挤度计算 | UC-03 | v0.1.0 Alpha | 【组长】 | 8h | `feature` `backend` `P0` |
| `06-strategy-engine.md` | [Feature] 排程引擎（综合评分 + 贪心装箱） | UC-03 | v0.1.0 Alpha | 【组长】 | 10h | `feature` `backend` `P0` |
| `07-budget-iteration.md` | [Feature] 可行性校验与预算降本迭代 | UC-03 | v0.1.0 Alpha | 【组长】 | 6h | `feature` `backend` `P0` |
| `08-itinerary-view.md` | [Feature] 行程结果页（时间轴 + 地图 + 预算） | UC-04 | v0.1.0 Alpha | 【组员2】 | 8h | `feature` `frontend` `P0` |
| `09-adjust-itinerary.md` | [Feature] 行程局部调整 | UC-05 | v0.2.0 Beta | 【组员1】 | 10h | `feature` `frontend` `P1` |
| `10-save-share.md` | [Feature] 行程收藏与分享 | UC-06 | v0.2.0 Beta | 【组员1】 | 6h | `feature` `backend` `P1` |
| `11-feedback.md` | [Feature] 规划反馈 | UC-07 | v0.2.0 Beta | 【组员2】 | 4h | `feature` `backend` `P1` |
| `12-poi-admin.md` | [Feature] POI 与活动数据维护 | UC-08 | v0.3.0 Pre | 【组员1】 | 8h | `feature` `frontend` `P2` |
| `13-strategy-config.md` | [Feature] 推荐策略参数配置 | UC-09 | v0.3.0 Pre | 【组长】 | 6h | `feature` `backend` `P2` |
| `14-ci-coverage.md` | [Chore] CI 门禁、覆盖率与性能基线 | NFR | M0-工程启动 | 【组长】 | 4h | `ci` `P0` |

**统计**：14 个 Issue，总预估 92 小时，人均 4.67 个（考核下限 4 个）、人均约 30.7 小时。

## 依赖关系

```
#1 工程基建 ──┬──> #2 登录       ──┐
             ├──> #3 条件录入    ──┤
             ├──> #5 候选POI     ──┤
             ├──> #6 排程引擎    ──┼──> #4 生成编排 ──> #8 结果页 ──> #9 调整
             ├──> #7 预算迭代    ──┘                              ├──> #10 分享
             └──> #14 CI                                             └──> #11 反馈
#12 POI 后台 ──> 被 #5 使用
#13 策略配置 ──> 被 #6 使用
```

依赖关系必须在 Issue 的「关联 / Related」小节里双向标注：被依赖方写「阻塞 #x」，依赖方写「依赖 #y」。
