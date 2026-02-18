"""add routine_json to users

Revision ID: a1b2c3d4e5f6
Revises: f3873f52e3ce
Create Date: 2026-02-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f3873f52e3ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('routine_json', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'routine_json')
