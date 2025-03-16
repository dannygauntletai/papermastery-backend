from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks, Query, Request, File, Form, UploadFile, Body
from typing import List, Optional, Dict, Any, Union
from uuid import UUID
import uuid
import json

from app.api.v1.models import PaperSubmission, PaperResponse, PaperSummary, SourceType
from app.core.logger import get_logger
from app.services.arxiv_service import (
    fetch_paper_metadata,
    get_related_papers
)
from app.services.pdf_service import download_and_process_paper
from app.services.url_service import detect_url_type, fetch_metadata_from_url, extract_arxiv_id_from_url
from app.database.supabase_client import (
    get_paper_by_arxiv_id,
    get_paper_by_id,
    get_paper_by_source,
    insert_paper,
    update_paper,
    list_papers as db_list_papers,
    add_paper_to_user,
    create_conversation,
    get_user_paper_conversations
)
from app.services.chunk_service import chunk_text
from app.services.pinecone_service import store_chunks
from app.services.summarization_service import generate_summaries
from app.services.learning_service import generate_learning_path
from app.dependencies import validate_environment, get_current_user
from app.core.exceptions import InvalidPDFUrlError
from app.services.storage_service import upload_file_to_storage, get_file_url
from app.core.exceptions import StorageError

logger = get_logger(__name__)

router = APIRouter(
    prefix="/papers",
    tags=["papers"],
    dependencies=[Depends(validate_environment)],
    responses={404: {"description": "Paper not found"}},
)


@router.post("/submit", response_model=PaperResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_paper(
    request: Request,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user),
    file: Optional[UploadFile] = File(None),
):
    """
    Submit a paper for processing.
    
    The submission is accepted immediately, and processing happens in the background.
    Check the status of the paper by retrieving it with GET /papers/{id}.
    
    Supports both JSON and multipart/form-data requests:
    - For JSON: Send a JSON object with source_url and source_type
    - For form data: Send file, source_url, and source_type as form fields
    
    Args:
        request: The FastAPI request object
        file: The PDF file (for file uploads)
        background_tasks: FastAPI background tasks
        user_id: The ID of the authenticated user
        
    Returns:
        The paper data with processing status
    """
    logger.info(f"Received paper submission from user {user_id}")
    
    # Determine if this is a JSON request or a form data request
    content_type = request.headers.get("content-type", "")
    
    # Handle JSON request
    if "application/json" in content_type:
        try:
            body = await request.json()
            source_url = body.get("source_url")
            source_type = body.get("source_type")
            
            if not source_url:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="source_url is required for JSON requests"
                )
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON body"
            )
    # Handle form data request
    else:
        form = await request.form()
        source_url = form.get("source_url")
        source_type = form.get("source_type")
        file = form.get("file")
    
    # Handle file uploads
    if file:
        source_type = SourceType.FILE
        file_name = file.filename
        file_content = await file.read()
        
        logger.info(f"Received file upload from user {user_id}: {file_name}")
        
        try:
            # Upload file to Supabase storage
            file_path = await upload_file_to_storage(
                file_content,
                file_name
            )
            
            # Generate the public URL
            source_url = await get_file_url(file_path)
            logger.info(f"File uploaded to storage: {source_url}")
            
        except StorageError as e:
            logger.error(f"Error uploading file: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error uploading file: {str(e)}"
            )
    else:
        # Handle URL submissions
        if not source_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Source URL is required for non-file submissions"
            )
            
        logger.info(f"Received paper submission from user {user_id}: {source_url}")
        
        # Convert string source_type to enum if needed
        if isinstance(source_type, str):
            if source_type.lower() == "arxiv":
                source_type = SourceType.ARXIV
            elif source_type.lower() == "pdf":
                source_type = SourceType.PDF
            elif source_type.lower() == "file":
                source_type = SourceType.FILE
        
        # Detect URL type if not provided
        try:
            if not source_type or source_type not in [SourceType.ARXIV, SourceType.PDF]:
                source_type = await detect_url_type(source_url)
        except InvalidPDFUrlError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"URL does not point to a valid PDF: {source_url}"
            )
    
    # Check if paper already exists
    existing_paper = None
    
    if source_type == SourceType.ARXIV:
        # Extract arXiv ID from the URL
        arxiv_id = await extract_arxiv_id_from_url(source_url)
        if not arxiv_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid arXiv URL: {source_url}"
            )
        
        # Check if paper already exists by arXiv ID
        existing_paper = await get_paper_by_arxiv_id(arxiv_id)
    else:
        # Check if paper already exists by source URL and type
        existing_paper = await get_paper_by_source(source_url, source_type)
    
    if existing_paper:
        logger.info(f"Paper with source URL {source_url} already exists, adding to user's papers")
        await add_paper_to_user(user_id, existing_paper["id"])
        
        # Check if a conversation exists for this paper, create one if not
        try:
            # Create a conversation with explicit paper_id
            await create_conversation({
                "id": str(uuid.uuid4()),  # Generate a new unique ID for the conversation
                "user_id": user_id,
                "paper_id": existing_paper["id"]  # Explicitly set the paper_id
            })
            logger.info(f"Created conversation for existing paper with ID: {existing_paper['id']}")
        except Exception as e:
            # If the conversation creation fails, log the error but continue
            logger.warning(f"Could not create conversation for existing paper: {str(e)}")
        
        return existing_paper
    
    # Fetch paper metadata based on source type
    try:
        paper_metadata = await fetch_metadata_from_url(source_url, source_type)
    except Exception as e:
        logger.error(f"Error fetching metadata for URL {source_url}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching paper metadata: {str(e)}"
        )
    
    # Create initial paper entry in database
    paper_data = {
        "title": paper_metadata.title,
        "authors": [{"name": author.name, "affiliations": author.affiliations} for author in paper_metadata.authors],
        "abstract": paper_metadata.abstract,
        "publication_date": paper_metadata.publication_date.isoformat(),
        "summaries": None,
        "embedding_id": None,
        "related_papers": None,
        "source_type": source_type,
        "source_url": source_url,
        "tags": {"status": "pending"}  # Use tags field to track status instead of processing_status
    }
    
    # Add arXiv ID if available
    if hasattr(paper_metadata, 'arxiv_id') and paper_metadata.arxiv_id:
        paper_data["arxiv_id"] = paper_metadata.arxiv_id
    
    new_paper = await insert_paper(paper_data)
    
    # Associate paper with user
    await add_paper_to_user(user_id, new_paper["id"])
    
    # Create a conversation for this paper
    try:
        # Create a conversation with explicit paper_id
        await create_conversation({
            "id": str(uuid.uuid4()),  # Generate a new unique ID for the conversation
            "user_id": user_id,
            "paper_id": new_paper["id"]  # Explicitly set the paper_id
        })
        logger.info(f"Created conversation for new paper with ID: {new_paper['id']}")
    except Exception as e:
        logger.error(f"Error creating conversation for paper {new_paper['id']}: {str(e)}")
        # Continue even if conversation creation fails
    
    # Process paper in background
    background_tasks.add_task(
        process_paper_in_background,
        source_url=source_url,
        source_type=source_type,
        paper_id=UUID(new_paper["id"])
    )
    
    logger.info(f"Paper submission accepted, processing in background: {source_url}")
    return new_paper


