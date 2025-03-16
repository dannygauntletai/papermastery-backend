import os
import logging
import httpx
import json
import asyncio
import re
from typing import Dict, Any, Optional, List, Set
from urllib.parse import quote, urlparse, parse_qs, urlunparse, quote_plus
import aiohttp
import datetime
import requests
import time

from app.core.logger import get_logger
from app.core.config import get_settings
from app.core.exceptions import ExternalAPIError
from app.utils.api_logging import log_api_call

logger = get_logger(__name__)
settings = get_settings()

# List of common academic domain indicators
ACADEMIC_DOMAINS = [
    ".edu", 
    ".ac.", 
    "university", 
    "college", 
    "institute", 
    "research", 
    "academy",
    "academia"
]

class FirecrawlError(ExternalAPIError):
    """Exception raised for errors in the Firecrawl API."""
    pass

async def scrape_researcher_profile(
    name: str, 
    affiliation: Optional[str] = None, 
    paper_title: Optional[str] = None, 
    position: Optional[str] = None
) -> Dict[str, Any]:
    """
    Scrape researcher profile from the web to get information.
    
    Args:
        name: Researcher name
        affiliation: Optional researcher affiliation (university, institute)
        paper_title: Optional paper title to help identify the researcher
        position: Optional academic position (e.g., 'Professor', 'Assistant Professor')
        
    Returns:
        Dictionary containing researcher profile data including bio, publications, etc.
    """
    try:
        api_key = settings.FIRECRAWL_API_KEY
        if not api_key:
            logger.error("Firecrawl API key is not configured")
            raise FirecrawlError("Firecrawl API key is not configured")
            
        # Ensure API key has the correct format with fc- prefix
        if not api_key.startswith("fc-"):
            api_key = f"fc-{api_key}"
            logger.info("Added fc- prefix to API key")
            
        # Try to use the Firecrawl Extract API first
        # Build search URLs
        encoded_name = quote(name)
        encoded_affiliation = quote(affiliation) if affiliation else ""
        paper_title_encoded = quote(paper_title) if paper_title else ""
        
        # List of URLs to extract from
        urls_to_extract = [
            f"https://www.google.com/search?q={encoded_name} researcher profile",
            f"https://scholar.google.com/scholar?q={encoded_name}",
            f"https://www.semanticscholar.org/search?q={encoded_name}",
            f"https://dblp.org/search?q={encoded_name}"
        ]
        
        # Add academic profile if affiliation is provided
        if affiliation:
            urls_to_extract.append(f"https://www.google.com/search?q={encoded_name} {encoded_affiliation}")
            urls_to_extract.append(f"https://www.google.com/search?q={encoded_name} {encoded_affiliation} faculty")
            
            # Add specific university profile searches
            clean_affiliation = encoded_affiliation.lower().replace("%20", "")
            if "stanford" in clean_affiliation:
                urls_to_extract.append(f"https://profiles.stanford.edu/search?q={encoded_name}")
            elif "ucsd" in clean_affiliation or "san diego" in clean_affiliation:
                urls_to_extract.append(f"https://profiles.ucsd.edu/search?q={encoded_name}")
            elif "mit" in clean_affiliation or "massachusetts institute" in clean_affiliation:
                urls_to_extract.append(f"https://www.mit.edu/search/?q={encoded_name}")
            elif "berkeley" in clean_affiliation or "ucb" in clean_affiliation:
                urls_to_extract.append(f"https://www.berkeley.edu/search?q={encoded_name}")
            elif "carnegie" in clean_affiliation or "cmu" in clean_affiliation:
                urls_to_extract.append(f"https://www.cmu.edu/search/index.html?q={encoded_name}")

        # Add paper title context if provided
        if paper_title:
            urls_to_extract.append(f"https://www.google.com/search?q={encoded_name} {paper_title_encoded}")
            urls_to_extract.append(f"https://scholar.google.com/scholar?q={encoded_name} {paper_title_encoded}")
            urls_to_extract.append(f"https://arxiv.org/search/?query={encoded_name}&searchtype=author")
            
        # Limit the number of URLs to try to avoid overwhelming the API
        urls_to_extract = urls_to_extract[:5]  # Only try 5 URLs maximum
        
        # Use the extract API
        extraction_results = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            for url in urls_to_extract:
                try:
                    logger.info(f"Trying to extract from {url}")
                    
                    # Add a delay between API calls to avoid rate limiting
                    await asyncio.sleep(3)  # Sleep for 3 seconds between requests
                    
                    # Prepare more detailed extraction prompt
                    extraction_prompt = f"""
                    Extract comprehensive information about researcher {name}.
                    
                    IMPORTANT: Search for and follow links to the researcher's personal page, university profile, or Google Scholar profile before extracting information.
                    
                    Find the following information in detail:
                    1. Biography or professional description - Include their career history, research focus, and background
                    2. Publications (titles, years, and journals/conferences) - List at least 5 recent publications with complete details
                    3. Email address (preferably academic email) - Look specifically for .edu or university domain emails
                    4. Areas of expertise or research interests - Be comprehensive, include all research areas mentioned
                    5. Achievements, awards, or honors - Include grants, recognitions, and notable accomplishments
                    6. Current affiliation (university, institution, or company) - Include department and specific role
                    7. Academic position (professor, researcher, student, etc.) - Specify the exact title
                    
                    For better results, check personal websites, university pages, Google Scholar profiles, and academic database entries.
                    """
                    
                    # Prepare API request payload - don't use settings as it's not supported by the v1 API
                    payload = {
                        "urls": [url],
                        "prompt": extraction_prompt.strip()
                    }
                    
                    response = await client.post(
                        "https://api.firecrawl.dev/v1/extract",
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {api_key}"
                        },
                        json=payload
                    )
                    
                    # Handle the response
                    error = None
                    response_data = None
                    extracted_data = None
                    
                    if response.status_code in [200, 201]:
                        result = response.json()
                        response_data = result
                        
                        # Debug log the response structure to help debug extraction issues
                        logger.debug(f"Extract response structure: {result.keys()}")
                        
                        # In v1 API, extract endpoint response format might have data in different structure
                        # Check if there's a data array
                        if "data" in result and isinstance(result["data"], list) and len(result["data"]) > 0:
                            # For multiple URLs, take first one
                            extracted_data = result["data"][0]
                            logger.debug(f"Found extraction data: {extracted_data.keys() if isinstance(extracted_data, dict) else 'not a dict'}")
                        # Try alternative response formats
                        elif "data" in result and isinstance(result["data"], dict):
                            extracted_data = result["data"]
                        elif "content" in result:
                            extracted_data = {"content": result["content"]}
                        elif "extracted_data" in result:
                            extracted_data = result["extracted_data"]
                        else:
                            # If no known fields are found, try using any field that might contain structured data
                            for key, value in result.items():
                                if isinstance(value, dict) and len(value) > 0:
                                    extracted_data = value
                                    logger.info(f"Using alternative field '{key}' for extraction data")
                                    break
                                elif isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                                    extracted_data = value[0]
                                    logger.info(f"Using first item in '{key}' array for extraction data")
                                    break
                                    
                        # If we have extracted data, process it
                        if extracted_data and isinstance(extracted_data, dict):
                            # Try to convert data fields into our structure
                            # Check for bio
                            bio = ""
                            for field in ["bio", "biography", "description", "about", "text", "content"]:
                                if field in extracted_data and extracted_data[field]:
                                    bio = extracted_data[field]
                                    if isinstance(bio, (list, dict)):
                                        bio = str(bio)
                                    break
                                    
                            # Check for publications
                            publications = []
                            for field in ["publications", "papers", "articles", "research"]:
                                if field in extracted_data and extracted_data[field]:
                                    pubs = extracted_data[field]
                                    if isinstance(pubs, list):
                                        for pub in pubs:
                                            if isinstance(pub, dict):
                                                publications.append(pub)
                                            elif isinstance(pub, str):
                                                publications.append({"title": pub})
                                    elif isinstance(pubs, str):
                                        # Try to split by newlines if it's a string
                                        for pub_str in pubs.split('\n'):
                                            if pub_str.strip():
                                                publications.append({"title": pub_str.strip()})
                                    break
                            
                            # Check for email
                            email = None
                            for field in ["email", "contact", "email_address"]:
                                if field in extracted_data and extracted_data[field]:
                                    email_data = extracted_data[field]
                                    if isinstance(email_data, str):
                                        email = email_data
                                    elif isinstance(email_data, list) and len(email_data) > 0:
                                        email = email_data[0]
                                    break
                            
                            # Check for expertise
                            expertise = []
                            for field in ["expertise", "research_interests", "interests", "skills", "specialization"]:
                                if field in extracted_data and extracted_data[field]:
                                    exp_data = extracted_data[field]
                                    if isinstance(exp_data, list):
                                        expertise.extend([e for e in exp_data if isinstance(e, str)])
                                    elif isinstance(exp_data, str):
                                        # Try to split by commas, semicolons if it's a string
                                        for splitter in [',', ';', ' and ']:
                                            if splitter in exp_data:
                                                expertise.extend([e.strip() for e in exp_data.split(splitter) if e.strip()])
                                                break
                                        if not expertise and exp_data.strip():
                                            expertise.append(exp_data.strip())
                                    break
                            
                            # Check for achievements
                            achievements = []
                            for field in ["achievements", "awards", "honors", "recognition"]:
                                if field in extracted_data and extracted_data[field]:
                                    ach_data = extracted_data[field]
                                    if isinstance(ach_data, list):
                                        achievements.extend([a for a in ach_data if isinstance(a, str)])
                                    elif isinstance(ach_data, str):
                                        # Try to split by newlines if it's a string
                                        for ach_str in ach_data.split('\n'):
                                            if ach_str.strip():
                                                achievements.append(ach_str.strip())
                                    break
                            
                            # Check for affiliation
                            current_affiliation = None
                            for field in ["affiliation", "university", "institution", "organization", "employer"]:
                                if field in extracted_data and extracted_data[field]:
                                    aff_data = extracted_data[field]
                                    if isinstance(aff_data, str):
                                        current_affiliation = aff_data
                                    elif isinstance(aff_data, list) and len(aff_data) > 0:
                                        current_affiliation = aff_data[0]
                                    break
                            
                            # Check for position
                            current_position = None
                            for field in ["position", "title", "role", "job_title", "occupation"]:
                                if field in extracted_data and extracted_data[field]:
                                    pos_data = extracted_data[field]
                                    if isinstance(pos_data, str):
                                        current_position = pos_data
                                    elif isinstance(pos_data, list) and len(pos_data) > 0:
                                        current_position = pos_data[0]
                                    break
                                    
                            # Construct the extracted result
                            result_data = {
                                "bio": bio,
                                "publications": publications,
                                "email": email,
                                "expertise": expertise,
                                "achievements": achievements,
                                "affiliation": current_affiliation,
                                "position": current_position
                            }
                            
                            # If we extracted meaningful data, add to results
                            if any(v for v in result_data.values() if v):
                                extraction_results.append(result_data)
                                logger.info(f"Successfully extracted data from {url}")
                        else:
                            error = f"No extraction data found in response from {url}"
                            logger.warning(error)
                    else:
                        # Check if we hit a rate limit error
                        if response.status_code == 429:
                            # Add extra wait time if rate limited, then continue to next URL
                            logger.warning(f"Rate limit hit for {url}, skipping...")
                            # Sleep for 10 seconds to let rate limits reset a bit
                            await asyncio.sleep(10)
                            error = f"Rate limit exceeded for {url}: {response.status_code} {response.text}"
                            continue
                        error = f"Failed to extract from {url}: {response.status_code} {response.text}"
                        logger.warning(error)
                    
                    # Log the API call details
                    log_api_call(
                        service_name="firecrawl",
                        operation="extract",
                        request_data={"payload": payload, "url": url, "researcher": name},
                        response_data=response_data,
                        error=error,
                        status_code=response.status_code
                    )
                    
                except Exception as e:
                    error_msg = f"Error extracting from {url}: {str(e)}"
                    logger.warning(error_msg)
                    
                    # Log the error
                    log_api_call(
                        service_name="firecrawl",
                        operation="extract",
                        request_data={"url": url, "researcher": name},
                        error=error_msg
                    )
                    
            # If we got any extraction results, combine them
            if extraction_results:
                # Initialize combined result
                combined_result = {
                    "bio": "",
                    "publications": [],
                    "email": None,
                    "expertise": [],
                    "achievements": [],
                    "affiliation": None,
                    "position": None
                }
                
                # Track seen publications to avoid duplicates
                seen_publications = set()
                
                # Combine all results, prioritizing academic emails
                for result in extraction_results:
                    # Bio - take the longest one
                    if result.get("bio") and len(result.get("bio", "")) > len(combined_result["bio"]):
                        combined_result["bio"] = result["bio"]
                        
                    # Publications - deduplicate
                    if result.get("publications"):
                        for pub in result["publications"]:
                            if isinstance(pub, dict) and "title" in pub:
                                pub_key = pub["title"].lower()[:100]  # Use first 100 chars as deduplication key
                            elif isinstance(pub, str):
                                pub_key = pub.lower()[:100]
                            else:
                                # Skip if we can't get a key
                                continue
                                
                            if pub_key not in seen_publications:
                                seen_publications.add(pub_key)
                                combined_result["publications"].append(pub)
                                
                    # Email - prioritize academic emails
                    if result.get("email"):
                        email = result["email"]
                        current_email = combined_result["email"]
                        
                        # If we don't have an email yet or the new one is academic
                        if not current_email or (email and any(domain in email for domain in ACADEMIC_DOMAINS) and not any(domain in current_email for domain in ACADEMIC_DOMAINS if current_email)):
                            combined_result["email"] = email
                            
                    # Expertise - deduplicate
                    if result.get("expertise"):
                        for exp in result["expertise"]:
                            if exp not in combined_result["expertise"]:
                                combined_result["expertise"].append(exp)
                                
                    # Achievements - deduplicate
                    if result.get("achievements"):
                        for ach in result["achievements"]:
                            if ach not in combined_result["achievements"]:
                                combined_result["achievements"].append(ach)
                                
                    # Affiliation - prioritize non-null values
                    if result.get("affiliation") and not combined_result["affiliation"]:
                        combined_result["affiliation"] = result["affiliation"]
                        
                    # Position - prioritize non-null values
                    if result.get("position") and not combined_result["position"]:
                        combined_result["position"] = result["position"]
                
                logger.info(f"Successfully extracted and combined data for {name}")
                
                # Log the combined results
                log_api_call(
                    service_name="firecrawl",
                    operation="combined_results",
                    request_data={
                        "name": name,
                        "affiliation": affiliation,
                        "paper_title": paper_title,
                        "position": position
                    },
                    response_data=combined_result
                )
                
                return combined_result
        
        # If extract didn't return useful data, fallback to traditional scraping
        logger.info(f"Falling back to traditional scraping for {name}")
        return await fallback_scrape_profile(name, affiliation, paper_title, position)
    
    except Exception as e:
        error_msg = f"Error scraping researcher profile for {name}: {str(e)}"
        logger.error(error_msg)
        
        # Return minimal structure with provided values
        return {
            "bio": "",
            "publications": [],
            "email": None,
            "expertise": [],
            "achievements": [],
            "affiliation": affiliation,
            "position": position
        }


