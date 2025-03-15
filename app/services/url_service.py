import re
import httpx
import asyncio
from typing import Tuple, Optional
from datetime import datetime
import PyPDF2
import tempfile
import io

from app.api.v1.models import PaperMetadata, Author, SourceType
from app.core.logger import get_logger
from app.core.exceptions import InvalidPDFUrlError, PDFDownloadError
from app.services.arxiv_service import fetch_paper_metadata as fetch_arxiv_metadata

logger = get_logger(__name__)

async def detect_url_type(url: str) -> str:
    """
    Detect the type of URL (arXiv or PDF).
    
    Args:
        url: The URL to check
        
    Returns:
        String indicating the URL type: "arxiv" or "pdf"
        
    Raises:
        InvalidPDFUrlError: If the URL is not a valid arXiv or PDF URL
    """
    # Check if it's an arXiv URL
    if re.match(r'https?://arxiv.org/(?:abs|pdf)/\d+\.\d+(?:v\d+)?', url):
        logger.info(f"URL {url} detected as arXiv")
        return SourceType.ARXIV
    
    # Check if it's a PDF URL by making a HEAD request
    try:
        async with httpx.AsyncClient() as client:
            response = await client.head(url, follow_redirects=True, timeout=10.0)
            
            content_type = response.headers.get('content-type', '').lower()
            if 'application/pdf' in content_type:
                logger.info(f"URL {url} detected as PDF (content-type: {content_type})")
                return SourceType.PDF
            else:
                logger.warning(f"URL {url} has non-PDF content-type: {content_type}")
                raise InvalidPDFUrlError(url)
    except httpx.RequestError as e:
        logger.error(f"Error checking URL {url}: {str(e)}")
        raise InvalidPDFUrlError(url)

async def is_pdf_url(url: str) -> bool:
    """
    Check if a URL points to a PDF by making a HEAD request.
    
    Args:
        url: The URL to check
        
    Returns:
        True if the URL points to a PDF, False otherwise
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.head(url, follow_redirects=True, timeout=10.0)
            
            content_type = response.headers.get('content-type', '').lower()
            return 'application/pdf' in content_type
    except httpx.RequestError:
        return False

async def extract_arxiv_id_from_url(url: str) -> Optional[str]:
    """
    Extract the arXiv ID from an arXiv URL.
    
    Args:
        url: The arXiv URL
        
    Returns:
        The arXiv ID, or None if the URL is not an arXiv URL
    """
    match = re.match(r'https?://arxiv.org/(?:abs|pdf)/(\d+\.\d+(?:v\d+)?)', url)
    if match:
        arxiv_id = match.group(1)
        # Remove version if present
        if 'v' in arxiv_id:
            arxiv_id = arxiv_id.split('v')[0]
        return arxiv_id
    return None

async def fetch_metadata_from_url(url: str, url_type: str) -> PaperMetadata:
    """
    Fetch metadata for a paper from its URL.
    
    Args:
        url: The URL to the paper
        url_type: The type of URL ("arxiv" or "pdf")
        
    Returns:
        PaperMetadata object with the paper's metadata
        
    Raises:
        InvalidPDFUrlError: If the URL is not a valid PDF URL
        PDFDownloadError: If there's an error downloading the PDF
    """
    if url_type == SourceType.ARXIV:
        # Extract arXiv ID from URL
        arxiv_id = await extract_arxiv_id_from_url(url)
        if not arxiv_id:
            raise InvalidPDFUrlError(url)
        
        # Use existing arXiv service to fetch metadata
        metadata = await fetch_arxiv_metadata(arxiv_id)
        
        # Add source information
        metadata.source_type = SourceType.ARXIV
        metadata.source_url = url
        
        return metadata
    
    elif url_type == SourceType.PDF:
        # Download PDF and extract metadata
        try:
            # Download PDF
            async with httpx.AsyncClient() as client:
                response = await client.get(url, follow_redirects=True)
                
                if response.status_code != 200:
                    raise PDFDownloadError(f"Failed to download PDF: HTTP {response.status_code}")
                
                # Check content type
                content_type = response.headers.get('content-type', '').lower()
                if 'application/pdf' not in content_type:
                    raise InvalidPDFUrlError(url)
                
                # Extract metadata from PDF
                pdf_content = io.BytesIO(response.content)
                
                try:
                    pdf_reader = PyPDF2.PdfReader(pdf_content)
                    info = pdf_reader.metadata
                    
                    # Extract title
                    title = info.get('/Title', 'Untitled PDF')
                    if not title or title == '':
                        # Try to extract from first page text
                        if len(pdf_reader.pages) > 0:
                            first_page_text = pdf_reader.pages[0].extract_text()
                            # Use first line as title (simplified approach)
                            lines = first_page_text.strip().split('\n')
                            if lines:
                                title = lines[0][:100]  # Limit title length
                    
                    # Extract authors
                    author_str = info.get('/Author', '')
                    if author_str:
                        # Split author string by common separators
                        author_names = re.split(r',|;|and', author_str)
                        authors = [Author(name=name.strip()) for name in author_names if name.strip()]
                    else:
                        authors = [Author(name="Unknown Author")]
                    
                    # Create metadata
                    metadata = PaperMetadata(
                        title=title,
                        authors=authors,
                        abstract="Abstract not available for direct PDF uploads.",
                        publication_date=datetime.now(),
                        source_type=SourceType.PDF,
                        source_url=url
                    )
                    
                    return metadata
                    
                except Exception as e:
                    logger.error(f"Error extracting metadata from PDF: {str(e)}")
                    # Return basic metadata if extraction fails
                    return PaperMetadata(
                        title=f"PDF from {url.split('/')[-1]}",
                        authors=[Author(name="Unknown Author")],
                        abstract="Abstract not available for this PDF.",
                        publication_date=datetime.now(),
                        source_type=SourceType.PDF,
                        source_url=url
                    )
                
        except Exception as e:
            logger.error(f"Error processing PDF URL {url}: {str(e)}")
            raise PDFDownloadError(f"Error processing PDF: {str(e)}")
    
    else:
        raise InvalidPDFUrlError(f"Unsupported URL type: {url_type}") 