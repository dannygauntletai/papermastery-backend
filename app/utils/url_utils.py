import re
from typing import Dict, Optional

from app.core.logger import get_logger

logger = get_logger(__name__)

async def extract_paper_id_from_url(url: str) -> Dict[str, Optional[str]]:
    """
    Extract paper identifiers from a URL.
    
    Args:
        url: The paper URL (can be arXiv, PDF, or file URL)
        
    Returns:
        Dictionary containing paper identifiers with keys like 'arxiv_id', 'doi', etc.
    """
    paper_ids = {
        'arxiv_id': None,
        'doi': None
    }
    
    # Extract arXiv ID if it's an arXiv URL
    if 'arxiv.org' in url:
        # Try the standard format first
        match = re.match(r'https?://arxiv.org/(?:abs|pdf)/(\d+\.\d+(?:v\d+)?)', url)
        if match:
            arxiv_id = match.group(1)
            
            if 'v' in arxiv_id:
                arxiv_id = arxiv_id.split('v')[0]
            logger.info(f"Extracted arXiv ID {arxiv_id} from URL {url}")
            paper_ids['arxiv_id'] = arxiv_id
        else:
            # Try a more flexible pattern as fallback
            match = re.search(r'(\d{4}\.\d{4,5}(?:v\d+)?)', url)
            if match:
                arxiv_id = match.group(1)
                
                if 'v' in arxiv_id:
                    arxiv_id = arxiv_id.split('v')[0]
                logger.info(f"Extracted arXiv ID {arxiv_id} from URL {url} using fallback pattern")
                paper_ids['arxiv_id'] = arxiv_id
    
    # Extract DOI if present
    doi_match = re.search(r'doi.org/([^/\s]+/[^/\s]+)', url)
    if doi_match:
        doi = doi_match.group(1)
        logger.info(f"Extracted DOI {doi} from URL {url}")
        paper_ids['doi'] = doi
    
    return paper_ids 