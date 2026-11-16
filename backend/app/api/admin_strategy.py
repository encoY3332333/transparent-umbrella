"""后台策略参数接口（Issue #13 / UC-09）。

路径沿用 `docs/api.md` 第 10 节与 `docs/diagrams/seq-uc09-strategy.puml` 的
`/api/admin/strategies`（Issue #13 正文里写的单数 `/api/admin/strategy` 是笔误，
契约与顺序图都用复数；改动方向见 PR 说明）。

**鉴权暂缺**：UC-01（#2）的登录与角色还没合入，这里先把接口做出来，
`created_by` 取配置里的 `ADMIN_INIT_USERNAME`。等 #2 合并后在本文件加一个
`Depends(require_admin)` 即可，业务代码不用动——这也是把校验全放在 service 的原因。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import DbDep, SettingsDep
from app.schemas.common import ApiResponse
from app.schemas.strategy import (
    NormalizeIn,
    NormalizeOut,
    StrategyPayload,
    StrategyPublishOut,
    StrategyVersionOut,
)
from app.services.strategy_service import StrategyParams, StrategyService, normalize_weights

router = APIRouter(prefix="/admin/strategies", tags=["admin-strategy"])


def _to_out(params: StrategyParams) -> StrategyVersionOut:
    return StrategyVersionOut(
        version=params.version,
        weights=params.weights,
        holiday_factors=params.holiday_factors,
        thresholds=params.thresholds,
        disabled_fallbacks=list(params.disabled_fallbacks),
        note=params.note,
        created_by=params.created_by,
        effective_from=params.effective_from,
    )


@router.get("/current", response_model=ApiResponse[StrategyVersionOut], summary="当前生效策略")
def get_current(session: DbDep) -> ApiResponse[StrategyVersionOut]:
    """当前生效参数。库为空时返回 `version=0` 的默认值（与 `Settings` 同源）。

    AC 里的「可通过接口查看当前生效版本」就是这一条——**没有**塞进 `/api/health`：
    `docs/api.md` 第 11 节明确要求健康检查保持极简、且不依赖数据库
    （库挂了探针要能立刻发现，而不是跟着一起 500）。
    """
    return ApiResponse.ok(_to_out(StrategyService(session).current()))


@router.get("", response_model=ApiResponse[list[StrategyVersionOut]], summary="策略版本历史")
def list_versions(session: DbDep) -> ApiResponse[list[StrategyVersionOut]]:
    """版本历史，按版本号倒序（BR-24：历史版本永久保留）。"""
    return ApiResponse.ok([_to_out(item) for item in StrategyService(session).list_versions()])


@router.post("", response_model=ApiResponse[StrategyPublishOut], summary="发布新策略")
def publish(
    payload: StrategyPayload, session: DbDep, settings: SettingsDep
) -> ApiResponse[StrategyPublishOut]:
    """发布新版本，版本号自增。

    三种结局都是 200：
    - 保存成功 `saved=true`；
    - 权重和不为 1 → 400 `PARAM_INVALID`（`details[0].field == "weights"`，
      `message` 里带当前和，满足 AC-2）；
    - 需要二次确认 → 200 `saved=false, requiresConfirm=true`，`warnings` 说明原因。
    """
    params, warnings = StrategyService(session).publish(
        payload, created_by=settings.admin_init_username
    )
    if params is None:
        return ApiResponse.ok(
            StrategyPublishOut(saved=False, requires_confirm=True, warnings=warnings)
        )
    return ApiResponse.ok(StrategyPublishOut(saved=True, strategy=_to_out(params)))


@router.post("/normalize", response_model=ApiResponse[NormalizeOut], summary="一键归一化")
def normalize(payload: NormalizeIn) -> ApiResponse[NormalizeOut]:
    """把五项权重按比例缩放到和为 1（AC：误差 ≤ 0.001）。

    放在服务端而不是只在前端算：页面与将来的脚本入口共用同一套归一化逻辑，
    否则「页面上点一下」和「接口调一次」会得到两个结果。
    """
    raw = payload.weights.as_dict()
    return ApiResponse.ok(
        NormalizeOut(weights=normalize_weights(raw), total_before=round(sum(raw.values()), 4))
    )


@router.post(
    "/rollback/{version}",
    response_model=ApiResponse[StrategyVersionOut],
    summary="回滚到指定版本",
)
def rollback(
    version: int, session: DbDep, settings: SettingsDep
) -> ApiResponse[StrategyVersionOut]:
    """回滚 = 以历史版本的参数再发一版（版本号 +1，`note` 记明来源）。"""
    params = StrategyService(session).rollback(version, created_by=settings.admin_init_username)
    return ApiResponse.ok(_to_out(params))


__all__ = ["router"]
