import os
import httpx
import asyncio
import logging
import hashlib
from pathlib import Path
from uuid import UUID
from typing import Optional, Tuple, List, Dict, Any
import re
import tempfile

from app.core.logger import get_logger
from app.core.exceptions import PDFDownloadError, InvalidPDFUrlError
from app.database.supabase_client import get_paper_by_id
from app.api.v1.models import SourceType
from app.utils.pdf_utils import extract_text_from_pdf, clean_pdf_text

logger = get_logger(__name__)

# Create a cache directory for PDFs
PDF_CACHE_DIR = Path("./pdf_cache")
PDF_CACHE_DIR.mkdir(exist_ok=True)

# Create a directory for proxied PDFs
PROXIED_PDF_DIR = Path("./static/proxied_pdfs")
PROXIED_PDF_DIR.mkdir(parents=True, exist_ok=True)

async def read_pdf_file_to_bytes(file_path: str) -> bytes:
    """
    Read a PDF file into bytes.
    
    Args:
        file_path: The path to the PDF file
        
    Returns:
        The binary content of the PDF file
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        IOError: If there's an error reading the file
    """
    try:
        logger.info(f"Reading PDF file: {file_path}")
        with open(file_path, 'rb') as f:
            content = f.read()
        return content
    except FileNotFoundError:
        logger.error(f"PDF file not found: {file_path}")
        raise
    except IOError as e:
        logger.error(f"Error reading PDF file {file_path}: {str(e)}")
        raise

async def download_pdf(url: str, force_download: bool = False) -> Tuple[str, bool]:
    """
    Download a PDF from any URL and cache it locally.
    
    Args:
        url: The URL to the PDF
        force_download: Whether to force a re-download even if the PDF is cached
        
    Returns:
        Tuple containing the path to the downloaded PDF and a boolean indicating if it's a new download
        
    Raises:
        PDFDownloadError: If there's an error downloading the PDF
    """
    try:
        # Convert arXiv abstract URLs to PDF URLs
        if url.startswith('https://arxiv.org/abs/'):
            arxiv_id = url.split('https://arxiv.org/abs/')[1].split('v')[0].split('?')[0].strip()
            url = f'https://arxiv.org/pdf/{arxiv_id}.pdf'
            logger.info(f"Converted arXiv abstract URL to PDF URL: {url}")
        
        # Generate a cache filename based on the URL
        url_hash = hashlib.md5(url.encode()).hexdigest()
        cache_path = PDF_CACHE_DIR / f"{url_hash}.pdf"
        
        # Check if the file is already cached
        if cache_path.exists() and not force_download:
            logger.info(f"Using cached PDF for URL: {url}")
            return str(cache_path), False
        
        # Download the PDF
        logger.info(f"Downloading PDF from URL: {url}")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, follow_redirects=True, timeout=60.0)
            
            if response.status_code != 200:
                raise PDFDownloadError(f"Failed to download PDF: HTTP {response.status_code}")
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if 'application/pdf' not in content_type and not url.endswith('.pdf') and '/storage/v1/object/public/' not in url:
                raise InvalidPDFUrlError(f"URL does not point to a PDF: {url}")
            
            # Save the PDF to the cache
            with open(cache_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"Successfully downloaded PDF to {cache_path}")
            return str(cache_path), True
            
    except Exception as e:
        logger.error(f"Error downloading PDF from {url}: {str(e)}")
        raise PDFDownloadError(f"Error downloading PDF: {str(e)}")

async def get_paper_pdf(paper_id: UUID) -> Optional[str]:
    """
    Get the PDF for a paper by its ID.
    
    Args:
        paper_id: The UUID of the paper
        
    Returns:
        Path to the PDF file, or None if the paper doesn't exist
        
    Raises:
        PDFDownloadError: If there's an error downloading the PDF
    """
    try:
        # Get the paper from the database
        paper = await get_paper_by_id(paper_id)
        if not paper:
            logger.warning(f"Paper with ID {paper_id} not found")
            return None
        
        # Get the source URL
        source_url = paper.get("source_url")
        if not source_url:
            logger.warning(f"Paper with ID {paper_id} doesn't have a source URL")
            return None
        
        # For arXiv papers, convert abstract URL to PDF URL if needed
        source_type = paper.get("source_type", SourceType.PDF)
        if source_type == SourceType.ARXIV and 'arxiv.org/abs/' in source_url:
            # Extract arXiv ID and convert to PDF URL
            from app.services.url_service import extract_paper_id_from_url
            paper_ids = await extract_paper_id_from_url(source_url)
            arxiv_id = paper_ids.get('arxiv_id') or paper.get("arxiv_id")
            
            if arxiv_id:
                source_url = f'https://arxiv.org/pdf/{arxiv_id}.pdf'
                logger.info(f"Converted arXiv abstract URL to PDF URL: {source_url}")
        
        # Download the PDF
        pdf_path, _ = await download_pdf(source_url)
        return pdf_path
            
    except Exception as e:
        logger.error(f"Error getting PDF for paper with ID {paper_id}: {str(e)}")
        raise PDFDownloadError(f"Error getting PDF for paper with ID {paper_id}: {str(e)}")

