from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from typing import List, Optional, Dict, Any
from uuid import UUID

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
    list_papers as db_list_papers
)
from app.services.chunk_service import chunk_text
from app.services.pinecone_service import store_chunks
from app.services.summarization_service import generate_summaries
from app.dependencies import validate_environment

logger = get_logger(__name__)

router = APIRouter(
    prefix="/papers",
    tags=["papers"],
    dependencies=[Depends(validate_environment)]
)


@router.post("/submit", response_model=PaperResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_paper(
    paper_submission: PaperSubmission,
    background_tasks: BackgroundTasks
):
    """
    Submit an arXiv paper for processing.
    
    The submission is accepted immediately, and processing happens in the background.
    Check the status of the paper by retrieving it with GET /papers/{id}.
    
    Args:
        paper_submission: The submission request containing the arXiv link
        background_tasks: FastAPI background tasks
        
    Returns:
        The paper data with processing status
    """
    logger.info(f"Received paper submission: {paper_submission.arxiv_link}")
    
    # Extract arXiv ID from the URL
    url_str = str(paper_submission.arxiv_link)
    arxiv_id = url_str.split("/")[-1]
    if "pdf" in arxiv_id:
        arxiv_id = arxiv_id.replace(".pdf", "")
    
    # Check if paper already exists
    existing_paper = await get_paper_by_arxiv_id(arxiv_id)
    if existing_paper:
        logger.info(f"Paper with arXiv ID {arxiv_id} already exists, returning existing paper")
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
        "processing_status": "pending"
    }
    
    new_paper = await insert_paper(paper_data)
    
    # Process paper in background
    background_tasks.add_task(
        process_paper_in_background,
        arxiv_id=arxiv_id,
        paper_id=UUID(new_paper["id"])
    )
    
    logger.info(f"Paper submission accepted, processing in background: {arxiv_id}")
    return new_paper


@router.get("/{paper_id}", response_model=PaperResponse)
async def get_paper(paper_id: UUID):
    """
    Get details for a specific paper.
    
    Args:
        paper_id: The UUID of the paper
        
    Returns:
        The paper data
        
    Raises:
        HTTPException: If the paper is not found
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
async def list_papers():
    """
    List all submitted papers.
    
    Returns:
        A list of papers
    """
    papers = await db_list_papers()
    logger.info(f"Retrieved {len(papers)} papers")
    return papers


@router.get("/{paper_id}/summaries", response_model=PaperSummary)
async def get_paper_summaries(paper_id: UUID):
    """
    Get tiered summaries for a specific paper.
    
    Args:
        paper_id: The UUID of the paper
        
    Returns:
        The paper summaries at beginner, intermediate, and advanced levels
        
    Raises:
        HTTPException: If the paper is not found or summaries are not available
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
async def get_related_papers_for_paper(paper_id: UUID):
    """
    Get related papers for a specific paper.
    
    Args:
        paper_id: The UUID of the paper
        
    Returns:
        A list of related papers with metadata
        
    Raises:
        HTTPException: If the paper is not found or related papers are not available
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
    7. Updates the paper in the database
    
    Args:
        arxiv_id: The arXiv ID of the paper
        paper_id: The UUID of the paper in our database
    """
    try:
        logger.info(f"Processing paper in background: {arxiv_id}")
        
        # Update status to processing
        await update_paper(paper_id, {"processing_status": "processing"})
        
        # Download and process PDF
        full_text, text_chunks = await download_and_process_paper(arxiv_id)
        
        # Chunk the text
        chunks = await chunk_text(full_text, paper_id)
        
        # Store chunks in Pinecone
        embedding_id = await store_chunks(paper_id, chunks)
        
        # Get related papers
        related_papers = await get_related_papers(arxiv_id)
        
        # Generate summaries
        paper = await get_paper_by_id(paper_id)
        summaries = await generate_summaries(
            paper_id=paper_id,
            abstract=paper.get("abstract", ""),
            full_text=full_text,
            chunks=chunks
        )
        
        # Update the paper in the database
        await update_paper(
            paper_id,
            {
                "full_text": full_text[:1000],  # Store first 1000 chars as preview
                "summaries": {
                    "beginner": summaries.beginner,
                    "intermediate": summaries.intermediate,
                    "advanced": summaries.advanced
                },
                "embedding_id": embedding_id,
                "related_papers": related_papers,
                "processing_status": "completed",
                "chunk_count": len(chunks)
            }
        )
        
        logger.info(f"Background processing completed for paper: {arxiv_id}")
        
    except Exception as e:
        logger.error(f"Error processing paper {arxiv_id} in background: {str(e)}")
        
        # Update paper status to error
        try:
            await update_paper(
                paper_id,
                {
                    "processing_status": "error",
                    "error_message": str(e)[:500]  # Limit error message length
                }
            )
        except Exception as update_error:
            logger.error(f"Error updating paper status: {str(update_error)}") 