# [Feature] 候选 POI 筛选与拥挤度计算

## 背景 / Background

排程引擎不可能对全城几千个 POI 做组合优化，必须先筛出一个「可算规模」的候选集（20–300 个）。同时，拥挤度是本项目区别于普通攻略工具的核心变量之一（问卷 Q6：75% 的受访者被「景点人太多」坑过）。

对应 SRS：3.3.3 · 用例 UC-03 基本流程第 1–2 步

## 需求描述 / Description

按目的地 + 偏好标签 + 必去/必避清单筛选 POI，并计算每个 POI 在行程期各日的拥挤度指数 `CrowdIndex ∈ [0,100]`。

## 任务清单 / Tasks

- [ ] 后端：`CandidateSelector.select()` 实现，筛选条件：同城、状态为 PUBLISHED（排除 DRAFT/INACTIVE）、命中偏好标签或属必去项、不在必避清单
- [ ] 后端：候选集规模收敛——过少时逐级放宽（先放宽次要标签，再放宽类别），过少到 20 以下仍不足则抛 `INSUFFICIENT_POI_DATA`
- [ ] 后端：`TrafficServerAdapter.getHistoricalVolume(poiId, dateRange)`，批量接口（禁止循环单查，避免 N+1）
- [ ] 后端：`CrowdIndexCalculator` 实现公式 `min(100, round(100 * HistVolume / Capacity))`
- [ ] 后端：人流量服务不可用时降级——`CrowdIndex` 标记为 `UNKNOWN`，排程时不再施加拥挤度惩罚
- [ ] 后端：缓存历史人流量（按 poiId + 日期，TTL 24h），避免重复计费
- [ ] 测试：`CrowdIndexCalculatorTest` 覆盖 0 / 50 / 80 / 100 / 超载（>100 截断）/ 承载量为 0 六个场景
- [ ] 测试：`CandidateSelectorTest` 覆盖必去命中、必避排除、候选不足放宽、数据不足报错

## 验收标准 / Acceptance Criteria

- [ ] 候选集规模落在 [20, 300]；不在区间时按放宽策略处理并记录日志
- [ ] 状态为 DRAFT 或 INACTIVE 的 POI 绝不进入候选集
- [ ] 必去清单中的 POI 100% 出现在候选集中（只要其状态为 PUBLISHED）
- [ ] 必避清单中的 POI 0% 出现在候选集中
- [ ] `CrowdIndex` 计算与公式一致，且值域 ∈ [0, 100] 的整数
- [ ] 承载量为 0 的 POI 不参与计算（数据异常），并记录 WARN 日志
- [ ] 对人流量服务的调用改为批量，200 个 POI 的查询不超过 5 次网络请求
- [ ] 人流量服务不可用时，接口仍返回候选集，`CrowdIndex` 为 `UNKNOWN`

## 关联 / Related

- 依赖 #1
- 阻塞 #4
- 阻塞 #6

## 元信息

- 预估工作量：8 小时
- Labels：`feature` `backend` `P0`
- Milestone：`v0.1.0 Alpha`
- Assignee：【组长】
- 分支：`feature/5-poi-crowd-index`
- 涉及业务规则：BR-09、BR-10

## 参考资料

SRS 3.3.3 节的公式块：

```
CrowdIndex(p, d) = min(100, round(100 * HistVolume(p, d) / Capacity(p)))
```

问卷 Q6 数据：景点人太多 24/32（75.0%），是四类规划失效场景中占比最高的一项。
