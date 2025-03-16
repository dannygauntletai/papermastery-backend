import os
import httpx
import asyncio
import logging
import hashlib
from pathlib import Path
from uuid import UUID
from typing import Optional, Tuple, List, Dict, Any

from app.core.logger import get_logger
from app.core.exceptions import PDFDownloadError, InvalidPDFUrlError
from app.database.supabase_client import get_paper_by_id
from app.api.v1.models import SourceType
from app.utils.pdf_utils import extract_text_from_pdf, clean_pdf_text

logger = get_logger(__name__)

# Create a cache directory for PDFs
PDF_CACHE_DIR = Path("./pdf_cache")
PDF_CACHE_DIR.mkdir(exist_ok=True)

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

async def download_arxiv_pdf(arxiv_id: str, force_download: bool = False) -> Tuple[str, bool]:
    """
    Download a PDF from arXiv and cache it locally.
    
    Args:
        arxiv_id: The arXiv ID of the paper
        force_download: Whether to force a re-download even if the PDF is cached
        
    Returns:
        Tuple containing (path to the PDF file, whether it was newly downloaded)
        
    Raises:
        PDFDownloadError: If there's an error downloading the PDF
    """
    # Clean the arXiv ID (remove version if present)
    clean_arxiv_id = arxiv_id.split('v')[0] if 'v' in arxiv_id else arxiv_id
    
    # Define the cache path
    cache_path = PDF_CACHE_DIR / f"{clean_arxiv_id}.pdf"
    
    # Check if the PDF is already cached
    if cache_path.exists() and not force_download:
        logger.info(f"Using cached PDF for arXiv ID: {arxiv_id}")
        return str(cache_path.absolute()), False
    
    # Construct the arXiv PDF URL
    arxiv_pdf_url = f"https://arxiv.org/pdf/{clean_arxiv_id}.pdf"
    
    # Use the generic download function
    return await download_pdf(arxiv_pdf_url, force_download)

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
        
        # Check the source type
        source_type = paper.get("source_type", SourceType.ARXIV)
        
        if source_type == SourceType.ARXIV:
            # Check if the paper has an arXiv ID
            arxiv_id = paper.get("arxiv_id")
            if not arxiv_id:
                # Try to extract arXiv ID from source_url
                source_url = paper.get("source_url")
                if source_url:
                    from app.services.url_service import extract_arxiv_id_from_url
                    arxiv_id = await extract_arxiv_id_from_url(source_url)
                
                if not arxiv_id:
                    logger.warning(f"Paper with ID {paper_id} doesn't have an arXiv ID and couldn't extract one from source_url")
                    return None
                
            # Download the PDF
            pdf_path, _ = await download_arxiv_pdf(arxiv_id)
            return pdf_path
        
        elif source_type == SourceType.PDF:
            # Check if the paper has a source URL
            source_url = paper.get("source_url")
            if not source_url:
                logger.warning(f"Paper with ID {paper_id} doesn't have a source URL")
                return None
                
            # Download the PDF
            pdf_path, _ = await download_pdf(source_url)
            return pdf_path
        
        else:
            logger.warning(f"Unsupported source type for paper with ID {paper_id}: {source_type}")
            return None
            
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
        
        logger.info(f"Successfully extracted text from PDF")
        
        return text
        
    except Exception as e:
        logger.error(f"Error processing PDF for source {source_url}: {str(e)}")
        raise PDFDownloadError(f"Error processing PDF: {str(e)}") 