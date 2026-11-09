# [Feature] 游客登录与偏好建档

## 背景 / Background

SmartTrip 的行程推荐需要「个性化」的输入：同样去杭州、同样 3 天，一个偏好人文历史的人和一个带孩子的人，行程应该完全不同。
偏好必须在首次使用时建档，否则每次规划都要重填，用户会流失（问卷 Q3：56.2% 的用户规划耗时超过 2 小时，任何额外填写成本都会被放大）。

对应 SRS：3.3.1 · 用例 UC-01

## 需求描述 / Description

对接统一身份认证系统完成手机号验证码登录；首次登录引导填写偏好档案（偏好标签、同行人员构成、出行节奏、消费档次）；再次登录直接回显。

## 任务清单 / Tasks

- [ ] 后端：`AuthController` 提供 `POST /api/auth/send-code`、`POST /api/auth/login`、`GET /api/auth/me`、`PUT /api/auth/preference`
- [ ] 后端：`AuthManager` 控制类，负责令牌校验、游客查找/创建、偏好保存
- [ ] 后端：`AuthServerAdapter` 代理类，对接 AuthServer 的 `verifyToken()`，配置 1.5s/3s 超时与降级
- [ ] 后端：验证码错误计数（5 次/5 分钟锁定），用 Redis 或内存缓存实现
- [ ] 前端：`LoginView.vue`（手机号 + 验证码、60 秒倒计时）、`PreferenceDialog.vue`（标签多选、构成单选、节奏滑块、消费档次）
- [ ] 前端：登录态持久化（token 存 localStorage + 请求拦截器自动附带）
- [ ] 测试：`AuthManagerTest` 覆盖登录成功、验证码错误、锁定、首次建档、偏好回显 5 个场景

## 验收标准 / Acceptance Criteria

- [ ] AC-1 输入正确验证码后，3 秒内完成登录并跳转首页
- [ ] AC-2 首次登录必须进入偏好设置页；偏好可成功保存，并在下次登录时完整回显
- [ ] AC-3 连续 5 次输入错误验证码后，账号被临时锁定 5 分钟，提示剩余时间
- [ ] 同一手机号只能绑定一个游客档案（BR-01），重复注册返回 409
- [ ] 偏好标签最多选 6 个（BR-02），超出时提交按钮禁用并提示
- [ ] 跳过偏好设置时以默认值（节奏适中、消费中等、无标签）建档
- [ ] AuthServer 不可用时返回明确错误码 `AUTH_SERVICE_UNAVAILABLE`，前端提示「登录服务暂不可用，请稍后重试」

## 关联 / Related

- 依赖 #1
- 阻塞 #3（需要登录态才能录入条件）

## 元信息

- 预估工作量：6 小时
- Labels：`feature` `backend` `P0`
- Milestone：`v0.1.0 Alpha`
- Assignee：【组员2】
- 分支：`feature/2-tourist-login`
- 涉及业务规则：BR-01、BR-02
