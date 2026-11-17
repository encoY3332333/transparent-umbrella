"""策略参数服务（Issue #13 / UC-09）。

职责只有四件：读当前生效、写新版本、回滚、校验与归一化。

**为什么不做进程内热加载**：参数改完要「只影响新发起的规划」。如果引擎在启动时
把权重读进内存，就得靠 reload / 重启才生效；而如果每个请求都直接查库，
`PlanService` 一次生成会走到 3 次（三套方案），白白多出 3 次查询。
折中是**一次读 + 60 秒 TTL 缓存 + 写操作主动失效**：

- 发布 / 回滚时 `invalidate_cache()`，所以 AC-1「保存后 5 秒内生效」是必然成立，
  不依赖 TTL 到期的运气；
- 多进程部署（uvicorn --workers）时，其它进程最多晚 60 秒感知——
  这正是 TTL 存在的意义，`docs/architecture.md` 也把它列为已知取舍。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, TypeVar

from cachetools import TTLCache
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import STRATEGY_WEIGHTS_TOLERANCE, get_settings
from app.core.errors import BusinessError, ErrorCode, FieldError
from app.models.strategy import ENGINE_WEIGHT_NAMES, WEIGHT_KEYS, StrategyParameter
from app.schemas.strategy import (
    DEFAULT_HOLIDAY_FACTORS,
    DEFAULT_THRESHOLDS,
    StrategyPayload,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

# 归一化结果保留 4 位小数：页面上滑块步长是 0.01，再多位没有意义，
# 而 4 位足够让 5 项之和精确落在 1.0000（残差补到最大项上）。
NORMALIZE_DECIMALS = 4

# 缓冲键只有一个（当前生效版本），容量给 8 是为了万一将来按城市分别缓存
_CACHE_KEY = "current"
_cache: TTLCache[str, StrategyParams] | None = None
_cache_ttl: int = -1


@dataclass(frozen=True)
class StrategyParams:
    """一份策略参数。`version=0` 表示库里还没有任何版本，用的是默认值。"""

    version: int
    weights: dict[str, float]
    holiday_factors: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_HOLIDAY_FACTORS))
    thresholds: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_THRESHOLDS))
    disabled_fallbacks: tuple[str, ...] = ()
    note: str = ""
    created_by: str = "system"
    effective_from: datetime | None = None

    def engine_weights(self) -> dict[str, float]:
        """转成 `engine.scorer.Weights` 的字段名（`preference` → `pref`）。

        同时**按总和等比缩放**：库里允许和落在 1±0.01，而 `Weights.__post_init__`
        的允差虽然也是 ±0.01，但两个容差一旦有一边被后人改小，
        `Weights()` 就会抛 ValueError 让整次生成失败。缩放到精确 1 之后，
        引擎侧无论容差怎么改都不会被这套数据绊倒。
        """
        raw = {ENGINE_WEIGHT_NAMES[key]: float(self.weights.get(key, 0.0)) for key in WEIGHT_KEYS}
        total = sum(raw.values())
        if total <= 0:
            # 五项全 0 是非法状态，validate_weights 会挡住；真出现就退回等权，
            # 让生成过程可继续，而不是抛一个用户看不懂的 500。
            logger.error("策略参数五项权重全为 0（v%s），退回等权", self.version)
            even = round(1.0 / len(raw), NORMALIZE_DECIMALS)
            return dict.fromkeys(raw, even)
        return {name: value / total for name, value in raw.items()}


# ----------------------------------------------------------------------
# 缓存
# ----------------------------------------------------------------------
def _get_cache() -> TTLCache[str, StrategyParams]:
    """按当前配置的 TTL 取缓存；TTL 被改过（测试里常见）就重建。"""
    global _cache, _cache_ttl
    ttl = get_settings().strategy_cache_ttl_seconds
    if _cache is None or ttl != _cache_ttl:
        _cache = TTLCache(maxsize=8, ttl=ttl)
        _cache_ttl = ttl
    return _cache


def invalidate_cache() -> None:
    """写操作后调用：下一次读一定回库。"""
    _get_cache().clear()


def reset_strategy_cache() -> None:
    """测试与运维用：丢掉缓存实例本身（连 TTL 一起重算）。"""
    global _cache, _cache_ttl
    _cache = None
    _cache_ttl = -1


# ----------------------------------------------------------------------
# 校验与归一化（纯函数，可单独测）
# ----------------------------------------------------------------------
def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    """按比例缩放到和为 1，保留 4 位小数，残差补到最大项。

    「补到最大项」而不是「补到第一项」：最大项加 0.0001 相对误差最小，
    不会把某一项推成负数或超过 1。
    """
    total = sum(float(weights.get(key, 0.0)) for key in WEIGHT_KEYS)
    if total <= 0:
        # 全 0 无法按比例缩放，等分是唯一有意义的解释
        even = round(1.0 / len(WEIGHT_KEYS), NORMALIZE_DECIMALS)
        return dict.fromkeys(WEIGHT_KEYS, even)

    scaled = {
        key: round(float(weights.get(key, 0.0)) / total, NORMALIZE_DECIMALS) for key in WEIGHT_KEYS
    }
    residue = round(1.0 - sum(scaled.values()), NORMALIZE_DECIMALS)
    if residue:
        biggest = max(WEIGHT_KEYS, key=lambda key: scaled[key])
        scaled[biggest] = round(scaled[biggest] + residue, NORMALIZE_DECIMALS)
    return scaled


def validate_weights(weights: dict[str, float]) -> None:
    """BR-23：每项 ∈ [0,1]，五项之和为 1（允差 ±`STRATEGY_WEIGHTS_TOLERANCE`）。

    AC-2 要求「拒绝并显示当前和」，所以错误信息里必须带 `total`，
    并且 `details[0].field` 指向 `weights`，前端据此把提示挂在滑块区。
    """
    missing = [key for key in WEIGHT_KEYS if key not in weights]
    if missing:
        raise BusinessError(
            code=ErrorCode.PARAM_INVALID,
            details=[FieldError(field="weights", reason=f"缺少权重项：{', '.join(missing)}")],
        )

    out_of_range = [
        f"{key}={float(weights[key]):.4f}"
        for key in WEIGHT_KEYS
        if not 0.0 <= float(weights[key]) <= 1.0
    ]
    if out_of_range:
        raise BusinessError(
            code=ErrorCode.PARAM_INVALID,
            details=[
                FieldError(field="weights", reason=f"每项权重须在 [0,1]：{', '.join(out_of_range)}")
            ],
        )

    total = sum(float(weights[key]) for key in WEIGHT_KEYS)
    if abs(total - 1.0) > STRATEGY_WEIGHTS_TOLERANCE:
        raise BusinessError(
            code=ErrorCode.PARAM_INVALID,
            message=f"五项权重之和必须为 1（允差 ±{STRATEGY_WEIGHTS_TOLERANCE}），当前为 {total:.4f}",
            details=[FieldError(field="weights", reason=f"当前和 {total:.4f}")],
        )


def zero_weight_warnings(weights: dict[str, float], disabled_fallbacks: list[str]) -> list[str]:
    """权重为 0 且对应兜底规则也关掉时，返回需要用户确认的说明。

    单独把某项权重设为 0 是合理操作（比如「这次不看费用」），引擎对缺失数据
    还有兜底（拥挤度缺失给中性 0.5）；但把兜底也关掉就意味着「这个维度既不算分、
    缺数据也不补偿」，排序会退化成只看剩下四项。这种组合不该静默保存。
    """
    warnings: list[str] = []
    for key in WEIGHT_KEYS:
        if float(weights.get(key, 0.0)) != 0.0:
            continue
        if key not in disabled_fallbacks:
            continue
        warnings.append(
            f"权重 {key}=0 且它的兜底规则已关闭：该维度既不计分、缺数据也不补偿，"
            f"推荐结果会只看其余四项。确认要这样保存吗？"
        )
    return warnings


def _dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def _loads(raw: str, fallback: T) -> T:
    """JSON 列解析。历史数据被手工改坏时退回默认值，不让整个页面 500。"""
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        logger.warning("策略参数 JSON 解析失败，已回退默认值：%r", raw)
        return fallback
    if not isinstance(value, type(fallback)):
        logger.warning("策略参数 JSON 类型不符（期望 %s），已回退默认值", type(fallback).__name__)
        return fallback
    return value


# ----------------------------------------------------------------------
# 服务
# ----------------------------------------------------------------------
class StrategyService:
    """读写策略参数。所有方法的第一参数都是实例绑定的 session，便于事务边界统一。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ---------------------------- 读 ----------------------------
    def current(self) -> StrategyParams:
        """当前生效参数：最新版本；没有任何版本时返回 `version=0` 的默认值。"""
        cache = _get_cache()
        cached = cache.get(_CACHE_KEY)
        if cached is not None:
            return cached

        row = self._latest()
        params = self._to_params(row) if row is not None else self._defaults()
        cache[_CACHE_KEY] = params
        return params

    def list_versions(self) -> list[StrategyParams]:
        """版本历史，按版本号倒序（docs/api.md 10.3）。"""
        rows = self._session.execute(
            select(StrategyParameter).order_by(StrategyParameter.version.desc())
        ).scalars()
        return [self._to_params(row) for row in rows]

    def get_version(self, version: int) -> StrategyParams:
        row = self._session.execute(
            select(StrategyParameter).where(StrategyParameter.version == version)
        ).scalar_one_or_none()
        if row is None:
            raise BusinessError(code=ErrorCode.NOT_FOUND, message=f"策略版本 v{version} 不存在")
        return self._to_params(row)

    # ---------------------------- 写 ----------------------------
    def publish(
        self, payload: StrategyPayload, *, created_by: str = "admin"
    ) -> tuple[StrategyParams | None, list[str]]:
        """发布新版本。

        返回 `(新版本, 警告列表)`：
        - 校验不通过 → 直接抛 `BusinessError(PARAM_INVALID)`（AC-2）；
        - 需要二次确认 → 返回 `(None, warnings)`，**不落库**，由路由转成
          `{saved:false, requiresConfirm:true}`；
        - 正常 → 返回 `(新版本, [])`。
        """
        weights = payload.weights.as_dict()
        validate_weights(weights)

        warnings = zero_weight_warnings(weights, payload.disabled_fallbacks)
        if warnings and not payload.confirm:
            logger.info("策略发布需要二次确认 warnings=%d", len(warnings))
            return None, warnings

        params = self._insert(
            weights=weights,
            holiday_factors=dict(payload.holiday_factors),
            thresholds=payload.thresholds.as_dict(),
            disabled_fallbacks=list(payload.disabled_fallbacks),
            note="",
            created_by=created_by,
        )
        logger.info("策略参数发布成功 version=%s by=%s", params.version, created_by)
        return params, []

    def rollback(self, version: int, *, created_by: str = "admin") -> StrategyParams:
        """回滚到历史版本。

        **不是把指针拨回去**：历史版本必须永久保留（BR-24），
        所以回滚 = 以目标版本的参数再插一条新版本，`note` 记明来源。
        这样版本列表里能看出「v5 是对 v3 的回滚」，AC-3 也要求新增一条回滚记录。
        """
        target = self.get_version(version)
        params = self._insert(
            weights=dict(target.weights),
            holiday_factors=dict(target.holiday_factors),
            thresholds=dict(target.thresholds),
            disabled_fallbacks=list(target.disabled_fallbacks),
            note=f"回滚自 v{version}",
            created_by=created_by,
        )
        logger.info("策略参数回滚 v%s -> 新版本 v%s", version, params.version)
        return params

    # ---------------------------- 内部 ----------------------------
    def _insert(
        self,
        *,
        weights: dict[str, float],
        holiday_factors: dict[str, float],
        thresholds: dict[str, int],
        disabled_fallbacks: list[str],
        note: str,
        created_by: str,
    ) -> StrategyParams:
        row = StrategyParameter(
            version=self._next_version(),
            w_pref=float(weights["preference"]),
            w_weather=float(weights["weather"]),
            w_crowd=float(weights["crowd"]),
            w_travel=float(weights["travel"]),
            w_cost=float(weights["cost"]),
            holiday_factors_json=_dumps(holiday_factors),
            thresholds_json=_dumps(thresholds),
            disabled_fallbacks_json=_dumps(disabled_fallbacks),
            note=note,
            created_by=created_by,
            effective_from=datetime.now(UTC),
        )
        self._session.add(row)
        try:
            self._session.commit()
        except IntegrityError as exc:  # pragma: no cover - 只在并发发布时发生
            self._session.rollback()
            raise BusinessError(code=ErrorCode.CONFLICT, message="策略版本号冲突，请重试") from exc
        # commit 之后 row 已有自增主键与默认值
        params = self._to_params(row)
        invalidate_cache()
        return params

    def _latest(self) -> StrategyParameter | None:
        return self._session.execute(
            select(StrategyParameter).order_by(StrategyParameter.version.desc()).limit(1)
        ).scalar_one_or_none()

    def _next_version(self) -> int:
        latest = self._latest()
        return 1 if latest is None else latest.version + 1

    def _defaults(self) -> StrategyParams:
        """库为空时的默认值：与 `Settings.strategy_w_*` 同源。

        同源很重要——否则「没发布过策略」和「发布了默认策略」会得到两组不同的
        推荐结果，而用户看不出差别。
        """
        settings = get_settings()
        return StrategyParams(
            version=0,
            weights=dict(settings.strategy_weights),
            holiday_factors=dict(DEFAULT_HOLIDAY_FACTORS),
            thresholds=dict(DEFAULT_THRESHOLDS),
            disabled_fallbacks=(),
            note="默认值（尚未发布任何版本）",
            created_by="system",
            effective_from=None,
        )

    @staticmethod
    def _to_params(row: StrategyParameter) -> StrategyParams:
        disabled: list[object] = _loads(row.disabled_fallbacks_json, [])
        return StrategyParams(
            version=row.version,
            weights={
                "preference": row.w_pref,
                "weather": row.w_weather,
                "crowd": row.w_crowd,
                "travel": row.w_travel,
                "cost": row.w_cost,
            },
            holiday_factors=_loads(row.holiday_factors_json, dict(DEFAULT_HOLIDAY_FACTORS)),
            thresholds=_loads(row.thresholds_json, dict(DEFAULT_THRESHOLDS)),
            disabled_fallbacks=tuple(str(item) for item in disabled),
            note=row.note,
            created_by=row.created_by,
            effective_from=row.effective_from,
        )


__all__ = [
    "NORMALIZE_DECIMALS",
    "StrategyParams",
    "StrategyService",
    "invalidate_cache",
    "normalize_weights",
    "reset_strategy_cache",
    "validate_weights",
    "zero_weight_warnings",
]
