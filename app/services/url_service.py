import re
import httpx
import asyncio
from typing import Tuple, Optional, Dict
from datetime import datetime
import PyPDF2
import tempfile
import io

from app.api.v1.models import PaperMetadata, Author, SourceType
from app.core.logger import get_logger
from app.core.exceptions import InvalidPDFUrlError, PDFDownloadError, StorageError
from app.services.storage_service import get_file_url
from app.utils.url_utils import extract_paper_id_from_url

logger = get_logger(__name__)

async def detect_url_type(url: str) -> str:
    """
    Detect the type of URL (arXiv, PDF, or storage file).
    
    Args:
        url: The URL to check
        
    Returns:
        String indicating the URL type: "arxiv", "pdf", or "file"
        
    Raises:
        InvalidPDFUrlError: If the URL is not a valid arXiv, PDF, or storage URL
    """
    # Check if it's an arXiv URL (both abs and pdf formats)
    if re.match(r'https?://arxiv.org/(?:abs|pdf)/\d+\.\d+(?:v\d+)?', url):
        logger.info(f"Detected arXiv URL: {url}")
        return SourceType.ARXIV
        
    # Check if it's a storage URL
    if 'storage.googleapis.com' in url or 'supabase.co/storage' in url:
        logger.info(f"Detected storage URL: {url}")
        return SourceType.FILE
        
    # Check if it's a PDF URL
    if url.lower().endswith('.pdf'):
        logger.info(f"Detected PDF URL by extension: {url}")
        return SourceType.PDF
        
    # If not obvious from the URL, try to check the content type
    try:
        is_pdf = await is_pdf_url(url)
        if is_pdf:
            logger.info(f"Detected PDF URL by content type: {url}")
            return SourceType.PDF
    except Exception as e:
        logger.warning(f"Error checking content type for URL {url}: {str(e)}")
        
    # If we get here, we couldn't determine the URL type
    logger.warning(f"Could not determine URL type for {url}")
    raise InvalidPDFUrlError(f"URL does not appear to be a valid arXiv or PDF URL: {url}")


async def is_pdf_url(url: str) -> bool:
    """
    Check if a URL points to a PDF by examining the content type.
    
    Args:
        url: The URL to check
        
    Returns:
        True if the URL points to a PDF, False otherwise
    """
    try:
        async with httpx.AsyncClient() as client:
            # Just get the headers to check content type
            response = await client.head(url, follow_redirects=True, timeout=10.0)
            
            content_type = response.headers.get('content-type', '')
            return 'application/pdf' in content_type.lower()
    except Exception as e:
        logger.warning(f"Error checking if URL is PDF: {str(e)}")
        return False


async def extract_arxiv_id_from_url(url: str) -> Optional[str]:
    """
    Extract the arXiv ID from an arXiv URL.
    
    Args:
        url: The arXiv URL (can be abs or pdf format)
        
    Returns:
        The arXiv ID, or None if the URL is not an arXiv URL
    """
    paper_ids = await extract_paper_id_from_url(url)
    return paper_ids.get('arxiv_id')