async def fallback_scrape_profile(
    name: str, 
    affiliation: Optional[str] = None,
    paper_title: Optional[str] = None,
    position: Optional[str] = None,
    url: Optional[str] = None,
    max_retries: int = 2,  # Add retry parameter
    retry_delay: int = 5   # Add base delay parameter for retries
) -> Dict[str, Any]:
    """
    Fallback method to scrape researcher profile using traditional scraping approach.
    This is used when Extract fails or returns insufficient data.
    
    Args:
        name: Researcher name
        affiliation: Optional researcher affiliation (university, institute)
        paper_title: Optional paper title to help identify the researcher
        position: Optional academic position (e.g., 'Professor', 'Assistant Professor')
        url: Optional specific URL to scrape
        max_retries: Maximum number of retries for rate limited requests
        retry_delay: Base delay in seconds between retries
        
    Returns:
        Dictionary containing researcher profile data
    """
    try:
        api_key = settings.FIRECRAWL_API_KEY
        if not api_key:
            logger.error("Firecrawl API key is not configured")
            raise FirecrawlError("Firecrawl API key is not configured")
        
        # Ensure API key has the correct format with fc- prefix
        if not api_key.startswith("fc-"):
            api_key = f"fc-{api_key}"
            logger.info("Added fc- prefix to API key")
            
        # Build search query
        search_query = name
        if affiliation:
            search_query += f" {affiliation}"
        if paper_title:
            search_query += f" {paper_title}"
            
        # If a specific URL is provided, use only that
        urls_to_try = []
        if url:
            urls_to_try.append(url)
        else:
            # Otherwise use search URLs
            encoded_name = quote(name)
            encoded_affiliation = quote(affiliation) if affiliation else ""
            paper_title_encoded = quote(paper_title) if paper_title else ""
            
            # URLs to try - directly use academic profile sites instead of just Google
            urls_to_try = [
                # Standard Google searches
                f"https://www.google.com/search?q={encoded_name}+profile",
                # Try Google Scholar directly
                f"https://scholar.google.com/scholar?q={encoded_name}",
                # Try Semantic Scholar
                f"https://www.semanticscholar.org/search?q={encoded_name}&sort=relevance",
                # Try DBLP
                f"https://dblp.org/search?q={encoded_name}",
                # Try ACM Digital Library
                f"https://dl.acm.org/action/doSearch?AllField={encoded_name}"
            ]
            
            # Add more targeted searches
            if affiliation:
                urls_to_try.append(f"https://www.google.com/search?q={encoded_name}+{encoded_affiliation}+profile")
                # Try affiliation-specific searches
                urls_to_try.append(f"https://www.google.com/search?q={encoded_name}+{encoded_affiliation}+faculty")
                urls_to_try.append(f"https://www.google.com/search?q={encoded_name}+{encoded_affiliation}+researcher")
                
                # Try university profile directories
                clean_affiliation = encoded_affiliation.lower().replace("%20", "")
                if "stanford" in clean_affiliation:
                    urls_to_try.append(f"https://profiles.stanford.edu/search?q={encoded_name}")
                elif "ucsd" in clean_affiliation or "san diego" in clean_affiliation:
                    urls_to_try.append(f"https://profiles.ucsd.edu/search?q={encoded_name}")
                elif "mit" in clean_affiliation or "massachusetts institute" in clean_affiliation:
                    urls_to_try.append(f"https://www.mit.edu/search/?q={encoded_name}&site=mit")
                elif "berkeley" in clean_affiliation or "ucb" in clean_affiliation:
                    urls_to_try.append(f"https://www.berkeley.edu/search?q={encoded_name}")
                elif "carnegie" in clean_affiliation or "cmu" in clean_affiliation:
                    urls_to_try.append(f"https://www.cmu.edu/search/index.html?q={encoded_name}")
            
            if paper_title:
                urls_to_try.append(f"https://www.google.com/search?q={encoded_name}+{paper_title_encoded}")
                # Try academic paper databases
                urls_to_try.append(f"https://arxiv.org/search/?query={encoded_name}&searchtype=author")
                urls_to_try.append(f"https://scholar.google.com/scholar?q={encoded_name}+{paper_title_encoded}")
                urls_to_try.append(f"https://www.semanticscholar.org/search?q={paper_title_encoded}&sort=relevance")

        # Limit the number of URLs to try to avoid overwhelming the API
        urls_to_try = urls_to_try[:5]  # Only try 5 URLs maximum
        
        # Try each URL until we get a good response
        results = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            for url in urls_to_try:
                try:
                    logger.info(f"Trying fallback scrape for {name} from URL: {url}")
                    
                    # Add a delay between API calls to avoid rate limiting
                    await asyncio.sleep(3)  # Sleep for 3 seconds between requests
                    
                    # Prepare API request payload - just URL in the simplest form (v1 API doesn't support settings)
                    payload = {
                        "url": url
                    }
                    
                    response = await client.post(
                        "https://api.firecrawl.dev/v1/scrape",
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {api_key}"
                        },
                        json=payload
                    )
                    
                    # Log the API call
                    response_data = None
                    error = None
                    
                    if response.status_code in [200, 201]:
                        result = response.json()
                        response_data = result
                        
                        # Debug log to show the complete response structure
                        logger.debug(f"Response keys from {url}: {result.keys()}")
                        
                        # Try different possible content fields
                        page_content = ""
                        
                        # In v1 /scrape API, the data could be in various fields
                        # Extract from 'data' dict if it exists
                        if "data" in result and isinstance(result["data"], dict):
                            data = result["data"]
                            logger.debug(f"Data keys: {data.keys()}")
                            
                            # Check for content in various fields
                            for field in ["markdown", "html", "text", "content"]:
                                if field in data and data[field]:
                                    page_content = data[field]
                                    logger.info(f"Found content in '{field}' field from {url}")
                                    break
                        
                        # If no data.field content, try content directly in result
                        if not page_content:
                            for field in ["markdown", "html", "text", "content", "data"]:
                                if field in result and result[field]:
                                    if isinstance(result[field], str):
                                        page_content = result[field]
                                        logger.info(f"Found content in root '{field}' field from {url}")
                                        break
                                    elif isinstance(result[field], dict) and "content" in result[field]:
                                        page_content = result[field]["content"]
                                        logger.info(f"Found content in '{field}.content' from {url}")
                                        break
                        
                        if page_content:
                            # Store the content and the source URL for better debugging
                            results.append({"content": page_content, "source": url})
                            logger.info(f"Found content from {url} with length {len(page_content)}")
                        else:
                            # Log the entire response for debugging
                            logger.warning(f"No content found in response from {url}. Full response: {result}")
                    else:
                        # Check if we hit a rate limit error
                        if response.status_code == 429:
                            # Add extra wait time if rate limited, then continue to next URL
                            logger.warning(f"Rate limit hit for {url}, skipping...")
                            # Sleep for 10 seconds to let rate limits reset a bit
                            await asyncio.sleep(10)
                            error = f"Rate limit exceeded for {url}: {response.status_code} {response.text}"
                            continue
                            
                        error = f"Failed to scrape {url}: {response.status_code} {response.text}"
                        logger.warning(error)
                    
                    # Log the API call details
                    log_api_call(
                        service_name="firecrawl",
                        operation="scrape",
                        request_data={"payload": payload, "url": url, "researcher": name},
                        response_data=response_data,
                        error=error,
                        status_code=response.status_code
                    )
                    
                except Exception as e:
                    error_msg = f"Error scraping {url}: {str(e)}"
                    logger.warning(error_msg)
                    
                    # Log the error
                    log_api_call(
                        service_name="firecrawl",
                        operation="scrape",
                        request_data={"url": url, "researcher": name},
                        error=error_msg
                    )
        
        # If no results found, return empty structure
        if not results:
            logger.warning(f"No results found for {name} using fallback scraping")
            
            empty_result = {
                "bio": "",
                "publications": [],
                "email": None,
                "expertise": [],
                "achievements": [],
                "affiliation": affiliation,  # Keep provided affiliation even if scraping failed
                "position": position  # Keep provided position even if scraping failed
            }
            
            # Log the empty result
            log_api_call(
                service_name="firecrawl",
                operation="fallback_empty",
                request_data={
                    "name": name,
                    "affiliation": affiliation,
                    "paper_title": paper_title,
                    "position": position
                },
                response_data=empty_result
            )
            
            return empty_result
        
        # Combine all scraped content
        combined_text = "\n".join([r["content"] for r in results])
        
        # Log the sources used for extraction
        sources = [r["source"] for r in results]
        logger.info(f"Extracting profile data for {name} from sources: {sources}")
        
        # Extract key information
        result = {
            "bio": extract_bio(combined_text, name),
            "publications": extract_publications(combined_text),
            "email": extract_email(combined_text),
            "expertise": extract_expertise(combined_text),
            "achievements": extract_achievements(combined_text),
            "affiliation": extract_affiliation(combined_text, affiliation),
            "position": extract_position(combined_text, position)
        }
        
        # If we still didn't get good data, use the provided values
        if not result["bio"] and not result["publications"] and not result["expertise"]:
            logger.warning(f"Extracted minimal data for {name}, using provided values where available")
            if position:
                result["position"] = position
            if affiliation:
                result["affiliation"] = affiliation
        
        logger.info(f"Successfully scraped profile for {name} using fallback method")
        
        # Log the extracted result
        log_api_call(
            service_name="firecrawl",
            operation="fallback_results",
            request_data={
                "name": name,
                "affiliation": affiliation,
                "paper_title": paper_title,
                "position": position
            },
            response_data=result
        )
        
        return result
    
    except Exception as e:
        error_msg = f"Error extracting researcher profile for {name}: {str(e)}"
        logger.error(error_msg)
        
        # Return minimal structure with provided values
        return {
            "bio": "",
            "publications": [],
            "email": None,
            "expertise": [],
            "achievements": [],
            "affiliation": affiliation,
            "position": position
        }


