"""game_stats: add variant_key and best_score

Revision ID: f81c4e9d2a30
Revises: c4f2a8b0e691
Create Date: 2026-05-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f81c4e9d2a30"
down_revision: Union[str, None] = "c4f2a8b0e691"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(op.f("ix_game_stats_game_code"), table_name="game_stats")
    op.drop_index(op.f("ix_game_stats_user_id"), table_name="game_stats")
    op.drop_table("game_stats")

    op.create_table(
        "game_stats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("game_code", sa.String(length=50), nullable=False),
        sa.Column("variant_key", sa.String(length=20), nullable=False, server_default="default"),
        sa.Column("played", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("losses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("draws", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("best_score", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "game_code", "variant_key", name="uq_user_game_variant"),
    )
    op.create_index(op.f("ix_game_stats_user_id"), "game_stats", ["user_id"])
    op.create_index(op.f("ix_game_stats_game_code"), "game_stats", ["game_code"])


def downgrade() -> None:
    op.drop_index(op.f("ix_game_stats_game_code"), table_name="game_stats")
    op.drop_index(op.f("ix_game_stats_user_id"), table_name="game_stats")
    op.drop_table("game_stats")

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
