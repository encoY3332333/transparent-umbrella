# UML 图集（PlantUML）

> **所有图必须以源码形式入库**，不接受只存在于答辩 PPT 截图里的图。
> 课程考核 A2「设计与架构」与 A7「文档与治理」都会检查「图是否与文字一致、是否可追溯」。

## 为什么用 PlantUML 而不是 draw.io / ProcessOn

| | PlantUML | 图形工具 |
|---|---|---|
| diff 可读 | 是，改了什么一眼看出 | 否，二进制/XML |
| 与文档同步 | 改代码同时改图，PR 里一起评审 | 容易忘记更新，图与文字脱节 |
| 渲染 | VS Code 插件 / 在线服务 / CI 均可 | 依赖本地工具 |
| 学习成本 | 半小时 | 更低 |

代价是排版不如手工拖拽好看。对本课程来说，**一致性比美观重要**。

## 如何渲染

**方式一：VS Code 插件**
安装 `PlantUML`（jebbs.plantuml），打开 `.puml` 文件按 `Alt+D` 预览。

**方式二：在线**
访问 https://www.plantuml.com/plantuml/uml/ ，粘贴源码。

**方式三：命令行**（需 Java + plantuml.jar）

```bash
java -jar plantuml.jar -tpng docs/diagrams/*.puml -o out/
```

**渲染产物不入库**（已加入 `.gitignore`），只入库 `.puml` 源码。需要插图到 docx 时临时渲染。

## 清单

| 文件 | 类型 | 对应 SRS 章节 | 状态 |
|---|---|---|---|
| `usecase.puml` | 用例图 | 3.2 | 已创建 |
| `class-analysis.puml` | 分析类图（边界/控制/实体） | 3.4 | 已创建 |
| `seq-uc01-login.puml` | 顺序图 | 3.3.1 UC-01 | 已创建 |
| `seq-uc02-condition.puml` | 顺序图 | 3.3.2 UC-02 | 已创建 |
| `seq-uc03-generate.puml` | 顺序图 | 3.3.3 UC-03 | 已创建 |
| `seq-uc04-view.puml` | 顺序图 | 3.3.4 UC-04 | 已创建 |
| `seq-uc05-adjust.puml` | 顺序图 | 3.3.5 UC-05 | 已创建 |
| `seq-uc06-share.puml` | 顺序图 | 3.3.6 UC-06 | 已创建 |
| `seq-uc07-feedback.puml` | 顺序图 | 3.3.7 UC-07 | 已创建 |
| `seq-uc08-poi-admin.puml` | 顺序图 | 3.3.8 UC-08 | 已创建 |
| `seq-uc09-strategy.puml` | 顺序图 | 3.3.9 UC-09 | 已创建 |
| `state-itinerary.puml` | 状态图：行程六态 | 3.5 | 已创建 |
| `state-activity.puml` | 状态图：活动锁定态 | 3.5 | 已创建 |
| `state-adjust.puml` | 状态图：调整事务 | 3.5、ADR-005 | 已创建 |

## 维护约定

1. **改行为先改图，再改代码**——图是契约的一部分
2. 顺序图里每个消息必须能对应到 `docs/api.md` 的一个接口或 `docs/architecture.md` 的一个方法
3. 类图中的类名必须与 `backend/src/main/java/com/smarttrip/` 下的真实类名一致；改名时图与代码在**同一个 PR** 里改
4. 图中的参与者用中文全称，类用英文类名（与代码一致），不用拼音缩写
