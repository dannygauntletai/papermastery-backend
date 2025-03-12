from typing import Dict, List, Any
import asyncio
from uuid import UUID
import os.path
from jinja2 import Environment, FileSystemLoader

from app.core.logger import get_logger
from app.api.v1.models import PaperSummary
from app.core.config import APP_ENV
from app.services.llm_service import generate_text, mock_generate_text

logger = get_logger(__name__)

# Initialize Jinja2 environment
templates_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'app', 'templates')
env = Environment(loader=FileSystemLoader(templates_dir))


async def generate_summaries(
    paper_id: UUID,
    abstract: str,
    full_text: str,
    chunks: List[Dict[str, Any]]
) -> PaperSummary:
    """
    Generate tiered summaries (beginner, intermediate, advanced) for a paper.
    
    Args:
        paper_id: The UUID of the paper
        abstract: The paper's abstract
        full_text: The full text of the paper
        chunks: The chunked text with metadata
        
    Returns:
        PaperSummary object with beginner, intermediate, and advanced summaries
    """
    try:
        logger.info(f"Generating summaries for paper ID: {paper_id}")
        
        # Extract intro and conclusion chunks if available
        intro_chunks = [c for c in chunks if c["metadata"].get("is_introduction", False)]
        conclusion_chunks = [c for c in chunks if c["metadata"].get("is_conclusion", False)]
        
        # Generate all summaries concurrently for efficiency
        beginner_summary, intermediate_summary, advanced_summary = await asyncio.gather(
            generate_beginner_summary(abstract, intro_chunks, conclusion_chunks),
            generate_intermediate_summary(abstract, intro_chunks, conclusion_chunks),
            generate_advanced_summary(abstract, full_text, chunks)
        )
        
        summaries = PaperSummary(
            beginner=beginner_summary,
            intermediate=intermediate_summary,
            advanced=advanced_summary
        )
        
        logger.info(f"Successfully generated summaries for paper ID: {paper_id}")
        return summaries
        
    except Exception as e:
        logger.error(f"Error generating summaries for paper ID {paper_id}: {str(e)}")
        # Return basic summaries instead of raising error
        return PaperSummary(
            beginner=f"Summary generation in progress. Abstract: {abstract[:200]}...",
            intermediate=f"Summary generation in progress. Abstract: {abstract[:300]}...",
            advanced=f"Summary generation in progress. Abstract: {abstract}"
        )


async def generate_beginner_summary(
    abstract: str,
    intro_chunks: List[Dict[str, Any]],
    conclusion_chunks: List[Dict[str, Any]]
) -> str:
    """
    Generate a beginner-level summary.
    
    This is a simplified, jargon-free overview for non-experts.
    
    Args:
        abstract: The paper's abstract
        intro_chunks: Chunks from the introduction
        conclusion_chunks: Chunks from the conclusion
        
    Returns:
        Beginner-level summary text
    """
    # Extract key information from the paper's abstract and chunks
    intro_text = " ".join([c["text"] for c in intro_chunks[:2]]) if intro_chunks else ""
    conclusion_text = " ".join([c["text"] for c in conclusion_chunks[:2]]) if conclusion_chunks else ""
    
    # Load and render the template
    template = env.get_template('prompts/beginner_summary.j2')
    prompt = template.render(
        abstract=abstract,
        intro_text=intro_text,
        conclusion_text=conclusion_text,
        block='content'  # Specify which block to use
    )
    
    try:
        # Use the appropriate generate function based on environment
        if APP_ENV == "testing":
            summary = await mock_generate_text(prompt, max_tokens=500, temperature=0.7)
        else:
            summary = await generate_text(prompt, max_tokens=500, temperature=0.7)
        
        return summary
    except Exception as e:
        logger.error(f"Error generating beginner summary: {str(e)}")
        # Use fallback template
        fallback_template = env.get_template('prompts/beginner_fallback.j2')
        return fallback_template.render(
            abstract=abstract,
            block='fallback_content'  # Specify which block to use
        )


