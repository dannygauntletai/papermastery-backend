from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(
    title="ArXiv Mastery API",
    description=(
        "API for transforming arXiv papers into personalized learning experiences"
    ),
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint to verify API is running."""
    return {"message": "Welcome to ArXiv Mastery"}


# Import and include API routers
# Will be implemented in later phases
# from app.api.v1.endpoints import papers, learning
# app.include_router(papers.router, prefix="/api/v1")
# app.include_router(learning.router, prefix="/api/v1") 