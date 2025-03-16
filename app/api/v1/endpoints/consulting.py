from typing import Dict, Any, List, Optional, Union
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
import datetime

from app.api.v1.models import (
    ResearcherCreate, 
    ResearcherResponse, 
    ResearcherCollectionRequest,
    ResearcherCollectionResponse,
    SessionCreate,
    SessionResponse, 
    OutreachRequestCreate,
    OutreachRequestResponse,
    SubscriptionResponse
)
from app.core.logger import get_logger
from app.services.data_collection_orchestrator import (
    collect_researcher_data,
    batch_collect_researcher_data,
    collect_for_institution
)
from app.services.consulting_service import (
    get_researcher,
    get_researcher_by_paper_id,
    create_or_update_researcher_profile,
    request_researcher_outreach,
    handle_researcher_response,
    book_session,
    update_session_status,
    get_researcher_sessions,
    get_user_sessions,
    create_user_subscription
)
from app.database.supabase_client import (
    get_researcher_by_email
)
from app.core.exceptions import SupabaseError

logger = get_logger(__name__)

router = APIRouter(prefix="/consulting", tags=["consulting"])


@router.post("/researchers/collect", response_model=ResearcherCollectionResponse, status_code=status.HTTP_200_OK)
async def collect_researcher_data_endpoint(
    request: ResearcherCollectionRequest,
    background_tasks: BackgroundTasks
) -> ResearcherCollectionResponse:
    """
    Collect researcher data from various sources (Firecrawl, RocketReach, Tavily).
    
    This endpoint initiates the collection of researcher data in the background:
    1. Scrapes profiles with Firecrawl with web search enabled
    2. Fetches emails with RocketReach (if email is missing) 
    3. Stores the result in Supabase for realtime updates
    
    The frontend should use Supabase realtime subscription to get updates.
    """
    try:
        # Always process the data collection in the background
        # Override the request's run_in_background value
        request.run_in_background = True
        
        # Check if researcher already exists by email (if email is provided)
        existing_researcher = None
        existing_researcher_id = None
        if request.email:
            existing_researcher = await get_researcher_by_email(request.email)
            if existing_researcher:
                existing_researcher_id = existing_researcher.get("id")
        
        # Add the background task
        background_tasks.add_task(
            handle_researcher_collection,
            request
        )
        
        # Return minimal information - just status and researcher ID
        return ResearcherCollectionResponse(
            success=True,
            message=f"Researcher data collection started for {request.name}",
            data={
                "status": "processing",
                "researcher_id": existing_researcher_id
            }
        )
            
    except Exception as e:
        logger.error(f"Error starting researcher data collection: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting researcher data collection: {str(e)}"
        )


@router.post("/researchers/batch-collect", response_model=List[ResearcherCollectionResponse], status_code=status.HTTP_200_OK)
async def batch_collect_researchers_endpoint(
    requests: List[ResearcherCollectionRequest],
    background_tasks: BackgroundTasks
) -> List[ResearcherCollectionResponse]:
    """
    Collect data for multiple researchers in batch.
    
    This endpoint processes multiple researcher data collection requests:
    1. Validates each request
    2. Processes them in parallel
    3. Returns results for each researcher
    
    The batch collection can be run in the background if specified in any request.
    """
    try:
        # Check if any request should run in background
        run_in_background = any(request.run_in_background for request in requests)
        
        if run_in_background:
            # Process the batch collection in the background
            background_tasks.add_task(
                handle_batch_collection,
                requests
            )
            
            return [
                ResearcherCollectionResponse(
                    success=True,
                    message=f"Data collection for researcher {request.name} started in background",
                    data={
                        "status": "background_started",
                        "researcher_id": None,
                        "name": request.name,
                        "affiliation": request.affiliation,
                    }
                )
                for request in requests
            ]
        else:
            # Process the batch collection synchronously
            results = []
            researchers_data = [
                {
                    "name": req.name,
                    "affiliation": req.affiliation,
                    "paper_title": req.paper_title,
                    "position": req.position,
                    "researcher_id": req.researcher_id,
                }
                for req in requests
            ]
            
            batch_results = await batch_collect_researcher_data(researchers_data)
            
            # Format the results
            for i, result in enumerate(batch_results):
                request = requests[i]
                
                if isinstance(result, dict) and result.get("success", False):
                    results.append(
                        ResearcherCollectionResponse(
                            success=True,
                            message=f"Successfully collected data for researcher {request.name}",
                            data=result
                        )
                    )
                else:
                    error_msg = result.get("error", "Unknown error") if isinstance(result, dict) else str(result)
                    results.append(
                        ResearcherCollectionResponse(
                            success=False,
                            message=f"Failed to collect data for researcher {request.name}: {error_msg}",
                            data={
                                "status": "failed",
                                "error": error_msg,
                                "name": request.name,
                                "affiliation": request.affiliation,
                            }
                        )
                    )
            
            return results
            
    except Exception as e:
        logger.error(f"Error in batch collection of researcher data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error in batch collection: {str(e)}"
        )


