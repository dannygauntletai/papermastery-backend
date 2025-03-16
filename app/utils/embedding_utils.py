import openai
from openai import OpenAI
import asyncio
from typing import List, Dict, Any
import os
from dotenv import load_dotenv
from app.core.logger import get_logger
from app.core.config import get_settings

# Load environment variables from .env file
load_dotenv()

logger = get_logger(__name__)
settings = get_settings()

# Initialize OpenAI client
try:
    # Get API key directly from environment for consistency
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        api_key = settings.OPENAI_API_KEY
        # Ensure it's also in the environment
        os.environ["OPENAI_API_KEY"] = api_key
    
    client = OpenAI(api_key=api_key)
    logger.info(f"OpenAI client initialized with API key: {api_key[:8]}... in embedding_utils.py")
except Exception as e:
    logger.error(f"Error initializing OpenAI client: {str(e)}")
    client = None

EMBEDDING_MODEL = settings.OPENAI_EMBEDDING_MODEL  # Use the model from settings

async def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for a list of text chunks using OpenAI embeddings.
    
    Args:
        texts: List of text chunks to embed
        
    Returns:
        List of embeddings (as float lists), OpenAI embeddings are 3072 dimensions
    """
    if not texts:
        logger.warning("No texts provided for embedding generation")
        return []
    
    if client is None:
        logger.error("OpenAI client not initialized, cannot generate embeddings")
        raise ValueError("OpenAI client not initialized")
    
    try:
        logger.info(f"Generating embeddings for {len(texts)} texts using OpenAI model {EMBEDDING_MODEL}")
        
        # Process in batches to avoid rate limits and large payload issues
        batch_size = 10  # OpenAI can handle more, but this is a safe batch size
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            # Handle empty strings which OpenAI API rejects
            batch = [text if text.strip() else " " for text in batch]
            
            # Log first text in batch (shortened for readability)
            first_text = batch[0][:100] + "..." if batch else ""
            logger.info(f"Batch {i//batch_size + 1}: Generating embeddings for {len(batch)} texts. First text: {first_text}")
            
            # Use the correct client instance
            response = await asyncio.to_thread(
                client.embeddings.create,
                model=EMBEDDING_MODEL,
                input=batch
            )
            
            # Extract embeddings from response
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)
            
            # Log information about dimensions
            if batch_embeddings:
                logger.info(f"Generated embeddings with {len(batch_embeddings[0])} dimensions")
            
            # Add a small delay to avoid rate limiting
            if i + batch_size < len(texts):
                await asyncio.sleep(0.5)
        
        logger.info(f"Successfully generated {len(all_embeddings)} embeddings using OpenAI. First embedding has {len(all_embeddings[0]) if all_embeddings else 0} dimensions")
        return all_embeddings
        
    except Exception as e:
        logger.error(f"Error generating OpenAI embeddings: {str(e)}")
        raise 