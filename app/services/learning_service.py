from typing import Dict, List, Optional, Any
import logging
import uuid
import random
from datetime import datetime
import asyncio
import httpx
import json
import os
from app.database.supabase_client import supabase, get_paper_by_id
from app.core.config import get_settings
from app.services.paper_service import get_related_papers
from app.api.v1.models import (
    LearningItem, 
    LearningItemType, 
    LearningPath, 
    UserProgressRecord,
    QuizAnswer,
    AnswerResult,
    CardItem,
    QuestionItem
)
from app.services.llm_service import generate_text, generate_learning_content_json_with_pdf, mock_generate_learning_content_json
from app.services.pdf_service import get_paper_pdf
from app.templates.prompts.learning_content import get_learning_content_prompt

logger = logging.getLogger(__name__)
settings = get_settings()

# Learning material types
MATERIAL_TYPES = {
    "concepts": "Key concepts from the paper",
    "methodology": "Methodology explanation",
    "results": "Results and findings",
    "quiz": "Interactive questions to test understanding",
    "flashcard": "Spaced repetition memory cards",
    "video": "Educational video content"
}

# Difficulty levels
LEVELS = ["beginner", "intermediate", "advanced"]

# Categories mapping (simplified version - can be expanded based on arXiv categories)
CATEGORY_MAPPING = {
    "cs.AI": "artificial-intelligence",
    "cs.CL": "natural-language-processing",
    "cs.CV": "computer-vision",
    "cs.LG": "machine-learning",
    "stat.ML": "machine-learning",
    "math": "mathematics",
    "physics": "physics",
    "q-bio": "biology",
    "q-fin": "finance"
}

# Cache to avoid regenerating content for the same paper
learning_path_cache: Dict[str, LearningPath] = {}

async def generate_youtube_search_query(paper_id: str) -> str:
    """
    Generate a YouTube search query using LLM based on paper content.
    
    Args:
        paper_id: The ID of the paper
        
    Returns:
        str: A search query optimized for finding relevant educational videos
    """
    try:
        # Get paper details
        paper = await get_paper_by_id(paper_id)
        if not paper:
            logger.warning(f"Paper with ID {paper_id} not found, using fallback query")
            return "machine learning paper explanation"
        
        # Extract relevant information from the paper
        title = paper.get("title", "")
        abstract = paper.get("abstract", "")
        authors = paper.get("authors", [])
        author_names = ", ".join([author.get("name", "") for author in authors[:2]]) if authors else ""
        
        # Create a prompt for the LLM
        prompt = f"""
        I need to find educational YouTube videos about an academic paper.
        
        Paper Title: {title}
        Authors: {author_names}
        Abstract: {abstract}
        
        Generate a concise, specific search query (under 10 words) that I should use on YouTube to find
        educational videos that would help someone understand this paper's topic and concepts.
        Focus on the most important technical terminology and concepts.
        
        The query should:
        1. Include the most important technical terms from the paper
        2. Be specific enough to find relevant videos (not too generic)
        3. Focus on educational content (tutorials, explanations, lectures)
        4. Be suitable for YouTube's search algorithm
        
        Return ONLY the search query text with no quotes, prefixes, or explanations.
        """
        
        # Generate the search query using LLM
        search_query = await generate_text(prompt, max_tokens=100, temperature=0.3)
        
        # Clean up the query (remove quotes, newlines, etc.)
        search_query = search_query.strip().replace('"', '').replace("'", "")
        
        # Fallback in case the LLM returns an empty string or something too long
        if not search_query or len(search_query.split()) > 15:
            logger.warning(f"LLM returned invalid search query: '{search_query}', using title instead")
            return f"{title} explanation tutorial"
        
        logger.info(f"LLM generated YouTube search query: '{search_query}'")
        return search_query
        
    except Exception as e:
        logger.error(f"Error generating YouTube search query with LLM: {str(e)}", exc_info=True)
        # Return a fallback query based on the paper ID as a last resort
        return f"paper explanation tutorial"

async def fetch_youtube_videos(paper_id: str) -> List[Dict[str, Any]]:
    """
    Fetch educational YouTube videos related to the paper topic.
    
    Args:
        paper_id: The ID of the paper
        
    Returns:
        List[Dict[str, Any]]: A list of YouTube video metadata
    """
    try:
        if not settings.YOUTUBE_API_KEY:
            logger.warning("YouTube API key not configured, using mock data")
            return _get_mock_youtube_videos()
        
        # Get paper details to create a relevant search query
        paper = await get_paper_by_id(paper_id)
        if not paper:
            logger.warning(f"Paper with ID {paper_id} not found, using mock data")
            return _get_mock_youtube_videos()
        
        # Extract relevant information from the paper
        title = paper.get("title", "")
        
        # First, try to generate a search query using the LLM
        try:
            search_term = await generate_youtube_search_query(paper_id)
            logger.info(f"Using LLM-generated search term: '{search_term}'")
        except Exception as e:
            logger.warning(f"Failed to generate search query with LLM: {str(e)}, falling back to keyword extraction")
            # Fall back to keyword extraction if LLM generation fails
            # The existing keyword extraction code remains as a fallback
            
            # (Keep the existing keyword extraction code as is)
            abstract = paper.get("abstract", "")
            keywords = []
            
            # Common words to exclude from keyword extraction
            common_words = {"the", "and", "for", "with", "using", "based", "from", "this", "that", 
                           "our", "we", "in", "on", "to", "of", "is", "are", "a", "an", "by", "as"}
            
            # Add main terms from the title
            if title:
                # Extract main terms (words longer than 3 letters, excluding common words)
                title_terms = [word.strip('.,():;"\'').lower() for word in title.split() 
                             if len(word) > 3 and word.lower().strip('.,():;"\'') not in common_words]
                keywords.extend(title_terms[:3])  # Add up to 3 terms from title
            
            # Extract key terms from the abstract
            if abstract:
                # First, look for any technical terms that might be in quotes
                import re
                quoted_terms = re.findall(r'"([^"]*)"', abstract)
                if quoted_terms:
                    keywords.extend([term for term in quoted_terms if len(term.split()) <= 3][:2])
                
                # Then extract individual important words
                abstract_words = abstract.split()
                # Look for capitalized words which might be important terms
                capitalized_terms = [word.strip('.,():;"\'') for word in abstract_words 
                                   if word[0].isupper() and len(word) > 3 
                                   and word.lower().strip('.,():;"\'') not in common_words]
                
                # Add up to 2 capitalized terms if found
                if capitalized_terms:
                    keywords.extend(capitalized_terms[:2])
                
                # If we still need more keywords, get the longest words which might be technical terms
                if len(keywords) < 5:
                    abstract_terms = [word.strip('.,():;"\'').lower() for word in abstract_words 
                                     if len(word) > 6 and word.lower().strip('.,():;"\'') not in common_words]
                    # Sort by length (longer words often more specific/technical)
                    abstract_terms.sort(key=len, reverse=True)
                    # Add up to 2 more terms, avoiding duplicates
                    added = 0
                    for term in abstract_terms:
                        if term not in [k.lower() for k in keywords]:
                            keywords.append(term)
                            added += 1
                            if added >= 2 or len(keywords) >= 5:
                                break
            
            # Create search query combining keywords
            if keywords:
                # Ensure we don't have duplicates
                unique_keywords = []
                for k in keywords:
                    if k.lower() not in [uk.lower() for uk in unique_keywords]:
                        unique_keywords.append(k)
                
                # Limit to 5 keywords to avoid too-specific searches
                final_keywords = unique_keywords[:5]
                search_term = f"{' '.join(final_keywords)} explanation tutorial"
                logger.info(f"Generated YouTube search term from paper keywords: '{search_term}'")
            else:
                # Fallback to at least the title if no keywords extracted
                search_term = f"{title[:30]} explanation" if title else "machine learning paper explanation"
                logger.info(f"Using fallback YouTube search term: '{search_term}'")
            
        # Rest of the function remains the same
        # Construct YouTube API request
        api_url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "q": search_term,
            "type": "video",
            "maxResults": 5,
            "key": settings.YOUTUBE_API_KEY,
            "videoEmbeddable": "true",
            "relevanceLanguage": "en",
            "safeSearch": "strict"
        }
        
        # Make the API request
        async with httpx.AsyncClient() as client:
            response = await client.get(api_url, params=params)
            response.raise_for_status()
            data = response.json()
        
        # Extract video IDs to get more details
        video_ids = [item["id"]["videoId"] for item in data.get("items", [])]
        
        if not video_ids:
            logger.warning(f"No YouTube videos found for search term '{search_term}', using mock data")
            return _get_mock_youtube_videos()
        
        logger.info(f"Found {len(video_ids)} YouTube videos for paper '{title}'")
        
        # Get video details
        video_url = "https://www.googleapis.com/youtube/v3/videos"
        video_params = {
            "part": "snippet,contentDetails",
            "id": ",".join(video_ids),
            "key": settings.YOUTUBE_API_KEY
        }
        
        async with httpx.AsyncClient() as client:
            video_response = await client.get(video_url, params=video_params)
            video_response.raise_for_status()
            video_data = video_response.json()
        
        # Process video data
        videos = []
        for item in video_data.get("items", []):
            snippet = item.get("snippet", {})
            content_details = item.get("contentDetails", {})
            
            videos.append({
                "video_id": item.get("id"),
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                "channel": snippet.get("channelTitle", ""),
                "duration": content_details.get("duration", "PT0M0S")  # ISO 8601 duration format
            })
        
        # Log the first video to verify relevance
        if videos:
            logger.info(f"First video found: '{videos[0].get('title')}' from channel '{videos[0].get('channel')}'")
        
        return videos
    
    except Exception as e:
        logger.error(f"Error fetching YouTube videos for paper {paper_id}: {str(e)}")
        return _get_mock_youtube_videos()

