"""Add pdf_data column to documents table

Revision ID: 001
Revises:
Create Date: 2026-03-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("pdf_data", sa.LargeBinary(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("documents", "pdf_data")
