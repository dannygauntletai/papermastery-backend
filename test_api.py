import requests
import json
import subprocess
from pprint import pprint

BASE_URL = "http://localhost:8001"

def run_curl_request(url, method="GET", data=None):
    """Run a curl request directly from the command line"""
    cmd = ["curl", "-s"]
    
    if method == "POST":
        cmd.extend(["-X", "POST"])
        if data:
            cmd.extend(["-H", "Content-Type: application/json", 
                       "-d", json.dumps(data)])
    
    cmd.append(url)
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error executing curl: {e}")
        print(f"Stderr: {e.stderr}")
        return None

def test_health():
    print("\n=== Testing Health Endpoint with curl ===")
    response = run_curl_request(f"{BASE_URL}/health")
    try:
        pprint(json.loads(response))
        return True
    except Exception as e:
        print(f"Error: {e}")
        print(f"Response: {response}")
        return False

def test_root():
    print("\n=== Testing Root Endpoint with curl ===")
    response = run_curl_request(f"{BASE_URL}/")
    try:
        pprint(json.loads(response))
        return True
    except Exception as e:
        print(f"Error: {e}")
        print(f"Response: {response}")
        return False

def test_list_papers():
    print("\n=== Testing List Papers Endpoint with curl ===")
    response = run_curl_request(f"{BASE_URL}/api/v1/papers/")
    try:
        pprint(json.loads(response))
        return True
    except Exception as e:
        print(f"Error: {e}")
        print(f"Response: {response}")
        return False

def test_submit_paper():
    print("\n=== Testing Submit Paper Endpoint with curl ===")
    data = {"arxiv_link": "https://arxiv.org/abs/1912.10389"}
    response = run_curl_request(
        f"{BASE_URL}/api/v1/papers/submit", 
        method="POST",
        data=data
    )
    try:
        pprint(json.loads(response))
        return True
    except Exception as e:
        print(f"Error: {e}")
        print(f"Response: {response}")
        return False

def test_with_args_kwargs():
    """Test with args and kwargs parameters to see if they're required"""
    print("\n=== Testing with args and kwargs parameters ===")
    response = run_curl_request(f"{BASE_URL}/api/v1/papers/?args=&kwargs=")
    try:
        pprint(json.loads(response))
        return True
    except Exception as e:
        print(f"Error: {e}")
        print(f"Response: {response}")
        return False

if __name__ == "__main__":
    print("Starting API Tests with Curl")
    test_health()
    test_root()
    test_list_papers()
    test_submit_paper()
    test_with_args_kwargs()
    print("\nAPI Tests Complete") 