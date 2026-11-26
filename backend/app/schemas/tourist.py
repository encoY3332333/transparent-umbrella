"""UC-01 游客登录与偏好建档的请求 / 响应模型。

字段名严格对齐 `docs/api.md` 第 1 章，不在这里另起一套命名。
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

# 中国大陆手机号：11 位、1 开头。演示环境不做号段校验，只挡明显不是手机号的输入。
_PHONE_LEN = 11


class Pace(StrEnum):
    """游玩节奏，对应 docs/api.md 1.3 的 `pace`。"""

    TIGHT = "TIGHT"
    MODERATE = "MODERATE"
    RELAXED = "RELAXED"


class BudgetLevel(StrEnum):
    """预算档位，对应 docs/api.md 1.3 的 `budgetLevel`。"""

    ECONOMY = "ECONOMY"
    COMFORT = "COMFORT"
    QUALITY = "QUALITY"


def _validate_phone(value: str) -> str:
    value = value.strip()
    if not value.isdigit() or len(value) != _PHONE_LEN or not value.startswith("1"):
        raise ValueError("手机号须为 11 位数字")
    return value


class SmsCodeIn(BaseModel):
    """请求验证码。"""

    phone: str = Field(min_length=1, max_length=20)

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, value: str) -> str:
        return _validate_phone(value)


class LoginIn(SmsCodeIn):
    """验证码登录。

    验证码字段同时接受 `code` 和 docs/api.md 写的 `smsCode`：文档先定的是
    `smsCode`，代码里用 `code` 更短，两者都支持可以避免前端照文档写完再返工。
    """

    code: str = Field(
        min_length=4,
        max_length=6,
        validation_alias=AliasChoices("code", "smsCode"),
    )


class SmsCodeOut(BaseModel):
    """验证码发放结果。

    `debugCode` 只在非生产环境返回，让课程演示与自动化测试不必真接短信网关；
    生产环境必须为 None——它等价于把验证码印在响应里。
    """

    expiresIn: int
    retryAfter: int
    debugCode: str | None = None


def mask_phone(phone: str) -> str:
    """`13800138000` → `138****8000`。

    响应里不做脱敏等于把用户手机号打进浏览器控制台和日志，课程项目也不该这么干。
    """
    if len(phone) < 7:
        return "***"
    return f"{phone[:3]}****{phone[-4:]}"


class TouristOut(BaseModel):
    """当前登录游客（docs/api.md 1.2 响应里的 `tourist`）。"""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    phone: str
    nickname: str
    hasPreference: bool = False

    @classmethod
    def from_model(cls, tourist) -> TouristOut:
        return cls(
            id=tourist.id,
            phone=mask_phone(tourist.phone),
            nickname=tourist.nickname,
            hasPreference=tourist.has_preference,
        )


class PreferenceIn(BaseModel):
    """偏好建档请求（docs/api.md 1.4）。"""

    preferenceTags: list[str] = Field(default_factory=list)
    partyType: str = "SOLO"
    pace: Pace = Pace.MODERATE
    budgetLevel: BudgetLevel = BudgetLevel.COMFORT

    @field_validator("partyType")
    @classmethod
    def _check_party_type(cls, value: str) -> str:
        allowed = {"SOLO", "COUPLE", "FAMILY", "FRIENDS"}
        if value not in allowed:
            raise ValueError(f"partyType 取值须为 {'/'.join(sorted(allowed))}")
        return value


class PreferenceOut(BaseModel):
    """偏好档案响应（docs/api.md 1.3/1.4 的 `data`）。"""

    id: int
    preferenceTags: list[str] = Field(default_factory=list)
    partyType: str
    pace: str
    budgetLevel: str
    updatedAt: datetime

    @classmethod
    def from_model(cls, tourist) -> PreferenceOut:
        return cls(
            id=tourist.id,
            preferenceTags=tourist.preference_tags,
            partyType=tourist.party_type,
            pace=tourist.pace,
            budgetLevel=tourist.budget_level,
            updatedAt=tourist.preference_saved_at or tourist.created_at,
        )


class LoginOut(BaseModel):
    """登录成功后的响应体。

    token 本体走 HttpOnly Cookie（ADR-001），**不在**响应体里回传——
    回传就等于绕过了 HttpOnly 的全部意义。
    """

    tourist: TouristOut
    expiresIn: int
