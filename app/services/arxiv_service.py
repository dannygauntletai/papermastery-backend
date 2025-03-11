import feedparser
import requests
import re
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
import asyncio
from urllib.parse import quote
import httpx

from app.api.v1.models import PaperMetadata, Author
from app.core.logger import get_logger
from app.core.config import ARXIV_API_BASE_URL, OPENALEX_API_BASE_URL
from app.core.exceptions import ArXivAPIError, InvalidArXivLinkError
from app.utils.pdf_utils import download_pdf, extract_text_from_pdf, clean_pdf_text

logger = get_logger(__name__)


async def fetch_paper_metadata(arxiv_id: str) -> PaperMetadata:
    """
    Fetch paper metadata from the arXiv API.
    
    Args:
        arxiv_id: The arXiv ID of the paper
        
    Returns:
        PaperMetadata object with the paper's metadata
        
    Raises:
        ArXivAPIError: If there's an error fetching from the arXiv API
        InvalidArXivLinkError: If the arXiv ID is invalid
    """
    # Validate arXiv ID format
    if not re.match(r'^\d+\.\d+(v\d+)?$', arxiv_id):
        logger.error(f"Invalid arXiv ID format: {arxiv_id}")
        raise InvalidArXivLinkError(f"https://arxiv.org/abs/{arxiv_id}")
    
    try:
        logger.info(f"Fetching metadata for arXiv ID: {arxiv_id}")
        
        # Construct API URL
        query = f"id:{arxiv_id}"
        url = f"{ARXIV_API_BASE_URL}?search_query={quote(query)}&max_results=1"
        
        # Fetch data from arXiv API
        response = await asyncio.to_thread(feedparser.parse, url)
        
        if 'entries' not in response or not response.entries:
            logger.error(f"No entries found for arXiv ID: {arxiv_id}")
            raise ArXivAPIError(f"No paper found with arXiv ID: {arxiv_id}")
        
        entry = response.entries[0]
        
        # Extract authors
        authors = []
        for author in entry.get('authors', []):
            name = author.get('name', '')
            authors.append(Author(name=name, affiliations=[]))
        
        # Extract publication date
        published = entry.get('published', '')
        try:
            publication_date = datetime.strptime(published, '%Y-%m-%dT%H:%M:%SZ')
        except (ValueError, TypeError):
            publication_date = datetime.now()
        
        # Create metadata object
        metadata = PaperMetadata(
            arxiv_id=arxiv_id,
            title=entry.get('title', '').replace('\n', ' '),
            authors=authors,
            abstract=entry.get('summary', '').replace('\n', ' '),
            publication_date=publication_date,
            categories=[tag.get('term', '') for tag in entry.get('tags', [])],
            doi=entry.get('arxiv_doi', None)
        )
        
        logger.info(f"Successfully fetched metadata for arXiv ID: {arxiv_id}")
        return metadata
        
    except Exception as e:
        logger.error(f"Error fetching metadata for arXiv ID {arxiv_id}: {str(e)}")
        raise ArXivAPIError(f"Error fetching paper metadata: {str(e)}")


async def download_and_process_paper(arxiv_id: str) -> Tuple[str, List[str]]:
    """
    Download and process a paper from arXiv.
    
    This function:
    1. Downloads the PDF from arXiv
    2. Extracts text from the PDF
    3. Cleans the text
    4. Breaks it into logical chunks
    
    Args:
        arxiv_id: The arXiv ID of the paper
        
    Returns:
        Tuple containing full text and a list of text chunks
        
    Raises:
        ArXivAPIError: If there's an error with the arXiv API
    """
    try:
        # Construct PDF URL
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        
        logger.info(f"Downloading PDF for arXiv ID: {arxiv_id}")
        
        # Download PDF
        pdf_path = await download_pdf(pdf_url)
        
        # Extract text from PDF
        text = await extract_text_from_pdf(pdf_path)
        
        # Clean text
        text = await clean_pdf_text(text)
        
        # Break into chunks (simple approach - in a real implementation, use NLP)
        # This is a placeholder for actual chunking logic
        chunks = break_text_into_chunks(text)
        
        logger.info(f"Successfully processed PDF for arXiv ID: {arxiv_id}")
        
        return text, chunks
        
    except Exception as e:
        logger.error(f"Error processing PDF for arXiv ID {arxiv_id}: {str(e)}")
        raise ArXivAPIError(f"Error processing PDF: {str(e)}")


