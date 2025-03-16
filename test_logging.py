import json
import os
import glob
from app.utils.api_logging import log_api_call

def test_logging():
    # Test the log_api_call function
    log_api_call(
        service_name="test", 
        operation="test_operation", 
        request_data={"test": "data"}, 
        response_data={"result": "success"}, 
        error=None, 
        status_code=200
    )
    
    print("Test log created successfully")
    
    # Find the most recent log file
    log_files = glob.glob("logs/api_calls/test_test_operation_*.json")
    if log_files:
        latest_log = max(log_files, key=os.path.getctime)
        
        # Print the content of the log file
        print(f"Log file: {latest_log}")
        print("Log content:")
        with open(latest_log) as f:
            log_data = json.loads(f.read())
            print(json.dumps(log_data, indent=2))
    else:
        print("No log file found!")

if __name__ == "__main__":
    test_logging() 