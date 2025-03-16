import asyncio
from typing import Dict, Any, Optional, List

from sqlalchemy.orm import Session
from fastapi import BackgroundTasks

from app.core.logger import get_logger
from app.core.config import get_settings
from app.core.exceptions import ExternalAPIError, DataCollectionError
from app.services.firecrawl_service import crawl_and_extract_researcher_profile, fallback_scrape_profile, extract_researcher_profile
from app.services.rocketreach_service import fetch_researcher_email, RocketReachError
from app.api.v1.models import ResearcherCreate, ResearcherCollectionRequest, Researcher
from app.database.supabase_client import create_researcher, get_researcher_by_id, get_researcher_by_email
from app.utils.api_logging import log_api_call

logger = get_logger(__name__)
settings = get_settings()

class OrchestratorError(ExternalAPIError):
    """Exception raised for errors in the data collection orchestration."""
    pass


async def collect_researcher_data(
    name: str,
    affiliation: Optional[str] = None,
    paper_title: Optional[str] = None,
    position: Optional[str] = None,
    researcher_id: Optional[str] = None,
    store_in_db: bool = True,
    email: Optional[str] = None
) -> Dict[str, Any]:
    """
    Collect researcher data from multiple sources.
    
    Args:
        name: Researcher name
        affiliation: Optional researcher affiliation
        paper_title: Optional paper title authored by the researcher
        position: Optional academic position
        researcher_id: Optional existing researcher ID to update
        store_in_db: Whether to store the data in the database
        email: Optional email if already known
        
    Returns:
        Dictionary with success flag and collected data
    """
    try:
        # Log the start of data collection
        logger.info(f"Starting data collection for researcher: {name}")
        
        # Log the initial request data
        log_api_call(
            service_name="data_collection_orchestrator",
            operation="start_collection",
            request_data={
                "name": name,
                "affiliation": affiliation,
                "paper_title": paper_title,
                "position": position,
                "researcher_id": researcher_id,
                "store_in_db": store_in_db,
                "email": email
            }
        )
            
        # If researcher_id is provided, check if researcher already exists
        if researcher_id:
            try:
                existing_researcher = await get_researcher_by_id(researcher_id)
                if existing_researcher:
                    # Log finding existing researcher
                    log_api_call(
                        service_name="data_collection_orchestrator",
                        operation="existing_researcher_found",
                        request_data={
                            "name": name,
                            "researcher_id": researcher_id
                        },
                        response_data={"researcher_id": existing_researcher["id"], "email": existing_researcher["email"]}
                    )
                    logger.info(f"Researcher with ID {researcher_id} already exists")
                    return {
                        "success": True,
                        "researcher_id": existing_researcher["id"],
                        "message": "Researcher already exists",
                        "researcher": existing_researcher
                    }
            except Exception as e:
                logger.warning(f"Error checking for existing researcher by ID: {str(e)}")
                # Continue with collection process
            
        # Step 1: Collect profile data using our comprehensive crawl and extract approach
        logger.info(f"Collecting profile data for {name}")
        profile_data = await safe_scrape_profile(name, affiliation, paper_title, position)
        
        # Log the profile data collection
        log_api_call(
            service_name="data_collection_orchestrator",
            operation="profile_data_collected",
            request_data={
                "name": name,
                "affiliation": affiliation,
                "paper_title": paper_title,
                "position": position
            },
            response_data=profile_data
        )
        
        # If email is provided, use it directly
        if email:
            profile_data["email"] = email
        
        # Step 2: Fetch researcher email if not found in profile data
        if not profile_data.get("email") and not email:
            logger.info(f"No email found in profile data, attempting to fetch from RocketReach")
            
            try:
                email_data = await fetch_researcher_email(
                    name=name,
                    affiliation=affiliation or profile_data.get("affiliation", "Academia"), 
                    position=position or profile_data.get("position", "Researcher")
                )
                
                # Log the email data collection
                log_api_call(
                    service_name="data_collection_orchestrator",
                    operation="email_data_collected",
                    request_data={
                        "name": name,
                        "affiliation": affiliation or profile_data.get("affiliation"),
                        "position": position or profile_data.get("position")
                    },
                    response_data=email_data
                )
                
                if email_data.get("email"):
                    profile_data["email"] = email_data["email"]
            except RocketReachError as e:
                # Log the error but continue without throwing an exception
                logger.warning(f"RocketReach API error: {str(e)}. Continuing with placeholder email.")
                log_api_call(
                    service_name="data_collection_orchestrator",
                    operation="rocketreach_error_handled",
                    request_data={
                        "name": name,
                        "affiliation": affiliation or profile_data.get("affiliation"),
                        "position": position or profile_data.get("position")
                    },
                    error=str(e)
                )
        
        # If still no email found, create a placeholder
        if not profile_data.get("email"):
            logger.warning(f"No email could be found for {name}")
            
            # Create a standardized placeholder
            domain = "academia.edu"
            name_parts = name.strip().lower().split()
            if len(name_parts) > 1:
                normalized_email = f"{name_parts[0]}.{name_parts[-1]}@{domain}"
            else:
                normalized_email = f"{name_parts[0]}@{domain}"
                
            profile_data["email"] = normalized_email
            profile_data["is_placeholder_email"] = True
            
            # Log the placeholder email creation
            log_api_call(
                service_name="data_collection_orchestrator",
                operation="placeholder_email_created",
                request_data={
                    "name": name
                },
                response_data={
                    "email": normalized_email
                }
            )
        
        # Step 3: Check if researcher already exists in database by email
        if profile_data.get("email"):
            existing_researcher = await get_researcher_by_email(profile_data["email"])
            if existing_researcher:
                # Log finding existing researcher by email
                log_api_call(
                    service_name="data_collection_orchestrator",
                    operation="existing_researcher_found_by_email",
                    request_data={
                        "email": profile_data["email"]
                    },
                    response_data={"researcher_id": existing_researcher["id"]}
                )
                logger.info(f"Researcher with email {profile_data['email']} already exists")
                return {
                    "success": True,
                    "researcher_id": existing_researcher["id"],
                    "message": "Researcher with this email already exists",
                    "researcher": existing_researcher
                }
                
        # Step 4: Create researcher in database if requested
        if store_in_db:
            # Prepare data structure for database
            bio = profile_data.get("bio", "")
            email = profile_data.get("email")
            is_placeholder_email = profile_data.get("is_placeholder_email", False)
            
            # Prepare the expertise array - Include publication titles
            expertise = profile_data.get("expertise", [])
            
            # Handle publications - normalize the format
            publications = []
            raw_publications = profile_data.get("publications", [])
            for pub in raw_publications:
                if isinstance(pub, dict) and "title" in pub:
                    pub_title = pub["title"]
                    if pub_title and len(pub_title) > 5:  # Basic validation
                        if pub_title not in expertise:
                            expertise.append(pub_title)
                        publications.append(pub_title)
                elif isinstance(pub, str) and len(pub) > 5:
                    if pub not in expertise:
                        expertise.append(pub)
                    publications.append(pub)
            
            # Prepare achievements array - Include affiliation and position if available
            achievements = profile_data.get("achievements", [])
            
            # Handle affiliation which could be a string or dictionary
            affiliation_value = profile_data.get("affiliation")
            if affiliation_value:
                # Convert affiliation to string representation if it's a dictionary
                affiliation_text = ""
                if isinstance(affiliation_value, dict):
                    # Extract information from the dictionary
                    if "institution" in affiliation_value:
                        affiliation_text = affiliation_value["institution"]
                        if "department" in affiliation_value:
                            affiliation_text += f", {affiliation_value['department']}"
                else:
                    # Use as is if it's already a string
                    affiliation_text = str(affiliation_value)
                
                # Only add if we have valid text and it's not already in achievements
                if affiliation_text and not any(affiliation_text.lower() in ach.lower() for ach in achievements):
                    achievements.append(f"Affiliated with {affiliation_text}")
            
            # Handle position similarly
            position_value = profile_data.get("position")
            if position_value and not any(str(position_value).lower() in ach.lower() for ach in achievements):
                achievements.append(f"Position: {position_value}")
            
            # Prepare database data - match the database schema
            db_data = {
                "name": name,
                "email": email,
                "bio": bio,
                "expertise": expertise,
                "achievements": achievements,
                "rate": 100,  # Default rate
                "verified": not is_placeholder_email,  # Set verified based on email confidence
                "availability": True  # Default availability
            }
            
            # Create researcher in database
            created_researcher = await create_researcher(db_data)
            
            # Log the successful creation
            log_api_call(
                service_name="data_collection_orchestrator",
                operation="researcher_created",
                request_data={
                    "name": name,
                    "email": email
                },
                response_data={
                    "researcher_id": created_researcher["id"],
                    "name": created_researcher["name"],
                    "email": created_researcher["email"]
                }
            )
            
            logger.info(f"Successfully created researcher: {created_researcher['name']} with ID {created_researcher['id']}")
            
            return {
                "success": True,
                "researcher_id": created_researcher["id"],
                "message": "Researcher data collected and saved to database",
                "researcher": created_researcher
            }
        else:
            # Return the collected data without storing in database
            return {
                "success": True,
                "researcher_id": None,
                "message": "Researcher data collected but not saved to database",
                "collected_data": profile_data
            }
    
    except Exception as e:
        error_message = f"Error collecting researcher data for {name}: {str(e)}"
        logger.error(error_message)
        
        # Log the error
        log_api_call(
            service_name="data_collection_orchestrator",
            operation="data_collection_error",
            request_data={
                "name": name,
                "affiliation": affiliation,
                "paper_title": paper_title,
                "position": position
            },
            error=error_message
        )
        
        return {
            "success": False,
            "message": f"Failed to collect researcher data: {str(e)}",
            "error": str(e)
        }


