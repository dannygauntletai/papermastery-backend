import os
import httpx
import asyncio
import logging
from pathlib import Path
from uuid import UUID
from typing import Optional, Tuple

from app.core.logger import get_logger
from app.core.exceptions import PDFDownloadError
from app.database.supabase_client import get_paper_by_id

logger = get_logger(__name__)

# Create a cache directory for PDFs
PDF_CACHE_DIR = Path("./pdf_cache")
PDF_CACHE_DIR.mkdir(exist_ok=True)

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
    
    try:
        # Download the PDF
        logger.info(f"Downloading PDF from arXiv: {arxiv_pdf_url}")
        async with httpx.AsyncClient() as client:
            response = await client.get(arxiv_pdf_url, follow_redirects=True)
            
            if response.status_code != 200:
                raise PDFDownloadError(f"Failed to download PDF from arXiv: {response.status_code}")
            
            # Save the PDF to the cache
            with open(cache_path, "wb") as f:
                f.write(response.content)
            
            logger.info(f"PDF downloaded and cached at: {cache_path}")
            return str(cache_path.absolute()), True
            
    except Exception as e:
        logger.error(f"Error downloading PDF from arXiv: {str(e)}")
        raise PDFDownloadError(f"Error downloading PDF from arXiv: {str(e)}")

async def get_paper_pdf(paper_id: UUID) -> Optional[str]:
    """
    Get the PDF for a paper by its ID.
    
    Args:
        paper_id: The UUID of the paper
        
    Returns:
        Path to the PDF file, or None if the paper doesn't exist or doesn't have an arXiv ID
        
    Raises:
        PDFDownloadError: If there's an error downloading the PDF
    """
    try:
        # Get the paper from the database
        paper = await get_paper_by_id(paper_id)
        if not paper:
            logger.warning(f"Paper with ID {paper_id} not found")
            return None
            
        # Check if the paper has an arXiv ID
        arxiv_id = paper.get("arxiv_id")
        if not arxiv_id:
            logger.warning(f"Paper with ID {paper_id} doesn't have an arXiv ID")
            return None
            
        # Download the PDF
        pdf_path, _ = await download_arxiv_pdf(arxiv_id)
        return pdf_path
        
    except Exception as e:
        logger.error(f"Error getting PDF for paper with ID {paper_id}: {str(e)}")
        raise PDFDownloadError(f"Error getting PDF for paper with ID {paper_id}: {str(e)}") 