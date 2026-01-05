"""
Document Service
Business logic for document management and data confirmation
"""
from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload
from loguru import logger

from app.models.document import Document, ExtractedEntity, DocumentType, DocumentStatus, EntityType
from app.models.consent_log import ConsentLog
from app.schemas.document import (
    DocumentUploadResponse, ExtractedDataPreview, ExtractedEntityPreview,
    ConfirmDataRequest, EntityUpdate
)
from app.services.ocr_service import OCRService
from app.utils.security import encrypt_sensitive_data, decrypt_sensitive_data, mask_sensitive_value
from app.utils.file_utils import delete_temp_file


class DocumentService:
    """Service for document management"""
    
    # Sensitive entity types that need masking
    SENSITIVE_ENTITIES = {
        EntityType.AADHAAR_NUMBER,
        EntityType.PAN_NUMBER,
        EntityType.VOTER_ID_NUMBER,
        EntityType.RATION_CARD_NUMBER,
        EntityType.ANNUAL_INCOME
    }
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.ocr_service = OCRService()
    
    async def create_document(
        self,
        user_id: UUID,
        document_type: DocumentType,
        filename: str,
        file_hash: str,
        mime_type: str,
        file_size: int
    ) -> Document:
        """Create a new document record"""
        document = Document(
            user_id=user_id,
            document_type=document_type.value,
            original_filename=filename,
            file_hash=file_hash,
            mime_type=mime_type,
            file_size_bytes=str(file_size),
            status="uploaded"
        )
        
        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)
        
        logger.info(f"Created document {document.id} for user {user_id}")
        return document
    
    async def process_document(
        self, document_id: UUID, file_path: str, user_id: UUID
    ) -> ExtractedDataPreview:
        """
        Process document with OCR and extract entities
        Returns preview for user review (data NOT saved yet)
        """
        # Get document
        document = await self.get_document(document_id, user_id)
        if not document:
            raise ValueError("Document not found")
        
        # Update status to processing
        await self._update_document_status(document_id, "processing")
        
        try:
            # Run OCR and extraction
            result = await self.ocr_service.process_document(file_path, document.document_type)
            
            if not result["success"]:
                await self._update_document_status(
                    document_id, "failed", result.get("error")
                )
                raise ValueError(f"OCR processing failed: {result.get('error')}")
            
            # Update document with results
            await self.db.execute(
                update(Document).where(Document.id == document_id).values(
                    detected_language=result["detected_language"],
                    ocr_confidence=str(result["overall_confidence"]),
                    status="extracted",
                    processed_at=datetime.utcnow()
                )
            )
            await self.db.commit()
            
            # Create temporary entity records (not confirmed yet)
            entity_previews = []
            for entity_data in result["entities"]:
                entity = ExtractedEntity(
                    document_id=document_id,
                    user_id=user_id,
                    entity_type=entity_data["entity_type"].lower(),  # Use lowercase string value
                    encrypted_value=encrypt_sensitive_data(entity_data["value"]),
                    original_language=entity_data.get("original_language"),
                    confidence_score=str(entity_data.get("confidence_score", 0)),
                    extraction_method=entity_data.get("extraction_method"),
                    is_approved=False  # Not approved until user confirms
                )
                self.db.add(entity)
                await self.db.flush()
                
                # Create preview with decrypted value
                entity_previews.append(ExtractedEntityPreview(
                    id=str(entity.id),
                    entity_type=entity.entity_type,
                    value=entity_data["value"],  # Plain text for preview
                    original_language=entity.original_language,
                    confidence_score=float(entity.confidence_score) if entity.confidence_score else None,
                    needs_review=float(entity.confidence_score or 0) < 0.8
                ))
            
            await self.db.commit()
            
            # Delete temp file after processing
            await delete_temp_file(file_path)
            
            # Log extraction consent
            await self._log_consent(
                user_id, "data_extraction",
                True, "Data extracted for review",
                document_id=document_id
            )
            
            return ExtractedDataPreview(
                document_id=str(document_id),
                document_type=document.document_type,
                detected_language=result["detected_language"],
                overall_confidence=result["overall_confidence"],
                entities=entity_previews,
                warnings=result.get("warnings", []),
                extraction_time_ms=result["processing_time_ms"]
            )
            
        except Exception as e:
            await self._update_document_status(document_id, "failed", str(e))
            await delete_temp_file(file_path)
            raise
    
    async def confirm_extracted_data(
        self, user_id: UUID, request: ConfirmDataRequest
    ) -> Dict[str, Any]:
        """
        Confirm and save user-approved extracted data
        This is the CRITICAL consent step
        """
        document_id = UUID(request.document_id)
        
        # Verify document belongs to user
        document = await self.get_document(document_id, user_id)
        if not document:
            raise ValueError("Document not found")
        
        if document.status != "extracted":
            raise ValueError("Document has not been processed or already confirmed")
        
        # Process entity updates
        confirmed_count = 0
        deleted_count = 0
        modified_count = 0
        
        for entity_update in request.entities:
            entity_id = UUID(entity_update.entity_id)
            
            # Get entity
            result = await self.db.execute(
                select(ExtractedEntity).where(
                    ExtractedEntity.id == entity_id,
                    ExtractedEntity.user_id == user_id
                )
            )
            entity = result.scalar_one_or_none()
            
            if not entity:
                continue
            
            if entity_update.delete:
                # User wants to delete this entity
                entity.is_deleted = True
                entity.deleted_at = datetime.utcnow()
                deleted_count += 1
            elif entity_update.is_approved:
                # User approves this entity
                if entity_update.new_value:
                    # User modified the value
                    entity.encrypted_value = encrypt_sensitive_data(entity_update.new_value)
                    entity.is_user_modified = True
                    entity.user_modified_at = datetime.utcnow()
                    modified_count += 1
                
                entity.is_approved = True
                entity.approved_at = datetime.utcnow()
                confirmed_count += 1
        
        # Update document status
        document.status = "confirmed"
        document.confirmed_at = datetime.utcnow()
        
        await self.db.commit()
        
        # Log storage consent
        await self._log_consent(
            user_id, "data_storage",
            True, request.consent_text,
            document_id=document_id,
            additional_data={
                "confirmed": confirmed_count,
                "deleted": deleted_count,
                "modified": modified_count
            }
        )
        
        logger.info(
            f"User {user_id} confirmed document {document_id}: "
            f"{confirmed_count} confirmed, {deleted_count} deleted, {modified_count} modified"
        )
        
        return {
            "success": True,
            "document_id": str(document_id),
            "confirmed_entities": confirmed_count,
            "deleted_entities": deleted_count,
            "modified_entities": modified_count,
            "message": "Data confirmed and securely stored"
        }
    
    async def get_user_profile_data(self, user_id: UUID) -> Dict[str, Any]:
        """Get all confirmed entity data for user"""
        # Get all confirmed entities
        result = await self.db.execute(
            select(ExtractedEntity).where(
                ExtractedEntity.user_id == user_id,
                ExtractedEntity.is_approved == True,
                ExtractedEntity.is_deleted == False
            ).order_by(ExtractedEntity.created_at.desc())
        )
        entities = result.scalars().all()
        
        # Get user's documents
        doc_result = await self.db.execute(
            select(Document).where(
                Document.user_id == user_id,
                Document.is_deleted == False
            ).order_by(Document.uploaded_at.desc())
        )
        documents = doc_result.scalars().all()
        
        # Group entities by type, keeping most recent value
        grouped_entities = {}
        entity_details = []  # Store full entity details for editing
        for entity in entities:
            entity_type = entity.entity_type  # Already a string
            if entity_type not in grouped_entities:
                decrypted = decrypt_sensitive_data(entity.encrypted_value)
                
                # Check if entity type is sensitive (use string comparison)
                is_sensitive = entity_type in ['aadhaar_number', 'pan_number', 'voter_id_number', 'ration_card_number', 'annual_income']
                
                # Mask sensitive values for display
                if is_sensitive:
                    display_value = mask_sensitive_value(decrypted)
                else:
                    display_value = decrypted
                
                grouped_entities[entity_type] = {
                    "value": display_value,
                    "full_value_available": True,
                    "source_document_id": str(entity.document_id),
                    "last_updated": entity.updated_at.isoformat() if entity.updated_at else None,
                    "entity_id": str(entity.id),
                    "is_editable": True,
                    "confidence_score": float(entity.confidence_score) if entity.confidence_score else None
                }
                
                entity_details.append({
                    "id": str(entity.id),
                    "entity_type": entity_type,
                    "value": display_value,
                    "full_value": decrypted,
                    "is_sensitive": is_sensitive,
                    "document_id": str(entity.document_id),
                    "created_at": entity.created_at.isoformat() if entity.created_at else None,
                    "updated_at": entity.updated_at.isoformat() if entity.updated_at else None
                })
        
        # Find last update time
        last_updated = None
        if entities:
            last_updated = max(e.updated_at for e in entities if e.updated_at)
        
        return {
            "user_id": str(user_id),
            "documents": [
                {
                    "id": str(d.id),
                    "document_type": d.document_type,
                    "status": d.status,
                    "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None
                }
                for d in documents
            ],
            "entities": grouped_entities,
            "entity_details": entity_details,
            "last_updated": last_updated.isoformat() if last_updated else None
        }
    
    async def get_autofill_data(
        self, user_id: UUID, requested_fields: List[str]
    ) -> Dict[str, str]:
        """
        Get decrypted data for autofill
        Only returns requested fields that user has approved
        Also includes mobile/email from user profile
        """
        # Get approved entities
        result = await self.db.execute(
            select(ExtractedEntity).where(
                ExtractedEntity.user_id == user_id,
                ExtractedEntity.is_approved == True,
                ExtractedEntity.is_deleted == False
            )
        )
        entities = result.scalars().all()
        
        # Get user for mobile/email
        from app.models.user import User
        user_result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        
        # Map to requested fields
        field_mapping = {
            "name": EntityType.FULL_NAME,
            "full_name": EntityType.FULL_NAME,
            "dob": EntityType.DATE_OF_BIRTH,
            "date_of_birth": EntityType.DATE_OF_BIRTH,
            "gender": EntityType.GENDER,
            "address": EntityType.ADDRESS,
            "aadhaar": EntityType.AADHAAR_NUMBER,
            "aadhaar_number": EntityType.AADHAAR_NUMBER,
            "pan": EntityType.PAN_NUMBER,
            "pan_number": EntityType.PAN_NUMBER,
            "voter_id": EntityType.VOTER_ID_NUMBER,
            "epic_number": EntityType.VOTER_ID_NUMBER,
            "father_name": EntityType.FATHER_NAME,
            "community": EntityType.COMMUNITY,
            "income": EntityType.ANNUAL_INCOME,
            # Mobile and email will be handled separately from user profile
            "mobile": None,
            "mobile_number": None,
            "phone": None,
            "phone_number": None,
            "email": None,
            "email_id": None,
            "mail": None,
        }
        
        # Fields that come from user profile (login data)
        profile_fields = {
            "mobile": "phone_number",
            "mobile_number": "phone_number",
            "phone": "phone_number",
            "phone_number": "phone_number",
            "email": "email",
            "email_id": "email",
            "mail": "email",
        }
        
        autofill_data = {}
        entity_map = {e.entity_type: e for e in entities}
        
        for field in requested_fields:
            field_lower = field.lower().replace(" ", "_")
            
            # Check if this is a profile field (mobile/email)
            if field_lower in profile_fields and user:
                profile_attr = profile_fields[field_lower]
                profile_value = getattr(user, profile_attr, None)
                if profile_value:
                    autofill_data[field] = profile_value
                continue
            
            entity_type = field_mapping.get(field_lower)
            
            if entity_type and entity_type in entity_map:
                entity = entity_map[entity_type]
                autofill_data[field] = decrypt_sensitive_data(entity.encrypted_value)
        
        return autofill_data
    
    async def delete_field(self, user_id: UUID, field_type: str) -> Dict[str, int]:
        """
        Delete a single field from user's saved data
        Returns count of deleted items
        """
        # Delete the entity using string comparison
        result = await self.db.execute(
            delete(ExtractedEntity).where(
                ExtractedEntity.user_id == user_id,
                ExtractedEntity.entity_type == field_type.lower()
            )
        )
        
        await self.db.commit()
        
        logger.info(f"Deleted field {field_type} for user {user_id}: {result.rowcount} records")
        
        return {"deleted": result.rowcount}
    
    async def update_entity(self, user_id: UUID, entity_id: str, new_value: str) -> Dict[str, Any]:
        """
        Update a single entity's value
        """
        from uuid import UUID as convert_uuid
        
        try:
            entity_uuid = convert_uuid(entity_id)
        except ValueError:
            raise ValueError("Invalid entity ID format")
        
        # Get entity
        result = await self.db.execute(
            select(ExtractedEntity).where(
                ExtractedEntity.id == entity_uuid,
                ExtractedEntity.user_id == user_id,
                ExtractedEntity.is_deleted == False
            )
        )
        entity = result.scalar_one_or_none()
        
        if not entity:
            raise ValueError("Entity not found")
        
        # Update entity
        entity.encrypted_value = encrypt_sensitive_data(new_value)
        entity.is_user_modified = True
        entity.user_modified_at = datetime.utcnow()
        entity.updated_at = datetime.utcnow()
        
        await self.db.commit()
        
        logger.info(f"Updated entity {entity_id} for user {user_id}")
        
        return {"updated": True}
    
    async def delete_entity(self, user_id: UUID, entity_id: str) -> Dict[str, Any]:
        """
        Delete a single entity by ID
        """
        from uuid import UUID as convert_uuid
        
        try:
            entity_uuid = convert_uuid(entity_id)
        except ValueError:
            raise ValueError("Invalid entity ID format")
        
        # Get entity
        result = await self.db.execute(
            select(ExtractedEntity).where(
                ExtractedEntity.id == entity_uuid,
                ExtractedEntity.user_id == user_id
            )
        )
        entity = result.scalar_one_or_none()
        
        if not entity:
            raise ValueError("Entity not found")
        
        # Delete entity
        await self.db.delete(entity)
        await self.db.commit()
        
        logger.info(f"Deleted entity {entity_id} for user {user_id}")
        
        return {"deleted": True}
    
    async def delete_user_data(self, user_id: UUID) -> Dict[str, int]:
        """
        Permanently delete all user data
        Returns count of deleted items
        """
        try:
            # Delete entities first (they reference documents)
            entity_result = await self.db.execute(
                delete(ExtractedEntity).where(ExtractedEntity.user_id == user_id)
            )
            entity_count = entity_result.rowcount
            
            # Delete documents
            doc_result = await self.db.execute(
                delete(Document).where(Document.user_id == user_id)
            )
            doc_count = doc_result.rowcount
            
            await self.db.commit()
            
            # Log deletion consent (after successful deletion)
            try:
                await self._log_consent(
                    user_id, "data_deletion",
                    True, "User requested permanent data deletion"
                )
            except Exception as log_error:
                logger.warning(f"Failed to log deletion consent: {log_error}")
            
            logger.info(f"Deleted all data for user {user_id}: {entity_count} entities, {doc_count} documents")
            
            return {
                "entities_deleted": entity_count,
                "documents_deleted": doc_count
            }
        except Exception as e:
            logger.error(f"Error deleting user data: {e}")
            await self.db.rollback()
            raise
    
    async def get_document(self, document_id: UUID, user_id: UUID) -> Optional[Document]:
        """Get document by ID for specific user"""
        result = await self.db.execute(
            select(Document).where(
                Document.id == document_id,
                Document.user_id == user_id,
                Document.is_deleted == False
            )
        )
        return result.scalar_one_or_none()
    
    async def _update_document_status(
        self, document_id: UUID, status: str, error: str = None
    ):
        """Update document status"""
        update_data = {"status": status}
        if error:
            update_data["processing_error"] = error
        
        await self.db.execute(
            update(Document).where(Document.id == document_id).values(**update_data)
        )
        await self.db.commit()
    
    async def _log_consent(
        self,
        user_id: UUID,
        action: str,
        consent_given: bool,
        consent_text: str,
        document_id: UUID = None,
        target_website: str = None,
        additional_data: Dict = None
    ):
        """Log consent action"""
        log = ConsentLog(
            user_id=user_id,
            action=action,
            consent_given=consent_given,
            consent_text=consent_text,
            document_id=document_id,
            target_website=target_website,
            additional_data=additional_data
        )
        self.db.add(log)
        await self.db.commit()
