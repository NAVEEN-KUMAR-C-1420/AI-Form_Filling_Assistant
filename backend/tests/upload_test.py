import base64
import os
import httpx

API_BASE = "http://localhost:8000"
TEST_EMAIL = "test.pan@example.com"
TEST_PASSWORD = "StrongP@ss1!"

PNG_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMBOgbdB9kAAAAASUVORK5CYII="
SAMPLE_PATH = os.path.join(os.path.dirname(__file__), "sample.png")


def ensure_sample_file():
    with open(SAMPLE_PATH, "wb") as f:
        f.write(base64.b64decode(PNG_BASE64))


def register_or_login(client):
    # Try register
    r = client.post(f"{API_BASE}/auth/register", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "full_name": "Test User",
        "phone_number": None
    })
    # Ignore errors if already exists
    # Login
    r = client.post(f"{API_BASE}/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    r.raise_for_status()
    data = r.json()
    return data["access_token"], data.get("refresh_token")


def upload_and_extract(doc_type="pan"):
    ensure_sample_file()
    with httpx.Client(timeout=20) as client:
        access, _ = register_or_login(client)
        headers = {"Authorization": f"Bearer {access}"}
        # Upload
        with open(SAMPLE_PATH, "rb") as f:
            files = {
                "document_type": (None, doc_type),
                "file": ("sample.png", f, "image/png"),
            }
            ur = client.post(f"{API_BASE}/documents/upload", headers=headers, files=files)
        print("Upload status:", ur.status_code, ur.text)
        ur.raise_for_status()
        up = ur.json()
        doc_id = up["document_id"]
        # Extract
        er = client.post(f"{API_BASE}/documents/extract", headers=headers, files={
            "document_id": (None, doc_id)
        })
        print("Extract status:", er.status_code)
        print(er.text)
        er.raise_for_status()
        return er.json()


if __name__ == "__main__":
    try:
        data = upload_and_extract("aadhaar")
        print("OK aadhaar keys:", list(data.keys()))
    except Exception as e:
        print("Aadhaar test failed:", e)
    try:
        data = upload_and_extract("pan")
        print("OK pan keys:", list(data.keys()))
    except Exception as e:
        print("PAN test failed:", e)
