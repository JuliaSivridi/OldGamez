"""initial schema

Revision ID: 0d7a54c2d5d9
Revises:
Create Date: 2026-05-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0d7a54c2d5d9"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("last_name", sa.String(length=255), nullable=True),
        sa.Column("language_code", sa.String(length=10), nullable=False, server_default="en"),
        sa.Column("settings", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_telegram_user_id"), "users", ["telegram_user_id"], unique=True)

    sessionmode_enum = sa.Enum("solo", "duel_private", "group_match", name="sessionmode")
    sessionstatus_enum = sa.Enum("pending", "active", "finished", "abandoned", "expired", name="sessionstatus")

    op.create_table(
        "game_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_code", sa.String(length=50), nullable=False),
        sa.Column("mode", sessionmode_enum, nullable=False),
        sa.Column("status", sessionstatus_enum, nullable=False, server_default="active"),
        sa.Column("join_code", sa.String(length=32), nullable=True),
        sa.Column("invite_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("current_turn_user_id", sa.Integer(), nullable=True),
        sa.Column("state", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("winner_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["current_turn_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["winner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("join_code"),
    )
    op.create_index(op.f("ix_game_sessions_game_code"), "game_sessions", ["game_code"])
    op.create_index(op.f("ix_game_sessions_mode"), "game_sessions", ["mode"])
    op.create_index(op.f("ix_game_sessions_status"), "game_sessions", ["status"])
    op.create_index(op.f("ix_game_sessions_join_code"), "game_sessions", ["join_code"])
    op.create_index(op.f("ix_game_sessions_telegram_chat_id"), "game_sessions", ["telegram_chat_id"])
    op.create_index(op.f("ix_game_sessions_created_by_user_id"), "game_sessions", ["created_by_user_id"])

    op.create_table(
        "session_players",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("seat_no", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["game_sessions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "user_id", name="uq_session_player"),
    )
    op.create_index(op.f("ix_session_players_session_id"), "session_players", ["session_id"])
    op.create_index(op.f("ix_session_players_user_id"), "session_players", ["user_id"])

    op.create_table(
        "game_stats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("game_code", sa.String(length=50), nullable=False),
        sa.Column("wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("losses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("draws", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("played", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "game_code", name="uq_user_game_stat"),
    )
    op.create_index(op.f("ix_game_stats_user_id"), "game_stats", ["user_id"])
    op.create_index(op.f("ix_game_stats_game_code"), "game_stats", ["game_code"])


def downgrade() -> None:
    op.drop_table("game_stats")
    op.drop_table("session_players")
    op.drop_table("game_sessions")
    op.drop_table("users")
    sa.Enum(name="sessionstatus").drop(op.get_bind())
    sa.Enum(name="sessionmode").drop(op.get_bind())
