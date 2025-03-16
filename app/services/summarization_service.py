from typing import Dict, List, Any
import asyncio
from uuid import UUID
import os.path
from jinja2 import Environment, FileSystemLoader

from app.core.logger import get_logger
from app.api.v1.models import PaperSummary
from app.core.config import APP_ENV
from app.services.llm_service import generate_summary_json, mock_generate_summary_json

logger = get_logger(__name__)

# Initialize Jinja2 environment
templates_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'app', 'templates')
env = Environment(loader=FileSystemLoader(templates_dir))


async def generate_summaries(
    paper_id: UUID,
    title: str,
    abstract: str,
    full_text: str
) -> PaperSummary:
    """
    Generate tiered summaries (beginner, intermediate, advanced) for a paper.
    
    Args:
        paper_id: The UUID of the paper
        title: The title of the paper
        abstract: The paper's abstract
        full_text: The full text of the paper
        
    Returns:
        PaperSummary object with beginner, intermediate, and advanced summaries
    """
    try:
        logger.info(f"Generating summaries for paper ID: {paper_id}")
        
        # Load and render the unified summary template
        template = env.get_template('prompts/unified_summary.j2')
        prompt = template.render(
            title=title,
            abstract=abstract,
            full_text=full_text,
            block='content'  # Specify which block to use
        )
        
        # Generate summaries using the appropriate function based on environment
        if APP_ENV == "testing":
            summaries_dict = await mock_generate_summary_json(prompt, max_tokens=2500, temperature=0.3)
        else:
            summaries_dict = await generate_summary_json(prompt, max_tokens=2500, temperature=0.3)
        
        # Create PaperSummary object from the generated summaries
        summaries = PaperSummary(
            beginner=summaries_dict["beginner"],
            intermediate=summaries_dict["intermediate"],
            advanced=summaries_dict["advanced"]
        )
        
        logger.info(f"Successfully generated summaries for paper ID: {paper_id}")
        return summaries
        
    except Exception as e:
        logger.error(f"Error generating summaries for paper ID {paper_id}: {str(e)}")
        # Return basic summaries instead of raising error
        # Use fallback template
        fallback_template = env.get_template('prompts/unified_summary.j2')
        fallback_content = fallback_template.render(
            abstract=abstract,
            block='fallback_content'  # Specify which block to use
        )
        
        try:
            # Try to parse the fallback content as JSON
            import json
            fallback_dict = json.loads(fallback_content)
            return PaperSummary(
                beginner=fallback_dict["beginner"],
                intermediate=fallback_dict["intermediate"],
                advanced=fallback_dict["advanced"]
            )
        except Exception:
            # If parsing fails, use a simple fallback
            return PaperSummary(
                beginner=f"Summary generation in progress. Abstract: {abstract[:200]}...",
                intermediate=f"Summary generation in progress. Abstract: {abstract[:300]}...",
                advanced=f"Summary generation in progress. Abstract: {abstract}"
            ) 