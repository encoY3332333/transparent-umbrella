"""异常 → 统一错误响应的转换层。

目标：任何异常出口都只有一种 JSON 形状 `{code, message, details?, traceId}`，
前端不需要为「校验错误 / 业务错误 / 500」写三套解析逻辑。
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.errors import ERROR_SPECS, BusinessError, ErrorCode, FieldError
from app.core.logging import trace_id_of

logger = logging.getLogger(__name__)


def _error_response(
    request: Request,
    *,
    code: ErrorCode,
    message: str | None = None,
    details: list[FieldError] | None = None,
    http_status: int | None = None,
) -> JSONResponse:
    spec = ERROR_SPECS[code]
    payload: dict[str, object] = {
        "code": code.value,
        "message": message or spec.message,
    }
    if details:
        payload["details"] = [{"field": d.field, "reason": d.reason} for d in details]
    trace_id = trace_id_of(request)
    if trace_id:
        payload["traceId"] = trace_id
    return JSONResponse(status_code=http_status or spec.http_status, content=payload)


def register_exception_handlers(app: FastAPI) -> None:
    """在 `create_app()` 里调用一次即可。"""

    @app.exception_handler(BusinessError)
    async def handle_business_error(request: Request, exc: BusinessError) -> JSONResponse:
        logger.info("业务异常 %s: %s", exc.code.value, exc.message)
        payload = exc.to_payload(trace_id_of(request))
        return JSONResponse(status_code=exc.resolved_status, content=payload)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            FieldError(
                field=".".join(str(part) for part in err.get("loc", ()) if part != "body"),
                reason=str(err.get("msg", "invalid")),
            )
            for err in exc.errors()
        ]
        return _error_response(request, code=ErrorCode.PARAM_INVALID, details=details)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        mapping = {
            401: ErrorCode.UNAUTHORIZED,
            403: ErrorCode.FORBIDDEN,
            404: ErrorCode.NOT_FOUND,
            429: ErrorCode.RATE_LIMITED,
        }
        code = mapping.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
        # 4xx 保留 FastAPI 自带 detail，5xx 不回显内部信息
        message = str(exc.detail) if exc.status_code < 500 else None
        return _error_response(request, code=code, message=message, http_status=exc.status_code)

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # 未预期异常必须带 traceId 落 ERROR 日志，否则线上只剩一句 500
        logger.exception("未处理异常: %s", exc)
        return _error_response(request, code=ErrorCode.INTERNAL_ERROR, http_status=500)
