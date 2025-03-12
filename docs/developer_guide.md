# Developer Guide

This guide provides comprehensive information for developers working on the PaperMastery backend project.

## Setup

### Prerequisites

- Python 3.11+
- Git
- Docker (optional, for containerized development)
- Supabase account
- Pinecone account
- OpenAI API key
- YouTube API key

### Local Development Environment

1. **Clone the repository**

```bash
git clone https://github.com/yourusername/papermastery-backend.git
cd papermastery-backend
```

2. **Create and activate a virtual environment**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Set up environment variables**

Create a `.env` file in the project root by copying `.env.example`:

```bash
cp .env.example .env
```

Then edit the `.env` file to include your API keys and configuration settings:

```
# App configuration
APP_ENV=development
DEBUG=true
LOG_LEVEL=INFO

# Supabase configuration
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
SUPABASE_JWT_SECRET=your_supabase_jwt_secret

# Pinecone configuration
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_ENVIRONMENT=us-east-1
PINECONE_INDEX=papermastery

# OpenAI configuration
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o

# YouTube API
YOUTUBE_API_KEY=your_youtube_api_key

# Rate limiting
RATE_LIMIT_ENABLED=false
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD_SECONDS=3600
```

5. **Run the server**

```bash
uvicorn app.main:app --reload
```

The API will be available at http://localhost:8000, and the API documentation will be available at http://localhost:8000/docs.

## Project Structure

```
papermastery-backend/
├── app/                     # Main application code
│   ├── __init__.py
│   ├── main.py              # FastAPI app setup and configuration
│   ├── dependencies.py      # Dependency injection
│   ├── api/                 # API-related code
│   │   └── v1/              # API version 1
│   │       ├── endpoints/   # API endpoints
│   │       └── models.py    # Pydantic models
│   ├── core/                # Core configuration and utilities
│   ├── services/            # Business logic
│   ├── utils/               # Helper functions
│   └── database/            # Database clients
├── tests/                   # Test files
├── docs/                    # Documentation
├── .env                     # Environment variables (not committed)
├── .env.example             # Example environment variables
├── requirements.txt         # Project dependencies
├── Dockerfile               # Docker configuration
├── .github/workflows/       # GitHub Actions workflows
└── README.md                # Project overview
```

## Testing

### Running Tests

Run all tests:

```bash
python -m pytest
```

Run a specific test file:

```bash
python -m pytest tests/test_chat.py
```

Run a specific test:

```bash
python -m pytest tests/test_chat.py::test_chat_with_paper_success
```

Run tests with coverage:

```bash
python -m pytest --cov=app tests/
```

Generate a coverage report:

```bash
python -m pytest --cov=app --cov-report=html tests/
```

### Writing Tests

- Create test files in the `tests/` directory
- Use meaningful test names that describe what is being tested
- Use pytest fixtures for setup and teardown
- Mock external services and dependencies
- Test both success and failure cases

Example test structure:

```python
import pytest
from unittest.mock import patch, AsyncMock

def test_some_function_success():
    """Test successful execution of some_function."""
    # Setup
    test_input = "test"
    
    # Execute
    result = some_function(test_input)
    
    # Verify
    assert result == expected_output

def test_some_function_failure():
    """Test failure case of some_function."""
    # Setup
    invalid_input = None
    
    # Execute and verify
    with pytest.raises(ValueError):
        some_function(invalid_input)
```

## Code Standards

### Style Guide

- Follow PEP 8 for Python code style
- Use 4 spaces for indentation
- Maximum line length of 79 characters
- Use meaningful variable and function names
- Add docstrings to all modules, classes, and functions

### Documentation

- Update the documentation when adding or modifying features
- Document all API endpoints with clear descriptions and examples
- Use type hints consistently

### Git Workflow

1. Create a feature branch from `develop`:

```bash
git checkout develop
git pull
git checkout -b feature/your-feature-name
```

2. Make your changes and commit them:

```bash
git add .
git commit -m "feat: add your feature"
```

3. Push your branch and create a pull request:

```bash
git push -u origin feature/your-feature-name
```

4. After code review, merge your pull request to `develop`

### Continuous Integration

The project uses GitHub Actions for CI. The following checks run on each pull request:

- Linting with flake8
- Type checking with mypy
- Running tests with pytest
- Generating code coverage reports

## API Documentation

The API documentation is generated automatically using FastAPI's built-in support for OpenAPI:

- **Swagger UI**: Available at `/docs` endpoint
- **ReDoc**: Available at `/redoc` endpoint

### Updating API Documentation

The custom OpenAPI schema is defined in `app/main.py`. To update the documentation:

1. Update the `custom_openapi()` function in `app/main.py`
2. Add or modify schema definitions, descriptions, and examples
3. Restart the server to see the changes

## Deployment

### Preparing for Production

1. Set environment variables for production:
   - Set `APP_ENV=production`
   - Set `DEBUG=false`
   - Use secure API keys and credentials

2. Create a production-ready Dockerfile:
   - Use multi-stage builds for smaller images
   - Include only necessary files
   - Set proper security configurations

3. Set up monitoring and logging:
   - Configure proper logging levels
   - Set up error tracking (e.g., Sentry)
   - Configure performance monitoring

### Deployment Platforms

The project supports deployment on various platforms:

- **Render**: Use the provided `render.yaml` file
- **Docker/Kubernetes**: Use the provided `Dockerfile`
- **Heroku**: Use the provided `Procfile`

For detailed deployment instructions, see [DEPLOYMENT.md](../DEPLOYMENT.md).

## Troubleshooting

### Common Issues

1. **Database Connection Issues**
   - Check your Supabase URL and API key
   - Verify network connectivity
   - Check if your IP is allowed in Supabase settings

2. **Pinecone Connection Issues**
   - Verify your Pinecone API key
   - Check if your index exists and is properly configured
   - Verify your environment setting matches the index location

3. **FastAPI Server Not Starting**
   - Check for syntax errors in your code
   - Verify dependencies are installed
   - Check port availability

4. **Test Failures**
   - Make sure mock services are properly configured
   - Check for changed API contracts
   - Ensure environment variables are set for testing

### Getting Help

If you encounter issues not covered in this guide:

1. Check the GitHub issues for similar problems
2. Consult the FastAPI documentation
3. Reach out to the project maintainers 