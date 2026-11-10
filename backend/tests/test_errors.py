"""错误码表与业务异常的行为约定。"""

from __future__ import annotations

import pytest

from app.core.errors import ERROR_SPECS, BusinessError, ErrorCode, FieldError


def test_every_code_has_spec() -> None:
    missing = [code for code in ErrorCode if code not in ERROR_SPECS]
    assert not missing, f"以下错误码缺少 HTTP 状态与提示文案: {missing}"


def test_codes_match_their_enum_values() -> None:
    assert all(code.value == code.name for code in ErrorCode)


def test_business_error_uses_spec_defaults() -> None:
    error = BusinessError(ErrorCode.SMS_CODE_INVALID)

    assert error.message == "验证码错误"
    assert error.resolved_status == 400


def test_business_error_allows_override() -> None:
    error = BusinessError(
        ErrorCode.PLAN_BUDGET_TOO_LOW,
        message="已降至最低成本 7800 元，仍超出预算 800 元",
        details=[FieldError(field="budget", reason="too_low")],
    )

    payload = error.to_payload(trace_id="abc123")

    assert error.resolved_status == 422
    assert payload["code"] == "PLAN_BUDGET_TOO_LOW"
    assert payload["message"].startswith("已降至最低成本")
    assert payload["details"] == [{"field": "budget", "reason": "too_low"}]
    assert payload["traceId"] == "abc123"


def test_payload_omits_empty_details_and_trace() -> None:
    payload = BusinessError(ErrorCode.NOT_FOUND).to_payload()

    assert set(payload) == {"code", "message"}


@pytest.mark.parametrize(
    ("code", "status"),
    [
        (ErrorCode.UNAUTHORIZED, 401),
        (ErrorCode.FORBIDDEN, 403),
        (ErrorCode.CONFLICT, 409),
        (ErrorCode.RATE_LIMITED, 429),
        (ErrorCode.AUTH_SERVICE_UNAVAILABLE, 503),
        (ErrorCode.EXTERNAL_SERVICE_DEGRADED, 200),
    ],
)
def test_status_mapping(code: ErrorCode, status: int) -> None:
    assert ERROR_SPECS[code].http_status == status