async def download_and_process_paper(source_url: str, paper_id: Optional[UUID] = None, source_type: str = SourceType.ARXIV) -> str:
    """
    Download and extract text from a paper.
    
    This function:
    1. Downloads the PDF from the source URL
    2. Extracts text from the PDF using PyPDF2
    3. Cleans the extracted text
    
    Args:
        source_url: The URL to the paper
        paper_id: Optional UUID of the paper in the database
        source_type: The type of source ("arxiv", "pdf", or "file")
        
    Returns:
        The full text of the paper
        
    Raises:
        PDFDownloadError: If there's an error downloading or processing the PDF
    """
    try:
        logger.info(f"Processing paper from {source_type} source: {source_url}")
        
        # Download PDF
        pdf_path, is_new = await download_pdf(source_url)
        
        # Extract text from PDF using PyPDF2
        text = await extract_text_from_pdf(pdf_path)
        
        # Clean text
        text = await clean_pdf_text(text)
        
        # Additional sanitization to ensure database compatibility
        # Remove any remaining problematic characters
        text = re.sub(r'[^\x20-\x7E\n\r\t]', '', text)
        
        logger.info(f"Successfully extracted and sanitized text from PDF")
        
        return text
        
    except Exception as e:
        logger.error(f"Error processing PDF for source {source_url}: {str(e)}")
        raise PDFDownloadError(f"Error processing PDF: {str(e)}")

async def extract_text_from_pdf_bytes(file_content: bytes) -> str:
    """
    Extract text directly from PDF bytes without saving to disk first.
    
    Args:
        file_content: The binary content of the PDF file
        
    Returns:
        The extracted text from the PDF
        
    Raises:
        PDFDownloadError: If there's an error extracting text from the PDF bytes
    """
    try:
        logger.info("Extracting text from PDF bytes")
        
        # Create a temporary file to store the PDF content
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_file.write(file_content)
            temp_path = temp_file.name
        
        # Extract text from the temporary file
        text = await extract_text_from_pdf(temp_path)
        
        # Clean text
        text = await clean_pdf_text(text)
        
        # Additional sanitization to ensure database compatibility
        # Remove any remaining problematic characters
        text = re.sub(r'[^\x20-\x7E\n\r\t]', '', text)
        
        logger.info("Successfully extracted and sanitized text from PDF bytes")
        
        return text
        
    except Exception as e:
        logger.error(f"Error extracting text from PDF bytes: {str(e)}")
        raise PDFDownloadError(f"Error extracting text from PDF bytes: {str(e)}")

async def proxy_pdf_from_url(url: str, paper_id: Optional[str] = None) -> Dict[str, str]:
    """
    Download a PDF from an external URL and store it locally for proxying.
    
    Args:
        url: The URL to download the PDF from
        paper_id: Optional ID of the paper to use in the filename
        
    Returns:
        Dictionary containing the URL of the proxied PDF
        
    Raises:
        PDFDownloadError: If there's an error downloading the PDF
        InvalidPDFUrlError: If the URL doesn't point to a PDF
    """
    try:
        logger.info(f"Proxying PDF from URL: {url}")
        
        # Validate URL
        if not url:
            raise InvalidPDFUrlError("URL is required")
            
        # Generate a unique filename for the PDF
        if paper_id:
            filename = f"{paper_id}.pdf"
        else:
            # Create a filename based on the URL hash
            url_hash = hashlib.md5(url.encode()).hexdigest()
            filename = f"{url_hash}.pdf"
        
        # Define path where the PDF will be stored
        pdf_path = PROXIED_PDF_DIR / filename
        
        # Check if the file already exists
        if pdf_path.exists():
            logger.info(f"PDF already proxied: {filename}")
            return {"url": f"/static/proxied_pdfs/{filename}"}
        
        # Download the PDF
        logger.info(f"Downloading PDF from URL: {url}")
        
        # Convert arXiv abstract URLs to PDF URLs if needed
        if url.startswith('https://arxiv.org/abs/'):
            arxiv_id = url.split('https://arxiv.org/abs/')[1].split('v')[0].split('?')[0].strip()
            url = f'https://arxiv.org/pdf/{arxiv_id}.pdf'
            logger.info(f"Converted arXiv abstract URL to PDF URL: {url}")
        
        # Download the PDF
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url, 
                follow_redirects=True, 
                timeout=30.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Accept": "application/pdf"
                }
            )
            
            if response.status_code != 200:
                raise PDFDownloadError(f"Failed to download PDF: HTTP {response.status_code}")
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if 'application/pdf' not in content_type and not url.endswith('.pdf') and '/storage/v1/object/public/' not in url:
                raise InvalidPDFUrlError(f"URL does not point to a PDF: {url}")
            
            # Save the PDF
            with open(pdf_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"Successfully proxied PDF to {pdf_path}")
            return {"url": f"/static/proxied_pdfs/{filename}"}
            
    except PDFDownloadError as e:
        logger.error(f"Error downloading PDF for proxying: {str(e)}")
        raise
    except InvalidPDFUrlError as e:
        logger.error(f"Invalid PDF URL for proxying: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error proxying PDF from {url}: {str(e)}")
        raise PDFDownloadError(f"Error proxying PDF: {str(e)}") 