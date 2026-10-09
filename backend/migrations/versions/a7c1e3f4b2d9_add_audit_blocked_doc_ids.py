"""add audit_logs.blocked_doc_ids

Revision ID: a7c1e3f4b2d9
Revises: 096c1a8da9f7
Create Date: 2026-10-03 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a7c1e3f4b2d9'
down_revision: Union[str, None] = '096c1a8da9f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('audit_logs', sa.Column('blocked_doc_ids', postgresql.ARRAY(sa.String()), nullable=True))


def downgrade() -> None:
    op.drop_column('audit_logs', 'blocked_doc_ids')
