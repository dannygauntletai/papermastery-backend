from fastapi import FastAPI, Depends, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute
from app.dependencies import validate_environment
from app.api.v1.endpoints.papers import router as papers_router
from app.api.v1.endpoints.chat import router as chat_router
import inspect
from typing import Callable, Dict, Any, List, Optional
import time


# Use the standard APIRoute instead of a patched version
app = FastAPI(
    title="ArXiv Mastery API",
    description=(
        "API for transforming arXiv papers into personalized learning experiences. "
        "This service fetches academic papers from arXiv, processes them into tiered "
        "learning materials (beginner, intermediate, advanced), and provides "
        "interactive learning paths with multimedia integration."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global start time for uptime tracking
start_time = time.time()


@app.get("/", dependencies=[Depends(validate_environment)])
async def root(
    # args: Optional[str] = Query(None, description="Not required"),
    # kwargs: Optional[str] = Query(None, description="Not required")
):
    """
    Root endpoint to verify API is running.
    
    Args:
        args: Optional arguments (system use only)
        kwargs: Optional keyword arguments (system use only)
    
    Returns:
        dict: A simple welcome message
    """
    return {"message": "Welcome to ArXiv Mastery"}


@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check(
    # args: Optional[str] = Query(None, description="Not required"),
    # kwargs: Optional[str] = Query(None, description="Not required")
):
    """
    Health check endpoint for monitoring and deployment platforms.
    
    Args:
        args: Optional arguments (system use only)
        kwargs: Optional keyword arguments (system use only)
    
    Returns:
        dict: Health status information including uptime
    """
    uptime = time.time() - start_time
    return {
        "status": "healthy",
        "uptime_seconds": uptime,
        "service": "arxiv-mastery-api"
    }


# Include API routers - use standard APIRoute
app.include_router(papers_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")

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
    
    ## Technology Stack:
    
    * FastAPI for the API framework
    * Pinecone for vector database operations
    * Supabase for authentication and data storage
    * LangChain for AI processing pipelines
    
    ## Getting Started:
    
    1. Submit a paper using the `/api/v1/papers/submit` endpoint
    2. Retrieve processed papers with `/api/v1/papers/{paper_id}`
    3. Chat with papers using `/api/v1/papers/{paper_id}/chat`
    
    For more information, refer to the detailed endpoint documentation below.
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
                "format": "date-time",
                "description": "Publication date of the paper"
            },
            "categories": {
                "type": "array",
                "nullable": True,
                "items": {
                    "type": "string"
                },
                "description": "ArXiv categories of the paper"
            },
            "tags": {
                "type": "array",
                "nullable": True,
                "items": {
                    "type": "string"
                },
                "description": "Tags categorizing the paper content"
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
            "paper_id": {
                "type": "string",
                "format": "uuid",
                "description": "The ID of the paper"
            },
            "materials": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "format": "uuid",
                            "description": "Unique identifier for the learning material"
                        },
                        "type": {
                            "type": "string",
                            "enum": ["video", "article", "book", "course", "exercise"],
                            "description": "Type of learning material"
                        },
                        "title": {
                            "type": "string",
                            "description": "Title of the learning material"
                        },
                        "description": {
                            "type": "string",
                            "description": "Description of the learning material"
                        },
                        "url": {
                            "type": "string",
                            "format": "uri",
                            "description": "URL to the learning material"
                        },
                        "level": {
                            "type": "string",
                            "enum": ["beginner", "intermediate", "advanced"],
                            "description": "Difficulty level of the material"
                        },
                        "estimated_time_minutes": {
                            "type": "integer",
                            "description": "Estimated time to complete in minutes"
                        },
                        "prerequisites": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "Prerequisites for this material"
                        }
                    }
                },
                "description": "List of learning materials in the path"
            },
            "estimated_total_time_minutes": {
                "type": "integer",
                "description": "Total estimated time to complete the learning path"
            },
            "last_modified": {
                "type": "string",
                "format": "date-time",
                "description": "When the learning path was last modified (matches publication date)"
            }
        },
        "description": "A structured learning path based on a paper"
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
    
    # Enhance PaperResponse schema with example
    if "PaperResponse" in openapi_schema["components"]["schemas"]:
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
            "publication_date": "2020-01-01T00:00:00Z"
        }
    
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