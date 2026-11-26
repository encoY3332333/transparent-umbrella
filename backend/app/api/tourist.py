"""偏好档案接口（UC-01 第 1.3 / 1.4 节）。

路径放在 `/api/tourists/me/preference` 而不是 `/api/auth/preferences`：
偏好是**用户资源**，认证路径下只该有登录登出这类凭证动作；把资源挂在
`tourists/me` 下，将来加「我的行程」「我的收藏」时路径族是一致的。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import CurrentTouristDep, DbDep, OptionalTouristDep
from app.schemas.common import ApiResponse
from app.schemas.tourist import PreferenceIn, PreferenceOut
from app.services import auth_service

router = APIRouter(prefix="/tourists", tags=["tourist"])


@router.get("/me/preference", response_model=ApiResponse[PreferenceOut])
def get_preference(tourist: OptionalTouristDep) -> ApiResponse[PreferenceOut]:
    """查询我的偏好。

    未建档时 `data` 为 `null` 而不是 404（docs/api.md 1.3 明确要求）：
    前端拿 null 就弹浮层引导建档，404 反而要额外区分「没建档」和「接口错了」。
    未登录同样返回 null，前端据 `/api/auth/me` 判断是否引导登录。
    """
    if tourist is None or not tourist.has_preference:
        return ApiResponse[PreferenceOut].ok(None)
    return ApiResponse[PreferenceOut].ok(PreferenceOut.from_model(tourist))


@router.put("/me/preference", response_model=ApiResponse[PreferenceOut])
def save_preference(
    payload: PreferenceIn, tourist: CurrentTouristDep, session: DbDep
) -> ApiResponse[PreferenceOut]:
    """保存偏好。未登录一律 401——偏好是账号数据，没有匿名写入的语义。"""
    tourist = auth_service.save_preferences(
        session,
        tourist,
        tags=payload.preferenceTags,
        party_type=payload.partyType,
        pace=payload.pace.value,
        budget_level=payload.budgetLevel.value,
    )
    return ApiResponse[PreferenceOut].ok(PreferenceOut.from_model(tourist))
