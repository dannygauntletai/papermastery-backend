# Research Paper Graph Visualization Implementation Plan

## 1. Introduction & Overview

### 1.1 Purpose

This document outlines the implementation plan for integrating a Research Paper Graph Visualization system into the PaperMastery platform. This feature will transform static research papers into interactive, visual knowledge networks by extracting key concepts and their relationships and presenting them in an intuitive graph format.

### 1.2 Feature Benefits

The graph visualization system offers several key benefits to users:

1. **Visual Knowledge Representation**: Transforms dense academic text into intuitive visual representations
2. **Enhanced Comprehension**: Helps users quickly grasp the relationships between concepts
3. **Contextual Learning**: Complements the tiered learning approach with visual explorations
4. **Deep Research Generation**: Provides AI-generated insights on key concepts in the knowledge graph
5. **Interactive Exploration**: Allows users to navigate the conceptual landscape of academic papers
6. **Learning Progress Tracking**: Visually tracks mastery across paper concepts

### 1.3 Core Components

The implementation consists of the following key components:

1. **Concept Extraction Engine**: Extracts key concepts and relationships from papers using LLM
2. **Graph Data Structure**: Stores nodes (concepts) and edges (relationships) in Supabase
3. **Interactive Visualization**: Renders the graph using @xyflow/react on the frontend
4. **Deep Research Panel**: Generates comprehensive research content for individual concepts
5. **Integration with Learning Path**: Connects graph nodes to learning items for cohesive experience

### 1.4 Technical Approach

The implementation follows these design principles:

1. **Serverless Architecture**: Leverages Supabase for database and serverless functions
2. **Modular Services**: Separates concerns into dedicated services for maintainability
3. **Strong Typing**: Uses TypeScript and Pydantic for type safety
4. **Optimized Performance**: Implements efficient data fetching and rendering strategies
5. **Security First**: Enforces proper authentication and row-level security

### 1.5 Alignment with Platform Goals

This feature directly supports the ArXiv Mastery Platform goals by:

- Enhancing the learning experience through visual knowledge representation
- Providing deeper context for key academic concepts
- Supporting the tiered learning approach (beginner/intermediate/advanced)
- Enabling interactive exploration of paper content
- Strengthening user engagement through visual interactions 

## 2. Database Schema Changes

### 2.1 New Tables

The following new tables will be added to the Supabase database to support the graph visualization functionality:

```sql
-- Graphs table
CREATE TABLE graphs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    paper_id UUID NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    settings JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Nodes table
CREATE TABLE nodes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    graph_id UUID NOT NULL REFERENCES graphs(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    description TEXT,
    node_type VARCHAR(20) NOT NULL DEFAULT 'concept',
    position JSONB NOT NULL DEFAULT '{"x": 0, "y": 0}'::jsonb,
    style JSONB DEFAULT '{}'::jsonb,
    content JSONB DEFAULT '{}'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Edges table
CREATE TABLE edges (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    graph_id UUID NOT NULL REFERENCES graphs(id) ON DELETE CASCADE,
    source UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    target UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    label TEXT,
    edge_type VARCHAR(20) NOT NULL DEFAULT 'relates_to',
    style JSONB DEFAULT '{}'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Research content table
CREATE TABLE research_content (
    node_id UUID PRIMARY KEY REFERENCES nodes(id) ON DELETE CASCADE,
    explanation TEXT,
    applications TEXT,
    related_concepts JSONB DEFAULT '[]'::jsonb,
    references TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### 2.2 Indexes

The following indexes will be created to optimize query performance:

```sql
-- Indexes for graphs table
CREATE INDEX idx_graphs_paper_id ON graphs(paper_id);
CREATE INDEX idx_graphs_user_id ON graphs(user_id);
CREATE INDEX idx_graphs_status ON graphs(status);

-- Indexes for nodes table
CREATE INDEX idx_nodes_graph_id ON nodes(graph_id);
CREATE INDEX idx_nodes_node_type ON nodes(node_type);

-- Indexes for edges table
CREATE INDEX idx_edges_graph_id ON edges(graph_id);
CREATE INDEX idx_edges_source ON edges(source);
CREATE INDEX idx_edges_target ON edges(target);
CREATE INDEX idx_edges_edge_type ON edges(edge_type);

-- Indexes for research_content table
CREATE INDEX idx_research_content_node_id ON research_content(node_id);
```

### 2.3 Row Level Security (RLS) Policies

To ensure data security, the following RLS policies will be implemented:

```sql
-- Enable RLS on all tables
ALTER TABLE graphs ENABLE ROW LEVEL SECURITY;
ALTER TABLE nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE edges ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_content ENABLE ROW LEVEL SECURITY;

-- Graphs table policies
CREATE POLICY "Graphs - Owner Full Access"
    ON graphs
    FOR ALL
    USING (auth.uid() = user_id);

-- Nodes table policies
CREATE POLICY "Nodes - Allow access via graph"
    ON nodes
    FOR ALL
    USING (
        graph_id IN (
            SELECT id FROM graphs WHERE user_id = auth.uid()
        )
    );

-- Edges table policies
CREATE POLICY "Edges - Allow access via graph"
    ON edges
    FOR ALL
    USING (
        graph_id IN (
            SELECT id FROM graphs WHERE user_id = auth.uid()
        )
    );

-- Research content table policies
CREATE POLICY "Research Content - Allow access via node"
    ON research_content
    FOR ALL
    USING (
        node_id IN (
            SELECT n.id FROM nodes n 
            JOIN graphs g ON n.graph_id = g.id 
            WHERE g.user_id = auth.uid()
        )
    );
```

### 2.4 Integration with Existing Schema

This new schema integrates with the existing database through the following relationships:

1. `graphs.paper_id` references `papers.id` - Links each graph to its source paper
2. `graphs.user_id` references `auth.users.id` - Associates graphs with specific users
3. Potential extension: Add a `graph_id` column to the `items` table to link learning materials with specific graph nodes

### 2.5 Data Types

The schema uses several JSONB fields to provide flexibility:

1. `graphs.settings` - Stores graph visualization settings (e.g., layout, theme)
2. `nodes.position` - Stores 2D coordinates for node positioning
3. `nodes.style` - Stores visual styling properties
4. `nodes.content` - Stores content-specific properties
5. `nodes.metadata` - Stores additional concept metadata
6. `edges.style` - Stores edge styling properties
7. `edges.metadata` - Stores additional relationship metadata
8. `research_content.related_concepts` - Stores structured array of related concepts 

## 3. Service Implementation

The graph visualization system requires several new services to handle concept extraction, graph management, and research content generation. These services will be implemented as part of the existing PaperMastery service layer.

### 3.1 Directory Structure

New service files will be added to the existing service directory structure:

```
app/
  └── services/
      ├── concept_extraction_service.py    # Extract concepts from papers
      ├── graph_service.py                 # Generate and manage concept graphs
      ├── research_content_service.py      # Generate deep research content
      └── graph_layout_service.py          # Handle graph visualization layouts
```

### 3.2 Concept Extraction Service

The `ConceptExtractionService` is responsible for analyzing papers and extracting key concepts and their relationships using LLM.

```python
# app/services/concept_extraction_service.py
from typing import Dict, List, Optional, Any
import logging
from app.core.logger import get_logger
from app.services.llm_service import LLMService
from app.services.paper_service import PaperService
from app.database.supabase_client import SupabaseClient

logger = get_logger(__name__)

class ConceptExtractionService:
    def __init__(
        self, 
        llm_service: LLMService,
        paper_service: PaperService,
        supabase: SupabaseClient
    ):
        self.llm_service = llm_service
        self.paper_service = paper_service
        self.supabase = supabase
        
    async def extract_concepts(self, paper_id: str) -> Dict[str, Any]:
        """
        Extract key concepts from a paper and their relationships.
        
        Args:
            paper_id: ID of the paper to process
            
        Returns:
            Dict containing concepts and relationships
        """
        try:
            # Get paper content and metadata
            paper_data = await self.paper_service.get_paper(paper_id)
            paper_content = paper_data.get("full_text", "")
            paper_metadata = {
                "title": paper_data.get("title", ""),
                "authors": paper_data.get("authors", []),
                "abstract": paper_data.get("abstract", "")
            }
            
            # Use LLM to extract concepts
            concepts_response = await self.llm_service.generate_with_template(
                template_name="concept_extraction.j2",
                context={
                    "paper_content": paper_content,
                    "title": paper_metadata["title"],
                    "authors": paper_metadata["authors"],
                    "abstract": paper_metadata["abstract"]
                }
            )
            
            # Process and validate the extraction results
            extracted_data = self._process_extraction_response(concepts_response)
            
            return extracted_data
        except Exception as e:
            logger.error(f"Error extracting concepts from paper {paper_id}: {str(e)}")
            raise
            
    def _process_extraction_response(self, response: str) -> Dict[str, Any]:
        """Process the LLM response into structured data."""
        try:
            # Parse JSON response from LLM
            import json
            
            # Clean up the response (handle possible markdown formatting)
            if "```json" in response:
                # Extract content between JSON code blocks
                content = response.split("```json")[1].split("```")[0].strip()
            else:
                content = response
                
            data = json.loads(content)
            
            # Validate required structure
            required_keys = ["concepts", "relationships"]
            for key in required_keys:
                if key not in data:
                    raise ValueError(f"Missing required key '{key}' in extraction response")
            
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse extraction response as JSON: {str(e)}")
            # Fallback: Return empty structure
            return {"concepts": [], "relationships": []}
