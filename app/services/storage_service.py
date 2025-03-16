import os
import uuid
import httpx
from typing import Optional, Tuple
import mimetypes
from datetime import datetime

from app.core.logger import get_logger
from app.core.config import (
    SUPABASE_URL,
    SUPABASE_SERVICE_KEY,
    SUPABASE_STORAGE_BUCKET,
    MAX_FILE_SIZE_MB
)
from app.core.exceptions import StorageError

logger = get_logger(__name__)

# Maximum file size in bytes (default to 10MB if not specified)
MAX_FILE_SIZE = int(MAX_FILE_SIZE_MB or 10) * 1024 * 1024

async def upload_file_to_storage(file_content: bytes, file_name: str) -> str:
    """
    Upload a file to Supabase storage.
    
    Args:
        file_content: The binary content of the file
        file_name: The name of the file
        
    Returns:
        The path to the file in storage
        
    Raises:
        StorageError: If there's an error uploading the file
    """
    try:
        # Check file size
        if len(file_content) > MAX_FILE_SIZE:
            max_size_mb = MAX_FILE_SIZE // (1024 * 1024)
            raise StorageError(f"File size exceeds maximum allowed size of {max_size_mb}MB")
        
        # Check file type
        content_type = mimetypes.guess_type(file_name)[0]
        if content_type != 'application/pdf':
            raise StorageError("Only PDF files are supported")
        
        # Generate a unique file path to avoid collisions
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        file_path = f"{timestamp}_{unique_id}_{file_name}"
        
        # Construct the storage API URL
        storage_url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_STORAGE_BUCKET}/{file_path}"
        
        # Upload the file
        headers = {
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "Content-Type": content_type
        }
        
        logger.info(f"Uploading file {file_name} to Supabase storage")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                storage_url,
                headers=headers,
                content=file_content,
                timeout=60.0  # Longer timeout for file uploads
            )
            
            if response.status_code != 200:
                logger.error(f"Error uploading file to storage: {response.text}")
                raise StorageError(f"Error uploading file: {response.text}")
            
            logger.info(f"Successfully uploaded file to {file_path}")
            return file_path
            
    except Exception as e:
        logger.error(f"Error uploading file to storage: {str(e)}")
        raise StorageError(f"Error uploading file: {str(e)}")

async def get_file_url(file_path: str) -> str:
    """
    Generate a public URL for a file in storage.
    
    Args:
        file_path: The path to the file in storage
        
    Returns:
        The public URL for the file
    """
    return f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_STORAGE_BUCKET}/{file_path}"

async def delete_file_from_storage(file_path: str) -> bool:
    """
    Delete a file from Supabase storage.
    
    Args:
        file_path: The path to the file in storage
        
    Returns:
        True if the file was deleted successfully, False otherwise
    """
    try:
        # Construct the storage API URL
        storage_url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_STORAGE_BUCKET}/{file_path}"
        
        # Delete the file
        headers = {
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"
        }
        
        logger.info(f"Deleting file {file_path} from Supabase storage")
        
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                storage_url,
                headers=headers,
                timeout=30.0
            )
            
            if response.status_code != 200:
                logger.error(f"Error deleting file from storage: {response.text}")
                return False
            
            logger.info(f"Successfully deleted file {file_path}")
            return True
            
    except Exception as e:
        logger.error(f"Error deleting file from storage: {str(e)}")
        return False 