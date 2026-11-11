"""一次请求内跨异步任务共享的外部调用计数（BR-10）。

**为什么必须用 `contextvars` 而不是模块级全局变量**：
FastAPI 会把同一个进程里的多个请求跑在不同的协程里，模块级 `_counter += 1`
在并发下会串数据——A 用户的规划把 B 用户的额度吃掉，或者反过来超限了却不报。
`ContextVar` 按「执行上下文」隔离，`asyncio.create_task` 会自动继承当前上下文，
所以一个请求里派生的子任务共享同一个计数器，不同请求之间互不影响。

**为什么放在 adapters 而不是 engine**：engine 是纯净层，不能有「外部调用」这个概念；
计数发生在真正发 HTTP 的那一层（`BaseAdapter`）。
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from app.core.errors import BusinessError, ErrorCode

logger = logging.getLogger(__name__)

# BR-10：单次规划的外部调用上限
EXTERNAL_CALL_LIMIT = 60

_count: ContextVar[int] = ContextVar("external_call_count", default=0)
# 当前上下文生效的上限。`budget(limit=n)` 会临时改它——
# 只清计数不改上限的话，`check()` 仍按 60 判断，测试里传 `limit=1` 根本不会触发，
# 而且真实场景下「某条低配路径限制更严」也没法表达。
_active_limit: ContextVar[int] = ContextVar("external_call_limit", default=EXTERNAL_CALL_LIMIT)


class ExternalCallLimitExceeded(BusinessError):
    """外部调用次数超限（BR-10）。

    业务上等价于 `EXTERNAL_CALL_LIMIT_EXCEEDED`，单独定义一是让 catch 更精确，
    二是让日志里能直接看出是「超限」而不是别的 503。
    """

    def __init__(self, limit: int = EXTERNAL_CALL_LIMIT, used: int | None = None) -> None:
        used = _count.get() if used is None else used
        super().__init__(
            code=ErrorCode.EXTERNAL_CALL_LIMIT_EXCEEDED,
            message=f"单次规划的外部接口调用已达上限 {limit} 次（当前 {used} 次），请稍后重试",
        )
        self.limit = limit
        self.used = used


def reset() -> None:
    """请求入口调用一次，清空计数。

    放在这里而不是让每个调用方自己 `set(0)`，是为了让「重置」只有一个实现，
    以后加指标（比如记录总调用量）不用改一堆地方。
    """
    _count.set(0)


def current() -> int:
    return _count.get()


def limit() -> int:
    """当前上下文生效的上限。默认 `EXTERNAL_CALL_LIMIT`，`budget()` 内可临时收紧。"""
    return _active_limit.get()


def record(n: int = 1, *, limit: int = EXTERNAL_CALL_LIMIT) -> int:
    """记一次外部调用并返回当前总次数；不回填、不抛异常。

    **先加后判**：第 61 次会返回 61，调用方据此在**发起 HTTP 之前**放弃，
    而不是「发出去再发现超了」——BR-10 的目的是控制对外部的压力，
    放在请求前判断才有意义。

    这里不抛异常是有意的：`BaseAdapter.get_json` 用 `except httpx.HTTPError`
    包住整个请求，如果 `record()` 抛 `ExternalCallLimitExceeded`，
    会被那个 except 吞成「重试一次」，反而把额度耗得更快。
    由调用方显式判断 `record() > limit` 再抛，语义清晰也不会被误捕。
    """
    used = _count.get() + n
    _count.set(used)
    return used


def check(limit_: int | None = None) -> None:
    """在真正发请求前检查额度，超了就抛。

    参数名带下划线：模块里已有同名函数 `limit()`，同名参数会把它遮蔽掉。
    """
    cap = _active_limit.get() if limit_ is None else limit_
    used = _count.get()
    if used > cap:
        logger.warning("外部调用超限：%d/%d", used, cap)
        raise ExternalCallLimitExceeded(limit=cap, used=used)


@contextmanager
def budget(limit: int = EXTERNAL_CALL_LIMIT) -> Iterator[None]:
    """把一段代码包进独立的调用预算里。

    进入时清零、退出时还原，避免嵌套调用（比如 service 里再调一个也带预算的函数）
    互相污染计数。
    """
    count_token = _count.set(0)
    limit_token = _active_limit.set(limit)
    try:
        yield
    finally:
        _active_limit.reset(limit_token)
        _count.reset(count_token)


__all__ = [
    "EXTERNAL_CALL_LIMIT",
    "ExternalCallLimitExceeded",
    "budget",
    "check",
    "current",
    "limit",
    "record",
    "reset",
]