def break_text_into_chunks(text: str, max_chunk_size: int = 1000) -> List[str]:
    """
    Break text into chunks of approximately equal size.
    
    In a real implementation, this would use more sophisticated NLP techniques
    to break the text at logical boundaries (paragraphs, sections, etc.).
    
    Args:
        text: The text to chunk
        max_chunk_size: Maximum characters per chunk
        
    Returns:
        List of text chunks
    """
    # Simple chunking by paragraphs
    paragraphs = [p for p in text.split('\n\n') if p.strip()]
    
    chunks = []
    current_chunk = ""
    
    for paragraph in paragraphs:
        # If adding this paragraph would exceed max_chunk_size, start a new chunk
        if len(current_chunk) + len(paragraph) > max_chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = paragraph
        else:
            current_chunk += "\n\n" + paragraph if current_chunk else paragraph
    
    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks


async def get_related_papers(arxiv_id: str) -> List[Dict[str, Any]]:
    """
    Get related papers using the OpenAlex API.
    
    This function queries the OpenAlex API to find papers related to the given arXiv ID.
    It searches for papers with similar concepts or that cite the same references.
    
    Args:
        arxiv_id: The arXiv ID of the paper
        
    Returns:
        List of related papers with metadata (title, authors, arxiv_id, abstract)
    """
    try:
        logger.info(f"Fetching related papers for arXiv ID: {arxiv_id} using OpenAlex API")
        
        # Construct the OpenAlex API URL using the configuration variable
        # Search for papers mentioning this arXiv ID in their references
        # Query format based on OpenAlex API documentation
        query = f"arxiv:{arxiv_id}"
        search_url = f"{OPENALEX_API_BASE_URL}?filter=cited_by:{query}&per_page=5"
        
        logger.debug(f"Querying OpenAlex API at: {search_url}")
        
        async with httpx.AsyncClient() as client:
            # Make async request to OpenAlex API
            response = await client.get(
                search_url,
                headers={"Accept": "application/json"},
                timeout=15.0
            )
            
            # Check response status
            if response.status_code != 200:
                logger.warning(
                    f"OpenAlex API returned non-200 status code: {response.status_code}"
                )
                return []
            
            # Parse response data
            data = response.json()
            results = data.get("results", [])
            
            # If no results found using cited_by, try similar papers by concept
            if not results:
                logger.info(f"No citing papers found, searching for conceptually similar papers")
                concept_url = f"{OPENALEX_API_BASE_URL}?filter=concepts.id:arxiv:{arxiv_id}&per_page=5"
                
                response = await client.get(
                    concept_url,
                    headers={"Accept": "application/json"},
                    timeout=15.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])
            
            # Process results into a consistent format
            related_papers = []
            for paper in results:
                # Extract basic metadata from OpenAlex response
                title = paper.get("title", "Untitled Paper")
                
                # Extract authors
                authors_data = []
                for author in paper.get("authorships", []):
                    author_obj = author.get("author", {})
                    authors_data.append({
                        "name": author_obj.get("display_name", "Unknown Author"),
                        "affiliations": [
                            affil.get("display_name", "Unknown Affiliation")
                            for affil in author.get("institutions", [])
                        ]
                    })
                
                # Extract abstract
                abstract = paper.get("abstract", "No abstract available")
                
                # Get arXiv ID if available
                arxiv_id = None
                for identifier in paper.get("ids", {}).values():
                    if isinstance(identifier, str) and "arxiv" in identifier.lower():
                        arxiv_id = identifier.split("/")[-1]
                        break
                
                # Only include papers with arXiv IDs
                if arxiv_id:
                    related_papers.append({
                        "title": title,
                        "authors": authors_data,
                        "arxiv_id": arxiv_id,
                        "abstract": abstract
                    })
            
            logger.info(f"Found {len(related_papers)} related papers for arXiv ID: {arxiv_id}")
            return related_papers[:5]  # Limit to 5 related papers
        
    except Exception as e:
        logger.error(f"Error fetching related papers for arXiv ID {arxiv_id}: {str(e)}")
        # Return empty list instead of raising an exception
        # since related papers are not critical
        return [] 