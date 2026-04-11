"""add_outreach_content_column

Revision ID: 7606ba12673b
Revises: 9f21df31cf47
Create Date: 2026-04-10 17:33:32.972083

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7606ba12673b'
down_revision: Union[str, Sequence[str], None] = '9f21df31cf47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("outreach_sequences", sa.Column("content", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("outreach_sequences", "content")
