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
└── README.md                  # Project documentation
```

## API Endpoints

- `POST /api/v1/papers/submit`: Submit an arXiv paper for processing
- `GET /api/v1/papers/{id}`: Get paper details
- `GET /api/v1/papers/{id}/learning-path`: Get a personalized learning path
- `GET /api/v1/papers/{id}/summaries`: Get tiered summaries (beginner, intermediate, advanced)
- `POST /api/v1/learning-items/{id}/feedback`: Submit feedback on learning materials

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