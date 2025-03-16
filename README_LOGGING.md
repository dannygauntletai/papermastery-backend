# API Call Logging System

This document describes the logging system implemented for external API calls in the PaperMastery backend.

## Overview

The logging system captures detailed information about API calls to external services (Firecrawl, RocketReach, etc.) to help with debugging and troubleshooting. Each API call is logged to a JSON file with a timestamp, making it easy to trace issues when they occur.

## Implementation Details

### Core Components

1. **Logging Utility**: `app/utils/api_logging.py`
   - Contains the `log_api_call` function that handles writing API call details to files
   - Creates structured JSON logs with timestamps, request data, response data, and errors

2. **Log Directory**: `logs/api_calls/`
   - Stores all API call logs in JSON format
   - Files are named with the pattern: `{service_name}_{operation}_{timestamp}.json`

3. **Service Integration**:
   - `app/services/firecrawl_service.py` - Logs all interactions with the Firecrawl API
   - `app/services/rocketreach_service.py` - Logs all interactions with the RocketReach API
   - `app/services/data_collection_orchestrator.py` - Logs the orchestration process

4. **Log Viewing Utility**: `view_logs.py`
   - Command-line tool to easily view and filter the most recent logs

## Log Structure

Each log file contains a JSON object with the following structure:

```json
{
  "timestamp": "2023-06-15T12:34:56.789012",
  "service": "firecrawl",
  "operation": "extract",
  "request": {
    // Request parameters
  },
  "status_code": 200,
  "success": true,
  "response": {
    // Response data (if successful)
  },
  // OR
  "error": "Error message" // (if failed)
}
```

## Usage

### Logging API Calls

To log an API call in your code:

```python
from app.utils.api_logging import log_api_call

# Log a successful API call
log_api_call(
    service_name="service_name",
    operation="operation_name",
    request_data={"param1": "value1"},
    response_data={"result": "success"},
    status_code=200
)

# Log a failed API call
log_api_call(
    service_name="service_name",
    operation="operation_name",
    request_data={"param1": "value1"},
    error="Error message",
    status_code=400
)
```

### Viewing Logs

Use the `view_logs.py` utility to view recent logs:

```bash
# View the 5 most recent logs from any service
python view_logs.py

# View the 5 most recent logs from a specific service
python view_logs.py firecrawl

# View a specific number of logs from a service
python view_logs.py rocketreach 10
```

## Troubleshooting

If you encounter issues with external services, check the logs in the `logs/api_calls/` directory. The logs contain detailed information about the request parameters, response data, and any errors that occurred.

Common issues that can be diagnosed using the logs:

1. Authentication failures (401 errors)
2. Rate limiting (429 errors)
3. Invalid request parameters (400 errors)
4. Service unavailability (500+ errors)

## Maintenance

The logging system creates files for each API call. To prevent disk space issues:

1. Periodically archive or delete old log files
2. Consider implementing log rotation for production environments
3. Monitor the size of the `logs/api_calls/` directory

## Future Improvements

Potential enhancements to the logging system:

1. Implement log rotation to automatically manage log file growth
2. Add a web-based log viewer for easier analysis
3. Integrate with monitoring systems for alerting on API failures
4. Add analytics to track API performance and reliability over time 