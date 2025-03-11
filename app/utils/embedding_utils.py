from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Dict, Any, Union
from app.core.logger import get_logger

logger = get_logger(__name__)

# Load the embedding model
model = None

def get_embedding_model():
    """
    Get or initialize the embedding model.
    
    Returns:
        SentenceTransformer model instance
    """
    global model
    if model is None:
        # Load a pre-trained model - all-MiniLM-L6-v2 is a good balance of performance and speed
        model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("Initialized embedding model: all-MiniLM-L6-v2")
    return model

async def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for a list of text chunks.
    
    Args:
        texts: List of text chunks to embed
        
    Returns:
        List of embeddings (as float lists)
    """
    model = get_embedding_model()
    
    # Generate embeddings
    embeddings = model.encode(texts)
    
    # Convert numpy arrays to lists for serialization
    return embeddings.tolist()

async def create_pinecone_records(
    texts: List[str],
    metadata_list: List[Dict[str, Any]],
    paper_id: str
) -> List[Dict[str, Any]]:
    """
    Create records for Pinecone with embeddings and metadata.
    
    Args:
        texts: List of text chunks
        metadata_list: List of metadata dictionaries for each chunk
        paper_id: ID of the parent paper
        
    Returns:
        List of records for Pinecone insertion
    """
    # Generate embeddings for all texts
    embeddings = await generate_embeddings(texts)
    
    # Create records for Pinecone
    records = []
    for i, (embedding, metadata) in enumerate(zip(embeddings, metadata_list)):
        # Create a unique ID for each chunk
        chunk_id = f"{paper_id}_chunk_{i}"
        
        # Add the embedding and metadata to the record
        record = {
            "id": chunk_id,
            "values": embedding,
            "metadata": {
                **metadata,
                "paper_id": paper_id,
                "chunk_index": i
            }
        }
        
        records.append(record)
        
    logger.info(f"Created {len(records)} Pinecone records for paper {paper_id}")
    return records 