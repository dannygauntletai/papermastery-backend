#!/usr/bin/env python
"""
Test script for the simplified researcher collection endpoint.
This script makes a request to the researcher endpoint and verifies the minimal response.
"""

import asyncio
import httpx
import json
from datetime import datetime
import os
import time

# The API endpoint
API_URL = "http://localhost:8000/api/v1/consulting/researchers/collect"

# Test researcher data
test_data = {
    "name": "Geoffrey Hinton",
    "affiliation": "University of Toronto",
    "paper_title": "Learning representations by back-propagating errors",
    "position": "Professor",
    "email": "hinton@cs.toronto.edu"  # Include email to test existing researcher check
}

async def test_simplified_endpoint():
    """Test the simplified researcher collection endpoint."""
    print(f"Testing simplified researcher endpoint at {API_URL}")
    print(f"Request data: {json.dumps(test_data, indent=2)}")
    
    async with httpx.AsyncClient() as client:
        start_time = datetime.now()
        print(f"Request started at: {start_time.isoformat()}")
        
        try:
            response = await client.post(API_URL, json=test_data)
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            print(f"Request completed in {duration:.2f} seconds")
            print(f"Status code: {response.status_code}")
            
            # Pretty print the response
            response_json = response.json()
            print("Response:")
            print(json.dumps(response_json, indent=2))
            
            # Verify the simplified response structure
            if "data" in response_json and "status" in response_json["data"]:
                status = response_json["data"]["status"]
                researcher_id = response_json["data"].get("researcher_id")
                
                print(f"\nStatus: {status}")
                print(f"Researcher ID: {researcher_id or 'Not found yet'}")
                
                if status == "processing":
                    print("\nBackground processing started successfully.")
                    print("To see the full researcher data, subscribe to Supabase realtime updates.")
            else:
                print("\nUnexpected response format!")
            
        except Exception as e:
            print(f"Error: {str(e)}")
    
if __name__ == "__main__":
    asyncio.run(test_simplified_endpoint()) 