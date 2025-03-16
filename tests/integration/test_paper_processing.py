import pytest
import asyncio
from uuid import uuid4
from app.services.url_service import (
    detect_url_type,
    extract_paper_id_from_url,
    fetch_metadata_from_url
)
from app.services.paper_service import (
    fetch_arxiv_metadata,
    get_related_papers
)
from app.services.pdf_service import (
    download_pdf,
    get_paper_pdf,
    download_and_process_paper
)
from app.api.v1.models import SourceType


@pytest.mark.asyncio
async def test_extract_paper_id_from_url():
    # Test arXiv URL
    arxiv_url = "https://arxiv.org/abs/2106.09685"
    paper_ids = await extract_paper_id_from_url(arxiv_url)
    assert paper_ids.get('arxiv_id') == "2106.09685"
    
    # Test PDF URL with DOI
    pdf_url = "https://doi.org/10.1145/3442188.3445922"
    paper_ids = await extract_paper_id_from_url(pdf_url)
    assert paper_ids.get('doi') == "10.1145/3442188.3445922"
    
    # Test storage URL
    storage_url = "https://example.com/storage/v1/object/public/papers/paper123.pdf"
    paper_ids = await extract_paper_id_from_url(storage_url)
    assert paper_ids.get('file_id') == "paper123.pdf"


@pytest.mark.asyncio
async def test_detect_url_type():
    # Test arXiv URL
    arxiv_url = "https://arxiv.org/abs/2106.09685"
    url_type = await detect_url_type(arxiv_url)
    assert url_type == SourceType.ARXIV
    
    # Test PDF URL
    pdf_url = "https://example.com/paper.pdf"
    url_type = await detect_url_type(pdf_url)
    assert url_type == SourceType.PDF
    
    # Test storage URL
    storage_url = "https://example.com/storage/v1/object/public/papers/paper.pdf"
    url_type = await detect_url_type(storage_url)
    assert url_type == SourceType.FILE


@pytest.mark.asyncio
async def test_fetch_metadata_from_url():
    # Test arXiv URL
    arxiv_url = "https://arxiv.org/abs/2106.09685"
    metadata = await fetch_metadata_from_url(arxiv_url, SourceType.ARXIV)
    assert metadata.title
    assert metadata.authors
    assert metadata.abstract
    assert metadata.arxiv_id == "2106.09685"
    assert metadata.source_type == SourceType.ARXIV
    
    # Test PDF URL (this might fail if the URL is not accessible)
    # pdf_url = "https://example.com/paper.pdf"
    # metadata = await fetch_metadata_from_url(pdf_url, SourceType.PDF)
    # assert metadata.title
    # assert metadata.authors
    # assert metadata.source_type == SourceType.PDF


@pytest.mark.asyncio
async def test_download_and_process_paper():
    # Test arXiv URL
    arxiv_url = "https://arxiv.org/pdf/2106.09685.pdf"
    paper_id = uuid4()
    full_text = await download_and_process_paper(arxiv_url, paper_id, SourceType.ARXIV)
    assert full_text
    assert len(full_text) > 1000  # Ensure we got a substantial amount of text


if __name__ == "__main__":
    # Run the tests
    asyncio.run(test_extract_paper_id_from_url())
    asyncio.run(test_detect_url_type())
    asyncio.run(test_fetch_metadata_from_url())
    asyncio.run(test_download_and_process_paper())
    print("All tests passed!") 