"""add win streaks to users and user_game_streaks table

Revision ID: b7d3f1a9c052
Revises: f81c4e9d2a30
Create Date: 2026-05-20

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7d3f1a9c052"
down_revision: Union[str, None] = "f81c4e9d2a30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Cross-game streak columns on users
    op.add_column("users", sa.Column("last_win_date", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("current_win_streak", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("best_win_streak", sa.Integer(), nullable=False, server_default="0"))

    # Per-game streak table
    op.create_table(
        "user_game_streaks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("game_code", sa.String(length=50), nullable=False),
        sa.Column("last_win_date", sa.Date(), nullable=True),
        sa.Column("current_win_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("best_win_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "game_code", name="uq_user_game_streak"),
    )
    op.create_index(op.f("ix_user_game_streaks_user_id"), "user_game_streaks", ["user_id"])
    op.create_index(op.f("ix_user_game_streaks_game_code"), "user_game_streaks", ["game_code"])


def downgrade() -> None:
    op.drop_index(op.f("ix_user_game_streaks_game_code"), table_name="user_game_streaks")
    op.drop_index(op.f("ix_user_game_streaks_user_id"), table_name="user_game_streaks")
    op.drop_table("user_game_streaks")

    op.drop_column("users", "best_win_streak")
    op.drop_column("users", "current_win_streak")
    op.drop_column("users", "last_win_date")
