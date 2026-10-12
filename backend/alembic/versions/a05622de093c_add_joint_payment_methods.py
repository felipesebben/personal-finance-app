"""add joint payment methods

A payment method can be a joint account: one both people top up in
advance (e.g. a shared Nubank debit card for groceries). What it pays for
is already settled between them, so /balances/ treats each person as
having paid their own share. Existing methods are personal (false).

Revision ID: a05622de093c
Revises: ce97750bbc4e
Create Date: 2026-10-12 14:39:33.398701

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a05622de093c'
down_revision: Union[str, Sequence[str], None] = 'ce97750bbc4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default fills existing rows, so NOT NULL is safe straight away.
    op.add_column('dim_payment_method', sa.Column('is_joint', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    """Downgrade schema. Which methods were joint is lost."""
    op.drop_column('dim_payment_method', 'is_joint')
