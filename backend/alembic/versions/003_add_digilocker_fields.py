"""Add DigiLocker fields to users table

Revision ID: 003_add_digilocker
Revises: 002_add_regional
Create Date: 2024-01-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_add_digilocker'
down_revision: Union[str, None] = '002_add_regional'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add DigiLocker related columns to users table
    op.add_column('users', sa.Column('digilocker_access_token', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('digilocker_refresh_token', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('digilocker_id', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('digilocker_name', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('digilocker_connected_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('digilocker_token_expires_at', sa.DateTime(), nullable=True))
    
    # Add driving_license to documenttype enum
    op.execute("ALTER TYPE documenttype ADD VALUE IF NOT EXISTS 'driving_license'")


def downgrade() -> None:
    # Remove DigiLocker related columns from users table
    op.drop_column('users', 'digilocker_token_expires_at')
    op.drop_column('users', 'digilocker_connected_at')
    op.drop_column('users', 'digilocker_name')
    op.drop_column('users', 'digilocker_id')
    op.drop_column('users', 'digilocker_refresh_token')
    op.drop_column('users', 'digilocker_access_token')
    
    # Note: Cannot remove enum values in PostgreSQL without dropping and recreating the type
