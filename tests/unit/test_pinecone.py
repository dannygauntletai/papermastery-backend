import os
import pytest
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()

@pytest.fixture
def pinecone_client() -> Optional[Pinecone]:
    """Create and return a Pinecone client."""
    pinecone_api_key = os.getenv("PINECONE_API_KEY")
    if not pinecone_api_key:
        pytest.skip("PINECONE_API_KEY environment variable is not set")
    
    return Pinecone(api_key=pinecone_api_key)

@pytest.fixture
def pinecone_index_name() -> str:
    """Get the Pinecone index name from environment variables."""
    index_name = os.getenv("PINECONE_INDEX")
    if not index_name:
        pytest.skip("PINECONE_INDEX environment variable is not set")
    
    return index_name

@pytest.fixture
def openai_client() -> Optional[OpenAI]:
    """Create and return an OpenAI client."""
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY environment variable is not set")
    
    return OpenAI(api_key=openai_api_key)

def test_pinecone_connection(pinecone_client: Pinecone, pinecone_index_name: str):
    """Test that we can connect to the Pinecone index."""
    # List available indexes
    indexes = pinecone_client.list_indexes().names()
    assert indexes is not None
    assert len(indexes) > 0
    
    # Connect to the index
    index = pinecone_client.Index(pinecone_index_name)
    assert index is not None
    
    # Get index stats
    stats = index.describe_index_stats()
    assert stats is not None
    assert "dimension" in stats
    assert "namespaces" in stats
    assert "total_vector_count" in stats

def test_pinecone_query_embedding(pinecone_client: Pinecone, pinecone_index_name: str, openai_client: OpenAI):
    """Test that we can query Pinecone with an embedding from OpenAI."""
    # Generate an embedding
    embedding_response = openai_client.embeddings.create(
        input="Hello, world!",
        model="text-embedding-3-small"
    )
    
    embedding = embedding_response.data[0].embedding
    assert embedding is not None
    assert len(embedding) > 0
    
    # Query the index
    index = pinecone_client.Index(pinecone_index_name)
    query_response = index.query(
        vector=embedding,
        top_k=5,
        include_metadata=True
    )
    
    # We may not have matching vectors, but the query should execute
    assert query_response is not None
    assert "matches" in query_response

def test_pinecone_upsert_fetch_delete(pinecone_client: Pinecone, pinecone_index_name: str, openai_client: OpenAI):
    """Test the full cycle of upserting, fetching, and deleting a vector."""
    # Generate a test vector
    embedding_response = openai_client.embeddings.create(
        input="Test vector for deletion",
        model="text-embedding-3-small"
    )
    
    embedding = embedding_response.data[0].embedding
    test_id = f"test-{os.getenv('USER', 'unknown')}-{os.urandom(4).hex()}"
    
    index = pinecone_client.Index(pinecone_index_name)
    
    try:
        # Upsert the vector
        upsert_response = index.upsert(
            vectors=[
                {
                    "id": test_id,
                    "values": embedding,
                    "metadata": {"test": True, "content": "Test vector"}
                }
            ],
            namespace="test"
        )
        
        assert upsert_response is not None
        assert "upserted_count" in upsert_response
        assert upsert_response["upserted_count"] == 1
        
        # Fetch the vector
        fetch_response = index.fetch(ids=[test_id], namespace="test")
        assert fetch_response is not None
        assert "vectors" in fetch_response
        assert test_id in fetch_response["vectors"]
        assert "metadata" in fetch_response["vectors"][test_id]
        assert fetch_response["vectors"][test_id]["metadata"]["test"] is True
        
    finally:
        # Delete the vector
        delete_response = index.delete(ids=[test_id], namespace="test")
        assert delete_response is not None 