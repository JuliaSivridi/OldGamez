"""add xp column to users

Revision ID: a1e8c3f07b24
Revises: b7d3f1a9c052
Create Date: 2026-05-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1e8c3f07b24"
down_revision: Union[str, None] = "b7d3f1a9c052"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("xp", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("users", "xp")
