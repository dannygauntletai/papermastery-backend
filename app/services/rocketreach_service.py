import httpx
import json
from typing import Dict, Any, Optional, List

from app.core.logger import get_logger
from app.core.config import get_settings
from app.core.exceptions import ExternalAPIError
from app.utils.api_logging import log_api_call

logger = get_logger(__name__)
settings = get_settings()

class RocketReachError(ExternalAPIError):
    """Exception raised for errors in the RocketReach API."""
    pass

async def fetch_researcher_email(
    name: str,
    affiliation: Optional[str] = None,
    position: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fetch researcher email using RocketReach API.
    
    Args:
        name: Full name of the researcher
        affiliation: University, institute, or company affiliation
        position: Academic position (e.g., 'Professor', 'Assistant Professor')
        
    Returns:
        Dictionary containing:
        - email: Primary email address found, or None if not found
        - emails: List of all email addresses found
        - work_email: Primary work email if found
        - personal_email: Primary personal email if found
        
    Raises:
        RocketReachError: If there's an error with the RocketReach API
    """
    try:
        api_key = settings.ROCKETREACH_API_KEY
        if not api_key:
            logger.error("RocketReach API key is not configured")
            raise RocketReachError("RocketReach API key is not configured")
        
        # Parse name to get first and last name
        name_parts = name.strip().split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        
        # Prepare search parameters
        params = {
            "name": name,
            "current_title": position if position else "Professor"
        }
        
        # RocketReach requires current_employer to be specified
        if affiliation:
            params["current_employer"] = affiliation
        else:
            # If no affiliation provided, try with "Academia" as a general search
            # This prevents the 400 Bad Request error seen in logs
            params["current_employer"] = "Academia"
            logger.info(f"No affiliation provided for {name}, using 'Academia' as default")
        
        # Log original request parameters
        log_api_call(
            service_name="rocketreach",
            operation="lookup_request",
            request_data={
                "name": name,
                "affiliation": affiliation,
                "position": position,
                "params": params
            }
        )
        
        # Step 1: Lookup person by name and employer
        async with httpx.AsyncClient(timeout=60.0) as client:
            # First, perform a lookup to find the profile ID
            lookup_response = await client.get(
                "https://api.rocketreach.co/v2/api/lookupProfile",
                headers={
                    "Content-Type": "application/json",
                    "Api-Key": api_key
                },
                params=params
            )
            
            # Log the lookup response
            lookup_error = None
            lookup_result = None
            
            if lookup_response.status_code not in [200, 201]:
                lookup_error = f"RocketReach lookup failed with status {lookup_response.status_code}: {lookup_response.text}"
                logger.warning(lookup_error)
                
                # Log the failed lookup
                log_api_call(
                    service_name="rocketreach",
                    operation="lookup",
                    request_data=params,
                    error=lookup_error,
                    status_code=lookup_response.status_code
                )
                
                if lookup_response.status_code == 429:
                    raise RocketReachError("Rate limit exceeded for RocketReach API")
                if lookup_response.status_code == 401:
                    raise RocketReachError("Invalid or unauthorized RocketReach API key")
                if lookup_response.status_code == 404:
                    return {
                        "email": None,
                        "emails": [],
                        "work_email": None,
                        "personal_email": None
                    }
                raise RocketReachError(f"RocketReach API error: {lookup_response.status_code} {lookup_response.text}")
            
            lookup_data = lookup_response.json()
            lookup_result = lookup_data
            
            # Log successful lookup
            log_api_call(
                service_name="rocketreach",
                operation="lookup",
                request_data=params,
                response_data=lookup_data,
                status_code=lookup_response.status_code
            )
            
            profile_id = lookup_data.get("id")
            
            if not profile_id:
                logger.warning(f"No RocketReach profile found for {name} at {affiliation or 'Academia'}")
                
                # Log the no profile found result
                log_api_call(
                    service_name="rocketreach",
                    operation="no_profile",
                    request_data={
                        "name": name,
                        "affiliation": affiliation,
                        "position": position,
                        "lookup_result": lookup_result
                    }
                )
                
                return {
                    "email": None,
                    "emails": [],
                    "work_email": None,
                    "personal_email": None
                }
            
            # Step 2: Get detailed profile data including all emails
            profile_response = await client.get(
                f"https://api.rocketreach.co/v2/api/profile/{profile_id}",
                headers={
                    "Api-Key": api_key
                }
            )
            
            # Log the profile request
            profile_error = None
            profile_data = None
            
            if profile_response.status_code != 200:
                profile_error = f"RocketReach profile retrieval failed with status {profile_response.status_code}: {profile_response.text}"
                logger.warning(profile_error)
                
                # Log the failed profile retrieval
                log_api_call(
                    service_name="rocketreach",
                    operation="profile",
                    request_data={"profile_id": profile_id},
                    error=profile_error,
                    status_code=profile_response.status_code
                )
                
                if profile_response.status_code == 429:
                    raise RocketReachError("Rate limit exceeded for RocketReach API")
                if profile_response.status_code == 401:
                    raise RocketReachError("Invalid or unauthorized RocketReach API key")
                raise RocketReachError(f"RocketReach API error: {profile_response.status_code} {profile_response.text}")
            
            profile_data = profile_response.json()
            
            # Log successful profile retrieval
            log_api_call(
                service_name="rocketreach",
                operation="profile",
                request_data={"profile_id": profile_id},
                response_data=profile_data,
                status_code=profile_response.status_code
            )
            
            # Extract email information
            emails = profile_data.get("emails", [])
            work_emails = [email["email"] for email in emails if email.get("type") == "work"]
            personal_emails = [email["email"] for email in emails if email.get("type") == "personal"]
            
            # Prioritize academic email addresses
            academic_emails = [
                email["email"] for email in emails 
                if any(academic_domain in email["email"].lower() for academic_domain in [".edu", ".ac.", "university", "college", "institute"])
            ]
            
            # Select primary email based on priority: academic > work > personal
            primary_email = None
            if academic_emails:
                primary_email = academic_emails[0]
            elif work_emails:
                primary_email = work_emails[0]
            elif personal_emails:
                primary_email = personal_emails[0]
            elif emails:
                primary_email = emails[0].get("email")
            
            # Prepare result
            result = {
                "email": primary_email,
                "emails": [email.get("email") for email in emails],
                "work_email": work_emails[0] if work_emails else None,
                "personal_email": personal_emails[0] if personal_emails else None
            }
            
            # Log the final processed result
            log_api_call(
                service_name="rocketreach",
                operation="processed_result",
                request_data={
                    "name": name,
                    "affiliation": affiliation,
                    "position": position
                },
                response_data=result
            )
            
            if primary_email:
                logger.info(f"Found email for {name}: {primary_email}")
            else:
                logger.info(f"No email found for {name}")
                
            return result
    
    except Exception as e:
        error_msg = f"Error fetching researcher email for {name}: {str(e)}"
        
        # Log any unexpected errors
        log_api_call(
            service_name="rocketreach",
            operation="error",
            request_data={
                "name": name,
                "affiliation": affiliation,
                "position": position
            },
            error=error_msg
        )
        
        if isinstance(e, RocketReachError):
            raise
        logger.error(error_msg)
        raise RocketReachError(f"Error fetching researcher email: {str(e)}")


async def search_researchers(
    affiliation: str,
    position: Optional[str] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Search for researchers at a specific institution using RocketReach.
    
    Args:
        affiliation: University or institution name
        position: Academic position (e.g., 'Professor', 'Assistant Professor')
        limit: Maximum number of results to return
        
    Returns:
        List of researcher profiles with basic information including email
        
    Raises:
        RocketReachError: If there's an error with the RocketReach API
    """
    try:
        api_key = settings.ROCKETREACH_API_KEY
        if not api_key:
            logger.error("RocketReach API key is not configured")
            raise RocketReachError("RocketReach API key is not configured")
        
        # Prepare search parameters
        params = {
            "employer": affiliation,
            "title": position if position else "Professor",
            "page_size": limit
        }
        
        # Clean up None values
        params = {k: v for k, v in params.items() if v is not None}
        
        # Log the search request
        log_api_call(
            service_name="rocketreach",
            operation="search_request",
            request_data={
                "affiliation": affiliation,
                "position": position,
                "limit": limit,
                "params": params
            }
        )
        
        # Execute search
        async with httpx.AsyncClient(timeout=60.0) as client:
            search_response = await client.post(
                "https://api.rocketreach.co/v2/api/search",
                headers={
                    "Content-Type": "application/json",
                    "Api-Key": api_key
                },
                json=params
            )
            
            # Log the search response
            search_error = None
            search_data = None
            
            if search_response.status_code != 200:
                search_error = f"RocketReach search failed with status {search_response.status_code}: {search_response.text}"
                logger.warning(search_error)
                
                # Log the failed search
                log_api_call(
                    service_name="rocketreach",
                    operation="search",
                    request_data=params,
                    error=search_error,
                    status_code=search_response.status_code
                )
                
                if search_response.status_code == 429:
                    raise RocketReachError("Rate limit exceeded for RocketReach API")
                if search_response.status_code == 401:
                    raise RocketReachError("Invalid or unauthorized RocketReach API key")
                raise RocketReachError(f"RocketReach API error: {search_response.status_code} {search_response.text}")
            
            search_data = search_response.json()
            
            # Log successful search
            log_api_call(
                service_name="rocketreach",
                operation="search",
                request_data=params,
                response_data=search_data,
                status_code=search_response.status_code
            )
            
            # Extract researcher profiles
            profiles = search_data.get("profiles", [])
            
            # Simplify and normalize the results
            simplified_profiles = []
            for profile in profiles:
                # Extract email if available
                emails = profile.get("emails", [])
                primary_email = emails[0].get("email") if emails else None
                
                # Create simplified profile
                simplified_profile = {
                    "id": profile.get("id"),
                    "name": f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip(),
                    "position": profile.get("current_title"),
                    "affiliation": profile.get("current_employer"),
                    "email": primary_email,
                    "linkedin_url": profile.get("linkedin_url"),
                    "profile_pic": profile.get("profile_pic")
                }
                
                simplified_profiles.append(simplified_profile)
            
            # Log the processed results
            log_api_call(
                service_name="rocketreach",
                operation="processed_search_results",
                request_data={
                    "affiliation": affiliation,
                    "position": position,
                    "limit": limit
                },
                response_data={
                    "count": len(simplified_profiles),
                    "profiles": simplified_profiles
                }
            )
            
            logger.info(f"Found {len(simplified_profiles)} researchers at {affiliation}")
            return simplified_profiles
    
    except Exception as e:
        error_msg = f"Error searching researchers at {affiliation}: {str(e)}"
        
        # Log any unexpected errors
        log_api_call(
            service_name="rocketreach",
            operation="search_error",
            request_data={
                "affiliation": affiliation,
                "position": position,
                "limit": limit
            },
            error=error_msg
        )
        
        if isinstance(e, RocketReachError):
            raise
        logger.error(error_msg)
        raise RocketReachError(f"Error searching researchers: {str(e)}") 