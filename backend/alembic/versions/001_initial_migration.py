"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table('users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('phone_number', sa.String(15), nullable=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_verified', sa.Boolean(), default=False),
        sa.Column('is_superuser', sa.Boolean(), default=False),
        sa.Column('failed_login_attempts', sa.String(5), default='0'),
        sa.Column('locked_until', sa.DateTime(), nullable=True),
        sa.Column('two_factor_enabled', sa.Boolean(), default=False),
        sa.Column('two_factor_secret', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), default=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_phone_number'), 'users', ['phone_number'], unique=True)

    # Create documents table
    op.create_table('documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_type', sa.Enum('aadhaar', 'pan', 'voter_id', 'ration_card', 
                                           'community_certificate', 'income_certificate', 'other',
                                           name='documenttype'), nullable=False),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('file_hash', sa.String(64), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=False),
        sa.Column('file_size_bytes', sa.String(20), nullable=False),
        sa.Column('status', sa.Enum('uploaded', 'processing', 'extracted', 'confirmed', 'failed',
                                    name='documentstatus'), default='uploaded'),
        sa.Column('detected_language', sa.String(50), nullable=True),
        sa.Column('ocr_confidence', sa.String(10), nullable=True),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), default=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_documents_user_id'), 'documents', ['user_id'], unique=False)

    # Create extracted_entities table
    op.create_table('extracted_entities',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entity_type', sa.Enum('full_name', 'date_of_birth', 'gender', 'address',
                                         'aadhaar_number', 'pan_number', 'voter_id_number',
                                         'ration_card_number', 'community', 'annual_income',
                                         'certificate_issue_date', 'father_name', 'mother_name',
                                         'spouse_name', name='entitytype'), nullable=False),
        sa.Column('encrypted_value', sa.Text(), nullable=False),
        sa.Column('original_language', sa.String(50), nullable=True),
        sa.Column('translated_value', sa.Text(), nullable=True),
        sa.Column('confidence_score', sa.String(10), nullable=True),
        sa.Column('extraction_method', sa.String(50), nullable=True),
        sa.Column('is_user_modified', sa.Boolean(), default=False),
        sa.Column('user_modified_at', sa.DateTime(), nullable=True),
        sa.Column('is_approved', sa.Boolean(), default=False),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), default=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_extracted_entities_document_id'), 'extracted_entities', ['document_id'], unique=False)
    op.create_index(op.f('ix_extracted_entities_user_id'), 'extracted_entities', ['user_id'], unique=False)

    # Create consent_logs table
    op.create_table('consent_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.Enum('document_upload', 'data_extraction', 'data_storage',
                                    'data_modification', 'autofill_request', 'form_submission',
                                    'data_deletion', 'data_export', 'voice_input',
                                    name='consentaction'), nullable=False),
        sa.Column('consent_given', sa.Boolean(), nullable=False),
        sa.Column('consent_text', sa.Text(), nullable=True),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('target_website', sa.String(500), nullable=True),
        sa.Column('form_fields', postgresql.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('request_id', sa.String(36), nullable=True),
        sa.Column('additional_data', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_consent_logs_user_id'), 'consent_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_consent_logs_created_at'), 'consent_logs', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_consent_logs_created_at'), table_name='consent_logs')
    op.drop_index(op.f('ix_consent_logs_user_id'), table_name='consent_logs')
    op.drop_table('consent_logs')
    
    op.drop_index(op.f('ix_extracted_entities_user_id'), table_name='extracted_entities')
    op.drop_index(op.f('ix_extracted_entities_document_id'), table_name='extracted_entities')
    op.drop_table('extracted_entities')
    
    op.drop_index(op.f('ix_documents_user_id'), table_name='documents')
    op.drop_table('documents')
    
    op.drop_index(op.f('ix_users_phone_number'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS consentaction')
    op.execute('DROP TYPE IF EXISTS entitytype')
    op.execute('DROP TYPE IF EXISTS documentstatus')
    op.execute('DROP TYPE IF EXISTS documenttype')
