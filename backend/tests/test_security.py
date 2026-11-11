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
