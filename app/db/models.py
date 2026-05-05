from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, BigInteger, DateTime, Enum as SqlEnum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SessionMode(str, Enum):
    solo = "solo"
    duel_private = "duel_private"
    group_match = "group_match"


class SessionStatus(str, Enum):
    active = "active"
    finished = "finished"
    abandoned = "abandoned"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language_code: Mapped[str] = mapped_column(String(10), default="ru")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sessions_created: Mapped[list[GameSession]] = relationship(
        back_populates="created_by",
        foreign_keys="GameSession.created_by_user_id",
    )


class GameSession(Base):
    __tablename__ = "game_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_code: Mapped[str] = mapped_column(String(50), index=True)
    mode: Mapped[SessionMode] = mapped_column(SqlEnum(SessionMode), index=True)
    status: Mapped[SessionStatus] = mapped_column(SqlEnum(SessionStatus), default=SessionStatus.active, index=True)
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    current_turn_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    state: Mapped[dict] = mapped_column(JSON, default=dict)
    winner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_by: Mapped[User] = relationship(
        back_populates="sessions_created",
        foreign_keys=[created_by_user_id],
    )
    players: Mapped[list[SessionPlayer]] = relationship(back_populates="session", cascade="all, delete-orphan")


class SessionPlayer(Base):
    __tablename__ = "session_players"
    __table_args__ = (UniqueConstraint("session_id", "user_id", name="uq_session_player"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("game_sessions.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    seat_no: Mapped[int] = mapped_column(Integer)
    role: Mapped[str | None] = mapped_column(String(50), nullable=True)

    session: Mapped[GameSession] = relationship(back_populates="players")


class GameStat(Base):
    __tablename__ = "game_stats"
    __table_args__ = (UniqueConstraint("user_id", "game_code", name="uq_user_game_stat"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    game_code: Mapped[str] = mapped_column(String(50), index=True)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    draws: Mapped[int] = mapped_column(Integer, default=0)
    played: Mapped[int] = mapped_column(Integer, default=0)

