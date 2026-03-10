"""widen evaluations article_id to 256

Revision ID: e55d5784cbfc
Revises: ab1d2e193ba4
Create Date: 2026-03-09 19:43:41.480852

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e55d5784cbfc"
down_revision: Union[str, Sequence[str], None] = "ab1d2e193ba4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "evaluations",
        "article_id",
        existing_type=sa.String(length=64),
        type_=sa.String(length=256),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "evaluations",
        "article_id",
        existing_type=sa.String(length=256),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
