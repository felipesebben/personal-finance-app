"""add password_reset_token table

Revision ID: 8f13ace0b19b
Revises: bc61f597d8fe
Create Date: 2026-10-10 20:43:06.812501

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f13ace0b19b'
down_revision: Union[str, Sequence[str], None] = 'bc61f597d8fe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # One row per reset link. Only the SHA-256 hex of the token is stored;
    # rows go with their user (ON DELETE CASCADE).
    op.create_table('password_reset_token',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['dim_user.user_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash', name='uq_password_reset_token_hash')
    )
    op.create_index(op.f('ix_password_reset_token_user_id'), 'password_reset_token', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_password_reset_token_user_id'), table_name='password_reset_token')
    op.drop_table('password_reset_token')
