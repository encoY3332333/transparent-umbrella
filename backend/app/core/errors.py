"""错误码与业务异常。

错误码是**前后端契约**：前端按 `code` 分支处理，不解析 `message`。
因此这里的取值必须与 `docs/api.md` 第 0.3 节逐字一致——改一个字母就是破坏性变更，
须先提 Issue 并在 PR 里标注。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """全部对外错误码。枚举名与取值相同，方便日志里直接检索。"""

    # 通用
    OK = "OK"
    PARAM_INVALID = "PARAM_INVALID"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"

    # 认证（UC-01）
    SMS_CODE_INVALID = "SMS_CODE_INVALID"
    SMS_CODE_EXPIRED = "SMS_CODE_EXPIRED"
    SMS_SEND_TOO_FREQUENT = "SMS_SEND_TOO_FREQUENT"
    AUTH_SERVICE_UNAVAILABLE = "AUTH_SERVICE_UNAVAILABLE"

    # 出行条件（UC-02）
    CONDITION_INVALID_DATE_RANGE = "CONDITION_INVALID_DATE_RANGE"
    CONDITION_DURATION_OUT_OF_RANGE = "CONDITION_DURATION_OUT_OF_RANGE"
    CONDITION_BUDGET_OUT_OF_RANGE = "CONDITION_BUDGET_OUT_OF_RANGE"
    CONDITION_PARTY_SIZE_OUT_OF_RANGE = "CONDITION_PARTY_SIZE_OUT_OF_RANGE"
    CONDITION_TOO_MANY_TAGS = "CONDITION_TOO_MANY_TAGS"
    CONDITION_CITY_UNRESOLVED = "CONDITION_CITY_UNRESOLVED"
    CONDITION_MUST_VISIT_CONFLICT = "CONDITION_MUST_VISIT_CONFLICT"

    # 行程生成（UC-03）
    PLAN_NO_CANDIDATE = "PLAN_NO_CANDIDATE"
    PLAN_INFEASIBLE = "PLAN_INFEASIBLE"
    PLAN_BUDGET_TOO_LOW = "PLAN_BUDGET_TOO_LOW"
    EXTERNAL_CALL_LIMIT_EXCEEDED = "EXTERNAL_CALL_LIMIT_EXCEEDED"
    EXTERNAL_SERVICE_DEGRADED = "EXTERNAL_SERVICE_DEGRADED"

    # 行程调整（UC-05）
    ADJUST_LOCKED_ACTIVITY = "ADJUST_LOCKED_ACTIVITY"
    ADJUST_TIME_OVERLAP = "ADJUST_TIME_OVERLAP"
    ADJUST_POI_UNAVAILABLE = "ADJUST_POI_UNAVAILABLE"
    ADJUST_VERSION_LIMIT = "ADJUST_VERSION_LIMIT"

    # 分享（UC-06）
    SHARE_TOKEN_INVALID = "SHARE_TOKEN_INVALID"
    SHARE_ITINERARY_NOT_FOUND = "SHARE_ITINERARY_NOT_FOUND"


@dataclass(frozen=True)
class ErrorSpec:
    """错误码的元信息：HTTP 状态码 + 面向用户的中文提示。"""

    http_status: int
    message: str


ERROR_SPECS: dict[ErrorCode, ErrorSpec] = {
    ErrorCode.OK: ErrorSpec(200, "success"),
    ErrorCode.PARAM_INVALID: ErrorSpec(400, "参数校验失败"),
    ErrorCode.UNAUTHORIZED: ErrorSpec(401, "请先登录"),
    ErrorCode.FORBIDDEN: ErrorSpec(403, "无权访问该资源"),
    ErrorCode.NOT_FOUND: ErrorSpec(404, "资源不存在"),
    ErrorCode.CONFLICT: ErrorSpec(409, "当前状态不允许该操作"),
    ErrorCode.RATE_LIMITED: ErrorSpec(429, "操作过于频繁，请稍后再试"),
    ErrorCode.INTERNAL_ERROR: ErrorSpec(500, "服务端异常，请稍后重试"),
    ErrorCode.SMS_CODE_INVALID: ErrorSpec(400, "验证码错误"),
    ErrorCode.SMS_CODE_EXPIRED: ErrorSpec(400, "验证码已过期，请重新获取"),
    ErrorCode.SMS_SEND_TOO_FREQUENT: ErrorSpec(429, "验证码发送过于频繁，请 60 秒后再试"),
    ErrorCode.AUTH_SERVICE_UNAVAILABLE: ErrorSpec(503, "登录服务暂不可用"),
    ErrorCode.CONDITION_INVALID_DATE_RANGE: ErrorSpec(400, "结束日期不能早于开始日期"),
    ErrorCode.CONDITION_DURATION_OUT_OF_RANGE: ErrorSpec(400, "行程天数须在 1 到 15 天之间"),
    ErrorCode.CONDITION_BUDGET_OUT_OF_RANGE: ErrorSpec(400, "预算须在 500 到 200000 元之间"),
    ErrorCode.CONDITION_PARTY_SIZE_OUT_OF_RANGE: ErrorSpec(400, "出行人数须在 1 到 20 人之间"),
    ErrorCode.CONDITION_TOO_MANY_TAGS: ErrorSpec(400, "偏好标签最多选择 6 个"),
    ErrorCode.CONDITION_CITY_UNRESOLVED: ErrorSpec(400, "城市名无法解析为坐标，请检查输入"),
    ErrorCode.CONDITION_MUST_VISIT_CONFLICT: ErrorSpec(400, "必去与必避列表存在相同景点"),
    ErrorCode.PLAN_NO_CANDIDATE: ErrorSpec(422, "符合条件的景点不足，无法生成行程"),
    ErrorCode.PLAN_INFEASIBLE: ErrorSpec(422, "无法生成满足全部硬性约束的方案"),
    ErrorCode.PLAN_BUDGET_TOO_LOW: ErrorSpec(422, "已降至最低成本仍超出预算"),
    ErrorCode.EXTERNAL_CALL_LIMIT_EXCEEDED: ErrorSpec(503, "外部接口调用次数超限，请稍后重试"),
    ErrorCode.EXTERNAL_SERVICE_DEGRADED: ErrorSpec(200, "部分外部数据不可用，结果基于估算"),
    ErrorCode.ADJUST_LOCKED_ACTIVITY: ErrorSpec(409, "该活动已锁定，不能移动或删除"),
    ErrorCode.ADJUST_TIME_OVERLAP: ErrorSpec(409, "调整后同一日期内时间重叠"),
    ErrorCode.ADJUST_POI_UNAVAILABLE: ErrorSpec(409, "目标景点已下架，请换一个"),
    ErrorCode.ADJUST_VERSION_LIMIT: ErrorSpec(409, "历史版本已达上限（10 个），无法继续调整"),
    ErrorCode.SHARE_TOKEN_INVALID: ErrorSpec(400, "分享链接无效或已过期"),
    ErrorCode.SHARE_ITINERARY_NOT_FOUND: ErrorSpec(404, "分享的行程已被删除"),
}


@dataclass
class FieldError:
    """字段级错误，对应响应体 `details[]` 的元素。"""

    field: str
    reason: str


@dataclass
class BusinessError(Exception):
    """业务异常：由 service 层抛出，统一由 handlers 转成标准错误响应。

    service 只负责抛，不负责拼 HTTP 状态码——状态码由 `ERROR_SPECS` 决定，
    保证同一个错误码在任何入口返回的状态码都一致。
    """

    code: ErrorCode
    message: str | None = None
    details: list[FieldError] = field(default_factory=list)
    http_status: int | None = None

    def __post_init__(self) -> None:
        spec = ERROR_SPECS[self.code]
        if self.message is None:
            self.message = spec.message
        if self.http_status is None:
            self.http_status = spec.http_status
        super().__init__(self.message)

    @property
    def resolved_status(self) -> int:
        assert self.http_status is not None
        return self.http_status

    def to_payload(self, trace_id: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code.value,
            "message": self.message,
        }
        if self.details:
            payload["details"] = [{"field": d.field, "reason": d.reason} for d in self.details]
        if trace_id:
            payload["traceId"] = trace_id
        return payload
