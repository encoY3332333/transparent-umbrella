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

> **状态：14 个 Issue 已于 2026-11-10 全部创建完毕**，实际编号与下表行序完全一致（`#1`–`#14`），
> 每个都带 Label 与 Milestone，正文与本目录文件内容一致。
> 唯一的待办是 **Assignee 尚未指派**——三人真实 GitHub 账号确认后，在 Issue 右侧设置即可（见文末）。

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

## 线上编号对照（已创建，可直接点）

| Issue | 标题 | 链接 |
|---|---|---|
| #1 | [Chore] 初始化仓库与工程基建 | https://github.com/encoY3332333/transparent-umbrella/issues/1 |
| #2 | [Feature] 游客登录与偏好建档 | https://github.com/encoY3332333/transparent-umbrella/issues/2 |
| #3 | [Feature] 出行条件录入与校验 | https://github.com/encoY3332333/transparent-umbrella/issues/3 |
| #4 | [Feature] 行程生成编排入口 | https://github.com/encoY3332333/transparent-umbrella/issues/4 |
| #5 | [Feature] 候选 POI 筛选与拥挤度计算 | https://github.com/encoY3332333/transparent-umbrella/issues/5 |
| #6 | [Feature] 排程引擎（综合评分 + 贪心装箱） | https://github.com/encoY3332333/transparent-umbrella/issues/6 |
| #7 | [Feature] 可行性校验与预算降本迭代 | https://github.com/encoY3332333/transparent-umbrella/issues/7 |
| #8 | [Feature] 行程结果页（时间轴 + 地图 + 预算） | https://github.com/encoY3332333/transparent-umbrella/issues/8 |
| #9 | [Feature] 行程局部调整 | https://github.com/encoY3332333/transparent-umbrella/issues/9 |
| #10 | [Feature] 行程收藏与分享 | https://github.com/encoY3332333/transparent-umbrella/issues/10 |
| #11 | [Feature] 规划反馈 | https://github.com/encoY3332333/transparent-umbrella/issues/11 |
| #12 | [Feature] POI 与活动数据维护 | https://github.com/encoY3332333/transparent-umbrella/issues/12 |
| #13 | [Feature] 推荐策略参数配置 | https://github.com/encoY3332333/transparent-umbrella/issues/13 |
| #14 | [Chore] CI 门禁、覆盖率与性能基线 | https://github.com/encoY3332333/transparent-umbrella/issues/14 |

## 仍需人工完成的两件事

1. **指派 Assignee**：Issue 创建时三人真实 GitHub 账号未定，故全部留空。
   组长确认账号后，按上表「Assignee」列（`【组长】`/`【组员1】`/`【组员2】`）逐条指派。
   注意：被指派者必须是仓库 Collaborator，否则下拉列表里搜不到。
2. **依赖关系回填**：Issue 正文里的「阻塞 #x / 依赖 #y」是按预排编号写的，编号已与上表一致，
   因此**无需修改**；若后续插入新 Issue 导致编号变化，再统一订正。
