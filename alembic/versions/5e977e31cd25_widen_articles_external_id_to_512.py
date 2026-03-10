"""widen articles external_id to 512

Revision ID: 5e977e31cd25
Revises: e55d5784cbfc
Create Date: 2026-03-09 20:09:01.302476

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5e977e31cd25"
down_revision: Union[str, Sequence[str], None] = "e55d5784cbfc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "articles",
        "external_id",
        existing_type=sa.String(length=128),
        type_=sa.String(length=512),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "articles",
        "external_id",
        existing_type=sa.String(length=512),
        type_=sa.String(length=128),
        existing_nullable=False,
    )
