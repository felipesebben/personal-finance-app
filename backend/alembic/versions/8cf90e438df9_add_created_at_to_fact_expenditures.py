"""add created_at to fact_expenditures

When an expense was logged, apart from the day it is for; NULL on older rows.

Revision ID: 8cf90e438df9
Revises: 526ebbac6d0a
Create Date: 2026-11-07 14:56:08.291415

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8cf90e438df9'
down_revision: Union[str, Sequence[str], None] = '526ebbac6d0a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Added without a default first, so existing rows stay NULL ("logged
    # before we kept track") instead of all getting the migration's time;
    # only then do new rows get now().
    op.add_column('fact_expenditures', sa.Column('created_at', sa.DateTime(timezone=True), nullable=True))
    op.alter_column('fact_expenditures', 'created_at', server_default=sa.text('now()'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('fact_expenditures', 'created_at')
