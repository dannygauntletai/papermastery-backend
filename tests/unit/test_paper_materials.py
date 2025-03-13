import asyncio
import pytest
import os
from typing import Optional, Dict, Any, List
from app.database.supabase_client import get_paper_by_id
from app.services.learning_service import generate_flashcards, generate_quiz_questions
from app.api.v1.models import CardItem, QuestionItem

@pytest.mark.asyncio
async def test_paper_exists():
    """Test that the test paper exists in the database."""
    paper_id = os.getenv('TEST_PAPER_ID', '0a066c79-1d2e-4d01-8963-f80f16023687')
    
    # Check if paper exists
    paper: Optional[Dict[str, Any]] = await get_paper_by_id(paper_id)
    assert paper is not None
    assert 'title' in paper
    assert 'abstract' in paper

@pytest.mark.asyncio
async def test_flashcard_generation():
    """Test flashcard generation for the paper."""
    paper_id = os.getenv('TEST_PAPER_ID', '0a066c79-1d2e-4d01-8963-f80f16023687')
    
    # Generate flashcards
    flashcards: List[CardItem] = await generate_flashcards(paper_id)
    
    # Basic validations
    assert flashcards is not None
    assert len(flashcards) > 0
    
    # Check first flashcard
    assert flashcards[0].front
    assert flashcards[0].back

@pytest.mark.asyncio
async def test_quiz_generation():
    """Test quiz generation for the paper."""
    paper_id = os.getenv('TEST_PAPER_ID', '0a066c79-1d2e-4d01-8963-f80f16023687')
    
    # Generate quiz questions
    quiz_questions: List[QuestionItem] = await generate_quiz_questions(paper_id)
    
    # Basic validations
    assert quiz_questions is not None
    assert len(quiz_questions) > 0
    
    # Check first question
    first_question = quiz_questions[0]
    assert first_question.question
    assert len(first_question.options) > 0
    assert isinstance(first_question.correct_answer, int)
    assert 0 <= first_question.correct_answer < len(first_question.options)

if __name__ == "__main__":
    asyncio.run(pytest.main(["-xvs", __file__])) 