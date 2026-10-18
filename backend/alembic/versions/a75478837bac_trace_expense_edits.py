"""trace expense edits

When and by whom an expense was last edited. Both columns are nullable
and need no backfill: NULL means never edited since it was logged.
Deleting the editor's account keeps the time and forgets who (SET NULL).

Revision ID: a75478837bac
Revises: 902de14b5176
Create Date: 2026-10-17 21:57:42.187397

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a75478837bac'
down_revision: Union[str, Sequence[str], None] = '902de14b5176'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('fact_expenditures', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('fact_expenditures', sa.Column('updated_by_user_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_fact_expenditures_updated_by', 'fact_expenditures', 'dim_user', ['updated_by_user_id'], ['user_id'], ondelete='SET NULL')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_fact_expenditures_updated_by', 'fact_expenditures', type_='foreignkey')
    op.drop_column('fact_expenditures', 'updated_by_user_id')
    op.drop_column('fact_expenditures', 'updated_at')
