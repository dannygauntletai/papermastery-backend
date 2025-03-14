import asyncio
import httpx
import os
import pytest
from typing import Dict, List, Any, Optional

@pytest.mark.asyncio
async def test_learning_materials_endpoint():
    """Test the learning materials endpoint and verify the response structure."""
    # Get paper ID from environment or use default
    paper_id = os.getenv('TEST_PAPER_ID', 'dbb7860b-ecbc-468f-998c-c52989f126b8')
    base_url = os.getenv('API_BASE_URL', 'http://localhost:8000')
    
    # Make a request to the API
    async with httpx.AsyncClient() as client:
        url = f"{base_url}/api/v1/learning/papers/{paper_id}/materials"
        response = await client.get(url)
        
        # Verify successful response
        assert response.status_code == 200
        
        data: List[Dict[str, Any]] = response.json()
        assert len(data) > 0
        
        # Verify items have required structure
        for item in data:
            assert 'id' in item
            assert 'type' in item
            assert 'title' in item
            assert 'content' in item
            assert 'metadata' in item
            assert 'difficulty_level' in item
        
        # Test for presence of different item types
        item_types = count_items_by_type(data)
        
        # Verify flashcards if present
        flashcards = [item for item in data if item.get("type") == "flashcard"]
        if flashcards:
            verify_flashcards(flashcards)
        
        # Verify quizzes if present
        quizzes = [item for item in data if item.get("type") == "quiz"]
        if quizzes:
            verify_quizzes(quizzes)
            
        # Verify videos if present
        videos = [item for item in data if item.get("type") == "video"]
        if videos:
            verify_videos(videos)

def count_items_by_type(items: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count items by type."""
    item_types: Dict[str, int] = {}
    for item in items:
        item_type = item.get("type")
        if item_type:
            item_types[item_type] = item_types.get(item_type, 0) + 1
    return item_types

def verify_flashcards(flashcards: List[Dict[str, Any]]) -> None:
    """Verify flashcards have the correct structure."""
    for card in flashcards:
        assert card.get('content')  # Front content
        metadata = card.get('metadata', {})
        assert 'back' in metadata
        assert metadata['back']  # Back content
        
def verify_quizzes(quizzes: List[Dict[str, Any]]) -> None:
    """Verify quizzes have the correct structure."""
    for quiz in quizzes:
        metadata = quiz.get('metadata', {})
        assert 'questions' in metadata
        
        questions = metadata.get('questions', [])
        if questions:
            for question in questions:
                assert 'question' in question
                assert 'options' in question
                assert 'correct_answer' in question
                
                # Verify options and correct answer
                options = question.get('options', [])
                assert len(options) > 0
                
                correct_answer = question.get('correct_answer')
                assert isinstance(correct_answer, int)
                assert 0 <= correct_answer < len(options)

def verify_videos(videos: List[Dict[str, Any]]) -> None:
    """Verify video items have the correct structure."""
    for video in videos:
        metadata = video.get('metadata', {})
        assert 'videos' in metadata
        
        video_list = metadata.get('videos', [])
        assert len(video_list) > 0
        
        # Check the structure of the first video
        first_video = video_list[0]
        assert 'video_id' in first_video
        assert 'title' in first_video
        assert 'thumbnail' in first_video
        assert 'channel' in first_video

if __name__ == "__main__":
    asyncio.run(pytest.main(["-xvs", __file__])) 