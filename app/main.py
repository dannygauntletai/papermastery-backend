from dotenv import load_dotenv
import os

# Load environment variables from .env file at the application start
load_dotenv()

# Explicitly set OpenAI API key in the environment
openai_key = os.getenv("OPENAI_API_KEY")
if openai_key:
    os.environ["OPENAI_API_KEY"] = openai_key
    print(f"Set OpenAI API key in environment (prefix: {openai_key[:8]}...)")

from fastapi import FastAPI, Depends, status, Query, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute
from app.dependencies import validate_environment
from app.api.v1.endpoints import chat, papers, learning, waiting_list, consulting
from app.core.config import get_settings
from app.core.logger import get_logger
import inspect
from typing import Callable, Dict, Any, List, Optional
import time

# Add imports for new auth and webhooks routers
from app.api.v1.endpoints import auth, webhooks

settings = get_settings()
logger = get_logger(__name__)

# Use the standard APIRoute instead of a patched version
app = FastAPI(
    title="ArXiv Mastery API",
    description="""
    # ArXiv Mastery API
    
    This API provides access to the ArXiv Mastery platform, which helps researchers
    manage, search, and interact with scientific papers from arXiv.
    
    ## Features
    
    - Paper metadata retrieval from arXiv
    - PDF downloading and text extraction
    - Text chunking and processing
    - Full-text search
    - Related papers discovery
    - Chat interface for paper discussions
    
    ## Implementation Details
    
    - FastAPI backend with async support
    - Supabase for authentication and database
    - OpenAI and Google Gemini for AI capabilities
    - Namespace-based organization for multi-user support
    """,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "papers",
            "description": "Operations related to paper submission, retrieval, and processing"
        },
        {
            "name": "learning",
            "description": "Operations related to learning paths, quizzes, and educational content"
        },
        {
            "name": "chat",
            "description": "Operations related to chat functionality with papers"
        },
        {
            "name": "waiting-list",
            "description": "Operations related to the waiting list for Paper Mastery"
        },
        {
            "name": "system",
            "description": "System-level operations like health checks"
        }
    ]
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080", "*"],  # For development; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global start time for uptime tracking
start_time = time.time()


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint that returns basic API information."""
    return {
        "name": "ArXiv Mastery API",
        "version": "0.1.0",
        "description": "API for managing and interacting with scientific papers from arXiv",
        "features": [
            "Paper metadata retrieval",
            "PDF downloading and text extraction",
            "Text chunking and processing",
            "Full-text search",
            "Related papers discovery",
            "Chat interface for paper discussions"
        ],
        "technologies": [
            "FastAPI",
            "Supabase for authentication and database",
            "OpenAI and Google Gemini for AI capabilities"
        ],
        "documentation": "/docs"
    }


@app.get("/health", status_code=status.HTTP_200_OK, tags=["system"])
async def health_check():
    """
    Health check endpoint for monitoring and deployment platforms.
    
    Returns:
        dict: Health status information including uptime
    """
    uptime = time.time() - start_time
    return {
        "status": "healthy",
        "uptime_seconds": uptime,
        "service": "arxiv-mastery-api"
    }


# Validate environment variables
validate_environment()

# Include routers
app.include_router(papers.router, prefix=f"{settings.API_V1_STR}")
app.include_router(chat.router, prefix=f"{settings.API_V1_STR}")
app.include_router(learning.router, prefix=f"{settings.API_V1_STR}")
app.include_router(waiting_list.router, prefix=f"{settings.API_V1_STR}")
app.include_router(consulting.router, prefix=f"{settings.API_V1_STR}")

# Include new routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}")
app.include_router(webhooks.router, prefix=f"{settings.API_V1_STR}")

# Custom OpenAPI schema to properly document the API
def custom_openapi():
    """
    Generate a custom OpenAPI schema for the application.
    
    This function enhances the default OpenAPI schema with additional information,
    examples, and better descriptions for the API endpoints.
    
    Returns:
        dict: The enhanced OpenAPI schema
    """
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Add a more detailed API description
    openapi_schema["info"]["description"] = """
    # ArXiv Mastery API

    This API transforms arXiv papers into personalized learning experiences.
    
    ## Key Features:
    
    * **Paper Processing**: Submit arXiv links and get structured paper data
    * **Tiered Summaries**: Get beginner, intermediate, and advanced summaries
    * **Learning Paths**: Generate customized learning paths based on papers
    * **Interactive Chat**: Ask questions about papers and get AI-generated answers
    * **Learning Materials**: Access text, videos, flashcards, and quizzes for papers
    * **Progress Tracking**: Track your learning progress and quiz results
    
    ## Technology Stack:
    
    * **Backend**: FastAPI, Python, Pydantic
    * **Storage**: Supabase for paper metadata and summaries
    * **NLP**: OpenAI GPT models for summarization, chat, flashcards, and quizzes
    * **External APIs**: YouTube API for educational videos
    
    ## API Usage Guide:
    
    1. **Submit a Paper**: POST to `/api/v1/papers/submit` with an arXiv link
    2. **List Papers**: GET `/api/v1/papers/` to see all processed papers
    3. **Get Paper Details**: GET `/api/v1/papers/{paper_id}` for a specific paper
    4. **Get Summaries**: GET `/api/v1/papers/{paper_id}/summaries` for tiered summaries
    5. **Get Related Papers**: GET `/api/v1/papers/{paper_id}/related` for similar papers
    6. **Chat with Paper**: POST to `/api/v1/chat/{paper_id}` with your question
    7. **Get Learning Path**: GET `/api/v1/learning/papers/{paper_id}/learning-path` for a personalized learning path
    8. **Get Learning Materials**: GET `/api/v1/learning/papers/{paper_id}/materials` for all learning materials
    9. **Filter by Difficulty**: GET `/api/v1/learning/papers/{paper_id}/materials?difficulty_level=1` for beginner content
    10. **Track Progress**: POST to `/api/v1/learning/learning-items/{item_id}/progress` to record your progress
    11. **Take Quizzes**: POST to `/api/v1/learning/questions/{question_id}/answer` to submit quiz answers
    
    ## Paper Processing Status:
    
    The `tags.status` field in the paper response indicates the processing state:
    
    * **pending**: Initial metadata fetched, awaiting processing
    * **processing**: Currently generating summaries or finding related papers
    * **completed**: All processing finished, all features available
    * **failed**: Processing encountered an error
    
    ## Learning Material Types:
    
    * **text**: Explanatory content about different aspects of the paper
    * **video**: Educational YouTube videos related to the paper topics
    * **flashcard**: Memory cards for spaced repetition learning
    * **quiz**: Multiple-choice questions to test understanding
    
    ## Difficulty Levels:
    
    * **1**: Beginner level content for those new to the subject
    * **2**: Intermediate level content for those with some background
    * **3**: Advanced level content for deeper understanding
    
    ## Data Models:
    
    * **PaperResponse**: Complete paper with metadata, summaries, and related papers
    * **PaperSummary**: Tiered summaries at beginner, intermediate, and advanced levels
    * **ChatRequest**: Question about a paper
    * **ChatResponse**: AI-generated answer with source references
    * **LearningPath**: Personalized learning path for a paper
    * **LearningItem**: Individual learning materials (text, video, flashcard, quiz)
    * **UserProgressRecord**: User progress on learning items
    * **AnswerResult**: Results of submitted answers to quiz questions
    """
    
    # Add paper schema
    openapi_schema["components"]["schemas"]["Paper"] = {
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "format": "uuid",
                "description": "Unique identifier for the paper"
            },
            "arxiv_id": {
                "type": "string",
                "description": "ArXiv ID of the paper"
            },
            "title": {
                "type": "string",
                "description": "Title of the paper"
            },
            "authors": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Author name"
                        },
                        "affiliations": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "Author affiliations"
                        }
                    }
                },
                "description": "List of paper authors"
            },
            "abstract": {
                "type": "string",
                "description": "Abstract of the paper"
            },
            "publication_date": {
                "type": "string",
                "format": "date",
                "description": "Publication date of the paper"
            },
            "last_updated_date": {
                "type": "string",
                "format": "date",
                "description": "Last updated date of the paper"
            },
            "categories": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "ArXiv categories of the paper"
            },
            "doi": {
                "type": "string",
                "description": "Digital Object Identifier"
            },
            "journal_ref": {
                "type": "string",
                "description": "Journal reference"
            },
            "pdf_url": {
                "type": "string",
                "format": "uri",
                "description": "URL to the PDF of the paper"
            },
            "tags": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["pending", "processing", "completed", "failed"],
                        "description": "Processing status of the paper"
                    }
                },
                "description": "Additional metadata and tags for the paper"
            },
            "summaries": {
                "type": "object",
                "properties": {
                    "beginner": {
                        "type": "string",
                        "description": "Beginner-level summary"
                    },
                    "intermediate": {
                        "type": "string",
                        "description": "Intermediate-level summary"
                    },
                    "advanced": {
                        "type": "string",
                        "description": "Advanced-level summary"
                    }
                },
                "description": "Tiered summaries of the paper"
            }
        }
    }
    
    # Add paper summary schema
    openapi_schema["components"]["schemas"]["PaperSummary"] = {
        "type": "object",
        "properties": {
            "beginner": {
                "type": "string",
                "description": "Simplified summary for beginners with minimal technical jargon"
            },
            "intermediate": {
                "type": "string",
                "description": "Intermediate summary with explained technical terms"
            },
            "advanced": {
                "type": "string",
                "description": "Advanced summary maintaining full technical depth"
            }
        },
        "description": "Tiered summaries of the paper at different expertise levels"
    }
    
    # Add learning path schema
    openapi_schema["components"]["schemas"]["LearningPath"] = {
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "format": "uuid",
                "description": "Unique identifier for the learning path"
            },
            "paper_id": {
                "type": "string",
                "format": "uuid",
                "description": "ID of the paper this learning path is for"
            },
            "title": {
                "type": "string",
                "description": "Title of the learning path"
            },
            "description": {
                "type": "string",
                "description": "Description of the learning path"
            },
            "items": {
                "type": "array",
                "items": {
                    "$ref": "#/components/schemas/LearningItem"
                },
                "description": "List of learning items in this path"
            },
            "created_at": {
                "type": "string",
                "format": "date-time",
                "description": "When this learning path was created"
            },
            "estimated_time_minutes": {
                "type": "integer",
                "description": "Estimated time to complete the learning path in minutes"
            }
        },
        "required": ["id", "paper_id", "title", "description", "items", "created_at", "estimated_time_minutes"]
    }
    
    # Add learning item schema
    openapi_schema["components"]["schemas"]["LearningItem"] = {
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "format": "uuid",
                "description": "Unique identifier for the learning item"
            },
            "paper_id": {
                "type": "string",
                "format": "uuid",
                "description": "ID of the paper this item is for"
            },
            "type": {
                "type": "string",
                "enum": ["text", "video", "flashcard", "quiz"],
                "description": "Type of learning material"
            },
            "title": {
                "type": "string",
                "description": "Title of the learning item"
            },
            "content": {
                "type": "string",
                "description": "Content of the learning item (text, question, front of flashcard, etc.)"
            },
            "metadata": {
                "type": "object",
                "additionalProperties": True,
                "description": "Additional metadata specific to the item type (e.g., video URL, quiz options, etc.)"
            },
            "difficulty_level": {
                "type": "integer",
                "minimum": 1,
                "maximum": 3,
                "description": "Difficulty level (1: beginner, 2: intermediate, 3: advanced)"
            }
        },
        "required": ["id", "paper_id", "type", "title", "content", "difficulty_level"]
    }
    
    # Add user progress record schema
    openapi_schema["components"]["schemas"]["UserProgressRecord"] = {
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "format": "uuid",
                "description": "Unique identifier for the progress record"
            },
            "user_id": {
                "type": "string",
                "description": "ID of the user"
            },
            "item_id": {
                "type": "string",
                "format": "uuid",
                "description": "ID of the learning item"
            },
            "status": {
                "type": "string",
                "enum": ["not_started", "in_progress", "completed"],
                "description": "Status of progress on this item"
            },
            "time_spent_seconds": {
                "type": "integer",
                "description": "Time spent on this item in seconds"
            },
            "timestamp": {
                "type": "string",
                "format": "date-time",
                "description": "When this progress was recorded"
            }
        },
        "required": ["id", "user_id", "item_id", "status", "time_spent_seconds", "timestamp"]
    }
    
    # Add quiz answer schema
    openapi_schema["components"]["schemas"]["QuizAnswer"] = {
        "type": "object",
        "properties": {
            "selected_answer": {
                "type": "integer",
                "minimum": 0,
                "description": "Index of the selected answer option"
            }
        },
        "required": ["selected_answer"]
    }
    
    # Add answer result schema
    openapi_schema["components"]["schemas"]["AnswerResult"] = {
        "type": "object",
        "properties": {
            "is_correct": {
                "type": "boolean",
                "description": "Whether the answer is correct"
            },
            "correct_answer": {
                "type": "integer",
                "description": "Index of the correct answer option"
            },
            "explanation": {
                "type": "string",
                "description": "Explanation of the correct answer"
            },
            "user_id": {
                "type": "string",
                "description": "ID of the user who submitted the answer"
            },
            "question_id": {
                "type": "string",
                "format": "uuid",
                "description": "ID of the question"
            },
            "selected_answer": {
                "type": "integer",
                "description": "Index of the answer selected by the user"
            },
            "timestamp": {
                "type": "string",
                "format": "date-time",
                "description": "When the answer was submitted"
            }
        },
        "required": ["is_correct", "correct_answer", "explanation", "user_id", "question_id", "selected_answer", "timestamp"]
    }
    
    # Define endpoint tags for better organization
    openapi_schema["tags"] = [
        {
            "name": "papers",
            "description": "Operations related to paper submission, retrieval, and processing"
        },
        {
            "name": "learning",
            "description": "Operations related to learning paths and educational materials"
        },
        {
            "name": "system",
            "description": "System status and health endpoints"
        },
        {
            "name": "chat",
            "description": "Chat with papers, ask questions, and get AI-generated answers"
        },
        {
            "name": "waiting-list",
            "description": "Operations related to the waiting list for Paper Mastery"
        }
    ]
    
    # Enhance ChatRequest schema
    if "ChatRequest" in openapi_schema["components"]["schemas"]:
        openapi_schema["components"]["schemas"]["ChatRequest"]["description"] = (
            "Request model for chatting with a paper. Submit your question about the paper "
            "content and the system will find relevant chunks and generate a response."
        )
        openapi_schema["components"]["schemas"]["ChatRequest"]["example"] = {
            "query": "What is the main methodology used in this paper?"
        }
    
    # Enhance ChatResponse schema
    if "ChatResponse" in openapi_schema["components"]["schemas"]:
        openapi_schema["components"]["schemas"]["ChatResponse"]["description"] = (
            "Response model for chat queries. Contains the AI-generated answer, "
            "the original query, and source chunks from the paper that were used to "
            "generate the response."
        )
        openapi_schema["components"]["schemas"]["ChatResponse"]["example"] = {
            "response": "The paper uses a novel deep learning approach combining "
                       "transformer models with...",
            "query": "What is the main methodology used in this paper?",
            "sources": [
                {
                    "chunk_id": "chunk_123",
                    "text": "In our methodology, we propose a novel approach using "
                           "transformer models...",
                    "metadata": {"page": 3, "section": "Methodology"}
                }
            ],
            "paper_id": "123e4567-e89b-12d3-a456-426614174000"
        }
    
    # Enhance PaperResponse schema with example and updated description
    if "PaperResponse" in openapi_schema["components"]["schemas"]:
        openapi_schema["components"]["schemas"]["PaperResponse"]["description"] = (
            "Complete paper data with metadata, summaries, and related papers. "
            "The tags field contains processing status and other metadata."
        )
        openapi_schema["components"]["schemas"]["PaperResponse"]["example"] = {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "arxiv_id": "1912.10389",
            "title": "Attention Is All You Need",
            "authors": [
                {
                    "name": "Jane Doe",
                    "affiliations": ["University of Research"]
                }
            ],
            "abstract": "We propose a novel architecture for neural sequence modeling...",
            "publication_date": "2020-01-01T00:00:00Z",
            "tags": {
                "status": "completed",
                "category": "machine-learning"
            },
            "summaries": {
                "beginner": "This paper introduces the Transformer model...",
                "intermediate": "The Transformer architecture uses self-attention...",
                "advanced": "The multi-head attention mechanism allows the model to..."
            },
            "related_papers": [
                {
                    "id": "456e789f-e89b-12d3-a456-426614174000",
                    "title": "BERT: Pre-training of Deep Bidirectional Transformers",
                    "authors": ["Researcher One", "Researcher Two"],
                    "arxiv_id": "1810.04805",
                    "url": "https://arxiv.org/abs/1810.04805"
                }
            ]
        }
    
    # Update submission endpoint documentation
    for path in openapi_schema["paths"]:
        if path.endswith("/papers/submit"):
            for method in openapi_schema["paths"][path]:
                if method == "post":
                    openapi_schema["paths"][path][method]["description"] = (
                        "Submit an arXiv paper for processing. The system will fetch metadata, "
                        "generate summaries, and identify related papers asynchronously. "
                        "The status can be tracked through the tags.status field."
                    )
                    if "responses" in openapi_schema["paths"][path][method]:
                        if "202" in openapi_schema["paths"][path][method]["responses"]:
                            openapi_schema["paths"][path][method]["responses"]["202"]["description"] = (
                                "Paper submission accepted and processing started. Returns the paper data "
                                "with initial metadata. Summaries and related papers will be added later."
                            )
        elif path.endswith("/papers/"):
            for method in openapi_schema["paths"][path]:
                if method == "get":
                    openapi_schema["paths"][path][method]["description"] = (
                        "List all papers in the system. Papers are ordered by publication date."
                    )
        elif "/papers/{paper_id}" in path and not path.endswith(("summaries", "related")):
            for method in openapi_schema["paths"][path]:
                if method == "get":
                    openapi_schema["paths"][path][method]["description"] = (
                        "Get detailed information about a specific paper including metadata, "
                        "summaries (if available), and related papers (if available)."
                    )
        elif path.endswith("/summaries"):
            for method in openapi_schema["paths"][path]:
                if method == "get":
                    openapi_schema["paths"][path][method]["description"] = (
                        "Get tiered summaries (beginner, intermediate, advanced) for a specific paper. "
                        "Returns 404 if summaries are not yet generated."
                    )
        elif path.endswith("/related"):
            for method in openapi_schema["paths"][path]:
                if method == "get":
                    openapi_schema["paths"][path][method]["description"] = (
                        "Get related papers for a specific paper. Returns 404 if related papers "
                        "are not yet identified or if none are found."
                    )
        # Learning API documentation
        elif path.endswith("/learning-path"):
            for method in openapi_schema["paths"][path]:
                if method == "get":
                    openapi_schema["paths"][path][method]["description"] = (
                        "Get or generate a personalized learning path for a paper. The learning path includes "
                        "various types of learning materials (text, videos, flashcards, quizzes) organized in "
                        "a meaningful sequence with estimated time to complete."
                    )
                elif method == "post":
                    openapi_schema["paths"][path][method]["description"] = (
                        "Force regeneration of a new learning path for a paper. This will clear any cached "
                        "learning path and generate a fresh one with new materials."
                    )
        elif path.endswith("/materials") and "difficulty_level" in str(openapi_schema["paths"][path]):
            for method in openapi_schema["paths"][path]:
                if method == "get":
                    openapi_schema["paths"][path][method]["description"] = (
                        "Get learning materials for a paper, with optional filtering by difficulty level (1-3). "
                        "Returns all learning items associated with the paper, organized by type and difficulty."
                    )
        elif "/learning-items/{item_id}" in path and not path.endswith("/progress"):
            for method in openapi_schema["paths"][path]:
                if method == "get":
                    openapi_schema["paths"][path][method]["description"] = (
                        "Get a specific learning item by ID. Returns the complete details of the learning item, "
                        "including its content, type, and metadata."
                    )
        elif path.endswith("/progress"):
            for method in openapi_schema["paths"][path]:
                if method == "post":
                    openapi_schema["paths"][path][method]["description"] = (
                        "Record a user's progress on a learning item. This tracks completion status and time spent, "
                        "which can be used to generate progress reports and personalized recommendations."
                    )
        elif "/questions/{question_id}/answer" in path:
            for method in openapi_schema["paths"][path]:
                if method == "post":
                    openapi_schema["paths"][path][method]["description"] = (
                        "Submit an answer to a quiz question and get immediate feedback. Returns whether the "
                        "answer is correct, the correct answer, and an explanation of the answer."
                    )
        elif path.endswith("/user/progress"):
            for method in openapi_schema["paths"][path]:
                if method == "get":
                    openapi_schema["paths"][path][method]["description"] = (
                        "Get a user's progress on learning materials, optionally filtered by paper. "
                        "Returns a list of progress records with status and time spent information."
                    )
    
    # Make args and kwargs optional in schema
    for path in openapi_schema["paths"]:
        for method in openapi_schema["paths"][path]:
            if "parameters" in openapi_schema["paths"][path][method]:
                parameters = openapi_schema["paths"][path][method]["parameters"]
                # Filter out args and kwargs parameters completely
                openapi_schema["paths"][path][method]["parameters"] = [
                    param for param in parameters 
                    if param.get("name") not in ["args", "kwargs"]
                ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi 