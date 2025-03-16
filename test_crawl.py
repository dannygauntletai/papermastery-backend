import asyncio
import os
import json
import logging
from app.services.firecrawl_service import crawl_url, extract_researcher_info_with_llm

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_crawl():
    # Get a researcher's profile
    researcher_name = 'Geoffrey Hinton'
    # Try a direct website instead of a search page
    url = 'https://www.cs.toronto.edu/~hinton/'
    
    # Crawl the URL with more retries and longer delays
    logger.info(f'Crawling URL: {url}')
    result = await crawl_url(url, max_retries=5, retry_delay=10)
    
    # Check if crawl was successful
    if result['success']:
        logger.info('Crawl successful!')
        
        # Print the raw response for inspection
        print("Raw API response:")
        print(json.dumps(result, indent=2))
        
        # Extract researcher info
        researcher_info = await extract_researcher_info_with_llm(result, researcher_name)
        logger.info('Extracted info:')
        logger.info(researcher_info)
    else:
        logger.error(f'Crawl failed: {result.get("error", "Unknown error")}')

if __name__ == "__main__":
    asyncio.run(test_crawl()) 