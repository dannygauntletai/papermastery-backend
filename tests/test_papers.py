import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime
import uuid

from app.main import app
from app.api.v1.models import PaperMetadata, Author
from app.dependencies import validate_environment

# Create a test client
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

@pytest.fixture
def mock_arxiv_service():
    """Mock the arxiv service for testing."""
    with patch("app.api.v1.endpoints.papers.fetch_paper_metadata") as mock_fetch:
        # Create a sample paper metadata
        mock_metadata = PaperMetadata(
            arxiv_id="2101.12345",
            title="Test Paper Title",
            authors=[Author(name="Test Author", affiliations=["Test University"])],
            abstract="This is a test abstract for the paper.",
            publication_date=datetime.now(),
            categories=["cs.AI"],
            doi=None
        )
        
        mock_fetch.return_value = mock_metadata
        
        with patch("app.api.v1.endpoints.papers.download_and_process_paper") as mock_download:
            mock_download.return_value = ("Full text", ["chunk1", "chunk2"])
            
            with patch("app.api.v1.endpoints.papers.get_related_papers") as mock_related:
                mock_related.return_value = []
                
                with patch("app.services.chunk_service.chunk_text") as mock_chunk:
                    mock_chunks = [
                        {"text": "chunk1", "metadata": {}},
                        {"text": "chunk2", "metadata": {}}
                    ]
                    mock_chunk.return_value = mock_chunks
                    
                    with patch("app.services.pinecone_service.store_chunks") as mock_store:
                        mock_store.return_value = str(uuid.uuid4())
                        
                        with patch("app.services.summarization_service.generate_summaries") as mock_summarize:
                            mock_summarize.return_value = {
                                "beginner": "Beginner summary",
                                "intermediate": "Intermediate summary",
                                "advanced": "Advanced summary"
                            }
                            
                            yield

@pytest.fixture
def mock_supabase_client():
    """Mock the Supabase client for testing."""
    with patch("app.api.v1.endpoints.papers.get_paper_by_arxiv_id") as mock_get_by_arxiv:
        mock_get_by_arxiv.return_value = None
        
        with patch("app.api.v1.endpoints.papers.insert_paper") as mock_insert:
            paper_id = str(uuid.uuid4())
            
            mock_paper = {
                "id": paper_id,
                "arxiv_id": "2101.12345",
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
                "abstract": "This is a related paper abstract."
            },
            {
                "title": "Related Paper 2",
                "authors": [{"name": "Related Author 2", "affiliations": ["University 2"]}],
                "arxiv_id": "2102.12345",
                "abstract": "This is another related paper abstract."
            }
        ]
        yield mock_related

def test_submit_paper(mock_arxiv_service, mock_supabase_client):
    """Test submitting a paper."""
    response = client.post(
        "/api/v1/papers/submit",
        json={"arxiv_link": "https://arxiv.org/abs/2101.12345"}
    )
    
    print(f"Response status: {response.status_code}")
    print(f"Response content: {response.content.decode()}")
    
    assert response.status_code == 202
    assert response.json()["arxiv_id"] == "2101.12345"
    assert response.json()["title"] == "Test Paper Title"

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
            "abstract": "This is a related paper abstract."
        },
        {
            "title": "Related Paper 2",
            "authors": [{"name": "Related Author 2", "affiliations": ["University 2"]}],
            "arxiv_id": "2102.12345",
            "abstract": "This is another related paper abstract."
        }
    ]
    
    # Mock the get_paper_by_id function to return a paper with related papers
    with patch("app.api.v1.endpoints.papers.get_paper_by_id") as mock_get_by_id:
        mock_get_by_id.return_value = {
            "id": paper_id,
            "arxiv_id": "2101.12345",
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