"""add pets

A pet dimension, a per-category flag saying its expenses are for the pets,
and an optional pet on each expense: the pet it was for, or NULL for all of
them ("Both") when the category is for_pets.

Revision ID: ce97750bbc4e
Revises: 8f13ace0b19b
Create Date: 2026-10-11 19:19:21.106079

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ce97750bbc4e'
down_revision: Union[str, Sequence[str], None] = '8f13ace0b19b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('dim_pet',
    sa.Column('pet_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.PrimaryKeyConstraint('pet_id'),
    sa.UniqueConstraint('name')
    )
    # server_default fills existing rows, so NOT NULL is safe straight away.
    op.add_column('dim_category', sa.Column('for_pets', sa.Boolean(), server_default='false', nullable=False))
    # A category already called "Pets" is clearly for them.
    op.execute("UPDATE dim_category SET for_pets = true WHERE lower(primary_category) = 'pets'")
    op.add_column('fact_expenditures', sa.Column('pet_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_fact_expenditures_pet_id', 'fact_expenditures', 'dim_pet', ['pet_id'], ['pet_id'])


def downgrade() -> None:
    """Downgrade schema. Which pet each expense was for is lost."""
    op.drop_constraint('fk_fact_expenditures_pet_id', 'fact_expenditures', type_='foreignkey')
    op.drop_column('fact_expenditures', 'pet_id')
    op.drop_column('dim_category', 'for_pets')
    op.drop_table('dim_pet')
