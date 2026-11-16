"""POI 仓储：把数据库里的景点行读成 `engine.selector.Poi`（Issue #4）。

**为什么要这一层**：`app/engine/**` 是纯净层，不许 import `app.models` / `sqlalchemy`。
但排程算法又必须拿到景点数据，于是「查库」这件事只能发生在 service 侧，
再把结果转成 engine 认识的 dataclass 传进去（`PlanContext.pois`）。

**为什么用 duck-typing 而不是 `from app.models.poi import Poi`**：
POI 表由 Issue #5 落地（`feat/5-poi-crowd-index`）。该分支合入前，
这里 import 一个不存在的模块会让整个应用起不来。
所以 `read_pois()` 里 `import` 放在函数内部并捕获 `ImportError`，
返回空列表——上层会得到 `PLAN_NO_CANDIDATE`，语义是「现在还没有景点数据」，
而不是 500。等 #5 合入后，这段代码**不需要改**，只是 import 真的能成功了。
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.selector import Poi

logger = logging.getLogger(__name__)


# 城市名归一：`西安` / `西安市` 应视为同一个城市（与 engine.selector 的口径一致）。
def normalize_city(city: str) -> str:
    return "".join(city.split()).removesuffix("市")


class PoiRepository:
    """按城市读 PUBLISHED 景点。单次查询，不分页——候选上限 300 由 engine 控制。"""

    def __init__(self, *, max_rows: int = 300) -> None:
        self._max_rows = max_rows

    def read_pois(self, session: Session, city: str) -> list[Poi]:
        model = _load_model()
        if model is None:
            logger.warning("POI 表尚不可用（Issue #5 未合入），候选池为空")
            return []

        stmt = select(model).where(model.status == "PUBLISHED").limit(self._max_rows)
        rows: Sequence[Any] = session.execute(stmt).scalars().all()
        target = normalize_city(city)
        # 城市过滤放在 Python 侧：`西安市` vs `西安` 这种差异用 SQL 表达要么走
        # `LIKE`（会误中「西安」「西安北」），要么加函数索引（MySQL 上不好写）。
        # 候选上限 300，全量拉回来过滤的代价可以接受。
        return [_to_poi(row) for row in rows if normalize_city(_attr(row, "city", "")) == target]


def _load_model() -> Any | None:
    try:
        from app.models.poi import Poi as PoiModel  # type: ignore[import-not-found]
    except ImportError:
        return None
    return PoiModel


def _attr(row: Any, name: str, default: Any) -> Any:
    """POI 表由别人维护，字段名可能略有出入（如 `lng` / `lon`）；
    取不到就给默认值，让 engine 侧的类型约束兜底，而不是在这里 KeyError。"""
    value = getattr(row, name, default)
    return default if value is None else value


def _to_poi(row: Any) -> Poi:
    return Poi(
        id=_attr(row, "id", 0),
        name=_attr(row, "name", ""),
        city=_attr(row, "city", ""),
        category=_attr(row, "category", "OTHER"),
        lat=float(_attr(row, "lat", 0.0)),
        lng=float(_attr(row, "lng", _attr(row, "lon", 0.0))),
        open_time=str(_attr(row, "open_time", "08:00")),
        close_time=str(_attr(row, "close_time", "18:00")),
        price=float(_attr(row, "price", 0.0)),
        capacity=int(_attr(row, "capacity", 0)),
        tags=tuple(_attr(row, "tags", ()) or ()),
        status=_attr(row, "status", "PUBLISHED"),
    )


__all__ = ["PoiRepository", "normalize_city"]
