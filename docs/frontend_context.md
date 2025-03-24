# Paper Highlight API Endpoints Documentation

## Overview
We've added new endpoints to support text highlighting, summarization, and explanation features within research papers. These endpoints allow frontend users to highlight text in papers, request AI-generated summaries and explanations of highlighted text.

## API Endpoints

### 1. Text Summarization Endpoint

**Endpoint:** `POST /api/v1/papers/{paper_id}/summarize`

**Purpose:** Generate a concise summary of highlighted text from a paper.

**Request Parameters:**
- `paper_id`: UUID - The ID of the paper containing the highlighted text (path parameter)

**Request Body:**
```json
{
  "text": "The highlighted text from the paper that needs to be summarized"
}
```

**Response Format:**
```json
{
  "summary": "A concise summary of the highlighted text"
}
```

**Notes:**
- The summary is approximately 30-50% the length of the original text
- Captures key points while eliminating redundant information
- Uses clear language while maintaining technical accuracy
- Responses are cached to improve performance on repeated requests for the same text
- Requires authentication
- The API uses the paper title as context but doesn't send the full paper text with each request
- Summaries are now stored in the messages table and can be retrieved via the messages endpoint

### 2. Text Explanation Endpoint

**Endpoint:** `POST /api/v1/papers/{paper_id}/explain`

**Purpose:** Generate a detailed explanation of highlighted text from a paper.

**Request Parameters:**
- `paper_id`: UUID - The ID of the paper containing the highlighted text (path parameter)

**Request Body:**
```json
{
  "text": "The highlighted text from the paper that needs to be explained"
}
```

**Response Format:**
```json
{
  "explanation": "A detailed explanation of the highlighted text"
}
```

**Notes:**
- Breaks down complex concepts into understandable components
- Defines technical terms and jargon
- Provides context for how the text fits into the broader research
- Uses examples or analogies where appropriate
- Responses are cached to improve performance on repeated requests for the same text
- Requires authentication
- The API uses the paper title as context but doesn't send the full paper text with each request
- Explanations are now stored in the messages table and can be retrieved via the messages endpoint

### 3. Persistent Highlight Management Endpoints

We've also added endpoints for managing persistent highlights (for future reference):

- **Create Highlight**: `POST /api/v1/papers/{paper_id}/highlights`
- **Get Paper Highlights**: `GET /api/v1/papers/{paper_id}/highlights`
- **Get Specific Highlight**: `GET /api/v1/papers/{paper_id}/highlights/{highlight_id}`
- **Update Highlight**: `PUT /api/v1/papers/{paper_id}/highlights/{highlight_id}`

## Implementation Details

- Both endpoints use AI-powered text generation to create summaries and explanations
- Text preprocessing is performed to clean input before generating content
- Custom prompt templates are used to guide the AI in producing appropriate responses
- Error handling is implemented for invalid paper IDs, empty text, or service failures
- Asynchronous processing is used for optimal performance

## Differences from Chat Functionality

The highlight summarize/explain endpoints differ from the existing chat functionality in these key ways:

1. **Context Usage**: While the chat endpoint sends the full paper text as context, the highlight endpoints only use the paper title and the highlighted text provided in the request.

2. **Response Storage**: Highlight operations (summaries and explanations) are now stored in the messages table:
   - They're still cached in memory for performance
   - They're saved with special fields: `highlighted_text` and `highlight_type`
   - They can be retrieved using the existing `/papers/{paper_id}/messages` endpoint
   - Frontend can filter messages by highlight_type ("summary" or "explanation")

3. **Response Format**: Chat responses include sources from the paper, while summarize/explain endpoints return only the generated content without source references.

## Frontend Implementation Guidance

When implementing in the frontend:

1. For transient highlight operations:
   - Use the `/papers/{paper_id}/summarize` and `/papers/{paper_id}/explain` endpoints
   - Display the response directly to the user
   - No need to fetch updated data after the request

2. For persistent highlights:
   - First create a highlight using the `/papers/{paper_id}/highlights` endpoint
   - Then use the highlight management endpoints to request and retrieve summaries/explanations

3. For retrieving highlight history:
   - Use the existing `/papers/{paper_id}/messages` endpoint
   - Filter the messages client-side by highlight_type:
   
   ```javascript
   // Example frontend code
   const messages = await fetchMessages(paperId);
   
   // Filter for highlight operations
   const summaries = messages.filter(msg => msg.highlight_type === 'summary');
   const explanations = messages.filter(msg => msg.highlight_type === 'explanation');
   
   // Access the highlighted text that was summarized or explained
   const highlightedText = msg.highlighted_text;
   
   // Display in the appropriate UI component
   displayHighlightHistory(summaries, explanations);
   ```

This implementation follows the backend plan outlined in our development roadmap, supporting the frontend's ability to capture highlighted text and display AI-generated summaries and explanations.
