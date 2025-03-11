import pinecone
from pinecone import Pinecone, ServerlessSpec
from typing import List, Dict, Any, Optional
import asyncio
from uuid import UUID

from app.core.logger import get_logger
from app.core.config import PINECONE_API_KEY, PINECONE_ENVIRONMENT, PINECONE_INDEX
from app.core.exceptions import PineconeError
from app.utils.embedding_utils import generate_embeddings

logger = get_logger(__name__)
index = None

# Initialize Pinecone
try:
    # Create Pinecone client
    pc = Pinecone(api_key=PINECONE_API_KEY)
    logger.info(f"Pinecone initialized with environment: {PINECONE_ENVIRONMENT}")
    
    # Check if index exists, create it if not
    if PINECONE_INDEX not in [idx['name'] for idx in pc.list_indexes()]:
        logger.info(f"Creating Pinecone index: {PINECONE_INDEX}")
        pc.create_index(
            name=PINECONE_INDEX,
            dimension=384,  # Dimension for all-MiniLM-L6-v2 model
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region=PINECONE_ENVIRONMENT
            )
        )
    
    # Connect to the index
    index = pc.Index(PINECONE_INDEX)
    logger.info(f"Connected to Pinecone index: {PINECONE_INDEX}")
    
except Exception as e:
    logger.error(f"Error initializing Pinecone: {str(e)}")
    # Don't raise exception here, as it would prevent the app from starting
    # Instead, the error will be handled when the service is used
    index = None


async def store_chunks(
    paper_id: UUID,
    chunks: List[Dict[str, Any]]
) -> str:
    """
    Store chunks in Pinecone with embeddings.
    
    Args:
        paper_id: The UUID of the paper
        chunks: List of text chunks with metadata
        
    Returns:
        Embedding ID (namespace in Pinecone)
        
    Raises:
        PineconeError: If there's an error storing chunks in Pinecone
    """
    if index is None:
        logger.error("Pinecone index not initialized")
        raise PineconeError("Pinecone index not initialized")
    
    try:
        logger.info(f"Storing {len(chunks)} chunks in Pinecone for paper ID: {paper_id}")
        
        # Extract texts from chunks
        texts = [chunk["text"] for chunk in chunks]
        
        # Generate embeddings for texts
        embeddings = await generate_embeddings(texts)
        
        # Create Pinecone records
        records = []
        for i, (text, embedding) in enumerate(zip(texts, embeddings)):
            # Create a unique ID for each chunk
            chunk_id = f"{paper_id}_chunk_{i}"
            
            # Get the metadata from the chunk
            metadata = chunks[i].get("metadata", {})
            metadata["paper_id"] = str(paper_id)
            metadata["text"] = text[:1000]  # Store first 1000 chars of text in metadata
            
            # Create the record
            record = {
                "id": chunk_id,
                "values": embedding,
                "metadata": metadata
            }
            records.append(record)
        
        # Use the paper_id as the namespace
        namespace = str(paper_id)
        
        # Upsert records in batches (Pinecone may have limits on batch size)
        batch_size = 100
        for i in range(0, len(records), batch_size):
            batch = records[i:i+batch_size]
            # Use asyncio.to_thread to run this blocking operation in a thread
            await asyncio.to_thread(
                index.upsert,
                vectors=batch,
                namespace=namespace
            )
        
        logger.info(f"Successfully stored {len(chunks)} chunks in Pinecone for paper ID: {paper_id}")
        
        return namespace
        
    except Exception as e:
        logger.error(f"Error storing chunks in Pinecone for paper ID {paper_id}: {str(e)}")
        raise PineconeError(f"Error storing chunks in Pinecone: {str(e)}")


async def search_similar_chunks(
    query: str,
    paper_id: Optional[UUID] = None,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Search for similar chunks in Pinecone.
    
    Args:
        query: The query text
        paper_id: Optional paper ID to filter results
        top_k: Number of results to return
        
    Returns:
        List of similar chunks with metadata and similarity scores
        
    Raises:
        PineconeError: If there's an error searching in Pinecone
    """
    if index is None:
        logger.error("Pinecone index not initialized")
        raise PineconeError("Pinecone index not initialized")
    
    try:
        logger.info(f"Searching for similar chunks with query: {query[:50]}...")
        
        # Generate embedding for the query
        query_embedding = (await generate_embeddings([query]))[0]
        
        # Set namespace if paper_id is provided
        namespace = str(paper_id) if paper_id else None
        
        # Perform the search
        results = await asyncio.to_thread(
            index.query,
            vector=query_embedding,
            namespace=namespace,
            top_k=top_k,
            include_metadata=True
        )
        
        # Format the results
        formatted_results = []
        for match in results.get("matches", []):
            formatted_results.append({
                "chunk_id": match["id"],
                "score": match["score"],
                "metadata": match["metadata"],
                "text": match["metadata"].get("text", "")
            })
        
        logger.info(f"Found {len(formatted_results)} similar chunks for query")
        
        return formatted_results
        
    except Exception as e:
        logger.error(f"Error searching in Pinecone: {str(e)}")
        raise PineconeError(f"Error searching in Pinecone: {str(e)}")


async def delete_paper_embeddings(paper_id: UUID) -> bool:
    """
    Delete all embeddings for a paper from Pinecone.
    
    Args:
        paper_id: The UUID of the paper
        
    Returns:
        True if successful
        
    Raises:
        PineconeError: If there's an error deleting embeddings
    """
    if index is None:
        logger.error("Pinecone index not initialized")
        raise PineconeError("Pinecone index not initialized")
    
    try:
        logger.info(f"Deleting embeddings for paper ID: {paper_id}")
        
        # Use the paper_id as the namespace
        namespace = str(paper_id)
        
        # Delete all vectors in the namespace
        await asyncio.to_thread(
            index.delete,
            delete_all=True,
            namespace=namespace
        )
        
        logger.info(f"Successfully deleted embeddings for paper ID: {paper_id}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error deleting embeddings for paper ID {paper_id}: {str(e)}")
        raise PineconeError(f"Error deleting embeddings: {str(e)}") 