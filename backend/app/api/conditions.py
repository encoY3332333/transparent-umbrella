"""出行条件 JSON 接口（UC-02）。"""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.common import ApiResponse
from app.schemas.condition import ConditionValidationOut, TravelConditionIn
from app.services.condition_service import validate_condition

router = APIRouter(prefix="/conditions", tags=["conditions"])


@router.post("/validate", response_model=ApiResponse[ConditionValidationOut])
def validate_travel_condition(payload: TravelConditionIn) -> ApiResponse[ConditionValidationOut]:
    """服务端权威校验；页面本地校验只做必填与格式。"""

    return ApiResponse.ok(validate_condition(payload))
