"""游客 / 用户模型（Issue #2 / UC-01）。

只落一件事：**谁在规划行程**。业务上游客可以不登录就生成行程（BR-03），
登录的意义是「能保存、能再来」——所以 `preference_tags` 才是这张表的核心字段，
它让下次规划不必重填偏好（问卷 Q3：56.2% 用户规划耗时超 2 小时，重复填写
是流失点）。

手机号是唯一登录标识：`phone` 上加唯一约束，避免同一手机号注册出两个账号。
不存验证码——验证码是短时效凭证，落在进程内的 `auth_service` 里，不落库。
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def _utcnow() -> datetime:
    """带时区的 UTC 时间，理由同 models/itinerary.py。"""
    return datetime.now(UTC)


# UC-02 已定的口径：偏好标签最多 6 个。这里再定义一次是为了让模型层能独立
# 校验（service 从请求进、模型从库里出，两条路径都要守住同一个上限）。
MAX_PREFERENCE_TAGS = 6


class Tourist(Base):
    """登录游客。"""

    __tablename__ = "tourist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 手机号：登录唯一标识。不加索引名，靠 unique 隐式建索引。
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nickname: Mapped[str] = mapped_column(String(40), nullable=False, default="游客")

    # 偏好标签存 JSON 文本（如 `["人文历史","美食"]`）：条数不固定、只整块读写，
    # 拆表收益不大；与 itinerary.reasons_json 的处理方式保持一致。
    preference_tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    # 偏好三件套（docs/api.md 1.3/1.4 的字段）。用带默认值的字符串而不是 ENUM：
    # 取值集合由 service 层枚举守住，库里加值不需要 ALTER TABLE。
    party_type: Mapped[str] = mapped_column(String(16), nullable=False, default="SOLO")
    pace: Mapped[str] = mapped_column(String(16), nullable=False, default="MODERATE")
    budget_level: Mapped[str] = mapped_column(String(16), nullable=False, default="COMFORT")

    # 「是否建过档」单独记时间，而不是拿 updated_at 判断：
    # 登录本身也会刷 updated_at，用它会让「只登录没建档」的用户被误判成已建档。
    preference_saved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    # 登录时间用于「多久没回来」这类运营口径，也便于排查登录异常。
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    @property
    def has_preference(self) -> bool:
        """是否已建档。前端据此决定要不要弹偏好浮层（docs/api.md 1.2）。"""
        return self.preference_saved_at is not None

    @property
    def preference_tags(self) -> list[str]:
        """把 JSON 文本解析成列表。坏数据（空串 / 非列表）一律当空，不抛异常。

        库里可能因为历史数据或手工改库出现不合法的 JSON；在这种情况下让整个
        「我的偏好」接口 500 是不可接受的，降级成空列表更合理。
        """
        import json

        try:
            value = json.loads(self.preference_tags_json or "[]")
        except ValueError:
            return []
        return [str(item) for item in value] if isinstance(value, list) else []

    @preference_tags.setter
    def preference_tags(self, tags: list[str]) -> None:
        import json

        self.preference_tags_json = json.dumps(list(tags), ensure_ascii=False)

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<Tourist id={self.id} phone={self.phone!r}>"
