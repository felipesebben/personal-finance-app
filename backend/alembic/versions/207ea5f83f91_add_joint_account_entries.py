"""add joint account entries

Deposits into a joint account and balance checks (what the bank showed),
so the app can say what is left in it. A new table: nothing to backfill.

Revision ID: 207ea5f83f91
Revises: a05622de093c
Create Date: 2026-10-12 19:26:34.294122

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '207ea5f83f91'
down_revision: Union[str, Sequence[str], None] = 'a05622de093c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('fact_joint_entry',
    sa.Column('joint_entry_id', sa.Integer(), nullable=False),
    sa.Column('payment_method_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('entry_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('note', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("kind IN ('deposit', 'balance')", name='ck_joint_entry_kind'),
    sa.CheckConstraint('amount >= 0', name='ck_joint_entry_amount_not_negative'),
    sa.ForeignKeyConstraint(['payment_method_id'], ['dim_payment_method.payment_method_id'], ),
    sa.PrimaryKeyConstraint('joint_entry_id')
    )


def downgrade() -> None:
    """Downgrade schema. Recorded deposits and balance checks are lost."""
    op.drop_table('fact_joint_entry')