@router.get("/{paper_id}", response_model=PaperResponse)
async def get_paper(
    paper_id: UUID,
    # args: Optional[str] = Query(None, description="Not required"),
    # kwargs: Optional[str] = Query(None, description="Not required")
):
    """
    Get details for a specific paper.
    
    Args:
        paper_id: The UUID of the paper
        # args: Optional arguments (system use only)
        # kwargs: Optional keyword arguments (system use only)
        
    Returns:
        The paper data
        
    Raises:
        HTTPException: If paper not found
    """
    paper = await get_paper_by_id(paper_id)
    
    if not paper:
        logger.warning(f"Paper with ID {paper_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper with ID {paper_id} not found"
        )
    
    logger.info(f"Retrieved paper with ID: {paper_id}")
    return paper


@router.get("/", response_model=List[PaperResponse])
async def list_papers(
    user_id: str = Depends(get_current_user),
    # args: Optional[str] = Query(None, description="Not required"),
    # kwargs: Optional[str] = Query(None, description="Not required")
):
    """
    List papers for the authenticated user.
    
    Args:
        user_id: The ID of the authenticated user
        # args: Optional arguments (system use only)
        # kwargs: Optional keyword arguments (system use only)
        
    Returns:
        List of papers associated with the user
    """
    papers = await db_list_papers(user_id)
    logger.info(f"Retrieved {len(papers)} papers for user {user_id}")
    return papers


@router.get("/{paper_id}/summaries", response_model=PaperSummary)
async def get_paper_summaries(
    paper_id: UUID,
    # args: Optional[str] = Query(None, description="Not required"),
    # kwargs: Optional[str] = Query(None, description="Not required")
):
    """
    Get tiered summaries for a paper.
    
    Args:
        paper_id: The UUID of the paper
        # args: Optional arguments (system use only)
        # kwargs: Optional keyword arguments (system use only)
        
    Returns:
        Beginner, intermediate, and advanced summaries
        
    Raises:
        HTTPException: If paper not found or summaries not available
    """
    paper = await get_paper_by_id(paper_id)
    
    if not paper:
        logger.warning(f"Paper with ID {paper_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper with ID {paper_id} not found"
        )
    
    if not paper.get("summaries"):
        logger.warning(f"Summaries not available for paper with ID {paper_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Summaries not available for this paper yet"
        )
    
    logger.info(f"Retrieved summaries for paper with ID: {paper_id}")
    return paper.get("summaries")


