from fastapi import FastAPI, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from app.dependencies import validate_environment
from app.api.v1.endpoints.papers import router as papers_router
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


# Include API routers
app.include_router(papers_router, prefix="/api/v1")


# Custom OpenAPI schema
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="ArXiv Mastery API",
        version="0.2.0",  # Updated version
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
            
            "## API Endpoints\n\n"
            "- `POST /api/v1/papers/submit`: Submit an arXiv paper for processing\n"
            "- `GET /api/v1/papers/{paper_id}`: Get a specific paper by ID\n"
            "- `GET /api/v1/papers/`: List all submitted papers\n"
            "- `GET /api/v1/papers/{paper_id}/summaries`: Get tiered summaries for a paper\n\n"
            
            "## Vector Database\n\n"
            "We use Pinecone for storing and retrieving vector embeddings of paper content. "
            "These embeddings enable semantic search and related paper recommendations.\n\n"
            
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
                "nullable": True,
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
            },
            "related_papers": {
                "type": "array",
                "nullable": True,
                "items": {
                    "type": "object",
                    "properties": {
                        "arxiv_id": {
                            "type": "string",
                            "description": "The arXiv ID of the related paper"
                        },
                        "title": {
                            "type": "string",
                            "description": "The title of the related paper"
                        },
                        "similarity_score": {
                            "type": "number",
                            "format": "float",
                            "description": "Similarity score between 0 and 1"
                        }
                    }
                },
                "description": "List of related papers based on semantic similarity"
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
        }
    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi 