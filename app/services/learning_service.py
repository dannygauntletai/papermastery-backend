from typing import Dict, List, Optional, Any, Union
import logging
import uuid
import random
from datetime import datetime
import asyncio
import httpx
import json
import os
from app.database.supabase_client import supabase, get_paper_by_id
from app.core.config import get_settings
from app.services.arxiv_service import get_related_papers
from app.services.summarization_service import generate_summaries
from app.api.v1.models import (
    LearningItem, 
    LearningItemType, 
    LearningPath, 
    QuizQuestion,
    UserProgressRecord,
    QuizAnswer,
    AnswerResult
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Learning material types
MATERIAL_TYPES = {
    "text": "Explanatory text content",
    "quiz": "Interactive questions to test understanding",
    "flashcard": "Spaced repetition memory cards",
    "video": "Educational video content"
}

# Difficulty levels
LEVELS = ["beginner", "intermediate", "advanced"]

# Categories mapping (simplified version - can be expanded based on arXiv categories)
CATEGORY_MAPPING = {
    "cs.AI": "artificial-intelligence",
    "cs.CL": "natural-language-processing",
    "cs.CV": "computer-vision",
    "cs.LG": "machine-learning",
    "stat.ML": "machine-learning",
    "math": "mathematics",
    "physics": "physics",
    "q-bio": "biology",
    "q-fin": "finance"
}

# Cache to avoid regenerating content for the same paper
learning_path_cache: Dict[str, LearningPath] = {}

async def fetch_youtube_videos(paper_id: str) -> List[Dict[str, Any]]:
    """
    Fetch educational YouTube videos related to the paper topic.
    
    Args:
        paper_id: The ID of the paper
        
    Returns:
        List[Dict[str, Any]]: A list of YouTube video metadata
    """
    try:
        if not settings.YOUTUBE_API_KEY:
            logger.warning("YouTube API key not configured, using mock data")
            return _get_mock_youtube_videos()
        
        # In a real implementation, we would first get the paper title and keywords
        # to use as search terms. For now, we'll use a fixed search term.
        search_term = "machine learning paper explanation"
        
        # Construct YouTube API request
        api_url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "q": search_term,
            "type": "video",
            "maxResults": 5,
            "key": settings.YOUTUBE_API_KEY,
            "videoEmbeddable": "true",
            "relevanceLanguage": "en",
            "safeSearch": "strict"
        }
        
        # Make the API request
        async with httpx.AsyncClient() as client:
            response = await client.get(api_url, params=params)
            response.raise_for_status()
            data = response.json()
        
        # Extract video IDs to get more details
        video_ids = [item["id"]["videoId"] for item in data.get("items", [])]
        
        if not video_ids:
            logger.warning("No YouTube videos found, using mock data")
            return _get_mock_youtube_videos()
        
        # Get video details
        video_url = "https://www.googleapis.com/youtube/v3/videos"
        video_params = {
            "part": "snippet,contentDetails",
            "id": ",".join(video_ids),
            "key": settings.YOUTUBE_API_KEY
        }
        
        async with httpx.AsyncClient() as client:
            video_response = await client.get(video_url, params=video_params)
            video_response.raise_for_status()
            video_data = video_response.json()
        
        # Process video data
        videos = []
        for item in video_data.get("items", []):
            snippet = item.get("snippet", {})
            content_details = item.get("contentDetails", {})
            
            videos.append({
                "video_id": item.get("id"),
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                "channel": snippet.get("channelTitle", ""),
                "duration": content_details.get("duration", "PT0M0S")  # ISO 8601 duration format
            })
        
        return videos
    
    except Exception as e:
        logger.error(f"Error fetching YouTube videos: {str(e)}")
        return _get_mock_youtube_videos()

def _convert_iso_duration(duration_iso: str) -> str:
    """Convert ISO 8601 duration to minutes:seconds format."""
    import re
    
    # Extract minutes and seconds from ISO 8601 duration
    minutes_match = re.search(r'(\d+)M', duration_iso)
    seconds_match = re.search(r'(\d+)S', duration_iso)
    hours_match = re.search(r'(\d+)H', duration_iso)
    
    minutes = int(minutes_match.group(1)) if minutes_match else 0
    seconds = int(seconds_match.group(1)) if seconds_match else 0
    hours = int(hours_match.group(1)) if hours_match else 0
    
    # Add hours to minutes if present
    if hours > 0:
        minutes += hours * 60
        
    return f"{minutes}:{seconds:02d}"

