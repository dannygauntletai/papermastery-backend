import httpx
import json
from typing import Dict, Any, List, Optional

from app.core.logger import get_logger
from app.core.config import get_settings
from app.core.exceptions import ExternalAPIError

logger = get_logger(__name__)
settings = get_settings()

class TavilyError(ExternalAPIError):
    """Exception raised for errors in the Tavily API."""
    pass

def trim_query(query: str, max_length: int = 400) -> str:
    """
    Trim a query to the maximum length accepted by Tavily API.
    
    Args:
        query: The original query string
        max_length: Maximum allowed length (default: 400 characters)
        
    Returns:
        Trimmed query string
    """
    if len(query) > max_length:
        logger.info(f"Trimming query from {len(query)} to {max_length} characters")
        return query[:max_length]
    return query

async def enrich_researcher_data(
    name: str,
    scraped_data: Dict[str, Any],
    field: Optional[str] = None
) -> Dict[str, Any]:
    """
    Enrich researcher data using Tavily's AI search API with structured extraction.
    
    Args:
        name: Researcher name
        scraped_data: Data already scraped from other sources
        field: Optional research field/specialty to focus the search
        
    Returns:
        Dictionary containing enriched data:
        - achievements: List of researcher achievements and awards
        - expertise: List of expertise areas
        
    Raises:
        TavilyError: If there's an error with the Tavily API
    """
    try:
        api_key = settings.TAVILY_API_KEY
        if not api_key:
            logger.error("Tavily API key is not configured")
            raise TavilyError("Tavily API key is not configured")
        
        # Extract context from scraped data
        context = build_context(name, scraped_data, field)
        
        # Define structured query templates with JSON response format instructions
        query_templates = {
            "achievements": {
                "query": trim_query(f"""
                Find the major achievements, awards, and recognitions of researcher {name}.
                Please respond in this specific JSON format:
                {{
                  "achievements": [
                    {{
                      "title": "[Achievement title/name]",
                      "year": "[Year if available, otherwise null]",
                      "description": "[Brief description if available]"
                    }},
                    ...
                  ]
                }}
                If you can't find specific achievements, return an empty array.
                Context: {context}
                """),
                "search_depth": "advanced"
            },
            "expertise": {
                "query": trim_query(f"""
                What are the main areas of expertise and research specializations of {name}?
                Please respond in this specific JSON format:
                {{
                  "expertise": [
                    {{
                      "area": "[Area of expertise]",
                      "subfields": ["[Subfield 1]", "[Subfield 2]", ...],
                      "relevance": "[primary/secondary]"
                    }},
                    ...
                  ]
                }}
                If you can't find specific expertise areas, return an empty array.
                Context: {context}
                """),
                "search_depth": "advanced"
            }
        }
        
        # Execute structured queries in parallel and parse results
        results = await execute_tavily_queries(api_key, query_templates)
        
        # Process the structured responses
        processed_results = process_structured_responses(results)
        
        # If we couldn't get structured data, fall back to our text processing approach
        if not processed_results["achievements"] and not processed_results["expertise"]:
            logger.info(f"Falling back to text processing for {name}")
            return await fallback_enrich_data(api_key, name, context)
        
        logger.info(f"Successfully enriched data for {name} using structured extraction")
        return processed_results
    
    except Exception as e:
        logger.error(f"Error enriching researcher data for {name}: {str(e)}")
        raise TavilyError(f"Error enriching researcher data: {str(e)}")


def build_context(name: str, scraped_data: Dict[str, Any], field: Optional[str] = None) -> str:
    """Build context string from scraped data to help guide the search."""
    context_parts = []
    
    # Add researcher name
    context_parts.append(f"Researcher name: {name}")
    
    # Add field if provided
    if field:
        context_parts.append(f"Field: {field}")
    
    # Add bio from scraped data if available
    if scraped_data.get("bio"):
        context_parts.append(f"Biography: {scraped_data['bio']}")
    
    # Get publications as context if available
    if scraped_data.get("publications"):
        pub_titles = []
        for pub in scraped_data["publications"][:5]:
            if isinstance(pub, dict):
                pub_titles.append(pub.get("title", ""))
            elif isinstance(pub, str):
                pub_titles.append(pub)
        
        if pub_titles:
            context_parts.append(f"Recent publications: {'; '.join(pub_titles)}")
    
    # Add any expertise already found if available
    if scraped_data.get("expertise"):
        expertise = scraped_data["expertise"]
        if isinstance(expertise, list) and expertise:
            context_parts.append(f"Known expertise areas: {', '.join(expertise)}")
    
    # Join all context parts
    return "\n".join(context_parts)


