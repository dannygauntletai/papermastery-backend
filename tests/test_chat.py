import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
from uuid import UUID, uuid4
import json
import uuid

from app.main import app
from app.core.config import APP_ENV
from app.services.llm_service import mock_generate_response
from app.dependencies import rate_limit

# Create a simple mock for the rate limit dependency
async def mock_rate_limit(*args, **kwargs):
    return True

# Override the rate limit dependency for testing
app.dependency_overrides[rate_limit] = mock_rate_limit

client = TestClient(app)

# Sample test data
TEST_PAPER_ID = str(uuid.uuid4())
TEST_QUERY = "What are the main findings of this paper?"
TEST_RESPONSE = "The main findings are..."
TEST_CHUNKS = [
    {
        "chunk_id": "chunk_1",
        "text": "This is the first relevant chunk of text.",
        "metadata": {"paper_id": TEST_PAPER_ID}
    },
    {
        "chunk_id": "chunk_2",
        "text": "This is the second relevant chunk of text.",
        "metadata": {"paper_id": TEST_PAPER_ID}
    }
]

# Mock responses
MOCK_PAPER = {
    "id": TEST_PAPER_ID,
    "arxiv_id": "2101.12345",
    "title": "Test Paper Title",
    "authors": [{"name": "Test Author", "affiliations": ["Test University"]}],
    "abstract": "This is a test abstract.",
    "publication_date": "2023-01-01T00:00:00Z",
    "embedding_id": TEST_PAPER_ID  # This indicates the paper has been processed
}

MOCK_RESPONSE_DATA = {
    "response": TEST_RESPONSE,
    "query": TEST_QUERY,
    "sources": TEST_CHUNKS
}


@pytest.fixture
def mock_get_paper_by_id():
    """Mock the get_paper_by_id function."""
    with patch("app.api.v1.endpoints.chat.get_paper_by_id") as mock:
        async_mock = AsyncMock()
        async_mock.return_value = MOCK_PAPER
        mock.return_value = async_mock
        yield mock


@pytest.fixture
def mock_search_similar_chunks():
    """Mock the search_similar_chunks function."""
    with patch("app.api.v1.endpoints.chat.search_similar_chunks") as mock:
        async_mock = AsyncMock()
        async_mock.return_value = TEST_CHUNKS
        mock.return_value = async_mock
        yield mock


@pytest.fixture
def mock_generate_response():
    """Mock the generate_response function."""
    with patch("app.api.v1.endpoints.chat.generate_response") as mock:
        async_mock = AsyncMock()
        async_mock.return_value = MOCK_RESPONSE_DATA
        mock.return_value = async_mock
        yield mock


@pytest.fixture
def mock_mock_generate_response():
    """Mock the mock_generate_response function."""
    with patch("app.api.v1.endpoints.chat.mock_generate_response") as mock:
        async_mock = AsyncMock()
        async_mock.return_value = MOCK_RESPONSE_DATA
        mock.return_value = async_mock
        yield mock


def test_chat_with_paper_success(mock_get_paper_by_id, mock_search_similar_chunks, mock_generate_response):
    """Test successful chat interaction with a paper."""
    # Set APP_ENV to 'development' to use the real generate_response function
    with patch("app.api.v1.endpoints.chat.APP_ENV", "development"):
        response = client.post(
            f"/api/v1/papers/{TEST_PAPER_ID}/chat?args=&kwargs=",
            json={"query": TEST_QUERY}
        )
        
        print("Response status:", response.status_code)
        print("Response body:", json.dumps(response.json(), indent=2))
        
        assert response.status_code == 200
        data = response.json()
        assert data["response"] == TEST_RESPONSE
        assert data["query"] == TEST_QUERY
        assert data["paper_id"] == TEST_PAPER_ID
        assert len(data["sources"]) == len(TEST_CHUNKS)


