import PyPDF2
import os
import tempfile
import requests
from app.core.logger import get_logger
from app.core.exceptions import PDFExtractionError
from typing import List, Tuple
import re

logger = get_logger(__name__)

async def download_pdf(url: str) -> str:
    """
    Download a PDF from a URL to a temporary file.
    
    Args:
        url: URL of the PDF to download
        
    Returns:
        Path to the downloaded PDF file
        
    Raises:
        PDFExtractionError: If the PDF cannot be downloaded
    """
    try:
        # Create a temporary file
        pdf_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        pdf_path = pdf_file.name
        
        # Download the PDF
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        with open(pdf_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        logger.info(f"Downloaded PDF from {url} to {pdf_path}")
        return pdf_path
    except Exception as e:
        logger.error(f"Failed to download PDF from {url}: {str(e)}")
        raise PDFExtractionError("N/A", f"Failed to download PDF from {url}: {str(e)}")
        
async def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from a PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Extracted text from the PDF
        
    Raises:
        PDFExtractionError: If the text cannot be extracted
    """
    try:
        with open(pdf_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            text = ""
            
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text += page.extract_text()
                
        logger.info(f"Extracted text from PDF {pdf_path}")
        
        # Clean up the temporary file if it exists
        if os.path.exists(pdf_path):
            os.unlink(pdf_path)
            logger.info(f"Deleted temporary PDF file {pdf_path}")
                
        return text
    except Exception as e:
        logger.error(f"Failed to extract text from PDF {pdf_path}: {str(e)}")
        
        # Clean up the temporary file if it exists
        if os.path.exists(pdf_path):
            os.unlink(pdf_path)
            logger.info(f"Deleted temporary PDF file {pdf_path}")
            
        raise PDFExtractionError(pdf_path, str(e))
        
async def clean_pdf_text(text: str) -> str:
    """
    Clean extracted text from a PDF, removing artifacts and fixing common issues.
    
    Args:
        text: Extracted text from a PDF
        
    Returns:
        Cleaned text
    """
    # Remove multiple consecutive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Remove page numbers
    text = re.sub(r'\n\s*\d+\s*\n', '\n', text)
    
    # Fix hyphenated words across line breaks
    text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)
    
    # Remove header/footer patterns (common in academic papers)
    # This is a simplified approach - might need customization for specific journals
    text = re.sub(r'\n.*(submitted|received|accepted|published).*\n', '\n', text, flags=re.IGNORECASE)
    
    return text 