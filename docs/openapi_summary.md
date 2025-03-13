# PaperMastery API Documentation

## Overview

The PaperMastery API provides functionality for transforming arXiv papers into personalized learning experiences. The service fetches academic papers, processes them into tiered learning materials, and offers interactive learning paths with multimedia integration.

Key features:
- PDF processing and chunking with LangChain
- Vector embeddings using OpenAI's text-embedding-3-large model
- RAG (Retrieval-Augmented Generation) for context-aware chat
- Tiered summaries for different expertise levels
- Pinecone vector database integration

## API Endpoints

### Paper Endpoints

#### Submit Paper

- **Endpoint**: `POST /papers/submit`
- **Description**: Submit an arXiv paper for processing. The submission is accepted immediately, and processing happens in the background.
- **Request Body**:
  ```json
  {
    "arxiv_link": "https://arxiv.org/abs/2203.12345"
  }
  ```
- **Response**: `PaperResponse` object with processing status
  ```json
  {
    "id": "uuid",
    "arxiv_id": "2203.12345",
    "title": "Paper Title",
    "authors": [
      {
        "name": "Author Name",
        "affiliations": ["University"]
      }
    ],
    "abstract": "Paper abstract text",
    "publication_date": "2023-03-15T00:00:00Z",
    "full_text": null,
    "embedding_id": null,
    "related_papers": null,
    "tags": {
      "status": "pending",
      "has_learning_materials": false,
      "learning_materials_count": 0
    },
    "summaries": null
  }
  ```

#### Get Paper

- **Endpoint**: `GET /papers/{paper_id}`
- **Description**: Retrieve a paper by its ID
- **Path Parameters**:
  - `paper_id`: UUID of the paper
- **Response**: `PaperResponse` object with paper details

#### List Papers

- **Endpoint**: `GET /papers/`
- **Description**: List all papers accessible to the current user
- **Response**: List of `PaperResponse` objects

#### Get Paper Summaries

- **Endpoint**: `GET /papers/{paper_id}/summaries`
- **Description**: Get beginner, intermediate, and advanced summaries for a paper
- **Path Parameters**:
  - `paper_id`: UUID of the paper
- **Response**: `PaperSummary` object with different summary levels
  ```json
  {
    "beginner": "Simple explanation of the paper",
    "intermediate": "More detailed explanation with some technical terms",
    "advanced": "Full technical explanation with all details"
  }
  ```

#### Get Related Papers

- **Endpoint**: `GET /papers/{paper_id}/related`
- **Description**: Get papers related to the specified paper
- **Path Parameters**:
  - `paper_id`: UUID of the paper
- **Response**: List of related paper objects

#### Get Paper Conversations

- **Endpoint**: `GET /papers/{paper_id}/conversations`
- **Description**: Get all conversations associated with a paper for the current user
- **Path Parameters**:
  - `paper_id`: UUID of the paper
- **Response**: List of conversation objects

### Learning Endpoints

#### Get Learning Path

- **Endpoint**: `GET /learning/papers/{paper_id}/learning-path`
- **Description**: Get a structured learning path for a paper
- **Path Parameters**:
  - `paper_id`: ID of the paper
- **Query Parameters**:
  - `use_mock_for_tests`: Boolean to use mock data for tests (default: false)
- **Response**: `LearningPath` object
  ```json
  {
    "id": "string",
    "paper_id": "string",
    "title": "Learning Path for Paper Title",
    "description": "A structured path to understand this paper",
    "items": [
      {
        "id": "string",
        "paper_id": "string",
        "type": "text|video|flashcard|quiz",
        "title": "Item Title",
        "content": "Item content text",
        "metadata": {},
        "difficulty_level": 1
      }
    ],
    "created_at": "2023-03-15T00:00:00Z",
    "estimated_time_minutes": 60
  }
  ```

#### Get Learning Materials

- **Endpoint**: `GET /learning/papers/{paper_id}/materials`
- **Description**: Get learning materials for a paper, optionally filtered by difficulty level
- **Path Parameters**:
  - `paper_id`: ID of the paper
