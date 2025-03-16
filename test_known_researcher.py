import os
import asyncio
import logging
from dotenv import load_dotenv
from app.services.firecrawl_service import extract_researcher_profile
from app.core.logger import get_logger

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler()
    ]
)

# Get logger
logger = get_logger(__name__)

async def test_extraction():
    try:
        print("Config: Using OpenAI API key from .env:", os.getenv("OPENAI_API_KEY")[:10] + "..." if os.getenv("OPENAI_API_KEY") else "Not found")
        print("Config: Using Gemini API key from .env:", os.getenv("GEMINI_API_KEY")[:10] + "..." if os.getenv("GEMINI_API_KEY") else "Not found")
        print("Config: Using Firecrawl API key from .env:", os.getenv("FIRECRAWL_API_KEY")[:10] + "..." if os.getenv("FIRECRAWL_API_KEY") else "Not found")
        
        logger.info("Starting extraction test script")
        logger.info("Environment variables loaded")
        
        # Test with a well-known researcher
        researcher_name = "Yoshua Bengio"
        affiliation = "University of Montreal"
        paper_title = "Attention is All You Need"
        
        logger.info(f"Testing extraction for researcher: {researcher_name}, affiliation: {affiliation}")
        logger.info(f"Using paper title: {paper_title} to help with identification")
        
        # Call the extraction function
        result = await extract_researcher_profile(
            name=researcher_name,
            affiliation=affiliation,
            paper_title=paper_title
        )
        
        # Print the result
        logger.info("Extraction completed successfully!")
        logger.info(f"Bio: {result.get('bio', '')[:100]}...")
        logger.info(f"Email: {result.get('email', '')}")
        logger.info(f"Affiliation: {result.get('affiliation', '')}")
        logger.info(f"Position: {result.get('position', '')}")
        logger.info(f"Publications: {len(result.get('publications', []))} found")
        logger.info(f"Expertise areas: {len(result.get('expertise', []))} found")
        logger.info(f"Achievements: {len(result.get('achievements', []))} found")
        
        # Print some publications if available
        if result.get('publications'):
            logger.info("Sample publications:")
            for i, pub in enumerate(result.get('publications')[:3], 1):
                if isinstance(pub, dict) and 'title' in pub:
                    logger.info(f"{i}. {pub['title']}")
                else:
                    logger.info(f"{i}. {pub}")
        
        # Print some expertise areas if available
        if result.get('expertise'):
            logger.info("Sample expertise areas:")
            for i, area in enumerate(result.get('expertise')[:3], 1):
                logger.info(f"{i}. {area}")
        
        logger.info("Test script completed")
        
    except Exception as e:
        logger.error(f"Error in test script: {str(e)}")
        logger.error("Extraction failed with error:", exc_info=True)
        print(f"Extraction failed with error: {str(e)}")

if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    
    # Run the test
    asyncio.run(test_extraction()) 