# [Feature] 行程结果页（时间轴 + 地图 + 预算）

## 背景 / Background

行程生成了但看不清，等于没生成。用户在行程页要做三件事：看「每天去哪儿」、看「路怎么走」、看「钱够不够」。问卷 Q8 显示 81.3% 的用户能接受 10 秒内出结果，但前提是这 10 秒里要有进度反馈，而不是白屏。

对应 SRS：3.3.4 · 用例 UC-04
渲染方式：Jinja2 服务端渲染 + HTMX 局部刷新（ADR-007）

## 需求描述 / Description

双视图（时间轴 / 地图）展示行程，地图显示 POI 标记与通勤路线，侧栏展示预算环形图与拥挤度标签，标注高风险 POI 与高降水时段。

## 任务清单 / Tasks

- [ ] 页面：`templates/itinerary/detail.html` 双视图容器，用 Alpine.js 的 `x-show` 在两个视图间切换（数据已在首次渲染时全量下发，切换不发请求，**滚动位置天然保留**）
- [ ] 局部片段：`templates/itinerary/_timeline.html` 按天分组的时间轴，活动卡片显示时间、名称、通勤时长、费用
- [ ] 局部片段：`templates/itinerary/_map.html` 地图视图，POI 标记 + 折线连路 + 通勤方式/时长标注（Leaflet，`app/static/vendor/leaflet/` 本地化）
- [ ] 局部片段：`templates/itinerary/_budget.html` 四类占比环形图 + 结余条（**纯 CSS `conic-gradient`**，不引 ECharts——省 500KB，且服务端渲染时更易对齐数值）
- [ ] 局部片段：`templates/itinerary/_activity_drawer.html`，用 `hx-get="/itineraries/{id}/activities/{aid}"` + `hx-target` 打开详情抽屉
- [ ] 标签渲染：拥挤度 ≥ 80 的 POI 打「拥挤」标签；降水概率 ≥ 60% 的时段打「雨」标签（判断逻辑放 Jinja2 宏 `templates/macros/badges.html`，避免模板里散落 `{% if %}`）
- [ ] 降级：地图服务不可用时后端置 `map_available=false`，模板渲染纯文本列表并显示提示
- [ ] 后端：`GET /api/itineraries/{id}` 返回视图模型（已聚合坐标、天气、预算、推荐理由）
- [ ] 后端：`GET /itineraries/{id}` 返回 HTML 页面；`GET /itineraries/{id}/activities/{aid}` 返回抽屉片段
- [ ] 测试：`tests/api/test_itinerary_page.py` 覆盖正常渲染、空数据、跨天活动、地图降级 4 个场景（断言 HTML 中关键文本与 `data-*` 属性）

## 验收标准 / Acceptance Criteria

- [ ] AC-1 行程页在 3 秒内完成首屏渲染（3 天以内行程，4G 网络）—— 服务端渲染，无 JS 打包等待
- [ ] AC-2 预算环形图四类占比之和为 100%（允许 1% 误差）
- [ ] AC-3 点击任一活动块，右侧抽屉显示该活动详情（时间、地点、费用、来源链接）
- [ ] 时间轴与地图切换时，滚动位置不丢失
- [ ] 拥挤度 ≥ 80 的 POI 带有可见的「拥挤」标签
- [ ] 地图不可用时降级为列表视图，且提示文案友好（不出现英文错误码）
- [ ] 移动端（375×667）单列布局可用，无横向滚动条
- [ ] **禁用 JavaScript 后**，时间轴与预算条仍能正常阅读（服务端渲染的天然优势，也是无障碍底线）

## 关联 / Related

- 依赖 #4
- 阻塞 #9
- 阻塞 #10

## 元信息

- 预估工作量：8 小时
- Labels：`feature` `frontend` `P0`
- Milestone：`v0.1.0 Alpha`
- Assignee：@encoY3332333
- 分支：`feature/8-itinerary-view`
- 涉及业务规则：BR-11、BR-12

## 界面参考

SRS 第 5 章 S5 界面说明：上部方案切换标签（A/B/C），左侧时间轴，右侧地图，底部固定预算条，右上角「调整/保存/分享」三个入口。

## 技术备注

- **双视图用 `x-show` 而不是 `hx-get`**。两个视图的数据同源，切一次发一次请求既慢又会让滚动位置归零。`x-show` 只是切 `display`，两个 DOM 都在页面里，浏览器会缓存滚动位置
- **预算环形图别用图表库**。四个扇区、固定顺序，`conic-gradient` 一行 CSS 就能画，还能在服务端把百分比直接算好写进 `style` 属性。引 ECharts 要多加载 500KB，还要处理 `resize`
- **活动详情的抽屉用 HTMX 是合理的**：它是「点一个才知道一个」的按需数据，全量下发会让首屏 HTML 变大
- **Leaflet 必须本地化**。CDN 在演示环境不可用的概率不低，一旦白屏，整个 UC-04 演示就废了。`marker-icon.png` 也要一起入库，Leaflet 默认图标路径是相对 CSS 的，配错会显示成裂图
- **模板里的分支逻辑尽量抽成宏**。`{% if activity.crowd_index >= 80 %}` 这种判断在 5 个地方出现就该抽 `macros/badges.html`，否则改阈值要改 5 处
- **测试断言 HTML 而不是断言「页面能打开」**。用 `client.get("/itineraries/1")` 拿 `response.text`，断言里面包含 `data-crowd="high"` 这类稳定标识，比断言中文文案抗改动
