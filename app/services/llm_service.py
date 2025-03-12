from typing import List, Dict, Any, Optional
import asyncio
from uuid import UUID
from openai import OpenAI, AsyncOpenAI
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from app.core.logger import get_logger
from app.core.config import OPENAI_API_KEY, OPENAI_MODEL, APP_ENV
from app.core.exceptions import LLMServiceError

logger = get_logger(__name__)

# Get API key directly from environment for consistency
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    api_key = OPENAI_API_KEY
    # Ensure it's also in the environment
    os.environ["OPENAI_API_KEY"] = api_key

# Initialize the OpenAI client
client = AsyncOpenAI(api_key=api_key)
logger.info(f"OpenAI client initialized with API key: {api_key[:8]}... in llm_service.py")

async def generate_response(
    query: str,
    context_chunks: List[Dict[str, Any]],
    paper_title: Optional[str] = None,
    max_tokens: int = 1000
) -> Dict[str, Any]:
    """
    Generate a response to a query using the OpenAI API.
    
    Args:
        query: The user's query
        context_chunks: List of text chunks with metadata to use as context
        paper_title: Optional title of the paper for context
        max_tokens: Maximum number of tokens in the response
        
    Returns:
        Dictionary containing the generated response and metadata
        
    Raises:
        LLMServiceError: If there's an error generating a response
    """
    try:
        logger.info(f"Generating response for query: {query[:50]}...")
        
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
        
        # Construct the prompt
        paper_context = f" about the paper '{paper_title}'" if paper_title else ""
        
        prompt = f"""You are an AI research assistant. Answer the following question{paper_context} 
using ONLY the information from the provided context chunks.

If the question cannot be answered using the context, say "I cannot answer this question based on the 
available information from the paper." and suggest what further information might be needed.

Question: {query}

Context:
{context_text}

Answer the question in a clear, concise manner. If appropriate, you may format your response using Markdown.
If there are relevant parts of the context that directly support your answer, you may quote them by
including the chunk number in square brackets, e.g., [1].
"""

        # Call the OpenAI API to generate a response
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "system", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.3,  # Lower temperature for more deterministic responses
        )
        
        # Extract the response text
        response_text = response.choices[0].message.content.strip()
        
        # Return the response with metadata
        result = {
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
        
        logger.info("Response generated successfully")
        return result
        
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}")
        raise LLMServiceError(f"Error generating response: {str(e)}")


async def mock_generate_response(
    query: str,
    context_chunks: List[Dict[str, Any]],
    paper_title: Optional[str] = None,
    max_tokens: int = 1000
) -> Dict[str, Any]:
    """
    Mock version of generate_response for testing without calling the OpenAI API.
    
    Args:
        query: The user's query
        context_chunks: List of text chunks with metadata to use as context
        paper_title: Optional title of the paper for context
        max_tokens: Maximum number of tokens in the response
        
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
    try:
        # Use mock for testing environments
        if APP_ENV == "testing":
            return await mock_generate_text(prompt, max_tokens, temperature)
            
        logger.info(f"Generating text for prompt: {prompt[:50]}...")
        
        # Use the global client instance instead of creating a new one
        global client
        if client is None:
            # Reinitialize if needed
            client = AsyncOpenAI(api_key=api_key)
            logger.info(f"Reinitialized OpenAI client with API key prefix: {api_key[:8]}...")
        
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        generated_text = response.choices[0].message.content
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