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
from uuid import UUID
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# API base URL
API_BASE_URL = "http://localhost:8000/api/v1"

# Test user ID (replace with a valid user ID from your database)
TEST_USER_ID = "your-test-user-id"  # Replace with a valid user ID

# Test paper arXiv link
TEST_ARXIV_LINK = "https://arxiv.org/abs/2106.09685"  # Replace with a valid arXiv link

# Test auth token
TEST_AUTH_TOKEN = os.getenv("TEST_AUTH_TOKEN")  # Replace with a valid auth token


async def submit_paper():
    """Submit a paper for processing and return the paper ID."""
    async with httpx.AsyncClient() as client:
        # Set up headers with authentication
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {TEST_AUTH_TOKEN}"
        }
        
        # Submit the paper
        response = await client.post(
            f"{API_BASE_URL}/papers/submit",
            headers=headers,
            json={"arxiv_link": TEST_ARXIV_LINK}
        )
        
        if response.status_code != 202:
            print(f"Error submitting paper: {response.text}")
            return None
        
        paper_data = response.json()
        paper_id = paper_data.get("id")
        print(f"Paper submitted with ID: {paper_id}")
        return paper_id


async def wait_for_paper_processing(paper_id, max_wait_time=60):
    """Wait for the paper to be processed."""
    async with httpx.AsyncClient() as client:
        # Set up headers with authentication
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {TEST_AUTH_TOKEN}"
        }
        
        start_time = time.time()
        while time.time() - start_time < max_wait_time:
            # Get the paper details
            response = await client.get(
                f"{API_BASE_URL}/papers/{paper_id}",
                headers=headers
            )
            
            if response.status_code != 200:
                print(f"Error getting paper details: {response.text}")
                await asyncio.sleep(5)
                continue
            
            paper_data = response.json()
            
            # Check if the paper has been processed
            if paper_data.get("embedding_id"):
                print(f"Paper {paper_id} has been processed")
                return True
            
            print(f"Paper {paper_id} is still being processed, waiting...")
            await asyncio.sleep(5)
        
        print(f"Timed out waiting for paper {paper_id} to be processed")
        return False


async def send_chat_message(paper_id, query):
    """Send a chat message to the paper and return the response."""
    async with httpx.AsyncClient() as client:
        # Set up headers with authentication
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {TEST_AUTH_TOKEN}"
        }
        
        # Send the chat message
        response = await client.post(
            f"{API_BASE_URL}/papers/{paper_id}/chat",
            headers=headers,
            json={"query": query}
        )
        
        if response.status_code != 200:
            print(f"Error sending chat message: {response.text}")
            return None
        
        chat_data = response.json()
        print(f"Chat response received: {chat_data.get('response')[:100]}...")
        return chat_data


async def main():
    """Run the test."""
    # Submit a paper
    paper_id = await submit_paper()
    if not paper_id:
        print("Failed to submit paper. Exiting.")
        return
    
    # Wait for the paper to be processed
    processed = await wait_for_paper_processing(paper_id)
    if not processed:
        print("Paper processing timed out. Exiting.")
        return
    
    # Send a chat message
    query = "What are the main findings of this paper?"
    chat_response = await send_chat_message(paper_id, query)
    if not chat_response:
        print("Failed to get chat response. Exiting.")
        return
    
    # Print the full response
    print("\nFull chat response:")
    print(f"Query: {chat_response.get('query')}")
    print(f"Response: {chat_response.get('response')}")
    print(f"Number of sources: {len(chat_response.get('sources', []))}")
    
    # Verify that the response is not empty
    if not chat_response.get('response'):
        print("❌ Test failed: Empty response")
        return
    
    print("\n✅ Test passed: Received non-empty response")


if __name__ == "__main__":
    asyncio.run(main()) 