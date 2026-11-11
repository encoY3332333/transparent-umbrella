"""令牌签发与校验：JWT 登录凭证 + HMAC 分享链接。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import Settings
from app.core.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    sign_share_token,
    tourist_id_from_token,
    verify_share_token,
)

FIXED_NOW = datetime(2026, 11, 10, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        jwt_secret="unit-test-jwt-secret-0123456789abcdef",
        share_sign_salt="unit-test-share-salt-0123456789abcdef",
    )


def test_access_token_roundtrip(settings: Settings) -> None:
    token, expires_in = create_access_token(1001, settings, now=FIXED_NOW)

    assert expires_in == settings.jwt_expire_minutes * 60
    # 必须传 now：否则 PyJWT 拿真实系统时间去比 exp，测试会随日历推移而失败
    assert tourist_id_from_token(token, settings, now=FIXED_NOW) == 1001


def test_access_token_rejects_other_secret(settings: Settings) -> None:
    token, _ = create_access_token(1001, settings, now=FIXED_NOW)
    other = Settings(
        jwt_secret="another-secret-0123456789abcdefghij",
        share_sign_salt="unit-test-share-salt-0123456789abcdef",
    )

    with pytest.raises(TokenError):
        decode_access_token(token, other)


def test_access_token_rejects_tampering(settings: Settings) -> None:
    token, _ = create_access_token(1001, settings, now=FIXED_NOW)
    tampered = token[:-2] + ("aa" if not token.endswith("aa") else "bb")

    with pytest.raises(TokenError):
        decode_access_token(tampered, settings)


def test_empty_token_is_rejected(settings: Settings) -> None:
    with pytest.raises(TokenError):
        decode_access_token("", settings)


def test_expired_token_is_rejected(settings: Settings) -> None:
    token, _ = create_access_token(1001, settings, now=FIXED_NOW - timedelta(days=30))

    with pytest.raises(TokenError):
        decode_access_token(token, settings, now=FIXED_NOW)


def test_decode_honours_injected_now(settings: Settings) -> None:
    """`now` 必须真正参与 exp 判定，而不是被忽略后回落到系统时间。

    构造一个「相对 FIXED_NOW 已过期」的令牌：若不注入 now，测试结果会随
    真实日历漂移；注入后与日历无关。
    """
    issued = FIXED_NOW - timedelta(minutes=settings.jwt_expire_minutes + 1)
    token, _ = create_access_token(1001, settings, now=issued)

    with pytest.raises(TokenError):
        decode_access_token(token, settings, now=FIXED_NOW)


def test_decode_accepts_token_valid_at_injected_now(settings: Settings) -> None:
    """反向用例：按注入时间仍在有效期内，应正常解出 payload。"""
    token, _ = create_access_token(1001, settings, now=FIXED_NOW)

    payload = decode_access_token(token, settings, now=FIXED_NOW + timedelta(seconds=30))

    assert payload["sub"] == "1001"


def test_share_token_roundtrip(settings: Settings) -> None:
    token, expires_at = sign_share_token(3001, settings, now=FIXED_NOW)

    assert token.startswith("v1.")
    assert expires_at == FIXED_NOW + timedelta(days=settings.share_link_ttl_days)
    assert verify_share_token(token, settings, now=FIXED_NOW) == 3001


def test_share_token_rejects_bad_signature(settings: Settings) -> None:
    token, _ = sign_share_token(3001, settings, now=FIXED_NOW)
    header, body, signature = token.split(".")
    forged = f"{header}.{body}.{'A' * len(signature)}"

    with pytest.raises(TokenError):
        verify_share_token(forged, settings, now=FIXED_NOW)


def test_share_token_rejects_other_salt(settings: Settings) -> None:
    token, _ = sign_share_token(3001, settings, now=FIXED_NOW)
    other = Settings(
        jwt_secret="unit-test-jwt-secret-0123456789abcdef",
        share_sign_salt="different-salt-0123456789abcdefghij",
    )

    with pytest.raises(TokenError):
        verify_share_token(token, other, now=FIXED_NOW)


def test_share_token_rejects_expired(settings: Settings) -> None:
    token, _ = sign_share_token(3001, settings, ttl_days=7, now=FIXED_NOW)

    with pytest.raises(TokenError):
        verify_share_token(token, settings, now=FIXED_NOW + timedelta(days=8))


@pytest.mark.parametrize("bad", ["", "v1", "v1.abc", "v2.abc.def", "v1.abc.def.ghi"])
def test_share_token_rejects_malformed(settings: Settings, bad: str) -> None:
    with pytest.raises(TokenError):
        verify_share_token(bad, settings, now=FIXED_NOW)
