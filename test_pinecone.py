import os
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from openai import OpenAI
import logging
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

def test_pinecone():
    """Test the Pinecone service by making a simple query."""
    try:
        # Get API keys from environment
        pinecone_api_key = os.getenv("PINECONE_API_KEY")
        pinecone_environment = os.getenv("PINECONE_ENVIRONMENT")
        pinecone_index_name = os.getenv("PINECONE_INDEX")
        openai_api_key = os.getenv("OPENAI_API_KEY")
        
        if not pinecone_api_key:
            logger.error("PINECONE_API_KEY environment variable is not set")
            return False
        if not pinecone_environment:
            logger.error("PINECONE_ENVIRONMENT environment variable is not set")
            return False
        if not pinecone_index_name:
            logger.error("PINECONE_INDEX environment variable is not set")
            return False
        if not openai_api_key:
            logger.error("OPENAI_API_KEY environment variable is not set")
            return False
        
        logger.info(f"Using Pinecone API key: {pinecone_api_key[:8]}...")
        logger.info(f"Using Pinecone environment: {pinecone_environment}")
        logger.info(f"Using Pinecone index: {pinecone_index_name}")
        
        # Initialize Pinecone
        pc = Pinecone(api_key=pinecone_api_key)
        
        # List available indexes
        indexes = pc.list_indexes().names()
        logger.info(f"Available Pinecone indexes: {indexes}")
        
        # Connect to the index
        index = pc.Index(pinecone_index_name)
        
        # Get index stats
        stats = index.describe_index_stats()
        logger.info(f"Index stats: {stats}")
        
        # Generate an embedding for a test query
        client = OpenAI(api_key=openai_api_key)
        embedding_response = client.embeddings.create(
            model="text-embedding-3-large",
            input="What is a brain computer interface?"
        )
        embedding = embedding_response.data[0].embedding
        logger.info(f"Generated embedding with {len(embedding)} dimensions")
        
        # Query the index
        test_paper_id = "test-paper-id-123"  # Use the fixed test paper ID
        query_response = index.query(
            vector=embedding,
            top_k=3,
            include_metadata=True,
            namespace=test_paper_id
        )
        
        logger.info(f"Query response: {query_response}")
        
        # Check if we got any matches
        if query_response.matches:
            logger.info(f"Found {len(query_response.matches)} matches")
            for i, match in enumerate(query_response.matches):
                logger.info(f"Match {i+1}: ID={match.id}, Score={match.score}")
                if hasattr(match, 'metadata') and match.metadata:
                    logger.info(f"Metadata: {match.metadata}")
        else:
            logger.info("No matches found")
        
        return True
    except Exception as e:
        logger.error(f"Error testing Pinecone: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("Testing Pinecone service...")
    success = test_pinecone()
    if success:
        logger.info("Pinecone test completed!")
    else:
        logger.error("Pinecone test failed!") 