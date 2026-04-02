from sqlalchemy import Boolean, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Voice(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "voices"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(10), nullable=False)
    reference_audio_path: Mapped[str] = mapped_column(String(500), nullable=False)
    reference_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_duration_sec: Mapped[float] = mapped_column(Float, nullable=False)
    moss_compatible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    qwen_compatible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    moss_cached_data: Mapped[str | None] = mapped_column(String(500), nullable=True)
    qwen_cached_data: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
