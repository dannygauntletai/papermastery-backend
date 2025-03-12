"""
Test script to verify that messages are properly saved to the database.

This script:
1. Submits a paper for processing
2. Sends a chat message
3. Verifies that the message is saved to the database
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

# Test chat message
TEST_CHAT_MESSAGE = "What is the main contribution of this paper?"


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


async def send_chat_message(paper_id):
    """Send a chat message for the paper and return the response."""
    async with httpx.AsyncClient() as client:
        # Set up headers with authentication
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.getenv('TEST_AUTH_TOKEN')}"  # Replace with a valid auth token
        }
        
        # Send the chat message
        response = await client.post(
            f"{API_BASE_URL}/papers/{paper_id}/chat",
            headers=headers,
            json={"query": TEST_CHAT_MESSAGE}
        )
        
        if response.status_code != 200:
            print(f"Error sending chat message: {response.text}")
            return None
        
        chat_response = response.json()
        print(f"Chat response received: {chat_response.get('response')[:100]}...")
        return chat_response


async def verify_messages_in_database(paper_id):
    """Verify that messages are saved in the database."""
    # Query the messages table for messages related to the paper
    response = supabase.table("messages").select("*").eq("paper_id", paper_id).execute()
    
    messages = response.data
    print(f"Found {len(messages)} messages in the database for paper {paper_id}")
    
    # Check if we have both user and bot messages
    user_messages = [m for m in messages if m.get("sender") == "user"]
    bot_messages = [m for m in messages if m.get("sender") == "bot"]
    
    print(f"User messages: {len(user_messages)}")
    print(f"Bot messages: {len(bot_messages)}")
    
    # Verify that the messages contain the expected text
    for message in user_messages:
        if message.get("text") == TEST_CHAT_MESSAGE:
            print("✅ Found user message with expected text")
            break
    else:
        print("❌ User message with expected text not found")
    
    # Verify that the conversation exists
    conversation_response = supabase.table("user_conversations").select("*").eq("id", paper_id).execute()
    conversations = conversation_response.data
    
    if conversations:
        print(f"✅ Found conversation with ID {paper_id}")
    else:
        print(f"❌ Conversation with ID {paper_id} not found")
    
    return len(user_messages) > 0 and len(bot_messages) > 0


async def main():
    """Run the test."""
    # Submit a paper
    paper_id = await submit_paper()
    if not paper_id:
        print("Failed to submit paper. Exiting.")
        return
    
    # Wait for the paper to be processed
    print("Waiting for paper to be processed...")
    await asyncio.sleep(10)  # Adjust this based on how long processing typically takes
    
    # Send a chat message
    chat_response = await send_chat_message(paper_id)
    if not chat_response:
        print("Failed to send chat message. Exiting.")
        return
    
    # Verify that messages are saved in the database
    success = await verify_messages_in_database(paper_id)
    
    if success:
        print("✅ Test passed: Messages are properly saved to the database")
    else:
        print("❌ Test failed: Messages are not properly saved to the database")


if __name__ == "__main__":
    asyncio.run(main()) 