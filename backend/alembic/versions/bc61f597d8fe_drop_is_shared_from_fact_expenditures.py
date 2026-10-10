"""drop is_shared from fact_expenditures

Contract step of retiring the flag (design note 02, decision 4). Since
PR #20 nothing reads it: whether an expense is shared is derived from
fact_expenditure_split (FactExpenditure.has_other_share).

Revision ID: bc61f597d8fe
Revises: 1962879e902d
Create Date: 2026-10-10 15:02:04.000030

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bc61f597d8fe'
down_revision: Union[str, Sequence[str], None] = '1962879e902d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column('fact_expenditures', 'is_shared')


def downgrade() -> None:
    """Downgrade schema.

    Re-adds the column in its original shape (nullable boolean) and
    rebuilds every value from the allocation rows, using the same rule as
    has_other_share, so a rollback loses nothing.
    """
    op.add_column('fact_expenditures', sa.Column('is_shared', sa.BOOLEAN(), autoincrement=False, nullable=True))
    op.execute("""
        UPDATE fact_expenditures f
        SET is_shared = EXISTS (
            SELECT 1 FROM fact_expenditure_split s
            WHERE s.expenditure_id = f.expenditure_id AND s.user_id <> f.user_id
        )
    """)