async def safe_scrape_profile(
    name: str,
    affiliation: Optional[str] = None,
    paper_title: Optional[str] = None,
    position: Optional[str] = None
) -> Dict[str, Any]:
    """
    Safely execute the scraping service with error handling.
    
    Args:
        name: Researcher name
        affiliation: Optional researcher affiliation 
        paper_title: Optional paper title
        position: Optional researcher position
        
    Returns:
        Dictionary with extracted data or empty structure if failed
    """
    try:
        # Log the scraping attempt
        logger.info(f"Attempting to scrape profile for {name}")
        
        # Use the same extraction method as our test script for consistency
        profile_data = await extract_researcher_profile(
            name=name, 
            affiliation=affiliation, 
            paper_title=paper_title, 
            position=position
        )
        
        # Log successful scraping
        logger.info(f"Successfully scraped profile data for {name}")
        
        return profile_data
        
    except Exception as e:
        error_message = f"Error scraping profile for {name}: {str(e)}"
        
        # Log the error for debugging
        log_api_call(
            service_name="data_collection_orchestrator",
            operation="profile_scrape_error",
            request_data={
                "name": name,
                "affiliation": affiliation,
                "paper_title": paper_title,
                "position": position
            },
            error=error_message
        )
        
        logger.error(error_message)
        
        # Return an empty structure with the same expected fields
        return {
            "name": name,
            "affiliation": affiliation,
            "position": position,
            "bio": "",
            "email": None,
            "publications": [],
            "expertise": [],
            "achievements": []
        }


