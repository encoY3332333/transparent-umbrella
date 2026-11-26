"""UC-01 认证接口：发放验证码、登录、登出、读取与保存偏好。

token 走 HttpOnly Cookie（ADR-001）：前端拿不到 token 本体，XSS 也偷不走，
代价是必须同源部署或配 CORS 凭证——课程项目前后端同域，这个代价为零。
"""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.core.config import Settings
from app.core.deps import CurrentTouristDep, DbDep, OptionalTouristDep, SettingsDep
from app.core.security import ACCESS_TOKEN_COOKIE, create_access_token
from app.models.tourist import Tourist
from app.schemas.common import ApiResponse
from app.schemas.tourist import (
    LoginIn,
    LoginOut,
    PreferenceIn,
    PreferenceOut,
    SmsCodeIn,
    SmsCodeOut,
    TouristOut,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_token_cookie(response: Response, tourist: Tourist, settings: Settings) -> int:
    """写入登录 Cookie，返回有效期秒数。

    `httponly=True` 是 ADR-001 的硬要求；`samesite="lax"` 挡住跨站 POST 携带
    Cookie；生产环境才加 `secure`——本地 http 调试加 secure 会让 Cookie 直接不落地。
    """
    # create_access_token 返回 (token, 有效期秒数)，有效期直接用它算出来的那个，
    # 不要自己再乘一遍 jw​t_expire_minutes——两处口径一旦不一致，Cookie 会比 token 活得久。
    token, expires_in = create_access_token(tourist.id, settings)
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=token,
        max_age=expires_in,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        path="/",
    )
    return expires_in


@router.post("/sms-code", response_model=ApiResponse[SmsCodeOut])
def send_sms_code(
    payload: SmsCodeIn, session: DbDep, settings: SettingsDep
) -> ApiResponse[SmsCodeOut]:
    """发放验证码。同一手机号 60 秒内只能请求一次。"""
    expires_in, debug_code = auth_service.request_code(session, settings, payload.phone)
    return ApiResponse[SmsCodeOut].ok(
        SmsCodeOut(
            expiresIn=expires_in,
            retryAfter=auth_service.CODE_RETRY_SECONDS,
            debugCode=debug_code,
        )
    )


@router.post("/login", response_model=ApiResponse[LoginOut])
def login(
    payload: LoginIn, response: Response, session: DbDep, settings: SettingsDep
) -> ApiResponse[LoginOut]:
    """验证码登录（首次登录即注册）。成功后下发 Cookie。"""
    tourist = auth_service.login(session, settings, payload.phone, payload.code)
    expires_in = _set_token_cookie(response, tourist, settings)
    return ApiResponse[LoginOut].ok(
        LoginOut(tourist=TouristOut.from_model(tourist), expiresIn=expires_in)
    )


@router.post("/logout", response_model=ApiResponse[dict])
def logout(response: Response, tourist: OptionalTouristDep) -> ApiResponse[dict]:
    """登出：清 Cookie。没登录也返回成功——前端只管清本地状态即可。"""
    response.delete_cookie(ACCESS_TOKEN_COOKIE, path="/")
    return ApiResponse[dict].ok({"loggedOut": True})


@router.get("/me", response_model=ApiResponse[TouristOut])
def me(tourist: OptionalTouristDep) -> ApiResponse[TouristOut]:
    """读取当前登录状态。

    未登录返回 `data: null` 而不是 401：前端启动时要靠这个接口判断「要不要显示
    登录按钮」，401 会让它必须把 401 当正常分支处理，容易和真正的鉴权失败混淆。
    """
    if tourist is None:
        return ApiResponse[TouristOut].ok(None)
    return ApiResponse[TouristOut].ok(TouristOut.from_model(tourist))
