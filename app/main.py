from fastapi import FastAPI, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from app.dependencies import validate_environment
import time


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

# Store startup time for health check
start_time = time.time()


@app.get("/", dependencies=[Depends(validate_environment)])
async def root():
    """
    Root endpoint to verify API is running.
    
    Returns:
        dict: A simple welcome message
    """
    return {"message": "Welcome to ArXiv Mastery"}


@app.get("/health", status_code=status.HTTP_200_OK)
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


# Custom OpenAPI schema
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="ArXiv Mastery API",
        version="0.1.0",
        description=(
            "## Overview\n\n"
            "The ArXiv Mastery Platform transforms arXiv papers into personalized, "
            "interactive learning experiences. It fetches paper content and metadata, "
            "breaks it into tiered learning levels (beginner, intermediate, advanced), "
            "integrates multimedia, and employs gamification to enhance user engagement.\n\n"
            
            "## Key Features\n\n"
            "- **Paper Processing**: Submit arXiv links and get detailed metadata, summaries, and chunks\n"
            "- **Personalized Learning**: Generate learning paths tailored to different expertise levels\n"
            "- **Interactive Q&A**: Ask questions about paper content and get AI-generated answers\n"
            "- **Progress Tracking**: Monitor mastery percentage for each paper\n"
            "- **Multimedia Integration**: Access relevant YouTube videos and other learning materials\n\n"
            
            "## Authentication\n\n"
            "This API uses Supabase Auth for authentication. Include the JWT token in the Authorization header.\n\n"
            
            "## Rate Limiting\n\n"
            "Rate limiting is applied to prevent abuse. Please keep requests reasonable."
        ),
        routes=app.routes,
    )
    
    # Add more custom documentation
    # Define the various schemas based on our Pydantic models
    # This ensures documentation matches implementation
    
    # Add paper submission schema
    openapi_schema["components"]["schemas"]["PaperSubmission"] = {
        "type": "object",
        "required": ["arxiv_link"],
        "properties": {
            "arxiv_link": {
                "type": "string",
                "format": "url",
                "description": "URL to the arXiv paper (e.g., https://arxiv.org/abs/1912.10389)",
                "example": "https://arxiv.org/abs/1912.10389"
            }
        }
    }
    
    # Add paper response schema
    openapi_schema["components"]["schemas"]["PaperResponse"] = {
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "format": "uuid",
                "description": "Unique identifier for the paper"
            },
            "arxiv_id": {
                "type": "string",
                "description": "The arXiv ID of the paper"
            },
            "title": {
                "type": "string",
                "description": "The title of the paper"
            },
            "authors": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Author's name"
                        },
                        "affiliations": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "Author's affiliations"
                        }
                    }
                },
                "description": "List of authors"
            },
            "abstract": {
                "type": "string",
                "description": "Abstract of the paper"
            },
            "publication_date": {
                "type": "string",
                "format": "date-time",
                "description": "Publication date"
            },
            "summaries": {
                "type": "object",
                "properties": {
                    "beginner": {
                        "type": "string",
                        "description": "Simplified, jargon-free overview"
                    },
                    "intermediate": {
                        "type": "string",
                        "description": "Key points with explained technical terms"
                    },
                    "advanced": {
                        "type": "string",
                        "description": "Detailed summary with technical depth"
                    }
                },
                "description": "Tiered summaries of the paper"
            }
        }
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
                            "enum": ["quiz", "text", "flashcard"],
                            "description": "Type of learning material"
                        },
                        "level": {
                            "type": "string",
                            "enum": ["beginner", "intermediate", "advanced"],
                            "description": "Difficulty level"
                        },
                        "category": {
                            "type": "string",
                            "description": "Subject category (e.g., math, physics)"
                        },
                        "data": {
                            "type": "object",
                            "description": "Content of the learning material"
                        },
                        "order": {
                            "type": "integer",
                            "description": "Sequence order in the learning path"
                        },
                        "videos": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {
                                        "type": "string",
                                        "description": "Video title"
                                    },
                                    "url": {
                                        "type": "string",
                                        "format": "url",
                                        "description": "URL to the video"
                                    }
                                }
                            },
                            "description": "Related videos"
                        }
                    }
                },
                "description": "Learning materials in this path"
            },
            "estimated_time_minutes": {
                "type": "integer",
                "description": "Estimated time to complete the learning path in minutes"
            }
        }
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

# Import and include API routers
# Will be implemented in later phases
# from app.api.v1.endpoints import papers, learning
# app.include_router(papers.router, prefix="/api/v1")
# app.include_router(learning.router, prefix="/api/v1") 