"""add sub_category to category_target

A target for one sub-category (e.g. Pets › Grooming); '' is the whole primary category.

Revision ID: cb492946d6cf
Revises: 8cf90e438df9
Create Date: 2026-11-07 15:03:20.448826

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cb492946d6cf'
down_revision: Union[str, Sequence[str], None] = '8cf90e438df9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Existing targets are for whole primary categories: sub_category ''.
    op.add_column('category_target', sa.Column('sub_category', sa.String(length=255), server_default='', nullable=False))
    op.drop_constraint('category_target_pkey', 'category_target', type_='primary')
    op.create_primary_key('category_target_pkey', 'category_target', ['primary_category', 'sub_category'])


def downgrade() -> None:
    """Downgrade schema."""
    # Sub-category targets have nowhere to go in the old shape: dropped.
    op.execute("DELETE FROM category_target WHERE sub_category <> ''")
    op.drop_constraint('category_target_pkey', 'category_target', type_='primary')
    op.drop_column('category_target', 'sub_category')
    op.create_primary_key('category_target_pkey', 'category_target', ['primary_category'])
