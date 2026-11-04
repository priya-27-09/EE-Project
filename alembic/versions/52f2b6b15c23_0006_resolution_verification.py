"""0006_resolution_verification

Revision ID: 52f2b6b15c23
Revises: 41e1a5a04b12
Create Date: 2026-09-23 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '52f2b6b15c23'
down_revision: Union[str, Sequence[str], None] = '41e1a5a04b12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create resolution_verifications table for Step 9 AI-assisted resolution evidence verification."""
    op.create_table(
        'resolution_verifications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('complaint_id', sa.Integer(), nullable=False),
        sa.Column('before_evidence_id', sa.Integer(), nullable=True),
        sa.Column('after_evidence_id', sa.Integer(), nullable=True),
        sa.Column('verification_status', sa.String(length=50), server_default='PENDING', nullable=False),
        sa.Column('verification_score', sa.Float(), nullable=True),
        sa.Column('human_review_required', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('verification_reason', sa.Text(), nullable=True),
        sa.Column('structural_similarity', sa.Float(), nullable=True),
        sa.Column('pixel_difference', sa.Float(), nullable=True),
        sa.Column('edge_similarity', sa.Float(), nullable=True),
        sa.Column('histogram_similarity', sa.Float(), nullable=True),
        sa.Column('perceptual_hash_distance', sa.Integer(), nullable=True),
        sa.Column('alignment_status', sa.String(length=50), server_default='NOT_AVAILABLE', nullable=False),
        sa.Column('algorithm_version', sa.String(length=50), server_default='resolution-v1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('reviewed_by_id', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('review_decision', sa.String(length=50), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['after_evidence_id'], ['complaint_evidence.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['before_evidence_id'], ['complaint_evidence.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['complaint_id'], ['complaints.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewed_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_index(op.f('ix_resolution_verifications_id'), 'resolution_verifications', ['id'], unique=False)
    op.create_index(op.f('ix_resolution_verifications_complaint_id'), 'resolution_verifications', ['complaint_id'], unique=False)
    op.create_index(op.f('ix_resolution_verifications_verification_status'), 'resolution_verifications', ['verification_status'], unique=False)
    op.create_index(op.f('ix_resolution_verifications_created_at'), 'resolution_verifications', ['created_at'], unique=False)
    op.create_index(
        'ix_resolution_verifications_complaint_status',
        'resolution_verifications',
        ['complaint_id', 'verification_status'],
        unique=False
    )
    op.create_index(
        'ix_resolution_verifications_complaint_time',
        'resolution_verifications',
        ['complaint_id', 'created_at'],
        unique=False
    )


def downgrade() -> None:
    """Downgrade schema: drop resolution_verifications table."""
    op.drop_index('ix_resolution_verifications_complaint_time', table_name='resolution_verifications')
    op.drop_index('ix_resolution_verifications_complaint_status', table_name='resolution_verifications')
    op.drop_index(op.f('ix_resolution_verifications_created_at'), table_name='resolution_verifications')
    op.drop_index(op.f('ix_resolution_verifications_verification_status'), table_name='resolution_verifications')
    op.drop_index(op.f('ix_resolution_verifications_complaint_id'), table_name='resolution_verifications')
    op.drop_index(op.f('ix_resolution_verifications_id'), table_name='resolution_verifications')
    op.drop_table('resolution_verifications')
