"""结构化日志与请求追踪号。

每个请求分配一个 `traceId`，同时写进日志与错误响应体（`docs/api.md` 0.2 节），
用户报「页面报错」时，凭这个号就能在日志里定位到那一次请求。
"""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from typing import Final

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

TRACE_ID_HEADER: Final = "X-Trace-Id"
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")


def new_trace_id() -> str:
    """12 位十六进制，够区分请求又不至于把日志撑爆。"""
    return uuid.uuid4().hex[:12]


class _TraceIdFilter(logging.Filter):
    """把当前上下文里的 traceId 塞进每条日志记录。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id_var.get()
        return True


def configure_logging(level: str = "INFO") -> None:
    """幂等地配置根 logger —— 重复调用不会叠加 handler。"""
    root = logging.getLogger()
    root.setLevel(level.upper())

    for handler in list(root.handlers):
        if getattr(handler, "_smarttrip", False):
            root.removeHandler(handler)

    handler = logging.StreamHandler()
    handler._smarttrip = True  # type: ignore[attr-defined]
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)-7s [%(trace_id)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    handler.addFilter(_TraceIdFilter())
    root.addHandler(handler)


class TraceIdMiddleware(BaseHTTPMiddleware):
    """优先复用上游传入的 X-Request-Id，没有就新生成一个。"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        trace_id = request.headers.get("X-Request-Id") or new_trace_id()
        token = trace_id_var.set(trace_id)
        request.state.trace_id = trace_id
        try:
            response = await call_next(request)
        finally:
            trace_id_var.reset(token)
        response.headers[TRACE_ID_HEADER] = trace_id
        return response


def trace_id_of(request: Request) -> str | None:
    """从 request.state 取 traceId；中间件未生效时回退到上下文变量。"""
    value: str | None = getattr(request.state, "trace_id", None)
    if value:
        return value
    current = trace_id_var.get()
    return None if current == "-" else current
