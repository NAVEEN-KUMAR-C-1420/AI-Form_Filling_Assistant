"""Add regional entity types to entitytype enum

Revision ID: 002_add_regional
Revises: 001_initial_migration
Create Date: 2025-12-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_add_regional'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new enum values to entitytype
    op.execute("ALTER TYPE entitytype ADD VALUE IF NOT EXISTS 'full_name_regional'")
    op.execute("ALTER TYPE entitytype ADD VALUE IF NOT EXISTS 'address_regional'")


def downgrade() -> None:
    # PostgreSQL doesn't support removing enum values easily
    # This would require recreating the enum type
    pass
