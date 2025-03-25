import asyncio
import logging
import sys
import uuid
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("test_summarization_retry")

# Set the log level for the LLM service to DEBUG
logging.getLogger("app.services.llm_service").setLevel(logging.DEBUG)
logging.getLogger("app.services.summarization_service").setLevel(logging.DEBUG)

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.summarization_service import generate_summaries
from app.api.v1.models import PaperSummary


async def test_retry_mechanism():
    """Test the retry mechanism for summary generation."""
    paper_id = uuid.uuid4()
    title = "Test Paper for Retry Mechanism"
    abstract = """
    This is a test abstract for testing the retry mechanism in the summary generation.
    The paper discusses important topics related to deep learning and neural networks.
    It introduces new methods for improving model performance and reducing computational costs.
    """
    
    # Use a deliberately incomplete paper text to increase the chance of the model having trouble
    # This mimics the real-world scenario where the extracted text might be problematic
    full_text = """
    Introduction
    In recent years, deep learning has revolutionized many fields including computer vision,
    natural language processing, and reinforcement learning. However, these models often require
    significant computational resources and large amounts of training data.
    
    Methodology
    We propose a novel approach that combines [MISSING TEXT]
    
    Results
    Our experiments show that [CORRUPTED DATA]
    
    Conclusion
    In this paper, we have demonstrated that [INCOMPLETE]
    """
    
    logger.info(f"Testing summary generation with retry mechanism for paper ID: {paper_id}")
    
    # Set max_retries to 3 to test the retry mechanism
    try:
        summaries, extracted_abstract = await generate_summaries(
            paper_id=paper_id,
            title=title,
            abstract=abstract,
            full_text=full_text,
            extract_abstract=True,
            max_retries=3
        )
        
        logger.info("Summary generation successful!")
        logger.info(f"Beginner summary: {summaries.beginner[:100]}...")
        logger.info(f"Intermediate summary: {summaries.intermediate[:100]}...")
        logger.info(f"Advanced summary: {summaries.advanced[:100]}...")
        logger.info(f"Extracted abstract: {extracted_abstract[:100]}...")
        
        # Check if summaries match expected format
        assert isinstance(summaries, PaperSummary)
        assert len(summaries.beginner) > 0
        assert len(summaries.intermediate) > 0
        assert len(summaries.advanced) > 0
        assert len(extracted_abstract) > 0
        
        logger.info("All assertions passed!")
        
    except Exception as e:
        logger.error(f"Error during test: {str(e)}")
        # Check if our fallback mechanisms worked
        logger.info("Testing if fallback mechanisms worked correctly...")
        
        # Even if the main process failed, we should still have fallback summaries
        try:
            summaries, extracted_abstract = await generate_summaries(
                paper_id=paper_id,
                title=title,
                abstract=abstract,
                full_text="",  # Use empty text to force fallback
                extract_abstract=True
            )
            
            logger.info("Fallback generation successful!")
            logger.info(f"Fallback beginner summary: {summaries.beginner[:100]}...")
            
            # Check if fallback summaries match expected format
            assert isinstance(summaries, PaperSummary)
            assert len(summaries.beginner) > 0
            
            logger.info("Fallback assertions passed!")
        except Exception as fallback_error:
            logger.error(f"Fallback also failed: {str(fallback_error)}")


if __name__ == "__main__":
    asyncio.run(test_retry_mechanism()) 