from typing import List, Dict, Any, Optional
import asyncio
import json
import os
import tempfile
from uuid import UUID
from openai import OpenAI, AsyncOpenAI
import google.generativeai as genai
from dotenv import load_dotenv
from pathlib import Path
import re

# Load environment variables from .env file
load_dotenv()

from app.core.logger import get_logger
from app.core.config import OPENAI_API_KEY, OPENAI_MODEL, GEMINI_API_KEY, GEMINI_MODEL, APP_ENV
from app.core.exceptions import LLMServiceError
from app.database.supabase_client import get_paper_full_text
from app.services.pdf_service import get_paper_pdf

logger = get_logger(__name__)

# Get OpenAI API key directly from environment for consistency
openai_api_key = os.environ.get("OPENAI_API_KEY")
if not openai_api_key:
    openai_api_key = OPENAI_API_KEY
    # Ensure it's also in the environment
    if openai_api_key:
        os.environ["OPENAI_API_KEY"] = openai_api_key
        logger.info(f"OpenAI client initialized with API key: {openai_api_key[:8]}... in llm_service.py")

# Get Gemini API key directly from environment for consistency
gemini_api_key = os.environ.get("GEMINI_API_KEY")
if not gemini_api_key:
    gemini_api_key = GEMINI_API_KEY
    # Ensure it's also in the environment
    if gemini_api_key:
        os.environ["GEMINI_API_KEY"] = gemini_api_key
        logger.info(f"Gemini client initialized with API key: {gemini_api_key[:8]}... in llm_service.py")

# Initialize the OpenAI client if API key is available
openai_client = None
if openai_api_key:
    openai_client = AsyncOpenAI(api_key=openai_api_key)
    logger.info(f"OpenAI client initialized with API key: {openai_api_key[:8]}... in llm_service.py")

# Initialize the Gemini client if API key is available
if gemini_api_key:
    genai.configure(api_key=gemini_api_key)
    logger.info(f"Gemini client initialized with API key: {gemini_api_key[:8]}... in llm_service.py")

async def generate_response(
    query: str,
    context_chunks: List[Dict[str, Any]],
    paper_title: Optional[str] = None,
    max_tokens: int = 1000,
    paper_id: Optional[UUID] = None
) -> Dict[str, Any]:
    """
    Generate a response to a query using the Gemini API with direct PDF processing.
    
    Args:
        query: The user's query
        context_chunks: List of text chunks with metadata (kept for backward compatibility)
        paper_title: Optional title of the paper for context
        max_tokens: Maximum number of tokens in the response
        paper_id: Optional UUID of the paper to retrieve the PDF
        
    Returns:
        Dictionary containing the generated response and metadata
        
    Raises:
        LLMServiceError: If there's an error generating a response
    """
    try:
        logger.info(f"Generating response for query: {query[:50]}...")
        
        # If paper_id is provided, get the PDF
        pdf_path = None
        if paper_id:
            try:
                pdf_path = await get_paper_pdf(paper_id)
                if pdf_path:
                    logger.info(f"Retrieved PDF for paper {paper_id}: {pdf_path}")
                else:
                    logger.warning(f"Could not retrieve PDF for paper {paper_id}")
            except Exception as e:
                logger.warning(f"Error retrieving PDF for paper {paper_id}: {str(e)}")
                # Continue with fallback if PDF retrieval fails
        
        # If PDF is available, use Gemini Files API
        if pdf_path and gemini_api_key:
            return await generate_response_with_pdf(query, pdf_path, paper_title, max_tokens)
        
        # Fallback: If PDF is not available or Gemini is not available, use the old method
        logger.info("Falling back to text-based response generation")
        
        # Get full text if available
        full_text = None
        if paper_id:
            try:
                full_text = await get_paper_full_text(paper_id)
                logger.info(f"Retrieved full text for paper {paper_id} ({len(full_text) if full_text else 0} characters)")
            except Exception as e:
                logger.warning(f"Error retrieving full text for paper {paper_id}: {str(e)}")
                # Continue with chunks if full text retrieval fails
        
        # If full text is not available, use the context chunks
        if not full_text:
            logger.info(f"Full text not available, using {len(context_chunks)} context chunks")
            # Format context chunks as a string with citations
            formatted_chunks = []
            for i, chunk in enumerate(context_chunks):
                # Use chunk_id if available, otherwise use a sequential number
                chunk_id = chunk.get("chunk_id", f"chunk_{i}")
                text = chunk.get("text", "")
                
                # Add the chunk to the formatted chunks with a citation marker
                formatted_chunks.append(f"[{i+1}] {text}")
                
            # Join all formatted chunks with separators
            context_text = "\n\n".join(formatted_chunks)
        else:
            context_text = full_text
        
        # Construct the prompt
        paper_context = f" about the paper '{paper_title}'" if paper_title else ""
        
        prompt = f"""You are an AI research assistant. Answer the following question{paper_context} 
using ONLY the information from the provided paper text.

If the question cannot be answered using the provided text, say "I cannot answer this question based on the 
available information from the paper." and suggest what further information might be needed.

Question: {query}

Paper Text:
{context_text}

Answer the question in a clear, concise manner. If appropriate, you may format your response using Markdown.
If there are relevant parts of the text that directly support your answer, you may quote them.

Your response should be structured as follows:
1. A direct answer to the question
2. Supporting evidence from the paper, with quotes and references to specific sections
3. Any limitations or caveats to your answer based on the available information
"""

        # Use Gemini if available, otherwise fall back to OpenAI
        if gemini_api_key:
            # Call the Gemini API to generate a response
            model = genai.GenerativeModel(GEMINI_MODEL)
            response = await asyncio.to_thread(
                model.generate_content,
                prompt,
                generation_config={
                    "max_output_tokens": max_tokens,
                    "temperature": 0.3,  # Lower temperature for more deterministic responses
                }
            )
            
            # Extract the response text
            response_text = response.text.strip()
        elif openai_api_key and openai_client:
            # Fall back to OpenAI if Gemini is not available
            logger.warning("Gemini API key not available, falling back to OpenAI")
            
            # Call the OpenAI API to generate a response
            response = await openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "system", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.3,  # Lower temperature for more deterministic responses
            )
            
            # Extract the response text
            response_text = response.choices[0].message.content.strip()
        else:
            raise LLMServiceError("Neither Gemini nor OpenAI API key is available")
        
        # Extract sources from the response if possible
        sources = extract_sources_from_text(response_text, context_chunks)
        
        # Return the response with metadata
        result = {
            "response": response_text,
            "query": query,
            "sources": sources if sources else [
                {
                    "chunk_id": chunk.get("chunk_id", f"chunk_{i}"),
                    "text": chunk.get("text", "")[:200] + "..." if len(chunk.get("text", "")) > 200 else chunk.get("text", ""),
                    "metadata": chunk.get("metadata", {})
                }
                for i, chunk in enumerate(context_chunks)
            ] if context_chunks else []
        }
        
        logger.info("Response generated successfully")
        return result
        
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}")
        raise LLMServiceError(f"Error generating response: {str(e)}")

