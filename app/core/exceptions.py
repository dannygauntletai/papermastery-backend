from fastapi import HTTPException, status

class ArXivMasteryException(Exception):
    """Base exception for all ArXiv Mastery app exceptions."""
    pass

class InvalidArXivLinkError(ArXivMasteryException):
    """Raised when an invalid arXiv link is provided."""
    def __init__(self, link: str):
        self.link = link
        self.message = f"Invalid arXiv link: {link}"
        super().__init__(self.message)
        
class ArXivAPIError(ArXivMasteryException):
    """Raised when there is an error with the arXiv API."""
    def __init__(self, message: str):
        self.message = f"ArXiv API error: {message}"
        super().__init__(self.message)
        
class PDFExtractionError(ArXivMasteryException):
    """Raised when there is an error extracting text from a PDF."""
    def __init__(self, pdf_path: str, message: str):
        self.pdf_path = pdf_path
        self.message = f"Error extracting text from PDF {pdf_path}: {message}"
        super().__init__(self.message)
        
class PineconeError(ArXivMasteryException):
    """Raised when there is an error with Pinecone operations."""
    def __init__(self, message: str):
        self.message = f"Pinecone error: {message}"
        super().__init__(self.message)
        
class SupabaseError(ArXivMasteryException):
    """Raised when there is an error with Supabase operations."""
    def __init__(self, message: str):
        self.message = f"Supabase error: {message}"
        super().__init__(self.message)
        
class ChunkingError(ArXivMasteryException):
    """Raised when there is an error chunking text."""
    def __init__(self, message: str):
        self.message = f"Error chunking text: {message}"
        super().__init__(self.message)
        
# HTTP Exception Handlers
def http_exception_handler(exc):
    """Convert ArXiv Mastery exceptions to appropriate HTTP exceptions."""
    if isinstance(exc, InvalidArXivLinkError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message
        )
    elif isinstance(exc, ArXivAPIError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=exc.message
        )
    elif isinstance(exc, PDFExtractionError):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.message
        )
    elif isinstance(exc, (PineconeError, SupabaseError)):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=exc.message
        )
    elif isinstance(exc, ChunkingError):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.message
        )
    else:
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc)
        ) 