def test_chat_with_paper_testing_env(mock_get_paper_by_id, mock_search_similar_chunks, mock_mock_generate_response):
    """Test chat interaction in testing environment."""
    # Set APP_ENV to 'testing' to use the mock_generate_response function
    with patch("app.api.v1.endpoints.chat.APP_ENV", "testing"):
        response = client.post(
            f"/api/v1/papers/{TEST_PAPER_ID}/chat?args=&kwargs=",
            json={"query": TEST_QUERY}
        )
        
        print("Response status:", response.status_code)
        print("Response body:", json.dumps(response.json(), indent=2))
        
        assert response.status_code == 200
        data = response.json()
        assert data["response"] == TEST_RESPONSE
        assert data["query"] == TEST_QUERY
        assert data["paper_id"] == TEST_PAPER_ID
        assert len(data["sources"]) == len(TEST_CHUNKS)


def test_chat_paper_not_found(mock_search_similar_chunks, mock_generate_response):
    """Test chat with non-existent paper."""
    with patch("app.api.v1.endpoints.chat.get_paper_by_id") as mock:
        async_mock = AsyncMock()
        async_mock.return_value = None
        mock.return_value = async_mock
        
        response = client.post(
            f"/api/v1/papers/{TEST_PAPER_ID}/chat?args=&kwargs=",
            json={"query": TEST_QUERY}
        )
        
        print("Response status:", response.status_code)
        print("Response body:", json.dumps(response.json(), indent=2))
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


def test_chat_paper_not_processed(mock_search_similar_chunks, mock_generate_response):
    """Test chat with paper that hasn't been processed yet."""
    unprocessed_paper = MOCK_PAPER.copy()
    unprocessed_paper["embedding_id"] = None
    
    with patch("app.api.v1.endpoints.chat.get_paper_by_id") as mock:
        async_mock = AsyncMock()
        async_mock.return_value = unprocessed_paper
        mock.return_value = async_mock
        
        response = client.post(
            f"/api/v1/papers/{TEST_PAPER_ID}/chat?args=&kwargs=",
            json={"query": TEST_QUERY}
        )
        
        print("Response status:", response.status_code)
        print("Response body:", json.dumps(response.json(), indent=2))
        
        assert response.status_code == 422
        assert "not been fully processed" in response.json()["detail"].lower()


def test_chat_no_relevant_chunks(mock_get_paper_by_id, mock_generate_response):
    """Test chat when no relevant chunks are found."""
    with patch("app.api.v1.endpoints.chat.search_similar_chunks") as mock:
        async_mock = AsyncMock()
        async_mock.return_value = []
        mock.return_value = async_mock
        
        response = client.post(
            f"/api/v1/papers/{TEST_PAPER_ID}/chat?args=&kwargs=",
            json={"query": TEST_QUERY}
        )
        
        print("Response status:", response.status_code)
        print("Response body:", json.dumps(response.json(), indent=2))
        
        assert response.status_code == 200
        data = response.json()
        assert "couldn't find specific information" in data["response"].lower()
        assert len(data["sources"]) == 0


def test_chat_invalid_query():
    """Test chat with invalid query (empty or too long)."""
    # Test empty query
    response = client.post(
        f"/api/v1/papers/{TEST_PAPER_ID}/chat?args=&kwargs=",
        json={"query": ""}
    )
    print("Empty query response status:", response.status_code)
    print("Empty query response body:", json.dumps(response.json(), indent=2))
    assert response.status_code == 422
    
    # Test query that's too long
    response = client.post(
        f"/api/v1/papers/{TEST_PAPER_ID}/chat?args=&kwargs=",
        json={"query": "a" * 1001}
    )
    print("Long query response status:", response.status_code)
    print("Long query response body:", json.dumps(response.json(), indent=2))
    assert response.status_code == 422


def test_chat_error_handling(mock_get_paper_by_id):
    """Test error handling in chat endpoint."""
    with patch("app.api.v1.endpoints.chat.search_similar_chunks") as mock:
        mock.side_effect = Exception("Test error")
        
        response = client.post(
            f"/api/v1/papers/{TEST_PAPER_ID}/chat?args=&kwargs=",
            json={"query": TEST_QUERY}
        )
        
        print("Response status:", response.status_code)
        print("Response body:", json.dumps(response.json(), indent=2))
        
        assert response.status_code == 500
        assert "error generating chat response" in response.json()["detail"].lower() 