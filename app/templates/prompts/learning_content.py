from jinja2 import Template
from typing import Optional

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
    # Read the template file
    with open("app/templates/prompts/learning_content.j2", "r") as f:
        template_content = f.read()
    
    # Create a Jinja2 template
    template = Template(template_content)
    
    # Render the template with the provided values
    prompt = template.render(
        title=title,
        abstract=abstract,
        full_text=full_text,
        pdf_path=pdf_path
    )
    
    return prompt 