import pytest
from fastapi.testclient import TestClient
import uuid
from unittest.mock import patch, MagicMock

from app.main import app
from app.api.dependencies import get_current_user
from app.services.learning_service import (
    generate_learning_path,
    record_progress,
    submit_answer,
    _get_mock_youtube_videos,
    _get_mock_flashcards,
    _get_mock_quiz_questions
)

# Mock user ID for testing
TEST_USER_ID = "test-user-123"
TEST_JWT_TOKEN = "mock.jwt.token"

# Override the authentication dependency for testing
async def mock_get_current_user():
    return TEST_USER_ID

app.dependency_overrides[get_current_user] = mock_get_current_user

# Create test client
client = TestClient(app)

# Test fixture to set up a test paper in database
@pytest.fixture
def test_paper_id():
    # In a real test, we would create a test paper in the database
    # and return its ID. For now, we'll just use a random UUID.
    paper_id = str(uuid.uuid4())
    yield paper_id
    # Cleanup would go here in a real test

# Test getting a learning path
def test_get_learning_path(test_paper_id):
    # Mock the YouTube, flashcards, and quiz generation to use mock data
    with patch('app.services.learning_service.fetch_youtube_videos', return_value=_get_mock_youtube_videos()), \
         patch('app.services.learning_service.generate_flashcards', return_value=_get_mock_flashcards()), \
         patch('app.services.learning_service.generate_quiz_questions', return_value=_get_mock_quiz_questions()):
        
        response = client.get(f"/api/v1/learning/papers/{test_paper_id}/learning-path")
        assert response.status_code == 200
        
        data = response.json()
        assert data["paper_id"] == test_paper_id
        assert "items" in data
        assert len(data["items"]) > 0
        assert "estimated_time_minutes" in data

# Test getting learning materials
def test_get_materials(test_paper_id):
    # First generate a learning path
    with patch('app.services.learning_service.fetch_youtube_videos', return_value=_get_mock_youtube_videos()), \
         patch('app.services.learning_service.generate_flashcards', return_value=_get_mock_flashcards()), \
         patch('app.services.learning_service.generate_quiz_questions', return_value=_get_mock_quiz_questions()):
        
        # Call the endpoint to ensure a learning path exists
        client.get(f"/api/v1/learning/papers/{test_paper_id}/learning-path")
        
        # Now test getting all materials
        response = client.get(f"/api/v1/learning/papers/{test_paper_id}/materials")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        
        # Check that we have different types of learning items
        item_types = set(item["type"] for item in data)
        assert len(item_types) >= 3  # Should have at least text, video, and quiz

# Test getting materials by difficulty level
def test_get_materials_by_level(test_paper_id):
    # First generate a learning path
    with patch('app.services.learning_service.fetch_youtube_videos', return_value=_get_mock_youtube_videos()), \
         patch('app.services.learning_service.generate_flashcards', return_value=_get_mock_flashcards()), \
         patch('app.services.learning_service.generate_quiz_questions', return_value=_get_mock_quiz_questions()):
        
        # Call the endpoint to ensure a learning path exists
        client.get(f"/api/v1/learning/papers/{test_paper_id}/learning-path")
        
        # Test getting materials filtered by difficulty level
        response = client.get(f"/api/v1/learning/papers/{test_paper_id}/materials?difficulty_level=1")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert all(item["difficulty_level"] == 1 for item in data)

# Test getting a specific learning item
def test_get_learning_item(test_paper_id):
    # First generate a learning path
    with patch('app.services.learning_service.fetch_youtube_videos', return_value=_get_mock_youtube_videos()), \
         patch('app.services.learning_service.generate_flashcards', return_value=_get_mock_flashcards()), \
         patch('app.services.learning_service.generate_quiz_questions', return_value=_get_mock_quiz_questions()):
        
        # Call the endpoint to ensure a learning path exists
        response = client.get(f"/api/v1/learning/papers/{test_paper_id}/learning-path")
        data = response.json()
        
        # Get the ID of the first learning item
        item_id = data["items"][0]["id"]
        
        # Now test getting that specific item
        response = client.get(f"/api/v1/learning/learning-items/{item_id}")
        assert response.status_code == 200
        
        item_data = response.json()
        assert item_data["id"] == item_id