- **Query Parameters**:
  - `difficulty_level`: Optional integer (1-3) to filter materials by difficulty
  - `use_mock_for_tests`: Boolean to use mock data for tests (default: false)
- **Response**: List of `LearningItem` objects

#### Get Learning Item

- **Endpoint**: `GET /learning/learning-items/{item_id}`
- **Description**: Get a specific learning item by its ID
- **Path Parameters**:
  - `item_id`: ID of the learning item
- **Response**: `LearningItem` object

#### Record Item Progress

- **Endpoint**: `POST /learning/learning-items/{item_id}/progress`
- **Description**: Record a user's progress on a learning item
- **Path Parameters**:
  - `item_id`: ID of the learning item
- **Request Body**:
  ```json
  {
    "status": "in_progress|completed",
    "time_spent_seconds": 120,
    "sprt_log_likelihood_ratio": 0.0,
    "decision": "in_progress|mastered|needs_review"
  }
  ```
- **Response**: No content (204)

#### Submit Question Answer

- **Endpoint**: `POST /learning/questions/{question_id}/answer`
- **Description**: Submit an answer to a quiz question
- **Path Parameters**:
  - `question_id`: ID of the quiz question
- **Request Body**:
  ```json
  {
    "selected_answer": 2
  }
  ```
- **Response**: `AnswerResult` object
  ```json
  {
    "is_correct": true,
    "correct_answer": 2,
    "explanation": "This is correct because...",
    "user_id": "string",
    "question_id": "string",
    "selected_answer": 2,
    "timestamp": "2023-03-15T00:00:00Z"
  }
  ```

#### Get User Progress

- **Endpoint**: `GET /learning/user/progress`
- **Description**: Get a user's progress on learning materials
- **Query Parameters**:
  - `paper_id`: Optional paper ID to filter progress by paper
- **Response**: List of `UserProgressRecord` objects

#### Generate New Learning Path

- **Endpoint**: `POST /learning/papers/{paper_id}/generate-learning-path`
- **Description**: Generate a new learning path for a paper, even if one already exists
- **Path Parameters**:
  - `paper_id`: ID of the paper
- **Response**: `LearningPath` object

#### Get Flashcards

- **Endpoint**: `GET /learning/papers/{paper_id}/flashcards`
- **Description**: Get flashcards for a paper
- **Path Parameters**:
  - `paper_id`: ID of the paper
- **Query Parameters**:
  - `use_mock_for_tests`: Boolean to use mock data for tests (default: false)
- **Response**: List of `CardItem` objects
  ```json
  [
    {
      "front": "What is supervised learning?",
      "back": "A type of machine learning where the model is trained on labeled data"
    }
  ]
  ```

#### Get Quiz Questions

- **Endpoint**: `GET /learning/papers/{paper_id}/quiz-questions`
- **Description**: Get quiz questions for a paper
- **Path Parameters**:
  - `paper_id`: ID of the paper
- **Query Parameters**:
  - `use_mock_for_tests`: Boolean to use mock data for tests (default: false)
- **Response**: List of `QuestionItem` objects
  ```json
  [
    {
      "question": "What is the purpose of regularization in machine learning?",
      "options": [
        "To increase model complexity",
        "To prevent overfitting",
        "To speed up convergence",
        "To allow for larger batch sizes"
      ],
      "correct_answer": 1,
      "explanation": "Regularization adds a penalty to the loss function to discourage complex models"
    }
  ]
  ```

### Chat Endpoints

#### Chat with Paper

- **Endpoint**: `POST /papers/{paper_id}/chat`
- **Description**: Chat with a paper by asking questions about its content
- **Path Parameters**:
  - `paper_id`: UUID of the paper
- **Request Body**:
  ```json
  {
    "query": "What are the main findings of this paper?",
    "conversation_id": "optional-conversation-id",
    "include_sources": true
  }
  ```