async def generate_response_with_pdf(
    query: str,
    pdf_path: str,
    paper_title: Optional[str] = None,
    max_tokens: int = 1000
) -> Dict[str, Any]:
    """
    Generate a response to a query using the Gemini Files API with a PDF.
    
    Args:
        query: The user's query
        pdf_path: Path to the PDF file
        paper_title: Optional title of the paper for context
        max_tokens: Maximum number of tokens in the response
        
    Returns:
        Dictionary containing the generated response and metadata
        
    Raises:
        LLMServiceError: If there's an error generating a response
    """
    try:
        logger.info(f"Generating response with PDF for query: {query[:50]}...")
        
        # Construct the prompt
        paper_context = f" about the paper '{paper_title}'" if paper_title else ""
        
        prompt = f"""You are an AI research assistant. Answer the following question{paper_context} 
using ONLY the information from the provided PDF.

If the question cannot be answered using the provided PDF, say "I cannot answer this question based on the 
available information from the paper." and suggest what further information might be needed.

Question: {query}

Answer the question in a clear, concise manner. If appropriate, you may format your response using Markdown.

Your response MUST be structured as follows:
1. A direct answer to the question
2. Supporting evidence from the paper, with quotes and references to specific sections
3. Any limitations or caveats to your answer based on the available information

For each piece of supporting evidence, include the exact quote from the paper and the page number or section where it appears.
"""

        # Open the PDF file
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            raise LLMServiceError(f"PDF file not found: {pdf_path}")
        
        # Call the Gemini API with the PDF
        model = genai.GenerativeModel(GEMINI_MODEL)
        
        # Upload the PDF file
        with open(pdf_path, "rb") as f:
            pdf_content = f.read()
            
        # Use the file content directly in the generate_content call
        response = await asyncio.to_thread(
            model.generate_content,
            [
                prompt,
                {"mime_type": "application/pdf", "data": pdf_content}
            ],
            generation_config={
                "max_output_tokens": max_tokens,
                "temperature": 0.3,  # Lower temperature for more deterministic responses
            }
        )
        
        # Extract the response text
        response_text = response.text.strip()
        
        # Extract sources from the response
        sources = extract_sources_from_pdf_response(response_text)
        
        # Return the response with metadata
        result = {
            "response": response_text,
            "query": query,
            "sources": sources
        }
        
        logger.info("Response with PDF generated successfully")
        return result
        
    except Exception as e:
        logger.error(f"Error generating response with PDF: {str(e)}")
        raise LLMServiceError(f"Error generating response with PDF: {str(e)}")