@router.post("/researchers/collect-by-institution", response_model=List[ResearcherCollectionResponse], status_code=status.HTTP_200_OK)
async def collect_institution_researchers_endpoint(
    institution: str,
    position: Optional[str] = None,
    limit: int = 10,
    background_tasks: BackgroundTasks = None,
    run_in_background: bool = False
) -> List[ResearcherCollectionResponse]:
    """
    Collect data for multiple researchers at a specific institution.
    
    This endpoint searches for researchers at the institution and collects their data:
    1. Searches for researchers using RocketReach
    2. Collects detailed data for each researcher found
    3. Returns results for all researchers
    
    The collection can be run in the background if specified.
    """
    try:
        if run_in_background and background_tasks:
            # Process the institution collection in the background
            background_tasks.add_task(
                handle_institution_collection,
                institution=institution,
                position=position,
                limit=limit
            )
            
            return [
                ResearcherCollectionResponse(
                    success=True,
                    message=f"Data collection for institution {institution} started in background",
                    data={
                        "status": "background_started",
                        "institution": institution,
                        "position": position,
                    }
                )
            ]
        else:
            # Process the institution collection synchronously
            results = await handle_institution_collection(
                institution=institution,
                position=position,
                limit=limit
            )
            
            # Format the results
            formatted_results = []
            for result in results:
                if isinstance(result, dict) and result.get("success", False):
                    formatted_results.append(
                        ResearcherCollectionResponse(
                            success=True,
                            message=f"Successfully collected data for researcher at {institution}",
                            data=result
                        )
                    )
                else:
                    error_msg = result.get("error", "Unknown error") if isinstance(result, dict) else str(result)
                    formatted_results.append(
                        ResearcherCollectionResponse(
                            success=False,
                            message=f"Failed to collect data: {error_msg}",
                            data={
                                "status": "failed",
                                "error": error_msg,
                                "institution": institution,
                            }
                        )
                    )
            
            return formatted_results
            
    except Exception as e:
        logger.error(f"Error collecting researchers for institution {institution}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error collecting institution researchers: {str(e)}"
        )


@router.get("/researchers/{researcher_id}", response_model=ResearcherResponse)
async def get_researcher_endpoint(
    researcher_id: UUID
) -> ResearcherResponse:
    """Get researcher profile by ID."""
    try:
        researcher = await get_researcher(researcher_id)
        return ResearcherResponse(
            success=True,
            message="Researcher found",
            data=researcher
        )
    except SupabaseError as e:
        logger.error(f"Error getting researcher: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error getting researcher: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving researcher: {str(e)}"
        )


@router.get("/researchers/paper/{paper_id}", response_model=ResearcherResponse)
async def get_researcher_by_paper_endpoint(
    paper_id: UUID
) -> ResearcherResponse:
    """Get researcher profile associated with a paper."""
    try:
        researcher = await get_researcher_by_paper_id(paper_id)
        if not researcher:
            return ResearcherResponse(
                success=False,
                message=f"No researcher found for paper {paper_id}",
                data=None
            )
        
        return ResearcherResponse(
            success=True,
            message="Researcher found for paper",
            data=researcher
        )
    except SupabaseError as e:
        logger.error(f"Error getting researcher for paper: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error getting researcher for paper: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving researcher for paper: {str(e)}"
        )


# Helper functions for background tasks