def extract_bio(text: str, name: str) -> str:
    """Extract researcher bio from scraped text."""
    # Look for paragraphs that contain the researcher's name
    lines = text.split("\n")
    bio_candidates = []
    
    # Try to normalize the name
    name_lower = name.lower()
    first_name = name_lower.split()[0] if len(name_lower.split()) > 0 else name_lower
    last_name = name_lower.split()[-1] if len(name_lower.split()) > 1 else name_lower
    
    for i, line in enumerate(lines):
        line_lower = line.lower()
        
        # Look for exact name or first/last name
        if (name_lower in line_lower or 
            (first_name in line_lower and last_name in line_lower)) and len(line) > 50:
            bio_candidates.append(line)
            
        # Look for "about" sections that might contain bios
        if i < len(lines) - 1 and "about" in line_lower and "about me" in line_lower:
            next_line = lines[i + 1]
            if len(next_line) > 50:
                bio_candidates.append(next_line)
    
    # If we found potential bio paragraphs, return the longest one
    if bio_candidates:
        return max(bio_candidates, key=len)
    
    # Otherwise, look for any paragraph that seems to be a bio
    for i, line in enumerate(lines):
        # More bio indicators
        bio_indicators = [
            "research", "interests", "work", "focuses on", "specializes in",
            "professor", "student", "faculty", "expertise", "background",
            "education", "phd", "received", "earned", "studies"
        ]
        
        line_lower = line.lower()
        if len(line) > 100 and any(indicator in line_lower for indicator in bio_indicators):
            return line
    
    # If all else fails, return an empty string
    return ""


def extract_publications(text: str) -> List[Dict[str, str]]:
    """Extract publications from scraped text."""
    publications = []
    lines = text.split("\n")
    
    # Publication-related keywords
    pub_indicators = ["paper", "publication", "journal", "conference", "proceedings", "arxiv"]
    year_patterns = ["2018", "2019", "2020", "2021", "2022", "2023", "2024"]
    
    for i, line in enumerate(lines):
        line_lower = line.lower()
        
        # Check more patterns for publications
        is_likely_pub = (
            # Length check - publication titles are typically longer
            len(line) > 30 and 
            # Not too long (likely not a publication title)
            len(line) < 300 and
            # Check for publication indicators
            (any(ind in line_lower for ind in pub_indicators) or
             # Check for year indicators
             any(year in line for year in year_patterns) or
             # Check for citation pattern (Author et al.)
             (" et al" in line_lower))
        )
        
        if is_likely_pub:
            # Check for citation patterns
            if " et al" in line_lower or any(year in line for year in year_patterns):
                publications.append({"title": line.strip()})
                continue
                
            # Check the next line for authors or journal information
            if i < len(lines) - 1:
                next_line = lines[i + 1]
                if ("," in next_line and 
                    (any(year in next_line for year in year_patterns) or
                     any(ind in next_line.lower() for ind in ["journal", "conference", "proceedings"]))):
                    pub = {
                        "title": line.strip(),
                        "details": next_line.strip()
                    }
                    publications.append(pub)
    
    # Deduplicate by title (case-insensitive)
    seen_titles = set()
    unique_publications = []
    
    for pub in publications:
        title_lower = pub["title"].lower()
        if title_lower not in seen_titles:
            seen_titles.add(title_lower)
            unique_publications.append(pub)
    
    # Limit to 10 most recent publications
    return unique_publications[:10]


def extract_email(text: str) -> Optional[str]:
    """Extract email address from scraped text."""
    import re
    
    # Look for email addresses using regex
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text)
    
    # Filter out common false positives
    filtered_emails = [
        email for email in emails 
        if not any(domain in email.lower() for domain in [
            "@example.com", "@gmail.com", "@yahoo.com", "@hotmail.com", 
            "@aol.com", "@outlook.com", "@live.com"
        ])
    ]
    
    # Prioritize academic emails
    academic_emails = [
        email for email in filtered_emails
        if any(domain in email.lower() for domain in 
              [".edu", ".ac.", "university", "college", "institute"])
    ]
    
    if academic_emails:
        return academic_emails[0]
    elif filtered_emails:
        return filtered_emails[0]
    
    return None


