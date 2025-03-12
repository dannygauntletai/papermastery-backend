import os
from dotenv import load_dotenv
from openai import OpenAI
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

def test_openai_api():
    """Test the OpenAI API key by making a simple completion request."""
    try:
        # Get API key from environment
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY environment variable is not set")
            return False
        
        logger.info(f"Using OpenAI API key: {api_key[:8]}...")
        
        # Initialize OpenAI client
        client = OpenAI(api_key=api_key)
        
        # Make a simple completion request
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello, are you working correctly?"}
            ]
        )
        
        # Log the response
        logger.info(f"OpenAI API response: {response.choices[0].message.content}")
        
        return True
    except Exception as e:
        logger.error(f"Error testing OpenAI API: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("Testing OpenAI API...")
    success = test_openai_api()
    if success:
        logger.info("OpenAI API test successful!")
    else:
        logger.error("OpenAI API test failed!") 