from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, Float, Text, JSON, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.database import Base


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    author_handle: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id"), nullable=True)
    coach_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("coaches.id"), nullable=True)
    match_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("matches.id"), nullable=True)
    reply_to_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rage_score: Mapped[float] = mapped_column(Float, default=0.0)
    swear_words: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
