"""
OCR Service
Image preprocessing, OCR processing, and entity extraction
"""
import re
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime

# OpenCV is optional - use PIL for basic processing if not available
try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    
import pytesseract
from PIL import Image, ImageFilter, ImageOps
from langdetect import detect, DetectorFactory
from loguru import logger

from app.config import settings
from app.models.document import DocumentType, EntityType

# PDF support is optional
try:
    from pdf2image import convert_from_path  # type: ignore
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

# Ensure consistent language detection
DetectorFactory.seed = 0

# Set Tesseract command path
pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD


class OCRService:
    """Service for OCR processing and entity extraction"""
    
    # Language codes for Tesseract
    LANG_CODES = {
        "en": "eng",
        "hi": "hin",
        "ta": "tam",
        "te": "tel",
        "kn": "kan",
        "ml": "mal"
    }
    
    # Entity extraction patterns
    ENTITY_PATTERNS = {
        EntityType.AADHAAR_NUMBER: [
            r'\b(\d{4}\s\d{4}\s\d{4})\b',  # With spaces (most common format)
            r'\b(\d{4}\s?\d{4}\s?\d{4})\b',  # Optional spaces
            r'\b(\d{12})\b',  # No spaces
            # Handling poor OCR where spaces might be read as other chars or missing
            r'\b(\d{4}).{0,2}(\d{4}).{0,2}(\d{4})\b' 
        ],
        EntityType.PAN_NUMBER: [
            # PAN format: 5 letters + 4 digits + 1 letter (e.g., ABCDE1234F)
            # Standard pattern with label
            r'(?:Permanent Account Number|PAN|P\.A\.N)[:\s]*([A-Z]{5}[0-9O]{4}[A-Z])\b',
            r'(?:Account Number)[:\s]*([A-Z]{5}[0-9O]{4}[A-Z])\b',
            # Generic clean PAN pattern
            r'\b([A-Z]{5}[0-9O]{4}[A-Z])\b',
            # Flexible pattern for OCR errors - letters in digit positions (will be corrected)
            r'\b([A-Z]{5}[A-Z0-9]{4}[A-Z])\b',
            # Very flexible pattern - some letters may be misread (e.g., AZHPN8387P could be AZHPNB3B7P) within reasonable context
            r'\b([A-Z]{3}[A-Z]{2}[A-Z0-9]{4}[A-Z])\b',
        ],
        EntityType.VOTER_ID_NUMBER: [
            # Standard EPIC number format: 3 letters + 7 digits (e.g., TIS1672596)
            r'\b([A-Z]{3}\d{7})\b',
            # Alternative format with state code
            r'\b([A-Z]{2,3}/\d{2}/\d{3}/\d{6})\b',
            # With spaces
            r'\b([A-Z]{3}\s?\d{7})\b',
            # EPIC label patterns
            r'(?:EPIC|Epic|ID)[:\s]*([A-Z]{3}\d{7})',
            r'(?:Voter ID|Voter No|EPIC No)[:\s]*([A-Z0-9]{10,12})',
        ],
        EntityType.DATE_OF_BIRTH: [
            # DOB label patterns with various separators, handling potential OCR garbage before label
            r'(?:DOB|D\.O\.B|Date of Birth|जन्म तिथि|பிறந்த தேதி).*?[:\s]*(\d{2}[/\-\.]\d{2}[/\-\.]\d{4})',
            # Year of Birth patterns (some Aadhaar cards only have year)
            r'(?:Year of Birth|YOB|वर्ष|பிறந்த ஆண்டு).*?[:\s]*(\d{4})',
            r'(?:DOB|D\.O\.B|Birth)[:\s]*(\d{4})',  # Just year with DOB label
            # Generic date patterns (DD/MM/YYYY)
            r'\b(\d{2}[/]\d{2}[/]\d{4})\b',  
            r'\b(\d{2}[-]\d{2}[-]\d{4})\b',  
            r'\b(\d{2}[\.]\d{2}[\.]\d{4})\b',
        ],
        EntityType.GENDER: [
            r'\b(MALE|FEMALE|Male|Female|पुरुष|महिला|ஆண்|பெண்|మగ|ఆడ)\b',
            r'(?:Gender|Sex|लिंग)[:\s]*(Male|Female|MALE|FEMALE|M|F)',
        ],
        EntityType.RATION_CARD_NUMBER: [
            r'\b(\d{2}\s?\d{6}\s?\d{6})\b',
            r'\b([A-Z]{2,3}\d{10,15})\b'
        ],
        EntityType.ANNUAL_INCOME: [
            r'(?:Annual Income|वार्षिक आय|ஆண்டு வருமானம்)[:\s]*(?:Rs\.?|₹)?\s*(\d[\d,]+)',
            r'(?:Rs\.?|₹)\s*(\d[\d,]+)\s*(?:per annum|p\.a\.|/year)'
        ],
        EntityType.DRIVING_LICENSE_NUMBER: [
            # Standard format: State code (2 letters) + RTO code (2 digits) + Year (4 digits) + Number (7 digits)
            # e.g., KA0119991234567, TN0420121234567
            r'\b([A-Z]{2}\d{2}\s?\d{4}\s?\d{7})\b',
            r'\b([A-Z]{2}\d{13})\b',
            # Alternative format with hyphens
            r'\b([A-Z]{2}-\d{2}-\d{4}-\d{7})\b',
            # DL Number label patterns
            r'(?:DL\s*No|License\s*No|Driving\s*Licence|D\.L\.)[:\s]*([A-Z]{2}\d{2,4}[\s\-]?\d{4,}[\s\-]?\d*)',
            r'(?:Licence\s*No|DL\s*Number)[:\s]*([A-Z0-9\-\s]{10,20})',
            # Old format
            r'\b([A-Z]{2}/\d{2}/\d{4}/\d{7})\b',
        ],
        EntityType.BLOOD_GROUP: [
            # Standard blood group patterns
            r'(?:Blood\s*Group|BG|Blood\s*Gp|रक्त समूह)[:\s]*([ABO]{1,2}[\+\-]|[ABO]{1,2}\s*(?:Positive|Negative|POS|NEG|\+|\-))',
            r'\b(A\+|A\-|B\+|B\-|AB\+|AB\-|O\+|O\-)\b',
            r'\b(A\s*(?:Positive|Negative|POS|NEG))\b',
            r'\b(B\s*(?:Positive|Negative|POS|NEG))\b',
            r'\b(AB\s*(?:Positive|Negative|POS|NEG))\b',
            r'\b(O\s*(?:Positive|Negative|POS|NEG))\b',
        ],
        EntityType.ORGAN_DONOR: [
            r'(?:Organ\s*Donor|Donor)[:\s]*(Yes|No|Y|N)',
            r'(?:Organ\s*Donation)[:\s]*(Yes|No|Y|N)',
        ],
        EntityType.VALIDITY_DATE: [
            # Validity patterns with various labels
            r'(?:Valid\s*(?:Till|Upto|Until)|Validity|VLD|NT|Non[\s-]*Transport)[:\s]*(\d{2}[/\-\.]\d{2}[/\-\.]\d{4})',
            r'(?:TR|Transport)[:\s]*(\d{2}[/\-\.]\d{2}[/\-\.]\d{4})',
            r'(?:Expiry|EXP|Expires)[:\s]*(\d{2}[/\-\.]\d{2}[/\-\.]\d{4})',
            r'(?:Valid\s*(?:Till|Upto|Until))[:\s]*(\d{4}[/\-\.]\d{2}[/\-\.]\d{2})',
        ],
        EntityType.ISSUE_DATE: [
            r'(?:Issue\s*Date|DOI|Date\s*of\s*Issue|Issued\s*On)[:\s]*(\d{2}[/\-\.]\d{2}[/\-\.]\d{4})',
            r'(?:Issue\s*Date|DOI)[:\s]*(\d{4}[/\-\.]\d{2}[/\-\.]\d{2})',
        ]
    }
    
    # Name extraction patterns for different languages
    NAME_PATTERNS = {
        "en": [
            # Aadhaar specific - "To" label followed by name
            r'(?:To\s*\n)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
            r'(?:To\s*:?\s*\n?)([A-Z][A-Za-z]+\s+[A-Z][A-Za-z]+)',
            # Voter ID specific - Elector's Name
            r"(?:Elector(?:'s)?\s*Name|Voter(?:'s)?\s*Name)[:\s]*\n?([A-Z][A-Z\s\.]+?)(?:\n|Father|$)",
            # PAN Card specific - look for name field
            r'(?:Name|NAME)[:\s]*\n?([A-Z][A-Z\s]+?)(?:\n|Father|S/O|D/O|$)',
            # Standard name patterns (but NOT S/O, D/O - those are father's name)
            r'(?:Name|NAME)[:\s]+([A-Za-z\s\.]+?)(?:\n|S/O|D/O|$)',
        ],
        "hi": [
            r'(?:नाम|नाम:)[:\s]*(.+?)(?:\n|$)',
            r'(?:निर्वाचक का नाम|मतदाता का नाम)[:\s]*(.+?)(?:\n|$)',
        ],
        "ta": [
            r'(?:பெயர்|பெயர்:)[:\s]*(.+?)(?:\n|$)',
        ]
    }
    
    # Words to skip when extracting names (government headers, etc.)
    SKIP_NAME_WORDS = [
        'government', 'india', 'aadhaar', 'unique', 'identification', 
        'authority', 'male', 'female', 'address', 'download', 'date', 'dob',
        'income', 'tax', 'department', 'permanent', 'account', 'number',
        'भारत', 'सरकार', 'आयकर', 'विभाग', 'govt', 'republic',
        'election', 'commission', 'voter', 'electoral', 'photo', 'identity',
        'card', 'elector', 'epic', 'roll', 'polling', 'station', 'booth'
    ]
    
    # Address keywords for extraction
    ADDRESS_KEYWORDS = [
        "address", "पता", "முகவரி", "చిరునామా", "ವಿಳಾಸ", "വിലാസം",
        "s/o", "d/o", "w/o", "c/o", "house", "street", "road", "lane",
        "district", "state", "pin", "pincode"
    ]
    
    def __init__(self):
        self.supported_languages = list(self.LANG_CODES.keys())
    
    async def process_document(
        self, file_path: str, document_type: DocumentType
    ) -> Dict[str, Any]:
        """
        Main method to process a document
        Returns extracted data with confidence scores
        """
        start_time = time.time()
        
        try:
            # Load and preprocess image(s)
            images = await self._load_document(file_path)
            
            # Detect language from first image
            detected_lang = await self._detect_language(images[0])
            
            # Get appropriate Tesseract language code
            lang_code = self._get_tesseract_lang(detected_lang)
            
            # Extract text from all pages
            full_text = ""
            confidences = []
            
            for img in images:
                # Preprocess image
                processed = await self._preprocess_image(img)
                
                # Run OCR
                text, confidence = await self._run_ocr(processed, lang_code)
                full_text += text + "\n"
                confidences.append(confidence)
            
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            # Tesseract returns confidence as 0-100, convert to 0-1 range
            avg_confidence = min(avg_confidence / 100.0, 1.0)
            
            # Extract entities based on document type
            logger.info(f"Processing extraction for doc_type: {document_type} ({type(document_type)})")
            entities = await self._extract_entities(full_text, document_type, detected_lang)
            
            processing_time = int((time.time() - start_time) * 1000)
            
            return {
                "success": True,
                "detected_language": detected_lang,
                "overall_confidence": round(avg_confidence, 2),
                "raw_text": full_text,
                "entities": entities,
                "processing_time_ms": processing_time,
                "warnings": self._generate_warnings(entities, avg_confidence)
            }
            
        except Exception as e:
            logger.error(f"OCR processing error: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "processing_time_ms": int((time.time() - start_time) * 1000)
            }
    
    async def _load_document(self, file_path: str) -> List[Image.Image]:
        """Load document and convert to PIL Images"""
        path = Path(file_path)
        
        if path.suffix.lower() == '.pdf':
            if not PDF_SUPPORT:
                raise ValueError("PDF support not available. Install pdf2image.")
            # Convert PDF pages to images
            pil_images = convert_from_path(file_path, dpi=300)
            return pil_images
        else:
            # Load image file using PIL
            img = Image.open(file_path)
            return [img]
    
    async def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        Preprocess image for better OCR accuracy using PIL
        """
        # Convert to grayscale
        gray = image.convert('L')
        
        # Resize if too small
        width, height = gray.size
        if width < 1000:
            scale = 1000 / width
            new_size = (int(width * scale), int(height * scale))
            gray = gray.resize(new_size, Image.Resampling.LANCZOS)
        
        # Apply sharpening filter
        sharpened = gray.filter(ImageFilter.SHARPEN)
        
        # Enhance contrast
        enhanced = ImageOps.autocontrast(sharpened)
        
        return enhanced
    
    async def _detect_language(self, image: Image.Image) -> str:
        """Detect language from image text"""
        try:
            # Quick OCR with English for language detection
            text = pytesseract.image_to_string(image, lang='eng+hin+tam')
            
            if len(text.strip()) > 20:
                detected = detect(text)
                return detected if detected in self.supported_languages else "en"
        except:
            pass
        
        return "en"  # Default to English
    
    def _get_tesseract_lang(self, detected_lang: str) -> str:
        """Get Tesseract language code"""
        # Always include English for mixed content
        base_lang = self.LANG_CODES.get(detected_lang, "eng")
        return f"{base_lang}+eng" if base_lang != "eng" else "eng"
    
    async def _run_ocr(
        self, image: Image.Image, lang: str
    ) -> Tuple[str, float]:
        """
        Run OCR on preprocessed image
        Returns (text, confidence)
        """
        # Get OCR data with confidence
        data = pytesseract.image_to_data(
            image, lang=lang, output_type=pytesseract.Output.DICT
        )
        
        # Calculate average confidence (excluding -1 values)
        confidences = [int(c) for c in data['conf'] if int(c) > 0]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        # Get text
        text = pytesseract.image_to_string(image, lang=lang)
        
        # Debug logging - log the extracted text
        logger.info(f"OCR extracted text (lang={lang}):\n{text}")
        logger.info(f"OCR confidence: {avg_confidence}")
        
        return text.strip(), avg_confidence
    

    async def _extract_entities(
        self, text: str, doc_type: DocumentType, language: str
    ) -> List[Dict[str, Any]]:
        """Extract entities from OCR text based on document type"""
        entities = []
        
        # Define which entities to extract based on document type
        # Now extracts both English and regional names for storage
        entity_map = {
            DocumentType.AADHAAR: [
                EntityType.FULL_NAME, EntityType.FULL_NAME_REGIONAL, EntityType.DATE_OF_BIRTH, 
                EntityType.GENDER, EntityType.ADDRESS, EntityType.AADHAAR_NUMBER, EntityType.FATHER_NAME
            ],
            DocumentType.PAN: [
                EntityType.FULL_NAME, EntityType.FULL_NAME_REGIONAL, EntityType.DATE_OF_BIRTH, 
                EntityType.PAN_NUMBER, EntityType.FATHER_NAME
            ],
            DocumentType.VOTER_ID: [
                EntityType.FULL_NAME, EntityType.FULL_NAME_REGIONAL, EntityType.DATE_OF_BIRTH, 
                EntityType.GENDER, EntityType.ADDRESS, EntityType.VOTER_ID_NUMBER, EntityType.FATHER_NAME
            ],
            DocumentType.RATION_CARD: [
                EntityType.FULL_NAME, EntityType.FULL_NAME_REGIONAL, EntityType.ADDRESS, 
                EntityType.RATION_CARD_NUMBER
            ],
            DocumentType.COMMUNITY_CERTIFICATE: [
                EntityType.FULL_NAME, EntityType.COMMUNITY, EntityType.CERTIFICATE_ISSUE_DATE,
                EntityType.FATHER_NAME
            ],
            DocumentType.INCOME_CERTIFICATE: [
                EntityType.FULL_NAME, EntityType.ANNUAL_INCOME, EntityType.CERTIFICATE_ISSUE_DATE,
                EntityType.ADDRESS
            ],
            DocumentType.DRIVING_LICENSE: [
                EntityType.FULL_NAME, EntityType.FULL_NAME_REGIONAL, EntityType.DATE_OF_BIRTH,
                EntityType.ADDRESS, EntityType.DRIVING_LICENSE_NUMBER, EntityType.BLOOD_GROUP,
                EntityType.ORGAN_DONOR, EntityType.VALIDITY_DATE, EntityType.ISSUE_DATE,
                EntityType.FATHER_NAME
            ]
        }
        
        target_entities = entity_map.get(doc_type, [EntityType.FULL_NAME])
        
        for entity_type in target_entities:
            extracted = await self._extract_single_entity(text, entity_type, language)
            if extracted:
                entities.append(extracted)
        
        return entities
    
    async def _extract_single_entity(
        self, text: str, entity_type: EntityType, language: str
    ) -> Optional[Dict[str, Any]]:
        """Extract a single entity from text"""
        
        if entity_type == EntityType.FULL_NAME:
            return self._extract_name(text, language)
        
        if entity_type == EntityType.FULL_NAME_REGIONAL:
            return self._extract_regional_name(text, language)
        
        if entity_type == EntityType.ADDRESS:
            return self._extract_address(text, language)
        
        if entity_type == EntityType.FATHER_NAME:
            return self._extract_father_name(text, language)
        
        # Special positional fallback for Driving License number
        if entity_type == EntityType.DRIVING_LICENSE_NUMBER:
            # First try regex patterns; if none match, use positional heuristics
            patterns = self.ENTITY_PATTERNS.get(entity_type, [])
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                if match:
                    value = match.group(1).strip()
                    confidence = self._calculate_confidence(entity_type, value)
                    return {
                        "entity_type": entity_type.value,
                        "value": self._clean_value(value, entity_type),
                        "original_language": language,
                        "confidence_score": confidence,
                        "extraction_method": "regex"
                    }

            # Positional/keyword-based heuristic: search near DL labels
            lines = text.split('\n')
            for i, line in enumerate(lines):
                l = line.strip()
                if not l:
                    continue
                if re.search(r'(DL\s*No|License\s*No|Driving\s*Licen[cs]e|D\.L\.|Licence\s*No)', l, re.IGNORECASE):
                    # Check same line for a token that resembles DL number
                    token_match = re.search(r'([A-Z]{2}[\s\-]?\d{2,4}[\s\-]?\d{4,}[\s\-]?\d*)', l)
                    if token_match:
                        value = token_match.group(1)
                        return {
                            "entity_type": entity_type.value,
                            "value": self._clean_value(value, entity_type),
                            "original_language": language,
                            "confidence_score": 0.80,
                            "extraction_method": "positional"
                        }
                    # Else look at the next few lines
                    for j in range(1, 3):
                        if i + j < len(lines):
                            nx = lines[i + j].strip()
                            token_match2 = re.search(r'([A-Z]{2}[\s\-]?\d{2,4}[\s\-]?\d{4,}[\s\-]?\d*)', nx)
                            if token_match2:
                                value = token_match2.group(1)
                                return {
                                    "entity_type": entity_type.value,
                                    "value": self._clean_value(value, entity_type),
                                    "original_language": language,
                                    "confidence_score": 0.78,
                                    "extraction_method": "positional"
                                }
            # If still not found, try scanning for a strong DL-like token anywhere
            any_match = re.search(r'\b([A-Z]{2}\d{2}[\s\-]?\d{4}[\s\-]?\d{5,7})\b', text)
            if any_match:
                value = any_match.group(1)
                return {
                    "entity_type": entity_type.value,
                    "value": self._clean_value(value, entity_type),
                    "original_language": language,
                    "confidence_score": 0.72,
                    "extraction_method": "pattern_fallback"
                }
            return None

        # Use pattern matching for other entities (including EPIC)
        patterns = self.ENTITY_PATTERNS.get(entity_type, [])
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                value = match.group(1).strip()
                confidence = self._calculate_confidence(entity_type, value)
                
                return {
                    "entity_type": entity_type.value,
                    "value": self._clean_value(value, entity_type),
                    "original_language": language,
                    "confidence_score": confidence,
                    "extraction_method": "regex"
                }
        
        return None
    
    def _extract_regional_name(self, text: str, language: str) -> Optional[Dict[str, Any]]:
        """Extract name in regional language (Tamil, Hindi, etc.) from text"""
        # Look for Tamil script (Unicode range: 0B80-0BFF)
        tamil_pattern = r'[\u0B80-\u0BFF]+'
        # Look for Hindi/Devanagari script (Unicode range: 0900-097F)
        hindi_pattern = r'[\u0900-\u097F]+'
        # Look for Telugu script (Unicode range: 0C00-0C7F)
        telugu_pattern = r'[\u0C00-\u0C7F]+'
        # Look for Kannada script (Unicode range: 0C80-0CFF)
        kannada_pattern = r'[\u0C80-\u0CFF]+'
        # Look for Malayalam script (Unicode range: 0D00-0D7F)
        malayalam_pattern = r'[\u0D00-\u0D7F]+'
        
        regional_patterns = [
            (tamil_pattern, 'tamil'),
            (hindi_pattern, 'hindi'),
            (telugu_pattern, 'telugu'),
            (kannada_pattern, 'kannada'),
            (malayalam_pattern, 'malayalam'),
        ]
        
        for pattern, script_lang in regional_patterns:
            matches = re.findall(pattern, text)
            if matches:
                # Find the longest match that looks like a name (not common words)
                # Skip common Hindi words like भारत (India), सरकार (Government), etc.
                skip_words = ['भारत', 'सरकार', 'आधार', 'पुरुष', 'महिला', 'पता', 'जन्म', 'तिथि', 
                             'विशिष्ट', 'पहचान', 'प्राधिकरण', 'मेरा', 'मेरी', 'आयकर', 'विभाग']
                
                for match in matches:
                    # Skip if it's a common word
                    if match in skip_words:
                        continue
                    # Name should be reasonably long (at least 3 characters in regional script)
                    if len(match) >= 3:
                        logger.info(f"Found regional name ({script_lang}): {match}")
                        return {
                            "entity_type": EntityType.FULL_NAME_REGIONAL.value,
                            "value": match,
                            "original_language": script_lang,
                            "confidence_score": 0.80,
                            "extraction_method": "unicode_pattern"
                        }
        
        return None
    
    def _extract_father_name(self, text: str, language: str) -> Optional[Dict[str, Any]]:
        """Extract father's name from text (for PAN cards and Voter ID)"""
        patterns = [
            # Voter ID specific patterns
            r"(?:Father(?:'s)?[\s/|]*Name|Fatver(?:'s)?[\s/|]*Name)[:\s|]*\n?([A-Z][A-Za-z\s\.]+?)(?:\n|$)",
            r"(?:Husband(?:'s)?[\s/|]*Name)[:\s|]*\n?([A-Z][A-Za-z\s\.]+?)(?:\n|$)",
            # PAN Card patterns
            r"(?:Father's Name|FATHER'S NAME|Father Name)[:\s]*\n?([A-Z][A-Z\s]+?)(?:\n|Date|DOB|$)",
            r"(?:S/O|D/O|Son of|Daughter of|W/O|Wife of)[:\s]*([A-Za-z\s\.]+?)(?:\n|$)",
            # Hindi patterns
            r"(?:पिता का नाम|पिता)[:\s]*(.+?)(?:\n|$)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                name = match.group(1).strip()
                name = re.sub(r'\s+', ' ', name)
                
                # Skip if contains government keywords
                if any(word.lower() in name.lower() for word in self.SKIP_NAME_WORDS):
                    continue
                
                # Skip single words that are common OCR errors
                if name.lower() in ['name', 'male', 'female', 'date']:
                    continue
                    
                if 3 <= len(name) <= 50:
                    return {
                        "entity_type": EntityType.FATHER_NAME.value,
                        "value": name.title(),
                        "original_language": language,
                        "confidence_score": 0.80,
                        "extraction_method": "regex"
                    }
        
        # For PAN cards - the second name line is typically the father's name
        # Pattern: After holder name, look for another name line before DOB
        lines = text.split('\n')
        name_lines = []
        for line in lines:
            clean_line = line.strip()
            # Check if line contains only letters and spaces (name pattern)
            if clean_line and re.match(r'^[A-Za-z\s\.]+$', clean_line):
                # Skip government keywords
                if any(word.lower() in clean_line.lower() for word in self.SKIP_NAME_WORDS):
                    continue
                # Skip single common words
                if clean_line.lower() in ['name', 'male', 'female', 'date', 'are']:
                    continue
                if 3 <= len(clean_line) <= 50 and self._is_valid_english_name(clean_line):
                    name_lines.append(clean_line)
        
        # If we found at least 2 name lines, second one is likely father's name
        if len(name_lines) >= 2:
            father_name = re.sub(r'\s+', ' ', name_lines[1]).title()
            logger.info(f"Found father name from line scan: {father_name}")
            return {
                "entity_type": EntityType.FATHER_NAME.value,
                "value": father_name,
                "original_language": language,
                "confidence_score": 0.75,
                "extraction_method": "line_scan"
            }
        
        return None
    
    def _extract_name(self, text: str, language: str) -> Optional[Dict[str, Any]]:
        """Extract name from text"""
        patterns = self.NAME_PATTERNS.get(language, self.NAME_PATTERNS["en"])
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                name = match.group(1).strip()
                # Clean up name
                name = re.sub(r'\s+', ' ', name)
                
                # Skip if name contains government/official keywords
                if any(word.lower() in name.lower() for word in self.SKIP_NAME_WORDS):
                    continue
                    
                # Skip if name is too short or looks like a header
                if len(name) < 3 or len(name) > 100:
                    continue
                
                name = name.title()
                
                return {
                    "entity_type": EntityType.FULL_NAME.value,
                    "value": name,
                    "original_language": language,
                    "confidence_score": 0.85,
                    "extraction_method": "regex"
                }

        # --- Enhanced Positional Extraction ---
        lines = text.split('\n')
        
        # 1. Look relative to specific anchors (DOB, Gender, PAN, Govt Header)
        dob_line_idx = -1
        pan_line_idx = -1
        
        for i, line in enumerate(lines):
            clean_line = line.strip().lower()
            if 'dob:' in clean_line or 'date of birth' in clean_line or 'year of birth' in clean_line:
                dob_line_idx = i
            # Very specific PAN Check
            if 'permanent account number' in clean_line or 'income tax department' in clean_line or 'pan' in clean_line.split(' '):
                pan_line_idx = i

        # Strategy A: Above DOB (Common in Aadhaar)
        if dob_line_idx != -1:
            # Look up to 3 lines above DOB
            for i in range(1, 4):
                if dob_line_idx - i >= 0:
                    candidate = lines[dob_line_idx - i].strip()
                    if self._is_potential_name(candidate):
                        # Skip if it is the Aadhaar number (mostly digits)
                        if re.search(r'\d{4}', candidate):
                            continue
                        logger.info(f"Found name relative to DOB: {candidate}")
                        return {
                            "entity_type": EntityType.FULL_NAME.value,
                            "value": candidate.title(),
                            "original_language": language,
                            "confidence_score": 0.82,
                            "extraction_method": "relative_dob"
                        }

        # Strategy B: Below PAN Header (Common in PAN)
        if pan_line_idx != -1:
             # Look up to 4 lines below PAN header
            for i in range(1, 5):
                if pan_line_idx + i < len(lines):
                    candidate = lines[pan_line_idx + i].strip()
                    if self._is_potential_name(candidate):
                        # Don't pick the PAN number itself
                        if re.search(r'[A-Z]{5}[0-9O]{4}[A-Z]', candidate):
                            continue
                         # Don't pick Signature label
                        if 'sign' in candidate.lower():
                            continue
                        logger.info(f"Found name relative to PAN Header: {candidate}")
                        return {
                            "entity_type": EntityType.FULL_NAME.value,
                            "value": candidate.title(),
                            "original_language": language,
                            "confidence_score": 0.82,
                            "extraction_method": "relative_pan"
                        }

        # Fallback: General Line Scan
        found_to_label = False
        for i, line in enumerate(lines):
            clean_line = line.strip()
            
            # Track "To" label for Aadhaar cards
            if clean_line.lower() == 'to':
                found_to_label = True
                continue
            
            if self._is_potential_name(clean_line):
                # If we found "To" label, this is likely the name (Aadhaar format)
                confidence = 0.85 if found_to_label else 0.70
                
                return {
                    "entity_type": EntityType.FULL_NAME.value,
                    "value": clean_line.title(),
                    "original_language": language,
                    "confidence_score": confidence,
                    "extraction_method": "line_scan"
                }
        
        return None
    
    def _is_potential_name(self, text: str) -> bool:
        """Helper to check if a line is likely a name"""
        clean_line = text.strip()
        
        # Check if line contains only letters and spaces (and is uppercase - common in ID cards)
        if not clean_line or not re.match(r'^[A-Za-z\s\.]+$', clean_line):
            return False
            
        # Skip lines containing government/official keywords
        if any(word.lower() in clean_line.lower() for word in self.SKIP_NAME_WORDS):
            return False
        
        # Skip single common words/labels
        if clean_line.lower() in ['name', 'to', 'from', 'signature', 'sign']:
            return False

        # Skip if the name looks like OCR garbage (random characters)
        if not self._is_valid_english_name(clean_line):
            return False
        
        # Skip S/O, D/O, W/O lines
        if re.match(r'^[SDWC]/O\s', clean_line, re.IGNORECASE):
            return False
            
        # Check length constraints
        if not (3 <= len(clean_line) <= 50):
            return False
            
        return True
    
    def _is_valid_english_name(self, name: str) -> bool:
        """
        Check if a string looks like a valid English name.
        Filters out OCR garbage like 'Gufweniseny' which is garbled regional text.
        """
        # Remove spaces and convert to lowercase for analysis
        clean = name.replace(' ', '').replace('.', '').lower()
        
        if len(clean) < 2:
            return False
        
        # Count vowels and consonants
        vowels = set('aeiou')
        consonants = set('bcdfghjklmnpqrstvwxyz')
        
        vowel_count = sum(1 for c in clean if c in vowels)
        consonant_count = sum(1 for c in clean if c in consonants)
        
        total_letters = vowel_count + consonant_count
        if total_letters == 0:
            return False
        
        vowel_ratio = vowel_count / total_letters
        
        # Valid English names typically have 25-50% vowels
        # OCR garbage often has unusual ratios
        if vowel_ratio < 0.15 or vowel_ratio > 0.6:
            return False
        
        # Check for unusual consonant clusters (more than 3 consonants in a row)
        # This catches OCR garbage like "Gufweniseny" (which has unusual patterns)
        consonant_streak = 0
        max_consonant_streak = 0
        for c in clean:
            if c in consonants:
                consonant_streak += 1
                max_consonant_streak = max(max_consonant_streak, consonant_streak)
            else:
                consonant_streak = 0
        
        # Most English names don't have more than 3 consonants in a row
        if max_consonant_streak > 4:
            return False
        
        # Check for repeated unusual patterns (OCR often produces these)
        # E.g., "weni" in "Gufweniseny" is unusual
        unusual_patterns = ['fw', 'wf', 'guf', 'ufwe', 'weni', 'nise']
        for pattern in unusual_patterns:
            if pattern in clean:
                return False
        
        return True
    
    def _extract_address(self, text: str, language: str) -> Optional[Dict[str, Any]]:
        """Extract address from text - stops at pincode"""
        # Look for address section
        text_lower = text.lower()
        
        for keyword in self.ADDRESS_KEYWORDS:
            if keyword.lower() in text_lower:
                # Find position and extract following text
                idx = text_lower.find(keyword.lower())
                address_text = text[idx:idx + 400]
                
                # Extract until pincode or end
                lines = address_text.split('\n')
                address_lines = []
                pincode_found = False
                
                for line in lines[1:8]:  # Take up to 8 lines after keyword
                    cleaned = line.strip()
                    if not cleaned or len(cleaned) < 3:
                        continue
                    
                    # Check if line contains pincode (6-digit number)
                    pincode_match = re.search(r'\b(\d{6})\b', cleaned)
                    if pincode_match:
                        # Include the line with pincode but stop there
                        # Extract only up to and including the pincode
                        pincode_pos = pincode_match.end()
                        address_lines.append(cleaned[:pincode_pos].strip())
                        pincode_found = True
                        break
                    
                    # Skip lines that look like document identifiers (Aadhaar, etc.)
                    if re.match(r'^\d{4}\s?\d{4}\s?\d{4}$', cleaned):
                        continue
                    
                    address_lines.append(cleaned)
                
                if address_lines:
                    address = ', '.join(address_lines)
                    # Clean up address - remove trailing commas, extra spaces
                    address = re.sub(r',\s*$', '', address)
                    address = re.sub(r'\s+', ' ', address)
                    logger.info(f"Extracted address (pincode_found={pincode_found}): {address}")
                    return {
                        "entity_type": EntityType.ADDRESS.value,
                        "value": address,
                        "original_language": language,
                        "confidence_score": 0.80 if pincode_found else 0.70,
                        "extraction_method": "keyword_search"
                    }
        
        # Fallback: Look for PIN code pattern and extract surrounding text as address
        pin_match = re.search(r'\b(\d{6})\b', text)
        if pin_match:
            # Find text before PIN code - likely address
            pin_pos = pin_match.start()
            # Get up to 300 chars before the PIN code
            start_pos = max(0, pin_pos - 300)
            address_text = text[start_pos:pin_match.end()]  # Include pincode, stop there
            
            # Clean up and extract address lines
            lines = address_text.split('\n')
            address_lines = []
            for line in lines[-6:]:  # Take last 6 lines ending with PIN
                cleaned = line.strip()
                # Skip lines that are just numbers or very short
                if cleaned and len(cleaned) > 3:
                    # Skip lines that look like Aadhaar numbers
                    if not re.match(r'^\d{4}\s?\d{4}\s?\d{4}$', cleaned):
                        # If this line contains the pincode, extract only up to pincode
                        pincode_in_line = re.search(r'\b(\d{6})\b', cleaned)
                        if pincode_in_line:
                            address_lines.append(cleaned[:pincode_in_line.end()].strip())
                        else:
                            address_lines.append(cleaned)
            
            if address_lines:
                address = ', '.join(address_lines)
                # Clean up - remove trailing commas and extra spaces
                address = re.sub(r',\s*$', '', address)
                address = re.sub(r'\s+', ' ', address)
                logger.info(f"Extracted address from PIN code fallback: {address}")
                return {
                    "entity_type": EntityType.ADDRESS.value,
                    "value": address,
                    "original_language": language,
                    "confidence_score": 0.75,
                    "extraction_method": "pincode_search"
                }
        
        return None
    
    def _calculate_confidence(self, entity_type: EntityType, value: str) -> float:
        """Calculate confidence score for extracted value"""
        base_confidence = 0.80
        
        # Validate specific formats
        if entity_type == EntityType.AADHAAR_NUMBER:
            clean = re.sub(r'\s', '', value)
            if len(clean) == 12 and clean.isdigit():
                return 0.95
        
        if entity_type == EntityType.PAN_NUMBER:
            if re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', value.upper()):
                return 0.95
        
        if entity_type == EntityType.DATE_OF_BIRTH:
            try:
                # Try to parse date
                for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%d.%m.%Y']:
                    try:
                        datetime.strptime(value, fmt)
                        return 0.90
                    except:
                        continue
            except:
                pass
        
        return base_confidence
    
    def _fix_pan_ocr_errors(self, value: str) -> str:
        """Fix common OCR misreads in PAN numbers.
        PAN format: AAAAA9999A (5 letters + 4 digits + 1 letter)
        Common OCR errors: S->8, O->0, I->1, B->8, G->6, Z->2, D->0
        
        Also handles cases like "DEPAR1237D" where "DEPAR" should be "ABCDE" type letters
        and fixes digits misread as letters in positions 5-8.
        """
        if len(value) != 10:
            return value
        
        value = value.upper()
        result = list(value)
        
        # First 5 characters should be letters
        # Fix digits that were misread as letters (rarely needed but can happen)
        ocr_digit_to_letter = {
            '0': 'O',
            '1': 'I',
            '8': 'B',
        }
        
        for i in range(0, 5):  # Positions 0-4 should be letters
            if result[i].isdigit() and result[i] in ocr_digit_to_letter:
                result[i] = ocr_digit_to_letter[result[i]]
        
        # Characters 5-8 should be digits - fix common OCR errors
        ocr_letter_to_digit = {
            'S': '8', 'B': '8',
            'O': '0', 'Q': '0', 'D': '0',
            'I': '1', 'L': '1', 'J': '1',
            'Z': '2',
            'E': '3',
            'A': '4', 'H': '4',
            'G': '6',
            'T': '7',
            'P': '9',  # P can look like 9
            'R': '2',  # R can look like 2
        }
        
        for i in range(5, 9):  # Positions 5-8 should be digits
            if result[i] in ocr_letter_to_digit:
                result[i] = ocr_letter_to_digit[result[i]]
        
        # Character 9 should be a letter
        if result[9].isdigit() and result[9] in ocr_digit_to_letter:
            result[9] = ocr_digit_to_letter[result[9]]
        
        # Verify result looks like a valid PAN
        fixed = ''.join(result)
        logger.info(f"PAN OCR fix: {value} -> {fixed}")
        
        return fixed
        
        return ''.join(result)
    
    def _clean_value(self, value: str, entity_type: EntityType) -> str:
        """Clean extracted value"""
        value = value.strip()
        
        if entity_type == EntityType.AADHAAR_NUMBER:
            # Format as XXXX XXXX XXXX
            clean = re.sub(r'\s', '', value)
            if len(clean) == 12:
                return f"{clean[:4]} {clean[4:8]} {clean[8:]}"
        
        if entity_type == EntityType.PAN_NUMBER:
            # Fix common OCR errors and uppercase
            value = value.upper()
            value = self._fix_pan_ocr_errors(value)
            return value
        
        if entity_type == EntityType.ANNUAL_INCOME:
            # Remove currency symbols and format
            clean = re.sub(r'[₹Rs\.\s,]', '', value)
            if clean.isdigit():
                return f"₹{int(clean):,}"
        
        # Format dates with month names for DOB, validity, issue dates
        if entity_type in [EntityType.DATE_OF_BIRTH, EntityType.VALIDITY_DATE, EntityType.ISSUE_DATE]:
            return self._format_date_with_month_name(value)
        
        # Normalize blood group
        if entity_type == EntityType.BLOOD_GROUP:
            return self._normalize_blood_group(value)
        
        # Normalize organ donor
        if entity_type == EntityType.ORGAN_DONOR:
            value_upper = value.upper().strip()
            if value_upper in ['Y', 'YES']:
                return 'Yes'
            elif value_upper in ['N', 'NO']:
                return 'No'
        
        # Clean driving license number
        if entity_type == EntityType.DRIVING_LICENSE_NUMBER:
            # Remove spaces and hyphens, return uppercase
            clean = re.sub(r'[\s\-/]', '', value.upper())
            return clean
        
        return value
    
    def _format_date_with_month_name(self, date_str: str) -> str:
        """Convert date to 'DD Mon YYYY' format (e.g., 15 Jan 1990)"""
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        # Try different date formats
        # DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
        date_patterns = [
            (r'(\d{2})[/\-\.](\d{2})[/\-\.](\d{4})', 'day_first'),  # DD/MM/YYYY
            (r'(\d{4})[/\-\.](\d{2})[/\-\.](\d{2})', 'year_first'),  # YYYY/MM/DD
        ]
        
        for pattern, format_type in date_patterns:
            match = re.match(pattern, date_str.strip())
            if match:
                if format_type == 'day_first':
                    day, month, year = match.groups()
                else:  # year_first
                    year, month, day = match.groups()
                
                try:
                    month_idx = int(month) - 1
                    if 0 <= month_idx < 12:
                        month_name = month_names[month_idx]
                        return f"{int(day)} {month_name} {year}"
                except (ValueError, IndexError):
                    pass
        
        # If no pattern matched, return original
        return date_str
    
    def _normalize_blood_group(self, value: str) -> str:
        """Normalize blood group to standard format (e.g., A+, B-, AB+, O-)"""
        value_upper = value.upper().strip()
        
        # Handle written forms
        value_upper = value_upper.replace('POSITIVE', '+').replace('POS', '+')
        value_upper = value_upper.replace('NEGATIVE', '-').replace('NEG', '-')
        
        # Remove spaces
        value_upper = re.sub(r'\s+', '', value_upper)
        
        # Validate and return
        valid_groups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
        if value_upper in valid_groups:
            return value_upper
        
        return value
    
    def _generate_warnings(
        self, entities: List[Dict], confidence: float
    ) -> List[str]:
        """Generate warnings based on extraction results"""
        warnings = []
        
        if confidence < 70:
            warnings.append("Low overall OCR confidence. Please verify all extracted data.")
        
        low_confidence_entities = [
            e['entity_type'] for e in entities 
            if e.get('confidence_score', 0) < 0.7
        ]
        
        if low_confidence_entities:
            warnings.append(
                f"Low confidence on: {', '.join(low_confidence_entities)}. Please review these fields."
            )
        
        return warnings
