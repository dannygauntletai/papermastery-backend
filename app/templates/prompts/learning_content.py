from jinja2 import Template
from typing import Optional, List, Dict
import os

def _get_template(template_filename):
    """
    Helper function to load a Jinja2 template from the prompts directory.
    
    Args:
        template_filename: The filename of the template to load
        
    Returns:
        Template: A Jinja2 template object
    """
    template_path = os.path.join(os.path.dirname(__file__), template_filename)
    with open(template_path, "r") as f:
        template_content = f.read()
    return Template(template_content)

def get_learning_content_prompt(
    title: str, 
    abstract: Optional[str] = None, 
    full_text: Optional[str] = None,
    pdf_path: Optional[str] = None
) -> str:
    """
    Generate a prompt for the LLM to extract structured learning content from a paper.
    
    Args:
        title: The title of the paper
        abstract: Optional abstract of the paper
        full_text: Optional full text of the paper
        pdf_path: Optional path to the PDF file
        
    Returns:
        str: The formatted prompt
    """
    template = _get_template('learning_content.j2')
    
    # Render the template with the provided values
    prompt = template.render(
        title=title,
        abstract=abstract,
        full_text=full_text,
        pdf_path=pdf_path
    )
    
    return prompt

def get_additional_quiz_questions_prompt(
    paper_title: str,
    paper_content: str,
    correct_answers: List[Dict],
    incorrect_answers: List[Dict],
    num_questions: int = 10
) -> str:
    """
    Get the prompt for generating additional quiz questions based on user performance.
    
    Args:
        paper_title: The title of the paper
        paper_content: The content of the paper
        correct_answers: List of questions answered correctly
        incorrect_answers: List of questions answered incorrectly
        num_questions: Number of questions to generate (default: 10)
        
    Returns:
        str: The formatted prompt
    """
    template = _get_template('additional_quiz_questions.j2')
    return template.render(
        paper_title=paper_title,
        paper_content=paper_content,
        correct_answers=correct_answers,
        incorrect_answers=incorrect_answers,
        num_questions=num_questions
    ) 