async def execute_tavily_queries(
    api_key: str, 
    query_templates: Dict[str, Dict[str, str]]
) -> Dict[str, Any]:
    """Execute multiple Tavily queries in parallel."""
    results = {}
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        tasks = []
        
        for query_type, template in query_templates.items():
            tasks.append(
                execute_single_query(
                    client, 
                    api_key, 
                    template["query"], 
                    template["search_depth"],
                    query_type
                )
            )
        
        # Execute all queries concurrently
        query_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for result in query_results:
            if isinstance(result, Exception):
                logger.warning(f"Query failed: {str(result)}")
                continue
            
            query_type, response = result
            results[query_type] = response
    
    return results


async def execute_single_query(
    client: httpx.AsyncClient,
    api_key: str,
    query: str,
    search_depth: str,
    query_type: str
) -> tuple:
    """Execute a single Tavily query and return the result with its type."""
    try:
        # Ensure query is within the 400 character limit
        query = trim_query(query)
        
        response = await client.post(
            "https://api.tavily.com/search",
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key
            },
            json={
                "query": query,
                "search_depth": search_depth,
                "include_answer": True,
                "include_raw_content": False,
                "include_images": False,
                "max_results": 5
            }
        )
        
        if response.status_code != 200:
            logger.warning(f"Tavily API error: {response.status_code} {response.text}")
            return query_type, None
        
        return query_type, response.json()
    except Exception as e:
        logger.warning(f"Error during Tavily query execution: {str(e)}")
        return query_type, None


def process_structured_responses(results: Dict[str, Any]) -> Dict[str, List[Any]]:
    """Process structured responses from Tavily API."""
    processed_results = {
        "achievements": [],
        "expertise": []
    }
    
    # Process achievements
    if "achievements" in results:
        try:
            answer = results["achievements"].get("answer", "")
            # Try to extract JSON from the answer
            achievements_data = extract_json_from_text(answer)
            
            if achievements_data and "achievements" in achievements_data:
                raw_achievements = achievements_data["achievements"]
                
                # Convert to our simplified format
                simplified_achievements = []
                for achievement in raw_achievements:
                    if isinstance(achievement, dict):
                        title = achievement.get("title", "")
                        year = achievement.get("year", "")
                        description = achievement.get("description", "")
                        
                        if title:
                            achievement_text = title
                            if year:
                                achievement_text += f" ({year})"
                            if description:
                                achievement_text += f": {description}"
                            simplified_achievements.append(achievement_text)
                    elif isinstance(achievement, str):
                        simplified_achievements.append(achievement)
                
                processed_results["achievements"] = simplified_achievements
        except Exception as e:
            logger.warning(f"Error processing achievements data: {str(e)}")
    
    # Process expertise
    if "expertise" in results:
        try:
            answer = results["expertise"].get("answer", "")
            # Try to extract JSON from the answer
            expertise_data = extract_json_from_text(answer)
            
            if expertise_data and "expertise" in expertise_data:
                raw_expertise = expertise_data["expertise"]
                
                # Convert to our simplified format
                simplified_expertise = []
                for expertise in raw_expertise:
                    if isinstance(expertise, dict):
                        area = expertise.get("area", "")
                        subfields = expertise.get("subfields", [])
                        
                        if area:
                            simplified_expertise.append(area)
                            for subfield in subfields:
                                if subfield and subfield not in simplified_expertise:
                                    simplified_expertise.append(subfield)
                    elif isinstance(expertise, str):
                        simplified_expertise.append(expertise)
                
                processed_results["expertise"] = simplified_expertise
        except Exception as e:
            logger.warning(f"Error processing expertise data: {str(e)}")
    
    return processed_results


def extract_json_from_text(text: str) -> Dict[str, Any]:
    """Extract JSON data from a text response that may contain additional content."""
    try:
        # First try to parse the entire text as JSON
        return json.loads(text)
    except json.JSONDecodeError:
        # If that fails, look for JSON object within the text
        try:
            start_idx = text.find('{')
            end_idx = text.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = text[start_idx:end_idx]
                return json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            pass
    
    # If all parsing attempts fail, return empty dict
    return {}