def _convert_iso_duration(duration_iso: str) -> str:
    """Convert ISO 8601 duration to minutes:seconds format."""
    import re
    
    # Extract minutes and seconds from ISO 8601 duration
    minutes_match = re.search(r'(\d+)M', duration_iso)
    seconds_match = re.search(r'(\d+)S', duration_iso)
    hours_match = re.search(r'(\d+)H', duration_iso)
    
    minutes = int(minutes_match.group(1)) if minutes_match else 0
    seconds = int(seconds_match.group(1)) if seconds_match else 0
    hours = int(hours_match.group(1)) if hours_match else 0
    
    # Add hours to minutes if present
    if hours > 0:
        minutes += hours * 60
        
    return f"{minutes}:{seconds:02d}"

def _get_mock_youtube_videos() -> List[Dict[str, Any]]:
    """Return mock YouTube video data"""
    return [
        {
            "video_id": "PL8dPuuaLjXtO65LeD2p4_Sb5XQ51par_b",
            "title": "Introduction to Machine Learning",
            "description": "A comprehensive introduction to the basic concepts of machine learning",
            "thumbnail": "https://i.ytimg.com/vi/example1/hqdefault.jpg",
            "channel": "Educational Channel 1",
            "duration": "PT15M30S"
        },
        {
            "video_id": "PL8dPuuaLjXtO65LeD2p4_Sb5XQ51par_c",
            "title": "Neural Networks Explained",
            "description": "How neural networks work and their applications in machine learning",
            "thumbnail": "https://i.ytimg.com/vi/example2/hqdefault.jpg",
            "channel": "Educational Channel 2",
            "duration": "PT12M45S"
        },
        {
            "video_id": "PL8dPuuaLjXtO65LeD2p4_Sb5XQ51par_d",
            "title": "Deep Learning Fundamentals",
            "description": "Understanding the basics of deep learning architectures",
            "thumbnail": "https://i.ytimg.com/vi/example3/hqdefault.jpg",
            "channel": "Educational Channel 3",
            "duration": "PT18M20S"
        }
    ]

def _get_mock_flashcards() -> List[CardItem]:
    """
    Return mock flashcard data following the CardItem interface.
    
    Returns:
        List[CardItem]: A list of flashcards with 'front' and 'back' fields
    """
    return [
        CardItem(
            front="What is supervised learning?",
            back="A type of machine learning where the model is trained on labeled data, learning to map inputs to known outputs."
        ),
        CardItem(
            front="What is the difference between classification and regression?",
            back="Classification predicts discrete class labels, while regression predicts continuous values."
        ),
        CardItem(
            front="What is overfitting?",
            back="When a model learns the training data too well, including its noise and outliers, leading to poor performance on new, unseen data."
        ),
        CardItem(
            front="What is a neural network?",
            back="A computational model inspired by the human brain, consisting of connected nodes (neurons) organized in layers that process information."
        ),
        CardItem(
            front="What is backpropagation?",
            back="An algorithm used to train neural networks by calculating gradients and adjusting weights to minimize the difference between actual and predicted outputs."
        )
    ]