def extract_expertise(text: str) -> List[str]:
    """Extract areas of expertise from scraped text."""
    expertise = []
    lines = text.split("\n")
    
    # Expanded list of expertise indicators
    expertise_indicators = [
        "research interests", "areas of expertise", "specializes in",
        "research areas", "specialist in", "expertise in", "specialization",
        "research topics", "research focus", "field of study", "focus areas",
        "specialties", "interests include", "working on", "researching"
    ]
    
    for line in lines:
        line_lower = line.lower()
        if any(indicator in line_lower for indicator in expertise_indicators):
            # Try to extract expertise from this line
            for indicator in expertise_indicators:
                if indicator in line_lower:
                    expertise_text = line_lower.split(indicator, 1)[1].strip()
                    # Split by various separators
                    for splitter in [",", ";", " and ", "."]:
                        if splitter in expertise_text:
                            areas = [area.strip() for area in expertise_text.split(splitter)]
                            areas = [area.capitalize() for area in areas if area and len(area) > 3]
                            expertise.extend(areas)
                            break
                    break
    
    # Expanded list of research keywords to check
    if not expertise:
        research_keywords = [
            "machine learning", "artificial intelligence", "deep learning",
            "natural language processing", "computer vision", "robotics",
            "big data", "data science", "quantum computing", "cybersecurity",
            "bioinformatics", "physics", "chemistry", "biology", "mathematics",
            "statistics", "economics", "psychology", "neuroscience",
            "computer science", "information retrieval", "data mining",
            "reinforcement learning", "neural networks", "automated reasoning",
            "knowledge representation", "semantic web", "human-computer interaction",
            "computational linguistics", "information theory", "algorithms",
            "computational biology", "genomics", "proteomics", "systems biology",
            "molecular biology", "materials science", "nanotechnology",
            "cryptography", "blockchain", "distributed systems", "cloud computing"
        ]
        
        for keyword in research_keywords:
            if keyword in text.lower():
                expertise.append(keyword.capitalize())
    
    # Deduplicate and return
    return list(set(expertise))


def extract_achievements(text: str) -> List[str]:
    """Extract achievements and awards from scraped text."""
    achievements = []
    lines = text.split("\n")
    
    # Look for lines that mention awards, honors, recognition
    achievement_indicators = [
        "award", "honor", "prize", "medal", "fellow", "recognition",
        "granted", "recipient", "won", "received"
    ]
    
    for line in lines:
        line_lower = line.lower()
        if any(indicator in line_lower for indicator in achievement_indicators):
            # Clean up the line
            achievement = line.strip()
            if achievement and len(achievement) > 10:
                achievements.append(achievement)
    
    # Deduplicate and limit
    unique_achievements = []
    for achievement in achievements:
        if achievement not in unique_achievements:
            unique_achievements.append(achievement)
    
    return unique_achievements[:10]

def extract_affiliation(text: str, provided_affiliation: Optional[str] = None) -> Optional[str]:
    """Extract the researcher's affiliation from text."""
    if not text:
        return provided_affiliation
    
    lines = text.split("\n")
    
    # Expanded list of affiliation indicators
    affiliation_indicators = [
        "affiliation:", "affiliated with", "works at", "employed by",
        "professor at", "researcher at", "student at", "faculty at",
        "department of", "school of", "university of", "college of",
        "institute of", "laboratory of", "lab at", "member of",
        "phd student at", "postdoc at", "graduate student at",
        "lecturer at", "teaching at", "working at", "based at"
    ]
    
    # Common universities and research institutions to look for
    common_institutions = [
        "stanford", "mit", "harvard", "berkeley", "cambridge", "oxford",
        "princeton", "caltech", "columbia", "yale", "chicago", "ucsd",
        "university of california", "carnegie mellon", "eth zurich",
        "imperial college", "cornell", "johns hopkins", "ucla", "nyu"
    ]
    
    # First check for direct mentions of institutions in the text
    if provided_affiliation:
        # If a specific affiliation was provided, look for related terms
        provided_lower = provided_affiliation.lower()
        for line in lines:
            line_lower = line.lower()
            if provided_lower in line_lower:
                # Extract the line around the provided affiliation
                start = max(0, line_lower.find(provided_lower) - 10)
                end = min(len(line), line_lower.find(provided_lower) + len(provided_lower) + 30)
                return line[start:end].strip()
    
    # Check for explicit affiliation mentions
    for line in lines:
        line_lower = line.lower()
        
        # Look for common institutions
        for institution in common_institutions:
            if institution in line_lower:
                # Find the institution in the text
                inst_idx = line_lower.find(institution)
                # Get some context before and after
                start = max(0, inst_idx - 10)
                end = min(len(line), inst_idx + len(institution) + 30)
                institution_text = line[start:end].strip()
                
                # If it's too generic, extend it a bit
                if len(institution_text) < 15:
                    start = max(0, inst_idx - 20)
                    end = min(len(line), inst_idx + len(institution) + 40)
                    institution_text = line[start:end].strip()
                
                return institution_text
        
        # Check for explicit affiliation indicators
        if any(indicator in line_lower for indicator in affiliation_indicators):
            # Clean up and return the line with the affiliation
            cleaned_line = line.strip()
            
            # If line is too long, try to extract just the institution name
            if len(cleaned_line) > 80:
                for indicator in affiliation_indicators:
                    if indicator in line_lower:
                        # Extract text after the indicator
                        idx = line_lower.find(indicator) + len(indicator)
                        institution = line[idx:].strip()
                        # Limit to first comma or period
                        end_idx = min(
                            (i for i in (institution.find(','), institution.find('.'), 
                                        institution.find(' and ')) if i > 0),
                            default=len(institution)
                        )
                        return institution[:end_idx].strip()
            
            # Remove trailing punctuation
            if cleaned_line.endswith('.'):
                cleaned_line = cleaned_line[:-1]
            
            return cleaned_line
    
    # If nothing found, use provided affiliation
    return provided_affiliation


def extract_position(text: str, provided_position: Optional[str] = None) -> Optional[str]:
    """Extract the researcher's position/title from text."""
    if not text:
        return provided_position
    
    lines = text.split("\n")
    
    # Expanded list of academic positions
    position_indicators = [
        "professor", "assistant professor", "associate professor", "full professor",
        "postdoc", "postdoctoral", "phd student", "doctoral student", "ph.d. candidate",
        "lecturer", "researcher", "scientist", "director", "dean", "chair", "head of",
        "visiting professor", "adjunct professor", "research assistant", "research associate",
        "graduate student", "faculty member", "emeritus professor", "instructor",
        "teaching assistant", "research fellow", "senior lecturer", "principal investigator"
    ]
    
    for line in lines:
        line_lower = line.lower()
        for position in position_indicators:
            if position in line_lower:
                # Get the position term and context
                idx = line_lower.find(position)
                
                # Extract a bit of context
                start = max(0, idx - 5)
                end = min(len(line_lower), idx + len(position) + 5)
                context = line_lower[start:end]
                
                # Extract just the position itself
                if position == "professor":
                    # Check if it's a specific type of professor
                    for specific in ["assistant professor", "associate professor", "full professor"]:
                        if specific in line_lower:
                            position = specific
                            break
                
                # Look for department or field
                department = ""
                dept_indicators = ["of ", "in "]
                for indicator in dept_indicators:
                    if indicator in line_lower[idx + len(position):idx + len(position) + 20]:
                        dept_start = line_lower.find(indicator, idx + len(position))
                        if dept_start > 0:
                            dept_end = line_lower.find(",", dept_start)
                            if dept_end < 0:
                                dept_end = line_lower.find(".", dept_start)
                            if dept_end < 0:
                                dept_end = dept_start + 30
                            
                            department = line[dept_start:dept_end].strip()
                            break
                
                # Format the position properly
                position_term = position.strip()
                formatted_position = " ".join(word.capitalize() for word in position_term.split())
                
                # Add department if available
                if department:
                    return f"{formatted_position}{department}"
                else:
                    return formatted_position
    
    # If nothing found, use provided position or researcher as default
    return provided_position if provided_position else "Researcher" 

