import asyncio
import os
import json
import logging
from app.services.firecrawl_service import extract_researcher_profile

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_extract():
    # Get a researcher's profile
    researcher_name = 'Geoffrey Hinton'
    affiliation = 'University of Toronto'
    
    # Extract the researcher profile
    logger.info(f'Extracting profile for: {researcher_name} from {affiliation}')
    result = await extract_researcher_profile(
        name=researcher_name,
        affiliation=affiliation
    )
    
    # Check if extraction was successful
    if result.get('success', False):
        logger.info('Extraction successful!')
        
        # Print the result
        print("Extracted profile:")
        print(json.dumps(result, indent=2))
        
        # Print specific fields
        print("\nBio:", result.get('bio', ''))
        print("\nPublications:", len(result.get('publications', [])))
        print("\nEmail:", result.get('email'))
        print("\nExpertise:", result.get('expertise', []))
        print("\nAchievements:", result.get('achievements', []))
        print("\nAffiliation:", result.get('affiliation'))
        print("\nPosition:", result.get('position'))
    else:
        logger.error(f'Extraction failed: {result.get("error", "Unknown error")}')

if __name__ == "__main__":
    asyncio.run(test_extract()) 