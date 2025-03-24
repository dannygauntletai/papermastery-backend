"""
Authentication utilities for the PaperMastery API.
"""

from fastapi import Request, HTTPException, status
from app.dependencies import get_current_user

# Re-export get_current_user for direct import from auth module
__all__ = ['get_current_user'] 