def _mock_youtube_videos(query: str, max_results: int = 3) -> List[Dict[str, str]]:
    """Generate mock YouTube videos when API is unavailable."""
    return [
        {
            "title": f"Understanding {query} - Beginner Tutorial",
            "url": "https://www.youtube.com/watch?v=example1",
            "thumbnail": "https://img.youtube.com/vi/example1/default.jpg",
            "duration": "10:15",
            "channel": "Educational Channel"
        },
        {
            "title": f"Advanced {query} Concepts Explained",
            "url": "https://www.youtube.com/watch?v=example2",
            "thumbnail": "https://img.youtube.com/vi/example2/default.jpg",
            "duration": "15:42",
            "channel": "Science Explained"
        },
        {
            "title": f"{query} in Practice: Case Studies",
            "url": "https://www.youtube.com/watch?v=example3",
            "thumbnail": "https://img.youtube.com/vi/example3/default.jpg",
            "duration": "8:30",
            "channel": "Research Channel"
        }
    ][:max_results]

async def generate_flashcards(paper_id: str) -> List[Dict[str, str]]:
    """
    Generate flashcards for the paper using OpenAI API.
    
    Args:
        paper_id: The ID of the paper
        
    Returns:
        List[Dict[str, str]]: A list of flashcards with front and back
    """
    try:
        if not settings.OPENAI_API_KEY:
            logger.warning("OpenAI API key not configured, using mock flashcards")
            return _get_mock_flashcards()
        
        # In a real implementation, we would first get the paper content
        # to use as context. For now, we'll create generic ML flashcards.
        
        prompt = """
        Generate 5 educational flashcards about machine learning concepts.
        Each flashcard should have a front side with a question or concept,
        and a back side with the answer or explanation.
        
        Format your response as a JSON array of objects with 'front' and 'back' fields.
        Example:
        [
            {
                "front": "What is gradient descent?",
                "back": "An optimization algorithm used to minimize a function by iteratively moving in the direction of steepest descent."
            }
        ]
        """
        
        # Make OpenAI API request
        api_url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}"
        }
        payload = {
            "model": settings.OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": "You are an educational assistant that creates high-quality flashcards."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(api_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        
        # Extract the flashcards from the response
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # Parse the JSON response
        try:
            # Extract JSON from the response if it's wrapped in markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            flashcards = json.loads(content)
            if isinstance(flashcards, list) and len(flashcards) > 0:
                return flashcards
            else:
                logger.warning("Invalid flashcards format from OpenAI, using mock data")
                return _get_mock_flashcards()
        except json.JSONDecodeError:
            logger.error("Failed to parse flashcards JSON from OpenAI")
            return _get_mock_flashcards()
    
    except Exception as e:
        logger.error(f"Error generating flashcards: {str(e)}")
        return _get_mock_flashcards()

def _get_mock_youtube_videos() -> List[Dict[str, Any]]:
    """Return mock YouTube video data"""
    return [
        {
            "video_id": "PL8dPuuaLjXtO65LeD2p4_Sb5XQ51par_b",
            "title": "Introduction to Machine Learning",
            "description": "A comprehensive introduction to the basic concepts of machine learning",
            "thumbnail": "https://i.ytimg.com/vi/example1/hqdefault.jpg",
            "channel": "Educational Channel 1",
            "duration": "PT15M30S"
        },
        {
            "video_id": "PL8dPuuaLjXtO65LeD2p4_Sb5XQ51par_c",
            "title": "Neural Networks Explained",
            "description": "How neural networks work and their applications in machine learning",
            "thumbnail": "https://i.ytimg.com/vi/example2/hqdefault.jpg",
            "channel": "Educational Channel 2",
            "duration": "PT12M45S"
        },
        {
            "video_id": "PL8dPuuaLjXtO65LeD2p4_Sb5XQ51par_d",
            "title": "Deep Learning Fundamentals",
            "description": "Understanding the basics of deep learning architectures",
            "thumbnail": "https://i.ytimg.com/vi/example3/hqdefault.jpg",
            "channel": "Educational Channel 3",
            "duration": "PT18M20S"
        }
    ]

def _get_mock_flashcards() -> List[Dict[str, str]]:
    """Return mock flashcard data"""
    return [
        {
            "front": "What is supervised learning?",
            "back": "A type of machine learning where the model is trained on labeled data, learning to map inputs to known outputs."
        },
        {
            "front": "What is the difference between classification and regression?",
            "back": "Classification predicts discrete class labels, while regression predicts continuous values."
        },
        {
            "front": "What is overfitting?",
            "back": "When a model learns the training data too well, including its noise and outliers, leading to poor performance on new, unseen data."
        },
        {
            "front": "What is a neural network?",
            "back": "A computational model inspired by the human brain, consisting of connected nodes (neurons) organized in layers that process information."
        },
        {
            "front": "What is backpropagation?",
            "back": "An algorithm used to train neural networks by calculating gradients and adjusting weights to minimize the difference between actual and predicted outputs."
        }
    ]

async def generate_quiz_questions(paper_id: str) -> List[Dict[str, Any]]:
    """
    Generate quiz questions for the paper using OpenAI API.
    
    Args:
        paper_id: The ID of the paper
        
    Returns:
        List[Dict[str, Any]]: A list of quiz questions with options and answers
    """
    try:
        if not settings.OPENAI_API_KEY:
            logger.warning("OpenAI API key not configured, using mock quiz questions")
            return _get_mock_quiz_questions()
        
        # In a real implementation, we would first get the paper content
        # to use as context. For now, we'll create generic ML quiz questions.
        
        prompt = """
        Generate 5 multiple-choice quiz questions about machine learning concepts.
        Each question should have 4 options with one correct answer.
        
        Format your response as a JSON array of objects with these fields:
        - question: The question text
        - options: Array of 4 possible answers
        - correct_answer: Index (0-3) of the correct option
        - explanation: Explanation of why the answer is correct
        
        Example:
        [
            {
                "question": "What is the purpose of regularization in machine learning?",
                "options": [
                    "To increase model complexity",
                    "To prevent overfitting",
                    "To speed up training time",
                    "To increase training accuracy"
                ],
                "correct_answer": 1,
                "explanation": "Regularization techniques add a penalty term to the loss function to discourage complex models, which helps prevent overfitting."
            }
        ]
        """
        
        # Make OpenAI API request
        api_url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}"
        }
        payload = {
            "model": settings.OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": "You are an educational assistant that creates high-quality quiz questions."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(api_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        
        # Extract the quiz questions from the response
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # Parse the JSON response
        try:
            # Extract JSON from the response if it's wrapped in markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            questions = json.loads(content)
            if isinstance(questions, list) and len(questions) > 0:
                return questions
            else:
                logger.warning("Invalid quiz questions format from OpenAI, using mock data")
                return _get_mock_quiz_questions()
        except json.JSONDecodeError:
            logger.error("Failed to parse quiz questions JSON from OpenAI")
            return _get_mock_quiz_questions()
    
    except Exception as e:
        logger.error(f"Error generating quiz questions: {str(e)}")
        return _get_mock_quiz_questions()

def _get_mock_quiz_questions() -> List[Dict[str, Any]]:
    """Return mock quiz question data"""
    return [
        {
            "question": "Which of the following is NOT a type of machine learning?",
            "options": [
                "Supervised learning",
                "Unsupervised learning",
                "Reinforcement learning",
                "Prospective learning"
            ],
            "correct_answer": 3,
            "explanation": "The three main types of machine learning are supervised learning, unsupervised learning, and reinforcement learning. 'Prospective learning' is not a standard type of machine learning."
        },
        {
            "question": "What is the purpose of the activation function in a neural network?",
            "options": [
                "To initialize the weights",
                "To add non-linearity to the model",
                "To normalize the input data",
                "To reduce computational complexity"
            ],
            "correct_answer": 1,
            "explanation": "Activation functions add non-linearity to neural networks, allowing them to learn complex patterns that couldn't be modeled with just linear combinations."
        },
        {
            "question": "Which algorithm is commonly used for dimensional reduction?",
            "options": [
                "Random Forest",
                "Gradient Boosting",
                "Principal Component Analysis (PCA)",
                "K-Nearest Neighbors (KNN)"
            ],
            "correct_answer": 2,
            "explanation": "PCA is a widely used technique for dimensionality reduction that transforms high-dimensional data into a lower-dimensional space while preserving as much variance as possible."
        },
        {
            "question": "What does the term 'epoch' refer to in machine learning?",
            "options": [
                "A hyperparameter that controls model complexity",
                "The time it takes to train a model",
                "A complete pass through the entire training dataset",
                "The error rate of a model"
            ],
            "correct_answer": 2,
            "explanation": "An epoch in machine learning refers to one complete pass through the entire training dataset during the training process."
        },
        {
            "question": "Which of the following is a common loss function for binary classification?",
            "options": [
                "Mean Squared Error",
                "Binary Cross-Entropy",
                "Hinge Loss",
                "All of the above"
            ],
            "correct_answer": 1,
            "explanation": "Binary Cross-Entropy (also called Log Loss) is commonly used for binary classification problems as it measures the performance of a model whose output is a probability value between 0 and 1."
        }
    ]

async def store_learning_material(material_data: Dict[str, Any]) -> str:
    """
    Store a learning material in the database.
    Returns the ID of the newly created material.
    """
    logger.info(f"Storing learning material of type {material_data.get('type')} for paper {material_data.get('paper_id')}")
    
    try:
        material_id = str(uuid.uuid4())
        material_data["id"] = material_id
        
        # Store in Supabase items table
        result = supabase.table("items").insert(material_data).execute()
        
        if len(result.data) == 0:
            raise Exception("Failed to insert learning material into database")
        
        # If this is a quiz material, also store the questions
        if material_data.get("type") == "quiz" and "questions" in material_data.get("data", {}):
            for question in material_data["data"]["questions"]:
                question_data = {
                    "id": str(uuid.uuid4()),
                    "item_id": material_id,
                    "type": question["type"],
                    "text": question["text"],
                    "choices": question.get("choices"),
                    "correct_answer": question["correct_answer"]
                }
                
                # Store in Supabase questions table
                supabase.table("questions").insert(question_data).execute()
        
        return material_id
        
    except Exception as e:
        logger.error(f"Error storing learning material: {str(e)}")
        raise

async def get_materials_for_paper(paper_id: str, level: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieve learning materials for a specific paper.
    Optionally filter by difficulty level.
    """
    logger.info(f"Retrieving learning materials for paper {paper_id}, level: {level}")
    
    try:
        query = supabase.table("items").select("*").eq("paper_id", paper_id).order("order", desc=False)
        
        if level:
            query = query.eq("level", level)
            
        result = query.execute()
        
        if not result.data:
            logger.warning(f"No learning materials found for paper {paper_id}")
            return []
            
        return result.data
        
    except Exception as e:
        logger.error(f"Error retrieving learning materials: {str(e)}")
        raise

async def generate_learning_path(paper_id: str, user_id: Optional[str] = None) -> LearningPath:
    """
    Generate a learning path for a paper.
    
    Args:
        paper_id: The ID of the paper
        user_id: The optional ID of the user requesting the learning path
        
    Returns:
        LearningPath: A learning path with learning materials
    """
    # Check if we have a cached learning path for this paper
    if paper_id in learning_path_cache:
        logger.info(f"Using cached learning path for paper {paper_id}")
        return learning_path_cache[paper_id]
    
    # Generate a new learning path
    logger.info(f"Generating new learning path for paper {paper_id}")
    
    # 1. Generate text content (would use OpenAI in production)
    text_items = generate_text_content(paper_id)
    
    # 2. Fetch YouTube videos
    videos = await fetch_youtube_videos(paper_id)
    
    # 3. Generate flashcards
    flashcards = await generate_flashcards(paper_id)
    
    # 4. Generate quiz questions
    questions = await generate_quiz_questions(paper_id)
    
    # Compile all materials into a learning path
    learning_items = []
    
    # Add text content first
    learning_items.extend(text_items)
    
    # Add videos
    for video in videos:
        learning_items.append(
            LearningItem(
                id=str(uuid.uuid4()),
                paper_id=paper_id,
                type=LearningItemType.VIDEO,
                title=video["title"],
                content=video["description"],
                metadata={
                    "video_id": video["video_id"],
                    "thumbnail": video["thumbnail"],
                    "channel": video["channel"],
                    "duration": video["duration"]
                },
                difficulty_level=random.randint(1, 3)
            )
        )
    
    # Add flashcards
    for flashcard in flashcards:
        learning_items.append(
            LearningItem(
                id=str(uuid.uuid4()),
                paper_id=paper_id,
                type=LearningItemType.FLASHCARD,
                title=flashcard["front"][:50] + "...",
                content=flashcard["front"],
                metadata={
                    "back": flashcard["back"]
                },
                difficulty_level=random.randint(1, 3)
            )
        )
    
    # Add quiz questions
    for question in questions:
        question_id = str(uuid.uuid4())
        learning_items.append(
            LearningItem(
                id=question_id,
                paper_id=paper_id,
                type=LearningItemType.QUIZ,
                title=question["question"][:50] + "...",
                content=question["question"],
                metadata={
                    "options": question["options"],
                    "correct_answer": question["correct_answer"],
                    "explanation": question["explanation"]
                },
                difficulty_level=random.randint(1, 3)
            )
        )
    
    # Create the learning path
    learning_path = LearningPath(
        id=str(uuid.uuid4()),
        paper_id=paper_id,
        title=f"Learning Path for Paper {paper_id}",
        description="A comprehensive learning path to understand this paper",
        items=learning_items,
        created_at=datetime.now().isoformat(),
        estimated_time_minutes=len(learning_items) * 10  # Rough estimate
    )
    
    # Cache for future requests
    learning_path_cache[paper_id] = learning_path
    
    return learning_path

def generate_text_content(paper_id: str) -> List[LearningItem]:
    """Generate explanatory text content for different aspects of the paper"""
    # This would use OpenAI API in production to generate content
    # For now, we'll use mock data
    sections = [
        {
            "title": "Introduction to Key Concepts",
            "content": "This section introduces the fundamental concepts covered in the paper..."
        },
        {
            "title": "Methodology Explained",
            "content": "The methodology used in this paper involves several key steps..."
        },
        {
            "title": "Results Analysis",
            "content": "The results of the paper demonstrate significant findings in the field..."
        }
    ]
    
    return [
        LearningItem(
            id=str(uuid.uuid4()),
            paper_id=paper_id,
            type=LearningItemType.TEXT,
            title=section["title"],
            content=section["content"],
            metadata={},
            difficulty_level=i+1
        )
        for i, section in enumerate(sections)
    ]

async def get_learning_path(paper_id: str) -> Dict[str, Any]:
    """
    Retrieve an existing learning path or generate a new one if it doesn't exist.
    """
    logger.info(f"Getting learning path for paper {paper_id}")
    
    try:
        # Check if materials already exist for this paper
        existing_materials = await get_materials_for_paper(paper_id)
        
        if existing_materials:
            logger.info(f"Found {len(existing_materials)} existing materials for paper {paper_id}")
            
            # Calculate total estimated time
            total_time = 0
            for material in existing_materials:
                if material["type"] == "text":
                    total_time += 10  # Estimate 10 minutes for reading
                elif material["type"] == "flashcard":
                    total_time += len(material.get("data", {}).get("cards", [])) * 2  # 2 minutes per card
                elif material["type"] == "quiz":
                    total_time += len(material.get("data", {}).get("questions", [])) * 3  # 3 minutes per question
                
                # Add video times if available
                if material.get("videos"):
                    for video in material.get("videos", []):
                        duration = video.get("duration", "10:00")
                        mins, secs = map(int, duration.split(":"))
                        total_time += mins * 60 + secs
            
            return {
                "paper_id": paper_id,
                "materials": existing_materials,
                "estimated_total_time_minutes": total_time,
                "last_modified": existing_materials[0].get("created_at", datetime.now().isoformat()) if existing_materials else datetime.now().isoformat()
            }
        else:
            logger.info(f"No learning materials found for paper {paper_id}, generating new learning path")
            return await generate_learning_path(paper_id)
            
    except Exception as e:
        logger.error(f"Error getting learning path: {str(e)}")
        raise

async def record_user_progress(user_id: str, item_id: str, status: str, 
                             sprt_log_likelihood_ratio: float = 0.0, 
                             decision: str = "in_progress") -> Dict[str, Any]:
    """
    Record a user's progress on a learning item.
    """
    logger.info(f"Recording progress for user {user_id} on item {item_id}, status: {status}")
    
    try:
        progress_data = {
            "user_id": user_id,
            "item_id": item_id,
            "status": status,
            "sprt_log_likelihood_ratio": sprt_log_likelihood_ratio,
            "decision": decision
        }
        
        # Upsert into progress table (insert if not exists, update if exists)
        result = supabase.table("progress").upsert(progress_data).execute()
        
        if not result.data:
            raise Exception("Failed to record user progress")
            
        return result.data[0]
        
    except Exception as e:
        logger.error(f"Error recording user progress: {str(e)}")
        raise

async def record_answer(user_id: str, question_id: str, answer: str) -> Dict[str, Any]:
    """
    Record a user's answer to a question.
    """
    logger.info(f"Recording answer for user {user_id} on question {question_id}")
    
    try:
        answer_data = {
            "user_id": user_id,
            "question_id": question_id,
            "answer": answer,
            "timestamp": datetime.now().isoformat()
        }
        
        # Insert into answers table
        result = supabase.table("answers").insert(answer_data).execute()
        
        if not result.data:
            raise Exception("Failed to record user answer")
            
        return result.data[0]
        
    except Exception as e:
        logger.error(f"Error recording user answer: {str(e)}")
        raise

async def get_user_progress(user_id: str, paper_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get a user's progress on learning items, optionally filtered by paper.
    """
    logger.info(f"Getting progress for user {user_id}, paper: {paper_id}")
    
    try:
        # Start with a basic query
        query = supabase.table("progress").select("*,items(*)").eq("user_id", user_id)
        
        # If paper_id is provided, filter by it
        if paper_id:
            query = query.eq("items.paper_id", paper_id)
            
        result = query.execute()
        
        if not result.data:
            logger.warning(f"No progress found for user {user_id}")
            return []
            
        return result.data
        
    except Exception as e:
        logger.error(f"Error getting user progress: {str(e)}")
        raise

# User progress tracking
progress_records: List[UserProgressRecord] = []

async def record_progress(item_id: str, user_id: str, status: str, time_spent_seconds: int) -> None:
    """
    Record a user's progress on a learning item.
    
    Args:
        item_id: The ID of the learning item
        user_id: The ID of the user
        status: The completion status (started, completed, etc.)
        time_spent_seconds: Time spent on the item in seconds
    """
    record = UserProgressRecord(
        id=str(uuid.uuid4()),
        user_id=user_id,
        item_id=item_id,
        status=status,
        time_spent_seconds=time_spent_seconds,
        timestamp=datetime.now().isoformat()
    )
    progress_records.append(record)
    logger.info(f"Recorded progress for user {user_id} on item {item_id}: {status}")

async def get_user_progress(user_id: str, paper_id: Optional[str] = None) -> List[UserProgressRecord]:
    """
    Get a user's progress on learning materials.
    
    Args:
        user_id: The ID of the user
        paper_id: Optional paper ID to filter by
        
    Returns:
        List[UserProgressRecord]: The user's progress records
    """
    if paper_id:
        # Filter by paper ID (would join with learning items in a real DB)
        # This is just a mock implementation
        return [record for record in progress_records if record.user_id == user_id]
    else:
        return [record for record in progress_records if record.user_id == user_id]

async def submit_answer(question_id: str, user_id: str, answer_index: int) -> AnswerResult:
    """
    Submit an answer to a quiz question and evaluate it.
    
    Args:
        question_id: The ID of the quiz question
        user_id: The ID of the user
        answer_index: The index of the selected answer
        
    Returns:
        AnswerResult: The result of the answer submission
    """
    # Find the learning item for this question
    # In a real implementation, this would query the database
    
    # Mock implementation - look through all cached learning paths
    correct_answer = None
    explanation = None
    
    for learning_path in learning_path_cache.values():
        for item in learning_path.items:
            if item.id == question_id and item.type == LearningItemType.QUIZ:
                correct_answer = item.metadata.get("correct_answer")
                explanation = item.metadata.get("explanation")
                break
        if correct_answer is not None:
            break
    
    # If we couldn't find the question, return a default response
    if correct_answer is None:
        return AnswerResult(
            is_correct=False,
            correct_answer=0,  # Default
            explanation="Question not found",
            user_id=user_id,
            question_id=question_id,
            selected_answer=answer_index,
            timestamp=datetime.now().isoformat()
        )
    
    # Evaluate the answer
    is_correct = answer_index == correct_answer
    
    # Record the result
    result = AnswerResult(
        is_correct=is_correct,
        correct_answer=correct_answer,
        explanation=explanation or "No explanation available",
        user_id=user_id,
        question_id=question_id,
        selected_answer=answer_index,
        timestamp=datetime.now().isoformat()
    )
    
    # In a real implementation, we would store this result in the database
    logger.info(f"User {user_id} answered question {question_id}: {'Correct' if is_correct else 'Incorrect'}")
    
    return result

async def get_learning_items_by_level(paper_id: str, difficulty_level: int) -> List[LearningItem]:
    """
    Get learning items filtered by difficulty level.
    
    Args:
        paper_id: The ID of the paper
        difficulty_level: The difficulty level to filter by (1-3)
        
    Returns:
        List[LearningItem]: The filtered learning items
    """
    # Get the learning path for this paper
    if paper_id not in learning_path_cache:
        await generate_learning_path(paper_id)
    
    learning_path = learning_path_cache.get(paper_id)
    if not learning_path:
        return []
    
    # Filter items by difficulty level
    return [item for item in learning_path.items if item.difficulty_level == difficulty_level] 