import uuid
from typing import Dict, Any
import pytest
import httpx


@pytest.mark.asyncio
async def test_chat_invalid_query() -> None:
    """Test chat with invalid query (empty or too long)."""
    test_paper_id = str(uuid.uuid4())
    base_url = "http://localhost:8001"
    
    async with httpx.AsyncClient() as client:
        # Test empty query
        empty_query_response = await client.post(
            f"{base_url}/api/v1/papers/{test_paper_id}/chat",
            json={"query": ""}
        )
        
        # We expect a 422 Unprocessable Entity for validation errors
        assert empty_query_response.status_code == 422
        
        # Test query that's too long (over 1000 characters)
        long_query = "a" * 1001
        long_query_response = await client.post(
            f"{base_url}/api/v1/papers/{test_paper_id}/chat",
            json={"query": long_query}
        )
        
        # We expect a 422 Unprocessable Entity for validation errors
        assert long_query_response.status_code == 422
        
        # Verify error response structure
        response_data = long_query_response.json()
        assert "detail" in response_data 