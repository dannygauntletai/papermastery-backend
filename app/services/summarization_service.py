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
    extract_abstract: bool = False,
    max_retries: int = 3
) -> Tuple[PaperSummary, str]:
    """
    Generate tiered summaries (beginner, intermediate, advanced) for a paper and optionally extract the abstract.
    
    Args:
        paper_id: The UUID of the paper
        title: The title of the paper
        abstract: The paper's abstract (can be None if extract_abstract is True)
        full_text: The full text of the paper
        extract_abstract: Whether to extract the abstract from the full text
        max_retries: Maximum number of retry attempts for handling LLM failures
        
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
            # Pass the max_retries parameter to the generate_summary_json function
            try:
                result_dict = await generate_summary_json(
                    prompt=prompt, 
                    max_tokens=2500, 
                    temperature=0.3,
                    max_retries=max_retries
                )
            except Exception as llm_error:
                logger.error(f"Error with LLM service during summary generation for paper ID {paper_id}: {str(llm_error)}")
                # Try with a simplified prompt if the original fails
                try:
                    logger.info(f"Attempting summary generation with simplified prompt for paper ID {paper_id}")
                    simplified_prompt = template.render(
                        title=title,
                        abstract=abstract,
                        # Use only abstract for a simplified generation
                        full_text=abstract, 
                        block='content'
                    ) + "\n\nPlease respond with ONLY valid JSON and nothing else."
                    
                    result_dict = await generate_summary_json(
                        prompt=simplified_prompt, 
                        max_tokens=1500,  # Reduce tokens for simplified summary
                        temperature=0.2,  # Lower temperature for more deterministic output
                        max_retries=max_retries
                    )
                except Exception as simplified_error:
                    logger.error(f"Even simplified prompt failed for paper ID {paper_id}: {str(simplified_error)}")
                    raise  # Re-raise to be caught by the outer try-except
        
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
        
        # Use fallback template for a more graceful degradation
        fallback_template = env.get_template('prompts/unified_summary.j2')
        try:
            # Try to load pre-defined fallback content
            fallback_content = fallback_template.render(
                abstract=abstract,
                block='fallback_content'  # Specify which block to use
            )
            
            # Try to parse the fallback content as JSON
            import json
            fallback_dict = json.loads(fallback_content)
            summaries = PaperSummary(
                beginner=fallback_dict["beginner"],
                intermediate=fallback_dict["intermediate"],
                advanced=fallback_dict["advanced"]
            )
            extracted_abstract = fallback_dict.get("extracted_abstract", abstract) if extract_abstract else abstract
            
            logger.info(f"Successfully used fallback template for paper ID: {paper_id}")
        except Exception as fallback_error:
            # If parsing fails, use a simple fallback with the abstract
            logger.error(f"Fallback template failed for paper ID {paper_id}: {str(fallback_error)}")
            
            # Create simple summaries based on the abstract
            abstract_preview = abstract[:100] + "..." if abstract and len(abstract) > 100 else (abstract or "Not available")
            
            summaries = PaperSummary(
                beginner=f"This paper discusses: {abstract_preview}\n\nA detailed summary is being generated and will be available soon.",
                intermediate=f"This academic paper covers: {abstract_preview}\n\nA comprehensive summary is being processed.",
                advanced=f"Research paper abstract: {abstract or 'Not available'}\n\nA technical summary is in progress."
            )
            extracted_abstract = abstract
            
            logger.warning(f"Using very basic fallback summaries for paper ID: {paper_id}")
            
        return summaries, extracted_abstract 