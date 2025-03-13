"""
Test script to verify the Gemini chat functionality.

This script:
1. Submits a paper for processing
2. Waits for the paper to be processed
3. Sends a chat message to the paper
4. Verifies that a response is received
"""

import asyncio
import httpx
import json
import os
import pytest
from typing import Dict, Any, Optional
from uuid import UUID
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# Configuration from environment variables
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
USER_ID = os.getenv("TEST_USER_ID", "your-test-user-id")
ARXIV_LINK = os.getenv("TEST_ARXIV_LINK", "https://arxiv.org/abs/2106.09685")
AUTH_TOKEN = os.getenv("TEST_AUTH_TOKEN", "")
MAX_WAIT_TIME = int(os.getenv("TEST_MAX_WAIT_TIME", "60"))

@pytest.mark.asyncio
async def test_gemini_chat_flow():
    """Test the complete flow of submitting a paper and chatting with it."""
    # Skip test if no auth token provided
    if not AUTH_TOKEN:
        pytest.skip("No auth token provided in environment variables")
    
    # Submit paper
    paper_id = await submit_paper()
    assert paper_id is not None
    
    # Wait for processing
    paper_processed = await wait_for_paper_processing(paper_id)
    assert paper_processed
    
    # Send chat message
    query = "What is the main contribution of this paper?"
    chat_response = await send_chat_message(paper_id, query)
    assert chat_response is not None
    assert "content" in chat_response
    assert len(chat_response["content"]) > 0

async def submit_paper() -> Optional[str]:
    """Submit a paper for processing and return the paper ID."""
    async with httpx.AsyncClient() as client:
        # Set up headers with authentication
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AUTH_TOKEN}"
        }
        
        # Submit the paper
        response = await client.post(
            f"{BASE_URL}/papers/submit",
            headers=headers,
            json={"arxiv_link": ARXIV_LINK}
        )
        
        if response.status_code != 200:
            return None
        
        # Extract the paper ID from the response
        data = response.json()
        return data.get("id")

async def wait_for_paper_processing(paper_id: str, max_wait_time: int = MAX_WAIT_TIME) -> bool:
    """Wait for the paper to be processed."""
    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"Bearer {AUTH_TOKEN}"
        }
        
        start_time = time.time()
        while time.time() - start_time < max_wait_time:
            # Check paper status
            response = await client.get(
                f"{BASE_URL}/papers/{paper_id}",
                headers=headers
            )
            
            if response.status_code != 200:
                return False
            
            data = response.json()
            status = data.get("status")
            
            if status == "completed":
                return True
            
            # Wait before checking again
            await asyncio.sleep(5)
        
        return False

async def send_chat_message(paper_id: str, query: str) -> Optional[Dict[str, Any]]:
    """Send a chat message to the paper and return the response."""
    async with httpx.AsyncClient() as client:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AUTH_TOKEN}"
        }
        
        # Send the chat message
        response = await client.post(
            f"{BASE_URL}/chat/papers/{paper_id}/messages",
            headers=headers,
            json={
                "content": query,
                "user_id": USER_ID
            }
        )
        
        if response.status_code != 200:
            return None
        
        return response.json()

if __name__ == "__main__":
    asyncio.run(pytest.main(["-xvs", __file__])) 