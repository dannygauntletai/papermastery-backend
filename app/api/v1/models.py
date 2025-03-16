from pydantic import BaseModel, Field, HttpUrl, validator
import re
from typing import List, Dict, Optional, Any, Union
from datetime import datetime
from uuid import UUID
from enum import Enum

class SourceType(str, Enum):
    """Enum for paper source types."""
    ARXIV = "arxiv"
    PDF = "pdf"
    FILE = "file"

class PaperSubmission(BaseModel):
    """Model for submitting a paper."""
    source_url: Optional[HttpUrl] = Field(None, description="URL to the paper (arXiv or PDF)")
    source_type: Optional[SourceType] = None
    file_content: Optional[bytes] = Field(None, description="Binary content of the uploaded PDF file")
    file_name: Optional[str] = Field(None, description="Name of the uploaded PDF file")
    
    @validator('source_url')
    @classmethod
    def validate_source_url(cls, v, values):
        """Validate that the URL is a valid URL if provided."""
        # If source_type is FILE, source_url is not required
        if values.get('source_type') == SourceType.FILE and v is None:
            return v
            
        # For other source types, source_url is required
        if v is None and values.get('source_type') != SourceType.FILE:
            raise ValueError("source_url is required for non-file uploads")
            
        # Basic URL validation is handled by HttpUrl type
        return v
        
    @validator('file_content')
    @classmethod
    def validate_file_content(cls, v, values):
        """Validate that file_content is provided for file uploads."""
        if values.get('source_type') == SourceType.FILE and v is None:
            raise ValueError("file_content is required for file uploads")
        return v
        
    @validator('file_name')
    @classmethod
    def validate_file_name(cls, v, values):
        """Validate that file_name is provided for file uploads and has a .pdf extension."""
        if values.get('source_type') == SourceType.FILE:
            if v is None:
                raise ValueError("file_name is required for file uploads")
            if not v.lower().endswith('.pdf'):
                raise ValueError("Only PDF files are supported")
        return v

class Author(BaseModel):
    """Model for paper authors."""
    name: str
    affiliations: Optional[List[str]] = None

class PaperMetadata(BaseModel):
    """Model for paper metadata."""
    # Paper identifiers - at least one should be provided if available
    arxiv_id: Optional[str] = None
    # Core metadata
    title: str
    authors: List[Author]
    abstract: str 
    publication_date: datetime
    
    # Additional metadata
    categories: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    
    # Source information
    source_type: SourceType = SourceType.PDF  # Default to PDF instead of ARXIV
    source_url: str

class PaperSummary(BaseModel):
    """Model for paper summaries."""
    beginner: str
    intermediate: str
    advanced: str
    
class PaperBase(BaseModel):
    """Base model for paper attributes."""
    # Paper identifiers - at least one should be provided if available
    arxiv_id: Optional[str] = None
    
    # Core metadata
    title: str
    authors: List[Author]
    abstract: str
    publication_date: datetime
    full_text: Optional[str] = None
    
    # Source information
    source_type: SourceType = SourceType.PDF  # Default to PDF instead of ARXIV
    source_url: str

class PaperCreate(PaperBase):
    """Model for creating a paper entry."""
    pass

class Paper(PaperBase):
    """Complete paper model matching the database schema."""
    id: UUID
    summaries: Optional[PaperSummary] = None
    related_papers: Optional[List[Dict[str, Any]]] = None
    tags: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

class PaperResponse(Paper):
    """Model for paper response in API."""
    pass

# Flashcard and Quiz models
class CardItem(BaseModel):
    """Model for flashcard item."""
    front: str
    back: str

class QuestionItem(BaseModel):
    """Model for quiz question."""
    question: str
    options: List[str]
    correct_answer: int
    explanation: Optional[str] = None

# API models for learning materials
class LearningItemType(str, Enum):
    """Enum for learning item types."""
    TEXT = "text"
    VIDEO = "video"
    FLASHCARD = "flashcard"
    QUIZ = "quiz"