```

### 3.3 Graph Service

The `GraphService` manages the creation and retrieval of concept graphs based on extracted concepts.

```python
# app/services/graph_service.py
from typing import Dict, List, Optional, Any
import logging
import uuid
import math
from app.core.logger import get_logger
from app.database.supabase_client import SupabaseClient
from app.services.concept_extraction_service import ConceptExtractionService

logger = get_logger(__name__)

class GraphService:
    def __init__(
        self, 
        supabase: SupabaseClient,
        concept_extraction_service: ConceptExtractionService
    ):
        self.supabase = supabase
        self.concept_extraction_service = concept_extraction_service
        
    async def create_graph(self, paper_id: str, user_id: str) -> Dict[str, Any]:
        """
        Create a new concept graph for a paper.
        
        Args:
            paper_id: ID of the paper
            user_id: ID of the user
            
        Returns:
            Dict with graph data including ID
        """
        try:
            # Check if a graph already exists for this paper and user
            existing_graph = await self._get_existing_graph(paper_id, user_id)
            if existing_graph:
                return await self.get_graph(existing_graph["id"])
                
            # Get paper details
            paper_response = await self.supabase.table("papers").select("title").eq("id", paper_id).single().execute()
            paper_title = paper_response.data.get("title", "")
            
            # Extract concepts
            concepts_data = await self.concept_extraction_service.extract_concepts(paper_id)
            
            # Create graph record
            graph_id = str(uuid.uuid4())
            graph_data = {
                "id": graph_id,
                "paper_id": paper_id,
                "user_id": user_id,
                "title": f"Concept Map: {paper_title}",
                "description": f"Concept map for {paper_title}",
                "status": "active",
                "settings": {
                    "layoutType": "force",
                    "theme": "light",
                    "nodeSpacing": 50,
                    "showLabels": True
                }
            }
            
            # Insert graph into database
            await self.supabase.table("graphs").insert(graph_data).execute()
            
            # Create nodes
            await self._create_nodes(graph_id, concepts_data.get("concepts", []))
            
            # Create edges
            await self._create_edges(graph_id, concepts_data.get("relationships", []))
            
            return await self.get_graph(graph_id)
        except Exception as e:
            logger.error(f"Error creating graph for paper {paper_id}: {str(e)}")
            raise
            
    async def get_graph(self, graph_id: str) -> Dict[str, Any]:
        """
        Get a complete graph with nodes and edges.
        
        Args:
            graph_id: ID of the graph
            
        Returns:
            Dict with graph data including nodes and edges
        """
        try:
            # Get graph data
            graph_response = await self.supabase.table("graphs").select("*").eq("id", graph_id).single().execute()
            
            # Get nodes
            nodes_response = await self.supabase.table("nodes").select("*").eq("graph_id", graph_id).execute()
            nodes = nodes_response.data
            
            # Get edges
            edges_response = await self.supabase.table("edges").select("*").eq("graph_id", graph_id).execute()
            edges = edges_response.data
            
            return {
                **graph_response.data,
                "nodes": nodes,
                "edges": edges
            }
        except Exception as e:
            logger.error(f"Error fetching graph {graph_id}: {str(e)}")
            raise
            
    async def _create_nodes(self, graph_id: str, concepts: List[Dict[str, Any]]) -> None:
        """Create nodes for each concept in the graph."""
        try:
            # First, create a central paper node
            paper_node_id = str(uuid.uuid4())
            paper_node = {
                "id": paper_node_id,
                "graph_id": graph_id,
                "label": "Paper",
                "description": "The main research paper",
                "node_type": "paper",
                "position": {"x": 300, "y": 300},
                "style": self._get_style_for_concept_type("paper"),
                "metadata": {}
            }
            
            # Insert paper node
            await self.supabase.table("nodes").insert(paper_node).execute()
            
            # Calculate positions in a circle around the paper node
            concept_nodes = []
            for i, concept in enumerate(concepts):
                angle = (2 * 3.14159 * i) / max(len(concepts), 1)
                radius = 200
                position = {
                    "x": 300 + radius * math.cos(angle),
                    "y": 300 + radius * math.sin(angle)
                }
                
                node_type = concept.get("type", "concept").lower()
                concept_nodes.append({
                    "id": str(uuid.uuid4()),
                    "graph_id": graph_id,
                    "label": concept.get("name", "Concept"),
                    "description": concept.get("description", ""),
                    "node_type": node_type,
                    "position": position,
                    "style": self._get_style_for_concept_type(node_type),
                    "metadata": concept.get("metadata", {})
                })
                
            # Batch insert concept nodes
            if concept_nodes:
                await self.supabase.table("nodes").insert(concept_nodes).execute()
        except Exception as e:
            logger.error(f"Error creating nodes for graph {graph_id}: {str(e)}")
            raise
    
    def _get_style_for_concept_type(self, concept_type: str) -> Dict[str, Any]:
        """Get styling for a concept node based on its type."""
        type_styles = {
            "paper": {
                "backgroundColor": "#f0f4f8",
                "borderColor": "#4f46e5",
                "width": 180,
                "padding": 10
            },
            "theory": {
                "backgroundColor": "#f0e7ff",
                "borderColor": "#8b5cf6"
            },
            "methodology": {
                "backgroundColor": "#dcfce7",
                "borderColor": "#10b981"
            },
            "finding": {
                "backgroundColor": "#fef3c7",
                "borderColor": "#f59e0b"
            },
            "concept": {
                "backgroundColor": "#dbeafe",
                "borderColor": "#3b82f6"
            }
        }
        
        return type_styles.get(concept_type.lower(), type_styles["concept"])
```

### 3.4 Research Content Service

The `ResearchContentService` generates comprehensive, AI-powered research content for individual concepts in the graph.

```python
# app/services/research_content_service.py
from typing import Dict, List, Optional, Any
import logging
from app.core.logger import get_logger
from app.services.llm_service import LLMService
from app.database.supabase_client import SupabaseClient

logger = get_logger(__name__)