async def generate_flashcards(paper_id: str) -> List[CardItem]:
    """
    Generate flashcards for the paper using OpenAI API.
    
    Args:
        paper_id: The ID of the paper
        
    Returns:
        List[CardItem]: A list of flashcards with standardized format
    """
    logger.info(f"Starting flashcard generation for paper ID: {paper_id}")
    
    try:
        if not settings.OPENAI_API_KEY:
            logger.warning("OpenAI API key not configured, using mock flashcards")
            return _get_mock_flashcards()
        
        # Get the paper content for context
        paper = await get_paper_by_id(paper_id)
        logger.debug(f"Paper retrieval result: {paper is not None}")
        if not paper:
            logger.warning(f"Paper {paper_id} not found, using mock flashcards")
            return _get_mock_flashcards()
            
        # Extract paper details for the prompt
        paper_title = paper.get("title", "")
        paper_abstract = paper.get("abstract", "")
        logger.debug(f"Paper title: {paper_title[:50]}...")
        logger.debug(f"Paper abstract length: {len(paper_abstract)} characters")
        
        # Create a prompt that includes paper-specific information
        prompt = f"""
        Generate 5 flashcards for the paper titled "{paper_title}".
        
        Here is the paper's abstract to help you create relevant flashcards:
        {paper_abstract}
        
        For each flashcard, provide:
        - front: The question or concept on the front of the card
        - back: The explanation or answer on the back of the card
        
        Make sure the flashcards are directly relevant to this specific paper's content, not generic concepts.
        
        Example:
        [
            {{
                "front": "What is the main contribution of this paper?",
                "back": "Answer specific to this paper's contribution."
            }}
        ]
        
        IMPORTANT: Return ONLY valid JSON. Do not include any special characters or escape sequences that would make the JSON invalid. If you need to include quotes within text, use single quotes inside the JSON strings.
        """
        
        # Set up the HTTP client with explicit timeouts
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=30.0)) as client:
            api_url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json"
            }
            data = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant that generates flashcards for learning."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 1000
            }
            
            response = await client.post(api_url, json=data, headers=headers)
            response.raise_for_status()
            
            logger.info(f"OpenAI API response status: {response.status_code}")
            
            # Extract the content from the response
            response_data = response.json()
            content = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
            logger.debug(f"OpenAI API response content length: {len(content)} characters")
            logger.debug(f"Response content preview: {content[:200]}...")
            
            # Process the response content
            try:
                # Find JSON array in the response
                import re
                json_match = re.search(r'\[\s*\{.*\}\s*\]', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
                
                # Try to parse the JSON
                try:
                    flashcards_data = json.loads(content)
                except json.JSONDecodeError as e:
                    # If normal parsing fails, try to handle escaped characters
                    logger.warning(f"Standard JSON parsing failed: {str(e)}")
                    # Replace invalid escape sequences
                    sanitized_content = re.sub(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', content)
                    try:
                        flashcards_data = json.loads(sanitized_content)
                        logger.info("Successfully parsed JSON after sanitizing escape characters")
                    except json.JSONDecodeError:
                        # If that fails too, try a more aggressive approach - replace all backslashes
                        logger.warning("Sanitized JSON parsing failed, trying more aggressive approach")
                        sanitized_content = content.replace('\\', '\\\\')
                        # But preserve valid escape sequences
                        for seq in ['\\"', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']:
                            sanitized_content = sanitized_content.replace('\\\\' + seq[1], seq)
                        try:
                            flashcards_data = json.loads(sanitized_content)
                            logger.info("Successfully parsed JSON with aggressive sanitizing")
                        except json.JSONDecodeError as e:
                            logger.error(f"All JSON parsing attempts failed: {str(e)}")
                
                # Validate and convert to CardItem objects
                flashcards = []
                for card_data in flashcards_data:
                    if "front" in card_data and "back" in card_data:
                        card = CardItem(
                            front=card_data["front"],
                            back=card_data["back"]
                        )
                        flashcards.append(card)
                
                if flashcards:
                    logger.info(f"Successfully generated {len(flashcards)} flashcards")
                return flashcards
                
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON response: {str(e)}")
        
    except Exception as e:
        logger.error(f"Error generating flashcards: {str(e)}", exc_info=True)
        return _get_mock_flashcards()

async def generate_quiz_questions(paper_id: str) -> List[QuestionItem]:
    """
    Generate quiz questions for the paper using OpenAI API.
    
    Args:
        paper_id: The ID of the paper
        
    Returns:
        List[QuestionItem]: A list of quiz questions with standardized format
    """
    logger.info(f"Starting quiz question generation for paper ID: {paper_id}")
    
    try:
        if not settings.OPENAI_API_KEY:
            logger.warning("OpenAI API key not configured, using mock quiz questions")
            return _get_mock_quiz_questions()
        
        # Get the paper content for context
        paper = await get_paper_by_id(paper_id)
        if not paper:
            logger.warning(f"Paper {paper_id} not found, using mock quiz questions")
            return _get_mock_quiz_questions()
            
        # Extract paper details for the prompt
        paper_title = paper.get("title", "")
        paper_abstract = paper.get("abstract", "")
        
        # Create a prompt that includes paper-specific information
        prompt = f"""
        Generate 5 multiple-choice quiz questions about the paper titled "{paper_title}".
        Each question should have 4 options with one correct answer.
        
        Here is the paper's abstract to help you create relevant questions:
        {paper_abstract}
        
        Format your response as a JSON array of objects with these fields:
        - question: The question text
        - options: An array of possible answers (4 options)
        - correct_answer: The index of the correct answer (0-3 as a number, not a string)
        - explanation: A brief explanation of why the answer is correct
        
        Make sure the questions are directly relevant to this specific paper's content, not generic concepts.
        
        Example:
        [
            {{
                "question": "What is the main methodology proposed in this paper?",
                "options": [
                    "Option specific to this paper",
                    "Another option specific to this paper",
                    "A third option specific to this paper",
                    "A fourth option specific to this paper"
                ],
                "correct_answer": 1,
                "explanation": "Explanation specific to this paper's methodology."
            }}
        ]
        
        IMPORTANT: Return ONLY valid JSON. Do not include any special characters or escape sequences that would make the JSON invalid. If you need to include quotes within text, use single quotes inside the JSON strings.
        """
        
        try:
            # Set up the HTTP client with explicit timeouts
            async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=30.0)) as client:
                api_url = "https://api.openai.com/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                }
                data = {
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant that generates quiz questions for learning."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 1500
                }
                
                response = await client.post(api_url, json=data, headers=headers)
                response.raise_for_status()
                
                logger.info(f"OpenAI API response status: {response.status_code}")
                
                # Extract the content from the response
                response_data = response.json()
                content = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                logger.debug(f"OpenAI API response content length: {len(content)} characters")
                logger.debug(f"Response content preview: {content[:200]}...")
                
                try:
                    # Find JSON array in the response
                    import re
                    json_match = re.search(r'\[\s*\{.*\}\s*\]', content, re.DOTALL)
                    if json_match:
                        content = json_match.group(0)
                    
                    # Try to parse the JSON
                    try:
                        questions_data = json.loads(content)
                    except json.JSONDecodeError as e:
                        # If normal parsing fails, try to handle escaped characters
                        logger.warning(f"Standard JSON parsing failed: {str(e)}")
                        # Replace invalid escape sequences
                        sanitized_content = re.sub(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', content)
                        try:
                            questions_data = json.loads(sanitized_content)
                            logger.info("Successfully parsed JSON after sanitizing escape characters")
                        except json.JSONDecodeError:
                            # If that fails too, try a more aggressive approach - replace all backslashes
                            logger.warning("Sanitized JSON parsing failed, trying more aggressive approach")
                            sanitized_content = content.replace('\\', '\\\\')
                            # But preserve valid escape sequences
                            for seq in ['\\"', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']:
                                sanitized_content = sanitized_content.replace('\\\\' + seq[1], seq)
                            try:
                                questions_data = json.loads(sanitized_content)
                                logger.info("Successfully parsed JSON with aggressive sanitizing")
                            except json.JSONDecodeError as e:
                                logger.error(f"All JSON parsing attempts failed: {str(e)}")
                    
                    # Validate and convert to QuestionItem objects
                    questions = []
                    for question_data in questions_data:
                        if all(key in question_data for key in ["question", "options", "correct_answer"]):
                            # Ensure correct_answer is an integer
                            if isinstance(question_data["correct_answer"], str):
                                try:
                                    question_data["correct_answer"] = int(question_data["correct_answer"])
                                except ValueError:
                                    logger.warning(f"Invalid correct_answer format: {question_data['correct_answer']}")
                                    continue
                                
                            question = QuestionItem(
                                question=question_data["question"],
                                options=question_data["options"],
                                correct_answer=question_data["correct_answer"],
                                explanation=question_data.get("explanation", "")
                            )
                            questions.append(question)
                    
                    if questions:
                        logger.info(f"Successfully generated {len(questions)} quiz questions")
                        return questions
                    else:
                        logger.warning("No valid quiz questions found in the response")
                        return _get_mock_quiz_questions()
                
                except Exception as e:
                    logger.error(f"Error parsing JSON response: {str(e)}")
                    return _get_mock_quiz_questions()
        
        except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
            logger.error(f"API request failed: {str(e)}")
            return _get_mock_quiz_questions()
    
    except Exception as e:
        logger.error(f"Error generating quiz questions: {str(e)}", exc_info=True)
        return _get_mock_quiz_questions()

def _get_mock_quiz_questions() -> List[QuestionItem]:
    """
    Return mock quiz question data following the QuestionItem interface.
    
    Returns:
        List[QuestionItem]: A list of quiz questions with 'question', 'options', 
        'correct_answer' (as number), and 'explanation' fields
    """
    return [
        QuestionItem(
            question="Which of the following is NOT a type of machine learning?",
            options=[
                "Supervised learning",
                "Unsupervised learning",
                "Reinforcement learning",
                "Prospective learning"
            ],
            correct_answer=3,
            explanation="The three main types of machine learning are supervised learning, unsupervised learning, and reinforcement learning. 'Prospective learning' is not a standard type of machine learning."
        ),
        QuestionItem(
            question="What is the purpose of the activation function in a neural network?",
            options=[
                "To initialize the weights",
                "To add non-linearity to the model",
                "To normalize the input data",
                "To reduce computational complexity"
            ],
            correct_answer=1,
            explanation="Activation functions add non-linearity to neural networks, allowing them to learn complex patterns that couldn't be modeled with just linear combinations."
        ),
        QuestionItem(
            question="Which algorithm is commonly used for dimensional reduction?",
            options=[
                "Random Forest",
                "Gradient Boosting",
                "Principal Component Analysis (PCA)",
                "K-Nearest Neighbors (KNN)"
            ],
            correct_answer=2,
            explanation="PCA is a widely used technique for dimensionality reduction that transforms high-dimensional data into a lower-dimensional space while preserving as much variance as possible."
        ),
        QuestionItem(
            question="What does the term 'epoch' refer to in machine learning?",
            options=[
                "A hyperparameter that controls model complexity",
                "The time it takes to train a model",
                "A complete pass through the entire training dataset",
                "The error rate of a model"
            ],
            correct_answer=2,
            explanation="An epoch in machine learning refers to one complete pass through the entire training dataset during the training process."
        ),
        QuestionItem(
            question="Which of the following is a common loss function for binary classification?",
            options=[
                "Mean Squared Error",
                "Binary Cross-Entropy",
                "Hinge Loss",
                "All of the above"
            ],
            correct_answer=1,
            explanation="Binary Cross-Entropy (also called Log Loss) is commonly used for binary classification problems as it measures the performance of a model whose output is a probability value between 0 and 1."
        )
    ]

async def store_learning_material(material_data: Dict[str, Any], use_mock_for_tests: bool = False) -> str:
    """
    Store a learning material in the database.
    
    Args:
        material_data: Dictionary containing learning material data
        use_mock_for_tests: Set to True in test environments to bypass database operations
        
    Returns:
        str: The ID of the newly created material
    """
    logger.info(f"Storing learning material of type {material_data.get('type')} for paper {material_data.get('paper_id')}")
    
    # Generate a UUID for the material
    material_id = str(uuid.uuid4())
    
    # In test mode, just return the ID without database operations
    if use_mock_for_tests:
        logger.info(f"Test mode: Bypassing database storage for material {material_id}")
        return material_id
    
    try:
        # Use our ItemCreate model for validation
        item_data = {
            "id": material_id,
            "paper_id": material_data.get("paper_id"),
            "type": material_data.get("type"),
            "level": material_data.get("level", "beginner"),
            "category": material_data.get("category", "general"),
            "data": material_data.get("data", {}),
            "order": material_data.get("order", 0),
            "videos": material_data.get("videos")
        }
        
        # Insert the item into the database
        result = supabase.table("items").insert(item_data).execute()
        logger.debug(f"Stored learning material with ID {material_id}")
        
        # If this is a quiz material, also store the questions
        if material_data.get("type") == "quiz" and "questions" in material_data.get("data", {}):
            for question in material_data["data"]["questions"]:
                # Create a question_data dictionary with proper fields
                question_data = {
                    "id": str(uuid.uuid4()),
                    "item_id": material_id,
                    "type": "multiple_choice",  # Default type
                    "text": question.get("question", question.get("text", "")),
                    # Use options key if available, or choices key if not
                    "choices": question.get("options", question.get("choices", [])),
                    # Ensure correct_answer is a string
                    "correct_answer": str(question.get("correct_answer", ""))
                }
                
                # Insert the question into the database
                supabase.table("questions").insert(question_data).execute()
                logger.debug(f"Stored question for item {material_id}")
        
        return material_id
    except Exception as e:
        logger.error(f"Error storing learning material: {str(e)}", exc_info=True)
        raise

async def get_materials_for_paper(paper_id: str, level: Optional[str] = None, use_mock_for_tests: bool = False) -> List[Dict[str, Any]]:
    """
    Retrieve learning materials for a specific paper.
    Optionally filter by difficulty level.
    
    Args:
        paper_id: The ID of the paper
        level: Optional difficulty level to filter by
        use_mock_for_tests: Set to True in test environments to return empty list instead of querying database
        
    Returns:
        List[Dict[str, Any]]: A list of learning materials
    """
    logger.info(f"Retrieving learning materials for paper {paper_id}, level: {level}")
    
    # In test mode, just return an empty list to indicate no existing materials
    if use_mock_for_tests:
        logger.info(f"Test mode: Returning empty materials list for {paper_id}")
        return []
    
    try:
        query = supabase.table("items").select("*").eq("paper_id", paper_id).order("order", desc=False)
        
        if level:
            query = query.eq("level", level)
            
        result = query.execute()
        
        if not result.data:
            logger.warning(f"No learning materials found for paper {paper_id}")
            return []
            
        # Log the first material to see its structure
        if result.data and len(result.data) > 0:
            logger.debug(f"Sample material from database: {result.data[0]}")
            
            # If there are flashcard materials, log one for debugging
            flashcard_materials = [m for m in result.data if m.get("type") == "flashcard"]
            if flashcard_materials:
                logger.debug(f"Sample flashcard material: {flashcard_materials[0]}")
                if "data" in flashcard_materials[0] and "cards" in flashcard_materials[0]["data"]:
                    cards = flashcard_materials[0]["data"]["cards"]
                    logger.debug(f"First flashcard from material: {cards[0] if cards else 'No cards found'}")
            
            # If there are video materials, log one for debugging
            video_materials = [m for m in result.data if m.get("type") == "video"]
            if video_materials:
                logger.info(f"Found {len(video_materials)} video materials")
                for i, vm in enumerate(video_materials):
                    logger.info(f"Video material {i+1}:")
                    logger.info(f"  ID: {vm.get('id')}")
                    logger.info(f"  Level: {vm.get('level')}")
                    
                    # Check for videos in data
                    if "data" in vm and isinstance(vm["data"], dict):
                        logger.info(f"  Data keys: {vm['data'].keys()}")
                        if "videos" in vm["data"]:
                            logger.info(f"  Videos in data: {len(vm['data']['videos'])}")
                    
                    # Check for videos at top level
                    if "videos" in vm:
                        logger.info(f"  Videos at top level: {len(vm['videos'])}")
            
        return result.data
        
    except Exception as e:
        logger.error(f"Error retrieving learning materials: {str(e)}")
        raise

async def generate_learning_path(paper_id: str, user_id: Optional[str] = None, use_mock_for_tests: bool = False) -> LearningPath:
    """
    Generate a learning path for a paper.
    
    Args:
        paper_id: The ID of the paper
        user_id: Optional user ID for personalized learning path
        use_mock_for_tests: Set to True in test environments to bypass paper existence check
        
    Returns:
        LearningPath: A structured learning path with materials for the paper
        
    Raises:
        ValueError: If paper not found or content generation fails
    """
    logger.info(f"Generating learning path for paper {paper_id}")
    
    # First, check if we already have materials stored for this paper
    existing_materials = await get_materials_for_paper(paper_id, use_mock_for_tests=use_mock_for_tests)
    
    # Initialize variables for tracking items
    stored_item_ids = []
    order_counter = 1
    learning_items = []
    
    logger.info(f"Initialized stored_item_ids for new materials generation for paper {paper_id}")
    
    if existing_materials and paper_id in learning_path_cache:
        logger.info(f"Using cached learning path for paper {paper_id}")
        stored_item_ids = [item["id"] for item in existing_materials if "id" in item]
        logger.info(f"Populated stored_item_ids with {len(stored_item_ids)} existing item IDs")
        learning_path = learning_path_cache[paper_id]
        
        # Initialize learning_items from the cached learning path
        learning_items = learning_path.items
        
        # Update the paper in the database to indicate materials exist
        if not use_mock_for_tests:
            try:
                # Update tags to include learning materials info
                update_data = {
                    "tags": {
                        "has_learning_materials": True,
                        "learning_materials_count": len(stored_item_ids)
                    }
                }
                
                logger.info(f"Updating paper {paper_id} with learning_materials_count={len(stored_item_ids)}")
                # Update the paper in the database
                supabase.table("papers").update(update_data).eq("id", paper_id).execute()
                logger.info(f"Updated paper {paper_id} with learning materials count {len(stored_item_ids)}")
            except Exception as e:
                logger.error(f"Error updating paper with learning materials status: {str(e)}", exc_info=True)
        
        return learning_path
    else:
        logger.info(f"Generating new learning materials for paper {paper_id}")
        
        # Get the paper details - Skip this check if we're in test mode
        paper = None
        if not use_mock_for_tests:
            paper = await get_paper_by_id(paper_id)
            if not paper:
                logger.error(f"Paper {paper_id} not found")
                raise ValueError(f"Paper {paper_id} not found")
        else:
            logger.info(f"Test mode: Bypassing paper existence check for {paper_id}")
            # Create a mock paper object for test mode
            paper = {
                "id": paper_id,
                "title": "Test Paper",
                "abstract": "This is a test paper for unit testing.",
                "authors": [{"name": "Test Author"}],
                "publication_date": datetime.now().isoformat()
            }
        
        # If we have existing materials, use them; otherwise, generate new ones
        if existing_materials:
            logger.info(f"Using {len(existing_materials)} existing materials for paper {paper_id}")
            
            # Convert existing materials to learning_items if they're not already from a cached path
            if paper_id not in learning_path_cache:
                logger.info(f"Converting {len(existing_materials)} existing materials to learning items")
                for material in existing_materials:
                    # Convert database material to LearningItem
                    learning_item = LearningItem(
                        id=material.get("id"),
                        paper_id=material.get("paper_id"),
                        type=LearningItemType(material.get("type", "concepts")),
                        title=material.get("data", {}).get("title", "Learning Item"),
                        content=material.get("data", {}).get("description", material.get("data", {}).get("content", "")),
                        metadata=material.get("data", {}).get("metadata", {}),
                        difficulty_level=get_difficulty_level(material.get("level", "beginner"))
                    )
                    
                    # Add specific metadata based on item type
                    if material.get("type") == "flashcard" and "cards" in material.get("data", {}):
                        # Convert each flashcard to a separate learning item
                        cards = material.get("data", {}).get("cards", [])
                        logger.info(f"Converting {len(cards)} flashcards to learning items for {material.get('id')}")
                        logger.debug(f"Flashcard material structure: {material}")
                        
                        # Check for empty or invalid cards
                        if not cards or not isinstance(cards, list):
                            logger.warning(f"Invalid cards data for material {material.get('id')}: {cards}")
                            # Try to look for cards in a different location
                            if "cards" in material:
                                cards = material.get("cards", [])
                                logger.info(f"Found {len(cards)} cards at top level of material")
                            else:
                                logger.warning(f"Cannot find valid cards data for material {material.get('id')}")
                        
                        # Detailed logging for first card's structure
                        if cards and len(cards) > 0:
                            logger.debug(f"First card structure: {cards[0]}")
                        
                        # Create a learning item for each card
                        for i, card in enumerate(cards):
                            logger.debug(f"Processing flashcard {i}: front={card.get('front', '')[:30]}, back={card.get('back', '')[:30]}")
                            flashcard_item = LearningItem(
                                id=f"{material.get('id')}-card-{i}",
                                paper_id=material.get("paper_id"),
                                type=LearningItemType.FLASHCARD,
                                title=card.get("front", "")[:50] + "..." if len(card.get("front", "")) > 50 else card.get("front", ""),
                                content=card.get("front", ""),
                                metadata={
                                    "back": card.get("back", "")
                                },
                                difficulty_level=get_difficulty_level(material.get("level", "beginner"))
                            )
                            learning_items.append(flashcard_item)
                        
                        # Skip adding the container item since we've created individual items
                        continue
                    elif material.get("type") == "quiz" and "questions" in material.get("data", {}):
                        learning_item.metadata = {"questions": material.get("data", {}).get("questions", []),
                                               "options": material.get("data", {}).get("questions", [])[0].get("options", []) if material.get("data", {}).get("questions", []) else [],
                                               "correct_answer": material.get("data", {}).get("questions", [])[0].get("correct_answer", 0) if material.get("data", {}).get("questions", []) else 0,
                                               "explanation": material.get("data", {}).get("questions", [])[0].get("explanation", "") if material.get("data", {}).get("questions", []) else ""}
                    elif material.get("type") == "video":
                        # Handle videos in data or at top level
                        videos_data = []
                        
                        # Check for videos in data.videos
                        if "data" in material and "videos" in material["data"]:
                            videos_data = material["data"]["videos"]
                            logger.info(f"Found {len(videos_data)} videos in material data")
                        
                        # Check for videos at top level
                        elif "videos" in material:
                            videos_data = material["videos"]
                            logger.info(f"Found {len(videos_data)} videos at top level")
                        
                        # Log video data for debugging
                        if videos_data:
                            logger.debug(f"Video data structure: {videos_data[0] if videos_data else 'No videos'}")
                        else:
                            logger.warning(f"No videos found for video material {material.get('id')}")
                        
                        # Set metadata with videos
                        learning_item.metadata = {"videos": videos_data}
                        
                        # Log the learning item
                        logger.info(f"Created video learning item: {learning_item.id} with {len(videos_data)} videos")
                    elif material.get("videos"):
                        # Handle case where videos are at the top level
                        videos_data = material.get("videos", [])
                        logger.info(f"Found {len(videos_data)} videos at top level")
                        logger.debug(f"Video data structure: {videos_data[:1]}")  # Log first video for debugging
                        learning_item.metadata = {"videos": videos_data}
                        
                    learning_items.append(learning_item)
                
                logger.info(f"Successfully converted {len(learning_items)} materials to learning items")
                
                # Check if any flashcards were added
                flashcard_count = sum(1 for item in learning_items if item.type == LearningItemType.FLASHCARD)
                logger.info(f"Converted materials include {flashcard_count} flashcard items")
                if flashcard_count == 0:
                    logger.warning("No flashcards were added to learning items, check conversion logic")
        else:
            logger.info(f"Generating new learning materials for paper {paper_id}")
            
            # Generate videos
            try:
                videos = await fetch_youtube_videos(paper_id)
                logger.debug(f"Generated {len(videos)} YouTube videos")
            except Exception as e:
                logger.error(f"Error in video generation: {str(e)}", exc_info=True)
                videos = []
    
            # Generate flashcards
            try:
                flashcards = await generate_flashcards(paper_id)
                logger.debug(f"Generated {len(flashcards)} flashcards")
            except Exception as e:
                logger.error(f"Error in flashcard generation: {str(e)}", exc_info=True)
                flashcards = []
    
            # Generate quiz questions
            try:
                questions = await generate_quiz_questions(paper_id)
                logger.debug(f"Generated {len(questions)} quiz questions")
            except Exception as e:
                logger.error(f"Error in quiz question generation: {str(e)}", exc_info=True)
                questions = []
            
            # Create learning items from the generated materials
            learning_items: List[LearningItem] = []
            
            # Generate text content for all difficulty levels at once
            # This is a critical step - if it fails, we should abort the entire process
            text_content = await generate_text_content(paper_id)
            logger.info(f"Generated {len(text_content)} text content items for paper {paper_id}")
            
            # Process text content based on difficulty level
            for content in text_content:
                # Get the difficulty level from the content
                level_name = content.get("level", "beginner")
                level = get_difficulty_level(level_name)
                content_type = content.get("type", "concepts")
                
                # Create a unique ID for the item
                item_id = f"{paper_id}-{content_type}-{uuid.uuid4().hex[:8]}"
                
                # Determine the LearningItemType based on content type
                if content_type == "concepts":
                    item_type = LearningItemType.CONCEPTS
                elif content_type == "methodology":
                    item_type = LearningItemType.METHODOLOGY
                elif content_type == "results":
                    item_type = LearningItemType.RESULTS
                else:
                    # Fallback (should not happen)
                    item_type = LearningItemType.CONCEPTS
                
                # Create a learning item
                learning_item = LearningItem(
                    id=item_id,
                    paper_id=paper_id,
                    type=item_type,
                    title=content.get("title", "Explanation"),
                    content=content.get("content", ""),
                    metadata=content.get("metadata", {}),
                    difficulty_level=level
                )
                
                learning_items.append(learning_item)
                
                # Store the learning item in the database
                text_material_data = {
                    "paper_id": paper_id,
                    "type": content_type,
                    "level": level_name,
                    "category": "general",
                    "data": {
                        "title": content.get("title", ""),
                        "content": content.get("content", ""),
                        "metadata": content.get("metadata", {})
                    },
                    "order": order_counter
                }
                
                text_item_id = await store_learning_material(text_material_data, use_mock_for_tests=use_mock_for_tests)
                stored_item_ids.append(text_item_id)
                order_counter += 1
                logger.info(f"Stored {content_type} material with ID {text_item_id} for level {level_name}")
            
            # Add additional materials for each difficulty level
            for level, level_name in enumerate(LEVELS, 1):
                # Add video items (limit to 3 per level)
                if videos:
                    video_material_data = {
                        "paper_id": paper_id,
                        "type": "video",
                        "level": level_name,
                        "category": "general",
                        "data": {
                            "title": "Supplemental Videos",
                            "description": "Educational videos to enhance understanding"
                        },
                        "order": order_counter,
                        "videos": videos[:3]  # Limit to 3 videos
                    }
                    
                    try:
                        video_item_id = await store_learning_material(video_material_data, use_mock_for_tests=use_mock_for_tests)
                        stored_item_ids.append(video_item_id)
                        order_counter += 1
                        
                        # Add a video learning item
                        video_item = LearningItem(
                            id=f"{paper_id}-video-{level}",
                            paper_id=paper_id,
                            type=LearningItemType.VIDEO,
                            title="Educational Videos",
                            content="Watch these videos to enhance your understanding",
                            metadata={"videos": videos[:3]},
                            difficulty_level=level
                        )
                        
                        learning_items.append(video_item)
                    except Exception as e:
                        logger.error(f"Error storing video material: {str(e)}", exc_info=True)
                
                # Store flashcards for intermediate and advanced levels
                if level >= 2:
                    try:
                        logger.info(f"Generating flashcards for level {level}")
                        flashcards = await generate_flashcards(paper_id)
                        
                        # Log the generated flashcards for debugging
                        logger.info(f"Generated {len(flashcards)} flashcards for level {level}")
                        if flashcards:
                            logger.debug(f"First flashcard: front='{flashcards[0].front}', back='{flashcards[0].back}'")
                        
                        # Store flashcards in the database
                        flashcard_data = {
                            "id": str(uuid.uuid4()),
                            "paper_id": paper_id,
                            "type": "flashcard",
                            "level": level,
                            "category": "general",
                            "order": order_counter,
                            "data": {
                                "title": f"{LEVELS[level-1].capitalize()} Flashcards",
                                "description": f"Flashcards to test your knowledge of {paper.get('title', 'the paper')}",
                                "cards": [{"front": card.front, "back": card.back} for card in flashcards]
                            }
                        }
                        
                        # Log the flashcard data being stored
                        logger.info(f"Storing flashcard data with {len(flashcards)} cards")
                        logger.debug(f"Flashcard data structure: {flashcard_data}")
                        
                        result = supabase.table("items").insert(flashcard_data).execute()
                        
                        if result.data:
                            stored_item_id = result.data[0]["id"]
                            stored_item_ids.append(stored_item_id)
                            logger.info(f"Stored flashcards with ID: {stored_item_id}")
                            
                            # Create individual learning items for each flashcard
                            for i, card in enumerate(flashcards):
                                flashcard_item = LearningItem(
                                    id=f"{stored_item_id}-card-{i}",
                                    paper_id=paper_id,
                                    type=LearningItemType.FLASHCARD,
                                    title=card.front[:50] + "..." if len(card.front) > 50 else card.front,
                                    content=card.front,
                                    metadata={
                                        "back": card.back
                                    },
                                    difficulty_level=level
                                )
                                learning_items.append(flashcard_item)
                        else:
                            logger.error(f"Failed to store flashcards for level {level}")
                    except Exception as e:
                        logger.error(f"Error storing flashcards: {str(e)}", exc_info=True)
                
                # Add quiz items if appropriate for this level (intermediate and advanced)
                if questions and level >= 2:
                    quiz_material_data = {
                        "paper_id": paper_id,
                        "type": "quiz",
                        "level": level_name,
                        "category": "general",
                        "data": {
                            "title": "Knowledge Check",
                            "description": "Test your understanding with these questions",
                            "questions": [question.dict() for question in questions]  # Convert Pydantic models to dicts
                        },
                        "order": order_counter
                    }
                    
                    try:
                        quiz_item_id = await store_learning_material(quiz_material_data, use_mock_for_tests=use_mock_for_tests)
                        stored_item_ids.append(quiz_item_id)
                        order_counter += 1
                        
                        # Convert each question to a learning item
                        for i, question in enumerate(questions):
                            quiz_item = LearningItem(
                                id=f"{paper_id}-quiz-{level}-{i}",
                                paper_id=paper_id,
                                type=LearningItemType.QUIZ,
                                title=question.question[:50] + "...",
                                content=question.question,
                                metadata={
                                    "options": question.options,
                                    "correct_answer": question.correct_answer,
                                    "explanation": question.explanation
                                },
                                difficulty_level=level
                            )
                            
                            learning_items.append(quiz_item)
                    except Exception as e:
                        logger.error(f"Error storing quiz material: {str(e)}", exc_info=True)
            
            # Reload the materials from the database
            existing_materials = await get_materials_for_paper(paper_id, use_mock_for_tests=use_mock_for_tests)
            
            # Log the counts of materials stored
            logger.info(f"Stored {len(stored_item_ids)} learning materials for paper {paper_id}")
            logger.debug(f"Stored item IDs: {stored_item_ids}")
    
    # Create the learning path
    learning_path = LearningPath(
        id=str(uuid.uuid4()),
        paper_id=paper_id,
        title=f"Learning Path for {paper.get('title', 'Unknown Paper')}",
        description=f"A structured path to understand {paper.get('title', 'this paper')}",
        items=learning_items,
        created_at=datetime.now().isoformat(),
        estimated_time_minutes=len(learning_items) * 10  # Rough estimate: 10 minutes per item
    )
    
    # Cache the learning path
    learning_path_cache[paper_id] = learning_path
    
    return learning_path

async def generate_text_content(paper_id: str) -> List[Dict[str, Any]]:
    """
    Generate explanatory text content for different aspects of the paper.
    
    This function uses the LLM to generate structured learning content from the paper's PDF.
    It organizes content by difficulty level:
    - Key concepts (beginner level)
    - Methodology (intermediate level)
    - Results (advanced level)
    
    Args:
        paper_id: The ID of the paper
        
    Returns:
        List[Dict[str, Any]]: A list of text content items organized by difficulty level
        
    Raises:
        ValueError: If paper not found or PDF not available
        Exception: If content generation fails
    """
    from app.services.llm_service import generate_learning_content_json_with_pdf
    from app.templates.prompts.learning_content import get_learning_content_prompt
    from app.services.pdf_service import get_paper_pdf
    from uuid import UUID
    
    # Get the paper details
    paper = await get_paper_by_id(paper_id)
    if not paper:
        logger.error(f"Paper {paper_id} not found")
        raise ValueError(f"Paper {paper_id} not found")
    
    # Get the PDF path
    pdf_path = await get_paper_pdf(UUID(paper_id))
    if not pdf_path:
        logger.error(f"PDF for paper {paper_id} not found")
        raise ValueError(f"PDF for paper {paper_id} not found")
    
    # Generate the prompt
    title = paper.get("title", "")
    abstract = paper.get("abstract", "")
    prompt = get_learning_content_prompt(title=title, abstract=abstract, pdf_path=pdf_path)
    
    # Generate content using the LLM
    content = await generate_learning_content_json_with_pdf(prompt, pdf_path)
    
    # Organize content by difficulty level
    text_content = []
    
    # Key concepts (beginner level) - use the array directly
    if "key_concepts" in content and isinstance(content["key_concepts"], list):
        # Add as a single learning item with concepts array directly from LLM
        text_content.append({
            "title": "Key Concepts",
            "content": "Key concepts from the paper",
            "level": "beginner",
            "type": "concepts",
            "metadata": {
                "concepts": content["key_concepts"]
            }
        })
    
    # Methodology (intermediate level)
    if "methodology" in content and isinstance(content["methodology"], dict):
        text_content.append({
            "title": content["methodology"].get("title", "Methodology Explained"),
            "content": content["methodology"].get("content", ""),
            "level": "intermediate",
            "type": "methodology"
        })
    
    # Results (advanced level)
    if "results" in content and isinstance(content["results"], dict):
        text_content.append({
            "title": content["results"].get("title", "Results Analysis"),
            "content": content["results"].get("content", ""),
            "level": "advanced",
            "type": "results"
        })
    
    if not text_content:
        logger.error("Failed to generate any text content")
        raise ValueError("Failed to generate any text content")
        
    return text_content

async def get_learning_path(paper_id: str) -> Dict[str, Any]:
    """
    Retrieve an existing learning path or generate a new one if it doesn't exist.
    
    Args:
        paper_id: The ID of the paper
        
    Returns:
        Dict[str, Any]: The learning path data
        
    Raises:
        ValueError: If paper not found or content generation fails
        Exception: If there's an error retrieving or generating the learning path
    """
    logger.info(f"Getting learning path for paper {paper_id}")
    
    # Check if materials already exist for this paper
    existing_materials = await get_materials_for_paper(paper_id)
    
    if existing_materials:
        logger.info(f"Found {len(existing_materials)} existing materials for paper {paper_id}")
        
        # Calculate total estimated time
        total_time = 0
        for material in existing_materials:
            if material["type"] == "text" or material["type"] == "concepts" or material["type"] == "methodology" or material["type"] == "results":
                total_time += 10  # Estimate 10 minutes for reading
            elif material["type"] == "flashcard":
                total_time += len(material.get("data", {}).get("cards", [])) * 2  # 2 minutes per card
            elif material["type"] == "quiz":
                total_time += len(material.get("data", {}).get("questions", [])) * 3  # 3 minutes per question
            
            # Add video times if available
            if material.get("videos"):
                for video in material.get("videos", []):
                    duration = video.get("duration", "10:00")
                    mins, secs = map(int, duration.split(":"))
                    total_time += mins * 60 + secs
        
        return {
            "paper_id": paper_id,
            "materials": existing_materials,
            "estimated_total_time_minutes": total_time,
            "last_modified": existing_materials[0].get("created_at", datetime.now().isoformat()) if existing_materials else datetime.now().isoformat()
        }
    else:
        logger.info(f"No learning materials found for paper {paper_id}, generating new learning path")
        # This will raise an exception if generation fails
        return await generate_learning_path(paper_id)

async def get_learning_items_by_level(paper_id: str, difficulty_level: int, use_mock_for_tests: bool = False) -> List[LearningItem]:
    """
    Get learning items filtered by difficulty level.
    
    Args:
        paper_id: The ID of the paper
        difficulty_level: The difficulty level to filter by (1-3)
        use_mock_for_tests: Set to True in test environments to bypass paper existence check
        
    Returns:
        List[LearningItem]: The filtered learning items
    """
    logger.info(f"Getting learning items for paper {paper_id} with difficulty level {difficulty_level}")
    
    # Get the learning path for this paper
    if paper_id not in learning_path_cache:
        logger.info(f"Learning path not in cache for paper {paper_id}, generating new path")
        await generate_learning_path(paper_id, use_mock_for_tests=use_mock_for_tests)
    else:
        logger.info(f"Using cached learning path for paper {paper_id}")
    
    learning_path = learning_path_cache.get(paper_id)
    if not learning_path:
        logger.warning(f"No learning path found for paper {paper_id} after generation attempt")
        return []
    
    # Filter items by difficulty level
    filtered_items = [item for item in learning_path.items if item.difficulty_level == difficulty_level]
    
    # Log item types for debugging
    item_types = {}
    for item in filtered_items:
        if item.type.value not in item_types:
            item_types[item.type.value] = 0
        item_types[item.type.value] += 1
    
    logger.info(f"Found {len(filtered_items)} items with difficulty level {difficulty_level} for paper {paper_id}")
    logger.info(f"Item types breakdown: {item_types}")
    
    # Log flashcard details if any exist
    flashcards = [item for item in filtered_items if item.type == LearningItemType.FLASHCARD]
    if flashcards:
        logger.info(f"Found {len(flashcards)} flashcard items at difficulty level {difficulty_level}")
        logger.info("FILTERED FLASHCARD CONTENT:")
        for i, card in enumerate(flashcards[:5]):  # Log first 5 flashcards
            logger.info(f"Flashcard {i+1}:")
            logger.info(f"  Front: '{card.content}'")
            logger.info(f"  Back: '{card.metadata.get('back', '')}'")
            logger.info("---")
    
    # Log quiz details if any exist
    quizzes = [item for item in filtered_items if item.type == LearningItemType.QUIZ]
    if quizzes:
        logger.info(f"Found {len(quizzes)} quiz items at difficulty level {difficulty_level}")
        logger.info("FILTERED QUIZ CONTENT:")
        for i, quiz in enumerate(quizzes[:3]):  # Log first 3 quizzes
            logger.info(f"Quiz {i+1}: {quiz.title}")
            if "questions" in quiz.metadata:
                for j, question in enumerate(quiz.metadata.get("questions", [])[:3]):  # Log up to 3 questions per quiz
                    logger.info(f"  Question {j+1}: {question.get('question', '')}")
                    logger.info(f"  Options: {question.get('options', [])}")
                    logger.info(f"  Correct answer: {question.get('correct_answer', '')}")
                    logger.info(f"  Explanation: {question.get('explanation', '')}")
                    logger.info("  ---")
    
    return filtered_items

def get_difficulty_level(level):
    """
    Convert a level value (string or number) to a difficulty level (1-3).
    
    Args:
        level: A string like 'beginner', 'intermediate', 'advanced', or a numeric value
        
    Returns:
        int: Difficulty level from 1 to 3
    """
    # Convert numeric strings to int
    if isinstance(level, str) and level.isdigit():
        level_num = int(level)
        if 1 <= level_num <= 3:
            return level_num
    
    # Handle string values
    if level in LEVELS:
        return LEVELS.index(level) + 1
    
    # If we can't determine the level, default to beginner
    logger.warning(f"Unknown level value: {level}, defaulting to beginner (1)")
    return 1

async def record_progress(item_id: str, user_id: str, completed: bool) -> None:
    """
    Record a user's progress on a learning item.
    
    Args:
        item_id: The ID of the learning item
        user_id: The ID of the user
        completed: Whether the item is completed
    """
    try:
        # Insert a new progress record in the database
        response = supabase.table('progress').insert({
            'user_id': user_id,
            'item_id': item_id,
            'completed': completed
        }).execute()
        
        if not response.data:
            logger.warning(f"Failed to record progress for user {user_id} on item {item_id}")
            return
        
        logger.info(f"Recorded progress for user {user_id} on item {item_id}: completed={completed}")
    except Exception as e:
        logger.error(f"Error recording progress: {str(e)}")
        raise

async def record_answer(user_id: str, question_id: str, answer: str) -> Dict[str, Any]:
    """
    Record a user's answer to a question.
    """
    logger.info(f"Recording answer for user {user_id} on question {question_id}")
    
    try:
        answer_data = {
            "user_id": user_id,
            "question_id": question_id,
            "answer": answer,
            "timestamp": datetime.now().isoformat()
        }
        
        # Insert into answers table
        result = supabase.table("answers").insert(answer_data).execute()
        
        if not result.data:
            raise Exception("Failed to record user answer")
            
        return result.data[0]
        
    except Exception as e:
        logger.error(f"Error recording user answer: {str(e)}")
        raise

async def record_paper_progress(paper_id: str, user_id: str, progress_type: str) -> None:
    """
    Record a user's progress on a paper's summary or related papers.
    
    Args:
        paper_id: The ID of the paper
        user_id: The ID of the user
        progress_type: The type of progress ('summary' or 'related_papers')
    """
    try:
        # Validate progress_type
        if progress_type not in ['summary', 'related_papers']:
            raise ValueError(f"Invalid progress_type: {progress_type}")
        
        # Determine which column to update
        column_name = f"{progress_type}_completed"
        
        # Update the paper record in the database
        response = supabase.table('papers').update({
            column_name: True
        }).eq('id', paper_id).execute()
        
        if not response.data:
            logger.warning(f"No paper found with ID {paper_id} when recording {progress_type} progress")
            return
        
        logger.info(f"Recorded {progress_type} progress for user {user_id} on paper {paper_id}")
    except Exception as e:
        logger.error(f"Error recording paper progress: {str(e)}")
        raise

async def get_user_progress(user_id: str, paper_id: Optional[str] = None) -> List[UserProgressRecord]:
    """
    Get a user's progress on learning materials.
    
    Args:
        user_id: The ID of the user
        paper_id: Optional paper ID to filter by
        
    Returns:
        List[UserProgressRecord]: The user's progress records
    """
    try:
        # Query the progress table in Supabase
        query = supabase.table('progress').select('*').eq('user_id', user_id)
        
        # If paper_id is provided, we need to join with the items table to filter by paper_id
        # This would require a more complex query in a production environment
        # For now, we'll just return all progress records for the user
        
        response = query.execute()
        
        if not response.data:
            return []
        
        # Convert the response data to UserProgressRecord objects
        records = []
        for item in response.data:
            records.append(UserProgressRecord(
                user_id=item['user_id'],
                item_id=item['item_id'],
                completed=item['completed']
            ))
        
        return records
    except Exception as e:
        logger.error(f"Error getting user progress: {str(e)}")
        raise

async def submit_answer(question_id: str, user_id: str, answer_index: int) -> AnswerResult:
    """
    Submit an answer to a quiz question and evaluate it.
    
    Args:
        question_id: The ID of the quiz question
        user_id: The ID of the user
        answer_index: The index of the selected answer
        
    Returns:
        AnswerResult: The result of the answer submission
    """
    # Find the learning item for this question
    # In a real implementation, this would query the database
    
    # Mock implementation - look through all cached learning paths
    correct_answer = None
    explanation = None
    
    for learning_path in learning_path_cache.values():
        for item in learning_path.items:
            if item.id == question_id and item.type == LearningItemType.QUIZ:
                correct_answer = item.metadata.get("correct_answer")
                explanation = item.metadata.get("explanation")
                break
        if correct_answer is not None:
            break
    
    # If we couldn't find the question, return a default response
    if correct_answer is None:
        return AnswerResult(
            is_correct=False,
            correct_answer=0,  # Default
            explanation="Question not found",
            user_id=user_id,
            question_id=question_id,
            selected_answer=answer_index,
            timestamp=datetime.now().isoformat()
        )
    
    # Evaluate the answer
    is_correct = answer_index == correct_answer
    
    # Record the result
    result = AnswerResult(
        is_correct=is_correct,
        correct_answer=correct_answer,
        explanation=explanation or "No explanation available",
        user_id=user_id,
        question_id=question_id,
        selected_answer=answer_index,
        timestamp=datetime.now().isoformat()
    )
    
    # In a real implementation, we would store this result in the database
    logger.info(f"User {user_id} answered question {question_id}: {'Correct' if is_correct else 'Incorrect'}")
    
    return result 