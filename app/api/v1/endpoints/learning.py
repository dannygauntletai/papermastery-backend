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
    QuizAnswer,
    QuestionItem,
    CardItem,
    LearningItemType
)
from app.services.learning_service import (
    generate_learning_path, 
    get_learning_path,
    get_learning_items_by_level,
    record_progress,
    get_user_progress,
    submit_answer,
    generate_flashcards,
    generate_quiz_questions
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
    time_spent_seconds: int
    sprt_log_likelihood_ratio: Optional[float] = 0.0
    decision: Optional[str] = "in_progress"

class AnswerSubmission(BaseModel):
    """Model for submitting an answer to a question."""
    answer: str

@router.get("/papers/{paper_id}/learning-path", response_model=LearningPath)
async def get_paper_learning_path(
    paper_id: str = Path(..., description="The ID of the paper"),
    user_id: Optional[str] = Depends(get_current_user),
    use_mock_for_tests: bool = Query(False, description="Use mock data for tests")
):
    """
    Get or generate a learning path for a paper.
    """
    try:
        return await generate_learning_path(paper_id, user_id, use_mock_for_tests=use_mock_for_tests)
    except Exception as e:
        logger.error(f"Error getting learning path: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting learning path: {str(e)}")

@router.get("/papers/{paper_id}/materials", response_model=List[LearningItem])
async def get_learning_materials(
    paper_id: str = Path(..., description="The ID of the paper"),
    difficulty_level: Optional[int] = Query(None, ge=1, le=3, description="Filter by difficulty level"),
    use_mock_for_tests: bool = Query(False, description="Use mock data for tests")
):
    """
    Get learning materials for a paper, optionally filtered by difficulty level.
    """
    logger.info(f"Getting learning materials for paper {paper_id}, difficulty_level={difficulty_level}")
    try:
        if difficulty_level is not None:
            logger.info(f"Filtering materials by difficulty level {difficulty_level}")
            return await get_learning_items_by_level(paper_id, difficulty_level, use_mock_for_tests=use_mock_for_tests)
        else:
            # Get the learning path and return all items
            logger.info(f"Getting all learning materials via learning path for paper {paper_id}")
            learning_path = await generate_learning_path(paper_id, use_mock_for_tests=use_mock_for_tests)
            logger.info(f"Retrieved learning path with {len(learning_path.items)} items")
            
            # Log the types of items
            item_types = {}
            for item in learning_path.items:
                item_type = item.type.value
                if item_type not in item_types:
                    item_types[item_type] = 0
                item_types[item_type] += 1
                
                # Log details of video items
                if item.type == LearningItemType.VIDEO:
                    logger.info(f"Video item found: id={item.id}, title={item.title}")
                    logger.info(f"Video metadata: {item.metadata}")
                    if "videos" in item.metadata:
                        logger.info(f"Number of videos in metadata: {len(item.metadata['videos'])}")
                        if item.metadata['videos']:
                            logger.info(f"First video: {item.metadata['videos'][0]}")
            
            logger.info(f"Returning items by type: {item_types}")
            
            # Check for expected types that are missing
            for expected_type in ["text", "video", "quiz", "flashcard"]:
                if expected_type not in item_types:
                    logger.warning(f"No {expected_type} items found in learning path")
            
            # Ensure video items are properly formatted
            formatted_items = []
            for item in learning_path.items:
                if item.type == LearningItemType.VIDEO:
                    # Ensure video items have the correct structure
                    if "videos" in item.metadata and item.metadata["videos"]:
                        # Keep the item as is
                        logger.info(f"Video item {item.id} has {len(item.metadata['videos'])} videos")
                        formatted_items.append(item)
                    else:
                        logger.warning(f"Video item {item.id} has no videos, skipping")
                else:
                    # Keep non-video items as is
                    formatted_items.append(item)
            
            # Log details about flashcards
            flashcard_items = [item for item in formatted_items if item.type == LearningItemType.FLASHCARD]
            if flashcard_items:
                logger.info(f"Returning {len(flashcard_items)} flashcard items")
                logger.info("FLASHCARD CONTENT BEING SENT TO FRONTEND:")
                for i, card in enumerate(flashcard_items[:5]):  # Log first 5 cards
                    logger.info(f"Flashcard {i+1}:")
                    logger.info(f"  Front: {card.content}")
                    logger.info(f"  Back: {card.metadata.get('back', '')}")
                    logger.info("---")
            
            # Log details about quiz questions
            quiz_items = [item for item in formatted_items if item.type == LearningItemType.QUIZ]
            if quiz_items:
                logger.info(f"Returning {len(quiz_items)} quiz items")
                logger.info("QUIZ CONTENT BEING SENT TO FRONTEND:")
                for i, quiz in enumerate(quiz_items[:3]):  # Log first 3 quizzes
                    logger.info(f"Quiz {i+1}: {quiz.title}")
                    if "questions" in quiz.metadata:
                        for j, question in enumerate(quiz.metadata.get("questions", [])[:3]):  # Log up to 3 questions per quiz
                            logger.info(f"  Question {j+1}: {question.get('question', '')}")
                            logger.info(f"  Options: {question.get('options', [])}")
                            logger.info(f"  Correct answer: {question.get('correct_answer', '')}")
                            logger.info(f"  Explanation: {question.get('explanation', '')}")
                            logger.info("  ---")
            
            # Print detailed structure of what we're returning
            logger.info("Detailed structure of returned learning items:")
            for i, item in enumerate(formatted_items[:5]):  # Log first 5 items
                logger.info(f"Item {i}: type={item.type}, title={item.title[:50]}")
                if item.type == LearningItemType.FLASHCARD:
                    logger.info(f"  Flashcard content: {item.content[:50]}")
                    logger.info(f"  Flashcard metadata: {item.metadata}")
                elif item.type == LearningItemType.QUIZ:
                    logger.info(f"  Quiz metadata: {item.metadata.keys()}")
            
            return formatted_items
    except Exception as e:
        logger.error(f"Error getting learning materials: {str(e)}", exc_info=True)
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
    progress: ProgressUpdate,
    item_id: str = Path(..., description="The ID of the learning item"),
    user_id: str = Depends(get_current_user)
):
    """
    Record a user's progress on a learning item.
    """
    try:
        # No need to check user_id and item_id match since we're using ProgressUpdate
        await record_progress(
            item_id=item_id,
            user_id=user_id,
            status=progress.status,
            time_spent_seconds=progress.time_spent_seconds
        )
        
        return None
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

@router.get("/papers/{paper_id}/flashcards", response_model=List[CardItem])
async def get_flashcards(
    paper_id: str = Path(..., description="The ID of the paper"),
    use_mock_for_tests: bool = Query(False, description="Use mock data for tests")
):
    """
    Get flashcards for a paper.
    """
    try:
        return await generate_flashcards(paper_id)
    except Exception as e:
        logger.error(f"Error getting flashcards: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting flashcards: {str(e)}")

@router.get("/papers/{paper_id}/quiz-questions", response_model=List[QuestionItem])
async def get_quiz_questions(
    paper_id: str = Path(..., description="The ID of the paper"),
    use_mock_for_tests: bool = Query(False, description="Use mock data for tests")
):
    """
    Get quiz questions for a paper.
    """
    try:
        return await generate_quiz_questions(paper_id)
    except Exception as e:
        logger.error(f"Error getting quiz questions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting quiz questions: {str(e)}") 