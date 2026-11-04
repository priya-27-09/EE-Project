"""0004_add_multilingual_fields

Revision ID: 31a9c1d04f21
Revises: 23b8bb733ca4
Create Date: 2026-09-22 21:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '31a9c1d04f21'
down_revision: Union[str, Sequence[str], None] = '23b8bb733ca4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add multilingual fields to complaints table."""
    op.add_column('complaints', sa.Column('original_text', sa.Text(), nullable=True))
    op.add_column('complaints', sa.Column('translated_text', sa.Text(), nullable=True))
    # Backfill original_text from description for existing complaints
    op.execute("UPDATE complaints SET original_text = description WHERE original_text IS NULL")


def downgrade() -> None:
    """Downgrade schema: remove multilingual fields from complaints table."""
    op.drop_column('complaints', 'translated_text')
    op.drop_column('complaints', 'original_text')
