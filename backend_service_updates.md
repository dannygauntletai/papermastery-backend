# Backend Service Updates

Based on the logs analysis, the following updates should be made to the backend services:

## 1. Update Firecrawl Service

The logs show that Firecrawl API endpoints are returning 404 errors. Update `app/services/firecrawl_service.py`:

```python
# Update API endpoints
# From
FIRECRAWL_EXTRACT_URL = "https://api.firecrawl.dev/extract"
FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/scrape"

# To (check with Firecrawl documentation for the correct endpoints)
FIRECRAWL_EXTRACT_URL = "https://api.firecrawl.dev/v1/extract"  # Adjust based on current API docs
FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v1/scrape"    # Adjust based on current API docs
```

## 2. Remove Google Scholar from Firecrawl Searches

Remove Google Scholar URLs from search targets:

```python
# Update in app/services/firecrawl_service.py

# Remove or comment out Google Scholar URLs
# Before:
urls_to_try = [
    f"https://scholar.google.com/scholar?q={encoded_search_query}",
    f"https://www.google.com/search?q={encoded_name}+{encoded_affiliation}+profile",
    f"https://www.google.com/search?q={encoded_name}+{paper_title_encoded}"
]

# After:
urls_to_try = [
    # Remove Google Scholar which seems problematic
    # f"https://scholar.google.com/scholar?q={encoded_search_query}",
    f"https://www.google.com/search?q={encoded_name}+{encoded_affiliation}+profile",
    f"https://www.google.com/search?q={encoded_name}+{paper_title_encoded}"
]
```

## 3. Fix RocketReach API Method

RocketReach API doesn't accept POST requests:

```python
# Update in app/services/rocketreach_service.py

# Change from:
async with httpx.AsyncClient(timeout=60.0) as client:
    response = await client.post(
        ROCKETREACH_LOOKUP_URL,
        headers=headers,
        json=request_data
    )

# To:
async with httpx.AsyncClient(timeout=60.0) as client:
    response = await client.get(
        ROCKETREACH_LOOKUP_URL,
        headers=headers,
        params=request_data  # Change json to params for GET request
    )
```

## 4. Handle Tavily API Query Length Limitation

Add a check to limit query length to 400 characters:

```python
# Update in app/services/tavily_service.py

# Add query length checking
def trim_query(query, max_length=400):
    """Trim query to max_length characters if necessary."""
    if len(query) > max_length:
        return query[:max_length]
    return query

# Then use this function before API calls
search_query = trim_query(search_query)
```

## 5. Update Data Collection Orchestrator

Make affiliation optional in the researcher data collection function:

```python
# Update in app/services/data_collection_orchestrator.py

# Change parameter definition to make affiliation optional
async def collect_researcher_data(
    name: str,
    affiliation: Optional[str] = None,  # Make optional
    paper_title: Optional[str] = None,
    position: Optional[str] = None,
    email: Optional[str] = None,
    researcher_id: Optional[str] = None,
    run_in_background: bool = False
) -> Dict[str, Any]:
    # Update logic to handle missing affiliation
    if affiliation:
        search_query = f"{name} {affiliation}"
    elif paper_title:
        search_query = f"{name} {paper_title}"
    else:
        search_query = name
```

## 6. Update API Endpoint Model

Make the affiliation field optional in the API request model:

```python
# Update in app/api/v1/models.py or wherever the model is defined

class ResearcherCollectionRequest(BaseModel):
    name: str
    affiliation: Optional[str] = None  # Change from required to optional
    paper_title: Optional[str] = None
    position: Optional[str] = None
    email: Optional[str] = None
    researcher_id: Optional[str] = None
    run_in_background: bool = False
``` 