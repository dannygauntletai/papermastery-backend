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
from app.core.exceptions import InvalidPDFUrlError, PDFDownloadError, StorageError
from app.services.arxiv_service import fetch_paper_metadata as fetch_arxiv_metadata
from app.services.storage_service import get_file_url

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
    # Check if it's an arXiv URL
    if re.match(r'https?://arxiv.org/(?:abs|pdf)/\d+\.\d+(?:v\d+)?', url):
        logger.info(f"Detected arXiv URL: {url}")
        return SourceType.ARXIV
    
    # Check if it's a Supabase storage URL
    if re.search(r'/storage/v1/object/public/papers/', url):
        logger.info(f"Detected storage file URL: {url}")
        return SourceType.FILE
        
    # Check if it's a PDF URL
    try:
        # Check if URL ends with .pdf
        if url.lower().endswith('.pdf'):
            logger.info(f"Detected PDF URL (by extension): {url}")
            return SourceType.PDF
            
        # Make a HEAD request to check content type
        async with httpx.AsyncClient() as client:
            response = await client.head(url, follow_redirects=True, timeout=10.0)
            
            content_type = response.headers.get('content-type', '')
            if 'application/pdf' in content_type.lower():
                logger.info(f"Detected PDF URL (by content-type): {url}")
                return SourceType.PDF
    except Exception as e:
        logger.error(f"Error checking URL type: {str(e)}")
        
    # If we get here, it's not a valid URL
    logger.error(f"Invalid URL: {url}")
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
        url_type: The type of URL ("arxiv", "pdf", or "file")
        
    Returns:
        PaperMetadata object with the paper's metadata
        
    Raises:
        InvalidPDFUrlError: If the URL is not a valid PDF URL
        PDFDownloadError: If there's an error downloading the PDF
        StorageError: If there's an error with storage operations
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
            # Download the PDF
            async with httpx.AsyncClient() as client:
                response = await client.get(url, follow_redirects=True, timeout=30.0)
                
                if response.status_code != 200:
                    raise PDFDownloadError(f"Failed to download PDF: HTTP {response.status_code}")
                
                pdf_content = response.content
                
            # Extract metadata from PDF
            metadata = await extract_metadata_from_pdf(pdf_content, url)
            
            # Add source information
            metadata.source_type = SourceType.PDF
            metadata.source_url = url
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error processing PDF from URL {url}: {str(e)}")
            raise PDFDownloadError(f"Error processing PDF: {str(e)}")
    
    elif url_type == SourceType.FILE:
        # For storage files, extract metadata from the PDF
        try:
            # Download the PDF from storage
            async with httpx.AsyncClient() as client:
                response = await client.get(url, follow_redirects=True, timeout=30.0)
                
                if response.status_code != 200:
                    raise StorageError(f"Failed to download PDF from storage: HTTP {response.status_code}")
                
                pdf_content = response.content
                
            # Extract metadata from PDF
            metadata = await extract_metadata_from_pdf(pdf_content, url)
            
            # Add source information
            metadata.source_type = SourceType.FILE
            metadata.source_url = url
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error processing PDF from storage {url}: {str(e)}")
            raise StorageError(f"Error processing PDF from storage: {str(e)}")
    
    else:
        raise InvalidPDFUrlError(f"Unsupported URL type: {url_type}")

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
        abstract = "Abstract not available for direct PDF uploads."
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