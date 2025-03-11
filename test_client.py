from fastapi.testclient import TestClient
import json
import pprint
import uuid
from app.main import app

# Initialize test client
client = TestClient(app)

# Store paper_id for use across tests
test_paper_id = None

def test_health():
    """Test the health endpoint"""
    print("\n=== Testing Health Endpoint ===")
    try:
        response = client.get("/health")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {response.json()}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {str(e)}")

def test_root():
    """Test the root endpoint"""
    print("\n=== Testing Root Endpoint ===")
    try:
        response = client.get("/?args=&kwargs=")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {response.json()}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {str(e)}")

def test_list_papers():
    """Test the list papers endpoint"""
    print("\n=== Testing List Papers Endpoint ===")
    try:
        response = client.get("/api/v1/papers/?args=&kwargs=")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            papers = response.json()
            print(f"Found {len(papers)} papers")
            if papers:
                print("First paper:")
                pprint.pprint(papers[0])
                # Store the first paper's ID for other tests
                global test_paper_id
                test_paper_id = papers[0]['id']
                print(f"Using paper ID {test_paper_id} for further tests")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {str(e)}")

def test_submit_paper():
    """Test the submit paper endpoint"""
    print("\n=== Testing Submit Paper Endpoint ===")
    try:
        # Use a sample arXiv paper
        data = {
            "arxiv_link": "https://arxiv.org/abs/2003.08271"
        }
        
        response = client.post("/api/v1/papers/submit?args=&kwargs=", json=data)
        print(f"Status: {response.status_code}")
        if response.status_code == 202:  # Accepted
            paper_data = response.json()
            print("Paper submission successful")
            print(f"Paper ID: {paper_data['id']}")
            print(f"Title: {paper_data['title']}")
            
            # Store the paper ID for other tests
            global test_paper_id
            test_paper_id = paper_data['id']
            print(f"Using paper ID {test_paper_id} for further tests")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {str(e)}")

def test_get_paper():
    """Test the get paper endpoint"""
    print("\n=== Testing Get Paper Endpoint ===")
    global test_paper_id
    
    if not test_paper_id:
        print("No paper ID available, skipping test")
        return
    
    try:
        response = client.get(f"/api/v1/papers/{test_paper_id}?args=&kwargs=")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            paper = response.json()
            print(f"Paper ID: {paper['id']}")
            print(f"Title: {paper['title']}")
            print(f"Authors: {[author['name'] for author in paper['authors']]}")
            print(f"Status: {paper['tags']['status'] if paper['tags'] else 'No status'}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {str(e)}")

def test_get_paper_summaries():
    """Test the get paper summaries endpoint"""
    print("\n=== Testing Get Paper Summaries Endpoint ===")
    global test_paper_id
    
    if not test_paper_id:
        print("No paper ID available, skipping test")
        return
    
    try:
        response = client.get(f"/api/v1/papers/{test_paper_id}/summaries?args=&kwargs=")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            summaries = response.json()
            print("Paper summaries retrieved successfully")
            print(f"Beginner summary length: {len(summaries['beginner']) if 'beginner' in summaries else 'N/A'}")
            print(f"Intermediate summary length: {len(summaries['intermediate']) if 'intermediate' in summaries else 'N/A'}")
            print(f"Advanced summary length: {len(summaries['advanced']) if 'advanced' in summaries else 'N/A'}")
        elif response.status_code == 404:
            print("Summaries not found or not yet generated")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {str(e)}")

def test_get_related_papers():
    """Test the get related papers endpoint"""
    print("\n=== Testing Get Related Papers Endpoint ===")
    global test_paper_id
    
    if not test_paper_id:
        print("No paper ID available, skipping test")
        return
    
    try:
        response = client.get(f"/api/v1/papers/{test_paper_id}/related?args=&kwargs=")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            related_papers = response.json()
            print(f"Found {len(related_papers)} related papers")
            if related_papers:
                print("First related paper:")
                pprint.pprint(related_papers[0])
        elif response.status_code == 404:
            print("Related papers not found or not yet generated")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {str(e)}")

def test_nonexistent_paper():
    """Test endpoints with non-existent paper ID"""
    print("\n=== Testing Endpoints with Non-existent Paper ID ===")
    fake_id = str(uuid.uuid4())
    
    try:
        # Test get paper with non-existent ID
        response = client.get(f"/api/v1/papers/{fake_id}?args=&kwargs=")
        print(f"Get paper - Status: {response.status_code} (expected 404)")
        
        # Test get summaries with non-existent ID
        response = client.get(f"/api/v1/papers/{fake_id}/summaries?args=&kwargs=")
        print(f"Get summaries - Status: {response.status_code} (expected 404)")
        
        # Test get related papers with non-existent ID
        response = client.get(f"/api/v1/papers/{fake_id}/related?args=&kwargs=")
        print(f"Get related papers - Status: {response.status_code} (expected 404)")
    except Exception as e:
        print(f"Exception: {str(e)}")

if __name__ == "__main__":
    print("\nStarting API tests...")
    
    # Run tests
    test_health()
    test_root() 
    test_list_papers()
    
    # If we don't have a paper ID from listing papers, try to submit a new one
    if not test_paper_id:
        test_submit_paper()
    
    # Test paper details endpoints
    test_get_paper()
    test_get_paper_summaries()
    test_get_related_papers()
    
    # Test error handling
    test_nonexistent_paper()
    
    print("\nAPI tests complete.") 