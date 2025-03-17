import feedparser
import requests
import re
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
import asyncio
from urllib.parse import quote
import httpx
import os
from uuid import UUID

from app.api.v1.models import PaperMetadata, Author, SourceType
from app.core.logger import get_logger
from app.core.config import ARXIV_API_BASE_URL, OPENALEX_API_BASE_URL
from app.core.exceptions import ArXivAPIError, InvalidArXivLinkError, PDFDownloadError
from app.utils.pdf_utils import download_pdf, extract_text_from_pdf, clean_pdf_text
from app.utils.url_utils import extract_paper_id_from_url
from app.services.llm_service import generate_structured_extraction

logger = get_logger(__name__)


async def fetch_arxiv_metadata(arxiv_id: str) -> PaperMetadata:
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
        
        # Construct source URL
        source_url = f"https://arxiv.org/abs/{arxiv_id}"
        
        # Create metadata object
        metadata = PaperMetadata(
            arxiv_id=arxiv_id,
            title=entry.get('title', '').replace('\n', ' '),
            authors=authors,
            abstract=entry.get('summary', '').replace('\n', ' '),
            publication_date=publication_date,
            categories=[tag.get('term', '') for tag in entry.get('tags', [])],
            doi=entry.get('arxiv_doi', None),
            source_type=SourceType.ARXIV,
            source_url=source_url
        )
        
        logger.info(f"Successfully fetched metadata for arXiv ID: {arxiv_id}")
        return metadata
        
    except Exception as e:
        logger.error(f"Error fetching metadata for arXiv ID {arxiv_id}: {str(e)}")
        raise ArXivAPIError(f"Error fetching paper metadata: {str(e)}")


