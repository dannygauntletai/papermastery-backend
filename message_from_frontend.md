# Graph Visualization Backend Implementation Instructions

Dear Backend Team,

Our frontend has implemented a graph visualization feature using React Flow for concept mapping of research papers. We need you to implement the necessary backend services using FastAPI to support this functionality. Below are your implementation instructions:

## Priority Tasks

1. **Create Database Schema** - Add these tables to the existing database:
   - `graphs` - Main table for storing graph metadata
   - `nodes` - For storing concept nodes
   - `edges` - For storing relationships between nodes
   - `research_content` - For storing AI-generated content about concepts

2. **Implement Core API Endpoints**:
   - Graph creation and retrieval
   - Node and edge CRUD operations
   - Research content generation and retrieval

3. **Implement Background Tasks**:
   - Automatic graph generation from paper content
   - AI-powered research content generation

## Database Schema Details

Please create the following tables with these fields:

### graphs
- `id` (uuid, primary key)
- `paper_id` (uuid, foreign key to papers table)
- `user_id` (uuid, foreign key to users)
- `title` (text)
- `description` (text)
- `status` (text, default: 'draft')
- `settings` (jsonb, default: '{}')
- `created_at` (timestamp with time zone)
- `updated_at` (timestamp with time zone)

### nodes
- `id` (uuid, primary key)
- `graph_id` (uuid, foreign key to graphs table)
- `label` (text)
- `description` (text)
- `node_type` (text, default: 'concept')
- `position` (jsonb, stores x/y coordinates)
- `style` (jsonb, default: '{}')
- `created_at` (timestamp with time zone)
- `updated_at` (timestamp with time zone)

### edges
- `id` (uuid, primary key)
- `graph_id` (uuid, foreign key to graphs table)
- `source` (uuid, references nodes.id)
- `target` (uuid, references nodes.id)
- `edge_type` (text, default: 'related_to')
- `label` (text)
- `style` (jsonb, default: '{}')
- `created_at` (timestamp with time zone)

### research_content
- `id` (uuid, primary key)
- `node_id` (uuid, references nodes.id)
- `explanation` (text)
- `applications` (text)
- `related_concepts` (jsonb, array of concepts)
- `references` (text)
- `status` (text, default: 'complete')
- `created_at` (timestamp with time zone)
- `updated_at` (timestamp with time zone)

## Required API Endpoints

Implement these endpoints with the specified functionality:

### Graph Management
- `POST /api/v1/graphs` - Create a new graph for a paper
- `GET /api/v1/graphs/{id}` - Get graph with all nodes and edges
- `GET /api/v1/papers/{paper_id}/graphs` - List all graphs for a paper

### Node Management
- `POST /api/v1/graphs/{graph_id}/nodes` - Create a new node
- `PUT /api/v1/nodes/{id}` - Update a node (position, label, etc.)
- `DELETE /api/v1/nodes/{id}` - Delete a node and its connected edges

### Edge Management
- `POST /api/v1/graphs/{graph_id}/edges` - Create an edge between nodes
- `PUT /api/v1/edges/{id}` - Update an edge
- `DELETE /api/v1/edges/{id}` - Delete an edge

### Research Content
- `GET /api/v1/nodes/{node_id}/research-content` - Get research content for a node
- `POST /api/v1/nodes/{node_id}/generate-research-content` - Generate research content
- `GET /api/v1/research-content-jobs/{job_id}` - Check generation status

## Background Tasks

Implement these background tasks using FastAPI's background task system:

1. **build-concept-graph**
   - Input: `graph_id`, `paper_id`
   - Purpose: Analyze a paper and generate a concept graph automatically
   - Steps:
     - Extract concepts from paper text using AI
     - Create nodes with appropriate positions
     - Create edges between related concepts
     - Update graph status when complete

2. **generate-research-content**
   - Input: `node_id`, `concept_name`
   - Purpose: Generate detailed research content for a concept node
   - Steps:
     - Get paper context for the concept
     - Generate comprehensive explanation, applications, etc.
     - Save to research_content table
     - Update status as it progresses

## AI Integration

For both tasks above, you'll need to integrate with an AI service:

1. **For concept extraction**:
   - Provide paper text to the AI service
   - Parse response into nodes (concepts) and edges (relationships)
   - Example prompt: "Extract the main concepts and their relationships from this research paper..."

2. **For research content generation**:
   - Provide concept name and paper context
   - Generate comprehensive explanations, applications, related concepts
   - Example prompt: "Generate detailed explanations for the concept [X] from this paper..."

## Real-time Updates

Implement WebSocket support:
- Endpoint: `/ws/graphs/{graph_id}`
- Send updates when nodes or edges change
- Send updates when research content generation status changes

## Authentication & Error Handling

- All endpoints must require authentication
- Users should only access their own graphs
- Implement appropriate error responses (400, 404, 403, 500)
- Return informative error messages for display in UI

## Testing Tips

- Test graph creation with various paper inputs
- Test concurrent editing of graphs
- Test error handling for missing resources
- Test AI generation with various concept types

## Implementation Schedule

1. Week 1: Database schema and basic CRUD endpoints
2. Week 2: AI integration for concept extraction
3. Week 3: Background tasks and research content generation
4. Week 4: WebSockets and real-time updates
5. Week 5: Testing and documentation

If you have any questions about the frontend implementation or API requirements, please consult the frontend team directly.

Thank you!
