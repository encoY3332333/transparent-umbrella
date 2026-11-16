"""业务依赖：把 engine 的三个子模块装配成一个 `PlanService`（Issue #4）。

**为什么需要这个文件**：`PlanService.__init__` 要求注入三个 Protocol 实现，
但 `#6`（排程引擎）和 `#7`（可行性校验）还没合入。如果路由直接 `PlanService(...)`，
应用启动就会 `NameError`。所以这里按「注册表 + 缺省占位」的方式装配：

1. 真实现存在就注册进来（`IMPLEMENTATIONS`），路由永远只依赖 Protocol；
2. 拿不到真实现时用 `UnavailablePacker` 之类的占位，它**明确报错**而不是返回空方案——
   用户看到的是 `PLAN_INFEASIBLE`（「暂时无法生成」），日志里是「#6 未落地」，
   而不是一套凭空编出来的行程。

`#6` / `#7` 合入后只需在 `_register()` 里加两行 import，路由与 service 一行都不用改。
"""

from __future__ import annotations

import logging
from functools import lru_cache

from app.core.errors import BusinessError, ErrorCode
from app.engine.protocols import (
    Candidate,
    Conflict,
    PlanContext,
    PlanDraft,
    Requirement,
)
from app.services.engine_bridge import build_packer
from app.services.plan_service import PlanService

logger = logging.getLogger(__name__)


class SelectorAdapter:
    """把 `engine.selector.CandidateSelector` 适配成 `protocols.CandidateSelector`。

    两者的差异是「候选 POI 从哪来」：`#5` 的实现是 `select(criteria, pois)`（POI 由调用方给），
    `#4` 的协议是 `select(requirement, pois)`（条件更窄，只有排程需要的字段）。
    适配层只做这一件事，不掺业务判断。
    """

    def __init__(self, inner: object | None = None) -> None:
        if inner is None:
            from app.engine.selector import CandidateSelector as InnerSelector

            inner = InnerSelector()
        self._inner = inner

    def select(self, requirement: Requirement, pois: list[object]) -> list[Candidate]:
        from app.engine.selector import SelectionCriteria

        criteria = SelectionCriteria(
            city=requirement.city,
            preference_tags=requirement.preference_tags,
            must_visit=requirement.must_visit,
            avoid_poi=requirement.avoid_poi,
        )
        selected = self._inner.select(criteria, pois)  # type: ignore[attr-defined]
        return [Candidate(poi=poi) for poi in selected]


class UnavailablePacker:
    """`#6` 未合入时的占位。显式抛错，绝不返回「看起来能用」的空方案。"""

    def plan(
        self, requirement: Requirement, candidates: list[Candidate], context: PlanContext
    ) -> list[PlanDraft]:
        logger.error("排程引擎（#6）尚未合入，无法生成方案")
        raise BusinessError(
            code=ErrorCode.PLAN_INFEASIBLE,
            message="排程引擎正在接入，暂无法生成行程，请稍后再试",
        )


class UnavailableChecker:
    """`#7` 未合入时的占位。

    返回空列表（= 无冲突）而不是抛错：可行性校验是「加法」，缺失时
    编排仍能产出方案，只是少了提示。这一点与 Packer 不同——
    没有 Packer 就没有方案本身。
    """

    def validate(self, plan: PlanDraft) -> list[Conflict]:
        logger.warning("可行性校验（#7）尚未合入，本方案未做冲突检查")
        return []


def _register() -> dict[str, object]:
    """真实现的注册表。

    **不能只 `getattr(app.engine, "Packer")`**：`engine/__init__.py` 目前只导出
    `#5` 的候选筛选与拥挤度，`#6` 的 `Packer` / `StrategyEngine` 都没在里面
    （见 PR #32 的 `engine/__init__.py`）。所以走 `services/engine_bridge.py`：
    它负责把 `#6` 的 `StrategyEngine.plan(candidates, request)` 适配成
    `#4` 的 `PlanPacker.plan(requirement, candidates, context)`，
    并且在 `#6` 未合入时返回 None，由这里回落成占位实现。
    """
    registry: dict[str, object] = {"selector": SelectorAdapter()}

    packer = build_packer()
    if packer is not None:
        registry["packer"] = packer

    # `#7` 的可行性校验由组长实现。它合入后在 `app.engine` 上导出
    # `FeasibilityChecker` 即可被这里发现——本 Issue 不改 `#7` 的文件。
    import app.engine as engine_pkg

    checker_cls = getattr(engine_pkg, "FeasibilityChecker", None)
    if checker_cls is not None:
        registry["feasibility"] = checker_cls()

    return registry


@lru_cache(maxsize=1)
def get_plan_service() -> PlanService:
    """进程内单例。装配成本只有几次 import，但没必要每个请求做一遍。"""
    registry = _register()
    packer = registry.get("packer") or UnavailablePacker()
    feasibility = registry.get("feasibility") or UnavailableChecker()
    logger.info(
        "PlanService 装配完成 packer=%s feasibility=%s",
        type(packer).__name__,
        type(feasibility).__name__,
    )
    return PlanService(
        selector=registry["selector"],  # type: ignore[arg-type]
        packer=packer,  # type: ignore[arg-type]
        feasibility=feasibility,  # type: ignore[arg-type]
    )


def reset_plan_service_cache() -> None:
    """测试用：清掉单例，下一次取依赖时按新注册表重建。"""
    get_plan_service.cache_clear()


plan_service_dep = get_plan_service

__all__ = ["get_plan_service", "plan_service_dep", "reset_plan_service_cache"]