@router.get("/{paper_id}/related", response_model=List[Dict[str, Any]])
async def get_related_papers_for_paper(
    paper_id: UUID,
    user_id: str = Depends(get_current_user)
):
    """
    Get related papers for a specific paper.
    
    Args:
        paper_id: The ID of the paper to get related papers for
        user_id: The ID of the authenticated user
        
    Returns:
        List of related papers
    """
    # Get the paper
    paper = await get_paper_by_id(str(paper_id))
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper with ID {paper_id} not found"
        )
    
    # Check if related papers are already in the database
    if paper.get("related_papers"):
        logger.info(f"Using cached related papers for paper with ID {paper_id}")
        return paper.get("related_papers")
    
    # If not in database, fetch them based on source type
    if paper.get("source_type") == SourceType.ARXIV:
        # For arXiv papers, use the arXiv ID to fetch related papers
        arxiv_id = paper.get("arxiv_id")
        if not arxiv_id:
            # Try to extract arXiv ID from source_url
            source_url = paper.get("source_url")
            if source_url:
                arxiv_id = await extract_arxiv_id_from_url(source_url)
            
            if not arxiv_id:
                logger.warning(f"Paper with ID {paper_id} has no arXiv ID")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Paper has no arXiv ID and cannot fetch related papers"
                )
        
        # Fetch related papers
        related_papers = await get_related_papers(arxiv_id)
    else:
        # For non-arXiv papers, we currently don't support finding related papers
        logger.warning(f"Related papers not supported for source type {paper.get('source_type')}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Related papers not supported for source type {paper.get('source_type')}"
        )
    
    if not related_papers:
        logger.warning(f"No related papers found for paper with ID {paper_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No related papers found for this paper"
        )
    
    # Update the paper in the database with the related papers
    await update_paper(
        str(paper_id),
        {"related_papers": related_papers}
    )
    
    logger.info(f"Retrieved and stored related papers for paper with ID: {paper_id}")
    return related_papers


@router.get("/{paper_id}/conversations", response_model=List[Dict[str, Any]])
async def get_paper_conversations(
    paper_id: UUID,
    user_id: str = Depends(get_current_user)
):
    """
    Get all conversations for a specific paper and user.
    
    Args:
        paper_id: The UUID of the paper
        user_id: The ID of the authenticated user
        
    Returns:
        List of conversations for the paper and user
        
    Raises:
        HTTPException: If paper not found or other errors occur
    """
    # Verify the paper exists
    paper = await get_paper_by_id(paper_id)
    if not paper:
        logger.warning(f"Paper with ID {paper_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper with ID {paper_id} not found"
        )
    
    try:
        # Get conversations for the user and paper
        conversations = await get_user_paper_conversations(user_id, str(paper_id))
        logger.info(f"Retrieved {len(conversations)} conversations for user {user_id} and paper {paper_id}")
        
        return conversations
    except Exception as e:
        logger.error(f"Error retrieving conversations for paper {paper_id} and user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving conversations: {str(e)}"
        )


# Background processing function
async def process_paper_in_background(source_url: str, source_type: str, paper_id: UUID) -> None:
    """
    Process a paper in the background.
    
    This function:
    1. Downloads and processes the paper
    2. Stores the chunks in Pinecone
    3. Generates summaries
    4. Finds related papers
    5. Updates the paper in the database
    
    Args:
        source_url: The URL to the paper
        source_type: The type of source ("arxiv" or "pdf")
        paper_id: The UUID of the paper in the database
    """
    try:
        logger.info(f"Starting background processing for paper {paper_id} from {source_url}")
        
        # Update status to processing
        await update_paper(paper_id, {"tags": {"status": "processing"}})
        
        # Download and process paper
        full_text, chunks = await download_and_process_paper(source_url, paper_id, source_type)
        
        # Store chunks in Pinecone
        embedding_id = await store_chunks(chunks, str(paper_id))
        
        # Generate summaries
        summaries = await generate_summaries(full_text)
        
        # Find related papers
        related_papers = []
        if source_type == SourceType.ARXIV:
            try:
                arxiv_id = None
                if hasattr(paper_metadata, 'arxiv_id') and paper_metadata.arxiv_id:
                    arxiv_id = paper_metadata.arxiv_id
                else:
                    arxiv_id = await extract_arxiv_id_from_url(source_url)
                
                if arxiv_id:
                    related_papers = await get_related_papers(arxiv_id)
            except Exception as e:
                logger.error(f"Error getting related papers for {source_url}: {str(e)}")
        
        # Update paper with processed data
        update_data = {
            "full_text": full_text,
            "embedding_id": embedding_id,
            "summaries": {
                "beginner": summaries.beginner,
                "intermediate": summaries.intermediate,
                "advanced": summaries.advanced
            },
            "related_papers": related_papers,
            "tags": {"status": "completed"}
        }
        
        await update_paper(paper_id, update_data)
        
        logger.info(f"Background processing completed for paper {paper_id}")
        
        # Generate learning path in the background (don't wait for it)
        try:
            await generate_learning_path(paper_id)
        except Exception as e:
            logger.error(f"Error generating learning path for paper {paper_id}: {str(e)}")
        
    except Exception as e:
        logger.error(f"Error processing paper {paper_id} in background: {str(e)}")
        # Update status to error
        await update_paper(paper_id, {"tags": {"status": "error", "error_message": str(e)}}) 