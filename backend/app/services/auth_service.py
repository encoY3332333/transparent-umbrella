"""UC-01 认证服务：验证码发放、登录、偏好建档。

**验证码为什么存在进程内**：课程环境不接真实短信网关（`auth_base_url` 是占位），
验证码只是「证明这个手机号此刻归你」的一次性凭证，有效期 5 分钟，没有落库的
必要。真接网关时只需把 `_send_sms()` 换成对外调用——其余逻辑（频控、过期、
一次性作废）不变。

**频控为什么按手机号而不是 IP**：验收口径是「同一手机号 60 秒内只能请求一次」，
按 IP 会让同一间宿舍的同学互相顶掉；按手机号才对应真实用户的骚扰场景。

**登录失败次数限制**复用 config 里的 `login_max_attempts` / `login_lock_minutes`：
连续输错达到上限后锁定一段时间，防止有人对着一个手机号穷举 6 位数字。
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import BusinessError, ErrorCode, FieldError
from app.models.tourist import MAX_PREFERENCE_TAGS, Tourist

logger = logging.getLogger(__name__)

# 验证码有效期与频控间隔（BR-03 家族口径，写死常量而不是配置项：
# 这两个数值是验收标准里点名的，改动要走需求变更而不是改环境变量）
CODE_TTL_SECONDS = 300
CODE_RETRY_SECONDS = 60
CODE_LENGTH = 6


@dataclass
class _CodeEntry:
    code: str
    expires_at: datetime
    sent_at: datetime


# 进程内存储：{手机号: 验证码记录}
_codes: dict[str, _CodeEntry] = {}
# 登录失败计数：{手机号: (次数, 首次失败时间)}
_failures: dict[str, tuple[int, datetime]] = {}


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(UTC)


def reset_state() -> None:
    """清空进程内状态。测试用——不提供 HTTP 入口，避免被当成后门。"""
    _codes.clear()
    _failures.clear()


def _send_sms(phone: str, code: str) -> None:
    """对接短信网关的占位实现。

    真实实现应调用 `settings.auth_base_url`，失败时抛
    `AUTH_SERVICE_UNAVAILABLE` 而不是静默成功——「短信没发出去但用户以为发了」
    会让登录流程卡在无解状态。
    """
    logger.info("sms code issued for %s (demo mode, code not printed)", phone[-4:].rjust(4, "*"))


def request_code(
    session: Session, settings: Settings, phone: str, *, now: datetime | None = None
) -> tuple[int, str | None]:
    """发放验证码。

    返回 `(有效期秒数, 调试用验证码或 None)`。非生产环境把验证码回给前端，
    是为了让演示和自动化测试不依赖真实短信；生产环境返回 None。
    """
    current = _now(now)
    previous = _codes.get(phone)
    if previous is not None:
        elapsed = (current - previous.sent_at).total_seconds()
        if elapsed < CODE_RETRY_SECONDS:
            raise BusinessError(
                ErrorCode.SMS_SEND_TOO_FREQUENT,
                details=[
                    FieldError(
                        "phone",
                        f"同一手机号 {CODE_RETRY_SECONDS} 秒内只能请求一次，请 {int(CODE_RETRY_SECONDS - elapsed)} 秒后重试",
                    )
                ],
            )

    code = f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"
    _codes[phone] = _CodeEntry(
        code=code,
        expires_at=current + timedelta(seconds=CODE_TTL_SECONDS),
        sent_at=current,
    )
    _send_sms(phone, code)
    debug = None if settings.is_production else code
    return CODE_TTL_SECONDS, debug


def _check_locked(phone: str, settings: Settings, current: datetime) -> None:
    """检查是否因连续失败被锁定。"""
    record = _failures.get(phone)
    if record is None:
        return
    count, first_at = record
    if count < settings.login_max_attempts:
        return
    unlock_at = first_at + timedelta(minutes=settings.login_lock_minutes)
    if current >= unlock_at:
        _failures.pop(phone, None)
        return
    raise BusinessError(
        ErrorCode.RATE_LIMITED,
        message=f"登录失败次数过多，请 {settings.login_lock_minutes} 分钟后再试",
    )


def _record_failure(phone: str, settings: Settings, current: datetime) -> None:
    record = _failures.get(phone)
    if record is None:
        _failures[phone] = (1, current)
        return
    count, first_at = record
    # 锁定窗口已过，重新计数
    if current >= first_at + timedelta(minutes=settings.login_lock_minutes):
        _failures[phone] = (1, current)
        return
    _failures[phone] = (count + 1, first_at)


def verify_code(phone: str, code: str, *, now: datetime | None = None) -> None:
    """校验验证码。成功即作废（一次性），失败也作废过期记录。"""
    current = _now(now)
    entry = _codes.get(phone)
    if entry is None:
        raise BusinessError(ErrorCode.SMS_CODE_INVALID, message="请先获取验证码")
    if current >= entry.expires_at:
        _codes.pop(phone, None)
        raise BusinessError(ErrorCode.SMS_CODE_EXPIRED)
    if not secrets.compare_digest(entry.code, code):
        raise BusinessError(ErrorCode.SMS_CODE_INVALID)


def login(
    session: Session,
    settings: Settings,
    phone: str,
    code: str,
    *,
    now: datetime | None = None,
) -> Tourist:
    """验证码登录：校验 → 锁定检查 → 取或建账号 → 记录登录时间。

    首次登录即注册（`get_or_create`），不额外做「注册」流程——UC-01 的游客
    本来就是低门槛身份，多一步注册只会增加流失。
    """
    current = _now(now)
    _check_locked(phone, settings, current)

    try:
        verify_code(phone, code, now=current)
    except BusinessError:
        _record_failure(phone, settings, current)
        raise

    _failures.pop(phone, None)
    _codes.pop(phone, None)

    tourist = session.scalar(select(Tourist).where(Tourist.phone == phone))
    if tourist is None:
        tourist = Tourist(phone=phone, nickname=f"游客{phone[-4:]}")
        session.add(tourist)
        session.flush()
    tourist.last_login_at = current
    session.commit()
    return tourist


def save_preferences(
    session: Session,
    tourist: Tourist,
    *,
    tags: list[str],
    party_type: str,
    pace: str,
    budget_level: str,
    now: datetime | None = None,
) -> Tourist:
    """保存偏好档案（tags / partyType / pace / budgetLevel 四件套）。

    标签上限与 UC-02 的 `preferenceTags` 用同一个数（6）和同一个错误码，
    否则用户会在两个入口遇到两套规则。
    """
    cleaned: list[str] = []
    for tag in tags:
        item = tag.strip()
        # 去空、去重但保序：前端多选控件容易把同一个标签重复提交，
        # 直接报错对用户不友好，静默去重更合理。
        if item and item not in cleaned:
            cleaned.append(item)
    if len(cleaned) > MAX_PREFERENCE_TAGS:
        raise BusinessError(
            ErrorCode.CONDITION_TOO_MANY_TAGS,
            details=[FieldError("preferenceTags", f"最多选择 {MAX_PREFERENCE_TAGS} 个偏好标签")],
        )
    tourist.preference_tags = cleaned
    tourist.party_type = party_type
    tourist.pace = pace
    tourist.budget_level = budget_level
    tourist.preference_saved_at = _now(now)
    session.commit()
    return tourist
