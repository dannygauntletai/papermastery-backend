papermastery-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                # FastAPI app setup and configuration
│   ├── dependencies.py        # Dependency injection for Pinecone and other services
│   ├── api/
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── endpoints/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── papers.py  # Endpoints for submitting arXiv links and retrieving paper data
│   │   │   │   └── learning.py# Endpoints for generating and retrieving learning paths
│   │   │   └── models.py      # Pydantic models for API validation
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py          # Configuration and environment variables
│   │   ├── exceptions.py      # Custom exceptions
│   │   └── logger.py          # Logging setup
│   ├── services/
│   │   ├── __init__.py
│   │   ├── arxiv_service.py   # Fetches paper metadata and content from arXiv API
│   │   ├── pinecone_service.py# Handles chunk embedding and Pinecone interactions
│   │   ├── summarization_service.py # Generates summaries using AI tools
│   │   ├── chunk_service.py   # Chunks paper content using NLP
│   │   └── learning_service.py# Creates learning paths from chunks
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── pdf_utils.py       # PDF text extraction and chunking
│   │   └── embedding_utils.py # Generates embeddings for chunks
│   └── database/
│       ├── __init__.py
│       └── supabase_client.py # Supabase client for metadata storage
├── tests/
│   ├── __init__.py
│   ├── test_papers.py         # Tests for paper submission and retrieval
│   ├── test_learning.py       # Tests for learning path generation
│   └── test_pinecone.py       # Tests for Pinecone integration
├── .env                       # Environment variables (API keys, etc.)
├── requirements.txt           # Project dependencies
└── README.md                  # Project documentation