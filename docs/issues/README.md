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
> **Assignee 已于 2026-11-11 全部指派**：A（`encoY3332333`）5 个、B（`richkoijx`）5 个、C（`star-X09`）4 个，
> 与 `附件5_需求清单与Issue拆分表.xlsx` 的表 2 一致。当前待办只剩 **#2–#14 的开发与关闭**——Issue 建好不等于任务完成，
> 关闭状态才计入个人贡献（B1）。
>
> **关于 `frontend` / `backend` 两个 Label**：Label 名沿用技术栈切换前的命名（已上线，改名会丢失历史），
> 语义已调整为——`backend` = Python 应用逻辑（`services/` `engine/` `adapters/` `models/` `schemas/`），
> `frontend` = Jinja2 模板与 HTMX 交互（`templates/` `static/`）。详见 [ADR-007](../adr/ADR-007-switch-to-python-stack.md)。

| 文件 | 标题 | 用例 | Milestone | Assignee | 预估 | Labels |
|---|---|---|---|---|---|---|
| `01-project-init.md` | [Chore] 初始化仓库与工程基建 | — | M0-工程启动 | @richkoijx | 4h | `ci` `backend` `frontend` `P0` |
| `02-tourist-login.md` | [Feature] 游客登录与偏好建档 | UC-01 | v0.1.0 Alpha | @encoY3332333 | 6h | `feature` `backend` `P0` |
| `03-travel-condition.md` | [Feature] 出行条件录入与校验 | UC-02 | v0.1.0 Alpha | @star-X09 | 8h | `feature` `frontend` `P0` |
| `04-generate-itinerary.md` | [Feature] 行程生成编排入口 | UC-03 | v0.1.0 Alpha | @richkoijx | 4h | `feature` `backend` `P0` |
| `05-poi-crowd-index.md` | [Feature] 候选 POI 筛选与拥挤度计算 | UC-03 | v0.1.0 Alpha | @star-X09 | 8h | `feature` `backend` `P0` |
| `06-strategy-engine.md` | [Feature] 排程引擎（综合评分 + 贪心装箱） | UC-03 | v0.1.0 Alpha | @richkoijx | 10h | `feature` `backend` `P0` |
| `07-budget-iteration.md` | [Feature] 可行性校验与预算降本迭代 | UC-03 | v0.1.0 Alpha | @encoY3332333 | 6h | `feature` `backend` `P0` |
| `08-itinerary-view.md` | [Feature] 行程结果页（时间轴 + 地图 + 预算） | UC-04 | v0.1.0 Alpha | @encoY3332333 | 8h | `feature` `frontend` `P0` |
| `09-adjust-itinerary.md` | [Feature] 行程局部调整 | UC-05 | v0.2.0 Beta | @star-X09 | 10h | `feature` `frontend` `P1` |
| `10-save-share.md` | [Feature] 行程收藏与分享 | UC-06 | v0.2.0 Beta | @star-X09 | 6h | `feature` `backend` `P1` |
| `11-feedback.md` | [Feature] 规划反馈 | UC-07 | v0.2.0 Beta | @encoY3332333 | 4h | `feature` `backend` `P1` |
| `12-poi-admin.md` | [Feature] POI 与活动数据维护 | UC-08 | v0.3.0 Pre | @encoY3332333 | 8h | `feature` `frontend` `P2` |
| `13-strategy-config.md` | [Feature] 推荐策略参数配置 | UC-09 | v0.3.0 Pre | @richkoijx | 6h | `feature` `backend` `P2` |
| `14-ci-coverage.md` | [Chore] CI 门禁、覆盖率与性能基线 | NFR | M0-工程启动 | @richkoijx | 4h | `ci` `P0` |

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

## Assignee 指派状态（2026-11-11 已完成）

三人 GitHub 账号已确认，14 个 Issue 全部指派完毕，无遗留无主 Issue：

| 成员 | GitHub | Issue | 数量 | 总预估 |
|---|---|---|---|---|
| 组长 | @richkoijx | #1 #4 #6 #13 #14 | 5 | 28h |
| 组员1 | @star-X09 | #3 #5 #9 #10 | 4 | 32h |
| 组员2 | @encoY3332333 | #2 #7 #8 #11 #12 | 5 | 32h |

分配原则：数量按 5/4/5（均不低于考核下限 4 个），工时按 28/32/32 持平；
每个成员的 Issue 都跨 Milestone（含一个早期任务 + 一个后期任务），
避免出现「某人只做第一阶段、后期无事可做」的空档。

**依赖关系回填**：Issue 正文里的「阻塞 #x / 依赖 #y」是按预排编号写的，
编号已与上表一致，因此无需修改；若后续插入新 Issue 导致编号变化，再统一订正。
