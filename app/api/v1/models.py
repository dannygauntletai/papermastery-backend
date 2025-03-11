from pydantic import BaseModel, Field, HttpUrl, validator
import re
from typing import List, Dict, Optional, Any
from datetime import datetime
from uuid import UUID

class PaperSubmission(BaseModel):
    """Model for submitting an arXiv paper."""
    arxiv_link: HttpUrl = Field(..., description="URL to the arXiv paper")
    
    @validator('arxiv_link')
    def validate_arxiv_link(cls, v):
        """Validate that the URL is an arXiv link."""
        # Convert to string for regex matching
        v_str = str(v)
        if not re.match(r'https?://arxiv.org/(?:abs|pdf)/\d+\.\d+(?:v\d+)?', v_str):
            raise ValueError("URL must be a valid arXiv link (e.g., https://arxiv.org/abs/1912.10389)")
        return v

class Author(BaseModel):
    """Model for paper authors."""
    name: str
    affiliations: Optional[List[str]] = None

class PaperMetadata(BaseModel):
    """Model for paper metadata."""
    arxiv_id: str
    title: str
    authors: List[Author]
    abstract: str
    publication_date: datetime
    categories: Optional[List[str]] = None
    doi: Optional[str] = None
    
class PaperSummary(BaseModel):
    """Model for paper summaries."""
    beginner: str
    intermediate: str
    advanced: str
    
class PaperResponse(BaseModel):
    """Model for paper response."""
    id: UUID
    arxiv_id: str
    title: str
    authors: List[Author]
    abstract: str
    publication_date: datetime
    summaries: Optional[PaperSummary] = None
    related_papers: Optional[List[Dict[str, Any]]] = None
    tags: Optional[Dict[str, Any]] = None
    
class LearningMaterial(BaseModel):
    """Model for learning materials."""
    id: UUID
    paper_id: UUID
    type: str  # 'quiz', 'text', 'flashcard'
    level: str  # 'beginner', 'intermediate', 'advanced'
    category: str  # 'math', 'physics', etc.
    data: Dict[str, Any]
    order: int
    videos: Optional[List[Dict[str, str]]] = None
    
class LearningPath(BaseModel):
    """Model for learning paths."""
    paper_id: UUID
    materials: List[LearningMaterial]
    estimated_time_minutes: int

class ChatSourceChunk(BaseModel):
    """Model for a source chunk used in chat responses."""
    chunk_id: str
    text: str
    metadata: Optional[Dict[str, Any]] = None

class ChatRequest(BaseModel):
    """Model for chat requests."""
    query: str = Field(..., description="The user's question about the paper", min_length=1, max_length=1000)
    
    @validator('query')
    def validate_query(cls, v):
        """Validate that the query is not empty and is a reasonable length."""
        if len(v.strip()) == 0:
            raise ValueError("Query cannot be empty")
        return v

class ChatResponse(BaseModel):
    """Model for chat responses."""
    response: str = Field(..., description="The AI-generated response to the query")
    query: str = Field(..., description="The original query that was asked")
    sources: List[ChatSourceChunk] = Field(..., description="The source chunks used to generate the response")
    paper_id: UUID = Field(..., description="The ID of the paper that was queried") 