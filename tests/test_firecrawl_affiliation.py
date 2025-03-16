import pytest
import asyncio
from unittest.mock import patch, MagicMock

from app.services.firecrawl_service import (
    extract_affiliation,
    extract_position,
    fallback_scrape_profile
)

# Test affiliation extraction
@pytest.mark.parametrize(
    "text,provided_affiliation,expected",
    [
        # Test with explicit affiliation indicator
        (
            "John Smith is a professor at Stanford University. He works on AI.",
            None,
            "John Smith is a professor at Stanford University"
        ),
        # Test with provided affiliation when text has none
        (
            "John Smith is a researcher working on AI.",
            "MIT",
            "MIT"
        ),
        # Test with long text, should extract just the institution
        (
            "He has an affiliation: University of California, Berkeley where he has been working for 10 years.",
            None,
            "University of California"
        ),
        # Test with different indicator
        (
            "Dr. Smith is affiliated with Harvard Medical School and conducts research on gene therapy.",
            None,
            "Dr. Smith is affiliated with Harvard Medical School"
        ),
        # Test with department mention
        (
            "Jane works in the Department of Computer Science at Carnegie Mellon.",
            "Princeton",
            "Jane works in the Department of Computer Science at Carnegie Mellon"
        ),
    ]
)
def test_extract_affiliation(text, provided_affiliation, expected):
    result = extract_affiliation(text, provided_affiliation)
    assert result == expected

# Test position extraction
@pytest.mark.parametrize(
    "text,provided_position,expected",
    [
        # Test with explicit position
        (
            "John Smith is an Assistant Professor working on AI.",
            None,
            "Assistant Professor"
        ),
        # Test with provided position when text has none
        (
            "John Smith works on AI research.",
            "Associate Professor",
            "Associate Professor"
        ),
        # Test with position in longer context
        (
            "Since 2018, Dr. Jane has been a Research Scientist at Google AI, focusing on NLP.",
            None,
            "Research Scientist"
        ),
    ]
)
def test_extract_position(text, provided_position, expected):
    result = extract_position(text, provided_position)
    assert result == expected

# Test the fallback scrape profile function
@patch('app.services.firecrawl_service.httpx.AsyncClient')
@patch('app.services.firecrawl_service.extract_bio')
@patch('app.services.firecrawl_service.extract_publications')
@patch('app.services.firecrawl_service.extract_email')
@patch('app.services.firecrawl_service.extract_expertise')
@patch('app.services.firecrawl_service.extract_achievements')
@patch('app.services.firecrawl_service.extract_affiliation')
@patch('app.services.firecrawl_service.extract_position')
async def test_fallback_scrape_profile(
    mock_extract_position,
    mock_extract_affiliation,
    mock_extract_achievements,
    mock_extract_expertise,
    mock_extract_email,
    mock_extract_publications,
    mock_extract_bio,
    mock_client
):
    # Setup mock client
    mock_client_instance = MagicMock()
    mock_client.return_value.__aenter__.return_value = mock_client_instance
    
    # Setup mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"markdown": "Mock content"}
    mock_client_instance.post.return_value = mock_response
    
    # Setup extraction mocks
    mock_extract_bio.return_value = "Mock bio"
    mock_extract_publications.return_value = ["Publication 1"]
    mock_extract_email.return_value = "test@example.com"
    mock_extract_expertise.return_value = ["AI", "Machine Learning"]
    mock_extract_achievements.return_value = ["Achievement 1"]
    mock_extract_affiliation.return_value = "Stanford University"
    mock_extract_position.return_value = "Professor"
    
    # Call the function
    result = await fallback_scrape_profile(
        name="John Smith",
        affiliation="MIT",
        position="Associate Professor",
        paper_title="Example Paper"
    )
    
    # Verify results
    assert result["bio"] == "Mock bio"
    assert result["publications"] == ["Publication 1"]
    assert result["email"] == "test@example.com"
    assert result["expertise"] == ["AI", "Machine Learning"]
    assert result["achievements"] == ["Achievement 1"]
    assert result["affiliation"] == "Stanford University"
    assert result["position"] == "Professor"
    
    # Verify that extract_affiliation was called with the provided affiliation
    mock_extract_affiliation.assert_called_once_with("Mock content", "MIT")
    
    # Verify that extract_position was called with the provided position
    mock_extract_position.assert_called_once_with("Mock content", "Associate Professor")

# Test empty results case
@patch('app.services.firecrawl_service.httpx.AsyncClient')
async def test_fallback_scrape_profile_empty_results(mock_client):
    # Setup mock client
    mock_client_instance = MagicMock()
    mock_client.return_value.__aenter__.return_value = mock_client_instance
    
    # Setup mock response that returns empty results
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"markdown": ""}
    mock_client_instance.post.return_value = mock_response
    
    # Call the function
    result = await fallback_scrape_profile(
        name="John Smith",
        affiliation="MIT",
        position="Associate Professor",
        paper_title="Example Paper"
    )
    
    # Verify empty structure is returned
    assert result["bio"] == ""
    assert result["publications"] == []
    assert result["email"] is None
    assert result["expertise"] == []
    assert result["achievements"] == []
    assert result["affiliation"] is None
    assert result["position"] is None 