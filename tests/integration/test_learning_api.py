import asyncio
import httpx
import os
import pytest
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@pytest.mark.asyncio
async def test_learning_api_endpoints():
    """Test various learning API endpoints."""
    # Test paper - use env var or default
    paper_id = os.getenv('TEST_PAPER_ID', '0a066c79-1d2e-4d01-8963-f80f16023687')
    base_url = os.getenv('API_BASE_URL', 'http://localhost:8000')
    
    async with httpx.AsyncClient() as client:
        # Test 1: Get learning path for the paper
        await test_get_learning_path(client, base_url, paper_id)
        
        # Test 2: Generate a new learning path
        await test_generate_learning_path(client, base_url, paper_id)
        
        # Test 3: Get materials for the paper
        await test_get_materials(client, base_url, paper_id)

async def test_get_learning_path(client: httpx.AsyncClient, base_url: str, paper_id: str) -> None:
    """Test the get learning path endpoint."""
    response = await client.get(f"{base_url}/api/v1/learning/papers/{paper_id}/learning-path")
    assert response.status_code == 200
    
    data = response.json()
    assert "materials" in data
    
    # Count materials by type
    material_types = count_by_type(data.get('materials', []))
    assert len(material_types) > 0

async def test_generate_learning_path(client: httpx.AsyncClient, base_url: str, paper_id: str) -> None:
    """Test the generate learning path endpoint."""
    response = await client.post(
        f"{base_url}/api/v1/learning/papers/{paper_id}/generate-learning-path"
    )
    assert response.status_code == 200
    
    data = response.json()
    assert "materials" in data
    
    # Count materials by type
    material_types = count_by_type(data.get('materials', []))
    assert len(material_types) > 0

async def test_get_materials(client: httpx.AsyncClient, base_url: str, paper_id: str) -> None:
    """Test the get materials endpoint."""
    response = await client.get(f"{base_url}/api/v1/learning/papers/{paper_id}/materials")
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    
    # Count materials by type
    types = count_by_type(data)
    assert len(types) > 0

def count_by_type(materials: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count materials by type."""
    type_counts: Dict[str, int] = {}
    for material in materials:
        material_type = material.get('type')
        if material_type:
            type_counts[material_type] = type_counts.get(material_type, 0) + 1
    return type_counts

if __name__ == "__main__":
    asyncio.run(test_learning_api_endpoints()) 