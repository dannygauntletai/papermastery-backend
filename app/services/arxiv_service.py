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

from app.api.v1.models import PaperMetadata, Author
from app.core.logger import get_logger
from app.core.config import ARXIV_API_BASE_URL, OPENALEX_API_BASE_URL
from app.core.exceptions import ArXivAPIError, InvalidArXivLinkError
from app.utils.pdf_utils import download_pdf, extract_text_from_pdf, clean_pdf_text
from app.services.pinecone_service import process_pdf_with_langchain

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


async def download_and_process_paper(arxiv_id: str, paper_id: Optional[UUID] = None) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Download and process a paper from arXiv.
    
    This function:
    1. Downloads the PDF from arXiv
    2. Extracts text from the PDF
    3. Processes it using LangChain (if available) or fallback to basic processing
    4. Breaks it into logical chunks with metadata
    
    Args:
        arxiv_id: The arXiv ID of the paper
        paper_id: Optional UUID of the paper in the database
        
    Returns:
        Tuple containing full text and a list of text chunks with metadata
        
    Raises:
        ArXivAPIError: If there's an error with the arXiv API
    """
    try:
        # Construct PDF URL
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        
        logger.info(f"Downloading PDF for arXiv ID: {arxiv_id}")
        
        # Download PDF
        pdf_path = await download_pdf(pdf_url)
        
        # Always try processing with LangChain first
        try:
            logger.info(f"Processing PDF with LangChain for arXiv ID: {arxiv_id}")
            formatted_chunks, langchain_chunks = await process_pdf_with_langchain(pdf_path, paper_id or UUID('00000000-0000-0000-0000-000000000000'))
            
            # Combine all text for full text
            full_text = "\n\n".join([chunk.get("text", "") for chunk in formatted_chunks])
            
            logger.info(f"Successfully processed PDF with LangChain for arXiv ID: {arxiv_id}")
            return full_text, formatted_chunks
                
        except Exception as langchain_error:
            logger.warning(f"LangChain processing failed, falling back to basic processing: {str(langchain_error)}")
            # Continue with basic processing if LangChain fails
        
        # Fallback to basic processing
        # Extract text from PDF
        text = await extract_text_from_pdf(pdf_path)
        
        # Clean text
        text = await clean_pdf_text(text)
        
        # Break into chunks using chunk_service instead of the simple approach
        from app.services.chunk_service import chunk_text
        chunks_with_metadata = await chunk_text(
            text=text,
            paper_id=paper_id or UUID('00000000-0000-0000-0000-000000000000'),
            max_chunk_size=1000,
            overlap=100
        )
        
        logger.info(f"Successfully processed PDF using basic processing for arXiv ID: {arxiv_id}")
        
        return text, chunks_with_metadata
        
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


async def get_related_papers(arxiv_id: str, title: Optional[str] = None, abstract: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get related papers using the OpenAlex API.
    
    This function searches for papers related to the given arXiv paper by:
    1. First finding the paper in OpenAlex using the abstract's first sentence or title
    2. Using the most relevant search result to get the OpenAlex work ID
    3. Using the work ID to find papers that cite this paper
    
    Args:
        arxiv_id: The arXiv ID of the paper (used only for logging and as a reference)
        title: Optional title of the paper (will be fetched if not provided)
        abstract: Optional abstract of the paper (will be fetched if not provided)
        
    Returns:
        List of related papers with metadata (title, authors, abstract, etc.)
    """
    try:
        logger.info(f"Fetching related papers for arXiv ID: {arxiv_id} using OpenAlex API")
        
        # If title and abstract are not provided, fetch them
        if title is None or abstract is None:
            try:
                paper_metadata = await fetch_paper_metadata(arxiv_id)
                title = paper_metadata.title
                abstract = paper_metadata.abstract
                logger.info(f"Fetched metadata for paper: {title}")
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
            
            logger.info(f"Found {len(related_papers)} related papers for arXiv ID: {arxiv_id}")
            return related_papers[:5]  # Limit to 5 related papers
        
    except Exception as e:
        logger.error(f"Error fetching related papers for arXiv ID {arxiv_id}: {str(e)}")
        # Return empty list instead of raising an exception
        # since related papers are not critical
        return [] 