async def fetch_metadata_from_url(url: str, url_type: str) -> PaperMetadata:
    """
    Fetch metadata for a paper from its URL.
    
    Args:
        url: The URL to the paper
        url_type: The type of URL ("arxiv", "pdf", or "file")
        
    Returns:
        PaperMetadata object with the paper's metadata
        
    Raises:
        InvalidPDFUrlError: If the URL is not a valid paper URL
        PDFDownloadError: If there's an error downloading the PDF
    """
    # Extract paper identifiers from URL
    paper_ids = await extract_paper_id_from_url(url)
    
    # For arXiv papers, use the arXiv API to fetch metadata
    if url_type == SourceType.ARXIV and paper_ids.get('arxiv_id'):
        try:
            # Import here to avoid circular imports
            from app.services.paper_service import fetch_arxiv_metadata
            
            # Use existing arXiv service to fetch metadata
            metadata = await fetch_arxiv_metadata(paper_ids['arxiv_id'])
            
            # Ensure source type is set correctly
            metadata.source_type = SourceType.ARXIV
            metadata.source_url = url
            
            return metadata
        except Exception as e:
            logger.error(f"Error fetching arXiv metadata for {url}: {str(e)}")
            # Fall back to PDF extraction if arXiv API fails
            pass
    
    # For all other types (PDF, FILE) or if arXiv API fails, extract metadata from PDF
    try:
        # Download the PDF
        async with httpx.AsyncClient() as client:
            response = await client.get(url, follow_redirects=True, timeout=30.0)
            
            if response.status_code != 200:
                raise PDFDownloadError(f"Failed to download PDF from {url}: HTTP {response.status_code}")
                
            pdf_content = response.content
            
        # Extract metadata from PDF
        metadata = await extract_metadata_from_pdf(pdf_content, url)
        
        # Set source type and URL
        metadata.source_type = url_type
        metadata.source_url = url
        
        # Add paper IDs if available
        if paper_ids.get('arxiv_id'):
            metadata.arxiv_id = paper_ids['arxiv_id']
        if paper_ids.get('doi'):
            metadata.doi = paper_ids['doi']
            
        return metadata
    except Exception as e:
        logger.error(f"Error extracting metadata from PDF at {url}: {str(e)}")
        raise PDFDownloadError(f"Error extracting metadata from PDF: {str(e)}")

async def extract_metadata_from_pdf(pdf_content: bytes, source_url: str) -> PaperMetadata:
    """
    Extract metadata from PDF content.
    
    Args:
        pdf_content: The binary content of the PDF
        source_url: The source URL of the PDF (for reference)
        
    Returns:
        PaperMetadata object with the extracted metadata
    """
    try:
        pdf_file = io.BytesIO(pdf_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        info = pdf_reader.metadata
        
        # Extract title
        title = info.get('/Title', '')
        if not title or title == '':
            # Try to extract from first page text
            if len(pdf_reader.pages) > 0:
                first_page_text = pdf_reader.pages[0].extract_text()
                # Use first line as title (simplified approach)
                lines = first_page_text.strip().split('\n')
                if lines:
                    title = lines[0][:100]  # Limit title length
                else:
                    title = f"PDF from {source_url.split('/')[-1]}"
            else:
                title = f"PDF from {source_url.split('/')[-1]}"
        
        # Extract authors
        author_str = info.get('/Author', '')
        if author_str:
            # Split author string by common separators
            author_names = re.split(r',|;|and', author_str)
            authors = [Author(name=name.strip(), affiliations=[]) for name in author_names if name.strip()]
        else:
            authors = [Author(name="Unknown Author", affiliations=[])]
        
        # Extract abstract
        abstract = "Unable to extract abstract from PDF"
        if len(pdf_reader.pages) > 0:
            # Try to extract abstract from first page
            first_page_text = pdf_reader.pages[0].extract_text()
            # Look for common abstract indicators
            abstract_patterns = [
                r'Abstract[:\s]+(.*?)(?=\n\n|\n[A-Z][a-z]+:|\n\d+\.|\n[A-Z][A-Z]+\s)',
                r'ABSTRACT[:\s]+(.*?)(?=\n\n|\n[A-Z][a-z]+:|\n\d+\.|\n[A-Z][A-Z]+\s)'
            ]
            
            for pattern in abstract_patterns:
                match = re.search(pattern, first_page_text, re.DOTALL)
                if match:
                    abstract = match.group(1).strip()
                    # Limit abstract length
                    if len(abstract) > 500:
                        abstract = abstract[:497] + "..."
                    break
        
        # Create metadata
        metadata = PaperMetadata(
            title=title,
            authors=authors,
            abstract=abstract,
            publication_date=datetime.now(),
            source_url=source_url,
            source_type=SourceType.PDF  # This will be overridden by the caller
        )
        
        return metadata
        
    except Exception as e:
        logger.error(f"Error extracting metadata from PDF: {str(e)}")
        # Return basic metadata if extraction fails
        return PaperMetadata(
            title=f"PDF from {source_url.split('/')[-1]}",
            authors=[Author(name="Unknown Author", affiliations=[])],
            abstract="Abstract not available for this PDF.",
            publication_date=datetime.now(),
            source_url=source_url,
            source_type=SourceType.PDF  # This will be overridden by the caller
        ) 