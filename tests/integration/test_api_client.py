import pytest
from fastapi.testclient import TestClient
from typing import Dict, List, Any, Optional
import uuid
from app.main import app
from app.dependencies import validate_environment

# Initialize test client
client = TestClient(app)

# Store paper_id for use across tests
test_paper_id = None

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

def test_health():
    """Test the health endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "uptime_seconds" in data
    assert data["service"] == "arxiv-mastery-api"

def test_root():
    """Test the root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "Welcome" in data["message"]

def test_list_papers():
    """Test the list papers endpoint"""
    response = client.get("/api/v1/papers/")
    assert response.status_code == 200
    papers = response.json()
    assert isinstance(papers, list)
    
    # If there are papers, check the structure
    if papers:
        paper = papers[0]
        assert "id" in paper
        assert "title" in paper
        assert "authors" in paper

def test_submit_paper():
    """Test submitting a paper"""
    global test_paper_id
    
    # Use a valid arXiv link
    arxiv_link = "https://arxiv.org/abs/1706.03762"  # Attention Is All You Need
    
    response = client.post(
        "/api/v1/papers/submit",
        json={"arxiv_link": arxiv_link}
    )
    
    # If we get a 409 Conflict, the paper already exists
    # This is still valid for our test
    assert response.status_code in [200, 409]
    
    data = response.json()
    assert "id" in data
    
    # Save the paper ID for other tests
    test_paper_id = data["id"]
    assert test_paper_id is not None

def test_get_paper():
    """Test getting a paper by ID"""
    global test_paper_id
    
    # Skip if we don't have a paper ID
    if not test_paper_id:
        pytest.skip("No paper ID available from previous test")
    
    response = client.get(f"/api/v1/papers/{test_paper_id}")
    assert response.status_code == 200
    
    paper = response.json()
    assert paper["id"] == test_paper_id
    assert "title" in paper
    assert "abstract" in paper
    assert "authors" in paper

def test_get_paper_summaries():
    """Test getting summaries for a paper"""
    global test_paper_id
    
    # Skip if we don't have a paper ID
    if not test_paper_id:
        pytest.skip("No paper ID available from previous test")
    
    response = client.get(f"/api/v1/papers/{test_paper_id}/summaries")
    
    # The paper might not have summaries yet if processing isn't complete
    if response.status_code == 200:
        summaries = response.json()
        assert isinstance(summaries, dict)
        
        # If we have summaries, check their structure
        if "summary" in summaries:
            assert isinstance(summaries["summary"], str)
        if "summary_bullet_points" in summaries and summaries["summary_bullet_points"]:
            assert isinstance(summaries["summary_bullet_points"], list)

def test_get_related_papers():
    """Test getting related papers"""
    global test_paper_id
    
    # Skip if we don't have a paper ID
    if not test_paper_id:
        pytest.skip("No paper ID available from previous test")
    
    response = client.get(f"/api/v1/papers/{test_paper_id}/related")
    
    # The paper might not have related papers yet if processing isn't complete
    if response.status_code == 200:
        related_papers = response.json()
        assert isinstance(related_papers, list)
        
        # If we have related papers, check their structure
        if related_papers:
            paper = related_papers[0]
            assert "id" in paper
            assert "title" in paper
            assert "similarity_score" in paper

def test_nonexistent_paper():
    """Test getting a nonexistent paper"""
    # Generate a random UUID that likely doesn't exist
    nonexistent_id = str(uuid.uuid4())
    
    response = client.get(f"/api/v1/papers/{nonexistent_id}")
    assert response.status_code == 404
    
    error = response.json()
    assert "detail" in error 