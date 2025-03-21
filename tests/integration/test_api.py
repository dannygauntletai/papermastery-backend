import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import validate_environment

client = TestClient(app)

# Override validate_environment dependency
@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock the dependencies."""
    # Override the validate_environment dependency
    async def mock_validate_environment():
        return True
    
    # Save old overrides and update with our new ones
    old_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[validate_environment] = mock_validate_environment
    
    yield
    
    # Restore original overrides
    app.dependency_overrides = old_overrides


def test_root_endpoint():
    """Test the root endpoint returns a welcome message."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to ArXiv Mastery"}


def test_health_check():
    """Test the health check endpoint returns a healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "uptime_seconds" in data
    assert data["service"] == "arxiv-mastery-api"


def test_docs_available():
    """Test that the API documentation is available."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_redoc_available():
    """Test that the ReDoc API documentation is available."""
    response = client.get("/redoc")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"] 