# Test recording progress
def test_record_progress(test_paper_id):
    # First generate a learning path
    with patch('app.services.learning_service.fetch_youtube_videos', return_value=_get_mock_youtube_videos()), \
         patch('app.services.learning_service.generate_flashcards', return_value=_get_mock_flashcards()), \
         patch('app.services.learning_service.generate_quiz_questions', return_value=_get_mock_quiz_questions()):
        
        # Call the endpoint to ensure a learning path exists
        response = client.get(f"/api/v1/learning/papers/{test_paper_id}/learning-path")
        data = response.json()
        
        # Get the ID of the first learning item
        item_id = data["items"][0]["id"]
        
        # Record progress on this item
        progress_data = {
            "id": str(uuid.uuid4()),
            "user_id": TEST_USER_ID,
            "item_id": item_id,
            "status": "completed",
            "time_spent_seconds": 300,
            "timestamp": "2023-05-01T12:00:00Z"
        }
        
        response = client.post(
            f"/api/v1/learning/learning-items/{item_id}/progress",
            json=progress_data,
            headers={"Authorization": TEST_JWT_TOKEN}
        )
        assert response.status_code == 204

# Test submitting an answer
def test_submit_answer(test_paper_id):
    # First generate a learning path
    with patch('app.services.learning_service.fetch_youtube_videos', return_value=_get_mock_youtube_videos()), \
         patch('app.services.learning_service.generate_flashcards', return_value=_get_mock_flashcards()), \
         patch('app.services.learning_service.generate_quiz_questions', return_value=_get_mock_quiz_questions()):
        
        # Call the endpoint to ensure a learning path exists
        response = client.get(f"/api/v1/learning/papers/{test_paper_id}/learning-path")
        data = response.json()
        
        # Find a quiz question
        quiz_items = [item for item in data["items"] if item["type"] == "quiz"]
        assert len(quiz_items) > 0
        
        question_id = quiz_items[0]["id"]
        correct_answer = quiz_items[0]["metadata"]["correct_answer"]
        
        # Submit a correct answer
        answer_data = {
            "selected_answer": correct_answer
        }
        
        response = client.post(
            f"/api/v1/learning/questions/{question_id}/answer",
            json=answer_data,
            headers={"Authorization": TEST_JWT_TOKEN}
        )
        assert response.status_code == 200
        
        result = response.json()
        assert result["is_correct"] is True
        assert result["correct_answer"] == correct_answer
        
        # Submit an incorrect answer
        incorrect_answer = (correct_answer + 1) % 4  # Ensure it's different
        answer_data = {
            "selected_answer": incorrect_answer
        }
        
        response = client.post(
            f"/api/v1/learning/questions/{question_id}/answer",
            json=answer_data,
            headers={"Authorization": TEST_JWT_TOKEN}
        )
        assert response.status_code == 200
        
        result = response.json()
        assert result["is_correct"] is False
        assert result["correct_answer"] == correct_answer

# Test getting user progress
def test_get_user_progress(test_paper_id):
    # First generate a learning path and record some progress
    with patch('app.services.learning_service.fetch_youtube_videos', return_value=_get_mock_youtube_videos()), \
         patch('app.services.learning_service.generate_flashcards', return_value=_get_mock_flashcards()), \
         patch('app.services.learning_service.generate_quiz_questions', return_value=_get_mock_quiz_questions()):
        
        # Call the endpoint to ensure a learning path exists
        response = client.get(f"/api/v1/learning/papers/{test_paper_id}/learning-path")
        data = response.json()
        
        # Get the ID of the first learning item
        item_id = data["items"][0]["id"]
        
        # Record progress on this item
        progress_data = {
            "id": str(uuid.uuid4()),
            "user_id": TEST_USER_ID,
            "item_id": item_id,
            "status": "completed",
            "time_spent_seconds": 300,
            "timestamp": "2023-05-01T12:00:00Z"
        }
        
        client.post(
            f"/api/v1/learning/learning-items/{item_id}/progress",
            json=progress_data,
            headers={"Authorization": TEST_JWT_TOKEN}
        )
        
        # Now get the user's progress
        response = client.get(
            f"/api/v1/learning/user/progress",
            headers={"Authorization": TEST_JWT_TOKEN}
        )
        assert response.status_code == 200
        
        progress_data = response.json()
        assert isinstance(progress_data, list)
        assert len(progress_data) >= 1
        
        # Check that our recorded progress is in the list
        matching_progress = [p for p in progress_data if p["item_id"] == item_id]
        assert len(matching_progress) >= 1
        assert matching_progress[0]["status"] == "completed" 