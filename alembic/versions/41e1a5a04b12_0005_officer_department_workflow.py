"""0005_officer_department_workflow

Revision ID: 41e1a5a04b12
Revises: 31a9c1d04f21
Create Date: 2026-09-23 10:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '41e1a5a04b12'
down_revision: Union[str, Sequence[str], None] = '31a9c1d04f21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add officer department, resolution fields, complaint notes, and evidence classification."""
    # 1. Users table: department_id
    op.add_column('users', sa.Column('department_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_users_department_id_departments',
        'users',
        'departments',
        ['department_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(op.f('ix_users_department_id'), 'users', ['department_id'], unique=False)

    # 2. Complaints table: resolution fields
    op.add_column('complaints', sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('complaints', sa.Column('resolved_by_id', sa.Integer(), nullable=True))
    op.add_column('complaints', sa.Column('resolution_notes', sa.Text(), nullable=True))
    op.create_foreign_key(
        'fk_complaints_resolved_by_id_users',
        'complaints',
        'users',
        ['resolved_by_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(op.f('ix_complaints_resolved_by_id'), 'complaints', ['resolved_by_id'], unique=False)

    # 3. Complaint Notes table
    op.create_table(
        'complaint_notes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('complaint_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('note', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['complaint_id'], ['complaints.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_complaint_notes_id'), 'complaint_notes', ['id'], unique=False)
    op.create_index(op.f('ix_complaint_notes_complaint_id'), 'complaint_notes', ['complaint_id'], unique=False)
    op.create_index(op.f('ix_complaint_notes_created_at'), 'complaint_notes', ['created_at'], unique=False)
    op.create_index('ix_complaint_notes_complaint_time', 'complaint_notes', ['complaint_id', 'created_at'], unique=False)

    # 4. Evidence table: is_resolution flag
    op.add_column(
        'complaint_evidence',
        sa.Column('is_resolution', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade() -> None:
    """Downgrade schema: revert officer department, resolution, and complaint notes changes."""
    op.drop_column('complaint_evidence', 'is_resolution')

    op.drop_index('ix_complaint_notes_complaint_time', table_name='complaint_notes')
    op.drop_index(op.f('ix_complaint_notes_created_at'), table_name='complaint_notes')
    op.drop_index(op.f('ix_complaint_notes_complaint_id'), table_name='complaint_notes')
    op.drop_index(op.f('ix_complaint_notes_id'), table_name='complaint_notes')
    op.drop_table('complaint_notes')

    op.drop_constraint('fk_complaints_resolved_by_id_users', 'complaints', type_='foreignkey')
    op.drop_index(op.f('ix_complaints_resolved_by_id'), table_name='complaints')
    op.drop_column('complaints', 'resolution_notes')
    op.drop_column('complaints', 'resolved_by_id')
    op.drop_column('complaints', 'resolved_at')

    op.drop_constraint('fk_users_department_id_departments', 'users', type_='foreignkey')
    op.drop_index(op.f('ix_users_department_id'), table_name='users')
    op.drop_column('users', 'department_id')
