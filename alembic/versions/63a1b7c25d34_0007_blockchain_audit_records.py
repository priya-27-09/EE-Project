"""0007_blockchain_audit_records

Revision ID: 63a1b7c25d34
Revises: 52f2b6b15c23
Create Date: 2026-09-23 11:44:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '63a1b7c25d34'
down_revision: Union[str, None] = '52f2b6b15c23'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'blockchain_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('complaint_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('event_hash', sa.String(length=66), nullable=False),
        sa.Column('data_hash', sa.String(length=66), nullable=False),
        sa.Column('canonical_payload', sa.JSON(), nullable=True),
        sa.Column('blockchain_network', sa.String(length=64), server_default='Ganache', nullable=False),
        sa.Column('chain_id', sa.Integer(), nullable=True),
        sa.Column('contract_address', sa.String(length=64), nullable=True),
        sa.Column('transaction_hash', sa.String(length=66), nullable=True),
        sa.Column('block_number', sa.BigInteger(), nullable=True),
        sa.Column('blockchain_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=32), server_default='PENDING', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['complaint_id'], ['complaints.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_blockchain_records_id'), 'blockchain_records', ['id'], unique=False)
    op.create_index(op.f('ix_blockchain_records_complaint_id'), 'blockchain_records', ['complaint_id'], unique=False)
    op.create_index(op.f('ix_blockchain_records_event_type'), 'blockchain_records', ['event_type'], unique=False)
    op.create_index(op.f('ix_blockchain_records_event_hash'), 'blockchain_records', ['event_hash'], unique=False)
    op.create_index(op.f('ix_blockchain_records_transaction_hash'), 'blockchain_records', ['transaction_hash'], unique=False)
    op.create_index(op.f('ix_blockchain_records_status'), 'blockchain_records', ['status'], unique=False)
    op.create_index(op.f('ix_blockchain_records_created_at'), 'blockchain_records', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_blockchain_records_created_at'), table_name='blockchain_records')
    op.drop_index(op.f('ix_blockchain_records_status'), table_name='blockchain_records')
    op.drop_index(op.f('ix_blockchain_records_transaction_hash'), table_name='blockchain_records')
    op.drop_index(op.f('ix_blockchain_records_event_hash'), table_name='blockchain_records')
    op.drop_index(op.f('ix_blockchain_records_event_type'), table_name='blockchain_records')
    op.drop_index(op.f('ix_blockchain_records_complaint_id'), table_name='blockchain_records')
    op.drop_index(op.f('ix_blockchain_records_id'), table_name='blockchain_records')
    op.drop_table('blockchain_records')
