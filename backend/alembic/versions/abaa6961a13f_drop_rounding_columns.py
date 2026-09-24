"""drop rounding columns

Billing is now exact (per second), so the rounding method/snapshot are gone.

Revision ID: abaa6961a13f
Revises: 7870a60e4198
Create Date: 2026-09-24 13:02:33.295871

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'abaa6961a13f'
down_revision = '7870a60e4198'
branch_labels = None
depends_on = None

ROUNDING_VALUES = ('PER_MINUTE', 'EVERY_15_MINUTES', 'EVERY_30_MINUTES', 'PER_HOUR')


def upgrade() -> None:
    op.drop_column('sessions', 'rounding_snapshot')
    op.drop_column('tariffs', 'rounding_method')
    # enum types are no longer used
    op.execute('DROP TYPE IF EXISTS rounding_snapshot')
    op.execute('DROP TYPE IF EXISTS rounding_method')


def downgrade() -> None:
    op.add_column(
        'tariffs',
        sa.Column(
            'rounding_method',
            postgresql.ENUM(*ROUNDING_VALUES, name='rounding_method'),
            nullable=False,
            server_default='EVERY_30_MINUTES',
        ),
    )
    op.add_column(
        'sessions',
        sa.Column(
            'rounding_snapshot',
            postgresql.ENUM(*ROUNDING_VALUES, name='rounding_snapshot'),
            nullable=False,
            server_default='EVERY_30_MINUTES',
        ),
    )
    op.alter_column('tariffs', 'rounding_method', server_default=None)
    op.alter_column('sessions', 'rounding_snapshot', server_default=None)
