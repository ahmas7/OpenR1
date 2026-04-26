"""
R1 - Ambient Context Placeholder
"""
import logging

logger = logging.getLogger("R1:ambient")

class AmbientContextService:
    def __init__(self):
        pass
    def get_context_summary(self, *args, **kwargs):
        return ""

_service = None
def get_ambient_context_service():
    global _service
    if _service is None:
        _service = AmbientContextService()
    return _service