class ItemLevel(str, Enum):
    """Enum for item difficulty levels."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

class ItemCategory(str, Enum):
    """Enum for item categories."""
    MATH = "math"
    PHYSICS = "physics"
    COMPUTER_SCIENCE = "computer-science"
    ARTIFICIAL_INTELLIGENCE = "artificial-intelligence"
    NATURAL_LANGUAGE_PROCESSING = "natural-language-processing"
    GENERAL = "general"

# Database Models
class ItemBase(BaseModel):
    """Base model for learning items."""
    paper_id: UUID
    type: str
    level: str
    category: str
    data: Dict[str, Any]
    order: int
    videos: Optional[List[Dict[str, str]]] = None

class ItemCreate(ItemBase):
    """Model for creating a learning item."""
    pass

class Item(ItemBase):
    """Complete item model matching the database schema."""
    id: UUID

    class Config:
        from_attributes = True

class QuestionBase(BaseModel):
    """Base model for questions."""
    item_id: UUID
    type: str
    text: str
    choices: Optional[List[str]] = None
    correct_answer: str

class QuestionCreate(QuestionBase):
    """Model for creating a question."""
    pass

class Question(QuestionBase):
    """Complete question model matching the database schema."""
    id: UUID

    class Config:
        from_attributes = True

class AnswerBase(BaseModel):
    """Base model for user answers."""
    user_id: UUID
    question_id: UUID
    answer: str

class AnswerCreate(AnswerBase):
    """Model for creating an answer record."""
    pass

class Answer(AnswerBase):
    """Complete answer model matching the database schema."""
    id: UUID
    timestamp: datetime

    class Config:
        from_attributes = True

class ProgressBase(BaseModel):
    """Base model for user progress."""
    user_id: UUID
    item_id: UUID
    status: str
    sprt_log_likelihood_ratio: float = 0.0
    decision: str = "in_progress"
    time_spent_seconds: Optional[int] = 0

class ProgressCreate(ProgressBase):
    """Model for creating a progress record."""
    pass

class Progress(ProgressBase):
    """Complete progress model matching the database schema."""
    class Config:
        from_attributes = True

class BadgeBase(BaseModel):
    """Base model for badges."""
    name: str
    description: Optional[str] = None

class BadgeCreate(BadgeBase):
    """Model for creating a badge."""
    pass

class Badge(BadgeBase):
    """Complete badge model matching the database schema."""
    id: UUID

    class Config:
        from_attributes = True

class AchievementBase(BaseModel):
    """Base model for achievements."""
    user_id: UUID
    badge_id: UUID

class AchievementCreate(AchievementBase):
    """Model for creating an achievement record."""
    pass

class Achievement(AchievementBase):
    """Complete achievement model matching the database schema."""
    id: UUID
    awarded_at: datetime

    class Config:
        from_attributes = True

class QueryBase(BaseModel):
    """Base model for user queries."""
    user_id: UUID
    paper_id: UUID
    question_text: str
    answer_text: Optional[str] = None

class QueryCreate(QueryBase):
    """Model for creating a query record."""
    pass

class Query(QueryBase):
    """Complete query model matching the database schema."""
    id: UUID
    timestamp: datetime

    class Config:
        from_attributes = True

# API Models
class LearningItem(BaseModel):
    """
    API model for learning items.
    
    The metadata field has different structures depending on the item type:
    
    - For VIDEO items:
        metadata = {
            "videos": [
                {
                    "video_id": str,  # YouTube video ID
                    "title": str,     # Video title
                    "description": str,  # Video description
                    "thumbnail": str,  # URL to the video thumbnail
                    "channel": str,    # Name of the YouTube channel
                    "duration": str    # Video duration in ISO 8601 format (e.g., PT5M30S)
                },
                ...
            ]
        }
    
    - For QUIZ items:
        metadata = {
            "questions": [
                {
                    "question": str,   # The question text
                    "options": List[str],  # List of answer options
                    "correct_answer": int,  # Index of the correct answer
                    "explanation": str  # Explanation of the correct answer
                },
                ...
            ]
        }
    
    - For FLASHCARD items:
        metadata = {
            "back": str  # Text for the back of the flashcard
        }
    """
    id: str
    paper_id: str
    type: LearningItemType
    title: str
    content: str
    metadata: Dict[str, Any] = {}
    difficulty_level: int = Field(1, ge=1, le=3)

class LearningPath(BaseModel):
    """API model for learning paths."""
    id: str
    paper_id: str
    title: str
    description: str
    items: List[LearningItem]
    created_at: str
    estimated_time_minutes: int

class QuizAnswer(BaseModel):
    """API model for quiz answers."""
    selected_answer: int = Field(..., ge=0)

class AnswerResult(BaseModel):
    """API model for answer results."""
    is_correct: bool
    correct_answer: int
    explanation: str
    user_id: str
    question_id: str
    selected_answer: int
    timestamp: str

class UserProgressRecord(BaseModel):
    """API model for user progress records."""
    id: str
    user_id: str
    item_id: str
    status: str
    time_spent_seconds: int
    timestamp: str

# Chat models
class ChatRequest(BaseModel):
    """Model for chat requests."""
    query: str
    conversation_id: Optional[str] = None
    include_sources: bool = True
    
class MessageSource(BaseModel):
    """Model for message sources."""
    text: str
    page: Optional[int] = None
    position: Optional[Dict[str, Any]] = None
    
class MessageResponse(BaseModel):
    """Model for individual messages in a conversation."""
    id: str
    user_id: str
    paper_id: str
    conversation_id: str
    query: str
    response: str
    sources: Optional[List[MessageSource]] = None
    timestamp: datetime
    
    class Config:
        from_attributes = True
        
class ChatResponse(BaseModel):
    """Model for chat response."""
    conversation_id: str
    response: str
    sources: Optional[List[MessageSource]] = None 