async def crawl_url(url: str, max_retries: int = 3, retry_delay: int = 5) -> Dict[str, Any]:
    """
    Crawl a URL using the Firecrawl API.
    
    Args:
        url: The URL to crawl
        max_retries: Maximum number of retries for polling the result
        retry_delay: Delay in seconds between retries
        
    Returns:
        Dictionary containing the crawled data
    """
    # Get API key
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        raise ValueError("FIRECRAWL_API_KEY not found in environment variables")
    
    # Prepare headers
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    # Prepare payload
    payload = {
        "url": url
    }
    
    # Log API call
    logger.info(f"Crawling URL: {url}")
    
    # Make API request to start the crawl
    async with aiohttp.ClientSession() as session:
        try:
            # Step 1: Initiate the crawl
            async with session.post(
                "https://api.firecrawl.dev/v1/crawl",
                headers=headers,
                json=payload,
                timeout=60  # 1 minute timeout
            ) as response:
                # Check for rate limiting
                if response.status == 429:
                    logger.warning(f"Rate limit hit while initiating crawl for {url}. Waiting before retrying.")
                    await asyncio.sleep(10)  # Wait 10 seconds
                    error_message = f"Rate limit exceeded for URL: {url}"
                    log_api_call(
                        service_name="firecrawl",
                        operation="crawl_initiate",
                        request_data={"url": url},
                        error=error_message
                    )
                    return {"success": False, "error": error_message}
                
                # Parse response
                response_data = await response.json()
                
                # Log response
                log_api_call(
                    service_name="firecrawl",
                    operation="crawl_initiate",
                    request_data={"url": url},
                    response_data={
                        "status": response.status,
                        "job_id": response_data.get("id", "unknown")
                    }
                )
                
                # Check if crawl initiation was successful
                if response.status != 200 or not response_data.get("success", False):
                    error_message = f"Failed to initiate crawl for URL: {url}, Status: {response.status}"
                    logger.warning(error_message)
                    return {"success": False, "error": error_message, "url": url}
                
                # Get the job ID
                job_id = response_data.get("id")
                if not job_id:
                    error_message = f"No job ID returned for crawl of URL: {url}"
                    logger.warning(error_message)
                    return {"success": False, "error": error_message, "url": url}
                
                logger.info(f"Crawl job initiated for {url} with job ID: {job_id}")
                
                # Step 2: Poll for the result
                result_url = f"https://api.firecrawl.dev/v1/crawl/{job_id}"
                
                # Try to get the result with retries
                for attempt in range(max_retries):
                    # Wait before polling
                    await asyncio.sleep(retry_delay * (attempt + 1))  # Increasing delay
                    
                    logger.info(f"Polling for crawl result, attempt {attempt + 1}/{max_retries} for job ID: {job_id}")
                    
                    async with session.get(
                        result_url,
                        headers=headers,
                        timeout=60  # 1 minute timeout
                    ) as result_response:
                        # Check for rate limiting
                        if result_response.status == 429:
                            logger.warning(f"Rate limit hit while polling for job ID: {job_id}. Waiting before retrying.")
                            await asyncio.sleep(10)  # Wait 10 seconds
                            continue
                        
                        # Parse result response
                        result_data = await result_response.json()
                        
                        # Log the raw result data for debugging
                        logger.debug(f"Raw result data for job ID {job_id}: {json.dumps(result_data)[:500]}...")
                        
                        # Log response
                        log_api_call(
                            service_name="firecrawl",
                            operation="crawl_poll",
                            request_data={"job_id": job_id},
                            response_data={
                                "status": result_response.status,
                                "content_length": len(str(result_data)) if result_data else 0
                            }
                        )
                        
                        # Check if the result is ready
                        if result_response.status == 200:
                            status = result_data.get("status", "unknown")
                            
                            if status == "completed":
                                logger.info(f"Crawl completed for job ID: {job_id}")
                                
                                # Extract the content - handle different response formats
                                content = {}
                                
                                # Try to get HTML content
                                if "html" in result_data:
                                    content["html"] = result_data["html"]
                                    logger.info(f"Found HTML content with length {len(content['html'])}")
                                
                                # Try to get text content
                                if "text" in result_data:
                                    content["text"] = result_data["text"]
                                    logger.info(f"Found text content with length {len(content['text'])}")
                                
                                # Try to get markdown content
                                if "markdown" in result_data:
                                    content["markdown"] = result_data["markdown"]
                                    logger.info(f"Found markdown content with length {len(content['markdown'])}")
                                
                                # Try to get content from data object
                                if "data" in result_data and isinstance(result_data["data"], dict):
                                    data = result_data["data"]
                                    for field in ["html", "text", "markdown", "content"]:
                                        if field in data and data[field]:
                                            content[field] = data[field]
                                            logger.info(f"Found {field} content in data with length {len(data[field])}")
                                
                                # Try to get content from content object
                                if "content" in result_data and isinstance(result_data["content"], dict):
                                    content_obj = result_data["content"]
                                    for field in ["html", "text", "markdown", "content"]:
                                        if field in content_obj and content_obj[field]:
                                            content[field] = content_obj[field]
                                            logger.info(f"Found {field} content in content object with length {len(content_obj[field])}")
                                
                                # If no structured content found, use the raw result
                                if not content:
                                    logger.warning(f"No structured content found in result for job ID: {job_id}, using raw result")
                                    content = {"raw": json.dumps(result_data)}
                                
                                logger.info(f"Successfully crawled page: {url} (content fields: {list(content.keys())})")
                                return {"success": True, "content": content, "url": url, "job_id": job_id}
                            
                            elif status == "failed":
                                error_message = f"Crawl failed for job ID: {job_id}, Error: {result_data.get('error', 'Unknown error')}"
                                logger.warning(error_message)
                                return {"success": False, "error": error_message, "url": url, "job_id": job_id}
                            
                            elif status in ["processing", "scraping"]:
                                logger.info(f"Crawl still {status} for job ID: {job_id}, will retry...")
                                continue
                            
                            else:
                                logger.warning(f"Unknown status '{status}' for job ID: {job_id}, will retry...")
                                continue
                        
                        else:
                            logger.warning(f"Failed to get result for job ID: {job_id}, Status: {result_response.status}, will retry...")
                            continue
                
                # If we get here, we've exhausted our retries
                error_message = f"Failed to get crawl result after {max_retries} attempts for job ID: {job_id}"
                logger.error(error_message)
                return {"success": False, "error": error_message, "url": url, "job_id": job_id}
        
        except asyncio.TimeoutError:
            error_message = f"Timeout while crawling URL: {url}"
            logger.warning(error_message)
            log_api_call(
                service_name="firecrawl",
                operation="crawl",
                request_data={"url": url},
                error=error_message
            )
            return {"success": False, "error": error_message, "url": url}
        
        except Exception as e:
            error_message = f"Error crawling URL: {url}, Error: {str(e)}"
            logger.error(error_message)
            log_api_call(
                service_name="firecrawl",
                operation="crawl",
                request_data={"url": url},
                error=error_message
            )
            return {"success": False, "error": error_message, "url": url}