async def safe_fetch_email(
    name: str, 
    affiliation: Optional[str] = None,
    position: Optional[str] = None
) -> Dict[str, Any]:
    """
    Safely execute the email fetching service with error handling.
    
    Args:
        name: Researcher name
        affiliation: Optional researcher affiliation
        position: Optional researcher position
        
    Returns:
        Dictionary with success flag and data or error message
    """
    try:
        data = await fetch_researcher_email(name, affiliation, position)
        return {
            "success": True,
            "data": data
        }
    except RocketReachError as e:
        logger.warning(f"RocketReach email fetch failed for {name}: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }
    except Exception as e:
        logger.error(f"Unexpected error in RocketReach email fetch for {name}: {str(e)}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


async def batch_collect_researcher_data(
    researchers: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Collect data for multiple researchers in parallel.
    
    Args:
        researchers: List of dictionaries, each containing researcher data
            
    Returns:
        List of results from collect_researcher_data for each researcher
    """
    tasks = []
    for researcher in researchers:
        task = asyncio.create_task(collect_researcher_data(
            name=researcher["name"],
            affiliation=researcher.get("affiliation"),
            paper_title=researcher.get("paper_title"),
            position=researcher.get("position"),
            researcher_id=researcher.get("researcher_id"),
            store_in_db=True,
            email=researcher.get("email")
        ))
        tasks.append(task)
    
    # Execute with concurrency limit
    semaphore = asyncio.Semaphore(3)  # Max 3 concurrent requests
    
    async def limited_collect(task):
        async with semaphore:
            return await task
    
    limited_tasks = [limited_collect(task) for task in tasks]
    results = await asyncio.gather(*limited_tasks, return_exceptions=True)
    
    # Process results, converting exceptions to error messages
    processed_results = []
    for i, result in enumerate(results):
        researcher = researchers[i]
        if isinstance(result, Exception):
            processed_results.append({
                "name": researcher["name"],
                "affiliation": researcher.get("affiliation", ""),
                "success": False,
                "error": str(result)
            })
        else:
            result["success"] = True
            processed_results.append(result)
    
    return processed_results


async def collect_for_institution(
    institution: str,
    position: Optional[str] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Collect data for multiple researchers at a specific institution.
    
    Args:
        institution: Name of the institution
        position: Optional academic position to filter by
        limit: Maximum number of researchers to collect data for
        
    Returns:
        List of results from collect_researcher_data for researchers at the institution
    """
    try:
        # First, search for researchers at the institution using RocketReach
        from app.services.rocketreach_service import search_researchers
        researchers = await search_researchers(
            affiliation=institution,
            position=position,
            limit=limit
        )
        
        # Then collect comprehensive data for each researcher
        researcher_data = []
        for researcher in researchers:
            researcher_data.append({
                "name": researcher["name"],
                "affiliation": researcher["affiliation"] or institution,
                "position": researcher["position"] or position,
                # RocketReach might already provide an email
                "email": researcher.get("email")
            })
        
        # Batch collect data for all researchers
        results = await batch_collect_researcher_data(researcher_data)
        return results
        
    except Exception as e:
        logger.error(f"Error collecting data for institution {institution}: {str(e)}")
        raise OrchestratorError(f"Institution data collection failed: {str(e)}") 