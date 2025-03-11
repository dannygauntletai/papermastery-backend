from typing import List, Dict, Any, Optional
import asyncio
from uuid import UUID
from openai import OpenAI, AsyncOpenAI
import json

from app.core.logger import get_logger
from app.core.config import OPENAI_API_KEY, OPENAI_MODEL
from app.core.exceptions import LLMServiceError

logger = get_logger(__name__)

# Initialize the OpenAI client
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

async def generate_response(
    query: str,
    context_chunks: List[Dict[str, Any]],
    paper_title: Optional[str] = None,
    max_tokens: int = 1000
) -> Dict[str, Any]:
    """
    Generate a response to a query using the OpenAI API.
    
    Args:
        query: The user's query
        context_chunks: List of text chunks with metadata to use as context
        paper_title: Optional title of the paper for context
        max_tokens: Maximum number of tokens in the response
        
    Returns:
        Dictionary containing the generated response and metadata
        
    Raises:
        LLMServiceError: If there's an error generating a response
    """
    try:
        logger.info(f"Generating response for query: {query[:50]}...")
        
        # Format context chunks as a string with citations
        formatted_chunks = []
        for i, chunk in enumerate(context_chunks):
            # Use chunk_id if available, otherwise use a sequential number
            chunk_id = chunk.get("chunk_id", f"chunk_{i}")
            text = chunk.get("text", "")
            
            # Add the chunk to the formatted chunks with a citation marker
            formatted_chunks.append(f"[{i+1}] {text}")
            
        # Join all formatted chunks with separators
        context_text = "\n\n".join(formatted_chunks)
        
        # Construct the prompt
        paper_context = f" about the paper '{paper_title}'" if paper_title else ""
        
        prompt = f"""You are an AI research assistant. Answer the following question{paper_context} 
using ONLY the information from the provided context chunks.

If the question cannot be answered using the context, say "I cannot answer this question based on the 
available information from the paper." and suggest what further information might be needed.

Question: {query}

Context:
{context_text}

Answer the question in a clear, concise manner. If appropriate, you may format your response using Markdown.
If there are relevant parts of the context that directly support your answer, you may quote them by
including the chunk number in square brackets, e.g., [1].
"""

        # Call the OpenAI API to generate a response
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "system", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.3,  # Lower temperature for more deterministic responses
        )
        
        # Extract the response text
        response_text = response.choices[0].message.content.strip()
        
        # Return the response with metadata
        result = {
            "response": response_text,
            "query": query,
            "sources": [
                {
                    "chunk_id": chunk.get("chunk_id", f"chunk_{i}"),
                    "text": chunk.get("text", "")[:200] + "..." if len(chunk.get("text", "")) > 200 else chunk.get("text", ""),
                    "metadata": chunk.get("metadata", {})
                }
                for i, chunk in enumerate(context_chunks)
            ]
        }
        
        logger.info("Response generated successfully")
        return result
        
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}")
        raise LLMServiceError(f"Error generating response: {str(e)}")


async def mock_generate_response(
    query: str,
    context_chunks: List[Dict[str, Any]],
    paper_title: Optional[str] = None,
    max_tokens: int = 1000
) -> Dict[str, Any]:
    """
    Mock version of generate_response for testing without calling the OpenAI API.
    
    Args:
        query: The user's query
        context_chunks: List of text chunks with metadata to use as context
        paper_title: Optional title of the paper for context
        max_tokens: Maximum number of tokens in the response
        
    Returns:
        Dictionary containing the generated response and metadata
    """
    # Simulate API latency
    await asyncio.sleep(0.5)
    
    # Create a simple response based on the query and chunks
    chunk_texts = [chunk.get("text", "")[:50] + "..." for chunk in context_chunks]
    chunk_summary = " ".join(chunk_texts)
    
    paper_context = f" about the paper '{paper_title}'" if paper_title else ""
    
    response_text = f"""Based on the paper{paper_context}, I can provide the following information:

The content discusses {chunk_summary}.

Your query was about "{query}". According to the paper [1], this topic is addressed in several sections.

## Key points:
1. First important point from the paper
2. Second important point
3. Third important point

For more detailed information, you may want to refer to the complete paper.
"""
    
    # Return mock response with metadata
    return {
        "response": response_text,
        "query": query,
        "sources": [
            {
                "chunk_id": chunk.get("chunk_id", f"chunk_{i}"),
                "text": chunk.get("text", "")[:200] + "..." if len(chunk.get("text", "")) > 200 else chunk.get("text", ""),
                "metadata": chunk.get("metadata", {})
            }
            for i, chunk in enumerate(context_chunks)
        ]
    } 