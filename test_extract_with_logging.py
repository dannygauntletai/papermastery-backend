import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional

from dotenv import load_dotenv

# Configure logging
def setup_logging():
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"{log_dir}/extract_test_{timestamp}.log"
    
    # Set up the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Clear existing handlers
    root_logger.handlers = []
    
    # Create handlers
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    
    # Create formatters
    console_format = logging.Formatter('%(levelname)s - %(message)s')
    file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Set formatters
    console_handler.setFormatter(console_format)
    file_handler.setFormatter(file_format)
    
    # Add handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    return root_logger

# Import after logging setup to capture import-time logs
from app.services.firecrawl_service import extract_researcher_profile, FirecrawlError

async def test_extract_researcher_profile():
    """Test the researcher profile extraction function with detailed logging"""
    try:
        # Using the researcher information provided
        researcher_name = "Shibo Hao"
        affiliation = "Meta"
        paper_title = "Training Large Language Models to Reason in a Continuous Latent Space"
        
        logging.info(f"Testing extraction for researcher: {researcher_name}, affiliation: {affiliation}")
        logging.info(f"Using paper title: {paper_title} to help with identification")
        
        # Test extract_researcher_profile function with enhanced progress tracking
        profile_data = await extract_researcher_profile(
            name=researcher_name,
            affiliation=affiliation,
            paper_title=paper_title,
            max_retries=10,  # Using the new default of 10 retries for maximum extraction success
            retry_delay=8   # Slightly increased delay to reduce rate limiting risks
        )
        
        # Log extraction results with field counts
        logging.info(f"Extraction completed for {researcher_name}")
        
        # Log bio length and snippet
        bio = profile_data.get("bio", "")
        bio_length = len(bio) if bio else 0
        bio_snippet = bio[:150] + "..." if bio_length > 150 else bio
        logging.info(f"Bio: {bio_length} chars. Snippet: {bio_snippet}")
        
        # Log publications count and sample
        publications = profile_data.get("publications", [])
        pub_count = len(publications) if publications else 0
        pub_sample = publications[:3] if pub_count > 0 else []
        logging.info(f"Publications: {pub_count} found. Sample: {pub_sample}")
        
        # Log email
        email = profile_data.get("email", None)
        logging.info(f"Email: {email}")
        
        # Log expertise
        expertise = profile_data.get("expertise", [])
        exp_count = len(expertise) if expertise else 0
        logging.info(f"Expertise: {exp_count} areas. Items: {expertise}")
        
        # Log achievements
        achievements = profile_data.get("achievements", [])
        ach_count = len(achievements) if achievements else 0
        logging.info(f"Achievements: {ach_count} found. Items: {achievements}")
        
        # Log affiliation and position
        affiliation_result = profile_data.get("affiliation", None)
        position = profile_data.get("position", None)
        logging.info(f"Affiliation: {affiliation_result}")
        logging.info(f"Position: {position}")
        
        # Print complete profile data for detailed inspection
        logging.debug(f"Complete profile data: {json.dumps(profile_data, indent=2)}")
        
        # Summary evaluation of extraction effectiveness
        fields_with_data = sum(1 for v in profile_data.values() if v and (not isinstance(v, list) or len(v) > 0))
        logging.info(f"Extraction effectiveness: {fields_with_data}/7 fields populated with data")
        
        # Print a final summary with colored output if supported
        print("\n" + "="*80)
        print("\033[1;32mEXTRACTION SUMMARY FOR SHIBO HAO\033[0m")
        print("="*80)
        print(f"\033[1mResearcher:\033[0m {researcher_name}")
        print(f"\033[1mAffiliation:\033[0m {affiliation_result or affiliation}")
        print(f"\033[1mPosition:\033[0m {position or 'Not found'}")
        print(f"\033[1mEmail:\033[0m {email or 'Not found'}")
        print(f"\033[1mBio Length:\033[0m {bio_length} characters")
        print(f"\033[1mPublications Found:\033[0m {pub_count}")
        print(f"\033[1mExpertise Areas Found:\033[0m {exp_count}")
        print(f"\033[1mAchievements Found:\033[0m {ach_count}")
        
        # Calculate success score
        success_score = min(10, int((fields_with_data/7)*10))
        score_color = "\033[1;31m" if success_score < 5 else "\033[1;33m" if success_score < 8 else "\033[1;32m"
        print(f"\n\033[1mExtraction Success Score:\033[0m {score_color}{success_score}/10\033[0m")
        
        if success_score >= 8:
            print("\n\033[1;32mWeb extraction with FirecrawlAPI was successful!\033[0m")
            print("The enableWebSearch parameter helped gather comprehensive researcher data.")
        elif success_score >= 5:
            print("\n\033[1;33mWeb extraction was partially successful.\033[0m")
            print("Some fields were populated, but more data might be available with tweaked prompts.")
        else:
            print("\n\033[1;31mWeb extraction was limited.\033[0m")
            print("Consider trying different URLs or more specific prompts to improve results.")
        
        print("="*80)
        
    except FirecrawlError as e:
        logging.error(f"FirecrawlError: {str(e)}")
        print(f"\n\033[1;31mExtraction failed with error:\033[0m {str(e)}")
        
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        print(f"\n\033[1;31mUnexpected error:\033[0m {str(e)}")

async def main():
    """Main entry point for testing"""
    logger = setup_logging()
    logger.info("Starting extraction test script")
    
    # Load environment variables
    load_dotenv()
    logger.info("Environment variables loaded")
    
    # Run the test
    await test_extract_researcher_profile()
    
    logger.info("Test script completed")

if __name__ == "__main__":
    asyncio.run(main()) 