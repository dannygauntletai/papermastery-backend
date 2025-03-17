from typing import Dict, List, Any, Tuple
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
    full_text: str,
    extract_abstract: bool = False
) -> Tuple[PaperSummary, str]:
    """
    Generate tiered summaries (beginner, intermediate, advanced) for a paper and optionally extract the abstract.
    
    Args:
        paper_id: The UUID of the paper
        title: The title of the paper
        abstract: The paper's abstract (can be None if extract_abstract is True)
        full_text: The full text of the paper
        extract_abstract: Whether to extract the abstract from the full text
        
    Returns:
        Tuple containing:
        - PaperSummary object with beginner, intermediate, and advanced summaries
        - Extracted abstract string (if extract_abstract is True, otherwise the original abstract)
    """
    try:
        logger.info(f"Generating summaries for paper ID: {paper_id}")
        
        # Ensure we have valid values for all parameters
        if full_text is None:
            logger.warning(f"Full text is None for paper ID: {paper_id}, using placeholder text")
            full_text = "Paper text not available"
            
        if title is None:
            logger.warning(f"Title is None for paper ID: {paper_id}, using placeholder title")
            title = "Untitled Paper"
            
        if abstract is None:
            logger.warning(f"Abstract is None for paper ID: {paper_id}, using placeholder abstract")
            abstract = "Abstract not available"
        
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
            result_dict = await mock_generate_summary_json(prompt, max_tokens=2500, temperature=0.3)
        else:
            result_dict = await generate_summary_json(prompt, max_tokens=2500, temperature=0.3)
        
        # Create PaperSummary object from the generated summaries
        summaries = PaperSummary(
            beginner=result_dict["beginner"],
            intermediate=result_dict["intermediate"],
            advanced=result_dict["advanced"]
        )
        
        # Get the extracted abstract if requested
        extracted_abstract = result_dict.get("extracted_abstract", abstract) if extract_abstract else abstract
        
        logger.info(f"Successfully generated summaries for paper ID: {paper_id}")
        if extract_abstract:
            logger.info(f"Successfully extracted abstract for paper ID: {paper_id}")
        
        return summaries, extracted_abstract
        
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
            summaries = PaperSummary(
                beginner=fallback_dict["beginner"],
                intermediate=fallback_dict["intermediate"],
                advanced=fallback_dict["advanced"]
            )
            extracted_abstract = fallback_dict.get("extracted_abstract", abstract) if extract_abstract else abstract
        except Exception:
            # If parsing fails, use a simple fallback
            summaries = PaperSummary(
                beginner=f"Summary generation in progress. Abstract: {abstract[:200] if abstract else 'Not available'}...",
                intermediate=f"Summary generation in progress. Abstract: {abstract[:300] if abstract else 'Not available'}...",
                advanced=f"Summary generation in progress. Abstract: {abstract if abstract else 'Not available'}"
            )
            extracted_abstract = abstract
            
        return summaries, extracted_abstract 