async def handle_researcher_collection(
    request: ResearcherCollectionRequest
) -> Dict[str, Any]:
    """
    Handle the collection of researcher data in a background task.
    This function is designed to be robust - it will log errors but not crash
    the background task, ensuring data is saved to Supabase for realtime updates.
    """
    try:
        # Record start time
        start_time = datetime.datetime.now()
        
        # Log background task started
        logger.info(f"Background task started for researcher collection: {request.name}")
        
        # Check if researcher already exists by email (if email is provided)
        existing_researcher = None
        if request.email:
            existing_researcher = await get_researcher_by_email(request.email)
        
        # Set researcher_id if found
        researcher_id = None
        if existing_researcher:
            researcher_id = existing_researcher.get("id")
            
        # Collect researcher data from various sources
        result = await collect_researcher_data(
            name=request.name,
            affiliation=request.affiliation,
            paper_title=request.paper_title,
            position=request.position,
            researcher_id=researcher_id,
            store_in_db=True
        )
        
        logger.info(f"Successfully collected data for researcher {request.name}")
        
        # Calculate processing time
        processing_time = datetime.datetime.now() - start_time
        processing_seconds = processing_time.total_seconds()
        
        # If we have researcher data in the result, return it in the expected format
        if "researcher" in result and result.get("success", False):
            researcher = result["researcher"]
            
            # Return the researcher data using the fields from the database
            return {
                "status": "complete",
                "researcher_id": researcher.get("id"),
                "name": researcher.get("name"),
                "email": researcher.get("email"),
                "affiliation": researcher.get("affiliation"),
                "expertise": researcher.get("expertise", []),
                "achievements": researcher.get("achievements", []),
                "bio": researcher.get("bio", ""),
                "publications": researcher.get("publications", []),
                "collected_at": researcher.get("created_at"),
                "processing_time_seconds": processing_seconds,
                "processing_started": start_time.isoformat()
            }
        
        # Fallback to returning the raw result if no researcher data was found
        return {
            "status": "complete",
            "researcher_id": result.get("researcher_id"),
            "name": request.name,
            "email": result.get("collected_data", {}).get("email") if "collected_data" in result else None,
            "affiliation": request.affiliation,
            "expertise": result.get("collected_data", {}).get("expertise", []) if "collected_data" in result else [],
            "achievements": result.get("collected_data", {}).get("achievements", []) if "collected_data" in result else [],
            "bio": result.get("collected_data", {}).get("bio", "") if "collected_data" in result else "",
            "publications": result.get("collected_data", {}).get("publications", []) if "collected_data" in result else [],
            "processing_time_seconds": processing_seconds,
            "processing_started": start_time.isoformat()
        }
    except Exception as e:
        # Log the error but don't crash the background task
        logger.error(f"Error collecting data for researcher {request.name}: {str(e)}")
        
        # Return error information in a way that won't break the client
        return {
            "status": "error",
            "name": request.name,
            "affiliation": request.affiliation,
            "error_message": str(e),
            "processing_started": datetime.datetime.now().isoformat()
        }


async def handle_batch_collection(
    requests: List[ResearcherCollectionRequest]
) -> List[Dict[str, Any]]:
    """Handle batch collection of researcher data."""
    try:
        # Convert requests to the format expected by batch_collect_researcher_data
        researchers_data = [
            {
                "name": req.name,
                "affiliation": req.affiliation,
                "paper_title": req.paper_title,
                "position": req.position,
                "researcher_id": req.researcher_id,
            }
            for req in requests
        ]
        
        # Collect data for all researchers
        batch_results = await batch_collect_researcher_data(researchers_data)
        
        logger.info(f"Completed batch collection for {len(requests)} researchers")
        return batch_results
    except Exception as e:
        logger.error(f"Error in batch collection: {str(e)}")
        raise e


async def handle_institution_collection(
    institution: str,
    position: Optional[str] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """Handle collection of researcher data for an institution."""
    try:
        # Collect data for researchers at the institution
        results = await collect_for_institution(
            institution=institution,
            position=position,
            limit=limit
        )
        
        logger.info(f"Completed collection for institution {institution} with {len(results)} researchers")
        return results
    except Exception as e:
        logger.error(f"Error collecting for institution {institution}: {str(e)}")
        raise e 