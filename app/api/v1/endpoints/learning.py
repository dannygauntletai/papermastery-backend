from fastapi import APIRouter, HTTPException, Depends, status, Path, Body, Query
from typing import Dict, List, Optional, Any
from uuid import UUID
import logging
from app.dependencies import validate_environment
from app.services import learning_service
from app.database.supabase_client import supabase
from pydantic import BaseModel

from app.api.v1.models import (
    LearningPath, 
    LearningItem, 
    UserProgressRecord, 
    AnswerResult,
    QuizAnswer
)
from app.services.learning_service import (
    generate_learning_path, 
    get_learning_path,
    get_learning_items_by_level,
    record_progress,
    get_user_progress,
    submit_answer
)
from app.api.dependencies import get_current_user

router = APIRouter(
    prefix="/learning",
    tags=["learning"],
    dependencies=[Depends(validate_environment)]
)

logger = logging.getLogger(__name__)

class ProgressUpdate(BaseModel):
    """Model for updating user progress on an item."""
    status: str
    sprt_log_likelihood_ratio: Optional[float] = 0.0
    decision: Optional[str] = "in_progress"

class AnswerSubmission(BaseModel):
    """Model for submitting an answer to a question."""
    answer: str

@router.get("/papers/{paper_id}/learning-path", response_model=LearningPath)
async def get_paper_learning_path(
    paper_id: str = Path(..., description="The ID of the paper"),
    user_id: Optional[str] = Depends(get_current_user)
):
    """
    Get or generate a learning path for a paper.
    """
    try:
        return await generate_learning_path(paper_id, user_id)
    except Exception as e:
        logger.error(f"Error getting learning path: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting learning path: {str(e)}")

@router.get("/papers/{paper_id}/materials", response_model=List[LearningItem])
async def get_learning_materials(
    paper_id: str = Path(..., description="The ID of the paper"),
    difficulty_level: Optional[int] = Query(None, ge=1, le=3, description="Filter by difficulty level")
):
    """
    Get learning materials for a paper, optionally filtered by difficulty level.
    """
    try:
        if difficulty_level is not None:
            return await get_learning_items_by_level(paper_id, difficulty_level)
        else:
            # Get the learning path and return all items
            learning_path = await generate_learning_path(paper_id)
            return learning_path.items
    except Exception as e:
        logger.error(f"Error getting learning materials: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting learning materials: {str(e)}")

@router.get("/learning-items/{item_id}", response_model=LearningItem)
async def get_learning_item(
    item_id: str = Path(..., description="The ID of the learning item")
):
    """
    Get a specific learning item by ID.
    """
    try:
        # In a full implementation, this would query the database
        # For now, we'll search through the cached learning paths
        from app.services.learning_service import learning_path_cache
        
        for learning_path in learning_path_cache.values():
            for item in learning_path.items:
                if item.id == item_id:
                    return item
        
        raise HTTPException(status_code=404, detail=f"Learning item {item_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting learning item: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting learning item: {str(e)}")

@router.post("/learning-items/{item_id}/progress", status_code=204)
async def record_item_progress(
    progress: UserProgressRecord,
    item_id: str = Path(..., description="The ID of the learning item"),
    user_id: str = Depends(get_current_user)
):
    """
    Record a user's progress on a learning item.
    """
    try:
        # Ensure the user ID matches
        if progress.user_id != user_id:
            raise HTTPException(status_code=400, detail="User ID mismatch")
        
        # Ensure the item ID matches
        if progress.item_id != item_id:
            raise HTTPException(status_code=400, detail="Item ID mismatch")
        
        await record_progress(
            item_id=item_id,
            user_id=user_id,
            status=progress.status,
            time_spent_seconds=progress.time_spent_seconds
        )
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recording progress: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error recording progress: {str(e)}")

@router.post("/questions/{question_id}/answer", response_model=AnswerResult)
async def submit_question_answer(
    question_id: str = Path(..., description="The ID of the quiz question"),
    answer: QuizAnswer = None,
    user_id: str = Depends(get_current_user)
):
    """
    Submit an answer to a quiz question and get feedback.
    """
    try:
        result = await submit_answer(
            question_id=question_id,
            user_id=user_id,
            answer_index=answer.selected_answer
        )
        return result
    except Exception as e:
        logger.error(f"Error submitting answer: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error submitting answer: {str(e)}")

@router.get("/user/progress", response_model=List[UserProgressRecord])
async def get_progress(
    user_id: str = Depends(get_current_user),
    paper_id: Optional[str] = Query(None, description="Filter by paper ID")
):
    """
    Get a user's progress on learning materials.
    """
    try:
        return await get_user_progress(user_id, paper_id)
    except Exception as e:
        logger.error(f"Error getting user progress: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting user progress: {str(e)}")

@router.post("/papers/{paper_id}/generate-learning-path", response_model=LearningPath)
async def generate_new_learning_path(
    paper_id: str = Path(..., description="The ID of the paper"),
    user_id: Optional[str] = Depends(get_current_user)
):
    """
    Force generation of a new learning path for a paper.
    """
    try:
        # Clear the cache for this paper to force regeneration
        from app.services.learning_service import learning_path_cache
        if paper_id in learning_path_cache:
            del learning_path_cache[paper_id]
        
        return await generate_learning_path(paper_id, user_id)
    except Exception as e:
        logger.error(f"Error generating new learning path: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating new learning path: {str(e)}") 