async def fallback_enrich_data(
    api_key: str,
    name: str,
    context: str
) -> Dict[str, List[str]]:
    """Fallback method using text processing for when structured extraction fails."""
    results = {
        "achievements": [],
        "expertise": []
    }
    
    # Create simple queries
    queries = [
        {
            "query": f"What are {name}'s major achievements, awards, and recognitions? {context}",
            "type": "achievements"
        },
        {
            "query": f"What are {name}'s main areas of expertise and research specializations? {context}",
            "type": "expertise"
        }
    ]
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        for query_data in queries:
            query = query_data["query"]
            query_type = query_data["type"]
            
            try:
                response = await client.post(
                    "https://api.tavily.com/search",
                    headers={
                        "Content-Type": "application/json",
                        "x-api-key": api_key
                    },
                    json={
                        "query": query,
                        "search_depth": "advanced",
                        "include_answer": True,
                        "include_raw_content": False,
                        "max_results": 5
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    answer = result.get("answer", "")
                    
                    # Process the answer based on query type
                    if query_type == "achievements":
                        achievements = process_achievements(answer)
                        results["achievements"] = achievements
                    elif query_type == "expertise":
                        expertise = process_expertise(answer)
                        results["expertise"] = expertise
            except Exception as e:
                logger.warning(f"Error in fallback Tavily API call: {str(e)}")
    
    return results


import asyncio

# The existing text processing functions remain unchanged as fallbacks
def process_achievements(text: str) -> List[str]:
    """Process raw achievement text into a structured list."""
    achievements = []
    
    # Split by common bullet point markers and newlines
    for splitter in ["\n-", "\n•", "\n*", "\n1.", "\n2.", "\n3.", "\n"]:
        if splitter in text:
            items = text.split(splitter)
            # Filter out empty items and clean up
            items = [item.strip() for item in items if item.strip()]
            if items:
                achievements = items
                break
    
    # If no structured achievements found, try to extract sentences
    if not achievements:
        sentences = text.split(".")
        achievements = [s.strip() + "." for s in sentences if len(s.strip()) > 20]
    
    # Deduplicate and clean the achievements
    cleaned_achievements = []
    for achievement in achievements:
        # Remove numbering and bullet points at the beginning
        cleaned = achievement.strip()
        cleaned = cleaned.lstrip("•-*1234567890. ")
        
        # Add to list if not a duplicate and substantial enough
        if cleaned and len(cleaned) > 15 and cleaned not in cleaned_achievements:
            cleaned_achievements.append(cleaned)
    
    return cleaned_achievements[:10]  # Limit to 10 achievements


def process_expertise(text: str) -> List[str]:
    """Process raw expertise text into a structured list."""
    expertise_areas = []
    
    # Split by common bullet point markers and newlines
    for splitter in ["\n-", "\n•", "\n*", "\n1.", "\n2.", "\n3.", "\n"]:
        if splitter in text:
            items = text.split(splitter)
            # Filter out empty items and clean up
            items = [item.strip() for item in items if item.strip()]
            if items:
                expertise_areas = items
                break
    
    # If no structured list found, try to extract relevant phrases
    if not expertise_areas:
        # Look for specific expertise indicators
        indicators = [
            "specializes in", "expertise in", "research focuses on",
            "specialization in", "expert in", "research interests include"
        ]
        
        for indicator in indicators:
            if indicator in text.lower():
                parts = text.lower().split(indicator, 1)
                if len(parts) > 1:
                    expertise_text = parts[1].strip()
                    # Split by commas and "and"
                    expertise_items = [item.strip() for item in expertise_text.split(',')]
                    flat_items = []
                    for item in expertise_items:
                        if " and " in item:
                            flat_items.extend([s.strip() for s in item.split(' and ')])
                        else:
                            flat_items.append(item)
                    expertise_areas = flat_items
                    break
    
    # If still no structured list, fall back to sentences
    if not expertise_areas:
        sentences = text.split(".")
        expertise_areas = [s.strip() + "." for s in sentences if len(s.strip()) > 10]
    
    # Clean up the expertise areas
    cleaned_expertise = []
    for area in expertise_areas:
        # Remove numbering and bullet points at the beginning
        cleaned = area.strip()
        cleaned = cleaned.lstrip("•-*1234567890. ")
        
        # Add to list if not a duplicate and substantial enough
        if cleaned and len(cleaned) > 3 and cleaned not in cleaned_expertise:
            cleaned_expertise.append(cleaned)
    
    return cleaned_expertise[:10]  # Limit to 10 areas of expertise 