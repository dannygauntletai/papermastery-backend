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
- **Text Processing**: PyPDF2, LangChain, OpenAI embeddings
- **APIs**: arXiv API, OpenAlex, Connected Papers, Semantic Scholar
- **LLM Integration**: OpenAI API (GPT-4o), Google Gemini API

## Getting Started

### Prerequisites

- Python 3.8+
- Supabase account
- Pinecone account (with a properly configured index)
- OpenAI API key or Google Gemini API key

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
   - Fill in the required API keys and configuration values:
   
   ```
   # OpenAI API
   OPENAI_API_KEY=your_openai_api_key
   OPENAI_MODEL=gpt-4o
   
   # Google Gemini API (alternative to OpenAI)
   GEMINI_API_KEY=your_gemini_api_key
   GEMINI_MODEL=gemini-1.5-pro
   
   # Pinecone
   PINECONE_API_KEY=your_pinecone_api_key
   PINECONE_ENVIRONMENT=your_pinecone_environment (e.g., us-east-1)
   PINECONE_INDEX=your_pinecone_index_name
   
   # Supabase
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_key
   
   # YouTube API (for learning features)
   YOUTUBE_API_KEY=your_youtube_api_key
   ```

### Running the Application

```bash
python -m app.main
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
├── tests/                     # All tests
│   ├── unit/                  # Unit tests for isolated components
│   ├── integration/           # Integration tests for multi-component flows
│   └── __init__.py            # Test package initialization
├── docs/                      # Documentation files
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

### Chat API Endpoints

The application includes a conversational interface for interacting with academic papers:

- `POST /api/v1/chat/papers/{paper_id}/messages`: Send a message to chat about a specific paper
  - Uses RAG (Retrieval-Augmented Generation) to provide context-aware answers
  - Retrieves relevant chunks from the paper using Pinecone vector search
  - Generates human-like responses using LLM models (OpenAI GPT or Google Gemini)

- `GET /api/v1/chat/papers/{paper_id}/messages`: Get chat history for a specific paper
  - Returns all previous messages for a given conversation

Example request:
```json
{
  "content": "What are the main conclusions of this paper?",
  "user_id": "user-123"
}
```

### Learning API Endpoints

The PaperMastery backend includes Learning API endpoints that provide personalized learning materials based on academic papers. These endpoints support:

- Generation of personalized learning paths for papers
- Access to various learning materials (text, videos, flashcards, quizzes)
- User progress tracking
- Quiz completion and evaluation

#### Learning API Routes

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

### Background Processing

The API includes background processing for:
- Downloading PDFs from arXiv
- Extracting and chunking text
- Generating embeddings and storing them in Pinecone
- Finding related papers via the OpenAlex API
- Generating multi-tiered summaries
- Creating learning materials (flashcards, quizzes, video recommendations)

## External API Integrations

The application integrates with several external APIs to provide rich features:

- **OpenAI API**: For embeddings generation and text completion
  - Used for generating embeddings with `text-embedding-3-large` model (3072 dimensions)
  - Used for text generation with GPT models (default: gpt-4o)

- **Google Gemini API**: Alternative to OpenAI for text generation
  - Used for text generation with Gemini model (default: gemini-1.5-pro)

- **Pinecone API**: For vector storage and similarity search
  - Uses namespaces to organize vectors by paper ID
  - Supports fallback index creation if dimension mismatch occurs
  - Provides similarity search for RAG implementation

- **YouTube API**: Fetches relevant educational videos
  - Used in the learning service to enhance learning materials

## Environment Variables

The application uses the following environment variables:

```
# OpenAI API
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-3-large

# Google Gemini API (alternative to OpenAI)
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-1.5-pro

# Pinecone
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_ENVIRONMENT=your_pinecone_environment (e.g., us-east-1)
PINECONE_INDEX=your_pinecone_index_name

# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# YouTube API (optional, for learning features)
YOUTUBE_API_KEY=your_youtube_api_key

# Application settings (optional)
APP_ENV=development  # Options: development, testing, production
LOG_LEVEL=INFO       # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
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

The project uses pytest for testing and includes both unit and integration tests:

- **Unit Tests**: Located in `tests/unit/`, these test individual components in isolation
- **Integration Tests**: Located in `tests/integration/`, these test how components work together

Run all tests with:
```bash
python -m pytest
```

Run tests with coverage:
```bash
python -m pytest --cov=app
```

Run specific test categories:
```bash
# Run only unit tests
python -m pytest tests/unit/

# Run only integration tests
python -m pytest tests/integration/

# Run a specific test file
python -m pytest tests/unit/test_flashcards.py
```

### Code Style

We follow PEP 8 style guidelines. Run linting with:

```bash
flake8
```

Format code with:
```bash
black app tests
```

Type checking with MyPy:
```bash
mypy app
```

### Pre-commit Hooks

The project uses pre-commit hooks to ensure code quality. Install them with:

```bash
pre-commit install
```

## LangChain Integration

The application uses LangChain for PDF processing and vector storage:

- **PDF Processing**: Uses LangChain's PyPDFLoader to load and process PDFs
- **Text Chunking**: Uses LangChain's RecursiveCharacterTextSplitter for intelligent text chunking
- **Embeddings**: Uses LangChain's OpenAIEmbeddings for generating embeddings
- **Vector Storage**: Uses LangChain's PineconeVectorStore for storing and retrieving embeddings
- **RAG Implementation**: Uses LangChain's similarity search capabilities for retrieval-augmented generation

The system supports fallback from LangChain methods to direct Pinecone/OpenAI implementations for robustness.

## Recent Updates

- **Reorganized Test Structure**: Separated tests into unit and integration directories for better organization
- **Added Google Gemini Support**: Implemented alternative LLM provider alongside OpenAI
- **Improved YouTube Video Integration**: Enhanced search query generation for more relevant educational videos
- **Enhanced Error Handling**: Added more robust error handling and fallback mechanisms throughout the codebase
- **Optimized Learning Path Generation**: Improved the generation and caching of learning materials
- **Improved LLM Interactions**: Better prompting and context management for higher quality AI responses

## License

[MIT License](LICENSE)

## Acknowledgements

- [arXiv](https://arxiv.org/) for providing access to research papers
- [Supabase](https://supabase.io/) for database and authentication
- [Pinecone](https://www.pinecone.io/) for vector search capabilities
- [OpenAI](https://openai.com/) for powerful language models and embeddings
- [Google AI](https://ai.google/) for Gemini models
- [LangChain](https://langchain.com/) for RAG components and PDF processing utilities 