"""令牌签发与校验：登录凭证（JWT）+ 分享链接（HMAC-SHA256）。

两个令牌用**不同的密钥**：JWT 用 `JWT_SECRET`，分享链接用 `SHARE_SIGN_SALT`。
即使一方泄露，另一方的签名仍然无法伪造。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any, Final

import jwt

from app.core.config import Settings

ACCESS_TOKEN_COOKIE: Final = "access_token"
SHARE_TOKEN_PREFIX: Final = "v1"


class TokenError(ValueError):
    """令牌无效、过期或被篡改。调用方负责翻译成对应的业务错误码。"""


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(UTC)


# ---------------------------------------------------------------------------
# 登录凭证（ADR-001：JWT 放在 HttpOnly Cookie 里，不落 localStorage）
# ---------------------------------------------------------------------------
def create_access_token(
    tourist_id: int, settings: Settings, *, now: datetime | None = None
) -> tuple[str, int]:
    """返回 (token, 有效期秒数)。"""
    issued_at = _now(now)
    expires_in = settings.jwt_expire_minutes * 60
    payload = {
        "sub": str(tourist_id),
        "iat": int(issued_at.timestamp()),
        "exp": int((issued_at + timedelta(seconds=expires_in)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_in


def decode_access_token(
    token: str, settings: Settings, *, now: datetime | None = None
) -> dict[str, Any]:
    """校验签名与有效期，返回 payload。失败一律抛 `TokenError`。

    时间校验自己做，不交给 PyJWT：`jwt.decode` 的 `now` 参数是 PyJWT 3.0 才有的，
    本项目锁的是 `pyjwt>=2.9,<3.0`，在 2.x 上传进去会被当成未知 kwarg 静默忽略，
    库改用真实系统时间去比 `exp`——于是 `create_access_token(now=...)` 与校验
    不在同一时间基准上，测试里传固定时间就会出现「签发即过期」。
    """
    if not token:
        raise TokenError("empty token")
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"], "verify_exp": False},
            leeway=0,
        )
    except jwt.InvalidTokenError as exc:
        raise TokenError("invalid token") from exc

    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise TokenError("token has no integer exp")
    if exp <= int(_now(now).timestamp()):
        raise TokenError("token expired")
    return payload


def tourist_id_from_token(token: str, settings: Settings, *, now: datetime | None = None) -> int:
    payload = decode_access_token(token, settings, now=now)
    try:
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise TokenError("token subject is not a tourist id") from exc


# ---------------------------------------------------------------------------
# 分享链接（BR-17：HMAC 签名防遍历，7 天有效）
# ---------------------------------------------------------------------------
def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _sign(message: str, salt: str) -> str:
    digest = hmac.new(salt.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    return _b64encode(digest)


def sign_share_token(
    itinerary_id: int,
    settings: Settings,
    *,
    ttl_days: int | None = None,
    now: datetime | None = None,
) -> tuple[str, datetime]:
    """返回 (token, 过期时间)。token 形如 `v1.<base64 payload>.<签名>`。"""
    days = settings.share_link_ttl_days if ttl_days is None else ttl_days
    expires_at = _now(now) + timedelta(days=days)
    payload = {"id": itinerary_id, "exp": int(expires_at.timestamp())}
    body = _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    message = f"{SHARE_TOKEN_PREFIX}.{body}"
    return f"{message}.{_sign(message, settings.share_sign_salt)}", expires_at


def verify_share_token(token: str, settings: Settings, *, now: datetime | None = None) -> int:
    """校验签名与过期时间，返回行程 ID。"""
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != SHARE_TOKEN_PREFIX:
        raise TokenError("malformed share token")

    prefix, body, signature = parts
    expected = _sign(f"{prefix}.{body}", settings.share_sign_salt)
    # 先验签再解析内容：避免对攻击者构造的 JSON 做多余解析
    if not hmac.compare_digest(expected, signature):
        raise TokenError("bad signature")

    try:
        payload = json.loads(_b64decode(body))
        itinerary_id = int(payload["id"])
        expires_at = int(payload["exp"])
    except (ValueError, KeyError, TypeError) as exc:
        raise TokenError("malformed share payload") from exc

    if expires_at < int(_now(now).timestamp()):
        raise TokenError("share token expired")
    return itinerary_id
