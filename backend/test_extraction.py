import asyncio
import sys
import os
import logging

# Configure logging to show info
logging.basicConfig(level=logging.INFO)

# Need to make sure app imports work
sys.path.append(os.getcwd())

from app.services.ocr_service import OCRService
from app.models.document import DocumentType

async def test_image(image_path, doc_type_str):
    print(f"\n[{doc_type_str.upper()}] Processing {image_path}...")
    
    if not os.path.exists(image_path):
        print(f"❌ File not found: {image_path}")
        return

    service = OCRService()
    try:
        # 1. Validate/Convert Document Type
        try:
            doc_type = DocumentType(doc_type_str.lower())
        except ValueError:
            print(f"❌ Invalid document type: {doc_type_str}. Valid types: {[t.value for t in DocumentType]}")
            return

        # 2. Run Processing
        # Note: We pass the raw path. The service usually handles opening it.
        result = await service.process_document(image_path, doc_type)
        
        # 3. Print Results
        print("\n--- Extraction Results ---")
        print(f"Status: {'✅ Success' if result['success'] else '❌ Failed'}")
        
        if not result['success']:
            print(f"Error: {result.get('error')}")
            return

        print(f"Language: {result.get('detected_language', 'N/A')}")
        print(f"Confidence: {result.get('overall_confidence', 0)}%")
        
        print("\n--- Extracted Entities ---")
        extracted = result.get('extracted_data', {})
        if extracted:
            for field, data in extracted.items():
                val = data.get('value')
                conf = data.get('confidence')
                print(f"  • {field}: {val} (Conf: {conf}%)")
        else:
            print("  ⚠️ No entities extracted.")
            
        print("\n--------------------------\n")

    except Exception as e:
        print(f"❌ Exception occurred: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python test_extraction.py <image_path> <doc_type>")
        print("Example: python test_extraction.py sample_aadhar.jpg aadhaar")
        sys.exit(1)
    
    image_path = sys.argv[1]
    doc_type = sys.argv[2]
    
    asyncio.run(test_image(image_path, doc_type))
