#!/bin/bash

# Create necessary directories
mkdir -p tests/unit tests/integration

# We already created refactored versions of these files, so we'll delete the originals:
rm test_flashcards.py
rm test_api_response.py
rm test_api.py
rm test_paper.py
rm test_gemini_chat.py
rm test_pinecone.py
rm test_client.py

# Move test_gemini_pdf_processing.py to tests/integration
mv test_gemini_pdf_processing.py tests/integration/

# Move test_message_storage.py to tests/unit
mv test_message_storage.py tests/unit/

# Move test_multiple_conversations.py to tests/integration
mv test_multiple_conversations.py tests/integration/

# Move summarization_test.py to tests/unit with the proper name
mv summarization_test.py tests/unit/test_summarization_extra.py

# Move test_openai.py to tests/unit
mv test_openai.py tests/unit/

# Move test_pdf_processing.py to tests/unit
mv test_pdf_processing.py tests/unit/

echo "All test files have been moved to their appropriate directories" 