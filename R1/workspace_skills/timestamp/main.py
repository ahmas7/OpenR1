"""
Timestamp Skill - Returns current time in various formats
"""
from datetime import datetime
from typing import Dict, Any


def register():
    """Register the skill handler"""
    return handle_timestamp


def handle_timestamp(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns the current timestamp in various formats.
    
    Args:
        context: Optional context with 'format' key:
            - "iso": ISO 8601 format (default)
            - "readable": Human readable format
            - "unix": Unix timestamp
            - "all": All formats
    
    Returns:
        Dict with timestamp information
    """
    now = datetime.now()
    format_type = context.get("format", "all") if context else "all"
    
    result = {}
    
    if format_type == "iso" or format_type == "all":
        result["iso"] = now.isoformat()
    
    if format_type == "readable" or format_type == "all":
        result["readable"] = now.strftime("%Y-%m-%d %I:%M %p")
    
    if format_type == "unix" or format_type == "all":
        result["unix"] = int(now.timestamp())
    
    if format_type == "all":
        result["timezone"] = str(now.astimezone().tzinfo)
    
    return {
        "format_used": format_type,
        "timestamp": result
    }
