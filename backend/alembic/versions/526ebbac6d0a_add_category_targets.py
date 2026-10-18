"""add category targets

A monthly target per primary category for the household's shared spending
(the dark tick on Our expenses' bullet bars). A new, empty table: nothing
to backfill.

Revision ID: 526ebbac6d0a
Revises: a75478837bac
Create Date: 2026-10-18 01:58:24.757495

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '526ebbac6d0a'
down_revision: Union[str, Sequence[str], None] = 'a75478837bac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('category_target',
    sa.Column('primary_category', sa.String(length=255), nullable=False),
    sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('amount > 0', name='ck_category_target_amount_positive'),
    sa.PrimaryKeyConstraint('primary_category')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('category_target')