async def get_related_papers(paper_id: UUID, title: Optional[str] = None, abstract: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get related papers using the OpenAlex API.
    
    This function searches for papers related to the given paper by:
    1. First finding the paper in OpenAlex using the abstract's first sentence or title
    2. Using the most relevant search result to get the OpenAlex work ID
    3. Using the work ID to find papers that cite this paper
    
    Args:
        paper_id: The UUID of the paper (used only for logging and as a reference)
        title: Optional title of the paper (will be fetched if not provided)
        abstract: Optional abstract of the paper (will be fetched if not provided)
        
    Returns:
        List of related papers with metadata (title, authors, abstract, etc.)
    """
    try:
        logger.info(f"Fetching related papers for paper ID: {paper_id} using OpenAlex API")
        
        # If title and abstract are not provided, fetch them
        if title is None or abstract is None:
            try:
                from app.database.supabase_client import get_paper_by_id
                paper = await get_paper_by_id(paper_id)
                if paper:
                    title = paper.get("title", "")
                    abstract = paper.get("abstract", "")
                    logger.info(f"Fetched metadata for paper: {title}")
                else:
                    logger.error(f"Paper with ID {paper_id} not found")
                    return []
            except Exception as e:
                logger.error(f"Error fetching paper metadata: {str(e)}")
                return []
        
        # Extract the first sentence from the abstract for searching
        first_sentence = abstract.split('.')[0].strip() if abstract else ""
        if not first_sentence and title:
            # Fall back to title if abstract is empty or has no sentences
            first_sentence = title
        
        if not first_sentence:
            logger.error("No search text available from abstract or title")
            return []
            
        logger.info(f"Searching for paper using first sentence: {first_sentence[:50]}...")
        
        # Step 1: Search for the paper in OpenAlex using the abstract's first sentence
        search_url = f"{OPENALEX_API_BASE_URL}?search={quote(first_sentence)}&filter=has_abstract:true&per_page=5"
        
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
            search_results = data.get("results", [])
            
            if not search_results:
                logger.warning(f"No papers found matching the abstract: {first_sentence[:50]}...")
                
                # Try searching by title as fallback
                if title and title != first_sentence:
                    logger.info(f"Trying to search by title instead: {title[:50]}...")
                    title_search_url = f"{OPENALEX_API_BASE_URL}?search={quote(title)}&per_page=5"
                    
                    response = await client.get(
                        title_search_url,
                        headers={"Accept": "application/json"},
                        timeout=15.0
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        search_results = data.get("results", [])
                
                if not search_results:
                    logger.warning("No papers found in OpenAlex matching this paper")
                    return []
            
            # Use the first result as the best match
            # OpenAlex search should return the most relevant results first
            if search_results:
                work_id = search_results[0].get("id")
                logger.info(f"Using best match with work_id: {work_id}")
            else:
                logger.warning("Could not determine work_id from search results")
                return []
            
            # Extract just the ID part if it's a full URL
            # OpenAlex IDs are typically in the format "https://openalex.org/W1234567890"
            # We need just the "W1234567890" part for the API query
            work_id_short = work_id
            if isinstance(work_id, str) and "/" in work_id:
                work_id_short = work_id.split("/")[-1]
                logger.debug(f"Extracted short work_id: {work_id_short} from {work_id}")
            
            # Step 2: Use the work ID to find papers that cite this paper
            cited_by_url = f"{OPENALEX_API_BASE_URL}?filter=cites:{work_id_short}&per_page=5"
            
            logger.debug(f"Querying OpenAlex API for citations at: {cited_by_url}")
            
            response = await client.get(
                cited_by_url,
                headers={"Accept": "application/json"},
                timeout=15.0
            )
            
            if response.status_code != 200:
                logger.warning(
                    f"OpenAlex API returned non-200 status code for citations: {response.status_code}"
                )
                return []
            
            # Parse response data
            data = response.json()
            results = data.get("results", [])
            
            # If no citing papers found, try papers with similar concepts
            if not results:
                logger.info(f"No citing papers found, searching for conceptually similar papers")
                
                # Extract concepts from the work
                work_url = f"{OPENALEX_API_BASE_URL}/{work_id_short}"
                work_response = await client.get(
                    work_url,
                    headers={"Accept": "application/json"},
                    timeout=15.0
                )
                
                if work_response.status_code == 200:
                    work_data = work_response.json()
                    concepts = work_data.get("concepts", [])
                    
                    if concepts:
                        # Use the top concept ID to find similar papers
                        top_concept = concepts[0].get("id") if concepts else None
                        
                        if top_concept:
                            concept_url = f"{OPENALEX_API_BASE_URL}?filter=concepts.id:{top_concept}&per_page=5"
                            
                            concept_response = await client.get(
                                concept_url,
                                headers={"Accept": "application/json"},
                                timeout=15.0
                            )
                            
                            if concept_response.status_code == 200:
                                concept_data = concept_response.json()
                                results = concept_data.get("results", [])
            
            # Process results into a consistent format
            related_papers = []
            for paper in results:
                # Extract basic metadata from OpenAlex response
                paper_title = paper.get("title", "Untitled Paper")
                paper_id = paper.get("id", "")
                
                # Extract DOI if available
                paper_doi = paper.get("doi", "")
                
                # Extract PDF URL if available
                pdf_url = None
                primary_location = paper.get("primary_location", {})
                if primary_location:
                    pdf_url = primary_location.get("pdf_url")
                
                # If no PDF URL in primary location, check all locations
                if not pdf_url:
                    for location in paper.get("locations", []):
                        if location.get("pdf_url"):
                            pdf_url = location.get("pdf_url")
                            break
                
                # Extract authors (limit to top 5 for brevity)
                authors_data = []
                for author in paper.get("authorships", [])[:5]:  # Limit to top 5 authors
                    author_obj = author.get("author", {})
                    author_name = author_obj.get("display_name", "Unknown Author")
                    
                    # Get author position if available
                    author_position = author.get("author_position", "")
                    
                    # Get primary affiliation if available
                    affiliations = []
                    for institution in author.get("institutions", [])[:1]:  # Just get primary affiliation
                        if institution.get("display_name"):
                            affiliations.append(institution.get("display_name"))
                    
                    authors_data.append({
                        "name": author_name,
                        "position": author_position,
                        "affiliations": affiliations
                    })
                
                # Extract publication year and date
                publication_year = paper.get("publication_year", None)
                publication_date = paper.get("publication_date", None)
                
                # Add paper to results
                related_papers.append({
                    "title": paper_title,
                    "authors": authors_data,
                    "openalex_id": paper_id,
                    "doi": paper_doi,
                    "pdf_url": pdf_url,
                    "publication_year": publication_year,
                    "publication_date": publication_date
                })
            
            logger.info(f"Found {len(related_papers)} related papers for paper ID: {paper_id}")
            return related_papers[:5]  # Limit to 5 related papers
        
    except Exception as e:
        logger.error(f"Error fetching related papers for paper ID {paper_id}: {str(e)}")
        # Return empty list instead of raising an exception
        # since related papers are not critical
        return [] 


async def extract_metadata_from_text(text: str) -> PaperMetadata:
    """
    Extract metadata from PDF text.
    
    Args:
        text: The text extracted from the PDF
        
    Returns:
        PaperMetadata object containing extracted metadata (title, authors, abstract, publication_date)
        
    Raises:
        Exception: If there's an error extracting metadata
    """
    try:
        logger.info("Extracting metadata from text")
        
        # Use LLM to extract metadata
        # First, use only the first 10000 characters to avoid token limits
        # This should be enough to capture the title, authors, and abstract
        text_sample = text[:10000]
        
        # Define the extraction prompt
        extraction_prompt = """
        Extract the following metadata from this academic paper text:
        1. Title
        2. Authors (with affiliations if available)
        3. Abstract
        4. Publication date (if available)
        
        Format the response as a JSON object with these fields:
        {
            "title": "Paper Title",
            "authors": [
                {"name": "Author Name", "affiliations": ["Affiliation 1", "Affiliation 2"]}
            ],
            "abstract": "Paper abstract...",
            "publication_date": "YYYY-MM-DD"
        }
        
        If any field is not found, set it to null.
        
        Here is the paper text:
        """
        
        # Use LLM service to extract structured metadata
        metadata_json = await generate_structured_extraction(
            text_sample, 
            extraction_prompt,
            max_tokens=1000
        )
        
        # Convert the JSON to a PaperMetadata object
        authors = []
        for author_data in metadata_json.get("authors", []):
            authors.append(Author(
                name=author_data.get("name", "Unknown Author"),
                affiliations=author_data.get("affiliations", [])
            ))
        
        # Parse the publication date
        pub_date = metadata_json.get("publication_date")
        if pub_date:
            try:
                publication_date = datetime.fromisoformat(pub_date)
            except ValueError:
                # Try to parse with different formats
                try:
                    # Try MM/DD/YYYY format
                    if "/" in pub_date:
                        parts = pub_date.split("/")
                        if len(parts) == 3:
                            month, day, year = parts
                            publication_date = datetime(int(year), int(month), int(day))
                    # Try Month Year format (e.g., "January 2023")
                    else:
                        # This is a simplification - would need more robust parsing
                        publication_date = datetime.now()
                except:
                    publication_date = datetime.now()
        else:
            publication_date = datetime.now()
        
        # Get abstract or provide a default
        abstract = metadata_json.get("abstract")
        if abstract is None:
            abstract = "Abstract not available"
        
        return PaperMetadata(
            title=metadata_json.get("title", "Untitled Paper"),
            authors=authors,
            abstract=abstract,
            publication_date=publication_date,
            source_url="placeholder_url",  # Add a placeholder URL that will be replaced later
            source_type=SourceType.PDF
        )
        
    except Exception as e:
        logger.error(f"Error extracting metadata from text: {str(e)}")
        # Return fallback metadata
        return PaperMetadata(
            title="Error Extracting Title",
            authors=[Author(name="Unknown Author", affiliations=[])],
            abstract="Abstract not available",
            publication_date=datetime.now(),
            source_url="placeholder_url",  # Add a placeholder URL that will be replaced later
            source_type=SourceType.PDF
        ) 