async def extract_researcher_info_with_llm(
    crawled_content: Dict[str, Any],
    name: str,
    affiliation: Optional[str] = None,
    paper_title: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extract researcher information from crawled content using our LLM.
    
    Args:
        crawled_content: Dictionary containing the crawled content from Firecrawl
        name: Researcher name
        affiliation: Optional researcher affiliation
        paper_title: Optional paper title
        
    Returns:
        Dictionary containing structured researcher information
    """
    from app.services.llm_service import generate_text
    
    try:
        # Prepare the content to analyze
        content_to_analyze = ""
        url = crawled_content.get("url", "unknown")
        
        if not crawled_content.get("success", False):
            logger.warning(f"Cannot extract information from unsuccessful scrape of {url}")
            return {
                "bio": "",
                "publications": [],
                "email": None,
                "expertise": [],
                "achievements": [],
                "affiliation": affiliation,
                "position": None
            }
        
        # Check if we have raw JSON content (from the crawl API)
        if "content" in crawled_content and "raw" in crawled_content["content"]:
            try:
                # Parse the raw JSON
                raw_data = json.loads(crawled_content["content"]["raw"])
                logger.info(f"Parsed raw JSON data from crawl API: {json.dumps(raw_data)[:500]}...")
                
                # Check if we have data array
                if "data" in raw_data and isinstance(raw_data["data"], list):
                    # Process each item in the data array
                    for item in raw_data["data"]:
                        # Try to get content from different fields
                        if "html" in item and item["html"]:
                            content_to_analyze += f"\n\n--- HTML Content from {item.get('url', url)} ---\n\n{item['html'][:50000]}"
                        
                        if "text" in item and item["text"]:
                            content_to_analyze += f"\n\n--- Text Content from {item.get('url', url)} ---\n\n{item['text'][:50000]}"
                        
                        if "markdown" in item and item["markdown"]:
                            content_to_analyze += f"\n\n--- Markdown Content from {item.get('url', url)} ---\n\n{item['markdown'][:50000]}"
                
                # If no content found in data array, try to get content from the raw data directly
                if not content_to_analyze:
                    # Try to get content from different fields in the raw data
                    for field in ["html", "text", "markdown", "content"]:
                        if field in raw_data and raw_data[field]:
                            content_to_analyze += f"\n\n--- {field.capitalize()} Content from {url} ---\n\n{raw_data[field][:50000]}"
                
                # If still no content, use the entire raw data as a fallback
                if not content_to_analyze:
                    content_to_analyze = f"\n\n--- Raw JSON Data from {url} ---\n\n{json.dumps(raw_data, indent=2)}"
                    logger.warning(f"No structured content found in raw JSON, using entire raw data")
            
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse raw JSON: {str(e)}")
                content_to_analyze = crawled_content["content"]["raw"]
                logger.warning(f"Using raw content as string due to JSON parse error")
        
        # If no raw JSON, try to extract content from pages if available
        elif "content" in crawled_content and "pages" in crawled_content["content"]:
            pages = crawled_content["content"]["pages"]
            
            # Combine content from all pages, prioritizing different content types
            for page in pages:
                # Try to get the most structured content
                page_content = ""
                
                # First try markdown which is usually most structured
                if "markdown" in page and page["markdown"]:
                    page_content = page["markdown"]
                # Then try text which is clean but less structured
                elif "text" in page and page["text"]:
                    page_content = page["text"]
                # Then try HTML as a last resort
                elif "html" in page and page["html"]:
                    page_content = page["html"]
                    
                if page_content:
                    page_url = page.get("url", "unknown")
                    content_to_analyze += f"\n\n--- Content from {page_url} ---\n\n{page_content}"
        
        # If no pages, use any direct content fields
        if not content_to_analyze:
            content = crawled_content.get("content", {})
            
            # Check each content type in order of preference
            for field in ["markdown", "text", "content", "html"]:
                if field in content and content[field]:
                    content_to_analyze += f"\n\n--- Content from {url} ({field}) ---\n\n{content[field]}"
                    break
        
        if not content_to_analyze:
            logger.warning(f"No content found to analyze from {url}")
            return {
                "bio": "",
                "publications": [],
                "email": None,
                "expertise": [],
                "achievements": [],
                "affiliation": affiliation,
                "position": None
            }
        
        # Limit content length to avoid token limits (around 100k characters is reasonable)
        if len(content_to_analyze) > 100000:
            logger.info(f"Truncating content from {len(content_to_analyze)} to 100,000 characters")
            content_to_analyze = content_to_analyze[:100000]
        
        # Prepare the extraction prompt for the LLM
        extraction_prompt = f"""
You are an AI assistant helping to extract structured information about a researcher from web content.

RESEARCHER INFO:
- Name: {name}
{f"- Affiliation: {affiliation}" if affiliation else ""}
{f"- Paper Title: {paper_title}" if paper_title else ""}

Based ONLY on the content provided, extract the following information about the researcher:

1. BIO: A concise professional biography or description
2. PUBLICATIONS: A list of publications (titles and optionally year and venue)
3. EMAIL: Their email address (especially academic emails)
4. EXPERTISE: Their research interests or areas of expertise
5. ACHIEVEMENTS: Awards, honors, grants, recognitions
6. AFFILIATION: Current university, institution, or company
7. POSITION: Academic position or title (e.g., Professor, Assistant Professor, etc.)

IMPORTANT GUIDELINES:
- Extract ONLY facts that are explicitly mentioned in the content
- If information for a field is not found, return an empty value
- For EMAIL, prioritize .edu or academic institution emails
- Format your response as a JSON object with these exact keys: "bio", "publications" (array of strings), "email", "expertise" (array of strings), "achievements" (array of strings), "affiliation", "position"
- Use null for missing values and empty arrays [] for missing lists

CONTENT TO ANALYZE:
{content_to_analyze}

JSON RESPONSE:
"""
        
        # Call the LLM to extract information
        llm_response = await generate_text(extraction_prompt, max_tokens=2000, temperature=0.1)
        
        # Log the raw response
        logger.debug(f"Raw LLM response: {llm_response[:500]}...")
        
        # Parse the JSON response
        # Find JSON object in the response (it might have additional text)
        json_match = re.search(r'\{[\s\S]*\}', llm_response)
        
        if json_match:
            json_str = json_match.group(0)
            try:
                extracted_data = json.loads(json_str)
                
                # Validate and normalize the extracted data
                result = {
                    "bio": extracted_data.get("bio") or "",
                    "publications": extracted_data.get("publications") or [],
                    "email": extracted_data.get("email"),
                    "expertise": extracted_data.get("expertise") or [],
                    "achievements": extracted_data.get("achievements") or [],
                    "affiliation": extracted_data.get("affiliation") or affiliation,
                    "position": extracted_data.get("position")
                }
                
                # Log successful extraction
                logger.info(f"Successfully extracted researcher info from scraped content: {url}")
                
                # Check for None before calling len()
                bio_length = len(result["bio"]) if result["bio"] is not None else 0
                publications_count = len(result["publications"]) if result["publications"] is not None else 0
                expertise_count = len(result["expertise"]) if result["expertise"] is not None else 0
                achievements_count = len(result["achievements"]) if result["achievements"] is not None else 0
                
                log_api_call(
                    service_name="firecrawl",
                    operation="llm_extraction",
                    request_data={
                        "name": name,
                        "affiliation": affiliation,
                        "paper_title": paper_title,
                        "url": url
                    },
                    response_data={
                        "bio_length": bio_length,
                        "publications_count": publications_count,
                        "has_email": result["email"] is not None,
                        "expertise_count": expertise_count,
                        "achievements_count": achievements_count
                    }
                )
                
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {str(e)}")
                
                # Try to extract structured data from the unstructured response
                return extract_from_unstructured_response(llm_response, name, affiliation)
        else:
            logger.warning("No JSON object found in LLM response")
            return extract_from_unstructured_response(llm_response, name, affiliation)
        
    except Exception as e:
        error_msg = f"Error extracting researcher info with LLM: {str(e)}"
        logger.error(error_msg)
        
        # Log the error
        log_api_call(
            service_name="firecrawl",
            operation="llm_extraction_error",
            request_data={
                "name": name,
                "affiliation": affiliation,
                "paper_title": paper_title
            },
            error=error_msg
        )
        
        # Return empty structure
        return {
            "bio": "",
            "publications": [],
            "email": None,
            "expertise": [],
            "achievements": [],
            "affiliation": affiliation,
            "position": None
        }


def extract_from_unstructured_response(
    response: str,
    name: str,
    affiliation: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extract structured data from an unstructured LLM response.
    
    Args:
        response: The raw LLM response text
        name: Researcher name
        affiliation: Optional researcher affiliation
        
    Returns:
        Dictionary containing structured researcher information
    """
    result = {
        "bio": "",
        "publications": [],
        "email": None,
        "expertise": [],
        "achievements": [],
        "affiliation": affiliation,
        "position": None
    }
    
    try:
        # Extract email using regex
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, response)
        if emails:
            # Prioritize academic emails
            academic_emails = [
                email for email in emails
                if any(domain in email.lower() for domain in ACADEMIC_DOMAINS)
            ]
            
            if academic_emails:
                result["email"] = academic_emails[0]
            else:
                result["email"] = emails[0]
        
        # Extract sections based on headings
        sections = {
            "bio": ["bio:", "biography:", "about:", "description:"],
            "publications": ["publications:", "papers:", "articles:"],
            "expertise": ["expertise:", "interests:", "research interests:", "areas of expertise:"],
            "achievements": ["achievements:", "awards:", "honors:"],
            "affiliation": ["affiliation:", "university:", "institution:"],
            "position": ["position:", "title:", "role:"]
        }
        
        lines = response.split("\n")
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check if this line is a section header
            section_found = False
            for section, headers in sections.items():
                if any(line.lower().startswith(header) for header in headers):
                    current_section = section
                    section_found = True
                    # Extract content from the header line
                    for header in headers:
                        if line.lower().startswith(header):
                            content = line[len(header):].strip()
                            if content:
                                if section in ["publications", "expertise", "achievements"]:
                                    result[section].append(content)
                                else:
                                    result[section] = content
                            break
                    break
            
            # If we're in a section and this line is not a new section header, add content to it
            if current_section and not section_found:
                if current_section in ["publications", "expertise", "achievements"]:
                    # Handle list items
                    if line.startswith("-") or line.startswith("*") or (
                            len(line) > 2 and line[0].isdigit() and line[1] in [".", ")"]):
                        result[current_section].append(line.split(" ", 1)[1].strip())
                    elif current_section == "publications" and len(line) > 10:
                        # Publications are usually long text
                        result[current_section].append(line)
                    elif current_section in ["expertise", "achievements"] and "," in line:
                        # Comma-separated lists
                        items = [item.strip() for item in line.split(",")]
                        result[current_section].extend(items)
                else:
                    # For single-value fields, just use the line
                    result[current_section] = line
        
        # Add affiliation if found
        if not result["affiliation"] and affiliation:
            result["affiliation"] = affiliation
            
        return result
        
    except Exception as e:
        logger.error(f"Error extracting from unstructured response: {str(e)}")
        return result

