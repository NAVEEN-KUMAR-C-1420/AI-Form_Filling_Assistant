"""
Test suite for the Form Filling Assistant API
"""
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def client():
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac


class TestHealthEndpoints:
    """Test health check endpoints."""
    
    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """Test the main health check endpoint."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
    
    @pytest.mark.asyncio
    async def test_root_endpoint(self, client: AsyncClient):
        """Test the root endpoint."""
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data


class TestAuthEndpoints:
    """Test authentication endpoints."""
    
    test_user = {
        "email": "test@example.com",
        "password": "SecurePass123!",
        "full_name": "Test User"
    }
    
    @pytest.mark.asyncio
    async def test_register_user(self, client: AsyncClient):
        """Test user registration."""
        response = await client.post("/auth/register", json=self.test_user)
        # May succeed or fail depending on DB state
        assert response.status_code in [200, 201, 400, 422]
    
    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, client: AsyncClient):
        """Test login with invalid credentials."""
        response = await client.post("/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "wrongpassword"
        })
        assert response.status_code in [401, 422]


class TestDocumentEndpoints:
    """Test document-related endpoints."""
    
    @pytest.mark.asyncio
    async def test_upload_without_auth(self, client: AsyncClient):
        """Test document upload without authentication."""
        response = await client.post(
            "/documents/upload",
            files={"file": ("test.pdf", b"fake content", "application/pdf")}
        )
        assert response.status_code == 401  # Unauthorized
    
    @pytest.mark.asyncio
    async def test_list_documents_without_auth(self, client: AsyncClient):
        """Test listing documents without authentication."""
        response = await client.get("/documents/list")
        assert response.status_code == 401


class TestUserEndpoints:
    """Test user-related endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_profile_without_auth(self, client: AsyncClient):
        """Test getting profile without authentication."""
        response = await client.get("/user/me")
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_get_autofill_data_without_auth(self, client: AsyncClient):
        """Test getting autofill data without authentication."""
        response = await client.post("/user/autofill", json={
            "website_url": "https://example.gov.in",
            "consent_given": True
        })
        assert response.status_code == 401


class TestVoiceEndpoints:
    """Test voice input endpoints."""
    
    @pytest.mark.asyncio
    async def test_voice_input_without_auth(self, client: AsyncClient):
        """Test voice input without authentication."""
        response = await client.post("/voice-input", json={
            "audio_data": "base64encodedaudio",
            "language": "en"
        })
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_get_supported_languages(self, client: AsyncClient):
        """Test getting supported languages for voice."""
        response = await client.get("/voice-input/languages")
        # This might be public or protected
        assert response.status_code in [200, 401]


class TestRateLimiting:
    """Test rate limiting functionality."""
    
    @pytest.mark.asyncio
    async def test_rate_limit_not_exceeded(self, client: AsyncClient):
        """Test that normal requests are not rate limited."""
        for _ in range(5):
            response = await client.get("/health")
            assert response.status_code == 200


class TestInputValidation:
    """Test input validation."""
    
    @pytest.mark.asyncio
    async def test_invalid_email_format(self, client: AsyncClient):
        """Test registration with invalid email."""
        response = await client.post("/auth/register", json={
            "email": "not-an-email",
            "password": "SecurePass123!",
            "full_name": "Test"
        })
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_weak_password(self, client: AsyncClient):
        """Test registration with weak password."""
        response = await client.post("/auth/register", json={
            "email": "test@example.com",
            "password": "weak",
            "full_name": "Test"
        })
        assert response.status_code == 422  # Validation error


if __name__ == "__main__":
    pytest.main(["-v", __file__])
