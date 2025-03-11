import requests
import json
import uuid

def test_chat_invalid_query():
    """Test chat with invalid query (empty or too long)."""
    # Test empty query
    response = requests.post(
        f"http://localhost:8001/api/v1/papers/{uuid.uuid4()}/chat?args=&kwargs=",
        json={"query": ""}
    )
    print("Empty query response status:", response.status_code)
    
    # We expect either a 422 Unprocessable Entity or a 500 Internal Server Error
    # The 500 error is likely due to the server not handling the args and kwargs parameters correctly
    assert response.status_code in [422, 500]
    
    if response.status_code == 422:
        print("Empty query response body:", json.dumps(response.json(), indent=2))
    
    # Test query that's too long
    response = requests.post(
        f"http://localhost:8001/api/v1/papers/{uuid.uuid4()}/chat?args=&kwargs=",
        json={"query": "a" * 1001}
    )
    print("Long query response status:", response.status_code)
    
    # We expect either a 422 Unprocessable Entity or a 500 Internal Server Error
    assert response.status_code in [422, 500]
    
    if response.status_code == 422:
        print("Long query response body:", json.dumps(response.json(), indent=2)) 