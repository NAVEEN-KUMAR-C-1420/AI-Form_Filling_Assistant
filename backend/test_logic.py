from app.services.ocr_service import OCRService
import logging
import sys

# Setup logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger()

service = OCRService()

print("--- Testing _is_valid_english_name ---")
names = ["C Naveen Kumar", "Naveen Kumar", "A Sd", "Gm wHrreit"]
for n in names:
    res = service._is_valid_english_name(n)
    print(f"'{n}': {res}")

print("\n--- Testing _extract_name logic ---")
text = """C Naveen Kumar
(Gm wHrreit/DOB: 14/05/2006
<3,607/ MALE"""
print(f"Text:\n{text}")

extracted = service._extract_name(text, "en")
print(f"Extracted: {extracted}")

print("\n--- Testing DOB Extraction ---")
# Need to access pattern manually or dummy call
import re
from app.models.document import EntityType
patterns = service.ENTITY_PATTERNS[EntityType.DATE_OF_BIRTH]
for p in patterns:
    match = re.search(p, text, re.IGNORECASE | re.MULTILINE)
    if match:
        print(f"Matched DOB with pattern '{p}': {match.group(1)}")
    else:
        print(f"No match for pattern '{p}'")

print("\n--- Testing PAN Regex ---")
pan_text = """Permanent Account Number
PECPKO354E
C Naveen Kumar"""
pan_patterns = service.ENTITY_PATTERNS[EntityType.PAN_NUMBER]
for p in pan_patterns:
    match = re.search(p, pan_text, re.IGNORECASE | re.MULTILINE)
    if match:
        print(f"Matched PAN with pattern '{p}': {match.group(1)}")

