from dotenv import load_dotenv
import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field

# Load environment variables from .env file
load_dotenv()

# Make sure important environment variables are properly set
openai_key = os.getenv("OPENAI_API_KEY")
if openai_key:
    os.environ["OPENAI_API_KEY"] = openai_key
    print(f"Config: Using OpenAI API key from .env: {openai_key[:8]}...")

# Make sure Gemini API key is properly set
gemini_key = os.getenv("GEMINI_API_KEY")
if gemini_key:
    os.environ["GEMINI_API_KEY"] = gemini_key
    print(f"Config: Using Gemini API key from .env: {gemini_key[:8]}...")

class Settings(BaseSettings):
    """Application settings with validation and defaults."""
    
    # Supabase configuration
    SUPABASE_URL: str = Field(default_factory=lambda: os.getenv("SUPABASE_URL", ""))
    SUPABASE_KEY: str = Field(default_factory=lambda: os.getenv("SUPABASE_KEY", ""))
    SUPABASE_SERVICE_KEY: str = Field(default_factory=lambda: os.getenv("SUPABASE_SERVICE_KEY", ""))
    SUPABASE_STORAGE_BUCKET: str = Field(default_factory=lambda: os.getenv("SUPABASE_STORAGE_BUCKET", "papers"))
    MAX_FILE_SIZE_MB: int = Field(default_factory=lambda: int(os.getenv("MAX_FILE_SIZE_MB", "10")))
    
    # Pinecone configuration
    PINECONE_API_KEY: str = Field(default_factory=lambda: os.getenv("PINECONE_API_KEY", ""))
    PINECONE_ENVIRONMENT: str = Field(default_factory=lambda: os.getenv("PINECONE_ENVIRONMENT", "us-west1-gcp"))
    PINECONE_INDEX: str = Field(default_factory=lambda: os.getenv("PINECONE_INDEX", "arxiv-chunks"))
    
    # ArXiv API configuration
    ARXIV_API_BASE_URL: str = Field(default_factory=lambda: os.getenv("ARXIV_API_BASE_URL", "http://export.arxiv.org/api/query"))
    
    # OpenAlex API configuration
    OPENALEX_API_BASE_URL: str = Field(default_factory=lambda: os.getenv("OPENALEX_API_BASE_URL", "https://api.openalex.org/works"))
    
    # OpenAI API configuration
    OPENAI_API_KEY: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    OPENAI_MODEL: str = Field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o"))
    OPENAI_EMBEDDING_MODEL: str = Field(default_factory=lambda: os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large"))
    
    # Gemini API configuration
    GEMINI_API_KEY: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    GEMINI_MODEL: str = Field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-1.5-pro"))
    
    # YouTube API configuration
    YOUTUBE_API_KEY: str = Field(default_factory=lambda: os.getenv("YOUTUBE_API_KEY", ""))
    
    # SendGrid configuration
    SENDGRID_API_KEY: str = Field(default_factory=lambda: os.getenv("SENDGRID_API_KEY", ""))
    SENDGRID_FROM_EMAIL: str = Field(default_factory=lambda: os.getenv("SENDGRID_FROM_EMAIL", ""))
    
    # Learning services configuration
    ANKIFLASHCARDS_API_KEY: str = Field(default_factory=lambda: os.getenv("ANKIFLASHCARDS_API_KEY", ""))
    PAPERQA_API_KEY: str = Field(default_factory=lambda: os.getenv("PAPERQA_API_KEY", ""))
    
    # Logging configuration
    LOG_LEVEL: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    
    # Application configuration
    APP_ENV: str = Field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    
    def validate_config(self) -> None:
        """Validate that all required environment variables are set."""
        errors = []
        
        if not self.SUPABASE_URL:
            errors.append("SUPABASE_URL environment variable is not set")
        if not self.SUPABASE_KEY:
            errors.append("SUPABASE_KEY environment variable is not set")
        if not self.PINECONE_API_KEY:
            errors.append("PINECONE_API_KEY environment variable is not set")
        if not self.OPENAI_API_KEY and not self.GEMINI_API_KEY and self.APP_ENV != "testing":
            errors.append("Either OPENAI_API_KEY or GEMINI_API_KEY environment variable must be set for non-testing environments")
            
        if errors:
            raise ValueError("\n".join(errors))

# For backward compatibility
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_STORAGE_BUCKET: str = os.getenv("SUPABASE_STORAGE_BUCKET", "papers")
MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY", "")
PINECONE_ENVIRONMENT: str = os.getenv("PINECONE_ENVIRONMENT", "us-west1-gcp")
PINECONE_INDEX: str = os.getenv("PINECONE_INDEX", "arxiv-chunks")
ARXIV_API_BASE_URL: str = os.getenv("ARXIV_API_BASE_URL", "http://export.arxiv.org/api/query")
OPENALEX_API_BASE_URL: str = os.getenv("OPENALEX_API_BASE_URL", "https://api.openalex.org/works")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
SENDGRID_API_KEY: str = os.getenv("SENDGRID_API_KEY", "")
SENDGRID_FROM_EMAIL: str = os.getenv("SENDGRID_FROM_EMAIL", "")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
APP_ENV: str = os.getenv("APP_ENV", "development")

_settings = None

def get_settings() -> Settings:
    """Get application settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
        # Only validate in non-testing environments
        if _settings.APP_ENV != "testing":
            _settings.validate_config()
    return _settings

# The original validation function, kept for backward compatibility
def validate_config() -> None:
    """Validate that all required environment variables are set."""
    if not SUPABASE_URL:
        raise ValueError("SUPABASE_URL environment variable is not set")
    if not SUPABASE_KEY:
        raise ValueError("SUPABASE_KEY environment variable is not set")
    if not PINECONE_API_KEY:
        raise ValueError("PINECONE_API_KEY environment variable is not set")
    if not OPENAI_API_KEY and not GEMINI_API_KEY and APP_ENV != "testing":
        raise ValueError("Either OPENAI_API_KEY or GEMINI_API_KEY environment variable must be set for non-testing environments") 