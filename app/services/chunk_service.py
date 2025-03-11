import re
from typing import List, Dict, Any
from uuid import UUID

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.logger import get_logger
from app.core.exceptions import ChunkingError

logger = get_logger(__name__)


async def chunk_text(
    text: str,
    paper_id: UUID,
    max_chunk_size: int = 1000,
    overlap: int = 100
) -> List[Dict[str, Any]]:
    """
    Break text into overlapping chunks of approximately equal size.
    
    Args:
        text: The text to chunk
        paper_id: The ID of the paper
        max_chunk_size: Maximum size of each chunk
        overlap: Overlap between chunks
        
    Returns:
        List of dictionaries containing chunk text and metadata
    """
    try:
        logger.info(f"Chunking text for paper ID: {paper_id}")
        
        # Extract sections from the text
        sections = extract_sections(text)
        chunks = []
        
        # Process each section
        for section_num, (section_title, section_content) in enumerate(sections):
            # Use Langchain RecursiveCharacterTextSplitter for each section
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=max_chunk_size,
                chunk_overlap=overlap,
                separators=["\n\n", "\n", ". ", " ", ""],
                keep_separator=True
            )
            
            section_chunks = text_splitter.create_documents(
                [section_content], 
                metadatas=[{
                    "section_title": section_title,
                    "section_number": section_num
                }]
            )
            
            for chunk_num, chunk_doc in enumerate(section_chunks):
                chunk_text = chunk_doc.page_content
                
                # Skip empty chunks
                if not chunk_text.strip():
                    continue
                
                # Format the chunk with metadata
                chunk = {
                    "text": chunk_text,
                    "paper_id": str(paper_id),
                    "chunk_id": f"{section_num}_{chunk_num}",
                    "metadata": {
                        "section_title": section_title,
                        "is_introduction": "introduction" in section_title.lower(),
                        "is_conclusion": any(
                            word in section_title.lower() 
                            for word in ["conclusion", "discussion", "summary"]
                        ),
                        "is_methodology": any(
                            word in section_title.lower() 
                            for word in ["method", "approach", "experiment"]
                        ),
                        "length": len(chunk_text)
                    }
                }
                chunks.append(chunk)
        
        # If no sections were found, create chunks from the raw text
        if not chunks:
            logger.warning(
                f"No sections found in text for paper ID: {paper_id}. "
                "Using raw text chunking."
            )
            
            # Use Langchain RecursiveCharacterTextSplitter for raw text
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=max_chunk_size,
                chunk_overlap=overlap,
                separators=["\n\n", "\n", ". ", " ", ""],
                keep_separator=True
            )
            
            raw_chunks = text_splitter.create_documents([text])
            
            for chunk_num, chunk_doc in enumerate(raw_chunks):
                chunk_text = chunk_doc.page_content
                
                # Skip empty chunks
                if not chunk_text.strip():
                    continue
                
                # Format the chunk with metadata
                chunk = {
                    "text": chunk_text,
                    "paper_id": str(paper_id),
                    "chunk_id": f"raw_{chunk_num}",
                    "metadata": {
                        "section_title": "No Section",
                        "is_introduction": False,
                        "is_conclusion": False,
                        "is_methodology": False,
                        "length": len(chunk_text)
                    }
                }
                chunks.append(chunk)
        
        logger.info(
            f"Successfully created {len(chunks)} chunks for paper ID: {paper_id}"
        )
        return chunks
        
    except Exception as e:
        logger.error(f"Error chunking text for paper ID {paper_id}: {str(e)}")
        raise ChunkingError(f"Error chunking text: {str(e)}")


def extract_sections(text: str) -> List[tuple]:
    """
    Extract sections from a scientific paper text.
    
    Args:
        text: The paper text
        
    Returns:
        List of tuples (section_title, section_content)
    """
    # Define patterns to identify section headers
    section_patterns = [
        r'^(?:\d+\.?\s*)?(?:INTRODUCTION|ABSTRACT|BACKGROUND|RELATED WORK|METHODOLOGY|METHODS|EXPERIMENTS|RESULTS|DISCUSSION|CONCLUSION|REFERENCES)(?:\s*\d+\.?)?(?:\n|\s*$)',
        r'^(?:\d+\.?\s*)?[A-Z][A-Z\s]+(?:\n|\s*$)',  # All caps title
        r'^\d+\.\s+[A-Z][a-zA-Z\s]+(?:\n|\s*$)'      # Numbered sections
    ]
    
    # Find potential section headers
    lines = text.split('\n')
    sections = []
    current_section = ("Introduction", "")
    
    for line in lines:
        found_header = False
        
        for pattern in section_patterns:
            match = re.match(pattern, line, re.MULTILINE)
            if match:
                # If we found a header, save the current section and start a new one
                if current_section[1].strip():
                    sections.append(current_section)
                current_section = (line.strip(), "")
                found_header = True
                break
        
        if not found_header:
            # Add this line to the current section
            current_section = (
                current_section[0], 
                current_section[1] + "\n" + line if current_section[1] else line
            )
    
    # Add the last section
    if current_section[1].strip():
        sections.append(current_section)
    
    # If no sections were found, create a single section with the entire text
    if not sections:
        sections = [("Introduction", text)]
    
    return sections 