async def crawl_and_extract_researcher_profile(
    name: str, 
    affiliation: Optional[str] = None, 
    paper_title: Optional[str] = None, 
    position: Optional[str] = None
) -> Dict[str, Any]:
    """
    Scrape web pages for researcher profiles and extract structured information using our LLM.
    This replaces the previous approach that relied on Firecrawl's extraction.
    
    Args:
        name: Researcher name
        affiliation: Optional researcher affiliation (university, institute)
        paper_title: Optional paper title to help identify the researcher
        position: Optional academic position (e.g., 'Professor', 'Assistant Professor')
        
    Returns:
        Dictionary containing researcher profile data including bio, publications, etc.
    """
    try:
        # Build search URLs
        encoded_name = quote(name)
        encoded_affiliation = quote(affiliation) if affiliation else ""
        paper_title_encoded = quote(paper_title) if paper_title else ""
        
        # List of URLs to scrape - focusing on most reliable sources
        urls_to_scrape = [
            f"https://scholar.google.com/scholar?q={encoded_name}",
            f"https://www.semanticscholar.org/search?q={encoded_name}&sort=relevance",
            f"https://dblp.org/search?q={encoded_name}"
        ]
        
        # Add academic profile if affiliation is provided
        if affiliation:
            # Add specific university profile searches
            clean_affiliation = encoded_affiliation.lower().replace("%20", "")
            if "stanford" in clean_affiliation:
                urls_to_scrape.append(f"https://profiles.stanford.edu/search?q={encoded_name}")
            elif "ucsd" in clean_affiliation or "san diego" in clean_affiliation:
                urls_to_scrape.append(f"https://profiles.ucsd.edu/search?q={encoded_name}")
            elif "mit" in clean_affiliation or "massachusetts institute" in clean_affiliation:
                urls_to_scrape.append(f"https://www.mit.edu/search/?q={encoded_name}")
            elif "berkeley" in clean_affiliation or "ucb" in clean_affiliation:
                urls_to_scrape.append(f"https://www.berkeley.edu/search?q={encoded_name}")
            elif "carnegie" in clean_affiliation or "cmu" in clean_affiliation:
                urls_to_scrape.append(f"https://www.cmu.edu/search/index.html?q={encoded_name}")
            
            # Regular Google search with affiliation
            urls_to_scrape.append(f"https://www.google.com/search?q={encoded_name}+{encoded_affiliation}+profile")
        else:
            # Regular Google search without affiliation
            urls_to_scrape.append(f"https://www.google.com/search?q={encoded_name}+researcher+profile")
        
        # Add paper title context if provided
        if paper_title:
            urls_to_scrape.append(f"https://scholar.google.com/scholar?q={encoded_name}+{paper_title_encoded}")
            urls_to_scrape.append(f"https://arxiv.org/search/?query={encoded_name}&searchtype=author")
            
        # Limit the number of URLs to try to avoid overwhelming the API
        urls_to_scrape = urls_to_scrape[:3]  # Only try 3 URLs maximum to prevent rate limits
        logger.info(f"Prepared {len(urls_to_scrape)} URLs for scraping")
        
        # Scrape each URL and collect the content
        scraped_contents = []
        for url in urls_to_scrape:
            try:
                logger.info(f"Scraping URL for {name}: {url}")
                
                # Add a delay between API calls to avoid rate limiting
                await asyncio.sleep(3)  # Sleep for 3 seconds between requests
                
                # Scrape the URL
                scrape_result = await crawl_url(url)
                
                # If successful, add to the results
                if scrape_result.get("success", False) and scrape_result.get("content"):
                    logger.info(f"Successfully scraped {url}")
                    scraped_contents.append(scrape_result)
                else:
                    logger.warning(f"Failed to scrape {url}: {scrape_result.get('error', 'Unknown error')}")
                
            except Exception as e:
                logger.error(f"Error scraping {url}: {str(e)}")
        
        # If no content was scraped, return empty structure
        if not scraped_contents:
            logger.warning(f"No content was successfully scraped for {name}")
            return {
                "bio": "",
                "publications": [],
                "email": None,
                "expertise": [],
                "achievements": [],
                "affiliation": affiliation,
                "position": position
            }
        
        # Extract researcher information from each scraped content
        extracted_results = []
        for content in scraped_contents:
            try:
                logger.info(f"Extracting information from {content.get('url', 'unknown')}")
                
                # Extract information using LLM
                extracted_info = await extract_researcher_info_with_llm(
                    content, name, affiliation, paper_title
                )
                
                # If we got meaningful results, add to the list
                if any(v for k, v in extracted_info.items() if k != "affiliation" and v):
                    extracted_results.append(extracted_info)
                    logger.info(f"Successfully extracted information from {content.get('url', 'unknown')}")
                else:
                    logger.warning(f"No meaningful information extracted from {content.get('url', 'unknown')}")
                
            except Exception as e:
                logger.error(f"Error extracting information from {content.get('url', 'unknown')}: {str(e)}")
        
        # If no information was extracted, return empty structure
        if not extracted_results:
            logger.warning(f"No information was successfully extracted for {name}")
            return {
                "bio": "",
                "publications": [],
                "email": None,
                "expertise": [],
                "achievements": [],
                "affiliation": affiliation,
                "position": position
            }
        
        # Merge all extracted results
        merged_result = {
            "bio": "",
            "publications": [],
            "email": None,
            "expertise": [],
            "achievements": [],
            "affiliation": affiliation,
            "position": position
        }
        
        # Track seen items to avoid duplicates
        seen_publications = set()
        seen_expertise = set()
        seen_achievements = set()
        
        # Combine all results, prioritizing the most complete
        for result in extracted_results:
            # Bio - take the longest one
            if result.get("bio") and len(result.get("bio", "")) > len(merged_result["bio"]):
                merged_result["bio"] = result["bio"]
                
            # Publications - deduplicate
            if result.get("publications"):
                for pub in result["publications"]:
                    # Create a key for deduplication (lowercase first 100 chars)
                    pub_key = pub.lower()[:100]
                    
                    if pub_key not in seen_publications:
                        seen_publications.add(pub_key)
                        merged_result["publications"].append(pub)
                        
            # Email - prioritize academic emails
            if result.get("email"):
                email = result["email"]
                current_email = merged_result["email"]
                
                # If we don't have an email yet or the new one is academic
                if not current_email or (
                    email and any(domain in email.lower() for domain in ACADEMIC_DOMAINS) and 
                    not (current_email and any(domain in current_email.lower() for domain in ACADEMIC_DOMAINS))
                ):
                    merged_result["email"] = email
                    
            # Expertise - deduplicate
            if result.get("expertise"):
                for exp in result["expertise"]:
                    exp_key = exp.lower() if isinstance(exp, str) else str(exp).lower()
                    if exp_key not in seen_expertise:
                        seen_expertise.add(exp_key)
                        merged_result["expertise"].append(exp)
                        
            # Achievements - deduplicate
            if result.get("achievements"):
                for ach in result["achievements"]:
                    ach_key = ach.lower() if isinstance(ach, str) else str(ach).lower()
                    if ach_key not in seen_achievements:
                        seen_achievements.add(ach_key)
                        merged_result["achievements"].append(ach)
                        
            # Affiliation - prioritize non-null values
            if result.get("affiliation") and not merged_result["affiliation"]:
                merged_result["affiliation"] = result["affiliation"]
                
            # Position - prioritize non-null values
            if result.get("position") and not merged_result["position"]:
                merged_result["position"] = result["position"]
        
        # Ensure we have affiliation and position
        if not merged_result["affiliation"] and affiliation:
            merged_result["affiliation"] = affiliation
            
        if not merged_result["position"] and position:
            merged_result["position"] = position
        
        # Log successful extraction
        logger.info(f"Successfully extracted and merged information for {name}")
        log_api_call(
            service_name="firecrawl",
            operation="crawl_and_extract_merged",
            request_data={
                "name": name,
                "affiliation": affiliation,
                "paper_title": paper_title,
                "position": position
            },
            response_data={
                "bio_length": len(merged_result["bio"]),
                "publications_count": len(merged_result["publications"]),
                "has_email": merged_result["email"] is not None,
                "expertise_count": len(merged_result["expertise"]),
                "achievements_count": len(merged_result["achievements"])
            }
        )
        
        return merged_result
        
    except Exception as e:
        error_msg = f"Error in crawl_and_extract_researcher_profile for {name}: {str(e)}"
        logger.error(error_msg)
        
        # Log the error
        log_api_call(
            service_name="firecrawl",
            operation="crawl_and_extract_error",
            request_data={
                "name": name,
                "affiliation": affiliation,
                "paper_title": paper_title,
                "position": position
            },
            error=error_msg
        )
        
        # Return minimal structure with provided values
        return {
            "bio": "",
            "publications": [],
            "email": None,
            "expertise": [],
            "achievements": [],
            "affiliation": affiliation,
            "position": position
        } 

