from dotenv import load_dotenv
import os
from typing import Optional

# Load environment variables from .env file
load_dotenv()

# Supabase configuration
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")

# Pinecone configuration
PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY", "")
PINECONE_ENVIRONMENT: str = os.getenv("PINECONE_ENVIRONMENT", "us-west1-gcp")
PINECONE_INDEX: str = os.getenv("PINECONE_INDEX", "arxiv-chunks")

# ArXiv API configuration
ARXIV_API_BASE_URL: str = os.getenv("ARXIV_API_BASE_URL", "http://export.arxiv.org/api/query")

# OpenAlex API configuration
OPENALEX_API_BASE_URL: str = os.getenv("OPENALEX_API_BASE_URL", "https://api.openalex.org/works")

# Logging configuration
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# Application configuration
APP_ENV: str = os.getenv("APP_ENV", "development")

# Validate critical configuration
def validate_config() -> None:
    """Validate that all required environment variables are set."""
    if not SUPABASE_URL:
        raise ValueError("SUPABASE_URL environment variable is not set")
    if not SUPABASE_KEY:
        raise ValueError("SUPABASE_KEY environment variable is not set")
    if not PINECONE_API_KEY:
        raise ValueError("PINECONE_API_KEY environment variable is not set")
        
# Call validation on import
validate_config() 