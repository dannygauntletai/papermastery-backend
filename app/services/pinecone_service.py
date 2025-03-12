import pinecone
from pinecone import Pinecone, ServerlessSpec
from typing import List, Dict, Any, Optional, Tuple, Union
import asyncio
import os
from dotenv import load_dotenv
from uuid import UUID
import numpy as np
import logging
from datetime import datetime
from langchain_pinecone import PineconeVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from app.core.logger import get_logger
from app.core.config import PINECONE_API_KEY, PINECONE_ENVIRONMENT, PINECONE_INDEX, OPENAI_API_KEY
from app.core.exceptions import PineconeError
from app.utils.embedding_utils import generate_embeddings

# Load environment variables from .env file
load_dotenv()

logger = get_logger(__name__)
# Declare global variables
global index, pc, langchain_embeddings, primary_index_name, fallback_index_name, available_indexes, vector_dimension
index = None
pc = None
# LangChain OpenAI embeddings instance
langchain_embeddings = None
primary_index_name = None
fallback_index_name = None
available_indexes = []
vector_dimension = 3072  # Default to 3072 dimensions

# Get API key directly from environment for consistency
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    api_key = OPENAI_API_KEY
    # Ensure it's also in the environment
    os.environ["OPENAI_API_KEY"] = api_key
    logger.info(f"Setting OpenAI API key in environment in pinecone_service.py: {api_key[:8]}...")

# Initialize Pinecone
try:
    # Create Pinecone client
    pc = Pinecone(api_key=PINECONE_API_KEY)
    logger.info(f"Pinecone initialized with environment: {PINECONE_ENVIRONMENT}")
    
    # Initialize LangChain OpenAI embeddings
    try:
        langchain_embeddings = OpenAIEmbeddings(
            model="text-embedding-3-large",  # 3072 dimensions
            openai_api_key=api_key
        )
        logger.info(f"LangChain OpenAI embeddings initialized successfully with API key: {api_key[:8]}...")
    except Exception as e:
        logger.error(f"Error initializing LangChain OpenAI embeddings: {str(e)}")
        langchain_embeddings = None
    
    # Primary index name from config
    primary_index_name = PINECONE_INDEX
    # Fallback index name
    fallback_index_name = "papermastery-fallback"
    
    # Set correct vector dimension for embeddings
    vector_dimension = 3072  # Using 3072 dimensions to match existing index
    
    # List available indexes
    available_indexes = [idx['name'] for idx in pc.list_indexes()]
    logger.info(f"Available Pinecone indexes: {available_indexes}")
    
    # Use the primary index if available
    if primary_index_name in available_indexes:
        logger.info(f"Using existing primary index: {primary_index_name}")
        index = pc.Index(primary_index_name)
    # If primary index doesn't exist, check for fallback
    elif fallback_index_name in available_indexes:
        logger.info(f"Primary index not found. Using fallback index: {fallback_index_name}")
        index = pc.Index(fallback_index_name)
    # If neither exists, create the fallback index
    else:
        logger.info(f"Creating fallback index: {fallback_index_name}")
        pc.create_index(
            name=fallback_index_name,
            dimension=vector_dimension,  # Using 3072 dimensions for consistency
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1"
            )
        )
        index = pc.Index(fallback_index_name)
    
    logger.info(f"Connected to Pinecone index: {index.describe_index_stats()['dimension']}-dimensional index")
    
except Exception as e:
    logger.error(f"Error initializing Pinecone: {str(e)}")
    pc = None
    index = None


