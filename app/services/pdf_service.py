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
from app.services.pinecone_service import process_pdf_with_langchain

logger = get_logger(__name__)

# Create a cache directory for PDFs
PDF_CACHE_DIR = Path("./pdf_cache")
PDF_CACHE_DIR.mkdir(exist_ok=True)

async def download_pdf(url: str, force_download: bool = False) -> Tuple[str, bool]:
    """
    Download a PDF from any URL and cache it locally.
    
    Args:
        url: The URL to the PDF
        force_download: Whether to force a re-download even if the PDF is cached
        
    Returns:
        Tuple containing (path to the PDF file, whether it was newly downloaded)
        
    Raises:
        PDFDownloadError: If there's an error downloading the PDF
        InvalidPDFUrlError: If the URL does not point to a PDF
    """
    # Generate a unique filename based on the URL
    url_hash = hashlib.md5(url.encode()).hexdigest()
    cache_path = PDF_CACHE_DIR / f"{url_hash}.pdf"
    
    # Check if the PDF is already cached
    if cache_path.exists() and not force_download:
        logger.info(f"Using cached PDF for URL: {url}")
        return str(cache_path.absolute()), False
    
    try:
        # Download the PDF
        logger.info(f"Downloading PDF from URL: {url}")
        async with httpx.AsyncClient() as client:
            response = await client.get(url, follow_redirects=True)
            
            if response.status_code != 200:
                raise PDFDownloadError(f"Failed to download PDF: HTTP {response.status_code}")
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if 'application/pdf' not in content_type:
                raise InvalidPDFUrlError(url)
            
            # Save the PDF to the cache
            with open(cache_path, "wb") as f:
                f.write(response.content)
            
            logger.info(f"PDF downloaded and cached at: {cache_path}")
            return str(cache_path.absolute()), True
            
    except httpx.RequestError as e:
        logger.error(f"Error downloading PDF from URL {url}: {str(e)}")
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

async def download_and_process_paper(url: str, paper_id: Optional[UUID] = None, source_type: str = SourceType.PDF) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Download and process a paper from any URL.
    
    This function:
    1. Downloads the PDF from the URL
    2. Extracts text from the PDF
    3. Processes it using LangChain (if available) or fallback to basic processing
    4. Breaks it into logical chunks with metadata
    
    Args:
        url: The URL to the PDF
        paper_id: Optional UUID of the paper in the database
        source_type: The type of source ("arxiv" or "pdf")
        
    Returns:
        Tuple containing full text and a list of text chunks with metadata
        
    Raises:
        PDFDownloadError: If there's an error downloading the PDF
        InvalidPDFUrlError: If the URL does not point to a PDF
    """
    try:
        logger.info(f"Downloading PDF for URL: {url}")
        
        # Download PDF
        if source_type == SourceType.ARXIV:
            # Extract arXiv ID from URL
            from app.services.url_service import extract_arxiv_id_from_url
            arxiv_id = await extract_arxiv_id_from_url(url)
            if not arxiv_id:
                raise InvalidPDFUrlError(url)
            pdf_path, _ = await download_arxiv_pdf(arxiv_id)
        else:
            pdf_path, _ = await download_pdf(url)
        
        # Always try processing with LangChain first
        try:
            logger.info(f"Processing PDF with LangChain for URL: {url}")
            formatted_chunks, langchain_chunks = await process_pdf_with_langchain(
                pdf_path, 
                paper_id or UUID('00000000-0000-0000-0000-000000000000')
            )
            
            # Combine all text for full text
            full_text = "\n\n".join([chunk.get("text", "") for chunk in formatted_chunks])
            
            logger.info(f"Successfully processed PDF with LangChain for URL: {url}")
            return full_text, formatted_chunks
                
        except Exception as langchain_error:
            logger.warning(f"LangChain processing failed, falling back to basic processing: {str(langchain_error)}")
            # Continue with basic processing if LangChain fails
        
        # Fallback to basic processing
        # Extract text from PDF
        text = await extract_text_from_pdf(pdf_path)
        
        # Clean text
        text = await clean_pdf_text(text)
        
        # Basic chunking (simplified)
        chunks = []
        paragraphs = text.split("\n\n")
        for i, paragraph in enumerate(paragraphs):
            if paragraph.strip():
                chunks.append({
                    "text": paragraph,
                    "metadata": {
                        "chunk_index": i,
                        "paper_id": str(paper_id) if paper_id else "unknown"
                    }
                })
        
        logger.info(f"Fallback processing completed for URL: {url}")
        return text, chunks
        
    except Exception as e:
        logger.error(f"Error processing PDF from URL {url}: {str(e)}")
        raise PDFDownloadError(f"Error processing PDF: {str(e)}") 