def extract_sources_from_pdf_response(response_text: str) -> List[Dict[str, Any]]:
    """
    Extract sources from a response generated with a PDF.
    
    Args:
        response_text: The response text from Gemini
        
    Returns:
        List of sources extracted from the response
    """
    sources = []
    
    # Look for quotes in the response
    lines = response_text.split('\n')
    for i, line in enumerate(lines):
        # Look for quoted text
        if '"' in line or '"' in line or '"' in line or "'" in line:
            # Extract the quote
            quote_start = line.find('"') if '"' in line else (line.find('"') if '"' in line else (line.find("'") if "'" in line else -1))
            quote_end = line.rfind('"') if '"' in line else (line.rfind('"') if '"' in line else (line.rfind("'") if "'" in line else -1))
            
            if quote_start != -1 and quote_end != -1 and quote_end > quote_start:
                quote = line[quote_start+1:quote_end]
                
                # Look for page or section reference
                reference = ""
                if "page" in line.lower() or "section" in line.lower() or "p." in line.lower() or "sec." in line.lower():
                    # Extract the reference
                    reference = line[quote_end+1:].strip()
                    if reference.startswith("(") and reference.endswith(")"):
                        reference = reference[1:-1]
                
                # Add the source
                sources.append({
                    "chunk_id": f"quote_{len(sources)+1}",
                    "text": quote,
                    "metadata": {
                        "reference": reference
                    }
                })
    
    return sources

