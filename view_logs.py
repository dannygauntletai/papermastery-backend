#!/usr/bin/env python3
"""
A utility script to view the latest API logs.
Run with: python view_logs.py [service_name] [num_logs]

Examples:
- python view_logs.py  # View the latest 5 logs from any service
- python view_logs.py firecrawl  # View the latest 5 firecrawl logs
- python view_logs.py rocketreach 10  # View the latest 10 rocketreach logs
"""

import os
import glob
import json
import sys
from datetime import datetime
import argparse

def list_latest_logs(service_name=None, num_logs=5):
    """List the latest API call logs, optionally filtered by service."""
    log_dir = "logs/api_calls"
    
    # Create a glob pattern based on the service name
    if service_name:
        pattern = f"{log_dir}/{service_name}_*.json"
    else:
        pattern = f"{log_dir}/*.json"
    
    # Get all matching log files
    log_files = glob.glob(pattern)
    
    # Sort by modification time (newest first)
    log_files.sort(key=os.path.getmtime, reverse=True)
    
    # Limit to the specified number
    log_files = log_files[:num_logs]
    
    if not log_files:
        print(f"No logs found for {'service ' + service_name if service_name else 'any service'}")
        return

    # Display the logs
    for i, log_file in enumerate(log_files, 1):
        print(f"\n{'-' * 80}\nLOG {i}: {os.path.basename(log_file)}\n{'-' * 80}")
        
        try:
            with open(log_file, 'r') as f:
                log_data = json.load(f)
                
            # Format the timestamp
            if 'timestamp' in log_data:
                try:
                    timestamp = datetime.fromisoformat(log_data['timestamp'])
                    log_data['timestamp'] = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass  # Keep the original timestamp if formatting fails
            
            # Extract basic info for the header
            service = log_data.get('service', 'unknown')
            operation = log_data.get('operation', 'unknown')
            success = log_data.get('success', False)
            status = "✅ SUCCESS" if success else "❌ ERROR"
            
            print(f"Service: {service}")
            print(f"Operation: {operation}")
            print(f"Status: {status}")
            print(f"Time: {log_data.get('timestamp', 'unknown')}")
            
            # Show error message prominently if there is one
            if 'error' in log_data:
                print(f"\nERROR: {log_data['error']}")
            
            # Print request data
            if 'request' in log_data:
                print("\nREQUEST DATA:")
                print(json.dumps(log_data['request'], indent=2))
            
            # Print response data (shortened if it's very large)
            if 'response' in log_data:
                print("\nRESPONSE DATA:")
                response_str = json.dumps(log_data['response'], indent=2)
                # If response is very large, truncate it
                if len(response_str) > 2000:
                    print(response_str[:2000] + "... [truncated]")
                else:
                    print(response_str)
                    
        except Exception as e:
            print(f"Error reading log file {log_file}: {e}")

def main():
    parser = argparse.ArgumentParser(description="View recent API logs")
    parser.add_argument("service", nargs="?", help="Service name to filter logs (e.g., firecrawl, rocketreach)")
    parser.add_argument("num_logs", nargs="?", type=int, default=5, help="Number of logs to display (default: 5)")
    
    args = parser.parse_args()
    
    list_latest_logs(args.service, args.num_logs)

if __name__ == "__main__":
    main() 