async def extract_researcher_profile(
    name: str,
    affiliation: Optional[str] = None,
    paper_title: Optional[str] = None,
    position: Optional[str] = None,
    max_retries: int = 10,  # Increased from 5 to 10 to match test script
    retry_delay: int = 8    # Changed from 10 to 8 to match test script
) -> Dict[str, Any]:
    """
    Extract researcher profile information using the Firecrawl Extract API.
    
    This function utilizes the Firecrawl Extract API with web search enabled to get
    comprehensive information about the researcher from academic sources.
    
    Args:
        name: Name of the researcher
        affiliation: Academic affiliation (university, lab, etc.)
        paper_title: Title of a paper authored by the researcher
        position: Academic position or title
        max_retries: Maximum number of retries for extraction
        retry_delay: Delay between retries in seconds
        
    Returns:
        dict: Dictionary containing researcher profile information
    """
    logger = logging.getLogger(__name__)
    
    # Validate API key
    api_key = settings.FIRECRAWL_API_KEY
    if not api_key:
        error = "Firecrawl API key not configured. Set FIRECRAWL_API_KEY environment variable."
        logger.error(error)
        raise FirecrawlError(error)
    
    # Ensure API key has the correct format with fc- prefix
    if not api_key.startswith("fc-"):
        api_key = f"fc-{api_key}"
        logger.info("Added fc- prefix to API key")
    
    # Construct a list of relevant URLs for the researcher
    # Start with specific profile URLs that are most likely to have accurate information
    urls = []
    
    # Personal website variations
    name_no_spaces = name.replace(" ", "").lower()
    urls.append(f"https://{name_no_spaces}.com/*")
    urls.append(f"https://{name_no_spaces}.org/*")
    urls.append(f"https://{name_no_spaces}.edu/*")
    
    # Academic profile URLs
    urls.append(f"https://scholar.google.com/citations?user=*&hl=en&oi=ao&q={quote_plus(name)}")
    urls.append(f"https://arxiv.org/search/?query={quote_plus(name)}&searchtype=author")
    urls.append(f"https://orcid.org/orcid-search/search?q={quote_plus(name)}")
    
    # If affiliation is provided, add university-specific URLs
    if affiliation:
        # Common university profile URL patterns
        university_domain = get_university_domain(affiliation)
        if university_domain:
            urls.append(f"{university_domain}/profile/{name.replace(' ', '-').lower()}")
            urls.append(f"{university_domain}/people/{name.replace(' ', '-').lower()}")
            urls.append(f"{university_domain}/faculty/{name.replace(' ', '-').lower()}")
    
    # If paper_title is provided, add paper-specific URLs to help with identification
    if paper_title:
        encoded_paper = quote_plus(paper_title)
        urls.append(f"https://arxiv.org/search/?query={quote_plus(name)}+{encoded_paper}&searchtype=all")
    
    # Limit to max 5 URLs to avoid overwhelming the API
    urls = urls[:5]
    logger.info(f"Using {len(urls)} URLs for extraction")
    
    # Create extraction prompt
    extraction_prompt = f"""
    Extract comprehensive information about researcher {name}.
    
    Focus on finding:
    1. Biography and professional background
    2. Complete publication list with titles, years, and venues 
    3. Email contact information (preferably academic email)
    4. Areas of expertise and research interests
    5. Achievements, awards, grants, and recognitions
    6. Current affiliation and institution details
    7. Academic position (professor, associate, assistant, etc.)
    
    {f"Note: The researcher is believed to be affiliated with {affiliation}." if affiliation else ""}
    {f"Note: The researcher has authored a paper titled '{paper_title}'." if paper_title else ""}
    
    Return all available information in a structured format.
    """
    
    # Prepare the payload for the Extract API
    payload = {
        "urls": urls,
        "prompt": extraction_prompt.strip(),
        "enableWebSearch": True  # Simplifying to just enable web search without additional settings
    }
    
    logger.info(f"Initiating extraction for researcher {name} with {len(urls)} URLs and web search enabled")
    
    try:
        # Make the API request using aiohttp
        api_endpoint = "https://api.firecrawl.dev/v1/extract"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                api_endpoint,
                headers=headers,
                json=payload,
                timeout=60  # 60 second timeout
            ) as response:
                # Handle API response
                response_text = await response.text()
                
                # Check for rate limiting
                if response.status == 429:
                    logger.warning(f"Rate limit hit for {name}, waiting {retry_delay}s before retrying...")
                    await asyncio.sleep(retry_delay)
                    error = f"Rate limit exceeded for {name}: {response.status} {response_text[:500]}"
                    raise FirecrawlError(error)
                
                # Check for successful response
                if response.status != 200:
                    error = f"Failed to extract profile for {name}: {response.status} {response_text[:500]}"
                    logger.error(error)
                    raise FirecrawlError(error)
                
                # Parse the response
                try:
                    result = await response.json()
                    logger.debug(f"Extraction response structure: {list(result.keys())}")
                    
                    # Log API call details
                    log_api_call(
                        service_name="firecrawl",
                        operation="extract_profile",
                        request_data={"researcher": name, "urls": urls, "web_search_enabled": True},
                        response_data={
                            "status": response.status,
                            "content_length": len(response_text)
                        },
                        error=None,
                        status_code=response.status
                    )
                    
                    # Check if this is an initiation response with a job ID
                    if "id" in result and result.get("success", False):
                        # API returned a job ID, we need to poll for the result
                        job_id = result["id"]
                        logger.info(f"Extraction job initiated with ID: {job_id}, polling for results")
                        
                        # Poll for the result
                        poll_url = f"{api_endpoint}/{job_id}"
                        
                        for attempt in range(max_retries):
                            current_delay = retry_delay * (2 ** attempt)
                            logger.info(f"Waiting {current_delay}s before polling attempt {attempt + 1}/{max_retries}")
                            await asyncio.sleep(current_delay)
                            
                            async with session.get(
                                poll_url,
                                headers=headers,
                                timeout=60
                            ) as poll_response:
                                poll_text = await poll_response.text()
                                
                                if poll_response.status == 429:
                                    logger.warning(f"Rate limit hit when polling for job {job_id}, waiting before retry...")
                                    await asyncio.sleep(retry_delay)
                                    continue
                                
                                if poll_response.status != 200:
                                    logger.warning(f"Error polling for job {job_id}: {poll_response.status} {poll_text[:500]}")
                                    continue
                                
                                try:
                                    poll_result = await poll_response.json()
                                    status = poll_result.get("status", "")
                                    
                                    logger.info(f"Poll result for job {job_id}, status: {status}")
                                    
                                    if status == "completed":
                                        logger.info(f"Extraction job {job_id} completed successfully")
                                        # Use the completed result for further processing
                                        result = poll_result
                                        break
                                    elif status == "failed":
                                        error = f"Extraction job {job_id} failed: {poll_result.get('error', 'Unknown error')}"
                                        logger.error(error)
                                        raise FirecrawlError(error)
                                    else:
                                        logger.info(f"Job {job_id} still in progress (status: {status}), waiting...")
                                        continue
                                except json.JSONDecodeError:
                                    logger.warning(f"Invalid JSON in polling response: {poll_text[:500]}")
                                    continue
                        
                        # If we've exhausted our retries and still don't have a result
                        if attempt >= max_retries - 1 and status != "completed":
                            # Check if we have any partial data that can be used
                            if "data" in poll_result and isinstance(poll_result["data"], dict):
                                logger.info(f"Using partial data from incomplete job {job_id}")
                                result = poll_result  # Use the partial result
                            else:
                                error = f"Extraction job {job_id} did not complete after {max_retries} polling attempts and no partial data is available"
                                logger.error(error)
                                raise FirecrawlError(error)
                    
                    # Extract data from the response
                    extracted_data = {}
                    
                    # Handle different response formats based on the Firecrawl API documentation
                    if "data" in result and isinstance(result["data"], dict):
                        extracted_data = result["data"]
                        logger.info(f"Found structured data in response with keys: {list(extracted_data.keys())}")
                        # Debug log the actual data values
                        for key, value in extracted_data.items():
                            if isinstance(value, list):
                                logger.info(f"Key '{key}' contains a list with {len(value)} items")
                                if len(value) > 0:
                                    logger.info(f"First item sample: {value[0]}")
                            else:
                                logger.info(f"Key '{key}' value type: {type(value)}")
                    elif "content" in result:
                        extracted_data = {"bio": result.get("content", "")}
                        logger.info("Using content field as biography")
                    else:
                        logger.warning(f"Unexpected response format: {list(result.keys())}")
                        # Try to extract useful information from any available fields
                        for key, value in result.items():
                            if isinstance(value, dict):
                                extracted_data = value
                                logger.info(f"Using field '{key}' as data source")
                                break
                    
                    # Construct the researcher profile
                    researcher_info = {
                        "bio": extracted_data.get("biography", extracted_data.get("bio", extracted_data.get("about", ""))),
                        "publications": extracted_data.get("publications", extracted_data.get("papers", [])),
                        "email": extracted_data.get("email", extracted_data.get("contact_email", None)),
                        "expertise": extracted_data.get("areas_of_expertise", extracted_data.get("areasOfExpertise", extracted_data.get("expertise", extracted_data.get("research_interests", [])))),
                        "achievements": extracted_data.get("achievements", extracted_data.get("awards", extracted_data.get("honors", []))),
                        "affiliation": extracted_data.get("current_affiliation", extracted_data.get("currentAffiliation", extracted_data.get("affiliation", extracted_data.get("university", affiliation)))),
                        "position": extracted_data.get("academic_position", extracted_data.get("academicPosition", extracted_data.get("position", extracted_data.get("title", position))))
                    }
                    
                    # Handle case where affiliation is a dictionary
                    if isinstance(researcher_info["affiliation"], dict) and "name" in researcher_info["affiliation"]:
                        researcher_info["affiliation"] = researcher_info["affiliation"]["name"]
                    
                    # Ensure the correct data types
                    if researcher_info["publications"] and not isinstance(researcher_info["publications"], list):
                        researcher_info["publications"] = [researcher_info["publications"]] if isinstance(researcher_info["publications"], str) else []
                    
                    if researcher_info["expertise"] and not isinstance(researcher_info["expertise"], list):
                        researcher_info["expertise"] = [researcher_info["expertise"]] if isinstance(researcher_info["expertise"], str) else []
                    
                    if researcher_info["achievements"] and not isinstance(researcher_info["achievements"], list):
                        researcher_info["achievements"] = [researcher_info["achievements"]] if isinstance(researcher_info["achievements"], str) else []
                    
                    # Log extraction results
                    logger.info(f"Successfully extracted researcher profile for {name}")
                    logger.info(f"Bio length: {len(researcher_info['bio']) if researcher_info['bio'] else 0} chars")
                    logger.info(f"Publications: {len(researcher_info['publications'])}")
                    logger.info(f"Email found: {'Yes' if researcher_info['email'] else 'No'}")
                    logger.info(f"Expertise areas: {len(researcher_info['expertise'])}")
                    logger.info(f"Achievements: {len(researcher_info['achievements'])}")
                    logger.info(f"Affiliation: {researcher_info['affiliation'] or 'Not found'}")
                    logger.info(f"Position: {researcher_info['position'] or 'Not found'}")
                    
                    return researcher_info
                    
                except json.JSONDecodeError as e:
                    error = f"Invalid JSON response from Extract API: {str(e)}"
                    logger.error(error)
                    logger.error(f"Response first 500 chars: {response_text[:500]}")
                    raise FirecrawlError(error)
                    
    except aiohttp.ClientError as e:
        error_msg = f"HTTP client error while extracting profile for {name}: {str(e)}"
        logger.error(error_msg)
        raise FirecrawlError(error_msg)
    except asyncio.TimeoutError:
        error_msg = f"Timeout while extracting profile for {name}"
        logger.error(error_msg)
        raise FirecrawlError(error_msg)
    except Exception as e:
        error_msg = f"Error extracting researcher profile for {name}: {str(e)}"
        logger.error(error_msg)
        raise FirecrawlError(error_msg)
    
    # Default return structure if we somehow get here (should not happen due to exceptions)
    return {
        "bio": "",
        "publications": [],
        "email": None,
        "expertise": [],
        "achievements": [],
        "affiliation": affiliation,
        "position": position
    }

def get_university_domain(affiliation: str) -> Optional[str]:
    """
    Attempts to determine the domain for a university based on the affiliation string.
    
    Args:
        affiliation: The university or institution name
        
    Returns:
        A URL string for the university domain or None if not found
    """
    if not affiliation:
        return None
        
    # Clean the affiliation string
    clean_affiliation = affiliation.lower()
    
    # Map of known universities to their domains
    university_domains = {
        "stanford": "https://stanford.edu",
        "berkeley": "https://berkeley.edu",
        "mit": "https://mit.edu",
        "harvard": "https://harvard.edu",
        "princeton": "https://princeton.edu",
        "carnegie mellon": "https://cmu.edu",
        "cmu": "https://cmu.edu",
        "yale": "https://yale.edu",
        "columbia": "https://columbia.edu",
        "cornell": "https://cornell.edu",
        "caltech": "https://caltech.edu",
        "university of chicago": "https://uchicago.edu",
        "university of washington": "https://washington.edu",
        "university of california": "https://universityofcalifornia.edu",
        "university of michigan": "https://umich.edu",
        "university of toronto": "https://utoronto.ca",
        "university of british columbia": "https://ubc.ca",
        "oxford": "https://ox.ac.uk",
        "cambridge": "https://cam.ac.uk",
        "eth zurich": "https://ethz.ch",
        "university of montreal": "https://umontreal.ca",
        "montreal": "https://umontreal.ca",
        "mcgill": "https://mcgill.ca",
    }
    
    # Check for matches in our known university domains
    for key, domain in university_domains.items():
        if key in clean_affiliation:
            return domain
            
    # If no match found, try to construct a domain based on affiliation
    # This is a simple heuristic and may not work for all universities
    if "university" in clean_affiliation:
        # Extract university name - very simplistic approach
        univ_name = clean_affiliation.replace("university", "").replace("of", "").strip()
        if univ_name:
            # Remove spaces and special characters
            domain_part = "".join(c for c in univ_name if c.isalnum())
            if len(domain_part) > 3:  # Make sure we have a reasonable length domain
                return f"https://{domain_part}.edu"
    
    # No match found
    return None