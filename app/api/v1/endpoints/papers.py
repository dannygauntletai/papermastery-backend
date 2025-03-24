from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks, Query, Request, File, Form, UploadFile, Body
from typing import List, Optional, Dict, Any, Union
from uuid import UUID
import uuid
import json
import hashlib
from datetime import datetime
import logging

from app.api.v1.models import PaperSubmission, PaperResponse, PaperSummary, SourceType, PaperSubmitResponse, HighlightRequest, HighlightResponse
from app.core.logger import get_logger
from app.services.paper_service import (
    fetch_arxiv_metadata,
    get_related_papers,
    extract_metadata_from_text
)
from app.services.pdf_service import download_and_process_paper, download_pdf, read_pdf_file_to_bytes, extract_text_from_pdf_bytes
from app.services.url_service import detect_url_type, fetch_metadata_from_url
from app.utils.url_utils import extract_paper_id_from_url
from app.database.supabase_client import (
    get_paper_by_id,
    get_paper_by_source,
    insert_paper,
    update_paper,
    list_papers as db_list_papers,
    add_paper_to_user,
    create_conversation,
    get_user_paper_conversations,
    insert_message
)
from app.services.storage_service import upload_file_to_storage, get_file_url
from app.dependencies import validate_environment, get_current_user
from app.core.exceptions import InvalidPDFUrlError, PDFDownloadError, StorageError, LLMServiceError
from app.services.llm_service import generate_highlight_summary, generate_highlight_explanation

logger = get_logger(__name__)

router = APIRouter(
    prefix="/papers",
    tags=["papers"],
    dependencies=[Depends(validate_environment)],
    responses={404: {"description": "Paper not found"}},
)


