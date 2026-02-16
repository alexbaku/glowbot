"""rewrite_two_table_schema

Revision ID: f3873f52e3ce
Revises: 07571212fdf0
Create Date: 2026-02-16 14:48:48.241616

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f3873f52e3ce'
down_revision: Union[str, None] = '07571212fdf0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # 1. Drop old child tables first (they have FK deps on parent tables)
    #    Order: leaf tables → parent tables
    for table in [
        'messages',         # FK → conversations
        'conversations',    # FK → users
        'allergies',        # FK → user_health_info
        'medications',      # FK → user_health_info
        'sensitivities',    # FK → user_health_info
        'user_health_info', # FK → users
        'skin_concerns',    # FK → users
        'user_preferences', # FK → users
        'user_routines',    # FK → users
    ]:
        if table in existing_tables:
            op.drop_table(table)

    # 2. Create message_log if it doesn't already exist (init_db may have created it)
    if 'message_log' not in existing_tables:
        op.create_table('message_log',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('role', postgresql.ENUM('USER', 'ASSISTANT', name='messagerole', create_type=False), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('media_url', sa.String(length=500), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_message_log_id'), 'message_log', ['id'], unique=False)
        op.create_index(op.f('ix_message_log_user_id'), 'message_log', ['user_id'], unique=False)

    # 3. Add new columns to users (skip if already present from init_db)
    existing_columns = {c['name'] for c in inspector.get_columns('users')}

    if 'profile_json' not in existing_columns:
        op.add_column('users', sa.Column('profile_json', sa.JSON(), nullable=True))
    if 'conversation_phase' not in existing_columns:
        op.add_column('users', sa.Column('conversation_phase', sa.String(length=20), nullable=True))
    if 'message_history_json' not in existing_columns:
        op.add_column('users', sa.Column('message_history_json', sa.JSON(), nullable=True))

    # 4. Drop old columns from users (skip if already gone)
    for col in ['language', 'sun_exposure', 'age_verified', 'skin_type', 'budget_range']:
        if col in existing_columns:
            op.drop_column('users', col)

    # 5. Clean up orphaned enum types
    op.execute("DROP TYPE IF EXISTS conversationstate")
    op.execute("DROP TYPE IF EXISTS routinetime")
    op.execute("DROP TYPE IF EXISTS routinestep")
    op.execute("DROP TYPE IF EXISTS skintype")
    op.execute("DROP TYPE IF EXISTS sunexposure")


def downgrade() -> None:
    op.add_column('users', sa.Column('budget_range', sa.VARCHAR(length=50), autoincrement=False, nullable=True))
    op.add_column('users', sa.Column('skin_type', postgresql.ENUM('DRY', 'OILY', 'COMBINATION', 'NORMAL', 'SENSITIVE', 'UNKNOWN', name='skintype'), autoincrement=False, nullable=True))
    op.add_column('users', sa.Column('age_verified', sa.BOOLEAN(), autoincrement=False, nullable=True))
    op.add_column('users', sa.Column('sun_exposure', postgresql.ENUM('MINIMAL', 'MODERATE', 'HIGH', name='sunexposure'), autoincrement=False, nullable=True))
    op.add_column('users', sa.Column('language', sa.VARCHAR(length=10), autoincrement=False, nullable=True))
    op.drop_column('users', 'message_history_json')
    op.drop_column('users', 'conversation_phase')
    op.drop_column('users', 'profile_json')
    op.create_table('user_health_info',
        sa.Column('user_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('is_pregnant', sa.BOOLEAN(), autoincrement=False, nullable=True),
        sa.Column('is_nursing', sa.BOOLEAN(), autoincrement=False, nullable=True),
        sa.Column('planning_pregnancy', sa.BOOLEAN(), autoincrement=False, nullable=True),
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='user_health_info_user_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='user_health_info_pkey'),
        sa.UniqueConstraint('user_id', name='user_health_info_user_id_key'),
    )
    op.create_table('allergies',
        sa.Column('health_info_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('allergen', sa.VARCHAR(length=200), autoincrement=False, nullable=False),
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(['health_info_id'], ['user_health_info.id'], name='allergies_health_info_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='allergies_pkey')
    )
    op.create_table('medications',
        sa.Column('health_info_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('name', sa.VARCHAR(length=200), autoincrement=False, nullable=False),
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(['health_info_id'], ['user_health_info.id'], name='medications_health_info_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='medications_pkey')
    )
    op.create_table('sensitivities',
        sa.Column('health_info_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('sensitivity', sa.VARCHAR(length=200), autoincrement=False, nullable=False),
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(['health_info_id'], ['user_health_info.id'], name='sensitivities_health_info_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='sensitivities_pkey')
    )
    op.create_table('skin_concerns',
        sa.Column('user_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('concern', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='skin_concerns_user_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='skin_concerns_pkey')
    )
    op.create_table('user_preferences',
        sa.Column('user_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('preference', sa.VARCHAR(length=100), autoincrement=False, nullable=False),
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='user_preferences_user_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='user_preferences_pkey')
    )
    op.create_table('user_routines',
        sa.Column('user_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('time_of_day', postgresql.ENUM('MORNING', 'EVENING', name='routinetime'), autoincrement=False, nullable=False),
        sa.Column('step', postgresql.ENUM('CLEANSER', 'TREATMENT', 'MOISTURIZER', 'SUNSCREEN', 'MAKEUP_REMOVAL', name='routinestep'), autoincrement=False, nullable=False),
        sa.Column('product', sa.VARCHAR(length=200), autoincrement=False, nullable=True),
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='user_routines_user_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='user_routines_pkey')
    )
    op.create_table('conversations',
        sa.Column('user_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('state', postgresql.ENUM('GREETING', 'AGE_VERIFICATION', 'SKIN_TYPE', 'SKIN_CONCERNS', 'HEALTH_CHECK', 'SUN_EXPOSURE', 'CURRENT_ROUTINE', 'PRODUCT_PREFERENCES', 'SUMMARY', 'COMPLETE', name='conversationstate'), autoincrement=False, nullable=False),
        sa.Column('context', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=True),
        sa.Column('is_active', sa.BOOLEAN(), autoincrement=False, nullable=True),
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='conversations_user_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='conversations_pkey'),
    )
    op.create_table('messages',
        sa.Column('conversation_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('role', postgresql.ENUM('USER', 'ASSISTANT', 'SYSTEM', name='messagerole'), autoincrement=False, nullable=False),
        sa.Column('content', sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column('media_url', sa.VARCHAR(length=500), autoincrement=False, nullable=True),
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], name='messages_conversation_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='messages_pkey')
    )
    op.drop_index(op.f('ix_message_log_user_id'), table_name='message_log')
    op.drop_index(op.f('ix_message_log_id'), table_name='message_log')
    op.drop_table('message_log')
