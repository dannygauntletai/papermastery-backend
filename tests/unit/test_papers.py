import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime
import uuid

from app.main import app
from app.api.v1.models import PaperMetadata, Author, SourceType
from app.dependencies import validate_environment, get_current_user

# Create a test client
client = TestClient(app)

# Override validate_environment dependency
@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock the dependencies."""
    # Override the validate_environment dependency
    async def mock_validate_environment():
        return True
    
    # Override the get_current_user dependency to bypass authentication
    async def mock_get_current_user(request=None):
        return str(uuid.uuid4())  # Return a valid UUID string
    
    # Save old overrides and update with our new ones
    old_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[validate_environment] = mock_validate_environment
    app.dependency_overrides[get_current_user] = mock_get_current_user
    
    yield
    
    # Restore original overrides
    app.dependency_overrides = old_overrides

@pytest.fixture
def mock_paper_service():
    """Mock the paper service for testing."""
    with patch("app.api.v1.endpoints.papers.fetch_paper_metadata") as mock_fetch:
        # Create a sample paper metadata
        mock_metadata = PaperMetadata(
            arxiv_id="2101.12345",
            title="Test Paper Title",
            authors=[Author(name="Test Author", affiliations=["Test University"])],
            abstract="This is a test abstract for the paper.",
            publication_date=datetime.now(),
            categories=["cs.AI"],
            doi=None,
            source_type=SourceType.ARXIV,
            source_url="https://arxiv.org/abs/2101.12345"
        )
        
        # Set up the mock to return the sample metadata
        mock_fetch.return_value = mock_metadata
        
        yield mock_fetch

@pytest.fixture
def mock_supabase_client():
    """Mock the Supabase client for testing."""
    with patch("app.api.v1.endpoints.papers.get_paper_by_source") as mock_get_by_source:
        mock_get_by_source.return_value = None
        
        with patch("app.api.v1.endpoints.papers.insert_paper") as mock_insert:
            paper_id = str(uuid.uuid4())
            
            mock_paper = {
                "id": paper_id,
                "arxiv_id": "2101.12345",
                "source_url": "https://arxiv.org/abs/2101.12345",
                "source_type": "arxiv",
                "title": "Test Paper Title",
                "authors": [{"name": "Test Author", "affiliations": ["Test University"]}],
                "abstract": "This is a test abstract for the paper.",
                "publication_date": datetime.now().isoformat(),
                "summaries": None,
                "related_papers": [],
                "tags": {"status": "pending", "category": "cs.AI"}
            }
            
            mock_insert.return_value = mock_paper
            
            with patch("app.api.v1.endpoints.papers.get_paper_by_id") as mock_get_by_id:
                mock_get_by_id.return_value = mock_paper
                
                with patch("app.api.v1.endpoints.papers.update_paper") as mock_update:
                    mock_update.return_value = mock_paper
                    
                    with patch("app.api.v1.endpoints.papers.db_list_papers") as mock_list:
                        mock_list.return_value = [mock_paper]
                        
                        # Mock add_paper_to_user to avoid foreign key constraint error
                        with patch("app.api.v1.endpoints.papers.add_paper_to_user") as mock_add_to_user:
                            mock_add_to_user.return_value = None
                            
                            # Mock create_conversation to avoid foreign key constraint error
                            with patch("app.api.v1.endpoints.papers.create_conversation") as mock_create_conversation:
                                mock_create_conversation.return_value = None
                                
                                yield paper_id

@pytest.fixture
def mock_related_papers():
    """Mock the related papers service for testing."""
    with patch("app.api.v1.endpoints.papers.get_related_papers") as mock_related:
        # Create sample related papers
        mock_related.return_value = [
            {
                "title": "Related Paper 1",
                "authors": [{"name": "Related Author 1", "affiliations": ["University 1"]}],
                "arxiv_id": "2101.54321",
                "source_url": "https://arxiv.org/abs/2101.54321",
                "source_type": "arxiv",
                "abstract": "This is a related paper abstract."
            },
            {
                "title": "Related Paper 2",
                "authors": [{"name": "Related Author 2", "affiliations": ["University 2"]}],
                "arxiv_id": "2102.12345",
                "source_url": "https://arxiv.org/abs/2102.12345",
                "source_type": "arxiv",
                "abstract": "This is another related paper abstract."
            }
        ]
        yield mock_related

def test_submit_paper(mock_paper_service, mock_supabase_client):
    """Test submitting a paper."""
    response = client.post(
        "/api/v1/papers/submit",
        json={"source_url": "https://arxiv.org/abs/2101.12345", "source_type": "arxiv"}
    )
    
    print(f"Response status: {response.status_code}")
    print(f"Response content: {response.content.decode()}")
    
    assert response.status_code == 202
    assert response.json()["arxiv_id"] == "2101.12345"
    assert response.json()["title"] == "Test Paper Title"
    assert response.json()["source_url"] == "https://arxiv.org/abs/2101.12345"
    assert response.json()["source_type"] == "arxiv"

def test_get_paper(mock_supabase_client):
    """Test getting a paper by ID."""
    response = client.get(f"/api/v1/papers/{mock_supabase_client}")
    
    assert response.status_code == 200
    assert response.json()["arxiv_id"] == "2101.12345"

def test_list_papers(mock_supabase_client):
    """Test listing all papers."""
    response = client.get("/api/v1/papers/")
    
    assert response.status_code == 200
    assert len(response.json()) > 0

def test_get_related_papers(mock_dependencies, mock_related_papers):
    """Test retrieving related papers for a paper."""
    # Create a test paper ID
    paper_id = str(uuid.uuid4())
    
    # Mock the get_paper_by_id function to return a paper
    with patch("app.api.v1.endpoints.papers.get_paper_by_id") as mock_get_by_id:
        mock_get_by_id.return_value = {
            "id": paper_id,
            "arxiv_id": "2101.12345",
            "source_url": "https://arxiv.org/abs/2101.12345",
            "source_type": "arxiv",
            "title": "Test Paper",
            "authors": [{"name": "Test Author", "affiliations": ["Test University"]}],
            "abstract": "Test abstract",
            "publication_date": "2023-01-01T00:00:00",
            "processing_status": "completed",
            "related_papers": None  # No related papers stored yet
        }
        
        # Mock the update_paper function
        with patch("app.api.v1.endpoints.papers.update_paper") as mock_update:
            # Make the request
            response = client.get(f"/api/v1/papers/{paper_id}/related")
            
            # Check the response
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["title"] == "Related Paper 1"
            assert data[1]["title"] == "Related Paper 2"
            
            # Verify that get_related_papers was called with the correct arxiv_id
            mock_related_papers.assert_called_once_with("2101.12345")
            
            # Verify that update_paper was called to store the related papers
            mock_update.assert_called_once()

def test_get_related_papers_from_database(mock_dependencies):
    """Test retrieving related papers that are already stored in the database."""
    # Create a test paper ID
    paper_id = str(uuid.uuid4())
    
    # Create sample related papers
    related_papers = [
        {
            "title": "Related Paper 1",
            "authors": [{"name": "Related Author 1", "affiliations": ["University 1"]}],
            "arxiv_id": "2101.54321",
            "source_url": "https://arxiv.org/abs/2101.54321",
            "source_type": "arxiv",
            "abstract": "This is a related paper abstract."
        },
        {
            "title": "Related Paper 2",
            "authors": [{"name": "Related Author 2", "affiliations": ["University 2"]}],
            "arxiv_id": "2102.12345",
            "source_url": "https://arxiv.org/abs/2102.12345",
            "source_type": "arxiv",
            "abstract": "This is another related paper abstract."
        }
    ]
    
    # Mock the get_paper_by_id function to return a paper with related papers
    with patch("app.api.v1.endpoints.papers.get_paper_by_id") as mock_get_by_id:
        mock_get_by_id.return_value = {
            "id": paper_id,
            "arxiv_id": "2101.12345",
            "source_url": "https://arxiv.org/abs/2101.12345",
            "source_type": "arxiv",
            "title": "Test Paper",
            "authors": [{"name": "Test Author", "affiliations": ["Test University"]}],
            "abstract": "Test abstract",
            "publication_date": "2023-01-01T00:00:00",
            "processing_status": "completed",
            "related_papers": related_papers  # Related papers already stored
        }
        
        # Mock the get_related_papers function to ensure it's not called
        with patch("app.api.v1.endpoints.papers.get_related_papers") as mock_related:
            # Make the request
            response = client.get(f"/api/v1/papers/{paper_id}/related")
            
            # Check the response
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["title"] == "Related Paper 1"
            assert data[1]["title"] == "Related Paper 2"
            
            # Verify that get_related_papers was NOT called
            # This is because the related papers were already in the database
            mock_related.assert_not_called()

def test_get_related_papers_paper_not_found(mock_dependencies):
    """Test retrieving related papers for a non-existent paper."""
    # Create a test paper ID
    paper_id = str(uuid.uuid4())
    
    # Mock the get_paper_by_id function to return None
    with patch("app.api.v1.endpoints.papers.get_paper_by_id") as mock_get_by_id:
        mock_get_by_id.return_value = None
        
        # Make the request
        response = client.get(f"/api/v1/papers/{paper_id}/related")
        
        # Check the response
        assert response.status_code == 404
        assert response.json()["detail"] == f"Paper with ID {paper_id} not found" 