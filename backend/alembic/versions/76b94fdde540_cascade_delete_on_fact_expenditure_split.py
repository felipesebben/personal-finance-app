"""cascade delete on fact_expenditure_split

Revision ID: 76b94fdde540
Revises: c733614c3aa4
Create Date: 2026-08-29 20:39:53.071461

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '76b94fdde540'
down_revision: Union[str, Sequence[str], None] = 'c733614c3aa4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(
        "fact_expenditure_split_expenditure_id_fkey",
        "fact_expenditure_split",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fact_expenditure_split_expenditure_id_fkey",
        "fact_expenditure_split",
        "fact_expenditures",
        ["expenditure_id"],
        ["expenditure_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fact_expenditure_split_expenditure_id_fkey",
        "fact_expenditure_split",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fact_expenditure_split_expenditure_id_fkey",
        "fact_expenditure_split",
        "fact_expenditures",
        ["expenditure_id"],
        ["expenditure_id"],
    )