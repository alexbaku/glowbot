"""add session_id to users

Revision ID: c1d2e3f4a5b6
Revises: a1b2c3d4e5f6
Create Date: 2026-04-03

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('session_id', sa.String(36), nullable=True))
    connection = op.get_bind()
    users = connection.execute(sa.text("SELECT id FROM users"))
    for row in users:
        connection.execute(
            sa.text("UPDATE users SET session_id = :sid WHERE id = :id"),
            {"sid": str(uuid.uuid4()), "id": row.id},
        )


def downgrade() -> None:
    op.drop_column('users', 'session_id')
