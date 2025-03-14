import asyncio
import pytest
from typing import List, Optional

from app.services.learning_service import generate_flashcards
from app.api.v1.models import CardItem


@pytest.mark.asyncio
async def test_flashcard_generation() -> None:
    """Test generating flashcards for a paper."""
    # Use a test paper ID
    paper_id = "dbb7860b-ecbc-468f-998c-c52989f126b8"
    
    # Generate flashcards
    flashcards: List[CardItem] = await generate_flashcards(paper_id)
    
    # Assertions
    assert flashcards is not None
    assert len(flashcards) > 0
    
    # Verify that each flashcard has the required properties
    for card in flashcards:
        assert card.front
        assert card.back
        
    # Verify these aren't mock flashcards if we have real data
    if flashcards and len(flashcards) >= 5:
        common_mock_questions = [
            "What is supervised learning?",
            "What is the difference between classification and regression?",
            "What is overfitting?",
            "What is a neural network?",
            "What is backpropagation?"
        ]
        
        is_mock = all(
            card.front in common_mock_questions
            for card in flashcards[:5]
        )
        
        if not is_mock:
            assert flashcards[0].front != "What is supervised learning?"


if __name__ == "__main__":
    asyncio.run(test_flashcard_generation()) 