- **Response**: `ChatResponse` object
  ```json
  {
    "conversation_id": "string",
    "response": "The main findings of this paper are...",
    "sources": [
      {
        "text": "Source text from the paper",
        "page": 3,
        "position": {
          "top": 100,
          "left": 50
        }
      }
    ]
  }
  ```

#### Get Paper Messages

- **Endpoint**: `GET /papers/{paper_id}/messages`
- **Description**: Get all messages from conversations about a paper
- **Path Parameters**:
  - `paper_id`: UUID of the paper
- **Query Parameters**:
  - `conversation_id`: Optional conversation ID to filter messages
- **Response**: List of `MessageResponse` objects
  ```json
  [
    {
      "id": "string",
      "user_id": "string",
      "paper_id": "string",
      "conversation_id": "string",
      "query": "What is this paper about?",
      "response": "This paper is about...",
      "sources": [
        {
          "text": "Source text from the paper",
          "page": 1,
          "position": {
            "top": 100,
            "left": 50
          }
        }
      ],
      "timestamp": "2023-03-15T00:00:00Z"
    }
  ]
  ```

## Data Models

### Paper Models

- **PaperSubmission**: Model for submitting an arXiv paper
  - `arxiv_link`: URL to the arXiv paper

- **PaperResponse**: Complete paper model with all attributes
  - `id`: UUID of the paper
  - `arxiv_id`: arXiv identifier
  - `title`: Paper title
  - `authors`: List of author objects with names and affiliations
  - `abstract`: Paper abstract
  - `publication_date`: When the paper was published
  - `full_text`: Optional full text of the paper
  - `embedding_id`: Optional ID for vector embeddings
  - `related_papers`: Optional list of related papers
  - `tags`: Optional metadata tags (including processing status)
  - `summaries`: Optional paper summaries at different levels

- **PaperSummary**: Model for paper summaries at different levels
  - `beginner`: Simplified summary for beginners
  - `intermediate`: More detailed summary with some technical terms
  - `advanced`: Full technical summary

### Learning Models

- **LearningPath**: Model for structured learning paths
  - `id`: Path identifier
  - `paper_id`: ID of the associated paper
  - `title`: Path title
  - `description`: Path description
  - `items`: List of learning items
  - `created_at`: Creation timestamp
  - `estimated_time_minutes`: Estimated completion time

- **LearningItem**: Model for individual learning materials
  - `id`: Item identifier
  - `paper_id`: ID of the associated paper
  - `type`: Item type (text, video, flashcard, quiz)
  - `title`: Item title
  - `content`: Item content
  - `metadata`: Additional metadata
  - `difficulty_level`: Difficulty level (1-3)

- **CardItem**: Model for flashcard items
  - `front`: Text for the front of the card
  - `back`: Text for the back of the card

- **QuestionItem**: Model for quiz questions
  - `question`: Question text
  - `options`: List of possible answers
  - `correct_answer`: Index of the correct answer
  - `explanation`: Optional explanation of the correct answer

- **UserProgressRecord**: Model for tracking user progress
  - `id`: Record identifier
  - `user_id`: ID of the user
  - `item_id`: ID of the learning item
  - `status`: Progress status
  - `time_spent_seconds`: Time spent on the item
  - `timestamp`: When the progress was recorded

### Chat Models

- **ChatRequest**: Model for chat requests
  - `query`: The user's question
  - `conversation_id`: Optional conversation ID for context
  - `include_sources`: Whether to include source quotes in the response

- **ChatResponse**: Model for chat responses
  - `conversation_id`: ID of the conversation
  - `response`: Response text
  - `sources`: Optional list of source quotes from the paper

- **MessageResponse**: Model for individual chat messages
  - `id`: Message identifier
  - `user_id`: ID of the user
  - `paper_id`: ID of the paper
  - `conversation_id`: ID of the conversation
  - `query`: User's question
  - `response`: System's response
  - `sources`: Optional list of source quotes
  - `timestamp`: When the message was created 