class ResearchContentService:
    def __init__(
        self, 
        llm_service: LLMService,
        supabase: SupabaseClient
    ):
        self.llm_service = llm_service
        self.supabase = supabase
        
    async def generate_research_content(
        self, 
        node_id: str, 
        concept_name: str, 
        graph_id: str
    ) -> Dict[str, Any]:
        """
        Generate comprehensive research content for a concept node.
        
        Args:
            node_id: ID of the node
            concept_name: Name of the concept
            graph_id: ID of the graph
            
        Returns:
            Dict with research content sections
        """
        try:
            # Check if content already exists
            existing_content = await self._get_existing_content(node_id)
            if existing_content:
                return existing_content
                
            # Get graph and paper data for context
            graph_context = await self._get_graph_context(graph_id, node_id)
            
            # Generate research content with LLM
            content_response = await self.llm_service.generate_with_template(
                template_name="research_content.j2",
                context={
                    "concept_name": concept_name,
                    "paper_title": graph_context.get("paper_title", ""),
                    "paper_authors": graph_context.get("paper_authors", []),
                    "related_concepts": graph_context.get("related_concepts", []),
                    "relationships": graph_context.get("relationships", [])
                }
            )
            
            # Process the content
            processed_content = self._process_content_response(content_response)
            
            # Store in database
            await self._store_research_content(node_id, processed_content)
            
            return processed_content
        except Exception as e:
            logger.error(f"Error generating research content for node {node_id}: {str(e)}")
            raise
            
    async def _get_existing_content(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Check if research content already exists for this node."""
        try:
            response = await self.supabase.table("research_content")\
                .select("*")\
                .eq("node_id", node_id)\
                .single()\
                .execute()
                
            if response.data:
                return response.data
            return None
        except Exception:
            return None
            
    def _process_content_response(self, response: str) -> Dict[str, Any]:
        """Process the LLM response into structured research content."""
        try:
            import re
            
            # Extract sections using regex
            explanation_match = re.search(r'(?:explanation:|1\.)(.*?)(?:applications:|2\.)', response, re.DOTALL | re.IGNORECASE)
            applications_match = re.search(r'(?:applications:|2\.)(.*?)(?:related concepts:|3\.)', response, re.DOTALL | re.IGNORECASE)
            related_match = re.search(r'(?:related concepts:|3\.)(.*?)(?:references:|4\.)', response, re.DOTALL | re.IGNORECASE)
            references_match = re.search(r'(?:references:|4\.)(.*)', response, re.DOTALL | re.IGNORECASE)
            
            return {
                "explanation": explanation_match.group(1).strip() if explanation_match else "No explanation available.",
                "applications": applications_match.group(1).strip() if applications_match else "No applications available.",
                "related_concepts": self._extract_related_concepts(related_match.group(1) if related_match else ""),
                "references": references_match.group(1).strip() if references_match else "No references available."
            }
        except Exception as e:
            logger.error(f"Error processing content response: {str(e)}")
            # Return fallback content
            return {
                "explanation": "Unable to generate explanation.",
                "applications": "Unable to generate applications.",
                "related_concepts": [],
                "references": "Unable to generate references."
            }
            
    def _extract_related_concepts(self, related_section: str) -> List[Dict[str, Any]]:
        """Extract structured related concepts from the text."""
        if not related_section:
            return []
            
        try:
            import re
            related_concepts = []
            
            # Find numbered or bulleted items
            concept_matches = re.findall(r'(?:^|\n)[-\d]+\.\s*(.*?)(?=(?:\n[-\d]+\.)|$)', related_section, re.DOTALL)
            
            for match in concept_matches[:5]:  # Limit to 5 concepts
                # Extract name, often in bold or before colon
                name_match = re.search(r'\*\*(.*?)\*\*', match)
                if name_match:
                    name = name_match.group(1)
                else:
                    # Try to find a name before a colon
                    name_parts = match.split(':', 1)
                    name = name_parts[0].strip()
                    
                # Extract or create a description
                if len(name_parts) > 1:
                    description = name_parts[1].strip()
                else:
                    description = match.replace(name, '').strip()
                    
                related_concepts.append({
                    "name": name,
                    "description": description
                })
                
            return related_concepts
        except Exception as e:
            logger.error(f"Error extracting related concepts: {str(e)}")
            return []
            
    async def _store_research_content(self, node_id: str, content: Dict[str, Any]) -> None:
        """Store the research content in the database."""
        try:
            content_data = {
                "node_id": node_id,
                "explanation": content.get("explanation", ""),
                "applications": content.get("applications", ""),
                "related_concepts": content.get("related_concepts", []),
                "references": content.get("references", ""),
                "created_at": "now()",
                "updated_at": "now()"
            }
            
            await self.supabase.table("research_content").insert(content_data).execute()
        except Exception as e:
            logger.error(f"Error storing research content for node {node_id}: {str(e)}")
            raise
```

### 3.5 LLM Prompt Templates

The following prompt templates will be used for AI-based content generation:

#### `concept_extraction.j2`

```jinja2
You are an expert academic concept mapper tasked with extracting key concepts and relationships from a research paper.

Paper Title: {{ title }}
Authors: {{ authors|join(', ') }}
Abstract: {{ abstract }}

Paper Content:
{{ paper_content }}

Please extract the key concepts from this paper and identify the relationships between them. Follow these rules:

1. Extract 5-10 main concepts from the paper
2. For each concept, provide:
   - A name (1-3 words)
   - A concise description (1-2 sentences)
   - The concept type (methodology, theory, finding, term)
   - Any relevant metadata

3. Identify the relationships between these concepts, including:
   - Source concept
   - Target concept
   - Relationship type (builds_on, contradicts, influences, part_of, applies_to, relates_to)
   - A brief description of the relationship

Format your response as a JSON object with 'concepts' and 'relationships' arrays.
```

#### `research_content.j2`

```jinja2
You are an academic research assistant tasked with generating comprehensive information about a concept from a research paper.

Research Paper Title: {{ paper_title }}
Authors: {{ paper_authors|join(', ') }}

The concept I need information on is: "{{ concept_name }}"

Other related concepts in this paper's concept graph:
{% for concept in related_concepts %}
- {{ concept.name }} ({{ concept.type }})
{% endfor %}

Relationships to this concept:
{% for rel in relationships %}
- {{ rel.other_concept_name }} ({{ rel.label or 'relates to' }})
{% endfor %}

Please provide a comprehensive research profile with:

1. An in-depth explanation of the concept (include definition, background, significance)
2. Practical applications of the concept
3. Five related concepts with brief descriptions and how they relate to the main concept
4. Academic references and further reading suggestions

Format your response as detailed markdown for each section.
```

### 3.6 Dependency Injection

The services will be integrated into the application's dependency injection system:

```python
# app/api/dependencies.py

# ... existing imports and dependencies ...

from app.services.concept_extraction_service import ConceptExtractionService
from app.services.graph_service import GraphService
from app.services.research_content_service import ResearchContentService

# ... existing dependencies ...

def get_concept_extraction_service(
    llm_service: LLMService = Depends(get_llm_service),
    paper_service: PaperService = Depends(get_paper_service),
    supabase: SupabaseClient = Depends(get_supabase_client)
) -> ConceptExtractionService:
    return ConceptExtractionService(llm_service, paper_service, supabase)
    
def get_graph_service(
    supabase: SupabaseClient = Depends(get_supabase_client),
    concept_extraction_service: ConceptExtractionService = Depends(get_concept_extraction_service)
) -> GraphService:
    return GraphService(supabase, concept_extraction_service)
    
def get_research_content_service(
    llm_service: LLMService = Depends(get_llm_service),
    supabase: SupabaseClient = Depends(get_supabase_client)
) -> ResearchContentService:
    return ResearchContentService(llm_service, supabase)
``` 

## 4. API Endpoint Implementation

The graph visualization system requires new API endpoints to handle creation, retrieval, and updates of graph data. These endpoints will be implemented following the existing API architecture of the PaperMastery platform.

### 4.1 Directory Structure

New API endpoint files will be added to the existing API directory structure:

```
app/
  └── api/
      └── v1/
          ├── endpoints/
          │   ├── graphs.py            # Graph management endpoints
          │   └── research_content.py  # Research content endpoints
          └── routers.py               # Updated router configuration
```

### 4.2 Graph Management Endpoints

The following endpoints will be implemented for graph management:

```python
# app/api/v1/endpoints/graphs.py
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import get_current_user
from app.services.graph_service import GraphService
from app.api.dependencies import get_graph_service
from app.schemas.graph import GraphCreate, GraphResponse, GraphUpdate, NodeUpdate

router = APIRouter(prefix="/graphs", tags=["graphs"])

@router.post("", response_model=GraphResponse)
async def create_graph(
    data: GraphCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """Create a new concept graph for a paper."""
    try:
        return await graph_service.create_graph(
            paper_id=data.paper_id,
            user_id=current_user["id"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create graph: {str(e)}"
        )

@router.get("/{graph_id}", response_model=GraphResponse)
async def get_graph(
    graph_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """Get a graph with all its nodes and edges."""
    try:
        graph = await graph_service.get_graph(graph_id)
        
        # Verify ownership
        if graph.get("user_id") != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this graph"
            )
            
        return graph
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve graph: {str(e)}"
        )

@router.get("", response_model=List[Dict[str, Any]])
async def list_user_graphs(
    current_user: Dict[str, Any] = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """List all graphs created by the current user."""
    try:
        return await graph_service.list_user_graphs(current_user["id"])
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list graphs: {str(e)}"
        )

@router.patch("/nodes/{node_id}/position", response_model=Dict[str, Any])
async def update_node_position(
    node_id: str,
    data: NodeUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    graph_service: GraphService = Depends(get_graph_service)
):
    """Update the position of a node in the graph."""
    try:
        # Verify node belongs to a graph owned by the user
        # This is handled by RLS, but we do an explicit check here
        node = await graph_service.get_node(node_id)
        graph = await graph_service.get_graph_basic(node["graph_id"])
        
        if graph.get("user_id") != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to modify this node"
            )
            
        await graph_service.update_node_position(node_id, data.position)
        return {"success": True}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update node position: {str(e)}"
        )
```

### 4.3 Research Content Endpoints

The following endpoints will be implemented for research content generation:

```python
# app/api/v1/endpoints/research_content.py
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from app.core.security import get_current_user
from app.services.research_content_service import ResearchContentService
from app.services.graph_service import GraphService
from app.api.dependencies import get_research_content_service, get_graph_service
from app.schemas.research import ResearchContentRequest, ResearchContentResponse

router = APIRouter(prefix="/research-content", tags=["research"])

@router.post("", response_model=ResearchContentResponse)
async def generate_research_content(
    data: ResearchContentRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user),
    research_content_service: ResearchContentService = Depends(get_research_content_service),
    graph_service: GraphService = Depends(get_graph_service)
):
    """
    Generate or retrieve research content for a concept node.
    If content already exists, returns it immediately.
    If not, initiates generation in the background and returns a status.
    """
    try:
        # Verify node belongs to a graph owned by the user
        node = await graph_service.get_node(data.node_id)
        graph = await graph_service.get_graph_basic(node["graph_id"])
        
        if graph.get("user_id") != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access content for this node"
            )
            
        # Check if content already exists
        existing_content = await research_content_service._get_existing_content(data.node_id)
        
        if existing_content:
            return {
                "node_id": data.node_id,
                "status": "complete",
                "content": existing_content
            }
            
        # Schedule content generation in background
        background_tasks.add_task(
            research_content_service.generate_research_content,
            node_id=data.node_id,
            concept_name=data.concept_name,
            graph_id=graph["id"]
        )
        
        return {
            "node_id": data.node_id,
            "status": "processing",
            "content": None
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate research content: {str(e)}"
        )

@router.get("/{node_id}", response_model=ResearchContentResponse)
async def get_research_content(
    node_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    research_content_service: ResearchContentService = Depends(get_research_content_service),
    graph_service: GraphService = Depends(get_graph_service)
):
    """
    Retrieve research content for a concept node.
    """
    try:
        # Verify node belongs to a graph owned by the user
        node = await graph_service.get_node(node_id)
        graph = await graph_service.get_graph_basic(node["graph_id"])
        
        if graph.get("user_id") != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access content for this node"
            )
            
        # Get existing content
        content = await research_content_service._get_existing_content(node_id)
        
        return {
            "node_id": node_id,
            "status": "complete" if content else "not_found",
            "content": content
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve research content: {str(e)}"
        )
```

### 4.4 Router Configuration

Update the API router configuration to include the new endpoints:

```python
# app/api/v1/routers.py
from fastapi import APIRouter
from app.api.v1.endpoints import users, papers, items, graphs, research_content

api_router = APIRouter()

# Existing routers
api_router.include_router(users.router)
api_router.include_router(papers.router)
api_router.include_router(items.router)

# New routers for graph visualization
api_router.include_router(graphs.router)
api_router.include_router(research_content.router)
```

### 4.5 Schemas

New Pydantic schemas will be created for data validation:

```python
# app/schemas/graph.py
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID

class Position(BaseModel):
    x: float = Field(..., description="X coordinate")
    y: float = Field(..., description="Y coordinate")

class NodeUpdate(BaseModel):
    position: Position = Field(..., description="New position for the node")

class GraphCreate(BaseModel):
    paper_id: str = Field(..., description="ID of the paper to create graph for")

class GraphUpdate(BaseModel):
    title: Optional[str] = Field(None, description="Graph title")
    description: Optional[str] = Field(None, description="Graph description")
    settings: Optional[Dict[str, Any]] = Field(None, description="Graph visualization settings")

class GraphResponse(BaseModel):
    id: str
    paper_id: str
    user_id: str
    title: str
    description: Optional[str] = None
    status: str
    settings: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    nodes: Optional[List[Dict[str, Any]] = None
    edges: Optional[List[Dict[str, Any]] = None

# app/schemas/research.py
from typing import Dict, Optional, Any
from pydantic import BaseModel, Field

class ResearchContentRequest(BaseModel):
    node_id: str = Field(..., description="ID of the node to generate content for")
    concept_name: str = Field(..., description="Name of the concept")

class ResearchContentResponse(BaseModel):
    node_id: str
    status: str = Field(..., description="Status of content generation: processing, complete, not_found")
    content: Optional[Dict[str, Any]] = Field(None, description="The research content if available")
``` 

## 5. Frontend Implementation

The frontend implementation will provide a rich, interactive graph visualization experience using React, TypeScript, and @xyflow/react (React Flow). The UI will be built with Shadcn UI components and styled with Tailwind CSS.

### 5.1 Directory Structure

New frontend components will be organized in a feature-based structure:

```
app/
  └── features/
      └── graph-visualization/
          ├── components/               # Graph UI components 
          │   ├── GraphCanvas.tsx       # Main graph visualization component
          │   ├── ResearchPanel.tsx     # Detailed research content panel
          │   ├── GraphControls.tsx     # Zoom, layout, and settings controls
          │   ├── NodeTypes/            # Custom node components
          │   │   ├── ConceptNode.tsx   # Component for concept nodes
          │   │   ├── PaperNode.tsx     # Component for paper nodes
          │   │   └── index.ts          # Node types registry
          │   └── EdgeTypes/            # Custom edge components
          │       ├── RelationshipEdge.tsx  # Component for relationship edges
          │       └── index.ts          # Edge types registry
          ├── hooks/                    # Custom React hooks
          │   ├── useGraph.ts           # Hook for graph data fetching
          │   └── useResearchContent.ts # Hook for research content
          ├── types/                    # TypeScript types
          │   └── graph.ts              # Type definitions for graph data
          ├── utils/                    # Utility functions
          │   ├── layout.ts             # Graph layout algorithms
          │   └── styling.ts            # Styling utilities
          └── store/                    # State management
              └── graphStore.ts         # Zustand store for graph state
```

### 5.2 Main Graph Visualization Component

The `GraphCanvas` component will serve as the main visualization container:

```tsx
// app/features/graph-visualization/components/GraphCanvas.tsx
import React, { useCallback, useEffect, useMemo } from 'react';
import ReactFlow, {
  Background,
  Controls,
  Panel,
  useNodesState,
  useEdgesState,
  useReactFlow,
  ConnectionLineType,
  OnConnect,
  OnNodeDragStop,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { useGraph } from '../hooks/useGraph';
import { GraphControls } from './GraphControls';
import { nodeTypes } from './NodeTypes';
import { edgeTypes } from './EdgeTypes';
import { useGraphStore } from '../store/graphStore';
import { Spinner } from '@/components/ui/spinner';

interface GraphCanvasProps {
  graphId: string;
  onNodeSelect: (nodeId: string | null) => void;
}

export const GraphCanvas: React.FC<GraphCanvasProps> = ({ 
  graphId, 
  onNodeSelect 
}) => {
  const { graph, isLoading, error, updateNodePosition } = useGraph(graphId);
  const reactFlowInstance = useReactFlow();
  const setSelectedNode = useGraphStore((state) => state.setSelectedNode);
  
  // Initialize nodes and edges states
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  
  // Update nodes and edges when graph data changes
  useEffect(() => {
    if (graph) {
      setNodes(graph.nodes.map(node => ({
        id: node.id,
        type: node.node_type,
        position: node.position,
        data: {
          label: node.label,
          description: node.description,
          type: node.node_type,
          style: node.style,
        },
      })));
      
      setEdges(graph.edges.map(edge => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        type: edge.edge_type,
        label: edge.label,
        data: {
          type: edge.edge_type,
          style: edge.style,
        },
      })));
    }
  }, [graph, setNodes, setEdges]);
  
  // Handle node selection
  const onNodeClick = useCallback((_, node) => {
    setSelectedNode(node);
    onNodeSelect(node.id);
  }, [setSelectedNode, onNodeSelect]);
  
  // Handle node drag end to update positions on server
  const onNodeDragStop: OnNodeDragStop = useCallback((_, node) => {
    updateNodePosition(node.id, node.position);
  }, [updateNodePosition]);
  
  // Handle layout controls
  const applyLayout = useCallback((layoutType: string) => {
    // Apply layout algorithm from layout.ts
    // This will be implemented in the utils/layout.ts file
  }, [nodes, setNodes]);
  
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spinner size="lg" />
        <span className="ml-2">Loading graph...</span>
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-red-500">Error loading graph: {error.message}</p>
      </div>
    );
  }
  
  return (
    <div className="w-full h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onNodeDragStop={onNodeDragStop}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        connectionLineType={ConnectionLineType.Bezier}
        defaultViewport={{ x: 0, y: 0, zoom: 1 }}
        minZoom={0.2}
        maxZoom={4}
        proOptions={{ hideAttribution: true }}
        fitView
      >
        <Background />
        <Controls />
        <Panel position="top-right">
          <GraphControls onApplyLayout={applyLayout} />
        </Panel>
      </ReactFlow>
    </div>
  );
};
```

### 5.3 Research Panel Component

The `ResearchPanel` component will display detailed AI-generated research content for selected nodes:

```tsx
// app/features/graph-visualization/components/ResearchPanel.tsx
import React, { useEffect, useState } from 'react';
import { useResearchContent } from '../hooks/useResearchContent';
import { useGraphStore } from '../store/graphStore';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Skeleton } from '@/components/ui/skeleton';
import { Markdown } from '@/components/ui/markdown';

export const ResearchPanel: React.FC = () => {
  const selectedNode = useGraphStore((state) => state.selectedNode);
  const [activeTab, setActiveTab] = useState('explanation');
  
  const {
    content,
    isLoading,
    error,
    generateContent
  } = useResearchContent(selectedNode?.id, selectedNode?.data?.label);
  
  // Reset active tab when selected node changes
  useEffect(() => {
    setActiveTab('explanation');
  }, [selectedNode?.id]);
  
  if (!selectedNode) {
    return (
      <Card className="w-full h-full">
        <CardContent className="p-6">
          <p className="text-muted-foreground text-center">
            Select a node in the graph to view detailed research
          </p>
        </CardContent>
      </Card>
    );
  }
  
  const handleGenerateContent = () => {
    if (selectedNode) {
      generateContent(selectedNode.id, selectedNode.data.label);
    }
  };
  
  const LoadingState = () => (
    <div className="space-y-4">
      <Skeleton className="w-full h-6" />
      <Skeleton className="w-full h-24" />
      <Skeleton className="w-3/4 h-4" />
      <Skeleton className="w-1/2 h-4" />
    </div>
  );
  
  const ErrorState = () => (
    <div className="text-center py-4">
      <p className="text-red-500 mb-4">Error loading research content</p>
      <Button onClick={handleGenerateContent}>
        Retry
      </Button>
    </div>
  );
  
  const EmptyState = () => (
    <div className="text-center py-8">
      <h3 className="text-xl font-semibold mb-2">
        Generate Research for "{selectedNode.data.label}"
      </h3>
      <p className="text-muted-foreground mb-6">
        Get AI-generated research content for this concept
      </p>
      <Button onClick={handleGenerateContent}>
        Generate Research
      </Button>
    </div>
  );
  
  if (isLoading) {
    return (
      <Card className="w-full h-full">
        <CardHeader>
          <CardTitle>{selectedNode.data.label}</CardTitle>
        </CardHeader>
        <CardContent>
          <LoadingState />
        </CardContent>
      </Card>
    );
  }
  
  if (error) {
    return (
      <Card className="w-full h-full">
        <CardHeader>
          <CardTitle>{selectedNode.data.label}</CardTitle>
        </CardHeader>
        <CardContent>
          <ErrorState />
        </CardContent>
      </Card>
    );
  }
  
  if (!content) {
    return (
      <Card className="w-full h-full">
        <CardHeader>
          <CardTitle>{selectedNode.data.label}</CardTitle>
        </CardHeader>
        <CardContent>
          <EmptyState />
        </CardContent>
      </Card>
    );
  }
  
  return (
    <Card className="w-full h-full overflow-auto">
      <CardHeader>
        <CardTitle className="text-xl">{selectedNode.data.label}</CardTitle>
      </CardHeader>
      
      <CardContent>
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="w-full">
            <TabsTrigger value="explanation" className="flex-1">Explanation</TabsTrigger>
            <TabsTrigger value="applications" className="flex-1">Applications</TabsTrigger>
            <TabsTrigger value="related" className="flex-1">Related</TabsTrigger>
            <TabsTrigger value="references" className="flex-1">References</TabsTrigger>
          </TabsList>
          
          <TabsContent value="explanation" className="mt-4">
            <Markdown content={content.explanation} />
          </TabsContent>
          
          <TabsContent value="applications" className="mt-4">
            <Markdown content={content.applications} />
          </TabsContent>
          
          <TabsContent value="related" className="mt-4">
            <div className="space-y-4">
              {content.related_concepts.map((concept, index) => (
                <div key={index} className="p-4 border rounded-md">
                  <h3 className="font-semibold">{concept.name}</h3>
                  <p className="text-sm text-muted-foreground">
                    {concept.description}
                  </p>
                </div>
              ))}
            </div>
          </TabsContent>
          
          <TabsContent value="references" className="mt-4">
            <Markdown content={content.references} />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
};
```

### 5.4 Custom Node Components

Custom node components will provide specialized rendering for different node types:

```tsx
// app/features/graph-visualization/components/NodeTypes/ConceptNode.tsx
import React, { memo } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';

export const ConceptNode = memo(({ data, selected }: NodeProps) => {
  const { label, description, style } = data;
  
  // Merge default styles with custom styles
  const nodeStyle = {
    padding: '10px',
    borderRadius: '4px',
    minWidth: '150px',
    maxWidth: '200px',
    boxShadow: selected ? '0 0 0 2px #4f46e5' : 'none',
    ...style,
  };
  
  return (
    <div className="concept-node" style={nodeStyle}>
      <Handle type="target" position={Position.Top} />
      
      <div className="text-center">
        <div className="font-semibold truncate">{label}</div>
        {description && (
          <div className="text-xs text-muted-foreground truncate mt-1">
            {description.length > 60 
              ? `${description.substring(0, 60)}...` 
              : description}
          </div>
        )}
      </div>
      
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
});

// app/features/graph-visualization/components/NodeTypes/PaperNode.tsx
import React, { memo } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import { FileTextIcon } from 'lucide-react';

export const PaperNode = memo(({ data, selected }: NodeProps) => {
  const { label, style } = data;
  
  // Merge default styles with custom styles
  const nodeStyle = {
    padding: '16px',
    borderRadius: '8px',
    background: '#f0f4f8',
    borderColor: '#4f46e5',
    borderWidth: '1px',
    borderStyle: 'solid',
    width: '220px',
    boxShadow: selected ? '0 0 0 2px #4f46e5' : 'none',
    ...style,
  };
  
  return (
    <div className="paper-node" style={nodeStyle}>
      <Handle type="target" position={Position.Top} />
      
      <div className="flex items-center gap-2">
        <FileTextIcon size={18} />
        <div className="font-bold truncate">{label}</div>
      </div>
      
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
});

// app/features/graph-visualization/components/NodeTypes/index.ts
import { ConceptNode } from './ConceptNode';
import { PaperNode } from './PaperNode';

export const nodeTypes = {
  concept: ConceptNode,
  theory: ConceptNode,
  methodology: ConceptNode,
  finding: ConceptNode,
  term: ConceptNode,
  paper: PaperNode,
};
```

### 5.5 Data Fetching Hooks

Custom hooks will handle data fetching and state management:

```tsx
// app/features/graph-visualization/hooks/useGraph.ts
import { useState, useEffect, useCallback } from 'react';
import { GraphData, Node, Edge } from '../types/graph';
import { supabase } from '@/lib/supabase';

interface UseGraphReturn {
  graph: GraphData | null;
  isLoading: boolean;
  error: Error | null;
  updateNodePosition: (nodeId: string, position: { x: number; y: number }) => Promise<void>;
}

export const useGraph = (graphId: string): UseGraphReturn => {
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);
  
  // Fetch graph data
  const fetchGraph = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      
      const response = await fetch(`/api/v1/graphs/${graphId}`);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch graph: ${response.statusText}`);
      }
      
      const data = await response.json();
      setGraph(data);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('An unknown error occurred'));
    } finally {
      setIsLoading(false);
    }
  }, [graphId]);
  
  // Update node position
  const updateNodePosition = useCallback(async (
    nodeId: string, 
    position: { x: number; y: number }
  ) => {
    try {
      const response = await fetch(`/api/v1/graphs/nodes/${nodeId}/position`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ position }),
      });
      
      if (!response.ok) {
        throw new Error(`Failed to update node position: ${response.statusText}`);
      }
      
      // Update local state to avoid refetching
      setGraph((prev) => {
        if (!prev) return null;
        
        return {
          ...prev,
          nodes: prev.nodes.map((node) => 
            node.id === nodeId ? { ...node, position } : node
          ),
        };
      });
    } catch (err) {
      console.error('Error updating node position:', err);
    }
  }, []);
  
  // Initial fetch
  useEffect(() => {
    if (graphId) {
      fetchGraph();
    }
  }, [graphId, fetchGraph]);
  
  return { graph, isLoading, error, updateNodePosition };
};

// app/features/graph-visualization/hooks/useResearchContent.ts
import { useState, useEffect, useCallback } from 'react';
import { ResearchContent } from '../types/graph';

interface UseResearchContentReturn {
  content: ResearchContent | null;
  isLoading: boolean;
  error: Error | null;
  generateContent: (nodeId: string, conceptName: string) => Promise<void>;
}

export const useResearchContent = (
  nodeId?: string,
  conceptName?: string
): UseResearchContentReturn => {
  const [content, setContent] = useState<ResearchContent | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);
  
  // Fetch research content
  const fetchContent = useCallback(async (id: string) => {
    try {
      setIsLoading(true);
      setError(null);
      
      const response = await fetch(`/api/v1/research-content/${id}`);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch research content: ${response.statusText}`);
      }
      
      const data = await response.json();
      
      if (data.status === 'complete' && data.content) {
        setContent(data.content);
      } else {
        setContent(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err : new Error('An unknown error occurred'));
    } finally {
      setIsLoading(false);
    }
  }, []);
  
  // Generate research content
  const generateContent = useCallback(async (
    id: string,
    name: string
  ) => {
    try {
      setIsLoading(true);
      setError(null);
      
      const response = await fetch('/api/v1/research-content', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          node_id: id,
          concept_name: name
        }),
      });
      
      if (!response.ok) {
        throw new Error(`Failed to generate research content: ${response.statusText}`);
      }
      
      const data = await response.json();
      
      if (data.status === 'complete' && data.content) {
        setContent(data.content);
      } else if (data.status === 'processing') {
        // Start polling for results
        const pollInterval = setInterval(async () => {
          const pollResponse = await fetch(`/api/v1/research-content/${id}`);
          const pollData = await pollResponse.json();
          
          if (pollData.status === 'complete' && pollData.content) {
            setContent(pollData.content);
            setIsLoading(false);
            clearInterval(pollInterval);
          } else if (pollData.status === 'error') {
            setError(new Error('Error generating research content'));
            setIsLoading(false);
            clearInterval(pollInterval);
          }
        }, 2000);
        
        // Clear interval after 2 minutes to prevent indefinite polling
        setTimeout(() => {
          clearInterval(pollInterval);
          if (isLoading) {
            setIsLoading(false);
            setError(new Error('Research generation timed out. Please try again.'));
          }
        }, 120000);
      }
    } catch (err) {
      setError(err instanceof Error ? err : new Error('An unknown error occurred'));
      setIsLoading(false);
    }
  }, []);
  
  // Fetch content when node changes
  useEffect(() => {
    if (nodeId) {
      fetchContent(nodeId);
    } else {
      setContent(null);
    }
  }, [nodeId, fetchContent]);
  
  return { content, isLoading, error, generateContent };
};
```

### 5.6 Graph Page Component

The main graph visualization page will integrate all components:

```tsx
// app/graph/[id]/page.tsx
'use client';

import React, { useState } from 'react';
import { ReactFlowProvider } from '@xyflow/react';
import { GraphCanvas } from '@/features/graph-visualization/components/GraphCanvas';
import { ResearchPanel } from '@/features/graph-visualization/components/ResearchPanel';
import { ResizablePanel, ResizablePanelGroup } from '@/components/ui/resizable';

interface GraphPageProps {
  params: {
    id: string;
  };
}

export default function GraphPage({ params }: GraphPageProps) {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  
  return (
    <div className="h-screen w-full">
      <ResizablePanelGroup direction="horizontal">
        <ResizablePanel defaultSize={70} minSize={40}>
          <ReactFlowProvider>
            <GraphCanvas 
              graphId={params.id} 
              onNodeSelect={setSelectedNodeId} 
            />
          </ReactFlowProvider>
        </ResizablePanel>
        
        <ResizablePanel defaultSize={30} minSize={20}>
          <ResearchPanel />
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  );
}
``` 

## 6. Integration with Existing Features

The graph visualization system will be integrated with existing PaperMastery features to provide a seamless user experience.

### 6.1 Paper Detail Page Integration

The Paper Detail page will be updated to include a link to launch the concept graph visualization:

```tsx
// app/papers/[id]/page.tsx
'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { MapIcon } from 'lucide-react';
import { usePaper } from '@/features/papers/hooks/usePaper';
import { useGraph } from '@/features/graph-visualization/hooks/useGraph';

interface PaperDetailPageProps {
  params: {
    id: string;
  };
}

export default function PaperDetailPage({ params }: PaperDetailPageProps) {
  const { paper, isLoading: paperLoading } = usePaper(params.id);
  const [isCreatingGraph, setIsCreatingGraph] = useState(false);
  const router = useRouter();
  
  const handleCreateGraph = async () => {
    try {
      setIsCreatingGraph(true);
      
      const response = await fetch('/api/v1/graphs', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ paper_id: params.id }),
      });
      
      if (!response.ok) {
        throw new Error('Failed to create concept graph');
      }
      
      const data = await response.json();
      router.push(`/graph/${data.id}`);
    } catch (err) {
      console.error('Error creating concept graph:', err);
      setIsCreatingGraph(false);
    }
  };
  
  // Add this button to the existing paper detail page
  const ConceptGraphButton = () => (
    <Button
      onClick={handleCreateGraph}
      disabled={isCreatingGraph}
      className="flex gap-2 items-center"
    >
      <MapIcon size={16} />
      {isCreatingGraph ? 'Creating Graph...' : 'View Concept Graph'}
    </Button>
  );
  
  // Include the ConceptGraphButton in the existing UI
  // The rest of the page remains unchanged
}
```

### 6.2 Learning Path Integration

The concept graph visualization will be integrated with the learning path feature to show relationships between learning items:

```typescript
// app/api/v1/endpoints/items.py (existing file)
# Add new endpoint to get learning items related to graph nodes

@router.get("/by-node/{node_id}", response_model=List[ItemResponse])
async def get_items_by_node(
    node_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    item_service: ItemService = Depends(get_item_service),
    graph_service: GraphService = Depends(get_graph_service)
):
    """Get learning items related to a specific graph node."""
    try:
        # Verify node belongs to a graph owned by the user
        node = await graph_service.get_node(node_id)
        graph = await graph_service.get_graph_basic(node["graph_id"])
        
        if graph.get("user_id") != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access items for this node"
            )
            
        # Get learning items related to the node concept
        items = await item_service.get_items_by_concept(
            paper_id=graph["paper_id"],
            concept_name=node["label"]
        )
        
        return items
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get items by node: {str(e)}"
        )
```

Update the `ResearchPanel` component to show related learning items:

```tsx
// app/features/graph-visualization/components/ResearchPanel.tsx
// Add a new "Learning" tab to the existing component

// ... existing imports ...
import { useLearningItems } from '../hooks/useLearningItems';

// Inside the ResearchPanel component:

// Add this hook call
const { items, isLoading: itemsLoading } = useLearningItems(selectedNode?.id);

// Add this new tab in the Tabs component
<TabsTrigger value="learning" className="flex-1">Learning</TabsTrigger>

// Add this new TabsContent
<TabsContent value="learning" className="mt-4">
  {itemsLoading ? (
    <LoadingState />
  ) : items && items.length > 0 ? (
    <div className="space-y-4">
      <h3 className="font-medium text-sm text-muted-foreground">
        Learning materials related to this concept:
      </h3>
      {items.map((item) => (
        <Card key={item.id} className="overflow-hidden">
          <CardContent className="p-4">
            <div className="flex justify-between items-start gap-2">
              <div>
                <h4 className="font-semibold">{item.title}</h4>
                <p className="text-sm text-muted-foreground line-clamp-2">
                  {item.description}
                </p>
              </div>
              <Button variant="outline" size="sm" asChild>
                <a href={`/items/${item.id}`} target="_blank" rel="noopener noreferrer">
                  Study
                </a>
              </Button>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  ) : (
    <div className="text-center py-6">
      <p className="text-muted-foreground">
        No learning materials available for this concept yet.
      </p>
      <Button variant="outline" size="sm" className="mt-4" asChild>
        <a href={`/papers/${graphId}/items/create?concept=${selectedNode.data.label}`}>
          Create Learning Material
        </a>
      </Button>
    </div>
  )}
</TabsContent>
```

### 6.3 Navigation Integration

The graph visualization feature will be integrated into the main navigation:

```tsx
// app/components/main-nav.tsx (existing file)
// Add graph visualization to the main navigation

// Inside the navigation items array
const navItems = [
  // ... existing items
  {
    title: "My Graphs",
    href: "/graphs",
    icon: <MapIcon className="mr-2 h-4 w-4" />,
  },
];
```

Create a graphs listing page:

```tsx
// app/graphs/page.tsx
'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';

interface Graph {
  id: string;
  title: string;
  description: string;
  created_at: string;
  paper_title: string;
}

export default function GraphsPage() {
  const [graphs, setGraphs] = useState<Graph[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();
  
  useEffect(() => {
    const fetchGraphs = async () => {
      try {
        const response = await fetch('/api/v1/graphs');
        if (!response.ok) {
          throw new Error('Failed to fetch graphs');
        }
        const data = await response.json();
        setGraphs(data);
      } catch (error) {
        console.error('Error fetching graphs:', error);
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchGraphs();
  }, []);
  
  if (isLoading) {
    return (
      <div className="container py-10">
        <h1 className="text-2xl font-bold mb-6">My Concept Graphs</h1>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <Card key={i}>
              <CardHeader className="pb-2">
                <Skeleton className="h-6 w-3/4" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-4 w-full mb-2" />
                <Skeleton className="h-4 w-2/3" />
              </CardContent>
              <CardFooter>
                <Skeleton className="h-10 w-full" />
              </CardFooter>
            </Card>
          ))}
        </div>
      </div>
    );
  }
  
  return (
    <div className="container py-10">
      <h1 className="text-2xl font-bold mb-6">My Concept Graphs</h1>
      
      {graphs.length === 0 ? (
        <div className="text-center py-10">
          <p className="text-muted-foreground mb-4">
            You haven't created any concept graphs yet.
          </p>
          <p className="text-muted-foreground mb-6">
            Create graphs from your paper detail pages to visualize key concepts.
          </p>
          <Button asChild>
            <a href="/papers">Browse Papers</a>
          </Button>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {graphs.map((graph) => (
            <Card key={graph.id}>
              <CardHeader className="pb-2">
                <CardTitle className="text-lg">{graph.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-2">
                  {graph.description || "Concept map for research paper"}
                </p>
                <p className="text-xs text-muted-foreground">
                  Paper: {graph.paper_title}
                </p>
                <p className="text-xs text-muted-foreground">
                  Created: {new Date(graph.created_at).toLocaleDateString()}
                </p>
              </CardContent>
              <CardFooter>
                <Button 
                  onClick={() => router.push(`/graph/${graph.id}`)}
                  className="w-full"
                >
                  View Graph
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
```

### 6.4 User Permissions

The graph visualization feature will respect the existing user permission system:

1. **Graph Creation**: Only users with access to a paper can create a concept graph for it
2. **Graph Viewing**: Graphs are private to the user who created them by default
3. **Graph Sharing**: Users can share graphs with specific recipients (using existing sharing mechanisms)
4. **Team Access**: If the paper is part of a team workspace, the graph can be made accessible to team members

This is enforced through the Row Level Security policies defined in the database schema.

### 6.5 Analytics Integration

The graph visualization feature will be integrated with the existing analytics system:

```typescript
// app/features/graph-visualization/components/GraphCanvas.tsx
// Add analytics tracking to key graph interactions

// Import the analytics service
import { track } from '@/lib/analytics';

// Inside the GraphCanvas component

// Track graph loading
useEffect(() => {
  if (graph) {
    track('graph_loaded', {
      graph_id: graphId,
      paper_id: graph.paper_id,
      node_count: graph.nodes.length,
      edge_count: graph.edges.length
    });
  }
}, [graph, graphId]);

// Track node selection
const onNodeClick = useCallback((_, node) => {
  setSelectedNode(node);
  onNodeSelect(node.id);
  
  track('graph_node_selected', {
    graph_id: graphId,
    node_id: node.id,
    node_type: node.type,
    node_label: node.data.label
  });
}, [setSelectedNode, onNodeSelect, graphId]);

// Track layout changes
const applyLayout = useCallback((layoutType: string) => {
  // Apply layout algorithm
  // ...
  
  track('graph_layout_changed', {
    graph_id: graphId,
    layout_type: layoutType
  });
}, [nodes, setNodes, graphId]);
``` 

## 7. Testing Strategy

A comprehensive testing strategy will be employed to ensure the reliability and quality of the graph visualization feature.

### 7.1 Unit Testing

Unit tests will be created for core service functions and utility methods:

```typescript
// tests/unit/services/graph_service_test.py
import pytest
from unittest.mock import MagicMock, patch
from app.services.graph_service import GraphService

@pytest.fixture
def mock_supabase():
    return MagicMock()

@pytest.fixture
def mock_concept_extraction_service():
    return MagicMock()

@pytest.fixture
def graph_service(mock_supabase, mock_concept_extraction_service):
    return GraphService(mock_supabase, mock_concept_extraction_service)

def test_create_graph(graph_service, mock_supabase, mock_concept_extraction_service):
    # Arrange
    paper_id = "test-paper-id"
    user_id = "test-user-id"
    paper_title = "Test Paper"
    test_concepts = {
        "concepts": [
            {"name": "Concept 1", "description": "Description 1", "type": "concept"},
            {"name": "Concept 2", "description": "Description 2", "type": "methodology"}
        ],
        "relationships": [
            {"source": "Concept 1", "target": "Concept 2", "type": "relates_to"}
        ]
    }
    
    # Mock responses
    mock_supabase.table().select().eq().single().execute.return_value.data = {"title": paper_title}
    mock_concept_extraction_service.extract_concepts.return_value = test_concepts
    mock_supabase.table().insert().execute.return_value = None
    
    # Act
    graph_service.create_graph(paper_id, user_id)
    
    # Assert
    # Verify supabase calls for graph creation
    mock_supabase.table.assert_any_call("graphs")
    mock_supabase.table().insert.assert_called()
    
    # Verify node creation
    mock_supabase.table.assert_any_call("nodes")
    # 1 for paper node + 2 for concept nodes = 3 nodes total
    assert mock_supabase.table("nodes").insert.call_count >= 1
```

Frontend component unit tests:

```tsx
// tests/unit/components/ConceptNode.test.tsx
import React from 'react';
import { render, screen } from '@testing-library/react';
import { ConceptNode } from '@/features/graph-visualization/components/NodeTypes/ConceptNode';

describe('ConceptNode', () => {
  it('renders with label and description', () => {
    // Arrange
    const nodeData = {
      data: {
        label: 'Test Concept',
        description: 'Test Description',
        style: {}
      },
      selected: false
    };
    
    // Act
    render(<ConceptNode {...nodeData} />);
    
    // Assert
    expect(screen.getByText('Test Concept')).toBeInTheDocument();
    expect(screen.getByText('Test Description')).toBeInTheDocument();
  });
  
  it('truncates long descriptions', () => {
    // Arrange
    const longDescription = 'This is a very long description that should be truncated in the UI to avoid taking up too much space in the graph visualization';
    const nodeData = {
      data: {
        label: 'Test Concept',
        description: longDescription,
        style: {}
      },
      selected: false
    };
    
    // Act
    render(<ConceptNode {...nodeData} />);
    
    // Assert
    expect(screen.getByText(/This is a very long description/)).toBeInTheDocument();
    expect(screen.getByText(/\.\.\./)).toBeInTheDocument();
  });
});
```

### 7.2 Integration Testing

Integration tests will ensure that the services work together correctly:

```typescript
// tests/integration/graph_creation_test.py
import pytest
from app.services.concept_extraction_service import ConceptExtractionService
from app.services.graph_service import GraphService
from app.services.llm_service import LLMService
from app.services.paper_service import PaperService

@pytest.mark.integration
async def test_graph_creation_flow(test_db, test_user):
    # Set up services with test dependencies
    llm_service = LLMService(api_key="test_key")
    paper_service = PaperService(test_db)
    concept_extraction_service = ConceptExtractionService(llm_service, paper_service, test_db)
    graph_service = GraphService(test_db, concept_extraction_service)
    
    # Create test paper
    paper_id = await paper_service.create_paper({
        "title": "Test Paper for Graph Creation",
        "authors": ["Test Author"],
        "abstract": "This is a test abstract",
        "full_text": "This is test content mentioning concepts like Machine Learning and Neural Networks"
    }, test_user["id"])
    
    # When graph is created
    graph = await graph_service.create_graph(paper_id, test_user["id"])
    
    # Then graph should be created with nodes and edges
    assert graph is not None
    assert "id" in graph
    assert "nodes" in graph
    assert "edges" in graph
    assert len(graph["nodes"]) > 0  # Should have at least the paper node
    
    # Verify node types and properties
    paper_nodes = [n for n in graph["nodes"] if n["node_type"] == "paper"]
    concept_nodes = [n for n in graph["nodes"] if n["node_type"] != "paper"]
    
    assert len(paper_nodes) == 1
    assert len(concept_nodes) > 0
```

### 7.3 End-to-End Testing

End-to-end tests will validate the full user flow:

```typescript
// tests/e2e/graph_visualization_test.py
import pytest
from playwright.sync_api import Page, expect

@pytest.mark.e2e
def test_create_and_view_graph(page: Page, authenticated_user):
    # Given a user views a paper detail page
    page.goto("/papers/some-test-paper-id")
    
    # When they click the "View Concept Graph" button
    page.click("text=View Concept Graph")
    
    # Then they should be redirected to the graph page
    expect(page).to_have_url("/graph/")
    
    # And the graph should load with nodes
    page.wait_for_selector(".react-flow__node")
    
    # Verify that nodes are visible
    nodes = page.locator(".react-flow__node")
    expect(nodes).to_have_count(3, minimum=True)  # At least 3 nodes (paper + 2 concepts)
    
    # When they click on a concept node
    concept_node = page.locator(".concept-node").first
    concept_node.click()
    
    # Then the research panel should show information about the concept
    research_panel = page.locator(".research-panel")
    expect(research_panel).to_be_visible()
    
    # And they can generate research content
    if page.locator("text=Generate Research").is_visible():
        page.click("text=Generate Research")
        page.wait_for_selector("text=Explanation")
    
    # Verify research content tabs
    expect(page.locator("text=Explanation")).to_be_visible()
    expect(page.locator("text=Applications")).to_be_visible()
    expect(page.locator("text=Related")).to_be_visible()
    expect(page.locator("text=References")).to_be_visible()
```

### 7.4 Performance Testing

Performance tests will ensure the system handles large graphs efficiently:

1. **Load Testing**: Simulate multiple users creating and accessing graphs concurrently
2. **Graph Size Testing**: Test with papers of varying sizes and complexity
3. **API Response Time**: Measure API response times for graph operations

```typescript
// tests/performance/graph_performance_test.py
import asyncio
import pytest
import time
from app.services.graph_service import GraphService

@pytest.mark.performance
async def test_graph_api_response_time(test_db, test_user, large_test_paper):
    # Arrange
    graph_service = GraphService(test_db, mock_concept_extraction_service)
    
    # Create a large graph
    graph_id = await graph_service.create_graph(large_test_paper["id"], test_user["id"])
    
    # Act
    start_time = time.time()
    graph = await graph_service.get_graph(graph_id)
    end_time = time.time()
    
    # Assert
    response_time = end_time - start_time
    assert response_time < 1.0  # Graph should load in under 1 second
    
    # Verify graph size
    assert len(graph["nodes"]) >= 20  # Large paper should have many concepts
```

### 7.5 Accessibility Testing

Accessibility tests will ensure the graph visualization is usable by all users:

1. **Keyboard Navigation**: Ensure users can navigate the graph with keyboard
2. **Screen Reader Compatibility**: Test with common screen readers
3. **Color Contrast**: Verify sufficient contrast for node and edge colors

```typescript
// tests/accessibility/graph_a11y_test.py
import pytest
from playwright.sync_api import Page, expect

@pytest.mark.accessibility
def test_graph_keyboard_navigation(page: Page, authenticated_user):
    # Given a user is on the graph page
    page.goto("/graph/test-graph-id")
    page.wait_for_selector(".react-flow__node")
    
    # When they use Tab to navigate
    page.keyboard.press("Tab")  # Focus first node
    page.keyboard.press("Tab")  # Focus next node
    
    # Then focus should move between elements
    focused_element = page.evaluate("document.activeElement.className")
    expect("react-flow__node" in focused_element).to_be_truthy()
    
    # When they press Enter on a node
    page.keyboard.press("Enter")
    
    # Then the node should be selected and research panel should update
    expect(page.locator(".research-panel h2")).to_be_visible()
```

### 7.6 Security Testing

Security tests will ensure proper access controls and data protection:

1. **Authentication**: Verify that unauthenticated users cannot access graphs
2. **Authorization**: Verify that users cannot access graphs they don't own
3. **Input Validation**: Test handling of malicious inputs

```typescript
// tests/security/graph_security_test.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.mark.security
def test_graph_authorization():
    client = TestClient(app)
    
    # Create two test users
    user1_token = "test_token_1"
    user2_token = "test_token_2"
    
    # User 1 creates a graph
    response = client.post(
        "/api/v1/graphs",
        json={"paper_id": "test-paper-id"},
        headers={"Authorization": f"Bearer {user1_token}"}
    )
    assert response.status_code == 200
    graph_id = response.json()["id"]
    
    # User 2 attempts to access User 1's graph
    response = client.get(
        f"/api/v1/graphs/{graph_id}",
        headers={"Authorization": f"Bearer {user2_token}"}
    )
    assert response.status_code == 403  # Should be forbidden
```

### 7.7 Testing Schedule

Testing will be integrated into the development workflow:

| Testing Phase | Timing | Scope |
|---------------|--------|-------|
| Unit Tests | During development | All services and components |
| Integration Tests | After feature completion | Service interactions |
| End-to-End Tests | Before staging deployment | Complete user flows |
| Performance Tests | Before production deployment | Response times, large graphs |
| Accessibility & Security Tests | Before production deployment | A11y compliance, security controls |
```

## 8. Timeline & Milestones

The graph visualization feature will be implemented in phases to allow for incremental delivery and feedback.

### 8.1 Phase 1: Core Infrastructure (Weeks 1-2)

| Task | Description | Estimated Effort |
|------|-------------|------------------|
| Database Schema Setup | Create tables, indexes, and RLS policies | 3 days |
| Concept Extraction Service | Implement paper analysis and concept extraction | 4 days |
| Graph Service | Implement graph creation and management | 3 days |
| API Endpoints | Implement core graph management endpoints | 2 days |

**Milestone:** Backend infrastructure deployed to staging with ability to create and retrieve graph data.

### 8.2 Phase 2: UI Components (Weeks 3-4)

| Task | Description | Estimated Effort |
|------|-------------|------------------|
| Graph Canvas | Implement main visualization component | 4 days |
| Node Components | Create custom node types | 2 days |
| Edge Components | Create custom edge types | 1 day |
| Graph Controls | Implement layout and formatting controls | 2 days |
| Graph Page | Implement page container and routing | 1 day |

**Milestone:** Basic graph visualization UI deployed to staging.

### 8.3 Phase 3: Research Content (Weeks 5-6)

| Task | Description | Estimated Effort |
|------|-------------|------------------|
| Research Content Service | Implement AI-powered research generation | 3 days |
| Research Panel UI | Implement tabbed research content display | 3 days |
| API Endpoints | Implement research content endpoints | 2 days |
| Content Generation Optimization | Optimize for performance and quality | 2 days |

**Milestone:** Complete research content feature deployed to staging.

### 8.4 Phase 4: Integration & Refinement (Weeks 7-8)

| Task | Description | Estimated Effort |
|------|-------------|------------------|
| Learning Path Integration | Connect with existing learning items | 3 days |
| Paper Detail Integration | Add graph visualization access to paper pages | 1 day |
| Navigation Integration | Add to main navigation | 1 day |
| User Testing & Feedback | Gather and process user feedback | 3 days |
| UI Polish & Refinements | Address feedback and polish UI | 4 days |

**Milestone:** Fully integrated graph visualization feature deployed to production.

### 8.5 Risks & Contingencies

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM-based concept extraction quality | Medium | Implement fallback mechanisms and human review options |
| Performance issues with large graphs | High | Implement pagination, lazy loading, and optimization techniques |
| Complex graph layouts | Medium | Start with simple force-directed layouts, add complex layouts later |
| Integration complexity | Medium | Plan integration points early, implement incrementally |

## 9. Deployment Considerations

### 9.1 Infrastructure Requirements

The graph visualization system will leverage the existing Supabase infrastructure with some optimizations:

1. **Database Resources**: 
   - Monitor database usage and increase resources if needed
   - Graph data is relatively efficient with PostgreSQL JSONB fields
   - Consider partitioning if graph tables grow significantly

2. **Backend Services**:
   - LLM API usage will increase with concept extraction and research generation
   - Set appropriate rate limits and budget alerts for OpenAI API calls
   - Implement caching for repeated concept extraction and research generation

3. **Frontend Resources**:
   - Graph rendering can be computationally intensive for browsers
   - Implement client-side optimizations (virtualization, worker threads)
   - Use progressive enhancement for complex features

### 9.2 Deployment Process

The deployment will follow the existing CI/CD pipeline with these additional steps:

1. **Database Migrations**:
   ```bash
   # Run from CI pipeline
   supabase db push
   ```

2. **Feature Flags**:
   - Implement feature flags to control rollout
   - Initially enable for admin users only, then gradually expand

   ```tsx
   // app/config/features.ts
   export const FEATURES = {
     GRAPH_VISUALIZATION: process.env.NEXT_PUBLIC_ENABLE_GRAPH_VISUALIZATION === 'true',
   };
   ```

3. **Monitoring**:
   - Add specific monitoring for graph operations
   - Monitor LLM API usage and costs
   - Set up alerts for performance bottlenecks

### 9.3 Post-Launch Support

After launching the graph visualization feature, these activities will be prioritized:

1. **Performance Monitoring**:
   - Track API response times for graph operations
   - Monitor client-side rendering performance
   - Identify and address any hotspots

2. **Content Quality Monitoring**:
   - Implement feedback mechanism for AI-generated research content
   - Track and address low-quality or incorrect content
   - Continuously improve prompts based on feedback

3. **Usage Analytics**:
   - Track feature adoption and engagement metrics
   - Identify most-used and least-used aspects of the feature
   - Use data to guide future refinements

4. **Documentation**:
   - Create user guides for graph visualization features
   - Add contextual help and tooltips
   - Document backend services for developer reference

### 9.4 Rollback Plan

In case of critical issues, a rollback plan is defined:

1. **Database**: 
   - Schema changes are additive and non-destructive
   - Can maintain schema while disabling UI features

2. **UI Features**:
   - Disable feature flags to hide UI elements
   - Return to previous paper detail view

3. **API Endpoints**:
   - Versioned endpoints allow graceful degradation

```typescript
// Rollback command example
supabase functions deploy rollback-graph-feature --project-ref <ref-id>
```