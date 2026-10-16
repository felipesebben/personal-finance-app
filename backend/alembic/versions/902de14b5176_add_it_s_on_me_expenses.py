"""add it's on me expenses

fact_expenditures.is_treat: a shared expense the payer treated ("it's on
me"). It is split as usual, so it counts in each person's share, but
/balances/ never makes anyone owe for it. Existing expenses are not
treats (false).

Revision ID: 902de14b5176
Revises: 207ea5f83f91
Create Date: 2026-10-16 00:08:51.921052

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '902de14b5176'
down_revision: Union[str, Sequence[str], None] = '207ea5f83f91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default fills existing rows, so NOT NULL is safe straight away.
    op.add_column('fact_expenditures', sa.Column('is_treat', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    """Downgrade schema. Which expenses were treats is lost, so they would count as owed again."""
    op.drop_column('fact_expenditures', 'is_treat')