async def process_pdf_with_langchain(
    pdf_path: str, 
    paper_id: UUID, 
    chunk_size: int = 1000, 
    chunk_overlap: int = 200
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Process a PDF file using LangChain components and store in Pinecone.
    
    Args:
        pdf_path: Path to the PDF file
        paper_id: The UUID of the paper
        chunk_size: Size of text chunks
        chunk_overlap: Overlap between chunks
        
    Returns:
        Tuple of (chunks, metadata)
    """
    logger.info(f"Processing PDF with LangChain: {pdf_path} for paper ID: {paper_id}")
    
    if langchain_embeddings is None:
        logger.error("LangChain OpenAI embeddings not initialized")
        raise PineconeError("LangChain OpenAI embeddings not initialized")
    
    try:
        # Load the PDF using PyPDFLoader
        loader = PyPDFLoader(pdf_path)
        documents = loader.load()
        logger.info(f"Loaded {len(documents)} pages from PDF")
        
        # Split text into chunks using RecursiveCharacterTextSplitter
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ".", " ", ""]
        )
        chunks = text_splitter.split_documents(documents)
        logger.info(f"Split into {len(chunks)} chunks")
        
        # Add metadata to chunks
        for i, chunk in enumerate(chunks):
            chunk.metadata["paper_id"] = str(paper_id)
            chunk.metadata["chunk_index"] = i
            
            # Identify potential sections based on content
            text_lower = chunk.page_content.lower()
            if any(term in text_lower for term in ["abstract", "summary"]):
                chunk.metadata["is_abstract"] = True
            if any(term in text_lower for term in ["introduction", "intro"]):
                chunk.metadata["is_introduction"] = True
            if any(term in text_lower for term in ["method", "methodology"]):
                chunk.metadata["is_methodology"] = True
            if any(term in text_lower for term in ["result", "findings"]):
                chunk.metadata["is_results"] = True
            if any(term in text_lower for term in ["discussion", "implications"]):
                chunk.metadata["is_discussion"] = True
            if any(term in text_lower for term in ["conclusion", "concluding"]):
                chunk.metadata["is_conclusion"] = True
        
        # Store in Pinecone using LangChain
        try:
            # Determine which index to use
            index_name = fallback_index_name if fallback_index_name in available_indexes else primary_index_name
            namespace = str(paper_id)
            
            # Create vector store from documents
            vector_store = await asyncio.to_thread(
                PineconeVectorStore.from_documents,
                documents=chunks,
                embedding=langchain_embeddings,
                index_name=index_name,
                namespace=namespace
            )
            logger.info(f"Successfully stored chunks in Pinecone using LangChain for paper ID: {paper_id}")
            
            # Convert LangChain documents to a format compatible with the rest of the app
            formatted_chunks = []
            for i, chunk in enumerate(chunks):
                formatted_chunks.append({
                    "text": chunk.page_content,
                    "metadata": chunk.metadata
                })
            
            return formatted_chunks, chunks
            
        except Exception as e:
            logger.error(f"Error storing chunks in Pinecone using LangChain: {str(e)}")
            raise PineconeError(f"Error storing chunks in Pinecone using LangChain: {str(e)}")
    
    except Exception as e:
        logger.error(f"Error processing PDF with LangChain: {str(e)}")
        raise PineconeError(f"Error processing PDF with LangChain: {str(e)}")


async def store_chunks_langchain(
    paper_id: UUID,
    chunks: List[Dict[str, Any]]
) -> str:
    """
    Store chunks in Pinecone using LangChain for compatibility with LangChain query methods.
    
    Args:
        paper_id: UUID of the paper the chunks belong to
        chunks: List of chunks with text and metadata
        
    Returns:
        Namespace where the chunks were stored
        
    Raises:
        PineconeError: If there's an error storing chunks in Pinecone
    """
    
    try:
        logger.info(f"Storing {len(chunks)} chunks in Pinecone using LangChain for paper ID: {paper_id}")
        
        # Extract texts from chunks
        texts = [chunk["text"] for chunk in chunks]
        
        # Generate embeddings using OpenAI
        embeddings = await generate_embeddings(texts)
        
        if embeddings and len(embeddings) > 0:
            embedding_dim = len(embeddings[0])
            logger.info(f"Generated embeddings with dimension: {embedding_dim}")
            
            # Get index dimension from Pinecone
            try:
                index_stats = index.describe_index_stats()
                index_dim = index_stats.get('dimension')
                logger.info(f"Pinecone index dimension: {index_dim}")
                
                if index_dim and embedding_dim != index_dim:
                    logger.warning(f"Dimension mismatch: Embeddings ({embedding_dim}) vs Pinecone index ({index_dim})")
            except Exception as stats_error:
                logger.warning(f"Could not get index dimension: {str(stats_error)}")
        
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
        try:
            logger.info(f"Upserting {len(records)} records to Pinecone index in batches of {batch_size}")
            for i in range(0, len(records), batch_size):
                batch = records[i:i+batch_size]
                # Use asyncio.to_thread to run this blocking operation in a thread
                await asyncio.to_thread(
                    index.upsert,
                    vectors=batch,
                    namespace=namespace
                )
                logger.info(f"Successfully upserted batch {i//batch_size + 1} of {(len(records) + batch_size - 1) // batch_size}")
            logger.info(f"Successfully stored {len(chunks)} chunks in Pinecone for paper ID: {paper_id}")
        except Exception as dim_error:
            # Check if it's a dimension mismatch error
            if "dimension" in str(dim_error).lower() and "does not match" in str(dim_error).lower():
                logger.warning(f"Dimension mismatch error from Pinecone: {str(dim_error)}")
                logger.warning(f"First vector dimension: {len(records[0]['values']) if records else 'unknown'}")
                
                # Re-initialize with fallback index
                pc = Pinecone(api_key=PINECONE_API_KEY)
                fallback_index_name = "papermastery-fallback"
                vector_dimension = 3072  # Using 3072 dimensions to match existing index
                available_indexes = [idx['name'] for idx in pc.list_indexes()]
                
                # Create fallback index if it doesn't exist
                if fallback_index_name not in available_indexes:
                    logger.info(f"Creating fallback index: {fallback_index_name}")
                    pc.create_index(
                        name=fallback_index_name,
                        dimension=vector_dimension,  # Using 3072 dimensions for consistency
                        metric="cosine",
                        spec=ServerlessSpec(
                            cloud="aws",
                            region="us-east-1"
                        )
                    )
                
                # Connect to fallback index
                index = pc.Index(fallback_index_name)
                logger.info(f"Reconnected to fallback Pinecone index: {fallback_index_name}")
                
                # Retry upsert with fallback index
                for i in range(0, len(records), batch_size):
                    batch = records[i:i+batch_size]
                    await asyncio.to_thread(
                        index.upsert,
                        vectors=batch,
                        namespace=namespace
                    )
                logger.info(f"Successfully stored {len(chunks)} chunks in fallback index for paper ID: {paper_id}")
            else:
                # Re-raise if it's not a dimension mismatch error
                raise
        
        return namespace
        
    except Exception as e:
        logger.error(f"Error storing chunks in Pinecone for paper ID {paper_id}: {str(e)}")
        raise PineconeError(f"Error storing chunks in Pinecone: {str(e)}")


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
    # Try using LangChain first if available
    if langchain_embeddings is not None:
        try:
            return await store_chunks_langchain(paper_id, chunks)
        except Exception as e:
            logger.warning(f"LangChain storage failed, falling back to default method: {str(e)}")
            # Fall back to the original method if LangChain fails
    
    global index
    
    if index is None:
        logger.error("Pinecone index not initialized")
        raise PineconeError("Pinecone index not initialized")
    
    try:
        logger.info(f"Storing {len(chunks)} chunks in Pinecone for paper ID: {paper_id}")
        
        # Extract texts from chunks
        texts = [chunk["text"] for chunk in chunks]
        
        # Generate embeddings for texts
        embeddings = await generate_embeddings(texts)
        
        # Check embedding dimensions
        if embeddings:
            embedding_dim = len(embeddings[0])
            logger.info(f"Embeddings generated with dimension: {embedding_dim}")
            
            # Get index dimension from Pinecone
            try:
                index_stats = index.describe_index_stats()
                index_dim = index_stats.get('dimension')
                logger.info(f"Pinecone index dimension: {index_dim}")
                
                if index_dim and embedding_dim != index_dim:
                    logger.warning(f"Dimension mismatch: Embeddings ({embedding_dim}) vs Pinecone index ({index_dim})")
            except Exception as stats_error:
                logger.warning(f"Could not get index dimension: {str(stats_error)}")
        
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
        try:
            logger.info(f"Upserting {len(records)} records to Pinecone index in batches of {batch_size}")
            for i in range(0, len(records), batch_size):
                batch = records[i:i+batch_size]
                # Use asyncio.to_thread to run this blocking operation in a thread
                await asyncio.to_thread(
                    index.upsert,
                    vectors=batch,
                    namespace=namespace
                )
                logger.info(f"Successfully upserted batch {i//batch_size + 1} of {(len(records) + batch_size - 1) // batch_size}")
            logger.info(f"Successfully stored {len(chunks)} chunks in Pinecone for paper ID: {paper_id}")
        except Exception as dim_error:
            # Check if it's a dimension mismatch error
            if "dimension" in str(dim_error).lower() and "does not match" in str(dim_error).lower():
                logger.warning(f"Dimension mismatch error from Pinecone: {str(dim_error)}")
                logger.warning(f"First vector dimension: {len(records[0]['values']) if records else 'unknown'}")
                
                # Re-initialize with fallback index
                pc = Pinecone(api_key=PINECONE_API_KEY)
                fallback_index_name = "papermastery-fallback"
                vector_dimension = 3072  # Using 3072 dimensions to match existing index
                available_indexes = [idx['name'] for idx in pc.list_indexes()]
                
                # Create fallback index if it doesn't exist
                if fallback_index_name not in available_indexes:
                    logger.info(f"Creating fallback index: {fallback_index_name}")
                    pc.create_index(
                        name=fallback_index_name,
                        dimension=vector_dimension,  # Using 3072 dimensions for consistency
                        metric="cosine",
                        spec=ServerlessSpec(
                            cloud="aws",
                            region="us-east-1"
                        )
                    )
                
                # Connect to fallback index
                index = pc.Index(fallback_index_name)
                logger.info(f"Reconnected to fallback Pinecone index: {fallback_index_name}")
                
                # Retry upsert with fallback index
                for i in range(0, len(records), batch_size):
                    batch = records[i:i+batch_size]
                    await asyncio.to_thread(
                        index.upsert,
                        vectors=batch,
                        namespace=namespace
                    )
                logger.info(f"Successfully stored {len(chunks)} chunks in fallback index for paper ID: {paper_id}")
            else:
                # Re-raise if it's not a dimension mismatch error
                raise
        
        return namespace
        
    except Exception as e:
        logger.error(f"Error storing chunks in Pinecone for paper ID {paper_id}: {str(e)}")
        raise PineconeError(f"Error storing chunks in Pinecone: {str(e)}")


async def search_similar_chunks(
    query: Union[str, List[float]],
    paper_id: Optional[UUID] = None,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Search for chunks that are similar to the query string or embedding.
    
    Args:
        query: String query or embedding vector
        paper_id: Optional ID to scope the search to a specific paper
        top_k: Number of results to return
        
    Returns:
        List of similar chunks with metadata
        
    Raises:
        PineconeError: If there's an error searching in Pinecone
    """
    global index
    
    # Set namespace if paper_id is provided
    namespace = str(paper_id) if paper_id else None
    logger.info(f"Searching in namespace: {namespace}")
    
    try:
        # Check if query is already an embedding vector
        is_embedding = isinstance(query, list) and len(query) > 0 and isinstance(query[0], (int, float))
        
        if is_embedding:
            logger.info(f"Using provided embedding vector with {len(query)} dimensions")
            query_embedding = query
        else:
            logger.info(f"Searching for similar chunks with query: {query[:50]}...")
            
            # Try using LangChain for search if available
            if langchain_embeddings is not None and not is_embedding:
                try:
                    # Determine which index to use
                    index_name = fallback_index_name if fallback_index_name in available_indexes else primary_index_name
                    namespace = str(paper_id) if paper_id else None
                    
                    # Create a vector store instance
                    vector_store = PineconeVectorStore(
                        index_name=index_name,
                        embedding=langchain_embeddings,
                        namespace=namespace
                    )
                    
                    # Search for similar documents
                    docs_with_scores = await asyncio.to_thread(
                        vector_store.similarity_search_with_score,
                        query=query,
                        k=top_k
                    )
                    
                    # Format results
                    formatted_results = []
                    for doc, score in docs_with_scores:
                        formatted_results.append({
                            "chunk_id": f"{doc.metadata.get('paper_id', 'unknown')}_chunk_{doc.metadata.get('chunk_index', 0)}",
                            "score": score,
                            "metadata": doc.metadata,
                            "text": doc.page_content
                        })
                    
                    logger.info(f"Found {len(formatted_results)} similar chunks using LangChain for query")
                    return formatted_results
                    
                except Exception as langchain_error:
                    logger.warning(f"LangChain search failed, falling back to default method: {str(langchain_error)}")
                    # Fall back to the original method if LangChain fails
            
            # Generate embedding for the query
            query_embedding = (await generate_embeddings([query]))[0]
        
        # Check embedding dimensions
        embedding_dim = len(query_embedding)
        logger.info(f"Query embedding dimension: {embedding_dim}")
        
        # Ensure dimensions match the index
        if embedding_dim != vector_dimension:
            logger.warning(f"Query embedding dimension mismatch: {embedding_dim} vs {vector_dimension}")
            # Pad or truncate embedding to match the expected dimension
            if embedding_dim < vector_dimension:
                # Pad with zeros
                padded_emb = np.pad(query_embedding, (0, vector_dimension - embedding_dim), 'constant')
                query_embedding = padded_emb.tolist()
            elif embedding_dim > vector_dimension:
                # Truncate
                query_embedding = query_embedding[:vector_dimension]
            logger.info(f"Adjusted query embedding to {vector_dimension} dimensions")
        
        # Set namespace if paper_id is provided
        namespace = str(paper_id) if paper_id else None
        
        # Search in Pinecone
        results = await asyncio.to_thread(
            index.query,
            vector=query_embedding,
            top_k=top_k,
            namespace=namespace,
            include_metadata=True
        )
        
        # Format results
        formatted_results = []
        for match in results.matches:
            formatted_results.append({
                "chunk_id": match.id,
                "score": match.score,
                "metadata": match.metadata,
                "text": match.metadata.get("text", "")
            })
        
        logger.info(f"Found {len(formatted_results)} similar chunks for query using direct Pinecone query")
        
        return formatted_results
        
    except Exception as e:
        logger.error(f"Error searching similar chunks: {str(e)}")
        raise PineconeError(f"Error searching similar chunks: {str(e)}")


async def delete_paper_embeddings(paper_id: UUID) -> bool:
    """
    Delete all embeddings for a paper from Pinecone.
    
    Args:
        paper_id: The UUID of the paper
        
    Returns:
        True if successful, False otherwise
        
    Raises:
        PineconeError: If there's an error deleting embeddings
    """
    global index
    
    if not index:
        logger.error("Pinecone index not initialized")
        raise PineconeError("Pinecone index not initialized")
    
    try:
        # Use the paper_id as the namespace
        namespace = str(paper_id)
        
        # Delete all vectors in the namespace
        index.delete(namespace=namespace, delete_all=True)
        
        logger.info(f"Successfully deleted all embeddings for paper ID: {paper_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error deleting embeddings for paper ID {paper_id}: {str(e)}")
        raise PineconeError(f"Error deleting embeddings: {str(e)}")


async def get_all_paper_chunks(paper_id: UUID, limit: int = 1000) -> List[Dict[str, Any]]:
    """
    Retrieve all chunks for a paper from Pinecone.
    
    Args:
        paper_id: The UUID of the paper
        limit: Maximum number of chunks to retrieve
        
    Returns:
        List of chunks with metadata
        
    Raises:
        PineconeError: If there's an error retrieving chunks
    """
    global index
    
    if not index:
        logger.error("Pinecone index not initialized")
        raise PineconeError("Pinecone index not initialized")
    
    try:
        # Use the paper_id as the namespace
        namespace = str(paper_id)
        
        # Try using LangChain for retrieval if available
        if langchain_embeddings is not None:
            try:
                # Determine which index to use
                index_name = fallback_index_name if fallback_index_name in available_indexes else primary_index_name
                
                # Create a vector store instance
                vector_store = PineconeVectorStore(
                    index_name=index_name,
                    embedding=langchain_embeddings,
                    namespace=namespace
                )
                
                # Get all documents in the namespace
                # Since LangChain doesn't have a direct method to get all documents,
                # we'll use a dummy query with a high limit
                docs = await asyncio.to_thread(
                    vector_store.similarity_search,
                    query="",  # Empty query to get all documents
                    k=limit    # High limit to get all documents
                )
                
                # Format results
                formatted_results = []
                for doc in docs:
                    formatted_results.append({
                        "chunk_id": f"{doc.metadata.get('paper_id', 'unknown')}_chunk_{doc.metadata.get('chunk_index', 0)}",
                        "metadata": doc.metadata,
                        "text": doc.page_content
                    })
                
                logger.info(f"Retrieved {len(formatted_results)} chunks for paper {paper_id} using LangChain")
                return formatted_results
                
            except Exception as langchain_error:
                logger.warning(f"LangChain retrieval failed, falling back to default method: {str(langchain_error)}")
                # Fall back to the original method if LangChain fails
        
        # Fallback: Use Pinecone directly
        # Since Pinecone doesn't have a direct method to get all vectors without a query,
        # we'll use a dummy vector with a high limit
        dummy_vector = [0.0] * vector_dimension  # Create a zero vector with the correct dimension
        
        # Query the index with the dummy vector
        response = index.query(
            namespace=namespace,
            vector=dummy_vector,
            top_k=limit,
            include_metadata=True
        )
        
        # Format results
        formatted_results = []
        for match in response.get("matches", []):
            metadata = match.get("metadata", {})
            formatted_results.append({
                "chunk_id": match.get("id", "unknown"),
                "metadata": metadata,
                "text": metadata.get("text", "")
            })
        
        logger.info(f"Retrieved {len(formatted_results)} chunks for paper {paper_id} using Pinecone directly")
        return formatted_results
        
    except Exception as e:
        logger.error(f"Error retrieving chunks for paper ID {paper_id}: {str(e)}")
        raise PineconeError(f"Error retrieving chunks: {str(e)}") 