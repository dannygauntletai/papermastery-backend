import os
import json
import datetime
from typing import Dict, Any, Optional
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def log_api_call(
    service_name: str,
    operation: str,
    request_data: Dict[str, Any],
    response_data: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    status_code: Optional[int] = None
) -> str:
    """
    Log API call details to a file for debugging purposes.
    
    Args:
        service_name: Name of the external service (e.g., 'firecrawl', 'rocketreach')
        operation: Type of operation performed (e.g., 'extract', 'lookup')
        request_data: Dictionary containing the request parameters
        response_data: Optional dictionary containing the response data
        error: Optional error message if the call failed
        status_code: Optional HTTP status code of the response
        
    Returns:
        Path to the log file
    """
    try:
        # Create logs directory if it doesn't exist
        log_dir = Path("logs/api_calls")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate timestamp for the filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        
        # Construct filename with service name, operation and timestamp
        filename = f"{service_name}_{operation}_{timestamp}.json"
        file_path = log_dir / filename
        
        # Prepare log data
        log_data = {
            "timestamp": datetime.datetime.now().isoformat(),
            "service": service_name,
            "operation": operation,
            "request": request_data,
            "status_code": status_code,
            "success": error is None and (status_code is None or (200 <= status_code < 300))
        }
        
        # Add response or error based on what happened
        if error:
            log_data["error"] = error
        if response_data:
            log_data["response"] = response_data
            
        # Write to file
        with open(file_path, 'w') as f:
            json.dump(log_data, f, indent=2, default=str)
            
        logger.info(f"API call logged to {file_path}")
        return str(file_path)
        
    except Exception as e:
        logger.error(f"Failed to log API call: {str(e)}")
        return "" 