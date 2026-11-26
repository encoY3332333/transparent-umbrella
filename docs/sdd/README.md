# 软件设计规格说明书（SDD）—— 校园智办 / SmartTrip

> 版本 v0.1（初稿骨架）｜2026-11-26｜第六组
> 编写方式：**从代码与既有设计资产反向组装**，不重写需求。需求侧引用 SRS，本册只描述"系统如何实现"。

## 章节与负责人

| 章节 | 文件 | 负责人 | 素材来源 | 状态 |
|---|---|---|---|---|
| 1 引言 | [01-introduction.md](./01-introduction.md) | A | SRS 第 1 章、docs/architecture.md | ✅ 初稿 |
| 2 总体设计 | [02-overall-design.md](./02-overall-design.md) | A | docs/architecture.md、ADR-007 | ✅ 初稿 |
| 3 模块设计 | [03-module-design.md](./03-module-design.md) | C | backend/app/、docs/diagrams/ | ⬜ 骨架 |
| 4 接口设计 | [04-interface-design.md](./04-interface-design.md) | C | docs/api.md、backend/app/api/ | ⬜ 骨架 |
| 5 数据设计 | [05-data-design.md](./05-data-design.md) | B | backend/app/models/、migrations/0001-0004 | ⬜ 骨架 |
| 6 关键设计决策 | [06-design-decisions.md](./06-design-decisions.md) | A | docs/adr/ADR-001~007 | ✅ 初稿 |
| 7 横切设计 | [07-cross-cutting.md](./07-cross-cutting.md) | B | backend/app/core/、adapters/ | ⬜ 骨架 |
| 8 部署与运维 | [08-deployment.md](./08-deployment.md) | B | docker-compose.yml、.github/workflows/ | ⬜ 骨架 |
| 附录 A 需求-设计追踪矩阵 | [appendix-a-traceability.md](./appendix-a-traceability.md) | A | SRS 用例表 + 本册各章 | ✅ 初稿 |

## 三条统一规则（写之前先看，避免返工）

1. **图必须指回代码**。任何类图、时序图、状态机、ER 图，都必须标注对应的源文件路径（如 `backend/app/engine/packer.py`）。老师第 1 次批阅第 4 条扣分就是"模型图与迭代表不同步"，因此本册不接受"只有图没有出处"。
2. **标注实现状态**。每个模块、每条接口、每张表都要写清 `已实现 / 部分实现 / 仅设计`。当前真实状态见附录 A 与第 5 章表清单，不要把"设计里有的"写成"系统里有的"。
3. **性能指标必须带测量前提**。写"P95 ≤ 10s"必须同时写数据量（POI 数量、天数上限）、缓存是否命中、外部超时与重试次数。没有前提的数字一律不算验收指标。

## 术语与约定

- `A / B / C` 指组内分工代号；真实姓名与贡献比例见报告封面与贡献说明书（A 杨婧妍 0.35、B 刘婕 0.34、C 铁昳萱 0.31）。
- 用例编号 `UC-01 ~ UC-09` 与 BR 编号沿用 SRS，不另起一套。
- 代码路径一律相对仓库根目录。

## 修订记录

| 日期 | 版本 | 修订人 | 说明 |
|---|---|---|---|
| 2026-11-26 | v0.1 | A | 建立骨架：章节分工、统一规则、第 1/2/6 章初稿与附录 A 追踪矩阵；3/4/5/7/8 章留骨架待 B、C 填写 |