async def generate_intermediate_summary(
    abstract: str,
    intro_chunks: List[Dict[str, Any]],
    conclusion_chunks: List[Dict[str, Any]]
) -> str:
    """
    Generate an intermediate-level summary.
    
    This includes key points with explained technical terms.
    
    Args:
        abstract: The paper's abstract
        intro_chunks: Chunks from the introduction
        conclusion_chunks: Chunks from the conclusion
        
    Returns:
        Intermediate-level summary text
    """
    # Extract and process content from the paper
    intro_text = " ".join([c["text"] for c in intro_chunks]) if intro_chunks else ""
    conclusion_text = " ".join([c["text"] for c in conclusion_chunks]) if conclusion_chunks else ""
    
    # Load and render the template
    template = env.get_template('prompts/intermediate_summary.j2')
    prompt = template.render(
        abstract=abstract,
        intro_text=intro_text,
        conclusion_text=conclusion_text,
        block='content'  # Specify which block to use
    )
    
    try:
        # Use the appropriate generate function based on environment
        if APP_ENV == "testing":
            summary = await mock_generate_text(prompt, max_tokens=800, temperature=0.7)
        else:
            summary = await generate_text(prompt, max_tokens=800, temperature=0.7)
        
        return summary
    except Exception as e:
        logger.error(f"Error generating intermediate summary: {str(e)}")
        # Use fallback template
        fallback_template = env.get_template('prompts/intermediate_fallback.j2')
        return fallback_template.render(
            abstract=abstract,
            block='fallback_content'  # Specify which block to use
        )


async def generate_advanced_summary(
    abstract: str,
    full_text: str,
    chunks: List[Dict[str, Any]]
) -> str:
    """
    Generate an advanced-level summary.
    
    This includes detailed information with full technical depth.
    
    Args:
        abstract: The paper's abstract
        full_text: The full text of the paper
        chunks: All text chunks with metadata
        
    Returns:
        Advanced-level summary text
    """
    # Extract different section types from the chunks
    method_chunks = [c for c in chunks if c["metadata"].get("is_methodology", False)]
    result_chunks = [c for c in chunks if c["metadata"].get("is_results", False)]
    discussion_chunks = [c for c in chunks if c["metadata"].get("is_discussion", False)]
    intro_chunks = [c for c in chunks if c["metadata"].get("is_introduction", False)]
    conclusion_chunks = [c for c in chunks if c["metadata"].get("is_conclusion", False)]
    
    # Combine text from each section
    method_text = " ".join([c["text"] for c in method_chunks]) if method_chunks else ""
    result_text = " ".join([c["text"] for c in result_chunks]) if result_chunks else ""
    discussion_text = " ".join([c["text"] for c in discussion_chunks]) if discussion_chunks else ""
    intro_text = " ".join([c["text"] for c in intro_chunks]) if intro_chunks else ""
    conclusion_text = " ".join([c["text"] for c in conclusion_chunks]) if conclusion_chunks else ""
    
    # Load and render the template
    template = env.get_template('prompts/advanced_summary.j2')
    prompt = template.render(
        abstract=abstract,
        intro_text=intro_text,
        method_text=method_text,
        result_text=result_text,
        discussion_text=discussion_text,
        conclusion_text=conclusion_text,
        block='content'  # Specify which block to use
    )
    
    try:
        # Use the appropriate generate function based on environment
        if APP_ENV == "testing":
            summary = await mock_generate_text(prompt, max_tokens=1500, temperature=0.7)
        else:
            summary = await generate_text(prompt, max_tokens=1500, temperature=0.7)
        
        return summary
    except Exception as e:
        logger.error(f"Error generating advanced summary: {str(e)}")
        # Use fallback template
        fallback_template = env.get_template('prompts/advanced_fallback.j2')
        return fallback_template.render(
            abstract=abstract,
            full_text=full_text,
            chunks=chunks,
            block='fallback_content'  # Specify which block to use
        ) 