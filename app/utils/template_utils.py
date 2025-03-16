import os
from jinja2 import Environment, FileSystemLoader

def get_template(template_path: str):
    """
    Get a Jinja2 template from the templates directory.
    
    Args:
        template_path: The path to the template relative to the templates directory
        
    Returns:
        A Jinja2 template object
    """
    templates_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'app', 'templates')
    env = Environment(loader=FileSystemLoader(templates_dir))
    return env.get_template(template_path) 