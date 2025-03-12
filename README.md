# ArXiv Mastery Backend

A FastAPI-based backend service that transforms dense academic papers from arXiv into personalized, interactive learning experiences.

## Project Overview

ArXiv Mastery Platform solves the challenge of understanding complex academic papers by:

1. Processing arXiv papers and breaking them into logical chunks
2. Creating tiered learning paths (beginner, intermediate, advanced)
3. Generating interactive content like quizzes, flashcards, and summaries
4. Providing personalized learning experiences with AI-powered assistance

## Tech Stack

- **Framework**: FastAPI
- **Database**: Supabase (PostgreSQL)
- **Authentication**: Supabase Auth
- **Vector Database**: Pinecone (for embedding storage and retrieval)
- **Text Processing**: PyPDF2, Sentence Transformers
- **APIs**: arXiv API, OpenAlex, Connected Papers, Semantic Scholar

## Getting Started

### Prerequisites

- Python 3.8+
- Supabase account
- Pinecone account

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/papermastery-backend.git
   cd papermastery-backend
   ```

2. Set up a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure your environment variables:
   - Copy `.env.example` to `.env`
   - Fill in the required API keys and configuration values

### Running the Application

```bash
uvicorn app.main:app --reload
```

The API will be available at http://localhost:8000

API documentation is available at http://localhost:8000/docs

### Docker Support

You can also run the application using Docker:

```bash
# Build the image
docker build -t arxiv-mastery-api .

# Run the container
docker run -p 8000:8000 --env-file .env arxiv-mastery-api
```

Or using Docker Compose for development:

```bash
docker-compose up
```

## Project Structure

```
papermastery-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                # FastAPI app setup and configuration
│   ├── dependencies.py        # Dependency injection
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/     # API endpoints
│   │       └── models.py      # Pydantic models
│   ├── core/                  # Configuration and utilities
│   ├── services/              # Business logic
│   ├── utils/                 # Helper functions
│   └── database/              # Database clients
├── tests/                     # Unit and integration tests
├── .env                       # Environment variables
├── requirements.txt           # Project dependencies
├── Dockerfile                 # Docker configuration
├── docker-compose.yml         # Docker Compose configuration
├── render.yaml                # Render deployment configuration
└── README.md                  # Project documentation
```

## API Endpoints

### General Endpoints

- `GET /`: Root endpoint that returns a welcome message and verifies the API is running
- `GET /health`: Health check endpoint for monitoring and deployment platforms

### Paper Management

- `POST /api/v1/papers/submit`: Submit an arXiv paper for processing
  - Takes an arXiv link and starts background processing
  - Returns the basic paper information and a processing status
  
- `GET /api/v1/papers/{paper_id}`: Get detailed information for a specific paper
  - Includes metadata, processing status, and generated content when available
  
- `GET /api/v1/papers`: List all papers that have been submitted to the system
  - Returns a collection of paper records with their metadata and processing status
  
- `GET /api/v1/papers/{paper_id}/summaries`: Get tiered summaries for a specific paper
  - Returns beginner, intermediate, and advanced level summaries
  - These summaries are generated during the background processing stage

- `GET /api/v1/papers/{paper_id}/related`: Get related papers for a specific paper
  - Returns a list of related papers with their metadata
  - Uses the OpenAlex API to find papers that cite or are conceptually similar to the given paper

### Background Processing

The API includes background processing for:
- Downloading PDFs from arXiv
- Extracting and chunking text
- Generating embeddings and storing them in Pinecone
- Finding related papers via the OpenAlex API
- Generating multi-tiered summaries

## Learning API Endpoints

The PaperMastery backend now includes Learning API endpoints that provide personalized learning materials based on academic papers. These endpoints support:

- Generation of personalized learning paths for papers
- Access to various learning materials (text, videos, flashcards, quizzes)
- User progress tracking
- Quiz completion and evaluation

### Learning API Routes

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/learning/papers/{paper_id}/learning-path` | GET | Get or generate a learning path for a paper |
| `/api/v1/learning/papers/{paper_id}/materials` | GET | Get learning materials for a paper |
| `/api/v1/learning/papers/{paper_id}/materials?difficulty_level=1` | GET | Get learning materials filtered by difficulty level (1-3) |
| `/api/v1/learning/learning-items/{item_id}` | GET | Get a specific learning item by ID |
| `/api/v1/learning/learning-items/{item_id}/progress` | POST | Record a user's progress on a learning item |
| `/api/v1/learning/questions/{question_id}/answer` | POST | Submit an answer to a quiz question |
| `/api/v1/learning/user/progress` | GET | Get a user's progress on learning materials |
| `/api/v1/learning/papers/{paper_id}/generate-learning-path` | POST | Force generation of a new learning path |

### External API Integrations

The learning service integrates with several external APIs to provide rich educational content:

- **YouTube API**: Fetches relevant educational videos
- **OpenAI API**: Generates flashcards and quiz questions

### Environment Variables

Add the following environment variables to your `.env` file:

```
# YouTube API
YOUTUBE_API_KEY=your_youtube_api_key

# OpenAI API (if not already configured)
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o
```

### Testing the Learning API

Run the tests for the learning API endpoints:

```bash
pytest tests/test_learning.py -v
```

## API Documentation

The API is fully documented using OpenAPI:

- **Swagger UI**: Available at `/docs` endpoint
- **ReDoc**: Available at `/redoc` endpoint

The documentation includes:
- Detailed endpoint descriptions
- Request and response schemas
- Example requests and responses
- Authentication information

## Deployment

The application is ready for deployment on various platforms, with special support for Render:

1. **Render**: Use the provided `render.yaml` file for automatic deployment
2. **Docker**: Use the provided `Dockerfile` for containerized deployment
3. **Heroku**: Use the `Procfile` for Heroku deployment

For detailed deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).

## Development

### Testing

```bash
pytest
```

### Code Style

We follow PEP 8 style guidelines. Run linting with:

```bash
flake8
```

## License

[MIT License](LICENSE)

## Acknowledgements

- [arXiv](https://arxiv.org/) for providing access to research papers
- [Supabase](https://supabase.io/) for database and authentication
- [Pinecone](https://www.pinecone.io/) for vector search capabilities

## LangChain Integration

The application uses LangChain for PDF processing and vector storage:

- **PDF Processing**: Uses LangChain's PyPDFLoader to load and process PDFs
- **Text Chunking**: Uses LangChain's RecursiveCharacterTextSplitter for intelligent text chunking
- **Embeddings**: Uses LangChain's OpenAIEmbeddings for generating embeddings
- **Vector Storage**: Uses LangChain's PineconeVectorStore for storing and retrieving embeddings 