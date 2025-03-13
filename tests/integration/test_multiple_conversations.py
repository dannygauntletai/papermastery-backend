"""
Test script to verify the multiple conversations support.

This script:
1. Submits a paper for processing
2. Creates multiple conversations for the paper
3. Fetches all conversations for the paper
"""

import asyncio
import httpx
import json
import os
from uuid import UUID
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# API base URL
API_BASE_URL = "http://localhost:8000/api/v1"

# Test user ID (replace with a valid user ID from your database)
TEST_USER_ID = "your-test-user-id"  # Replace with a valid user ID

# Test paper arXiv link
TEST_ARXIV_LINK = "https://arxiv.org/abs/2106.09685"  # Replace with a valid arXiv link


async def submit_paper():
    """Submit a paper for processing and return the paper ID."""
    async with httpx.AsyncClient() as client:
        # Set up headers with authentication
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.getenv('TEST_AUTH_TOKEN')}"  # Replace with a valid auth token
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


async def create_additional_conversation(paper_id):
    """Create an additional conversation for the paper."""
    # This would normally be done through an API endpoint, but for testing purposes,
    # we'll use the Supabase client directly
    try:
        conversation_data = {
            "id": str(UUID(int=int.from_bytes(os.urandom(16), byteorder="big"))),  # Generate a random UUID
            "user_id": TEST_USER_ID,
            "paper_id": paper_id
        }
        
        response = supabase.table("user_conversations").insert(conversation_data).execute()
        
        if len(response.data) == 0:
            print("Failed to create conversation: No data returned")
            return None
            
        conversation_id = response.data[0]["id"]
        print(f"Created additional conversation with ID: {conversation_id}")
        return conversation_id
    except Exception as e:
        print(f"Error creating conversation: {str(e)}")
        return None


async def get_paper_conversations(paper_id):
    """Fetch all conversations for the paper."""
    async with httpx.AsyncClient() as client:
        # Set up headers with authentication
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.getenv('TEST_AUTH_TOKEN')}"  # Replace with a valid auth token
        }
        
        # Get conversations
        response = await client.get(
            f"{API_BASE_URL}/papers/{paper_id}/conversations",
            headers=headers
        )
        
        if response.status_code != 200:
            print(f"Error fetching conversations: {response.text}")
            return None
        
        conversations = response.json()
        print(f"Retrieved {len(conversations)} conversations for paper {paper_id}")
        return conversations


async def main():
    """Run the test."""
    # Submit a paper
    paper_id = await submit_paper()
    if not paper_id:
        print("Failed to submit paper. Exiting.")
        return
    
    # Wait for the paper to be processed
    print("Waiting for paper to be processed...")
    await asyncio.sleep(5)  # Adjust this based on how long processing typically takes
    
    # Create additional conversations
    for i in range(2):
        await create_additional_conversation(paper_id)
    
    # Fetch all conversations
    conversations = await get_paper_conversations(paper_id)
    if not conversations:
        print("Failed to fetch conversations. Exiting.")
        return
    
    # Print conversation details
    print("\nConversation details:")
    for i, conversation in enumerate(conversations):
        print(f"Conversation {i+1}:")
        print(f"  ID: {conversation.get('id')}")
        print(f"  Paper ID: {conversation.get('paper_id')}")
        print(f"  User ID: {conversation.get('user_id')}")
        print(f"  Created at: {conversation.get('created_at')}")
    
    # Verify that all conversations have the correct paper_id
    all_valid = all(conversation.get("paper_id") == paper_id for conversation in conversations)
    
    if all_valid:
        print("\n✅ Test passed: All conversations have the correct paper_id")
    else:
        print("\n❌ Test failed: Some conversations have incorrect paper_id")


if __name__ == "__main__":
    asyncio.run(main()) 