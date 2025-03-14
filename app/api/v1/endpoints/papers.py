from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks, Query, Request
from typing import List, Optional, Dict, Any
from uuid import UUID
import uuid

from app.api.v1.models import PaperSubmission, PaperResponse, PaperSummary
from app.core.logger import get_logger
from app.services.arxiv_service import (
    fetch_paper_metadata,
    download_and_process_paper,
    get_related_papers
)
from app.database.supabase_client import (
    get_paper_by_arxiv_id,
    get_paper_by_id,
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

logger = get_logger(__name__)

router = APIRouter(
    prefix="/papers",
    tags=["papers"],
    dependencies=[Depends(validate_environment)],
    responses={404: {"description": "Paper not found"}},
)


@router.post("/submit", response_model=PaperResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_paper(
    paper_submission: PaperSubmission,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user),
    # args: Optional[str] = Query(None, description="Not required"),
    # kwargs: Optional[str] = Query(None, description="Not required")
):
    """
    Submit an arXiv paper for processing.
    
    The submission is accepted immediately, and processing happens in the background.
    Check the status of the paper by retrieving it with GET /papers/{id}.
    
    Args:
        paper_submission: The submission request containing the arXiv link
        background_tasks: FastAPI background tasks
        user_id: The ID of the authenticated user
        # args: Optional arguments (system use only)
        # kwargs: Optional keyword arguments (system use only)
        
    Returns:
        The paper data with processing status
    """
    logger.info(f"Received paper submission from user {user_id}: {paper_submission.arxiv_link}")
    
    # Extract arXiv ID from the URL
    url_str = str(paper_submission.arxiv_link)
    arxiv_id = url_str.split("/")[-1]
    if "pdf" in arxiv_id:
        arxiv_id = arxiv_id.replace(".pdf", "")
    
    # Check if paper already exists
    existing_paper = await get_paper_by_arxiv_id(arxiv_id)
    if existing_paper:
        logger.info(f"Paper with arXiv ID {arxiv_id} already exists, adding to user's papers")
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
    
    # Fetch paper metadata from arXiv
    paper_metadata = await fetch_paper_metadata(arxiv_id)
    
    # Create initial paper entry in database
    paper_data = {
        "arxiv_id": arxiv_id,
        "title": paper_metadata.title,
        "authors": [{"name": author.name, "affiliations": author.affiliations} for author in paper_metadata.authors],
        "abstract": paper_metadata.abstract,
        "publication_date": paper_metadata.publication_date.isoformat(),
        "summaries": None,
        "embedding_id": None,
        "related_papers": None,
        "tags": {"status": "pending"}  # Use tags field to track status instead of processing_status
    }
    
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
        arxiv_id=arxiv_id,
        paper_id=UUID(new_paper["id"])
    )
    
    logger.info(f"Paper submission accepted, processing in background: {arxiv_id}")
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
    # args: Optional[str] = Query(None, description="Not required"),
    # kwargs: Optional[str] = Query(None, description="Not required")
):
    """
    Get papers related to the specified paper.
    
    Args:
        paper_id: The UUID of the paper
        # args: Optional arguments (system use only)
        # kwargs: Optional keyword arguments (system use only)
        
    Returns:
        List of related papers with similarity scores
        
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
    
    # Check if related papers are already stored in the database
    if paper.get("related_papers"):
        logger.info(f"Retrieved related papers for paper with ID: {paper_id} from database")
        return paper.get("related_papers")
    
    # If not in database, fetch them from OpenAlex API
    arxiv_id = paper.get("arxiv_id")
    if not arxiv_id:
        logger.warning(f"Paper with ID {paper_id} has no arXiv ID")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper has no arXiv ID"
        )
    
    # Fetch related papers
    related_papers = await get_related_papers(arxiv_id)
    
    if not related_papers:
        logger.warning(f"No related papers found for paper with ID {paper_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No related papers found for this paper"
        )
    
    # Update the paper in the database with the related papers
    await update_paper(
        paper_id,
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
async def process_paper_in_background(arxiv_id: str, paper_id: UUID):
    """
    Process a paper in the background.
    
    This function:
    1. Downloads the PDF from arXiv
    2. Extracts text from the PDF
    3. Breaks it into logical chunks
    4. Generates embeddings and stores them in Pinecone
    5. Finds related papers
    6. Generates summaries
    7. Generates learning materials (videos, flashcards, quizzes)
    8. Updates the paper in the database
    
    Args:
        arxiv_id: The arXiv ID of the paper
        paper_id: The UUID of the paper in our database
    """
    embedding_id = None
    related_papers = None
    error_message = None
    
    try:
        logger.info(f"Processing paper in background: {arxiv_id}")
        
        # Update status to processing
        await update_paper(paper_id, {"tags": {"status": "processing"}})
        
        # Download and process PDF - pass the paper_id for LangChain processing
        full_text, text_chunks = await download_and_process_paper(arxiv_id, paper_id)
        
        # Chunk the text - now processes with LangChain if available
        chunks = await chunk_text(full_text, paper_id, text_chunks)
        
        # Try to store chunks in Pinecone, but continue if it fails
        try:
            embedding_id = await store_chunks(paper_id, chunks)
            logger.info(f"Successfully stored chunks in Pinecone for paper ID: {paper_id}")
        except Exception as pinecone_error:
            logger.error(f"Error storing chunks in Pinecone for paper ID {paper_id}: {str(pinecone_error)}")
            error_message = f"Pinecone error: {str(pinecone_error)[:200]}"
            # Continue processing despite Pinecone error
        
        # Try to get related papers, but continue if it fails
        try:
            related_papers = await get_related_papers(arxiv_id)
            logger.info(f"Successfully fetched related papers for paper ID: {paper_id}")
        except Exception as related_papers_error:
            logger.error(f"Error fetching related papers for paper ID {paper_id}: {str(related_papers_error)}")
            error_message = error_message or f"Related papers error: {str(related_papers_error)[:200]}"
            # Continue processing despite related papers error
        
        # Generate summaries
        paper = await get_paper_by_id(paper_id)
        summaries = await generate_summaries(
            paper_id=paper_id,
            abstract=paper.get("abstract", ""),
            full_text=full_text,
            chunks=chunks
        )
        
        # Generate learning materials (videos, flashcards, quizzes)
        try:
            learning_path = await generate_learning_path(str(paper_id))
            logger.info(f"Successfully generated learning materials for paper ID: {paper_id}")
            has_learning_materials = True
            learning_materials_count = len(learning_path.items) if learning_path and learning_path.items else 0
        except Exception as learning_error:
            logger.error(f"Error generating learning materials for paper ID {paper_id}: {str(learning_error)}")
            error_message = error_message or f"Learning materials error: {str(learning_error)[:200]}"
            has_learning_materials = False
            learning_materials_count = 0
            # Continue processing despite learning materials generation error
        
        # Update the paper in the database
        update_data = {
            "full_text": full_text[:1000],  # Store first 1000 chars as preview
            "summaries": {
                "beginner": summaries.beginner,
                "intermediate": summaries.intermediate,
                "advanced": summaries.advanced
            },
            "chunk_count": len(chunks),
            "tags": {
                "status": "completed",
                "has_learning_materials": has_learning_materials,
                "learning_materials_count": learning_materials_count
            }
        }
        
        # Add embedding_id and related_papers if they were successfully retrieved
        if embedding_id:
            update_data["embedding_id"] = embedding_id
        if related_papers:
            update_data["related_papers"] = related_papers
        if error_message:
            update_data["partial_error"] = error_message
            
        await update_paper(paper_id, update_data)
        
        logger.info(f"Background processing completed for paper: {arxiv_id}")
        
    except Exception as e:
        logger.error(f"Error processing paper {arxiv_id} in background: {str(e)}")
        
        # Update paper status to error
        try:
            await update_paper(
                paper_id,
                {
                    "tags": {"status": "error"},
                    "error_message": str(e)[:500]  # Limit error message length
                }
            )
        except Exception as update_error:
            logger.error(f"Error updating paper status: {str(update_error)}") 