@router.post("/submit", response_model=PaperSubmitResponse, status_code=status.HTTP_202_ACCEPTED)
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
        The paper ID as a UUID
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
            
        # Download the PDF from the URL
        original_url = source_url
        try:
            # Download the PDF
            pdf_path, is_new_download = await download_pdf(source_url)
            
            # Read the PDF file into bytes
            pdf_content = await read_pdf_file_to_bytes(pdf_path)
            
            # Extract filename from URL or use a default name
            from urllib.parse import urlparse
            parsed_url = urlparse(source_url)
            path_parts = parsed_url.path.split('/')
            file_name = path_parts[-1] if path_parts[-1] else f"paper_{hashlib.md5(source_url.encode()).hexdigest()[:8]}.pdf"
            
            # Make sure the filename ends with .pdf
            if not file_name.lower().endswith('.pdf'):
                file_name += '.pdf'
            
            # Upload the PDF to Supabase storage
            file_path = await upload_file_to_storage(pdf_content, file_name)
            
            # Generate the public URL
            source_url = await get_file_url(file_path)
            logger.info(f"PDF downloaded from {original_url} and uploaded to storage: {source_url}")
            
        except (PDFDownloadError, InvalidPDFUrlError) as e:
            logger.error(f"Error downloading PDF from URL: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error downloading PDF: {str(e)}"
            )
        except StorageError as e:
            logger.error(f"Error uploading PDF to storage: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error uploading PDF to storage: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error processing PDF: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error processing PDF: {str(e)}"
            )
    
    # Extract paper ID from URL if it's an arXiv URL
    paper_ids = await extract_paper_id_from_url(original_url if 'original_url' in locals() else source_url)
    arxiv_id = paper_ids.get('arxiv_id')
    
    if source_type == SourceType.ARXIV and not arxiv_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid arXiv URL: {original_url if 'original_url' in locals() else source_url}"
        )
    
    # Check if paper already exists
    # If we downloaded and reuploaded, use the original URL for checking
    check_url = original_url if 'original_url' in locals() else source_url
    existing_paper = await get_paper_by_source(check_url, source_type)

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
        
        return {"id": existing_paper["id"]}
    
    # Create initial paper entry in database with minimal information
    paper_data = {
        "title": "Processing...",
        "authors": [],
        "abstract": None,
        "publication_date": datetime.now().isoformat(),
        "summaries": None,
        "embedding_id": None,
        "related_papers": None,
        "source_type": source_type,
        "source_url": source_url,
        "tags": {"status": "processing", "processing_stage": "submitted"}
    }
    
    # Add arXiv ID if available
    if arxiv_id:
        paper_data["arxiv_id"] = arxiv_id
    
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
    
    # Start immediate processing based on submission type
    if file:
        # For file uploads, use the file content directly
        background_tasks.add_task(
            run_immediate_processing,
            file_content=file_content,
            paper_id=UUID(new_paper["id"]),
            source_url=source_url,
            source_type=source_type
        )
    else:
        # For URL submissions, download and process
        background_tasks.add_task(
            download_and_run_immediate_processing,
            source_url=source_url,
            source_type=source_type,
            paper_id=UUID(new_paper["id"])
        )
    
    logger.info(f"Paper submission accepted, processing in background: {source_url}")
    return {"id": new_paper["id"]}


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
                arxiv_id = await extract_paper_id_from_url(source_url)
            
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
    1. Downloads and extracts text from the paper
    2. Generates summaries for the paper
    3. Finds related papers
    4. Updates the paper in the database
    
    Args:
        source_url: The URL to the paper (Supabase storage URL for uploaded files)
        source_type: The type of source ("arxiv", "pdf", or "file")
        paper_id: The UUID of the paper in the database
    """
    try:
        logger.info(f"Starting background processing for paper {paper_id} from {source_url}")
        
        # Update status to processing
        await update_paper(paper_id, {"tags": {"status": "processing"}})
        
        # Get the paper from the database to access title and abstract
        paper = await get_paper_by_id(paper_id)
        if not paper:
            logger.error(f"Paper with ID {paper_id} not found in database")
            await update_paper(paper_id, {"tags": {"status": "error", "error_message": "Paper not found in database"}})
            return
        
        # Download and extract text from paper
        # Use the storage URL for downloading the PDF
        full_text = await download_and_process_paper(source_url, paper_id, source_type)
        
        # Generate summaries for the paper
        from app.services.summarization_service import generate_summaries
        try:
            logger.info(f"Generating summaries and extracting abstract for paper {paper_id}")
            summaries, extracted_abstract = await generate_summaries(
                paper_id=paper_id,
                title=paper.get("title", ""),
                abstract=paper.get("abstract"),  # Pass the existing abstract, which might be None
                full_text=full_text,
                extract_abstract=True  # Enable abstract extraction
            )
            logger.info(f"Successfully generated summaries and extracted abstract for paper {paper_id}")
        except Exception as summary_error:
            logger.error(f"Error generating summaries and extracting abstract for paper {paper_id}: {str(summary_error)}")
            summaries = None
            extracted_abstract = None
        
        # Find related papers
        related_papers = []
        try:
            # Get related papers using the paper ID, title, and abstract
            related_papers = await get_related_papers(
                paper_id=paper_id,
                title=paper.get("title"),
                abstract=extracted_abstract or paper.get("abstract")
            )
        except Exception as e:
            logger.error(f"Error getting related papers for {source_url}: {str(e)}")
        
        # Update paper with processed data
        update_data = {
            "full_text": full_text,
            "related_papers": related_papers,
            "tags": {"status": "completed"}
        }
        
        # Add extracted abstract to update data if available
        if extracted_abstract:
            update_data["abstract"] = extracted_abstract
        
        # Add summaries to update data if available
        if summaries:
            # Convert PaperSummary object to a dictionary for JSON serialization
            update_data["summaries"] = {
                "beginner": summaries.beginner,
                "intermediate": summaries.intermediate,
                "advanced": summaries.advanced
            }
        
        try:
            await update_paper(paper_id, update_data)
            logger.info(f"Background processing completed for paper {paper_id}")
        except Exception as db_error:
            logger.error(f"Database error updating paper {paper_id}: {str(db_error)}")
            
            # If there's an error with the full text, try to update without it
            if "full_text" in update_data:
                logger.warning(f"Attempting to update paper {paper_id} without full text")
                # Try to update with a truncated or sanitized version of the text
                try:
                    # Further sanitize the text by removing any potential problematic characters
                    import re
                    sanitized_text = re.sub(r'[^\x20-\x7E\n\r\t]', '', full_text)
                    # Truncate if still too large
                    if len(sanitized_text) > 1000000:  # Limit to 1MB
                        sanitized_text = sanitized_text[:1000000] + "... [truncated]"
                    
                    update_data["full_text"] = sanitized_text
                    await update_paper(paper_id, update_data)
                    logger.info(f"Successfully updated paper {paper_id} with sanitized text")
                except Exception as sanitize_error:
                    logger.error(f"Failed to update paper {paper_id} even with sanitized text: {str(sanitize_error)}")
                    # Last resort: update without the full text
                    del update_data["full_text"]
                    update_data["tags"]["status"] = "partial"
                    update_data["tags"]["error_message"] = "Could not store full text due to encoding issues"
                    await update_paper(paper_id, update_data)
                    logger.warning(f"Updated paper {paper_id} without full text")
        
    except Exception as e:
        logger.error(f"Error processing paper {paper_id} in background: {str(e)}")
        # Update status to error
        await update_paper(paper_id, {"tags": {"status": "error", "error_message": str(e)}})

async def run_immediate_processing(file_content: bytes, paper_id: UUID, source_url: str, source_type: str) -> None:
    """
    Run metadata extraction and summarization immediately after upload.
    
    Args:
        file_content: The binary content of the uploaded PDF file
        paper_id: The UUID of the paper
        source_url: The URL to the paper in storage
        source_type: The type of source ("arxiv", "pdf", "file")
    """
    try:
        logger.info(f"Starting immediate processing for paper {paper_id}")
        
        # Update status to processing
        await update_paper(paper_id, {"tags": {"status": "processing", "processing_stage": "extracting_text"}})
        
        # Extract text from PDF bytes
        full_text = await extract_text_from_pdf_bytes(file_content)
        
        if not full_text:
            logger.error(f"Failed to extract text from PDF for paper {paper_id}")
            await update_paper(paper_id, {"tags": {"status": "error", "error_message": "Failed to extract text from PDF"}})
            return
        
        # Extract metadata from text first
        await update_paper(paper_id, {"tags": {"status": "processing", "processing_stage": "extracting_metadata"}})
        try:
            metadata = await extract_metadata_from_text(full_text)
            
            # Update the source_url in the metadata
            metadata.source_url = source_url
            metadata.source_type = SourceType(source_type)
            
            # Update paper with metadata immediately
            await update_paper(paper_id, {
                "title": metadata.title,
                "authors": [{"name": author.name, "affiliations": author.affiliations} for author in metadata.authors],
                "abstract": metadata.abstract,
                "publication_date": metadata.publication_date.isoformat(),
                "source_url": source_url,
                "source_type": source_type,
                "tags": {"status": "processing", "processing_stage": "metadata_extracted"}
            })
            
            logger.info(f"Successfully extracted and updated metadata for paper {paper_id}")
        except Exception as metadata_error:
            logger.error(f"Error extracting metadata for paper {paper_id}: {str(metadata_error)}")
            # Continue with summarization even if metadata extraction fails
        
        # Generate summaries next
        await update_paper(paper_id, {"tags": {"status": "processing", "processing_stage": "summarizing"}})
        try:
            from app.services.summarization_service import generate_summaries
            
            # Get the updated paper to use its metadata for summarization
            paper = await get_paper_by_id(paper_id)
            
            if not paper:
                logger.error(f"Paper {paper_id} not found when trying to generate summaries")
                return
                
            summaries, _ = await generate_summaries(
                paper_id=paper_id,
                title=paper.get("title", "Processing..."),
                abstract=paper.get("abstract"),
                full_text=full_text,
                extract_abstract=False  # We'll extract abstract in a later step if needed
            )
            
            # Update the paper with summaries
            if summaries:
                await update_paper(paper_id, {
                    "summaries": {
                        "beginner": summaries.beginner,
                        "intermediate": summaries.intermediate,
                        "advanced": summaries.advanced
                    },
                    "tags": {"status": "processing", "processing_stage": "summarized"}
                })
                
                logger.info(f"Successfully generated and updated summaries for paper {paper_id}")
                
                # Generate learning path immediately after summarization is complete
                try:
                    from app.services.learning_service import generate_learning_path
                    
                    # Generate the learning path
                    learning_path = await generate_learning_path(str(paper_id))
                    
                    logger.info(f"Successfully generated learning path with {len(learning_path.items)} items for paper {paper_id}")
                    
                    # Update the paper with learning path status
                    await update_paper(paper_id, {
                        "tags": {
                            "status": "processing", 
                            "processing_stage": "learning_path_generated",
                            "has_learning_materials": True,
                            "learning_materials_count": len(learning_path.items)
                        }
                    })
                except Exception as learning_path_error:
                    logger.error(f"Error generating learning path for paper {paper_id}: {str(learning_path_error)}")
                    # Continue with further processing even if learning path generation fails
        except Exception as summary_error:
            logger.error(f"Error generating summaries for paper {paper_id}: {str(summary_error)}")
            # Continue with further processing even if summarization fails
        
        # Save the full_text to the database immediately after summarization
        logger.info(f"Saving full text for paper {paper_id}")
        try:
            await update_paper(paper_id, {
                "full_text": full_text,
                "tags": {"status": "processing", "processing_stage": "text_extracted"}
            })
            logger.info(f"Successfully saved full text for paper {paper_id}")
        except Exception as full_text_error:
            logger.error(f"Error saving full text for paper {paper_id}: {str(full_text_error)}")
            
            # Try to save with a truncated or sanitized version of the text
            try:
                # Further sanitize the text by removing any potential problematic characters
                import re
                sanitized_text = re.sub(r'[^\x20-\x7E\n\r\t]', '', full_text)
                # Truncate if still too large
                if len(sanitized_text) > 1000000:  # Limit to 1MB
                    sanitized_text = sanitized_text[:1000000] + "... [truncated]"
                
                await update_paper(paper_id, {
                    "full_text": sanitized_text,
                    "tags": {"status": "processing", "processing_stage": "text_extracted_partial"}
                })
                logger.info(f"Successfully saved sanitized full text for paper {paper_id}")
                # Update the local full_text with the sanitized version for further processing
                full_text = sanitized_text
            except Exception as sanitize_error:
                logger.error(f"Failed to save even sanitized full text for paper {paper_id}: {str(sanitize_error)}")
                # Continue with further processing even if full text saving fails
                await update_paper(paper_id, {
                    "tags": {"status": "processing", "processing_stage": "text_extraction_failed", 
                            "error_message": "Could not store full text due to encoding or size issues"}
                })
        
        # Start additional processing in background (abstract extraction, related papers, etc.)
        background_tasks = BackgroundTasks()
        background_tasks.add_task(
            process_additional_paper_data,
            file_content=file_content,
            paper_id=paper_id,
            full_text=full_text
        )
        
    except Exception as e:
        logger.error(f"Error in immediate processing for paper {paper_id}: {str(e)}")
        await update_paper(paper_id, {"tags": {"status": "error", "error_message": f"Processing error: {str(e)}"}})

async def download_and_run_immediate_processing(source_url: str, source_type: str, paper_id: UUID) -> None:
    """
    Download a PDF from a URL and run immediate processing.
    
    Args:
        source_url: The URL to download the PDF from
        source_type: The type of source ("arxiv" or "pdf")
        paper_id: The UUID of the paper
    """
    try:
        logger.info(f"Downloading PDF for immediate processing for paper {paper_id} from {source_url}")
        
        # Update status to downloading
        await update_paper(paper_id, {"tags": {"status": "processing", "processing_stage": "downloading"}})
        
        # Download the PDF based on source type
        pdf_path, is_new = await download_pdf(source_url)
        
        if not pdf_path:
            logger.error(f"Failed to download PDF from {source_url} for paper {paper_id}")
            await update_paper(paper_id, {"tags": {"status": "error", "error_message": "Failed to download PDF"}})
            return
        
        # Read the PDF file into bytes
        pdf_content = await read_pdf_file_to_bytes(pdf_path)
        
        # Run immediate processing with the downloaded content
        await run_immediate_processing(
            file_content=pdf_content, 
            paper_id=paper_id,
            source_url=source_url,
            source_type=source_type
        )
        
    except Exception as e:
        logger.error(f"Error downloading PDF for immediate processing for paper {paper_id}: {str(e)}")
        await update_paper(paper_id, {"tags": {"status": "error", "error_message": f"PDF download error: {str(e)}"}})

async def process_additional_paper_data(file_content: bytes, paper_id: UUID, full_text: str) -> None:
    """
    Process additional paper data after immediate processing is complete.
    
    Args:
        file_content: The binary content of the PDF file
        paper_id: The UUID of the paper
        full_text: The already extracted text from the PDF
    """
    try:
        logger.info(f"Starting additional processing for paper {paper_id}")
        
        # Get the current paper data
        paper = await get_paper_by_id(paper_id)
        if not paper:
            logger.error(f"Paper with ID {paper_id} not found in database")
            return
        
        # Extract abstract if needed
        if not paper.get("abstract"):
            await update_paper(paper_id, {"tags": {"status": "processing", "processing_stage": "extracting_abstract"}})
            try:
                from app.services.summarization_service import generate_summaries
                _, extracted_abstract = await generate_summaries(
                    paper_id=paper_id,
                    title=paper.get("title", ""),
                    abstract=paper.get("abstract"),
                    full_text=full_text,
                    extract_abstract=True
                )
                
                if extracted_abstract:
                    await update_paper(paper_id, {
                        "abstract": extracted_abstract,
                        "tags": {"status": "processing", "processing_stage": "abstract_extracted"}
                    })
                    paper["abstract"] = extracted_abstract  # Update local copy for next steps
            except Exception as abstract_error:
                logger.error(f"Error extracting abstract for paper {paper_id}: {str(abstract_error)}")
                # Continue processing even if abstract extraction fails
        
        # Find related papers
        await update_paper(paper_id, {"tags": {"status": "processing", "processing_stage": "finding_related_papers"}})
        try:
            related_papers = await get_related_papers(
                paper_id=paper_id,
                title=paper.get("title"),
                abstract=paper.get("abstract")
            )
            
            if related_papers:
                await update_paper(paper_id, {
                    "related_papers": related_papers,
                    "tags": {"status": "processing", "processing_stage": "related_papers_found"}
                })
        except Exception as related_error:
            logger.error(f"Error finding related papers for paper {paper_id}: {str(related_error)}")
            # Continue processing even if related papers fails
            
        # Mark paper processing as complete
        await update_paper(paper_id, {
            "tags": {"status": "completed", "processing_stage": "paper_complete"}
        })
        
        # Start learning items processing
        from app.api.v1.endpoints.learning import process_learning_items
        background_tasks = BackgroundTasks()
        background_tasks.add_task(
            process_learning_items,
            paper_id=paper_id,
            full_text=full_text,
            title=paper.get("title"),
            abstract=paper.get("abstract")
        )
        
    except Exception as e:
        logger.error(f"Error processing additional data for paper {paper_id}: {str(e)}")
        await update_paper(paper_id, {"tags": {"status": "error", "error_message": f"Additional processing error: {str(e)}"}})

@router.post("/{paper_id}/summarize-highlight", response_model=HighlightResponse)
async def summarize_highlighted_text(
    paper_id: UUID,
    highlight_request: HighlightRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """
    Summarize a highlighted text section from a paper.
    
    This endpoint takes a section of highlighted text and returns a concise summary,
    focusing on the key points and maintaining the original meaning.
    
    Args:
        paper_id: UUID of the paper the highlight is from
        highlight_request: Contains the highlighted text and optional surrounding context
        current_user: Optional current user information
        
    Returns:
        A response containing the generated summary
        
    Raises:
        HTTPException: If paper not found or LLM service error occurs
    """
    user_id = current_user.get("id", "anonymous") if current_user else "anonymous"
    logger.info(f"[HIGHLIGHT-SUMMARY] Request received for paper={paper_id}, user={user_id}")
    logger.debug(f"[HIGHLIGHT-SUMMARY] Highlighted text length: {len(highlight_request.text)} chars, context provided: {highlight_request.context is not None}")
    
    try:
        # Check if paper exists (for validation and to get title)
        logger.debug(f"[HIGHLIGHT-SUMMARY] Retrieving paper {paper_id} from database")
        paper = await get_paper_by_id(paper_id)
        if not paper:
            logger.warning(f"[HIGHLIGHT-SUMMARY] Paper {paper_id} not found while attempting to summarize highlight for user {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paper not found"
            )
        
        paper_title = paper.get("title", "Unknown title")
        logger.info(f"[HIGHLIGHT-SUMMARY] Found paper: '{paper_title}' (ID: {paper_id})")
        
        # Generate summary using LLM service
        logger.info(f"[HIGHLIGHT-SUMMARY] Calling LLM service to generate summary for paper '{paper_title}'")
        result = await generate_highlight_summary(
            highlighted_text=highlight_request.text,
            context=highlight_request.context,
            paper_title=paper_title
        )
        
        response_length = len(result.get("response", "")) if result else 0
        logger.info(f"[HIGHLIGHT-SUMMARY] Successfully generated summary ({response_length} chars) for paper {paper_id}")
        logger.debug(f"[HIGHLIGHT-SUMMARY] Summary response preview: {result.get('response', '')[:100]}...")
        
        # Store the highlight summary in the database
        try:
            # Get paper conversations to find the right conversation ID
            conversations = await get_user_paper_conversations(user_id, str(paper_id))
            
            # Use the first conversation or create a new one if none exists
            conversation_id = None
            if conversations and len(conversations) > 0:
                conversation_id = conversations[0].get("id")
                logger.debug(f"[HIGHLIGHT-SUMMARY] Using existing conversation {conversation_id} for paper {paper_id}")
            else:
                # Create a new conversation
                new_conversation = await create_conversation({
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "paper_id": str(paper_id)
                })
                conversation_id = new_conversation.get("id")
                logger.debug(f"[HIGHLIGHT-SUMMARY] Created new conversation {conversation_id} for paper {paper_id}")
            
            # Prepare message data
            message_data = {
                "id": str(uuid.uuid4()),
                "conversation_id": conversation_id,
                "user_id": user_id,
                "paper_id": str(paper_id),
                "text": result.get("response", ""),
                "sender": "bot",
                # Additional fields for highlight operations
                "highlighted_text": highlight_request.text,
                "highlight_type": "summary",
                "created_at": datetime.now().isoformat()
            }
            
            # Insert message into database
            await insert_message(message_data)
            logger.info(f"[HIGHLIGHT-SUMMARY] Stored summary in database for paper {paper_id}")
        
        except Exception as db_error:
            # Log the error but don't fail the request
            logger.error(f"[HIGHLIGHT-SUMMARY] Error storing summary in database: {str(db_error)}")
        
        return result
        
    except LLMServiceError as e:
        error_message = str(e)
        logger.error(f"[HIGHLIGHT-SUMMARY] LLM service error for paper={paper_id}, user={user_id}: {error_message}")
        # Log additional details that might help with debugging
        if hasattr(e, "response"):
            logger.error(f"[HIGHLIGHT-SUMMARY] LLM service response details: {e.response}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating summary: {error_message}"
        )
    except Exception as e:
        error_message = str(e)
        logger.error(f"[HIGHLIGHT-SUMMARY] Unexpected error for paper={paper_id}, user={user_id}: {error_message}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while generating the summary"
        )


@router.post("/{paper_id}/explain-highlight", response_model=HighlightResponse)
async def explain_highlighted_text(
    paper_id: UUID,
    highlight_request: HighlightRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """
    Generate an explanation for a highlighted text section from a paper.
    
    This endpoint takes a section of highlighted text and returns a detailed explanation,
    breaking down complex concepts and clarifying technical terminology.
    
    Args:
        paper_id: UUID of the paper the highlight is from
        highlight_request: Contains the highlighted text and optional surrounding context
        current_user: Optional current user information
        
    Returns:
        A response containing the generated explanation
        
    Raises:
        HTTPException: If paper not found or LLM service error occurs
    """
    user_id = current_user.get("id", "anonymous") if current_user else "anonymous"
    logger.info(f"[HIGHLIGHT-EXPLAIN] Request received for paper={paper_id}, user={user_id}")
    logger.debug(f"[HIGHLIGHT-EXPLAIN] Highlighted text length: {len(highlight_request.text)} chars, context provided: {highlight_request.context is not None}")
    
    try:
        # Check if paper exists (for validation and to get title)
        logger.debug(f"[HIGHLIGHT-EXPLAIN] Retrieving paper {paper_id} from database")
        paper = await get_paper_by_id(paper_id)
        if not paper:
            logger.warning(f"[HIGHLIGHT-EXPLAIN] Paper {paper_id} not found while attempting to explain highlight for user {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paper not found"
            )
        
        paper_title = paper.get("title", "Unknown title")
        logger.info(f"[HIGHLIGHT-EXPLAIN] Found paper: '{paper_title}' (ID: {paper_id})")
        
        # Generate explanation using LLM service
        logger.info(f"[HIGHLIGHT-EXPLAIN] Calling LLM service to generate explanation for paper '{paper_title}'")
        result = await generate_highlight_explanation(
            highlighted_text=highlight_request.text,
            context=highlight_request.context,
            paper_title=paper_title
        )
        
        response_length = len(result.get("response", "")) if result else 0
        logger.info(f"[HIGHLIGHT-EXPLAIN] Successfully generated explanation ({response_length} chars) for paper {paper_id}")
        logger.debug(f"[HIGHLIGHT-EXPLAIN] Explanation response preview: {result.get('response', '')[:100]}...")
        
        # Store the highlight explanation in the database
        try:
            # Get paper conversations to find the right conversation ID
            conversations = await get_user_paper_conversations(user_id, str(paper_id))
            
            # Use the first conversation or create a new one if none exists
            conversation_id = None
            if conversations and len(conversations) > 0:
                conversation_id = conversations[0].get("id")
                logger.debug(f"[HIGHLIGHT-EXPLAIN] Using existing conversation {conversation_id} for paper {paper_id}")
            else:
                # Create a new conversation
                new_conversation = await create_conversation({
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "paper_id": str(paper_id)
                })
                conversation_id = new_conversation.get("id")
                logger.debug(f"[HIGHLIGHT-EXPLAIN] Created new conversation {conversation_id} for paper {paper_id}")
            
            # Prepare message data
            message_data = {
                "id": str(uuid.uuid4()),
                "conversation_id": conversation_id,
                "user_id": user_id,
                "paper_id": str(paper_id),
                "text": result.get("response", ""),
                "sender": "bot",
                # Additional fields for highlight operations
                "highlighted_text": highlight_request.text,
                "highlight_type": "explanation",
                "created_at": datetime.now().isoformat()
            }
            
            # Insert message into database
            await insert_message(message_data)
            logger.info(f"[HIGHLIGHT-EXPLAIN] Stored explanation in database for paper {paper_id}")
        
        except Exception as db_error:
            # Log the error but don't fail the request
            logger.error(f"[HIGHLIGHT-EXPLAIN] Error storing explanation in database: {str(db_error)}")
        
        return result
        
    except LLMServiceError as e:
        error_message = str(e)
        logger.error(f"[HIGHLIGHT-EXPLAIN] LLM service error for paper={paper_id}, user={user_id}: {error_message}")
        # Log additional details that might help with debugging
        if hasattr(e, "response"):
            logger.error(f"[HIGHLIGHT-EXPLAIN] LLM service response details: {e.response}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating explanation: {error_message}"
        )
    except Exception as e:
        error_message = str(e)
        logger.error(f"[HIGHLIGHT-EXPLAIN] Unexpected error for paper={paper_id}, user={user_id}: {error_message}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while generating the explanation"
        )

@router.post("/debug/set-log-level")
async def set_debug_log_level(
    level: str = Query(..., description="Logging level to set (DEBUG, INFO, WARNING, ERROR, CRITICAL)"),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """
    Set the logging level for debugging purposes.
    
    This endpoint allows dynamically changing the log level to assist with debugging.
    Only accessible to authenticated users.
    
    Args:
        level: The logging level to set (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        current_user: Current authenticated user
        
    Returns:
        Confirmation message with the new log level
    """
    # Only allow authenticated users
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    # Map string level to logging module level
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    
    if level.upper() not in level_map:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid log level. Must be one of: {', '.join(level_map.keys())}"
        )
    
    # Get main logger
    from app.core.logger import get_logger
    main_logger = get_logger("arxiv_mastery")
    
    # Set the new log level
    numeric_level = level_map[level.upper()]
    main_logger.setLevel(numeric_level)
    
    # Also set the level for highlight-specific loggers
    highlight_loggers = [
        get_logger("arxiv_mastery.app.api.v1.endpoints.papers"),
        get_logger("arxiv_mastery.app.services.llm_service")
    ]
    
    for logger in highlight_loggers:
        logger.setLevel(numeric_level)
    
    logger.info(f"Log level changed to {level.upper()} by user {current_user.get('id', 'unknown')}")
    
    return {
        "status": "success",
        "message": f"Log level set to {level.upper()}",
        "affected_loggers": ["arxiv_mastery", "arxiv_mastery.app.api.v1.endpoints.papers", "arxiv_mastery.app.services.llm_service"]
    }

@router.post("/{paper_id}/summarize", response_model=HighlightResponse)
async def summarize_highlighted_text_alias(
    paper_id: UUID,
    highlight_request: HighlightRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """
    Alias endpoint for summarize-highlight to maintain compatibility with frontend.
    
    This endpoint has the same functionality as /{paper_id}/summarize-highlight but
    uses the URL format expected by the frontend.
    """
    # Ensure current_user is properly formatted as a dictionary if it's a string
    current_user_dict = {"id": current_user} if isinstance(current_user, str) else current_user
    # Call the original implementation
    return await summarize_highlighted_text(paper_id, highlight_request, current_user_dict)


@router.post("/{paper_id}/explain", response_model=HighlightResponse)
async def explain_highlighted_text_alias(
    paper_id: UUID,
    highlight_request: HighlightRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """
    Alias endpoint for explain-highlight to maintain compatibility with frontend.
    
    This endpoint has the same functionality as /{paper_id}/explain-highlight but
    uses the URL format expected by the frontend.
    """
    # Ensure current_user is properly formatted as a dictionary if it's a string
    current_user_dict = {"id": current_user} if isinstance(current_user, str) else current_user
    # Call the original implementation
    return await explain_highlighted_text(paper_id, highlight_request, current_user_dict) 