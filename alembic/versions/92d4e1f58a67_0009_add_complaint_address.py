"""add complaint address column

Revision ID: 92d4e1f58a67
Revises: 81c3d9e47f56
Create Date: 2026-10-27 12:25:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '92d4e1f58a67'
down_revision = '81c3d9e47f56'
branch_labels = None
depends_on = None


def upgrade():
    # Safely add address column to complaints table
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('complaints')]
    
    if 'address' not in existing_columns:
        op.add_column('complaints', sa.Column('address', sa.String(length=500), nullable=True))


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('complaints')]
    
    if 'address' in existing_columns:
        op.drop_column('complaints', 'address')