def extract_sources_from_text(response_text: str, context_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extract sources from a response generated with text.
    
    Args:
        response_text: The response text from Gemini
        context_chunks: The context chunks used to generate the response
        
    Returns:
        List of sources extracted from the response
    """
    sources = []
    
    # Look for quotes in the response
    lines = response_text.split('\n')
    for i, line in enumerate(lines):
        # Look for quoted text
        if '"' in line or '"' in line or '"' in line or "'" in line:
            # Extract the quote
            quote_start = line.find('"') if '"' in line else (line.find('"') if '"' in line else (line.find("'") if "'" in line else -1))
            quote_end = line.rfind('"') if '"' in line else (line.rfind('"') if '"' in line else (line.rfind("'") if "'" in line else -1))
            
            if quote_start != -1 and quote_end != -1 and quote_end > quote_start:
                quote = line[quote_start+1:quote_end]
                
                # Try to find the chunk that contains this quote
                for chunk in context_chunks:
                    if quote in chunk.get("text", ""):
                        # Add the source
                        sources.append({
                            "chunk_id": chunk.get("chunk_id", f"chunk_{len(sources)+1}"),
                            "text": quote,
                            "metadata": chunk.get("metadata", {})
                        })
                        break
    
    return sources

async def mock_generate_response(
    query: str,
    context_chunks: List[Dict[str, Any]],
    paper_title: Optional[str] = None,
    max_tokens: int = 1000,
    paper_id: Optional[UUID] = None
) -> Dict[str, Any]:
    """
    Mock version of generate_response for testing without calling the API.
    
    Args:
        query: The user's query
        context_chunks: List of text chunks with metadata to use as context
        paper_title: Optional title of the paper for context
        max_tokens: Maximum number of tokens in the response
        paper_id: Optional UUID of the paper to retrieve full text
        
    Returns:
        Dictionary containing the generated response and metadata
    """
    # Simulate API latency
    await asyncio.sleep(0.5)
    
    # Create a simple response based on the query and chunks
    chunk_texts = [chunk.get("text", "")[:50] + "..." for chunk in context_chunks]
    chunk_summary = " ".join(chunk_texts)
    
    paper_context = f" about the paper '{paper_title}'" if paper_title else ""
    
    response_text = f"""Based on the paper{paper_context}, I can provide the following information:

The content discusses {chunk_summary}.

Your query was about "{query}". According to the paper [1], this topic is addressed in several sections.

## Key points:
1. First important point from the paper
2. Second important point
3. Third important point

For more detailed information, you may want to refer to the complete paper.
"""
    
    # Return mock response with metadata
    return {
        "response": response_text,
        "query": query,
        "sources": [
            {
                "chunk_id": chunk.get("chunk_id", f"chunk_{i}"),
                "text": chunk.get("text", "")[:200] + "..." if len(chunk.get("text", "")) > 200 else chunk.get("text", ""),
                "metadata": chunk.get("metadata", {})
            }
            for i, chunk in enumerate(context_chunks)
        ]
    } 

async def generate_text(
    prompt: str,
    max_tokens: int = 1000,
    temperature: float = 0.7
) -> str:
    """
    Generate text using a Large Language Model.
    
    Args:
        prompt: The prompt to generate a response for
        max_tokens: Maximum tokens to generate
        temperature: Controls randomness (0.0-1.0)
        
    Returns:
        Generated text for the given prompt
        
    Raises:
        LLMServiceError: If an error occurs while generating the text
    """
    global openai_client
    
    try:
        # Use mock for testing environments
        if APP_ENV == "testing":
            return await mock_generate_text(prompt, max_tokens, temperature)
            
        logger.info(f"Generating text for prompt: {prompt[:50]}...")
        
        # Use Gemini if available, otherwise fall back to OpenAI
        if gemini_api_key:
            # Call the Gemini API to generate a response
            model = genai.GenerativeModel(GEMINI_MODEL)
            response = await asyncio.to_thread(
                model.generate_content,
                prompt,
                generation_config={
                    "max_output_tokens": max_tokens,
                    "temperature": temperature,
                }
            )
            
            # Extract the response text
            generated_text = response.text
        elif openai_api_key and openai_client:
            # Fall back to OpenAI if Gemini is not available
            logger.warning("Gemini API key not available, falling back to OpenAI")
            
            # Use the global client instance instead of creating a new one
            if openai_client is None:
                # Reinitialize if needed
                openai_client = AsyncOpenAI(api_key=openai_api_key)
                logger.info(f"Reinitialized OpenAI client with API key prefix: {openai_api_key[:8]}...")
            
            response = await openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            generated_text = response.choices[0].message.content
        else:
            raise LLMServiceError("Neither Gemini nor OpenAI API key is available")
        
        logger.info(f"Successfully generated text ({len(generated_text)} characters)")
        return generated_text
        
    except Exception as e:
        error_msg = f"Error generating text: {str(e)}"
        logger.error(error_msg)
        raise LLMServiceError(error_msg)


async def mock_generate_text(
    prompt: str,
    max_tokens: int = 1000,
    temperature: float = 0.7
) -> str:
    """
    Mock version of generate_text for testing purposes.
    
    Args:
        prompt: The prompt to generate a response for
        max_tokens: Maximum tokens to generate
        temperature: Controls randomness (0.0-1.0)
        
    Returns:
        Generated text for the given prompt
    """
    # Simulate API latency
    await asyncio.sleep(0.5)
    
    # Determine the type of summary based on the prompt
    if "beginner-friendly summary" in prompt.lower():
        return """
Neural networks are computer systems inspired by the human brain. Think of them as digital brains that can learn patterns from data. This research paper looked at how different types of neural networks perform on language tasks like understanding sentiment in text, identifying names of people and places, and answering questions.

The researchers found that a special type of neural network called a "transformer" consistently works better than older types of neural networks (called RNNs). This is especially true for tasks that require understanding relationships between words that are far apart in a sentence. They also invented a new way for these networks to pay attention to important parts of text, which improved performance by about 7%.

In everyday terms, this research helps make technology like virtual assistants, chatbots, and translation services work better. The improvements they discovered could lead to computer systems that understand human language more accurately, making our interactions with technology more natural and effective.
"""
    elif "intermediate-level summary" in prompt.lower():
        return """
# Neural Network Architectures for NLP Tasks: A Comparative Analysis

## Overview
This study evaluates the effectiveness of various neural network architectures for natural language processing (NLP) tasks. The researchers specifically compare transformer-based models with recurrent neural networks (RNNs) across multiple NLP applications, including sentiment analysis, named entity recognition (NER), and question answering. The study introduces a novel attention mechanism that enhances performance on context-dependent tasks.

## Methodology
The researchers implemented and compared three primary neural network architectures:

1. **Long Short-Term Memory (LSTM) networks** - A type of RNN designed to address the vanishing gradient problem, allowing them to capture longer-term dependencies in sequential data.
2. **Gated Recurrent Units (GRUs)** - A simplified variant of LSTMs that uses fewer parameters.
3. **Transformer models** - Architecture based entirely on attention mechanisms rather than recurrence.

All models were implemented in PyTorch and trained on identical datasets using pre-trained GloVe embeddings as input representations. Performance was evaluated using standard metrics including precision, recall, and F1 scores.

## Results
Transformer-based architectures consistently outperformed RNN variants across all evaluated tasks. The performance gap was most significant in tasks requiring long-range dependency understanding, with transformers achieving an average F1 score of 0.87 compared to 0.79 for LSTMs and 0.78 for GRUs. The novel attention mechanism proposed by the researchers yielded an additional 7.2% improvement on context-heavy tasks.

## Implications
These findings suggest that attention mechanisms are particularly effective for modeling complex language relationships. The superior performance of transformers can be attributed to their ability to directly model relationships between all words in a sequence, regardless of their distance from each other. This represents a fundamental advantage over recurrent architectures that process text sequentially.

The study indicates that future NLP research should focus on attention mechanism innovations, though challenges remain in terms of computational efficiency, as attention operations scale quadratically with sequence length. Additionally, the researchers note that task-specific architectural modifications can yield substantial benefits, suggesting that general-purpose models may not always be optimal for specialized applications.
"""
    elif "advanced, technically detailed summary" in prompt.lower():
        return """
# Technical Analysis of Neural Network Architectures for Natural Language Processing

## Abstract
This study provides a comprehensive evaluation of contemporary neural network architectures in the context of natural language processing (NLP), with particular emphasis on the performance differential between transformer-based and recurrent neural network (RNN) implementations. Experimental results demonstrate statistically significant performance advantages for transformer architectures across all evaluated downstream tasks, with particular efficacy in modeling long-range dependencies. The novel contribution includes a syntactically-informed attention mechanism that yields a 7.2% performance improvement on context-dependent tasks. Results suggest architectural innovations focused on attention mechanisms represent the most promising direction for advancing NLP performance.

## Research Context and Objectives
The research addresses the comparative efficacy of various neural architectures in NLP applications. The field has witnessed a paradigm shift from traditional approaches relying on feature engineering toward representation learning methodologies. The transition from RNN-based architectures (including LSTM and GRU variants) to transformer-based models has dramatically altered the landscape of NLP research and applications.

The primary research objectives encompass:
1. Quantitative comparison of transformer and RNN architectures across diverse NLP tasks
2. Identification of task-specific performance characteristics for each architecture
3. Development and evaluation of an enhanced attention mechanism optimized for context-dependent tasks
4. Analysis of computational efficiency trade-offs between architectural approaches

## Methodological Approach
The experimental framework employed a controlled comparative methodology utilizing three principal neural architectures:

1. **Long Short-Term Memory (LSTM) networks**: Implemented with standard forget gate configuration and peephole connections, with hidden state dimensionality of 512.
2. **Gated Recurrent Units (GRU)**: Implemented with hidden dimensionality matched to the LSTM configuration for comparative validity.
3. **Transformer models**: Implemented following the architecture described by Vaswani et al. (2017), utilizing 8 attention heads and 6 encoder/decoder layers.

All implementations utilized identical preprocessing pipelines, tokenization methodologies, and embedding initializations via pre-trained GloVe vectors (Pennington et al., 2014). Training employed AdamW optimization with a linear warmup and cosine decay learning rate schedule. Hyperparameter optimization was conducted via Bayesian optimization techniques.

The proposed attention mechanism enhancement incorporates syntactic structure awareness through dependency parsing information, which is integrated into the self-attention computation via a modified attention scoring function:

A(Q, K, V) = softmax((QK^T + S)/√d_k)V

where S represents a syntax-aware bias matrix derived from dependency parse structures.

## Results
Quantitative evaluation across the task spectrum demonstrates consistent transformer superiority, with performance differentials particularly pronounced in question answering (9.3 percentage point advantage), coreference resolution (7.8 percentage point advantage), and long-document sentiment analysis (6.2 percentage point advantage).

The syntax-aware attention mechanism further enhanced performance metrics, with statistically significant improvements (p < 0.01) observed across all context-heavy tasks. Performance on syntactically complex sentences showed the most substantial improvements, suggesting the mechanism effectively leverages structural information.

Efficiency analysis reveals the expected computational complexity differentials, with transformers demonstrating O(n²) scaling characteristics with sequence length, compared to the O(n) scaling of RNN variants. However, the parallelization capabilities of transformer architectures resulted in faster training convergence despite the theoretical complexity disadvantage.

## Theoretical Implications
The empirical results support the theoretical advantage of direct modeling of long-range dependencies through attention mechanisms versus the sequential information propagation in recurrent architectures. The performance differential on tasks requiring understanding of distant contextual relationships provides compelling evidence for the fundamental architectural advantage of transformers in capturing complex linguistic phenomena.

The effectiveness of the syntax-aware attention mechanism suggests that explicit incorporation of linguistic structure remains valuable despite the impressive capability of transformer models to implicitly learn such relationships. This finding indicates potential complementarity between neural approaches and linguistic formalisms.

## Limitations and Future Research
### Limitations
The primary limitations include:
1. Computational resource requirements constraining the exploration of larger model configurations
2. Dataset limitations, particularly for low-resource languages and specialized domains
3. The quadratic computational scaling of standard attention mechanisms with sequence length

### Future Research Directions
Promising research directions emerging from this analysis include:
1. Development of more computationally efficient attention variants that preserve modeling power while reducing the quadratic complexity constraint
2. Investigation of task-specific architectural optimizations given the observed variability in relative performance advantages
3. Exploration of hybrid architectures that combine the strengths of different neural network paradigms
4. Further integration of explicit linguistic knowledge into neural architectures through enhanced attention mechanisms

## Conclusion
This research provides empirical validation for the architectural advantages of transformer models in NLP tasks, particularly through their ability to model direct relationships between arbitrarily distant tokens. The proposed syntax-aware attention mechanism demonstrates that further performance gains are achievable through targeted architectural enhancements. These findings suggest continued research emphasis on attention mechanism innovations is likely to yield the most significant advances in NLP performance.
"""
    else:
        # Default fallback response
        return "Generated text for your query about " + prompt[:50] + "..." 

async def generate_summary_json(
    prompt: str,
    max_tokens: int = 2500,
    temperature: float = 0.3
) -> Dict[str, str]:
    """
    Generate a JSON response containing paper summaries and extracted abstract using a Large Language Model.
    
    Args:
        prompt: The prompt to generate summaries and extract abstract
        max_tokens: Maximum tokens to generate
        temperature: Controls randomness (0.0-1.0)
        
    Returns:
        Dictionary containing the extracted abstract and generated summaries (beginner, intermediate, advanced)
        
    Raises:
        LLMServiceError: If an error occurs while generating or parsing the JSON
    """
    try:
        logger.info("Generating paper summaries and extracting abstract in JSON format")
        
        # Generate the text response
        response_text = await generate_text(prompt, max_tokens, temperature)
        
        # Extract JSON from the response
        # First, try to parse the entire response as JSON
        try:
            result = json.loads(response_text)
            logger.info("Successfully parsed JSON response")
        except json.JSONDecodeError:
            # If that fails, try to extract JSON from markdown code blocks
            logger.warning("Failed to parse entire response as JSON, trying to extract JSON from code blocks")
            json_match = re.search(r'```(?:json)?\s*({[\s\S]*?})\s*```', response_text)
            
            if json_match:
                try:
                    result = json.loads(json_match.group(1))
                    logger.info("Successfully extracted and parsed JSON from code block")
                except json.JSONDecodeError:
                    raise LLMServiceError("Failed to parse extracted JSON from code block")
            else:
                # Last resort: try to find anything that looks like a JSON object
                logger.warning("No code blocks found, trying to extract JSON object directly")
                json_match = re.search(r'{[\s\S]*?}', response_text)
                
                if json_match:
                    try:
                        result = json.loads(json_match.group(0))
                        logger.info("Successfully extracted and parsed JSON object")
                    except json.JSONDecodeError:
                        raise LLMServiceError("Failed to parse extracted JSON object")
                else:
                    raise LLMServiceError("No JSON found in the response")
        
        # Validate that the required keys are present
        required_keys = ["beginner", "intermediate", "advanced", "extracted_abstract"]
        missing_keys = [key for key in required_keys if key not in result]
        
        if missing_keys:
            logger.error(f"Missing required keys in JSON response: {missing_keys}")
            
            # If only missing extracted_abstract, add a placeholder
            if missing_keys == ["extracted_abstract"]:
                logger.warning("Adding placeholder for missing extracted_abstract")
                result["extracted_abstract"] = "Abstract extraction failed"
            else:
                raise LLMServiceError(f"Missing required keys in JSON response: {missing_keys}")
        
        logger.info("Successfully generated and parsed summaries and abstract in JSON format")
        return result
        
    except Exception as e:
        logger.error(f"Error generating summary JSON: {str(e)}")
        raise LLMServiceError(f"Error generating summary JSON: {str(e)}")

async def mock_generate_summary_json(
    prompt: str,
    max_tokens: int = 2500,
    temperature: float = 0.3
) -> Dict[str, str]:
    """
    Generate a mock JSON response containing paper summaries and extracted abstract for testing.
    
    Args:
        prompt: The prompt to generate summaries
        max_tokens: Maximum tokens to generate (ignored in mock)
        temperature: Controls randomness (ignored in mock)
        
    Returns:
        Dictionary containing the extracted abstract and generated summaries (beginner, intermediate, advanced)
    """
    # Extract the abstract from the prompt
    abstract_match = re.search(r'Paper abstract: (.*?)(?:\n\n|\Z)', prompt, re.DOTALL)
    abstract = abstract_match.group(1) if abstract_match else "Abstract not found in prompt"
    
    # Create mock summaries
    return {
        "extracted_abstract": f"This is a mock extracted abstract for testing purposes. Original abstract: {abstract[:100]}...",
        "beginner": f"This is a mock beginner summary based on: {abstract[:100]}...",
        "intermediate": f"This is a mock intermediate summary that provides more details about: {abstract[:150]}...",
        "advanced": f"This is a mock advanced summary with technical depth covering: {abstract[:200]}..."
    } 

async def mock_generate_learning_content_json(prompt: str, max_tokens: int = 2500, temperature: float = 0.3) -> Dict[str, Any]:
    """
    Mock function for generating learning content in JSON format.
    
    Args:
        prompt: The prompt to generate content from
        max_tokens: Maximum number of tokens to generate
        temperature: Temperature for generation
        
    Returns:
        Dictionary containing the generated content
    """
    logger.info(f"Mock generating learning content JSON with prompt: {prompt[:100]}...")
    
    # Return a mock response
    return {
        "title": "Mock Learning Content",
        "sections": [
            {
                "title": "Introduction",
                "content": "This is a mock introduction to the topic."
            },
            {
                "title": "Key Concepts",
                "content": "These are mock key concepts related to the topic."
            },
            {
                "title": "Examples",
                "content": "These are mock examples illustrating the concepts."
            }
        ]
    }

async def generate_structured_extraction(
    text: str,
    extraction_prompt: str,
    max_tokens: int = 1000,
    temperature: float = 0.2
) -> Dict[str, Any]:
    """
    Extract structured data from text using LLM.
    
    Args:
        text: The text to extract data from
        extraction_prompt: The prompt explaining what to extract and how to format it
        max_tokens: Maximum number of tokens to generate
        temperature: Temperature for generation (lower for more deterministic extraction)
        
    Returns:
        Dictionary containing the extracted structured data
        
    Raises:
        LLMServiceError: If there's an error with the LLM service
    """
    try:
        logger.info(f"Extracting structured data from text of length {len(text)}")
        
        # Combine the extraction prompt with the text
        full_prompt = f"{extraction_prompt}\n\n{text}"
        
        # Use OpenAI if available
        if openai_client:
            try:
                response = await openai_client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that extracts structured data from text."},
                        {"role": "user", "content": full_prompt}
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                
                # Extract the JSON from the response
                result_text = response.choices[0].message.content
                
                # Try to parse the JSON
                try:
                    # Extract JSON if it's wrapped in markdown code blocks
                    if "```json" in result_text:
                        json_text = result_text.split("```json")[1].split("```")[0].strip()
                    elif "```" in result_text:
                        json_text = result_text.split("```")[1].split("```")[0].strip()
                    else:
                        json_text = result_text
                        
                    result_json = json.loads(json_text)
                    return result_json
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse JSON from LLM response: {result_text}")
                    # Try to extract JSON using regex as a fallback
                    json_pattern = r'\{.*\}'
                    match = re.search(json_pattern, result_text, re.DOTALL)
                    if match:
                        try:
                            result_json = json.loads(match.group(0))
                            return result_json
                        except json.JSONDecodeError:
                            pass
                    
                    # If all parsing attempts fail, return a basic structure
                    return {
                        "title": "Parsing Error",
                        "authors": [],
                        "abstract": None,
                        "publication_date": None
                    }
                
            except Exception as e:
                logger.error(f"Error with OpenAI extraction: {str(e)}")
                raise LLMServiceError(f"OpenAI extraction error: {str(e)}")
                
        # Use Gemini if OpenAI is not available
        elif gemini_api_key:
            try:
                model = genai.GenerativeModel(GEMINI_MODEL)
                response = model.generate_content(full_prompt)
                
                # Extract the text from the response
                result_text = response.text
                
                # Try to parse the JSON
                try:
                    # Extract JSON if it's wrapped in markdown code blocks
                    if "```json" in result_text:
                        json_text = result_text.split("```json")[1].split("```")[0].strip()
                    elif "```" in result_text:
                        json_text = result_text.split("```")[1].split("```")[0].strip()
                    else:
                        json_text = result_text
                        
                    result_json = json.loads(json_text)
                    return result_json
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse JSON from LLM response: {result_text}")
                    # Try to extract JSON using regex as a fallback
                    json_pattern = r'\{.*\}'
                    match = re.search(json_pattern, result_text, re.DOTALL)
                    if match:
                        try:
                            result_json = json.loads(match.group(0))
                            return result_json
                        except json.JSONDecodeError:
                            pass
                    
                    # If all parsing attempts fail, return a basic structure
                    return {
                        "title": "Parsing Error",
                        "authors": [],
                        "abstract": None,
                        "publication_date": None
                    }
                
            except Exception as e:
                logger.error(f"Error with Gemini extraction: {str(e)}")
                raise LLMServiceError(f"Gemini extraction error: {str(e)}")
        
        # If no LLM service is available, use mock data
            logger.warning("No LLM service available, using mock extraction")
            return {
                "title": "Mock Paper Title",
                "authors": [{"name": "Mock Author", "affiliations": ["Mock University"]}],
                "abstract": "This is a mock abstract for testing purposes.",
                "publication_date": "2023-01-01"
            }
            
    except Exception as e:
        logger.error(f"Error in generate_structured_extraction: {str(e)}")
        # Return a basic structure in case of error
        return {
            "title": "Extraction Error",
            "authors": [],
            "abstract": None,
            "publication_date": None
        } 
    



async def generate_learning_content_json_with_pdf(
    prompt: str,
    pdf_path: str,
    max_tokens: int = 2500,
    temperature: float = 0.3
) -> Dict[str, Any]:
    """
    Generate a JSON response containing structured learning content using a Large Language Model with PDF input.
    
    Args:
        prompt: The prompt to generate learning content in JSON format
        pdf_path: Path to the PDF file
        max_tokens: Maximum tokens to generate
        temperature: Controls randomness (0.0-1.0)
        
    Returns:
        Dictionary containing:
        - methodology: Object with title and content
        - results: Object with title and content
        - key_concepts: Array of 3 objects with key_concept and explainer
        
    Raises:
        LLMServiceError: If an error occurs while generating or parsing the JSON
    """
    try:
        logger.info("Generating structured learning content with PDF in JSON format")
        
        # Check if PDF file exists
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            raise LLMServiceError(f"PDF file not found: {pdf_path}")
        
        # Use Gemini if available, otherwise fall back to OpenAI
        if gemini_api_key:
            # Call the Gemini API with the PDF
            model = genai.GenerativeModel(GEMINI_MODEL)
            
            # Read the PDF file
            with open(pdf_path, "rb") as f:
                pdf_content = f.read()
            
            # Use the file content directly in the generate_content call
            response = await asyncio.to_thread(
                model.generate_content,
                [
                    prompt,
                    {"mime_type": "application/pdf", "data": pdf_content}
                ],
                generation_config={
                    "max_output_tokens": max_tokens,
                    "temperature": temperature,
                }
            )
            
            # Extract the response text
            response_text = response.text
        elif openai_api_key and openai_client:
            # Fall back to OpenAI if Gemini is not available
            # Note: OpenAI doesn't support direct PDF input, so we'll need to extract text first
            logger.warning("Gemini API key not available, falling back to OpenAI (note: PDF content may be limited)")
            
            # Extract text from PDF
            from app.services.pdf_service import extract_text_from_pdf
            pdf_text = await extract_text_from_pdf(pdf_path)
            
            # Truncate if too long for OpenAI
            if len(pdf_text) > 10000:
                pdf_text = pdf_text[:10000] + "... [truncated]"
            
            # Create a modified prompt that includes the PDF text
            modified_prompt = f"{prompt}\n\nPDF Content:\n{pdf_text}"
            
            # Call the OpenAI API
            response = await openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": modified_prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            
            # Extract the response text
            response_text = response.choices[0].message.content
        else:
            raise LLMServiceError("Neither Gemini nor OpenAI API key is available")
        
        # Extract JSON from the response
        # First, try to parse the entire response as JSON
        try:
            result = json.loads(response_text)
            logger.info("Successfully parsed JSON response")
        except json.JSONDecodeError:
            # If that fails, try to extract JSON from markdown code blocks
            logger.warning("Failed to parse entire response as JSON, trying to extract JSON from code blocks")
            json_match = re.search(r'```(?:json)?\s*({[\s\S]*?})\s*```', response_text)
            
            if json_match:
                try:
                    result = json.loads(json_match.group(1))
                    logger.info("Successfully extracted and parsed JSON from code block")
                except json.JSONDecodeError:
                    raise LLMServiceError("Failed to parse extracted JSON from code block")
            else:
                # Last resort: try to find anything that looks like a JSON object
                logger.warning("No code blocks found, trying to extract JSON object directly")
                json_match = re.search(r'{[\s\S]*?}', response_text)
                
                if json_match:
                    try:
                        result = json.loads(json_match.group(0))
                        logger.info("Successfully extracted and parsed JSON object")
                    except json.JSONDecodeError:
                        raise LLMServiceError("Failed to parse extracted JSON object")
                else:
                    raise LLMServiceError("No JSON found in the response")
        
        # Validate that the required keys are present
        required_keys = ["methodology", "results", "key_concepts"]
        missing_keys = [key for key in required_keys if key not in result]
        
        if missing_keys:
            logger.error(f"Missing required keys in JSON response: {missing_keys}")
            raise LLMServiceError(f"Missing required keys in JSON response: {missing_keys}")
        
        # Validate structure of the response
        if not isinstance(result["methodology"], dict) or "title" not in result["methodology"] or "content" not in result["methodology"]:
            raise LLMServiceError("Invalid structure for methodology in JSON response")
            
        if not isinstance(result["results"], dict) or "title" not in result["results"] or "content" not in result["results"]:
            raise LLMServiceError("Invalid structure for results in JSON response")
            
        if not isinstance(result["key_concepts"], list) or len(result["key_concepts"]) != 3:
            raise LLMServiceError("key_concepts must be an array of exactly 3 items")
            
        for concept in result["key_concepts"]:
            if not isinstance(concept, dict) or "key_concept" not in concept or "explainer" not in concept:
                raise LLMServiceError("Each key_concept item must have key_concept and explainer fields")
        
        logger.info("Successfully generated and parsed structured learning content from PDF in JSON format")
        return result
        
    except Exception as e:
        logger.error(f"Error generating learning content JSON with PDF: {str(e)}")
        raise LLMServiceError(f"Error generating learning content JSON with PDF: {str(e)}") 