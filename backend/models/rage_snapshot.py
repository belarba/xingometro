from datetime import datetime

from sqlalchemy import Integer, Float, Text, JSON, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.database import Base


class RageSnapshot(Base):
    __tablename__ = "rage_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    match_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("matches.id"), nullable=True)
    round: Mapped[int | None] = mapped_column(Integer, nullable=True)
    period: Mapped[str] = mapped_column(Text, nullable=False)
    post_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_rage_score: Mapped[float] = mapped_column(Float, default=0.0)
    max_rage_score: Mapped[float] = mapped_column(Float, default=0.0)
    top_swear_words: Mapped[dict] = mapped_column(JSON, default=dict)
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
